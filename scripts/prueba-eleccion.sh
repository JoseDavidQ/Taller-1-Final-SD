#!/usr/bin/env bash
# E4: registro de la elección de líder, incluida la caída del líder y el líder falso.
# Requisito: los nodos corren como servicio systemd (coord-nodo@N), ver README.
#
#   SSH_USER=tu_usuario ./scripts/prueba-eleccion.sh
set -u
export PYTHONPATH="${PYTHONPATH:-.}"
PY="${PY:-python3}"
CFG="${CFG:-config/cluster.json}"
SSH_USER="${SSH_USER:?Define SSH_USER}"
CTL="$PY -m coord.ctl --config $CFG"
LOG="evidencias/E4 Registro eleccion de lider $(date +%d-%m-%Y).txt"
mkdir -p evidencias
host_de() { $PY -c "import json;n=json.load(open('$CFG'))['nodes']['$1'];print(n.get('ssh_host', n['host']))"; }
IDS=$($PY -c "import json;print(' '.join(sorted(json.load(open('$CFG'))['nodes'], key=int)))")
lider_actual() { $PY -c "
from coord import config, ctl
cfg = config.load('$CFG')
for nid, s in sorted(ctl.estados(cfg).items()):
    if s and s['estado'] == 'líder':
        print(nid); break
"; }
LIDER=$(lider_actual)
MENOR=$(echo $IDS | tr ' ' '\n' | grep -vx "$LIDER" | sort -n | head -n1)   # un nodo que NO es líder: hará de falso líder
paso() { echo; echo "================ $(date -Is) :: $* ================"; }

{
paso "1. Estado: debe haber UN líder único (nodo $LIDER)"
$CTL estado
paso "2. Caída del líder: se detiene el servicio en el nodo $LIDER"
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$SSH_USER@$(host_de "$LIDER")" "sudo systemctl stop coord-nodo@$LIDER"
sleep 12
$CTL estado
paso "3. El antiguo líder vuelve: debe reconocer al nuevo (sin volver a tomar el mando)"
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$SSH_USER@$(host_de "$LIDER")" "sudo systemctl start coord-nodo@$LIDER"
sleep 8
$CTL estado
paso "4. Líder falso: el nodo $MENOR se autoproclama líder sin haber ganado la elección"
$CTL lider-falso --nodo "$MENOR"
$CTL estado
} 2>&1 | tee "$LOG"
echo "Registro: $LOG  (adjunta también los logs/nodo-N.log de cada VM)"
