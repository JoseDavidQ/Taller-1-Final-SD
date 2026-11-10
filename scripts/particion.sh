#!/usr/bin/env bash
# Partición de red con iptables (entrada y salida) y latencia opcional con tc netem.
# Se ejecuta EN el nodo que se quiere aislar. Solo bloquea el tráfico hacia/desde las
# IPs Tailscale de los OTROS nodos del clúster; el SSH de administración (desde tu
# computador, que no está en cluster.json) y los comandos de ctl siguen funcionando.
#
#   sudo ./scripts/particion.sh aislar          # bloquea a los demás nodos
#   sudo ./scripts/particion.sh reconectar      # quita las reglas
#   sudo ./scripts/particion.sh estado          # muestra reglas
#   sudo ./scripts/particion.sh latencia 100 20 # +100 ms +-20 ms (opcional)
#   sudo ./scripts/particion.sh sin-latencia
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar con sudo"; exit 1; }
CFG="${CFG:-config/cluster.json}"
IFACE="${IFACE:-tailscale0}"   # si netem no funciona en tailscale0, usar la NIC física (ej. ens4)
MI_IP="$(tailscale ip -4 | head -n1)"
OTROS=$(python3 -c "import json;print('\n'.join(n['host'] for n in json.load(open('$CFG'))['nodes'].values()))" | grep -vx "$MI_IP" || true)
TAG="coord-particion"

borrar_reglas() {
  for CH in INPUT OUTPUT; do
    while iptables -S "$CH" | grep -q -- "--comment $TAG"; do
      N=$(iptables -L "$CH" --line-numbers -n | grep "$TAG" | head -n1 | awk '{print $1}')
      iptables -D "$CH" "$N"
    done
  done
}

case "${1:-}" in
  aislar)
    borrar_reglas
    for IP in $OTROS; do
      iptables -I INPUT  -s "$IP" -m comment --comment "$TAG" -j DROP
      iptables -I OUTPUT -d "$IP" -m comment --comment "$TAG" -j DROP
    done
    echo "$(date -Is) NODO AISLADO de: $(echo $OTROS)" ;;
  reconectar)
    borrar_reglas
    echo "$(date -Is) NODO RECONECTADO" ;;
  estado)
    iptables -L INPUT -n -v --line-numbers | grep -E "Chain|$TAG" || true
    iptables -L OUTPUT -n -v --line-numbers | grep -E "Chain|$TAG" || true
    tc qdisc show dev "$IFACE" || true ;;
  latencia)
    tc qdisc replace dev "$IFACE" root netem delay "${2:-100}ms" "${3:-20}ms"
    echo "latencia ${2:-100}ms +-${3:-20}ms en $IFACE" ;;
  sin-latencia)
    tc qdisc del dev "$IFACE" root 2>/dev/null || true
    echo "latencia quitada" ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
