# Guía paso a paso: de cero a las evidencias

Orden recomendado. Entrega: **11 de noviembre de 2026** en Moodle.

## 0. Aviso importante sobre la norma 8 del taller

La norma dice: *“No se usan servicios en la nube de pago, VPS ni servidores de terceros. Los recursos se ejecutan en las VM del grupo.”* Una VM de Google Cloud (aunque sea con crédito gratuito) puede interpretarse como VPS/nube de terceros. **Antes de entregar, pregúntale al docente por escrito** si se acepta GCP con la prueba gratuita. Si no lo acepta, el código no cambia: solo cambia dónde corren las VM (VirtualBox/VMware en los computadores del grupo, con red *bridged* o NAT; Tailscale las une igual). Ver sección 9.

## 1. Qué es Tailscale y cómo se usa (lo mínimo)

Tailscale crea una **red privada virtual** (WireGuard) entre tus dispositivos: cada uno recibe una IP estable `100.x.y.z` y se hablan directo, sin abrir puertos ni configurar el router. Al conjunto se le llama **tailnet**.

```bash
sudo tailscale up            # une esta máquina a la tailnet (imprime un enlace para autenticar)
tailscale status             # lista de máquinas de la tailnet y si están conectadas
tailscale ip -4              # la IP 100.x.y.z de ESTA máquina  (la que va en cluster.json)
tailscale ping 100.x.y.z     # ping a nivel Tailscale (indica si va directo o por relevo DERP)
sudo tailscale down          # desconecta
```

* En tu PC Windows ya está instalado: ábrelo desde la bandeja del sistema e inicia sesión con **la misma cuenta** con la que se unirán las VM.
* Cómo conformar la tailnet del grupo: lo más simple es que **una sola persona** (dueña de la cuenta) una las 3 VM y su PC; a los demás integrantes se les **comparte** acceso (panel de administración → *Machines* → *Share*) o se les invita como usuarios. Revisa los límites del plan gratuito vigente (usuarios por tailnet).
* Los puertos del sistema (7001 de la app, 6379 de Redis) quedan **solo dentro de la tailnet**: no abras nada en el firewall público de GCP.

## 2. Crear las 3 VM en Google Cloud (opción GCP)

Con la consola web o con `gcloud` (ya instalado en tu PC; primero `gcloud auth login` y `gcloud config set project TU_PROYECTO`):

```bash
# Nodos 1 y 2: 2 GB.   Nodo 3 (líder inicial, aloja la BD): 3 GB.
gcloud compute instances create nodo1 --zone=us-central1-a --machine-type=e2-small \
  --image-family=debian-13 --image-project=debian-cloud --boot-disk-size=20GB
gcloud compute instances create nodo2 --zone=us-central1-a --machine-type=e2-small \
  --image-family=debian-13 --image-project=debian-cloud --boot-disk-size=20GB
gcloud compute instances create nodo3 --zone=us-central1-a --custom-cpu=2 --custom-memory=3GB \
  --image-family=debian-13 --image-project=debian-cloud --boot-disk-size=20GB
```

* `e2-small` = 2 GB. Para el nodo 3 se usa un tipo personalizado de 3 GB (el taller pide exactamente 3 GB).
* Sin entorno gráfico: las imágenes de Debian de GCP ya son de servidor.
* **Apaga las VM cuando no las uses** (`gcloud compute instances stop nodo1 nodo2 nodo3 --zone=us-central1-a`) para no gastar crédito. Al terminar el curso: `gcloud compute instances delete ...`.

## 3. SSH por clave pública

En tu PC (PowerShell o Git Bash):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/taller1 -C "tu_usuario"     # crea clave privada y .pub (NO se sube a Git)
```

Registra la clave pública para las VM (GCP la instala en `authorized_keys`):

```bash
# el formato es  USUARIO:CLAVE_PUBLICA
echo "tu_usuario:$(cat ~/.ssh/taller1.pub)" > claves.txt
gcloud compute project-info add-metadata --metadata-from-file ssh-keys=claves.txt
ssh -i ~/.ssh/taller1 tu_usuario@IP_EXTERNA_DE_nodo1       # primera entrada (IP en `gcloud compute instances list`)
```

Para que los nodos se conecten **entre sí** por SSH (requisito de E3), cada nodo necesita una clave: en cada VM `ssh-keygen -t ed25519` y copia su `~/.ssh/id_ed25519.pub` a las `authorized_keys` de los otros dos (`ssh-copy-id` o pegando la línea).

En cada VM, el script `01-preparar-vm.sh` desactiva la contraseña (`PasswordAuthentication no`) **solo si ya hay una clave autorizada**, y muestra la configuración efectiva (evidencia del requisito).

## 4. Tailscale en las VM y verificación de conectividad (E3)

En cada VM:

```bash
git clone <URL_DEL_REPO> && cd taller1-coordinacion-datos
sudo ./scripts/01-preparar-vm.sh
sudo tailscale up                       # abre el enlace en tu navegador y aprueba
tailscale ip -4                         # anota las 3 IPs
cp config/cluster.example.json config/cluster.json   # pega las IPs 100.x.y.z de los nodos 1, 2, 3
./scripts/00-verificar-conectividad.sh tu_usuario    # ping + SSH hacia los demás -> evidencias/E3 ...txt
```

Guarda esos 3 archivos (uno por nodo) como **E3**.

## 5. Redis y aplicación

En cada VM (misma contraseña en las 3):

```bash
sudo REDIS_PASSWORD='una-clave-larga' ./scripts/02-configurar-redis.sh
./scripts/03-instalar-app.sh                 # crea .venv, config/cluster.json (si falta) y .env
nano .env                                    # REDIS_PASSWORD=una-clave-larga
sudo cp deploy/coord-nodo.service /etc/systemd/system/coord-nodo@.service
sudo nano /etc/systemd/system/coord-nodo@.service     # reemplaza USUARIO y RUTA (ej. /home/tu_usuario)
sudo systemctl daemon-reload
sudo systemctl enable --now coord-nodo@1     # en la VM 1   (@2 en la VM 2, @3 en la VM 3)
journalctl -u coord-nodo@1 -f                # ver el log en vivo
```

Comprobación: con los 3 arriba, uno de ellos (el nodo 3) debe decir `*** ELEGIDO LÍDER ***`.

```bash
export PYTHONPATH=.
.venv/bin/python -m coord.ctl estado
.venv/bin/python -m coord.ctl sembrar
.venv/bin/python -m coord.ctl inventario
```

## 6. E4: elección y caída del líder

Desde un equipo con acceso SSH por clave a las tres VM (tu PC con Tailscale, o una de las VM):

```bash
SSH_USER=tu_usuario ./scripts/prueba-eleccion.sh
```

Hace: estado inicial → detiene el servicio del líder → espera la reelección → lo vuelve a iniciar (debe reconocer al nuevo y **no** recuperar el mando) → prueba de líder falso (debe ser rechazado). Entrega: `evidencias/E4 ...txt` + los `logs/nodo-N.log` de cada VM.

## 7. E5: experimento de partición

```bash
SSH_USER=tu_usuario ./scripts/experimento-particion.sh          # aísla al líder actual
CON_LATENCIA=1 SSH_USER=tu_usuario ./scripts/experimento-particion.sh   # variante opcional con tc netem
```

El script: siembra → tabla **antes** → `iptables` aísla al líder → espera reelección → escribe sobre `nodo1` en el líder viejo y en el nuevo + una vía seguidor → tabla **durante** → reconecta → espera reintegro → tabla **después** + `convergencia`. Resultados en `resultados/E5-experimento-particion.md` (tablas listas para el informe) y el log completo en `evidencias/`. Copia los logs de cada nodo (`logs/`) al repo (`evidencias/logs-nodo-N/`).

Comandos manuales equivalentes (para el informe, sección 2):

```bash
sudo ./scripts/particion.sh aislar        # iptables -I INPUT/OUTPUT -s/-d <IP de cada otro nodo> -j DROP
sudo ./scripts/particion.sh reconectar
sudo ./scripts/particion.sh latencia 100 20   # tc qdisc replace dev tailscale0 root netem delay 100ms 20ms
sudo ./scripts/particion.sh sin-latencia
```

Si `tc` no acepta `tailscale0`, usa la NIC física: `IFACE=ens4 sudo -E ./scripts/particion.sh latencia 100 20`.

## 8. Informe y entrega

1. El informe se genera con `python informe/generar_informe.py` y se exporta a PDF con `informe/exportar_pdf.ps1` (6–8 páginas, **la última es la bitácora de autoevaluación**, una por integrante, con su nombre). Se completa la bitácora en el `.docx` antes de exportar.
2. Sube a Moodle: URL del repo (E1) con commits de todos, PDF (E2), E3, E4, E5.
3. Verifica que el repo **no** contiene `*.pem`, `*.key`, `.ssh/`, `.env` ni `config/cluster.json`.

## 9. Alternativa: VM locales (si el docente no acepta GCP)

VirtualBox (funciona en Windows 11 Home): 3 VM Debian 13 *netinst* (sin entorno gráfico, instalar solo “servidor SSH” y “utilidades estándar”), 2 GB / 2 GB / 3 GB, adaptador de red **en puente** o NAT; instala Tailscale en cada una. Todo lo demás (scripts, config, experimentos) es idéntico. Cada integrante puede alojar una VM: Tailscale las une aunque estén en casas distintas.

## 10. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `ssh` pide contraseña o “Permission denied (publickey)” | Falta la clave pública en `~/.ssh/authorized_keys` del destino |
| Nadie es líder, log repite “sin mayoría” | Menos de 2 de 3 nodos se ven: revisa `tailscale status`, IPs de `cluster.json`, puerto 7001 |
| `NOAUTH` / `WRONGPASS` | `REDIS_PASSWORD` distinta entre nodos o `.env` mal |
| `Connection refused` a Redis de otro nodo | Redis solo en 127.0.0.1: re-ejecuta `02-configurar-redis.sh` (hace `bind` a la IP Tailscale) |
| `ctl` no responde de un nodo | El servicio no corre (`systemctl status coord-nodo@N`) |
| No convergen tras reconectar | Espera ~15 s; revisa `logs/nodo-N.log` por `REINTEGRO` y `CONFLICTO` |
