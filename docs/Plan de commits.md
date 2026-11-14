# Plan de commits y push

Repositorio: https://github.com/JoseDavidQ/Taller-1-Final-SD.git

El taller exige **varios commits y de todos los integrantes**. El proyecto está dividido en 16 bloques lógicos que `aplicar-commits.sh` confirma de a uno. Cada persona ejecuta **solo sus bloques con su propia identidad de Git** y cada quien debería poder explicar lo que sube. Los bloques siguen el orden en que se construyó el trabajo (los posteriores dependen de los anteriores).

## Reparto sugerido (dos integrantes)

| Bloque | Contenido | Quién |
|---|---|---|
| 1 | Estructura, `.gitignore`, dependencias | José David |
| 2 | Verificación de conectividad (E3) y config de ejemplo | José David |
| 3 | Preparación de VM, Redis y systemd | José David |
| 4 | Reloj de Lamport y vectores de versión | Gerson |
| 5 | Mensajería TCP y configuración | Gerson |
| 6 | Almacén Redis / simulación en memoria | Gerson |
| 7 | Detección y resolución de conflictos + pruebas unitarias | José David |
| 8 | Nodo: algoritmo del matón con términos y quórum | Gerson |
| 9 | Cliente `ctl` | José David |
| 10 | Simulación y pruebas de integración (incluye prueba con Redis en Docker) | Gerson |
| 11 | Scripts de partición y de los experimentos E4/E5 | José David |
| 12 | Documentación (consistencia, guía, plan) | Gerson |
| 13 | README | José David |
| 14 | Evidencias E3 y E4 | José David |
| 15 | Evidencia E5 (tablas y logs de los tres nodos) | Gerson |
| 16 | Informe en PDF y su generador | José David |

Se puede cambiar el reparto; lo importante es que ambos tengan commits propios y que el orden numérico se respete.

## Procedimiento

1. Quien tenga la carpeta del proyecto (`taller1-coordinacion-datos`) hace, **una sola vez**:
   ```bash
   cd taller1-coordinacion-datos
   git init -b main
   git remote add origin https://github.com/JoseDavidQ/Taller-1-Final-SD.git
   git config user.name "Nombre Apellido"
   git config user.email "correo@ejemplo.com"
   ```
2. Confirma y sube sus bloques en orden. Ejemplo para el primer tramo:
   ```bash
   ./aplicar-commits.sh 1 3
   git push -u origin main
   ```
3. La otra persona clona el repo, **copia a su clon los archivos de los bloques que le tocan** (la carpeta completa sirve), configura su propio `user.name` y `user.email`, hace `git pull origin main` y ejecuta sus bloques:
   ```bash
   ./aplicar-commits.sh 4 6
   git push origin main
   ```
4. Alternen así hasta el bloque 16. Para ver el resultado: `git log --format='%h %an %s'`.

`./aplicar-commits.sh lista` muestra todos los bloques.

## Qué NO se sube (ya está en `.gitignore`)

* Claves privadas (`*.pem`, `*.key`, `.ssh/`), `.env` y `config/cluster.json` (tienen la contraseña de Redis y las IP).
* `scripts/gcp-crear-vms.ps1`: contiene la cuenta y el proyecto de nube; queda solo en tu PC.
* El `.docx` del informe (se sube el PDF).

Antes de publicar, revisa con `git status` que no aparezca nada de esa lista.

## Después de la entrega

Si hacen cambios (correcciones del informe, más evidencias), cada uno los confirma con mensajes propios, por ejemplo `Corrección del análisis CAP en el informe`. Así se ve trabajo real a lo largo de los días y no solo una carga inicial.
