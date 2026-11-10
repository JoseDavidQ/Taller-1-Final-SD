# Taller 1 — Coordinación y datos del sistema

Sistemas Distribuidos Modernos · Ingeniería en Telemática · Docente: Msc. Ing. Óscar Gabriel Espejo Mojica

**Integrantes:** _(nombre 1)_ · _(nombre 2)_ · _(nombre 3)_ · _(nombre 4)_

Capa de coordinación y datos de un sistema de gestión de recursos de borde:

* **Elección de coordinador** con el **algoritmo del matón** (Garcia-Molina, 1982), reforzado con *términos*, *quórum* y *certificados de líder*.
* **Inventario replicado** (CPU, memoria y ancho de banda por nodo) en **Redis con replicación maestro-réplica**.
* **Detección de escrituras concurrentes** con **vectores de versión** y resolución con **reloj de Lamport**.
* **Experimento de partición** con `iptables` (y `tc netem` opcional) con evidencia antes / durante / después.

```
        Tailnet (Tailscale / WireGuard)  — IPs 100.x.y.z, SSH solo con clave pública
 ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
 │ nodo 1 (2 GB) │        │ nodo 2 (2 GB) │        │ nodo 3 (3 GB) │
 │ coord.node    │◄──TCP─►│ coord.node    │◄──TCP─►│ coord.node    │   latidos, ELECTION,
 │  (TCP :7001)  │ JSON   │  (TCP :7001)  │ JSON   │  (TCP :7001)  │   PROPOSE, COORDINATOR,
 │ Redis :6379   │        │ Redis :6379   │        │ Redis :6379   │   VERIFY, REJOIN, write
 └──────┬────────┘        └──────┬────────┘        └──────┬────────┘
        │  REPLICAOF <líder>     │  REPLICAOF <líder>     │  REPLICAOF NO ONE (líder)
        └────────────────────────┴────────────────────────┘
              el líder elegido es el MAESTRO de Redis; los demás son réplicas
```

## 1. Decisiones de diseño (resumen — el informe las desarrolla)

| Tema | Decisión | Justificación |
|---|---|---|
| Elección | **Algoritmo del matón** | Detección directa por temporizador de latido; gana el mayor id vivo de forma determinista; con pocos nodos su costo O(n²) en el peor caso es irrelevante. El anillo exige mantener y reparar un anillo lógico: si un nodo cae o hay una partición, el mensaje deja de circular y hay que reconfigurar el anillo. |
| Almacén | **Redis maestro-réplica** | Ligero (cabe en 2 GB). `REPLICAOF` permite que el rol maestro/réplica siga al líder elegido por **nuestro** algoritmo. MongoDB trae su propia elección (Raft): competiría con la nuestra y su primario aislado se degrada a solo lectura, así que nunca habría escrituras concurrentes que detectar. Con Redis el maestro aislado sigue aceptando escrituras (comportamiento AP observable). |
| Versionado | **Vector de versión por recurso** + **Lamport** | El vector decide *si* hay concurrencia; Lamport decide *quién gana*. |
| Regla de conflicto | **Mayor Lamport; empate → menor id de escritor** | Determinista y simétrica (todos los nodos llegan al mismo resultado). La escritura perdedora queda en `logs/conflictos-N.jsonl`. |
| Partición | **AP por defecto**, **CP opcional** (`require_quorum_for_writes`) | Permite comparar ambos comportamientos en el análisis CAP. |

Modelo de consistencia efectivo: [docs/Modelo de consistencia.md](docs/Modelo%20de%20consistencia.md).

### Cómo se cumple cada punto del taller

| Requisito | Dónde / cómo |
|---|---|
| Estado seguidor / candidato / líder y temporizador de latido | `coord/node.py` (`SEGUIDOR`, `CANDIDATO`, `LIDER`; `_ticker`, `_send_heartbeats`) |
| Nueva elección si el líder no responde | `_ticker` → `_start_election_async` → `_election_loop` |
| Solo el coordinador asigna recursos | `_h_write` reenvía al líder; `_leader_write` solo corre en el líder; las réplicas Redis son de solo lectura |
| Líder autoproclamado detectado y rechazado | Voto único por término + mayoría + certificado verificado con `VERIFY` (`_adopt_leader`, `_verify_claim`). Prueba: `ctl lider-falso` |
| Antiguo líder reconoce al nuevo y deja de asignar | Término mayor con certificado válido → degradación a seguidor + `REJOIN` (`_try_rejoin`) |
| Escrituras del período de partición registradas | `logs/diario-escrituras-N.jsonl` (marca `sin_quorum`) y lista `divergent` |
| Inventario en Redis maestro-réplica | `coord/store.py` (`RedisStore`), `scripts/02-configurar-redis.sh` |
| Reloj de Lamport / vector de versión en cada cambio | `coord/clock.py`, `_leader_write` |
| Detección por vectores, regla, contadores | `coord/reconcile.py` (`merge_remote`, `winner`, `ConflictLog`) |
| Partición con iptables, medición, convergencia | `scripts/particion.sh`, `scripts/experimento-particion.sh`, `ctl snapshot / convergencia` |
| Latencia opcional con `tc netem` | `scripts/particion.sh latencia 100 20` |

## 2. Estructura del repositorio

```
coord/            código (Python 3, solo biblioteca estándar + redis-py)
  node.py         nodo: elección, latidos, escrituras, reintegro
  clock.py        Lamport + vectores de versión
  reconcile.py    detección/resolución de conflictos
  store.py        RedisStore (producción) y MemoryStore (simulación)
  net.py          mensajería TCP+JSON y red simulada
  ctl.py          cliente de operación y medición
  sim.py          simulación local completa (sin VMs)
scripts/          preparación de VM, conectividad (E3), partición (E5), elección (E4)
deploy/           unidad systemd
config/           cluster.example.json  (copiar a cluster.json, que NO se versiona)
docs/             guía de despliegue, modelo de consistencia, plan de commits
evidencias/       E3 / E4 (logs)         resultados/  E5 (tablas)
tests/            pruebas unitarias y de integración
```

## 3. Requisitos del entorno

* ≥ 3 VM Debian 13 o Ubuntu Server 26.04.1 LTS, sin entorno gráfico: 2 GB (agentes/coordinador) y 3 GB para el nodo que aloja la base de datos (nodo 3, líder inicial).
* SSH solo con clave pública (`scripts/01-preparar-vm.sh` deshabilita la contraseña y comprueba que exista una clave autorizada antes de hacerlo).
* Conectividad por Tailscale (una tailnet por grupo).
* Claves privadas **nunca** en el repo: `.gitignore` cubre `*.pem`, `*.key`, `.ssh/`, `.env` y `config/cluster.json`.

## 4. Puesta en marcha (en cada VM)

Guía completa con GCP y Tailscale: [docs/Guía paso a paso.md](docs/Gu%C3%ADa%20paso%20a%20paso.md). Resumen:

```bash
git clone <url-del-repo> && cd taller1-coordinacion-datos
sudo ./scripts/01-preparar-vm.sh            # paquetes + SSH solo clave + Tailscale
sudo tailscale up                            # autenticar en la tailnet del grupo
./scripts/00-verificar-conectividad.sh USUARIO   # E3 (ping + SSH entre nodos)
sudo REDIS_PASSWORD='clave-larga' ./scripts/02-configurar-redis.sh
./scripts/03-instalar-app.sh                 # venv + dependencias; crea config/cluster.json y .env
# editar config/cluster.json (IPs de `tailscale ip -4`) y .env (misma REDIS_PASSWORD)
sudo cp deploy/coord-nodo.service /etc/systemd/system/coord-nodo@.service   # editar USUARIO y RUTA
sudo systemctl enable --now coord-nodo@N     # N = id del nodo (1, 2, 3)
```

Operación y medición (desde cualquier equipo de la tailnet con el repo):

```bash
export PYTHONPATH=.
python3 -m coord.ctl estado                       # rol, término, líder, Redis, conflictos
python3 -m coord.ctl sembrar                      # crea nodo1..nodoN en el inventario
python3 -m coord.ctl asignar nodo1 --cpu 1 --mem 256 --bw 10 [--nodo N]
python3 -m coord.ctl inventario                   # inventario visto por cada nodo
python3 -m coord.ctl convergencia                 # ¿todos tienen el mismo estado?
python3 -m coord.ctl snapshot --etiqueta antes    # fila de tabla para el informe (E5)
python3 -m coord.ctl lider-falso --nodo 1         # prueba de líder autoproclamado
```

## 5. Experimentos y evidencias

| Entregable | Cómo se genera |
|---|---|
| **E3** conectividad | `./scripts/00-verificar-conectividad.sh` → `evidencias/E3 Conectividad desde …txt` |
| **E4** elección + caída del líder | `SSH_USER=… ./scripts/prueba-eleccion.sh` → `evidencias/E4 …txt` + `logs/nodo-N.log` |
| **E5** partición antes/durante/después | `SSH_USER=… ./scripts/experimento-particion.sh` → `resultados/E5-experimento-particion.md` + log |

Aislar/reconectar a mano: `sudo ./scripts/particion.sh aislar` / `reconectar` (reglas `iptables` de entrada y salida hacia los demás nodos).

## 6. Pruebas sin VMs

```bash
PYTHONPATH=. python -m coord.sim                  # escenario completo con 3 nodos en localhost
PYTHONPATH=. python -m unittest discover -s tests -t .
```

Con Docker (3 contenedores Redis reales) también: `PYTHONPATH=. python tests/prueba_redis_docker.py` (verifica `REPLICAOF`, réplicas de solo lectura, partición, conflicto y convergencia sobre Redis real).

Cubren: líder único, reelección tras caída, líder falso rechazado, solo el líder escribe, partición con doble escritura → conflicto detectado y resuelto, convergencia y modo CP.

## 7. Bibliotecas de terceros (norma 8)

* [redis-py](https://github.com/redis/redis-py) (MIT) — cliente de Redis.
* [Redis](https://redis.io) (versión libre del repositorio de la distribución) — almacén del inventario.
* [Tailscale](https://tailscale.com) — red superpuesta entre nodos.
* Todo lo demás es biblioteca estándar de Python. El código de elección, versionado, reconciliación y mensajería es propio.

## 8. Referencias

* Garcia-Molina, H. (1982). Elections in a Distributed Computing System. *IEEE Trans. on Computers*, C-31(1).
* Chang, E., & Roberts, R. (1979). An Improved Algorithm for Decentralized Extrema-Finding in Circular Configurations of Processes. *CACM*, 22(5).
* Fidge, C. J. (1988). Timestamps in Message-Passing Systems That Preserve the Partial Ordering. *11th ACSC*.
* Mattern, F. (1989). Virtual Time and Global States of Distributed Systems. *Parallel and Distributed Algorithms*.
* Lamport, L. (1978). Time, Clocks, and the Ordering of Events in a Distributed System. *CACM*, 21(7).
* Documentación oficial de Redis: replicación (`REPLICAOF`).
