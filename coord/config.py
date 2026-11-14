"""Carga de la configuración del clúster (config/cluster.json)."""
import json
import os

DEFAULTS = {
    "heartbeat_interval": 1.0,   # s entre latidos del líder
    "heartbeat_timeout": 4.0,    # s sin latido => el líder se considera caído
    "election_timeout": 3.0,     # s esperando el COORDINATOR de un nodo superior
    "rpc_timeout": 1.5,          # s por petición entre nodos
    "require_quorum_for_writes": False,  # False = AP (sigue escribiendo); True = CP
    "redis_password_env": "REDIS_PASSWORD",
}


def load(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    cfg["nodes"] = {int(k): v for k, v in cfg["nodes"].items()}
    for nid, n in cfg["nodes"].items():
        n.setdefault("redis_port", 6379)
        n.setdefault("redis_host", n["host"])  # dirección con que los demás ven su Redis
        n.setdefault("ssh_host", n["host"])    # dirección para administrar por SSH (IP pública, fuera de la tailnet)
    return cfg


def redis_password(cfg):
    return os.environ.get(cfg.get("redis_password_env", "REDIS_PASSWORD")) or None
