"""Simulación local completa (sin VMs ni Redis): 3 nodos reales sobre TCP en localhost.

Ejecuta el escenario del taller de principio a fin:
  1) elección inicial  2) caída del líder y reelección  3) partición con doble
  escritura sobre el mismo recurso  4) reconexión, detección de conflicto y
  convergencia.

    python -m coord.sim            # imprime los logs de los nodos
"""
import os
import shutil
import sys
import tempfile
import time

from .config import DEFAULTS
from .net import SimNetwork
from .node import Node, LIDER
from .store import MemoryStore

BASE_PORT = 18700


def make_cluster(n=3, log_dir=None, fast=True, quiet=False, require_quorum=False):
    cfg = dict(DEFAULTS)
    if fast:
        cfg.update(heartbeat_interval=0.25, heartbeat_timeout=1.2, election_timeout=1.0, rpc_timeout=0.6)
    cfg["require_quorum_for_writes"] = require_quorum
    cfg["nodes"] = {i: {"host": "127.0.0.1", "port": BASE_PORT + i, "redis_host": "127.0.0.1",
                        "redis_port": 6379} for i in range(1, n + 1)}
    log_dir = log_dir or tempfile.mkdtemp(prefix="coord-sim-")
    MemoryStore.reset()
    net = SimNetwork()
    nodes = {}
    for i in cfg["nodes"]:
        nodes[i] = Node(i, cfg, MemoryStore(i, reach=net.up), os.path.join(log_dir, f"n{i}"),
                        simnet=net, quiet=quiet)
    return cfg, net, nodes, log_dir


def wait_for(cond, timeout=15.0, step=0.1):
    fin = time.time() + timeout
    while time.time() < fin:
        if cond():
            return True
        time.sleep(step)
    return False


def leaders(nodes, only=None):
    return [i for i, n in nodes.items() if n.state == LIDER and (only is None or i in only)]


def write(nodes, via, op, res, **kw):
    return nodes[via].handle(dict(type="write", op=op, resource=res, **kw))


def main():
    cfg, net, nodes, log_dir = make_cluster(quiet=False)
    ids = sorted(nodes)
    A, B = ids[-1], ids[-2]          # A = mayor id (líder inicial), B = segundo mayor
    resto = [i for i in ids if i != A]
    print(f"[sim] logs en {log_dir}\n")
    for n in nodes.values():
        n.start()
    assert wait_for(lambda: leaders(nodes) == [A] and all(n.leader_id == A for n in nodes.values()))
    print(f"\n[sim] === 1) líder inicial = nodo {A} ===\n")
    for i in ids:
        write(nodes, i, "set", f"nodo{i}", cpu=2, mem=2048, bw=100)
    time.sleep(0.5)

    print(f"\n[sim] === 2) cae el líder (nodo {A}) ===\n")
    nodes[A].stop()
    assert wait_for(lambda: leaders(nodes, set(resto)) == [B], timeout=15)
    print(f"\n[sim] nuevo líder: nodo {B}\n")
    net.heal()
    nodes[A] = Node(A, cfg, MemoryStore(A, reach=net.up), os.path.join(log_dir, f"n{A}b"), simnet=net)
    nodes[A].start()
    assert wait_for(lambda: nodes[A].leader_id == B and nodes[A].state != LIDER, timeout=15)
    print(f"\n[sim] nodo {A} reiniciado y reconoce al líder {B} (no hay 'bullying' de vuelta)\n")

    print(f"\n[sim] === 3) partición: se aísla al líder (nodo {B}) ===\n")
    net.isolate(B, ids)
    assert wait_for(lambda: nodes[A].state == LIDER, timeout=20)
    print(f"\n[sim] ahora hay DOS líderes creyéndose líderes: {B} (aislado, término viejo) y {A}\n")
    time.sleep(1.6)  # el líder aislado pierde los acks de latido => escribe SIN quórum
    r_old = write(nodes, B, "allocate", "nodo1", cpu=1, mem=256, bw=10)
    r_new = write(nodes, A, "allocate", "nodo1", cpu=1, mem=512, bw=20)
    r_f = write(nodes, 1, "allocate", "nodo1", cpu=0, mem=1, bw=0)
    print("[sim] escritura en líder viejo:", r_old.get("ok"), "| en líder nuevo:", r_new.get("ok"),
          "| vía seguidor 1:", r_f.get("ok"), "\n")

    print("\n[sim] === 4) se reconecta la red ===\n")
    net.heal()
    assert wait_for(lambda: leaders(nodes) == [A] and nodes[B].rejoin_pending is None
                    and nodes[B].leader_id == A, timeout=25)
    time.sleep(1.5)
    inv = {i: nodes[i].store.all() for i in nodes}
    vista = lambda d: {k: (v["cpu"], v["mem"], v["bw"], v["vv"]) for k, v in d.items()}
    iguales = all(vista(inv[i]) == vista(inv[1]) for i in inv)
    print(f"\n[sim] conflictos nodo {A}:", nodes[A].conflog.stats(), "| convergencia:", iguales)
    for n in nodes.values():
        n.stop()
    return 0 if iguales else 1


if __name__ == "__main__":
    sys.exit(main())
