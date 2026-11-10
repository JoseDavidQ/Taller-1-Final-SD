"""Detección y resolución de conflictos al reconectar la red (punto 3.3).

Detección : dos escrituras sobre el mismo recurso son concurrentes si sus
            vectores de versión no se dominan entre sí.
Regla     : gana la escritura con MAYOR marca de Lamport; en empate gana el
            identificador de nodo (escritor) MENOR.  La perdedora no se descarta
            en silencio: queda en conflictos-<nodo>.jsonl para auditoría.
Resultado : la entrada resuelta lleva el vector fusionado (máximo componente a
            componente) + 1 del nodo que resuelve, de modo que domina a ambas
            versiones y converge en todos los nodos.
"""
import json
import os
import threading
import time

from .clock import vv_compare, vv_merge, vv_increment

REGLA = "mayor Lamport; empate -> menor id de escritor"


def winner(a, b):
    """Devuelve (ganadora, perdedora) según la regla documentada."""
    ka = (-a.get("lamport", 0), a.get("writer", 0))
    kb = (-b.get("lamport", 0), b.get("writer", 0))
    return (a, b) if ka <= kb else (b, a)


class ConflictLog:
    def __init__(self, path=None):
        self.path = path
        self.detected = 0
        self.resolved = 0
        self.fast_forward = 0
        self._lock = threading.Lock()

    def record(self, rec):
        if not self.path:
            return
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    def stats(self):
        return {"detectados": self.detected, "resueltos": self.resolved,
                "avance_simple": self.fast_forward}


def merge_remote(store, remote_entries, my_id, clock, conflog, log=print):
    """Funde el inventario de un líder antiguo dentro del inventario del líder actual.

    Se ejecuta en el NUEVO líder (única autoridad de escritura)."""
    stats = {"detectados": 0, "resueltos": 0, "avance_simple": 0}
    local_all = store.all()
    for res, remote in remote_entries.items():
        local = local_all.get(res)
        if local is None:
            store.put(res, remote)
            stats["avance_simple"] += 1
            conflog.fast_forward += 1
            log(f"RECONCILIACIÓN {res}: recurso nuevo del líder antiguo, se adopta")
            continue
        rel = vv_compare(local.get("vv"), remote.get("vv"))
        if rel in ("equal", "after"):
            continue  # el local ya contiene (o domina) lo remoto
        if rel == "before":
            store.put(res, remote)  # lo remoto es posterior: avance simple
            stats["avance_simple"] += 1
            conflog.fast_forward += 1
            log(f"RECONCILIACIÓN {res}: versión remota domina a la local, se adopta")
            continue
        # ---- concurrentes: conflicto ----
        stats["detectados"] += 1
        conflog.detected += 1
        win, lose = winner(local, remote)
        merged = dict(win)
        merged["vv"] = vv_increment(vv_merge(local.get("vv"), remote.get("vv")), my_id)
        merged["lamport"] = clock.tick()
        merged["resolved_by"] = my_id
        merged["conflict"] = True
        store.put(res, merged)
        stats["resueltos"] += 1
        conflog.resolved += 1
        conflog.record({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "recurso": res, "regla": REGLA,
            "ganadora": win, "perdedora": lose, "resultado": merged,
        })
        log(f"CONFLICTO {res}: vv local={local.get('vv')} vs remoto={remote.get('vv')} "
            f"-> concurrentes. Gana escritor {win.get('writer')} "
            f"(Lamport {win.get('lamport')}) sobre escritor {lose.get('writer')} "
            f"(Lamport {lose.get('lamport')})")
    return stats
