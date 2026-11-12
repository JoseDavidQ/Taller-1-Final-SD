"""Reloj lógico de Lamport (Lamport, 1978) y vectores de versión (Fidge 1988, Mattern 1989)."""
import threading


class LamportClock:
    """Reloj de Lamport: tick() en eventos locales/envíos, update() al recibir."""

    def __init__(self, start=0):
        self._v = start
        self._lock = threading.Lock()

    def tick(self):
        with self._lock:
            self._v += 1
            return self._v

    def update(self, received):
        with self._lock:
            self._v = max(self._v, int(received)) + 1
            return self._v

    @property
    def value(self):
        with self._lock:
            return self._v


# ---- Vectores de versión: dict {id_nodo(str): contador(int)} ----

def vv_increment(vv, node_id):
    nuevo = dict(vv or {})
    k = str(node_id)
    nuevo[k] = nuevo.get(k, 0) + 1
    return nuevo


def vv_merge(a, b):
    """Máximo componente a componente."""
    res = dict(a or {})
    for k, v in (b or {}).items():
        res[k] = max(res.get(k, 0), v)
    return res


def vv_compare(a, b):
    """Compara dos vectores de versión.

    Devuelve:
      'equal'      a == b
      'before'     a es dominado por b (a ocurrió antes que b)
      'after'      a domina a b
      'concurrent' ninguno domina al otro  -> conflicto
    """
    a = a or {}
    b = b or {}
    keys = set(a) | set(b)
    a_le_b = all(a.get(k, 0) <= b.get(k, 0) for k in keys)
    b_le_a = all(b.get(k, 0) <= a.get(k, 0) for k in keys)
    if a_le_b and b_le_a:
        return "equal"
    if a_le_b:
        return "before"
    if b_le_a:
        return "after"
    return "concurrent"
