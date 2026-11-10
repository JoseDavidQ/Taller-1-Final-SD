import unittest

from coord.clock import LamportClock, vv_compare, vv_increment, vv_merge
from coord.reconcile import ConflictLog, merge_remote, winner
from coord.store import MemoryStore


class VectoresTest(unittest.TestCase):
    def test_comparacion(self):
        self.assertEqual(vv_compare({"1": 1}, {"1": 1}), "equal")
        self.assertEqual(vv_compare({"1": 1}, {"1": 2}), "before")
        self.assertEqual(vv_compare({"1": 2, "2": 1}, {"1": 1}), "after")
        self.assertEqual(vv_compare({"3": 3}, {"3": 1, "2": 1}), "concurrent")

    def test_merge_e_incremento(self):
        self.assertEqual(vv_merge({"1": 2}, {"1": 1, "2": 4}), {"1": 2, "2": 4})
        self.assertEqual(vv_increment({"1": 2}, 1), {"1": 3})

    def test_lamport(self):
        c = LamportClock()
        self.assertEqual(c.tick(), 1)
        self.assertEqual(c.update(10), 11)
        self.assertEqual(c.tick(), 12)


class ReglaTest(unittest.TestCase):
    def test_gana_mayor_lamport(self):
        a = {"lamport": 5, "writer": 3}
        b = {"lamport": 7, "writer": 2}
        self.assertIs(winner(a, b)[0], b)

    def test_empate_gana_menor_id(self):
        a = {"lamport": 5, "writer": 3}
        b = {"lamport": 5, "writer": 2}
        self.assertIs(winner(a, b)[0], b)
        self.assertIs(winner(b, a)[0], b)  # simétrica


class MergeTest(unittest.TestCase):
    def setUp(self):
        MemoryStore.reset()

    def test_concurrente_se_detecta_y_resuelve(self):
        s = MemoryStore(1)
        s.put("r", {"cpu": 1, "mem": 1, "bw": 1, "vv": {"3": 3}, "lamport": 81, "writer": 3})
        remoto = {"r": {"cpu": 9, "mem": 9, "bw": 9, "vv": {"3": 1, "2": 1}, "lamport": 63, "writer": 2}}
        log = ConflictLog()
        stats = merge_remote(s, remoto, 3, LamportClock(100), log, log=lambda m: None)
        self.assertEqual((stats["detectados"], stats["resueltos"]), (1, 1))
        res = s.get("r")
        self.assertEqual(res["cpu"], 1)  # ganó Lamport 81
        self.assertEqual(vv_compare(res["vv"], {"3": 3}), "after")   # domina a ambas
        self.assertEqual(vv_compare(res["vv"], {"3": 1, "2": 1}), "after")

    def test_avance_simple_no_es_conflicto(self):
        s = MemoryStore(1)
        s.put("r", {"cpu": 1, "mem": 1, "bw": 1, "vv": {"3": 1}, "lamport": 1, "writer": 3})
        remoto = {"r": {"cpu": 5, "mem": 5, "bw": 5, "vv": {"3": 1, "2": 1}, "lamport": 2, "writer": 2}}
        log = ConflictLog()
        stats = merge_remote(s, remoto, 3, LamportClock(), log, log=lambda m: None)
        self.assertEqual(stats["detectados"], 0)
        self.assertEqual(s.get("r")["cpu"], 5)


if __name__ == "__main__":
    unittest.main()
