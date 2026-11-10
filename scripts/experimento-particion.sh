#!/usr/bin/env bash
# E5: experimento de partición completo (antes / durante / después).
# Se ejecuta desde un equipo con acceso SSH por clave a los nodos y que esté en la tailnet
# (por ejemplo tu computador con Tailscale, o uno de los nodos), en la raíz del repo.
#
#   SSH_USER=tu_usuario ./scripts/experimento-particion.sh [id_nodo_a_aislar]
#
# Por defecto aísla al líder actual (se detecta con ctl estado). Variables opcionales:
#   REPO_DIR   ruta del repo en las VM (def. ~/taller1-coordinacion-datos)
#   CON_LATENCIA=1  repite la fase con tc netem 100 ms +-20 ms antes de particionar
set -u
export PYTHONPATH="${PYTHONPATH:-.}"
PY="${PY:-python3}"
CFG="${CFG:-config/cluster.json}"
SSH_USER="${SSH_USER:?Define SSH_USER}"
REPO_DIR="${REPO_DIR:-taller1-coordinacion-datos}"
CTL="$PY -m coord.ctl --config $CFG"
SALIDA="resultados/E5-experimento-particion.md"
LOG="evidencias/E5 Registro experimento $(date +%d-%m-%Y).txt"
mkdir -p resultados evidencias

host_de() { $PY -c "import json;n=json.load(open('$CFG'))['nodes']['$1'];print(n.get('ssh_host', n['host']))"; }
ids() { $PY -c "import json;print(' '.join(sorted(json.load(open('$CFG'))['nodes'], key=int)))"; }
# IMPORTANTE: se administra por la IP PÚBLICA (ssh_host), no por Tailscale, porque el nodo aislado
# bloquea justamente el tráfico Tailscale de los demás nodos (cortaría la propia sesión SSH).
remoto() { ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$SSH_USER@$(host_de "$1")" "cd $REPO_DIR && $2"; }
CTLR="PYTHONPATH=. .venv/bin/python -m coord.ctl --config $CFG"   # ctl ejecutado EN un nodo

lider_actual() { $PY -c "
from coord import config, ctl
cfg = config.load('$CFG')
for nid, s in sorted(ctl.estados(cfg).items()):
    if s and s['estado'] == 'líder':
        print(nid); break
"; }
IDS=$(ids)
VIEJO="${1:-$(lider_actual)}"
[ -n "$VIEJO" ] || { echo "No hay líder: revisa ctl estado"; exit 1; }
# nuevo líder esperado = mayor id restante; seguidor = el otro
RESTO=$(echo $IDS | tr ' ' '\n' | grep -vx "$VIEJO" | sort -n)
NUEVO=$(echo "$RESTO" | tail -n1)
SEGUIDOR=$(echo "$RESTO" | head -n1)

paso() { echo; echo "================ $(date -Is) :: $* ================"; }

{
paso "0. Estado inicial y siembra del inventario"
$CTL estado
$CTL sembrar
sleep 2
paso "1. ANTES de la partición"
$CTL snapshot --etiqueta "antes" --salida "$SALIDA"
$CTL convergencia

if [ "${CON_LATENCIA:-0}" = "1" ]; then
  paso "1b. Latencia opcional 100 ms +-20 ms en nodo $VIEJO"
  remoto "$VIEJO" "sudo ./scripts/particion.sh latencia 100 20"
  sleep 5; $CTL estado
  remoto "$VIEJO" "sudo ./scripts/particion.sh sin-latencia"
fi

paso "2. PARTICIÓN: aislando nodo $VIEJO con iptables (entrada y salida)"
remoto "$VIEJO" "sudo ./scripts/particion.sh aislar"
echo "Esperando detección de caída del líder y reelección (~12 s)..."
sleep 12
$CTL estado --nodos "$(echo $RESTO | tr ' ' ',')"

paso "3. DURANTE: escrituras concurrentes sobre el MISMO recurso (nodo1)"
echo "-- al líder viejo (nodo $VIEJO, aislado, cree seguir siendo líder). Se ejecuta EN ese nodo:"
remoto "$VIEJO" "$CTLR asignar nodo1 --cpu 1 --mem 256 --bw 10 --nodo $VIEJO"
echo "-- al líder nuevo (nodo $NUEVO):"
$CTL asignar nodo1 --cpu 1 --mem 512 --bw 20 --nodo "$NUEVO"
echo "-- a un seguidor (nodo $SEGUIDOR), se reenvía al líder nuevo:"
$CTL asignar nodo2 --cpu 1 --mem 128 --bw 5 --nodo "$SEGUIDOR"
echo "-- escritura DIRECTA al Redis de una réplica debe ser rechazada (solo lectura):"
echo "   (verificar con: redis-cli -a \$REDIS_PASSWORD set inv:x 1  -> READONLY)"
echo "-- estado según el nodo aislado (su propia vista):"
remoto "$VIEJO" "$CTLR estado --nodos $VIEJO"
$CTL snapshot --etiqueta "durante (nodos conectados)" --nodos "$(echo $RESTO | tr ' ' ',')" --salida "$SALIDA"
remoto "$VIEJO" "$CTLR snapshot --etiqueta 'durante (nodo $VIEJO aislado)' --nodos $VIEJO --salida /dev/null" | tee -a "$SALIDA"

paso "4. RECONEXIÓN: se quitan las reglas de iptables del nodo $VIEJO"
remoto "$VIEJO" "sudo ./scripts/particion.sh reconectar"
echo "Esperando reintegro del antiguo líder y resolución de conflictos (~15 s)..."
sleep 15
$CTL estado

paso "5. DESPUÉS: convergencia"
$CTL snapshot --etiqueta "después" --salida "$SALIDA"
$CTL convergencia
echo
echo "Conflictos registrados por el líder: ver columna 'conflictos(det/res)' arriba y logs/conflictos-*.jsonl"

paso "6. Logs de los nodos (recogidos en evidencias/)"
for N in $IDS; do
  mkdir -p "evidencias/logs-nodo-$N"
  scp -q -o StrictHostKeyChecking=accept-new "$SSH_USER@$(host_de "$N"):$REPO_DIR/logs/*" "evidencias/logs-nodo-$N/" 2>/dev/null \
    && echo "logs del nodo $N copiados" || echo "no pude copiar logs del nodo $N"
done
} 2>&1 | tee "$LOG"
echo "Registro: $LOG   |   Tablas: $SALIDA"
