#!/usr/bin/env bash
# E3: verificación inicial obligatoria. Cada nodo hace ping y SSH a los demás.
# Uso (en CADA nodo):  ./scripts/00-verificar-conectividad.sh [usuario_ssh]
# Lee los hosts de config/cluster.json y guarda el registro en evidencias/.
set -u
USUARIO="${1:-$USER}"
CFG="${CFG:-config/cluster.json}"
mkdir -p evidencias
SALIDA="evidencias/E3 Conectividad desde $(hostname) $(date +%d-%m-%Y).txt"
HOSTS=$(python3 -c "import json;print(' '.join(n['host'] for n in json.load(open('$CFG'))['nodes'].values()))")
{
  echo "=== Verificación de conectividad desde $(hostname) - $(date -Is) ==="
  echo "--- tailscale status ---"; tailscale status 2>&1 || true
  echo "--- IP propia ---"; tailscale ip -4 2>&1 || true
  FALLOS=0
  for H in $HOSTS; do
    echo; echo "### ping a $H"
    if ping -c 3 -W 2 "$H"; then echo "PING OK $H"; else echo "PING FALLO $H"; FALLOS=$((FALLOS+1)); fi
    echo "### ssh a $H (solo clave pública, sin contraseña)"
    if ssh -o BatchMode=yes -o PasswordAuthentication=no -o ConnectTimeout=5 \
        -o StrictHostKeyChecking=accept-new "$USUARIO@$H" 'echo "SSH OK hacia $(hostname)"'; then
      echo "SSH OK $H"
    else
      echo "SSH FALLO $H"; FALLOS=$((FALLOS+1))
    fi
  done
  echo; echo "=== Resultado: $FALLOS fallos ==="
} 2>&1 | tee "$SALIDA"
echo "Registro guardado en: $SALIDA"
