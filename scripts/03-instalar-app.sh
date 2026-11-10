#!/usr/bin/env bash
# Crea el entorno virtual e instala dependencias. Ejecutar en la raíz del repo.
set -euo pipefail
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
if [ ! -f config/cluster.json ]; then
  cp config/cluster.example.json config/cluster.json
  echo "Edita config/cluster.json con las IPs de Tailscale"
fi
if [ ! -f .env ]; then
  echo "REDIS_PASSWORD=cambia-esta-clave" > .env; chmod 600 .env
  echo "Edita .env con la misma REDIS_PASSWORD usada en 02-configurar-redis.sh"
fi
echo "Listo. Prueba sin VMs:  PYTHONPATH=. .venv/bin/python -m coord.sim"
