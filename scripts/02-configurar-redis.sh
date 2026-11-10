#!/usr/bin/env bash
# Configura el Redis local del nodo. TODOS los nodos arrancan como maestros
# independientes; la capa de coordinación ejecuta REPLICAOF según el líder.
# Uso:  sudo REDIS_PASSWORD='clave-larga' ./scripts/02-configurar-redis.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar con sudo"; exit 1; }
: "${REDIS_PASSWORD:?Define REDIS_PASSWORD (la misma en los 3 nodos)}"
TS_IP="$(tailscale ip -4 | head -n1)"
CONF=/etc/redis/redis.conf
cp -n "$CONF" "$CONF.orig" || true
sed -i -E '/^(bind|requirepass|masterauth|protected-mode|appendonly|replica-read-only) /d' "$CONF"
cat >> "$CONF" <<CONF

# --- Taller 1 ---
bind 127.0.0.1 $TS_IP
protected-mode yes
requirepass $REDIS_PASSWORD
masterauth $REDIS_PASSWORD
replica-read-only yes
appendonly yes
# Modo CP en Redis (el maestro rechaza escribir si no tiene réplicas): descomentar
# min-replicas-to-write 1
# min-replicas-max-lag 5
CONF
systemctl restart redis-server
sleep 1
redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping
redis-cli -a "$REDIS_PASSWORD" --no-auth-warning info replication | head -5
echo "Redis escuchando en 127.0.0.1 y $TS_IP"
