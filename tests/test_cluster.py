"""Pruebas de integración: nodos reales sobre TCP local con red simulada."""
import shutil
import unittest

from coord.sim import make_cluster, wait_for, leaders, write
from coord.node import LIDER
from coord.store import MemoryStore


class ClusterTest(unittest.TestCase):
    def arrancar(self, **kw):
        self.cfg, self.net, self.nodes, self.dir = make_cluster(quiet=True, **kw)
        for n in self.nodes.values():
            n.start()
        self.addCleanup(lambda: [n.stop() for n in self.nodes.values()])
        self.addCleanup(lambda: shutil.rmtree(self.dir, ignore_errors=True))
        self.assertTrue(wait_for(lambda: leaders(self.nodes) == [3]
                                 and all(n.leader_id == 3 for n in self.nodes.values())))

    def test_lider_unico_y_reeleccion(self):
        self.arrancar()
        self.nodes[3].stop()
        self.assertTrue(wait_for(lambda: leaders(self.nodes, {1, 2}) == [2], timeout=15))
        self.assertEqual(self.nodes[1].leader_id, 2)

    def test_solo_el_lider_asigna_y_seguidor_reenvia(self):
        self.arrancar()
        r = write(self.nodes, 1, "set", "nodo1", cpu=2, mem=100, bw=5)
        self.assertTrue(r["ok"])
        self.assertEqual(r["coordinador"], 3)
        self.assertTrue(wait_for(lambda: self.nodes[1].store.get("nodo1") is not None))
        # escritura directa a una réplica es rechazada por el almacén
        from coord.store import ReadOnlyError
        with self.assertRaises(ReadOnlyError):
            self.nodes[1].store.put("x", {})

    def test_lider_falso_es_rechazado(self):
        self.arrancar()
        r = self.nodes[1].handle({"type": "fake_leader"})
        self.assertTrue(r["ok"])
        self.assertFalse(any(v for v in r["respuestas"].values()))
        self.assertEqual(leaders(self.nodes), [3])
        self.assertTrue(all(n.leader_id == 3 for n in self.nodes.values()))

    def test_particion_conflicto_y_convergencia(self):
        self.arrancar()
        write(self.nodes, 3, "set", "nodo1", cpu=4, mem=4096, bw=100)
        wait_for(lambda: all(n.store.get("nodo1") for n in self.nodes.values()))
        self.net.isolate(3, [1, 2, 3])
        self.assertTrue(wait_for(lambda: self.nodes[2].state == LIDER, timeout=15))
        import time; time.sleep(1.6)
        viejo = write(self.nodes, 3, "allocate", "nodo1", cpu=1, mem=100, bw=1)
        nuevo = write(self.nodes, 2, "allocate", "nodo1", cpu=2, mem=200, bw=2)
        self.assertTrue(viejo["ok"] and nuevo["ok"])
        self.assertFalse(viejo["quorum"])  # el líder aislado escribe sin quórum
        self.assertEqual(len(self.nodes[3].divergent), 1)
        self.net.heal()
        self.assertTrue(wait_for(lambda: self.nodes[3].leader_id == 2
                                 and self.nodes[3].rejoin_pending is None, timeout=20))
        time.sleep(0.8)
        st = self.nodes[2].conflog.stats()
        self.assertEqual((st["detectados"], st["resueltos"]), (1, 1))
        vistas = [{k: (v["cpu"], v["mem"], v["bw"], v["vv"]) for k, v in n.store.all().items()}
                  for n in self.nodes.values()]
        self.assertTrue(all(v == vistas[0] for v in vistas))
        self.assertEqual(leaders(self.nodes), [2])

    def test_modo_cp_rechaza_sin_quorum(self):
        self.arrancar(require_quorum=True)
        self.net.isolate(3, [1, 2, 3])
        import time; time.sleep(1.6)
        r = write(self.nodes, 3, "set", "nodo3", cpu=1, mem=1, bw=1)
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
