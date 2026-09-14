# Unsloth Studio para Halo Strix (PyTorch 2.11 / ROCm 7.14)

[Español](README.md) | [English](README.en.md)

Workspace local y autocontenido para construir y operar la web de Unsloth
Studio en un host remoto `gfx1151`. No administra Lemonade ni otros procesos,
puertos o servicios del host.

## Estado del stack: UI validada; entrenamiento no validado

La base oficial AMD/ROCm está fijada por digest completo de registry:

`rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80`

Nombre y tag de procedencia:
`rocm/pytorch:rocm7.14_ubuntu24.04_py3.12_pytorch_release_2.11.0`.
El build no usa ese tag mutable: usa exclusivamente el digest anterior,
confirmado directamente contra Docker Registry y mediante inspección local.

La inspección dentro de la base devuelve PyTorch `2.11.0+rocm7.14.0`, torchvision
`0.26.0+rocm7.14.0`, torchaudio `2.11.0+rocm7.14.0`, triton
`3.7.1+git0263a6a6.rocm7.14.0` y HIP `7.14.60850`. PyTorch 2.11 está dentro
del rango upstream de Unsloth `<2.12`; esto habilita el build, pero no constituye
por sí solo una afirmación de soporte funcional. La compatibilidad se acepta
únicamente después de superar build, imports, GPU gfx1151, health y UI.

Validación del 2026-09-01: build y `pip check` correctos; el resolver conservó
el stack AMD; `import torch`, `import triton`, `import unsloth`, health y SPA
pasaron; Torch detectó `AMD Radeon 8060S Graphics`, `gfx1151` y GPU disponible.
`bitsandbytes` no está instalado, por lo que QLoRA 4-bit no está disponible.
Unsloth Zoo avisó que su ruta FLA no considera Triton soportado en esta
plataforma y usaría CPU para esa ruta. No se inició entrenamiento, así que este
resultado valida Studio web y detección GPU, no compatibilidad de entrenamiento.

La configuración se identifica mediante el tag local
`e18a069-rocm7.14-torch2.11` y el label OCI
`com.halostrix.stack=pytorch-2.11-rocm-7.14-gfx1151`. El build conserva las
versiones exactas de torch, torchvision, torchaudio y triton de la base como
constraints normales del resolver, ejecuta `pip check` y falla si cualquiera
cambia o aparece un paquete CUDA/NVIDIA. No usa `--no-deps`, no altera metadata
y no fuerza un stack fuera del rango declarado por upstream.
La fuente se instala con su extra oficial `huggingface`, que declara
`unsloth_zoo`, torchvision y triton; el stack AMD existente continúa fijado por
constraints y se compara byte por byte en su manifest de versiones antes y
después del resolver.

## Fijaciones verificadas (2026-09-01)

- Unsloth: commit firmado actual
  `e18a069c15cde98c7af77ccdb952254db8b0315d`.
- Tarball codeload del commit: SHA-256
  `52037b47de581f360e1db0a2072e65202d8993782e99f0300f181df93c63eeb8`.
- Node `22.12.0-bookworm-slim`: índice OCI por digest
  `node@sha256:35531c52ce27b6575d69755c73e65d4468dba93a25644eed56dc12879cae9213`.
- `studio/frontend/package-lock.json` pertenece al mismo tarball. El frontend
  no viene precompilado en source: el stage Node usa `npm ci` y `npm run build`,
  y copia `studio/frontend/dist`.
- CLI headless verificado en la fuente y en el script CI primario:
  `unsloth studio -H 0.0.0.0 -p 8888`. No se usa `--api-only`, pues ese flag
  deshabilita el frontend.
- Healthcheck real: `GET /api/health`.
- Rutas verificadas en
  `studio/backend/utils/paths/storage_roots.py`.

Fuentes primarias:

- `https://github.com/unslothai/unsloth/commit/e18a069c15cde98c7af77ccdb952254db8b0315d`
- `https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/pyproject.toml`
- `https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/studio/backend/utils/paths/storage_roots.py`
- `https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/.github/scripts/boot-studio-api-only.sh`

La fuente Core (`unsloth/*`) es Apache-2.0. Studio y CLI (`studio/*`,
`unsloth_cli/*`) son AGPL-3.0-only. Las licencias originales permanecen en el
tarball/imagen; redistribuir una imagen o una modificación exige respetar sus
obligaciones, incluida la oferta de fuente correspondiente de AGPL.

## Preparación y operación

Requisitos: host Linux AMD `gfx1151`, dispositivos `/dev/kfd` y un render node,
Docker con Compose v2 y acceso autorizado al daemon, Bash 4+ y utilidades GNU
(`stat`, `readlink`, `find`, `sed`, `awk`, `grep`). El build necesita acceso a
registros, GitHub/codeload, APT, npm y al índice Python; reserva espacio para
imágenes y datos. Los scripts no instalan ni ajustan drivers.
Consulta la [guía de configuración reutilizable](../../docs/configuracion-reutilizable-halo-strix.md).

En el host Linux remoto, desde este directorio (copia `.env.example` sólo si no
existe `.env`; no sobrescribas configuración privada):

```bash
cp .env.example .env
chmod 600 .env
ls -l /dev/kfd /dev/dri/renderD*
readlink -f /dev/dri/by-path/*-render 2>/dev/null || true
stat -c '%n GID=%g grupo=%G permisos=%A' /dev/kfd /dev/dri/renderD128
```

Configura en privado `UNSLOTH_STUDIO_PASSWORD` con un valor largo, aleatorio y
exclusivo, `RENDER_DEVICE` con el render correcto y `DEVICE_GID` con su GID
numérico observado. **No hay autodetección de `DEVICE_GID` en este workspace**:
queda vacío en la plantilla y se requiere explícitamente.

```bash
chmod +x build.sh start.sh stop.sh status.sh logs.sh cleanup.sh scripts/common.sh
./build.sh
./start.sh       # siempre usa --no-build
./status.sh
./logs.sh
./stop.sh
```

`build.sh` y `start.sh` están separados. Un build exitoso registra
atómicamente el ID inmutable real en `.last-built-image`; cuando cambia,
desplaza el ID anterior a `.previous-built-image`. Un build o inspect fallido
no modifica ninguno, y reconstruir el mismo ID conserva el previous. Para
seleccionar cualquiera de los dos:

```bash
RUN_IMAGE=last ./start.sh
RUN_IMAGE=previous ./start.sh
```

También se admite el ID completo. Antes de arrancar, toda referencia se
inspecciona y debe tener los labels exactos de proyecto, servicio, revisión y
commit; una imagen ajena se rechaza.
`UNSLOTH_STUDIO_PASSWORD` permanece exclusivamente en `.env` (modo 600) y se
entrega al bootstrap oficial de Studio. Consulta las credenciales sólo en tu
configuración privada local; nunca las imprimas, copies a logs ni publiques.
Si ya existe un usuario en la DB de autenticación persistente, el entrypoint
retira la variable del proceso de arranque: cambiar `.env` no restablece la
contraseña existente. Usa la gestión de credenciales oficial de Studio.

El bind predeterminado es `127.0.0.1:8888`. Cambia `WEB_BIND` sólo tras
establecer autenticación y controles de red adecuados. El contenedor corre
como el UID/GID no-root del propietario host de los datos. `start.sh` usa
`id -u`/`id -g`, o `SUDO_UID`/`SUDO_GID` si se invoca mediante `sudo`, corrige
la propiedad de los cuatro bind mounts sin permisos globales y falla si no
puede dejarlos escribibles. La imagen conserva UID/GID `10001` como fallback.
Compose añade además el GID suplementario de render configurado explícitamente,
por lo que cambiar el usuario primario no elimina acceso GPU.
Se pueden fijar explícitamente `HOST_UID` y `HOST_GID` en el entorno.
Los directorios padre internos son atravesables (`0755`) para que el UID/GID
runtime pueda alcanzar los bind mounts, sin hacer escribible ningún padre.
El entrypoint local crea únicamente el enlace administrado
`data/studio/unsloth_studio -> /opt/venv` que la CLI oficial exige para
reconocer una instalación preparada; rechaza cualquier objeto distinto que ya
exista en esa ruta.

No usa `privileged`, socket Docker, red host, `ipc:host`, `/opt/rocm` del host,
`HSA_OVERRIDE_GFX_VERSION`, reinicio automático ni mapeo completo de
`/dev/dri`.

### Variables

| Variable | Valor de ejemplo / función |
| --- | --- |
| `BASE_IMAGE` / `NODE_IMAGE` | Digests completos AMD/Node indicados arriba |
| `UNSLOTH_COMMIT` / `UNSLOTH_TARBALL_SHA256` | SHA de fuente y checksum indicados arriba |
| `UNSLOTH_IMAGE` | `halostrix-unsloth-studio:e18a069-rocm7.14-torch2.11` |
| `PIP_INDEX_URL` | `https://pypi.org/simple`, sin credenciales incrustadas |
| `UNSLOTH_STUDIO_PASSWORD` | Vacío en plantilla; bootstrap privado obligatorio |
| `RENDER_DEVICE` | `/dev/dri/renderD128`; verificar en el host |
| `DEVICE_GID` | Vacío en plantilla; GID numérico del render, obligatorio |
| `HOST_UID` / `HOST_GID` | Exportaciones opcionales; en su ausencia se usan `SUDO_UID`/`SUDO_GID` o `id`; no-root |
| `WEB_BIND` / `WEB_PORT` | `127.0.0.1` / `8888` |
| `SHM_SIZE` | `16g`, memoria compartida del contenedor, no tuning de RAM/GTT |
| `RUN_IMAGE` | Vacío, `last`, `previous` o referencia/ID local validado |

Build/start leen las variables listadas de `.env` con preferencia por el entorno
exportado; **`HOST_UID`/`HOST_GID` se deben exportar**, no basta rellenarlas en
`.env` porque start calcula la identidad. `stop.sh`, `status.sh` y `logs.sh`
usan valores neutros al renderizar Compose, pero Compose sigue requiriendo la
variable de contraseña (puede obtenerla del `.env` local). No muestres la
salida completa de `docker compose config`: puede contener credenciales.
`start.sh` solicita el contenedor sin esperar health; compruébalo con
`./status.sh`, `./logs.sh` (sigue las últimas 200 líneas) y
`curl --fail http://127.0.0.1:8888/api/health` cuando se usa el bind predeterminado.
`stop.sh` hace `compose down`; conserva los bind mounts.

### GPU, actualización y rollback

Antes de cargar modelos o entrenar, revisa quién usa GPU/GTT/RAM y detén tú mismo
las cargas que procedan. Estos scripts nunca detienen Lemonade ni otros servicios.
No se ha validado entrenamiento; no interpretes health/UI como prueba de LoRA.

Conserva las imágenes y respalda los cuatro directorios de datos antes de
actualizar. No uses prune si necesitas rollback. `RUN_IMAGE=previous ./start.sh`
o un ID completo conservado revierte **la imagen**, no los datos ni migraciones
de DB. Los digests/SHA fijan las fuentes y bases, no todo APT/Python transitivo:
no se promete build hermético ni byte a byte reproducible.
Cambiar de revisión upstream exige revisar conjuntamente pins, checksum,
`EXPECTED_REVISION` en `scripts/common.sh`, `REVISION` y base en `cleanup.sh`,
labels y pruebas; no basta cambiar el SHA de `.env`. No uses CUDA/NVIDIA ni
mezcles `/opt/rocm` del host.

## Persistencia

| Host | Contenedor | Semántica |
| --- | --- | --- |
| `data/studio` | `/home/unsloth/.unsloth/studio` | Studio home completo: DB, auth, assets, outputs, exports, runs, caches y binarios |
| `data/hf-cache` | `/workspace/hf-cache` | `HF_HOME`, hub y Transformers |
| `data/projects` | `/workspace/projects` | `UNSLOTH_STUDIO_PROJECTS_HOME` |
| `data/tmp` | `/workspace/tmp` | temporales y caches de recetas/validadores |

Estas rutas corresponden a `studio_root`, `cache_root`, `outputs_root`,
`exports_root`, `tensorboard_root`, `project_workspaces_root` y `tmp_root` del
commit fijado. Los datos no son volúmenes Docker anónimos.

## Limpieza segura

Sólo admite `<repo>/workspaces/unsloth-studio` y
`$HOME/ai/unsloth-studio`. En el segundo caso, usa la cuenta propietaria:
`sudo` puede cambiar `HOME` y hacer que se rechace el layout.
Ayuda: `./cleanup.sh --help` o `-h`.

Inventario sin borrar (predeterminado):

```bash
./cleanup.sh
./cleanup.sh --dry-run
```

Limpieza interactiva:

```bash
./cleanup.sh --all
# frase: BORRAR HALOSTRIX UNSLOTH STUDIO
```

Automatización consciente (omite confirmaciones):

```bash
./cleanup.sh --all --yes
```

**Irreversible:** `--all` elimina DB/autenticación, modelos en caché, proyectos,
outputs/exports, runs y temporales de los cuatro directorios permitidos, además
de recursos Docker validados. Sólo una copia externa permite recuperar datos.
`--yes` sin `--all` no borra. La confirmación interactiva exige TTY.

La base ROCm se conserva. Para incluir **sólo el digest exacto compartido**:

```bash
./cleanup.sh --all --include-base
# segunda frase: BORRAR BASE ROCM COMPARTIDA
# o --all --include-base --yes en automatización
```

`--dry-run` domina incondicionalmente `--all` y `--yes`, independientemente
del orden. El script selecciona contenedores sólo cuando coinciden
simultáneamente los labels Compose de proyecto `halostrix-unsloth-studio` y
servicio `studio`. La única red admisible debe llamarse exactamente
`halostrix-unsloth-studio_default` y tener los labels exactos de proyecto y
network `default`. Compose declara únicamente bind mounts, así que no enumera
ni borra volúmenes Docker.

Las imágenes se resuelven a ID y deben tener simultáneamente los labels exactos
de proyecto, servicio, revisión OCI y commit fijado. `.env` y
`.last-built-image` y `.previous-built-image` son sólo candidatos no confiables
y jamás autorización.
Cada recurso se revalida inmediatamente antes del borrado. Un fallo Docker
individual no detiene los recursos independientes ni los datos validados; el
resumen cuenta errores y el proceso termina nonzero. Nunca realiza limpieza global.
Valida cada ruta real antes de vaciar únicamente `data/studio`,
`data/hf-cache`, `data/projects` y `data/tmp`. Conserva el workspace, `.env`,
documentación y scripts. Si Docker no existe o no responde, lo indica y aún
puede limpiar esos datos.
Si se pide borrado sin Docker disponible, el resultado es parcial y nonzero.
Para reconstruir, conserva o restaura `.env` privado (sin sobrescribirlo),
revisa GID/credenciales, y ejecuta `./build.sh` y `./start.sh`.

## Validación local (sin GPU ni daemon real)

Plataforma de referencia: **Linux con Bash/utilidades GNU y symlinks reales**.
El runner build/start también necesita GNU `mktemp`: el escritor atómico
existente crea ficheros intermedios dentro del workspace de pruebas, no en un
directorio temporal del sistema. Si el entorno prohíbe esa operación, no ejecutes
ese runner y repórtalo como **no ejecutado**, nunca como pasado.

```bash
for script in ./*.sh scripts/*.sh tests/*.sh; do bash -n "$script" || exit; done
bash tests/test-shell-files.sh
bash tests/test-build-start.sh
bash tests/test-cleanup.sh
bash tests/test-ownership.sh
# Valores sintéticos sólo para validar, nunca para arrancar:
DEVICE_GID=0 UNSLOTH_STUDIO_PASSWORD=validation-only-not-a-credential \
  docker compose --env-file .env.example config --quiet
```

`test-shell-files.sh` es un gate binario: falla ante cualquier byte CR en
cualquier `.sh` fuera de `data/`, además de ejecutar `bash -n`. El test de
ownership también limita su búsqueda a fuentes publicables. Los tests restantes sustituyen
Docker, `stat`, `id` y `chown` por fakes. Cubren rotación first/second build,
fallos sin cambio, rebuild del mismo ID, rechazo de ID malformado e imagen
ajena, previous propio/ajeno durante cleanup, además del
dry-run combinado y en distinto orden, imagen/tag ajenos, filtro de servicio,
fallo parcial con continuación y exit nonzero, rechazo de symlinks, ausencia
de volúmenes/prune, labels exactos y ownership con sudo simulado. No tocan
recursos ni datos reales.
Reserva los directorios `tests/sandbox`, `tests/build-start` y `tests/ownership`
para los runners: los crean y borran. Las líneas `...: OK` confirman éxito; un
fallo de aserción o sintaxis termina nonzero. Compose config sólo valida; no
demuestra build, health, GPU ni entrenamiento. Los diagnósticos Bash/Python
se mantienen en español. No publiques `.env`, datos, marcadores de imágenes
locales ni logs privados.
Las reglas locales de Git y del contexto Docker excluyen configuraciones
privadas, datos y marcadores de imagen; `.env.example` sigue siendo publicable.
`.gitattributes` conserva LF en Bash al clonar desde Windows.

### Tests sandbox desde Windows

El `ln -s` predeterminado de Git Bash puede copiar directorios en vez de crear
symlinks, invalidando la prueba de rechazo de enlaces. El runner cleanup
comprueba esta capacidad antes de llamar Docker y falla explícitamente con
`ERROR: cleanup tests require real symlinks`; nunca omite esas pruebas en silencio.

Desde PowerShell en la raíz del repo, con Git Bash ya instalado:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -c 'set -e; export MSYS=winsymlinks:nativestrict; for f in workspaces/unsloth-studio/tests/test-cleanup.sh workspaces/unsloth-studio/tests/test-build-start.sh workspaces/unsloth-studio/tests/test-ownership.sh workspaces/unsloth-studio/tests/test-shell-files.sh; do bash "$f"; done'
```

La orden completa exige todos los requisitos anteriores.
`winsymlinks:nativestrict` pide enlaces nativos reales y falla en vez de copiar;
**no concede permisos** en Windows. Si faltan permisos de symlink u otra
operación requerida, usa un entorno Linux autorizado ya disponible. No cambies
políticas, eleves privilegios, instales herramientas, sustituyas enlaces por
copias ni omitas runners en silencio para declarar suite completa.
Esto sólo adapta tests offline; no soporta ejecutar el workload Linux/ROCm en Git Bash.
