"""Nodo del sistema: elección de coordinador (algoritmo del matón) + inventario replicado.

Estados: seguidor | candidato | líder.

Algoritmo del matón (Garcia-Molina, 1982) con tres refuerzos para particiones:
  1. TÉRMINOS: cada líder elegido lleva un número de término creciente.
  2. VOTO ÚNICO por término y aceptación solo si el candidato es el mayor id
     vivo que el votante conoce  ->  el ganador reúne MAYORÍA (quórum) de votos.
  3. CERTIFICADO: todo anuncio de líder (COORDINATOR / latido) lleva la lista de
     votantes; quien no votó verifica con los votantes (VERIFY). Un nodo que se
     autoproclama líder sin haber ganado queda RECHAZADO.

Si un líder aislado sigue creyéndose líder (término viejo), al reconectar ve un
término mayor con certificado válido, se degrada a seguidor, entrega sus
escrituras al nuevo líder (REJOIN) y se convierte en réplica de su Redis.
"""
import argparse
import json
import os
import random
import sys
import threading
import time

from . import config as cfgmod
from .clock import LamportClock, vv_increment
from .net import Server, request
from .reconcile import ConflictLog, merge_remote, REGLA
from .store import MemoryStore, ReadOnlyError, RedisStore

SEGUIDOR, CANDIDATO, LIDER = "seguidor", "candidato", "líder"


class Node:
    def __init__(self, node_id, cfg, store, log_dir="logs", simnet=None, quiet=False):
        self.id = int(node_id)
        self.cfg = cfg
        self.store = store
        self.simnet = simnet
        self.quiet = quiet
        self.all_ids = sorted(cfg["nodes"])
        self.peers = [i for i in self.all_ids if i != self.id]
        self.majority = len(self.all_ids) // 2 + 1
        self.hb_int = cfg["heartbeat_interval"]
        self.hb_timeout = cfg["heartbeat_timeout"]
        self.el_timeout = cfg["election_timeout"]
        self.rpc_timeout = cfg["rpc_timeout"]
        self.require_quorum = cfg["require_quorum_for_writes"]

        self.clock = LamportClock()
        self.lock = threading.RLock()
        self.wlock = threading.Lock()
        self.stop_ev = threading.Event()

        # --- estado de coordinación ---
        self.state = SEGUIDOR
        self.term = 0
        self.max_term_seen = 0
        self.leader_id = None
        self.cert = []
        self.voted = {}              # término -> candidato votado
        self.last_hb = 0.0           # último latido válido del líder
        self.seen = {}               # id -> último contacto
        self.acks = {}               # id -> último ack de latido (solo líder)
        self.following = None        # (líder, término) que sigue mi Redis
        self.rejoin_pending = None   # líder al que debo entregar mis escrituras
        self.rejoining = False
        self.last_rejoin_try = 0.0
        self.electing = False
        self.divergent = []          # escrituras hechas sin quórum (para 3.3)
        self.rejected_claims = 0

        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"nodo-{self.id}.log")
        self.journal_path = os.path.join(log_dir, f"diario-escrituras-{self.id}.jsonl")
        self.state_path = os.path.join(log_dir, f"estado-{self.id}.json")
        self.conflog = ConflictLog(os.path.join(log_dir, f"conflictos-{self.id}.jsonl"))
        self._load_state()

        me = cfg["nodes"][self.id]
        self.server = Server(me["host"], me["port"], self.handle)

    # ------------------------------------------------------------ utilidades
    def log(self, msg):
        line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S')} [nodo {self.id}] "
                f"[{self.state} t={self.term} L={self.clock.value}] {msg}")
        if not self.quiet:
            print(line, flush=True)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                s = json.load(f)
            self.term = self.max_term_seen = int(s.get("term", 0))
            self.voted = {int(k): v for k, v in s.get("voted", {}).items()}
        except (OSError, ValueError):
            pass

    def _save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"term": self.term, "voted": self.voted}, f)
        except OSError:
            pass

    def _journal(self, rec):
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    def _reach(self, a, b):
        return self.simnet.up(a, b) if self.simnet else True

    # ----------------------------------------------------------------- red
    def send(self, peer, msg, timeout=None):
        if self.simnet and not self.simnet.up(self.id, peer):
            return None
        n = self.cfg["nodes"][peer]
        msg = dict(msg)
        msg["from"] = self.id
        msg["lc"] = self.clock.tick()
        r = request(n["host"], n["port"], msg, timeout or self.rpc_timeout)
        if r is not None:
            self.clock.update(r.get("lc", 0))
            with self.lock:
                self.seen[peer] = time.time()
        return r

    def _broadcast(self, ids, msg, timeout=None):
        out = {}

        def work(pid):
            out[pid] = self.send(pid, msg, timeout)

        ths = [threading.Thread(target=work, args=(p,)) for p in ids]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        return out

    def handle(self, msg):
        sender = msg.get("from")
        if self.simnet and sender is not None and not self.simnet.up(sender, self.id):
            return None
        if "lc" in msg:
            self.clock.update(msg["lc"])
        if sender is not None:
            with self.lock:
                self.seen[sender] = time.time()
        fn = getattr(self, "_h_" + str(msg.get("type")), None)
        if fn is None:
            return {"ok": False, "error": "tipo de mensaje desconocido"}
        try:
            r = fn(msg)
        except Exception as e:  # nunca tumbar el servidor por un mensaje
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        r["from"] = self.id
        r["lc"] = self.clock.tick()
        return r

    # ----------------------------------------------------------- ciclo vital
    def start(self):
        self.server.start()
        self.last_hb = time.time()
        self.log(f"nodo iniciado; clúster={self.all_ids} mayoría={self.majority}")
        threading.Thread(target=self._ticker, daemon=True).start()

    def stop(self):
        self.stop_ev.set()
        try:
            self.server.stop()
        except Exception:
            pass

    def _ticker(self):
        next_hb = 0.0
        while not self.stop_ev.is_set():
            now = time.time()
            with self.lock:
                state, last = self.state, self.last_hb
                pending = self.rejoin_pending
            if state == LIDER:
                if now >= next_hb:
                    next_hb = now + self.hb_int
                    threading.Thread(target=self._send_heartbeats, daemon=True).start()
            else:
                if pending is not None:
                    threading.Thread(target=self._try_rejoin, daemon=True).start()
                if now - last > self.hb_timeout:
                    self._start_election_async()
            try:
                self.store.sync()
            except Exception:
                pass
            time.sleep(0.1)

    def _fresh_leader(self):
        with self.lock:
            return (self.state == SEGUIDOR and self.leader_id is not None
                    and time.time() - self.last_hb < self.hb_timeout)

    def _has_quorum(self):
        now = time.time()
        with self.lock:
            vivos = 1 + sum(1 for p in self.peers if now - self.acks.get(p, 0) < self.hb_timeout)
        return vivos >= self.majority

    # --------------------------------------------------------------- latidos
    def _send_heartbeats(self):
        with self.lock:
            if self.state != LIDER:
                return
            msg = {"type": "heartbeat", "term": self.term, "leader": self.id, "cert": self.cert}
        res = self._broadcast(self.peers, msg, timeout=min(self.rpc_timeout, self.hb_timeout / 2))
        for pid, r in res.items():
            if r is None:
                continue
            if r.get("ok"):
                with self.lock:
                    self.acks[pid] = time.time()
            elif r.get("stale") and r.get("term", 0) > self.term:
                self.log(f"nodo {pid} reporta término {r['term']} > {self.term}: "
                         f"líder {r.get('leader')}; verificando")
                self._adopt_leader(r["term"], r.get("leader"), r.get("cert", []))

    def _h_heartbeat(self, msg):
        t, leader, cert = msg["term"], msg["leader"], msg.get("cert", [])
        with self.lock:
            if t < self.term:
                return {"ok": False, "stale": True, "term": self.term,
                        "leader": self.leader_id, "cert": self.cert}
        ok = self._adopt_leader(t, leader, cert)
        return {"ok": ok, "term": self.term, "leader": self.leader_id}

    def _h_coordinator(self, msg):
        ok = self._adopt_leader(msg["term"], msg["leader"], msg.get("cert", []))
        return {"ok": ok}

    # ------------------------------------------------- aceptación de líderes
    def _verify_claim(self, term, leader, cert):
        """Un nodo que no votó comprueba con los votantes que el líder ganó."""
        if leader not in cert or len(cert) < self.majority:
            return False
        confirmados = 1  # el propio reclamante
        for m in cert:
            if m in (self.id, leader):
                continue
            r = self.send(m, {"type": "verify", "term": term, "leader": leader})
            if r and r.get("ok"):
                confirmados += 1
        return confirmados >= self.majority

    def _h_verify(self, msg):
        t, l = msg["term"], msg["leader"]
        with self.lock:
            ok = (self.term == t and self.leader_id == l) or self.voted.get(t) == l
        return {"ok": ok}

    def _adopt_leader(self, term, leader, cert):
        """Acepta (o rechaza) el anuncio de un líder. Devuelve True si lo acepta."""
        if leader is None:
            return False
        need_follow = False
        with self.lock:
            if term < self.term:
                return False
            if leader == self.id:
                return self.state == LIDER and term == self.term
            if term == self.term and self.state == LIDER:
                return False  # dos líderes en el mismo término: imposible con mayoría
            if term == self.term and self.leader_id not in (None, leader):
                return False
            known = term == self.term and self.leader_id == leader
            voted = self.voted.get(term) == leader
            if known:
                self.last_hb = time.time()
                if self.state == CANDIDATO:
                    self.state = SEGUIDOR
                need_follow = self.following != (leader, term) and self.rejoin_pending is None
        if known:
            if need_follow:
                self._follow(leader, term)
            return True
        if not voted and not self._verify_claim(term, leader, cert):
            with self.lock:
                self.rejected_claims += 1
            self.log(f"RECHAZADO: nodo {leader} se declara líder del término {term} sin "
                     f"certificado válido (cert={cert}); se ignora")
            return False
        with self.lock:
            if term < self.term:
                return False
            era_lider = self.state == LIDER
            viejo_term = self.term
            self.term = self.max_term_seen = max(self.max_term_seen, term)
            self.leader_id, self.cert = leader, list(cert)
            self.state = SEGUIDOR
            self.last_hb = time.time()
            self.following = None
            if era_lider:
                self.rejoin_pending = leader
            self._save_state()
        if era_lider:
            self.log(f"ANTIGUO LÍDER (término {viejo_term}) reconoce al nodo {leader} "
                     f"(término {term}); deja de asignar recursos y entrega sus escrituras")
        else:
            self.log(f"líder reconocido: nodo {leader}, término {term}")
            self._follow(leader, term)
        return True

    def _follow(self, leader, term):
        n = self.cfg["nodes"][leader]
        try:
            self.store.follow(leader, n["redis_host"], n["redis_port"])
            with self.lock:
                self.following = (leader, term)
            self.log(f"Redis local ahora es réplica del nodo {leader}")
        except Exception as e:
            self.log(f"no pude seguir al maestro {leader}: {e}")

    # ------------------------------------------------ reintegro del ex-líder
    def _try_rejoin(self):
        with self.lock:
            leader = self.rejoin_pending
            if leader is None or self.state == LIDER or self.rejoining:
                return
            if time.time() - self.last_rejoin_try < 1.0:
                return
            self.rejoining = True
            self.last_rejoin_try = time.time()
            term = self.term
        try:
            self._do_rejoin(leader, term)
        finally:
            with self.lock:
                self.rejoining = False

    def _do_rejoin(self, leader, term):
        entries = self.store.all()
        with self.lock:
            div = list(self.divergent)
        r = self.send(leader, {"type": "rejoin", "entries": entries, "divergent": div,
                               "term": term}, timeout=max(self.rpc_timeout, 5))
        if not r or not r.get("ok"):
            return  # se reintenta en el siguiente tick
        with self.lock:
            self.rejoin_pending = None
            self.divergent = []
        s = r["stats"]
        self.log(f"REINTEGRO completado: detectados={s['detectados']} resueltos={s['resueltos']} "
                 f"avance_simple={s['avance_simple']} (escrituras sin quórum entregadas: {len(div)})")
        self._follow(leader, term)

    def _h_rejoin(self, msg):
        with self.lock:
            if self.state != LIDER:
                return {"ok": False, "error": "no soy líder"}
            origen = msg["from"]
        self.log(f"REJOIN de nodo {origen}: {len(msg['entries'])} recursos, "
                 f"{len(msg.get('divergent', []))} escrituras divergentes registradas")
        with self.wlock:
            stats = merge_remote(self.store, msg["entries"], self.id, self.clock,
                                 self.conflog, log=self.log)
        self.log(f"CONFLICTOS tras reconexión: detectados={stats['detectados']} "
                 f"resueltos={stats['resueltos']} (regla: {REGLA})")
        return {"ok": True, "stats": stats}

    # -------------------------------------------------------------- elección
    def _start_election_async(self):
        with self.lock:
            if self.electing or self.state == LIDER:
                return
            self.electing = True
        threading.Thread(target=self._election_loop, daemon=True).start()

    def _election_loop(self):
        intentos = 0
        try:
            while not self.stop_ev.is_set():
                if self._fresh_leader():
                    return
                with self.lock:
                    if self.state == LIDER:
                        return
                    self.state = CANDIDATO
                intentos += 1
                if intentos == 1 or intentos % 10 == 0:
                    self.log("sin latido del líder: inicio ELECCIÓN (algoritmo del matón)")
                superiores = [p for p in self.peers if p > self.id]
                res = self._broadcast(superiores, {"type": "election", "term": self.term})
                respondieron = []
                for pid, r in res.items():
                    if r and r.get("ok"):
                        respondieron.append(pid)
                        if r.get("leader") is not None:
                            self._adopt_leader(r["term"], r["leader"], r.get("cert", []))
                if self._fresh_leader():
                    return
                if respondieron:
                    # hay un nodo superior vivo: él debe ganar; esperar su COORDINATOR
                    fin = time.time() + self.el_timeout
                    while time.time() < fin and not self.stop_ev.is_set():
                        if self._fresh_leader():
                            return
                        time.sleep(0.1)
                    continue
                # soy el mayor id vivo: pedir votos
                with self.lock:
                    nuevo = self.max_term_seen + 1
                    self.max_term_seen = nuevo
                    self.voted[nuevo] = self.id
                    self._save_state()
                res = self._broadcast(self.peers, {"type": "propose", "term": nuevo, "cand": self.id})
                votos = [p for p, r in res.items() if r and r.get("ok")]
                if len(votos) + 1 >= self.majority:
                    self._become_leader(nuevo, sorted([self.id] + votos))
                    return
                if intentos == 1 or intentos % 10 == 0:
                    self.log(f"sin mayoría para el término {nuevo} ({len(votos) + 1}/"
                             f"{len(self.all_ids)}); no puedo ser líder, reintento")
                time.sleep(random.uniform(1.0, 2.0))
        finally:
            with self.lock:
                self.electing = False
                if self.state == CANDIDATO:
                    self.state = SEGUIDOR

    def _h_election(self, msg):
        origen = msg["from"]
        with self.lock:
            if self.state == LIDER:
                return {"ok": True, "leader": self.id, "term": self.term, "cert": self.cert}
        if self._fresh_leader():
            with self.lock:
                return {"ok": True, "leader": self.leader_id, "term": self.term, "cert": self.cert}
        if origen < self.id:
            self.log(f"ELECTION recibido de nodo {origen} (menor): respondo OK y tomo la elección")
            self._start_election_async()
            return {"ok": True}
        return {"ok": False}

    def _h_propose(self, msg):
        t, c = msg["term"], msg["cand"]
        now = time.time()
        with self.lock:
            if t <= self.term:
                return {"ok": False, "reason": "término obsoleto"}
            if self.voted.get(t, c) != c:
                return {"ok": False, "reason": "ya voté en ese término"}
            if self.state == LIDER:
                return {"ok": False, "reason": "soy líder vigente"}
            if self.state == SEGUIDOR and self.leader_id not in (None, c) and \
                    now - self.last_hb < self.hb_timeout:
                return {"ok": False, "reason": "tengo líder vigente"}
            mayor = self.id > c
            mayores_vivos = [p for p in self.peers if p > c and now - self.seen.get(p, 0) < self.hb_timeout]
            if not mayor and not mayores_vivos:
                self.voted[t] = c
                self.max_term_seen = max(self.max_term_seen, t)
                self._save_state()
                return {"ok": True}
        if mayor:
            self._start_election_async()
        self.log(f"propuesta de nodo {c} (término {t}) rechazada: hay un nodo vivo con id mayor")
        return {"ok": False, "reason": "existe nodo vivo con id mayor"}

    def _become_leader(self, term, cert):
        with self.lock:
            self.state = LIDER
            self.term = self.max_term_seen = term
            self.leader_id = self.id
            self.cert = cert
            self.last_hb = time.time()
            self.following = None
            self.rejoin_pending = None
            now = time.time()
            self.acks = {p: now for p in cert if p != self.id}
            self._save_state()
        try:
            self.store.promote()
        except Exception as e:
            self.log(f"error promoviendo Redis: {e}")
        self.log(f"*** ELEGIDO LÍDER *** término={term} votos={cert} "
                 f"(mayoría {self.majority}/{len(self.all_ids)}); Redis local promovido a maestro")
        self._broadcast(self.peers, {"type": "coordinator", "term": term,
                                     "leader": self.id, "cert": cert})
        threading.Thread(target=self._send_heartbeats, daemon=True).start()

    # ------------------------------------------------------------- escrituras
    def _h_write(self, msg):
        with self.lock:
            state, leader = self.state, self.leader_id
            fresh = time.time() - self.last_hb < self.hb_timeout
        if state == LIDER:
            if msg.get("fterm", 0) > self.term:
                return {"ok": False, "error": "mi término es obsoleto; no soy líder válido"}
            return self._leader_write(msg)
        if msg.get("forwarded"):
            return {"ok": False, "error": "este nodo no es el coordinador"}
        if leader is None or not fresh:
            return {"ok": False, "error": "sin coordinador vigente: escritura rechazada"}
        r = self.send(leader, dict(msg, forwarded=True, fterm=self.term, type="write"))
        if r is None:
            return {"ok": False, "error": f"coordinador {leader} inaccesible: escritura rechazada"}
        r["via"] = self.id
        return r

    def _leader_write(self, msg):
        op, res = msg.get("op"), msg.get("resource")
        if not res or op not in ("set", "allocate", "release"):
            return {"ok": False, "error": "op/resource inválidos"}
        quorum = self._has_quorum()
        if self.require_quorum and not quorum:
            self.log(f"escritura {op} {res} RECHAZADA: sin quórum (modo CP)")
            return {"ok": False, "error": "sin quórum (modo CP): escritura rechazada"}
        d = {k: int(msg.get(k, 0)) for k in ("cpu", "mem", "bw")}
        with self.wlock:
            cur = self.store.get(res)
            base = {k: (cur or {}).get(k, 0) for k in ("cpu", "mem", "bw")}
            if op == "set":
                new = {k: (d[k] if k in msg else base[k]) for k in base}
            elif op == "allocate":
                if cur is None or any(base[k] < d[k] for k in base):
                    return {"ok": False, "error": "recursos insuficientes"}
                new = {k: base[k] - d[k] for k in base}
            else:
                new = {k: base[k] + d[k] for k in base}
            entry = dict(new, resource=res, op=op, writer=self.id, term=self.term,
                         vv=vv_increment((cur or {}).get("vv"), self.id),
                         lamport=self.clock.tick(), ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
            try:
                self.store.put(res, entry)
            except ReadOnlyError as e:
                return {"ok": False, "error": f"Redis de solo lectura: {e}"}
            except Exception as e:
                return {"ok": False, "error": f"error de almacenamiento: {e}"}
        self._journal(dict(entry, sin_quorum=not quorum))
        if not quorum:
            with self.lock:
                self.divergent.append(entry)
            self.log(f"ESCRITURA SIN QUÓRUM (posible divergencia) {op} {res} -> "
                     f"cpu={entry['cpu']} mem={entry['mem']} bw={entry['bw']} vv={entry['vv']} "
                     f"lamport={entry['lamport']}")
        else:
            self.log(f"escritura {op} {res} -> cpu={entry['cpu']} mem={entry['mem']} "
                     f"bw={entry['bw']} vv={entry['vv']} lamport={entry['lamport']}")
        return {"ok": True, "entry": entry, "quorum": quorum, "coordinador": self.id}

    # --------------------------------------------------- consultas / depuración
    def _h_inventory(self, msg):
        return {"ok": True, "inventory": self.store.all()}

    def _h_status(self, msg):
        with self.lock:
            base = {"id": self.id, "estado": self.state, "termino": self.term,
                    "lider": self.leader_id, "lamport": self.clock.value,
                    "cert": self.cert, "reclamos_rechazados": self.rejected_claims,
                    "escrituras_sin_quorum_pendientes": len(self.divergent),
                    "reintegro_pendiente": self.rejoin_pending}
        try:
            base["redis_rol"] = self.store.role()
        except Exception as e:
            base["redis_rol"] = f"error: {e}"
        base["conflictos"] = self.conflog.stats()
        base["quorum"] = self._has_quorum() if base["estado"] == LIDER else None
        base["ok"] = True
        return base

    def _h_fake_leader(self, msg):
        """PRUEBA: este nodo se autoproclama líder sin haber ganado la elección."""
        with self.lock:
            falso = self.max_term_seen + 1
        self.log(f"PRUEBA: me autoproclamo líder del término {falso} sin elección")
        res = self._broadcast(self.peers, {"type": "heartbeat", "term": falso, "leader": self.id,
                                           "cert": sorted(self.all_ids)})
        return {"ok": True, "respuestas": {str(p): (r.get("ok") if r else None) for p, r in res.items()}}


# ------------------------------------------------------------------ arranque
def build_store(kind, node_id, cfg):
    if kind == "memory":
        return MemoryStore(node_id)
    me = cfg["nodes"][node_id]
    local = me.get("redis_local", f"127.0.0.1:{me['redis_port']}")
    host, port = local.rsplit(":", 1)
    return RedisStore(node_id, host, int(port), cfgmod.redis_password(cfg))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Nodo de coordinación y datos (Taller 1)")
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--config", default="config/cluster.json")
    ap.add_argument("--store", choices=["redis", "memory"], default="redis")
    ap.add_argument("--log-dir", default="logs")
    a = ap.parse_args(argv)
    cfg = cfgmod.load(a.config)
    node = Node(a.id, cfg, build_store(a.store, a.id, cfg), a.log_dir)
    node.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        node.stop()


if __name__ == "__main__":
    main()
