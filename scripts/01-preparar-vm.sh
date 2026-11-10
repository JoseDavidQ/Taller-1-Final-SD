# Prepara una VM Debian 13 :
# paquetes de SSH y Tailscale.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecutar con sudo"; exit 1; }

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip redis-server iptables iproute2 iputils-ping \
  openssh-server git curl jq

#  SSH: deshabilitar contraseña  
HOME_USER="${SUDO_USER:-root}"
AK="$(getent passwd "$HOME_USER" | cut -d: -f6)/.ssh/authorized_keys"
if [ ! -s "$AK" ]; then
  echo "ERROR: $AK no existe o está vacío. Agrega tu clave pública ANTES de deshabilitar la contraseña."
  exit 1
fi
cat > /etc/ssh/sshd_config.d/99-solo-clave.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
CONF
sshd -t
systemctl reload ssh || systemctl reload sshd
echo "configuración efectiva de SSH "
sshd -T | grep -Ei '^(passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|permitrootlogin)'

#  Tailscale 
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
echo
echo "Siguiente paso (interactivo):  sudo tailscale up"
echo "y abre el enlace que imprime para autenticar el nodo en la tailnet del grupo."
