#!/usr/bin/env bash
# Crea los commits del proyecto en bloques lógicos (el taller exige varios commits y
# de TODOS los integrantes). Cada integrante ejecuta SOLO los bloques que le tocan,
# con su propio nombre/correo de Git, y hace push; el siguiente hace pull y sigue.
#
#   git config user.name "Tu Nombre"; git config user.email "tu@correo"   (una vez)
#   ./aplicar-commits.sh lista          # muestra los bloques
#   ./aplicar-commits.sh 1              # commit del bloque 1
#   ./aplicar-commits.sh 1 3            # bloques 1 a 3 en orden
#
# Ver el reparto sugerido en docs/Plan de commits.md
set -euo pipefail
cd "$(dirname "$0")"
[ -d .git ] || git init -b main

bloque() {
  case "$1" in
    1) MSG="Estructura inicial: .gitignore, dependencias y paquete coord"
       FILES=(.gitignore .gitattributes requirements.txt coord/__init__.py evidencias/.gitkeep resultados/.gitkeep) ;;
    2) MSG="Verificación de conectividad inicial (E3) y configuración de ejemplo del clúster"
       FILES=(scripts/00-verificar-conectividad.sh config/cluster.example.json) ;;
    3) MSG="Preparación de VM: SSH solo con clave, Redis, entorno virtual y servicio systemd"
       FILES=(scripts/01-preparar-vm.sh scripts/02-configurar-redis.sh scripts/03-instalar-app.sh deploy/coord-nodo.service) ;;
    4) MSG="Reloj de Lamport y vectores de versión"
       FILES=(coord/clock.py) ;;
    5) MSG="Mensajería TCP+JSON, red simulada y carga de configuración"
       FILES=(coord/net.py coord/config.py) ;;
    6) MSG="Almacén del inventario: Redis maestro-réplica y simulación en memoria"
       FILES=(coord/store.py) ;;
    7) MSG="Detección y resolución de conflictos con vectores de versión y Lamport + pruebas"
       FILES=(coord/reconcile.py tests/__init__.py tests/test_vectores_y_reglas.py) ;;
    8) MSG="Nodo: algoritmo del matón con términos, quórum, latidos y certificado de líder"
       FILES=(coord/node.py) ;;
    9) MSG="Cliente ctl: estado, inventario, asignación, convergencia y snapshots para el informe"
       FILES=(coord/ctl.py) ;;
    10) MSG="Simulación local de 3 nodos y pruebas de integración (elección, partición, conflictos)"
       FILES=(coord/sim.py tests/test_cluster.py tests/prueba_redis_docker.py) ;;
    11) MSG="Scripts de partición (iptables, tc netem) y de los experimentos E4 y E5"
       FILES=(scripts/particion.sh scripts/experimento-particion.sh scripts/prueba-eleccion.sh) ;;
    12) MSG="Documentación: modelo de consistencia, guía de despliegue y plan de commits"
       FILES=("docs/Modelo de consistencia.md" "docs/Guía paso a paso.md" "docs/Plan de commits.md") ;;
    13) MSG="README con decisiones, mapa de requisitos, uso y referencias"
       FILES=(README.md aplicar-commits.sh) ;;
    14) MSG="Evidencias E3 y E4: conectividad inicial y elección de líder con caída del líder"
       FILES=("evidencias/E3 Conectividad desde taller1-nodo1 10-11-2026.txt" "evidencias/E4 Registro eleccion de lider 10-11-2026.txt") ;;
    15) MSG="Evidencia E5: experimento de partición (tablas y logs de los tres nodos)"
       FILES=("evidencias/E5 Registro experimento 10-11-2026.txt" resultados/E5-experimento-particion.md evidencias/logs-nodo-1 evidencias/logs-nodo-2 evidencias/logs-nodo-3) ;;
    16) MSG="Informe técnico del taller (PDF) y generador del informe"
       FILES=("informe/Informe Taller 1 Coordinación y Datos.pdf" informe/generar_informe.py informe/exportar_pdf.ps1 informe/recursos) ;;
    *) echo "bloque desconocido: $1"; exit 1 ;;
  esac
}

if [ "${1:-}" = "lista" ] || [ $# -eq 0 ]; then
  for i in $(seq 1 16); do bloque "$i"; printf '%2s  %s\n' "$i" "$MSG"; done
  exit 0
fi
DESDE="$1"; HASTA="${2:-$1}"
for i in $(seq "$DESDE" "$HASTA"); do
  bloque "$i"
  git add -- "${FILES[@]}"
  if git diff --cached --quiet; then
    echo "bloque $i: nada nuevo que confirmar"
  else
    git commit -m "$MSG"
    echo "bloque $i confirmado: $MSG"
  fi
done
