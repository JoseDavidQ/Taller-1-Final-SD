"""Mensajería mínima: una línea JSON por petición sobre TCP (petición/respuesta)."""
import json
import socket
import socketserver
import threading


def request(host, port, msg, timeout=1.5):
    """Envía un mensaje y devuelve la respuesta (dict) o None si falla/expira."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode("utf-8")) if buf.strip() else None
    except (OSError, ValueError):
        return None


class SimNetwork:
    """Red simulada para pruebas locales: permite cortar enlaces entre nodos.

    En producción NO se usa; la partición real se hace con iptables
    (scripts/particion.sh)."""

    def __init__(self):
        self.blocked = set()
        self._lock = threading.Lock()

    def block(self, a, b):
        with self._lock:
            self.blocked.add(frozenset((a, b)))

    def isolate(self, node, others):
        for o in others:
            if o != node:
                self.block(node, o)

    def heal(self):
        with self._lock:
            self.blocked.clear()

    def up(self, a, b):
        with self._lock:
            return frozenset((a, b)) not in self.blocked


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            line = self.rfile.readline(4 * 1024 * 1024)
            if not line.strip():
                return
            msg = json.loads(line.decode("utf-8"))
            resp = self.server.node_handler(msg)
            if resp is None:  # descartar (partición simulada)
                return
            self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
        except (OSError, ValueError):
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, host, port, node_handler):
        super().__init__((host, int(port)), _Handler)
        self.node_handler = node_handler
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self.shutdown()
        self.server_close()
