
### ANTES — 2026-11-10 04:05:17

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 5 | 2 | slave | nodo1 | 2 | 2048 | 100 | {"2": 5, "3": 1} | 6208 |
| 1 | seguidor | 5 | 2 | slave | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 1} | 6214 |
| 1 | seguidor | 5 | 2 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |
| 2 | líder | 5 | 2 | master | nodo1 | 2 | 2048 | 100 | {"2": 5, "3": 1} | 6208 |
| 2 | líder | 5 | 2 | master | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 1} | 6214 |
| 2 | líder | 5 | 2 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |
| 3 | seguidor | 5 | 2 | slave | nodo1 | 2 | 2048 | 100 | {"2": 5, "3": 1} | 6208 |
| 3 | seguidor | 5 | 2 | slave | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 1} | 6214 |
| 3 | seguidor | 5 | 2 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |

### DURANTE (NODOS CONECTADOS) — 2026-11-10 04:05:31

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 6 | 3 | slave | nodo1 | 1 | 1536 | 80 | {"2": 5, "3": 2} | 6288 |
| 1 | seguidor | 6 | 3 | slave | nodo2 | 1 | 1920 | 95 | {"2": 4, "3": 2} | 6291 |
| 1 | seguidor | 6 | 3 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |
| 3 | líder | 6 | 3 | master | nodo1 | 1 | 1536 | 80 | {"2": 5, "3": 2} | 6288 |
| 3 | líder | 6 | 3 | master | nodo2 | 1 | 1920 | 95 | {"2": 4, "3": 2} | 6291 |
| 3 | líder | 6 | 3 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |

### DURANTE (NODO 2 AISLADO) — 2026-11-10 04:05:31

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | líder | 5 | 2 | master | nodo1 | 1 | 1792 | 90 | {"2": 6, "3": 1} | 6266 |
| 2 | líder | 5 | 2 | master | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 1} | 6214 |
| 2 | líder | 5 | 2 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |

(añadido a /dev/null)

### DESPUÉS — 2026-11-10 04:05:46

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 6 | 3 | slave | nodo1 | 1 | 1536 | 80 | {"2": 6, "3": 3} | 6312 |
| 1 | seguidor | 6 | 3 | slave | nodo2 | 1 | 1920 | 95 | {"2": 4, "3": 2} | 6291 |
| 1 | seguidor | 6 | 3 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |
| 2 | seguidor | 6 | 3 | slave | nodo1 | 1 | 1536 | 80 | {"2": 6, "3": 3} | 6312 |
| 2 | seguidor | 6 | 3 | slave | nodo2 | 1 | 1920 | 95 | {"2": 4, "3": 2} | 6291 |
| 2 | seguidor | 6 | 3 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |
| 3 | líder | 6 | 3 | master | nodo1 | 1 | 1536 | 80 | {"2": 6, "3": 3} | 6312 |
| 3 | líder | 6 | 3 | master | nodo2 | 1 | 1920 | 95 | {"2": 4, "3": 2} | 6291 |
| 3 | líder | 6 | 3 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 1} | 6220 |

### ANTES — 2026-11-10 04:06:33

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 6 | 3 | slave | nodo1 | 2 | 2048 | 100 | {"2": 6, "3": 4} | 6641 |
| 1 | seguidor | 6 | 3 | slave | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 3} | 6643 |
| 1 | seguidor | 6 | 3 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
| 2 | seguidor | 6 | 3 | slave | nodo1 | 2 | 2048 | 100 | {"2": 6, "3": 4} | 6641 |
| 2 | seguidor | 6 | 3 | slave | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 3} | 6643 |
| 2 | seguidor | 6 | 3 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
| 3 | líder | 6 | 3 | master | nodo1 | 2 | 2048 | 100 | {"2": 6, "3": 4} | 6641 |
| 3 | líder | 6 | 3 | master | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 3} | 6643 |
| 3 | líder | 6 | 3 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |

### DURANTE (NODOS CONECTADOS) — 2026-11-10 04:06:51

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 8 | 2 | slave | nodo1 | 1 | 1536 | 80 | {"2": 7, "3": 4} | 6717 |
| 1 | seguidor | 8 | 2 | slave | nodo2 | 1 | 1920 | 95 | {"2": 5, "3": 3} | 6720 |
| 1 | seguidor | 8 | 2 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
| 2 | líder | 8 | 2 | master | nodo1 | 1 | 1536 | 80 | {"2": 7, "3": 4} | 6717 |
| 2 | líder | 8 | 2 | master | nodo2 | 1 | 1920 | 95 | {"2": 5, "3": 3} | 6720 |
| 2 | líder | 8 | 2 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |

### DURANTE (NODO 3 AISLADO) — 2026-11-10 04:06:51

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | líder | 6 | 3 | master | nodo1 | 1 | 1792 | 90 | {"2": 6, "3": 5} | 6719 |
| 3 | líder | 6 | 3 | master | nodo2 | 2 | 2048 | 100 | {"2": 4, "3": 3} | 6643 |
| 3 | líder | 6 | 3 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |

(añadido a /dev/null)

### DESPUÉS — 2026-11-10 04:07:07

| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | seguidor | 8 | 2 | slave | nodo1 | 1 | 1792 | 90 | {"2": 8, "3": 5} | 6743 |
| 1 | seguidor | 8 | 2 | slave | nodo2 | 1 | 1920 | 95 | {"2": 5, "3": 3} | 6720 |
| 1 | seguidor | 8 | 2 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
| 2 | líder | 8 | 2 | master | nodo1 | 1 | 1792 | 90 | {"2": 8, "3": 5} | 6743 |
| 2 | líder | 8 | 2 | master | nodo2 | 1 | 1920 | 95 | {"2": 5, "3": 3} | 6720 |
| 2 | líder | 8 | 2 | master | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
| 3 | seguidor | 8 | 2 | slave | nodo1 | 1 | 1792 | 90 | {"2": 8, "3": 5} | 6743 |
| 3 | seguidor | 8 | 2 | slave | nodo2 | 1 | 1920 | 95 | {"2": 5, "3": 3} | 6720 |
| 3 | seguidor | 8 | 2 | slave | nodo3 | 2 | 2048 | 100 | {"2": 2, "3": 2} | 6645 |
