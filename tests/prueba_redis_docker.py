"""Prueba manual contra Redis REAL en Docker (3 contenedores en una red propia).

    PYTHONPATH=. python tests/prueba_redis_docker.py

Los nodos corren en este proceso (TCP en localhost); la partición se aplica a la
mensajería (SimNetwork) y a la replicación de Redis (docker network disconnect).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

from coord.config import DEFAULTS
from coord.net import SimNetwork
from coord.node import Node, LIDER
from coord.sim import wait_for, leaders, write
from coord.store import RedisStore

IDS = (1, 2, 3)
PWD = "clave-test"
NET = "coordnet"


def sh(*a, check=True):
    return subprocess.run(a, capture_output=True, text=True, check=check)


def main():
    sh("docker", "network", "create", NET, check=False)
    for i in IDS:
        sh("docker", "rm", "-f", f"r{i}", check=False)
        sh("docker", "run", "-d", "--name", f"r{i}", "-p", f"{6390 + i}:6379",
           "redis:7", "redis-server", "--requirepass", PWD, "--masterauth", PWD)
        # bridge (puerto publicado al host) + coordnet (replicación); la partición corta solo coordnet
        sh("docker", "network", "connect", NET, f"r{i}")
    time.sleep(3)
    cfg = dict(DEFAULTS)
    cfg.update(heartbeat_interval=0.5, heartbeat_timeout=2.5, election_timeout=1.5, rpc_timeout=1.0)
    cfg["nodes"] = {i: {"host": "127.0.0.1", "port": 18900 + i, "redis_host": f"r{i}",
                        "redis_port": 6379} for i in IDS}
    net = SimNetwork()
    logd = tempfile.mkdtemp(prefix="coord-redis-")
    nodes = {i: Node(i, cfg, RedisStore(i, "127.0.0.1", 6390 + i, PWD), os.path.join(logd, f"n{i}"),
                     simnet=net, quiet=True) for i in IDS}
    ok = True
    try:
        for n in nodes.values():
            n.start()
        assert wait_for(lambda: leaders(nodes) == [3] and all(n.leader_id == 3 for n in nodes.values()), 20)
        print("1) líder inicial 3; roles Redis:", {i: n.store.role() for i, n in nodes.items()})
        assert write(nodes, 1, "set", "nodo1", cpu=4, mem=4096, bw=100)["ok"]
        assert wait_for(lambda: all(n.store.get("nodo1") for n in nodes.values()), 10)
        print("2) escritura vía seguidor replicada a los 3 Redis")
        try:
            nodes[1].store.put("x", {})
            print("   FALLO: réplica aceptó escritura"); ok = False
        except Exception as e:
            print("   escritura directa a réplica rechazada:", type(e).__name__)

        net.isolate(3, list(IDS))
        sh("docker", "network", "disconnect", NET, "r3")
        assert wait_for(lambda: nodes[2].state == LIDER, 25)
        print("3) partición: nuevo líder 2; roles Redis:", {i: nodes[i].store.role() for i in IDS})
        time.sleep(3)
        a = write(nodes, 3, "allocate", "nodo1", cpu=1, mem=100, bw=1)
        b = write(nodes, 2, "allocate", "nodo1", cpu=2, mem=200, bw=2)
        print("   escritura líder viejo:", a["ok"], "sin quórum:", not a["quorum"], "| líder nuevo:", b["ok"])
        sh("docker", "network", "connect", NET, "r3")
        net.heal()
        assert wait_for(lambda: nodes[3].leader_id == 2 and nodes[3].rejoin_pending is None, 30)
        def vista(n):
            return {k: (v["cpu"], v["mem"], v["bw"], v["vv"]) for k, v in n.store.all().items()}
        wait_for(lambda: all(vista(n) == vista(nodes[2]) for n in nodes.values()), 20)
        print("4) conflictos en nodo 2:", nodes[2].conflog.stats())
        vistas = [vista(n) for n in nodes.values()]
        print("   vistas:", vistas)
        conv = all(v == vistas[0] for v in vistas)
        print("   convergencia:", conv, "| roles Redis:", {i: n.store.role() for i, n in nodes.items()})
        print("   estado final nodo1:", vistas[0].get("nodo1"))
        ok = ok and conv and nodes[2].conflog.stats()["detectados"] == 1
    finally:
        for n in nodes.values():
            n.stop()
        for i in IDS:
            sh("docker", "rm", "-f", f"r{i}", check=False)
        sh("docker", "network", "rm", NET, check=False)
        shutil.rmtree(logd, ignore_errors=True)
    print("RESULTADO:", "OK" if ok else "FALLO")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
