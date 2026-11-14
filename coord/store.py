"""Almacenamiento del inventario.

* RedisStore  : producción. Replicación maestro-réplica de Redis. Solo el maestro
                acepta escrituras; las réplicas son de solo lectura (Redis lo exige).
                El rol cambia en caliente con REPLICAOF según quién sea el líder.
* MemoryStore : simulación local sin Redis (pruebas y demo en un solo equipo).
                Imita el mismo contrato: maestro, réplicas de solo lectura y
                replicación que se corta cuando la red está particionada.
"""
import copy
import json
import threading


class ReadOnlyError(Exception):
    """Se intentó escribir en una réplica."""


class RedisStore:
    PREFIX = "inv:"

    def __init__(self, node_id, host="127.0.0.1", port=6379, password=None):
        import redis  # import perezoso: la simulación no lo necesita

        self.id = node_id
        self.r = redis.Redis(host=host, port=port, password=password,
                             decode_responses=True, socket_timeout=2,
                             socket_connect_timeout=2)

    def get(self, key):
        v = self.r.get(self.PREFIX + key)
        return json.loads(v) if v else None

    def put(self, key, entry):
        try:
            self.r.set(self.PREFIX + key, json.dumps(entry, sort_keys=True))
        except Exception as e:  # redis.exceptions.ReadOnlyError, etc.
            if "READONLY" in str(e).upper():
                raise ReadOnlyError(str(e))
            raise

    def all(self):
        keys = sorted(self.r.scan_iter(self.PREFIX + "*"))
        if not keys:
            return {}
        vals = self.r.mget(keys)
        return {k[len(self.PREFIX):]: json.loads(v) for k, v in zip(keys, vals) if v}

    def promote(self):
        self.r.execute_command("REPLICAOF", "NO", "ONE")

    def follow(self, peer_id, host, port):
        self.r.execute_command("REPLICAOF", host, int(port))

    def role(self):
        return self.r.info("replication").get("role", "?")

    def sync(self):  # Redis reconecta y resincroniza solo
        pass


class MemoryStore:
    registry = {}
    _reg_lock = threading.Lock()

    def __init__(self, node_id, reach=None):
        self.id = node_id
        self.data = {}
        self.master = None  # None => soy maestro
        self.reach = reach or (lambda a, b: True)
        self.lock = threading.RLock()
        with MemoryStore._reg_lock:
            MemoryStore.registry[node_id] = self

    @classmethod
    def reset(cls):
        with cls._reg_lock:
            cls.registry = {}

    def get(self, key):
        with self.lock:
            v = self.data.get(key)
            return copy.deepcopy(v) if v else None

    def put(self, key, entry):
        with self.lock:
            if self.master is not None:
                raise ReadOnlyError("READONLY: réplica de solo lectura")
            self.data[key] = copy.deepcopy(entry)
            followers = [s for s in MemoryStore.registry.values() if s.master == self.id]
        for s in followers:
            if self.reach(self.id, s.id):  # replicación asíncrona: se pierde si hay partición
                with s.lock:
                    s.data[key] = copy.deepcopy(entry)

    def all(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def promote(self):
        with self.lock:
            self.master = None

    def follow(self, peer_id, host=None, port=None):
        with self.lock:
            self.master = peer_id
        self.sync()

    def role(self):
        return "master" if self.master is None else "slave"

    def sync(self):
        """Resincronización completa con el maestro si hay conectividad."""
        with self.lock:
            m = self.master
        if m is None:
            return
        src = MemoryStore.registry.get(m)
        if src is not None and src.master is None and self.reach(self.id, m):
            snap = src.all()
            with self.lock:
                self.data = snap
