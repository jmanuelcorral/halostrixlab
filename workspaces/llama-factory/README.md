# LLaMA-Factory + LlamaBoard en Halo Strix

[Español](README.md) | [English](README.en.md)

Carpeta autocontenida para **construir y arrancar sólo la interfaz web** sobre
Docker y ROCm. No arranca ningún entrenamiento por sí sola ni administra otros
servicios del host.

## Estado y alcance

Objetivo: Linux con AMD Radeon 8060S Graphics (`gfx1151`) y ROCm. La base
indicada se validó en este repositorio; eso no certifica cada combinación de
modelo, dataset o entrenamiento. El POC de abajo es una receta existente que
debes revisar, no una prueba de entrenamiento superada. Consulta también la
[guía de configuración reutilizable](../../docs/configuracion-reutilizable-halo-strix.md).

## Versiones fijadas

- Base validada en este repositorio:
  `rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`
  (PyTorch `2.12.0+rocm7.14.0`, HIP 7.14).
- LLaMA-Factory `v0.9.5`, commit
  `7af909522a951e3ad9f022ea6f88b6755257eaa5`.

Las fuentes se descargan por commit, sin clonar `main`. Esto **no es un build
byte a byte reproducible**: APT y las dependencias transitivas Python se
resuelven durante cada build desde repositorios vivos y pueden cambiar. El
digest base y el commit hacen el build razonablemente repetible a nivel
funcional, no hermético. Para reproducir o revertir exactamente el artefacto,
conserva la imagen construida y su ID `sha256`, que `build.sh` registra desde
Docker (sin inventar hashes) en `.last-built-image`. El mismo ID garantiza la
misma imagen, no un entorno de ejecución idéntico: host, firmware, dispositivos
y datos montados siguen siendo externos.

## Preparación

Desde esta carpeta en el servidor:

```bash
cp .env.example .env
ls -l /dev/kfd /dev/dri/renderD*
readlink -f /dev/dri/by-path/*-render 2>/dev/null || true
stat -c '%n GID=%g grupo=%G permisos=%A' /dev/kfd /dev/dri/renderD128
```

Edita `RENDER_DEVICE` si no es `renderD128`. `DEVICE_GID` puede quedar vacío:
`start.sh` toma el GID del render node con `stat`; también se puede fijar.
Docker y Compose v2 deben existir y la cuenta debe acceder al daemon y a ambos
dispositivos. Si Docker requiere privilegios, usa `sudo ./start.sh`; el script
no habilita ni inicia el daemon.

Se necesitan Bash moderno (4.3+ por los namerefs de cleanup), utilidades GNU
(`stat`, `readlink`, `find`, `sed`, `awk`, `du`, `grep`) y espacio suficiente para
imagen/modelos/datos. El build requiere acceso a los registros, GitHub, APT y al
índice Python configurado. No instales ni ajustes drivers mediante estos scripts.
No sobrescribas un `.env` existente: copia la plantilla sólo en una instalación
nueva y conserva los valores locales fuera del repositorio.

### Variables

Las variables exportadas prevalecen sobre `.env` en build/start. `.env` no es
un almacén de tokens.

| Variable | Valor de ejemplo / función |
| --- | --- |
| `BASE_IMAGE` | Digest AMD completo indicado arriba |
| `LLAMAFACTORY_COMMIT` | SHA upstream completo indicado arriba |
| `LLAMAFACTORY_IMAGE` | `halostrix-llamafactory:v0.9.5-rocm7.14`, tag local de build |
| `RUN_IMAGE` | Vacío; opcionalmente ID de imagen conservada para start |
| `PIP_INDEX_URL` | `https://pypi.org/simple`; sin credenciales incrustadas |
| `RENDER_DEVICE` | `/dev/dri/renderD128`; verificar en el host |
| `DEVICE_GID` | Vacío: autodetección del GID del render node por start |
| `WEB_BIND` / `WEB_PORT` | `127.0.0.1` / `7860` |
| `SHM_SIZE` | `16g`, memoria compartida del contenedor; no ajusta la RAM/GTT host |
| `LOG_TAIL` | Variable de entorno opcional para logs; por defecto `100` líneas |

## Construir y arrancar

```bash
chmod +x build.sh start.sh stop.sh status.sh logs.sh scripts/common.sh
./build.sh
./start.sh
./status.sh
./logs.sh
./stop.sh
```

`build.sh` valida los inputs de build, construye la imagen con labels de
ownership exactos (`com.halostrix.project`, `com.halostrix.service`), revisión
upstream y base por digest, y guarda su ID inmutable real. `start.sh` valida
Docker, imagen local, render node,
permisos y puerto; crea persistencia, arranca con `--no-build` y espera el
healthcheck. Ambos son fail-fast e idempotentes. El bind inicial
`127.0.0.1:7860` sólo es accesible desde el host.

Para arrancar exactamente el último artefacto, sin resolver APT/Python:

```bash
RUN_IMAGE="$(cat .last-built-image)" ./start.sh
```

También puedes copiar ese ID a `RUN_IMAGE` en `.env`. `stop.sh`, `status.sh` y
`logs.sh` sólo validan Docker/Compose y usan valores neutros al renderizar
Compose: siguen gestionando un contenedor existente aunque no haya GPU, falte
`.env` o su configuración de arranque sea inválida.

No ejecutes `docker image prune` si necesitas rollback. Antes del siguiente
build, guarda el ID anterior fuera de `.last-built-image` o añade una etiqueta
propia con `docker image tag sha256:ID nombre:rollback`; ambas referencias
apuntan al mismo contenido local.

### Acceso LAN

En `.env`, cambia `WEB_BIND=0.0.0.0` y, si hace falta, `WEB_PORT`. Después
ejecuta `./start.sh` y abre `http://IP_DEL_HOST:7860`. No se supone ninguna IP.
Limita el puerto a la subred de confianza con el firewall ya administrado del
host; este workspace no modifica reglas. LlamaBoard no aporta autenticación
perimetral: no lo publiques en Internet y no guardes tokens en `.env`.

## Primer POC LoRA BF16 (no QLoRA)

Antes de entrenar, detén manualmente cualquier otra carga GPU que tú decidas:
entrenamiento e inferencia simultáneos compiten por GPU/GTT/RAM. Estos scripts
**no paran ni reconfiguran servicios ajenos**.

1. Coloca o descarga el modelo sin cuantizar en `data/models/`.
2. Coloca el dataset en `data/datasets/` y añade allí `dataset_info.json`
   según el formato de LLaMA-Factory.
3. En LlamaBoard selecciona SFT, LoRA, BF16, batch 1, acumulación 8, longitud
   1024, hasta 100 muestras y salida `/workspace/saves/poc-lora-bf16`.
4. Comprueba que no aparece cuantización de 4/8 bits: eso sería QLoRA.
5. Inicia el entrenamiento **sólo tras revisar** modelo, template y dataset.

Como alternativa, copia `examples/poc-lora-bf16.yaml` a `data/config/`,
sustituye ambos `CHANGE_ME` y revísalo. No se invoca automáticamente. Para el
primer gate, vigila pérdida finita, uso real de `AMD Radeon 8060S Graphics`,
temperatura, memoria y un checkpoint reanudable.

## Persistencia

| Host | Contenedor | Contenido |
| --- | --- | --- |
| `data/hf-cache` | `/workspace/hf-cache` | caché Hugging Face |
| `data/models` | `/workspace/models` | modelos explícitos |
| `data/datasets` | `/workspace/data` | datasets y catálogo |
| `data/outputs` | `/workspace/saves` | adaptadores/checkpoints |
| `data/cache` | `/workspace/cache` | Torch/Triton/compilación |
| `data/config` | `/workspace/config` | configuraciones locales |
| `data/logs` | `/workspace/logs` | `llamaboard.log` |

`docker compose down` no borra estos bind mounts, pero se recomienda
`./stop.sh`. Nunca uses `rm -rf data`, `down -v` ni `docker system prune`
sin copia y autorización.

## Actualización y rollback

1. Detén la UI y respalda `data/config` y `data/outputs`.
2. Verifica un release/tag en GitHub y resuélvelo a SHA completo mediante la
   API primaria `.../repos/hiyouga/LlamaFactory/git/ref/tags/TAG`.
3. Cambia `LLAMAFACTORY_COMMIT` y usa un **nuevo**
   `LLAMAFACTORY_IMAGE`; conserva el nombre anterior.
4. Ejecuta `./build.sh`, conserva la imagen y el ID mostrado, luego
   `./start.sh` y valida health/GPU antes de entrenar.
5. Para rollback exacto **de la imagen**, fija `RUN_IMAGE=sha256:...` al ID
   conservado y ejecuta `./start.sh`; no se reconstruye ni se vuelven a
   resolver dependencias.

Para cambiar ROCm, usa únicamente una imagen AMD PyTorch compatible fijada por
digest. No uses variantes CUDA/NVIDIA ni mezcles userspace del host.

## Diagnóstico y limpieza segura

`cleanup.sh` está diseñado para este workspace y rechaza raíces, enlaces y
rutas ambiguas. Admite `<repo>/workspaces/llama-factory` y
`$HOME/ai/llama-factory`, sin fijar un usuario concreto. Para el segundo layout,
ejecuta como el propietario: `sudo` puede cambiar `HOME` y provocar rechazo.
Por defecto sólo hace inventario:

```bash
chmod +x cleanup.sh
./cleanup.sh                 # igual que --dry-run
./cleanup.sh --dry-run
```

El inventario muestra los contenidos de los siete directorios permitidos bajo
`data/` y únicamente contenedores, la red exacta e imágenes cuya atribución se
valida por labels exactos. En imágenes también deben coincidir la revisión y la
base inmutable configuradas; un tag, `.env`, `RUN_IMAGE` o
`.last-built-image` sólo aportan candidatos y nunca prueban ownership. Cada
recurso se inspecciona otra vez inmediatamente antes de borrarlo. Este Compose
sólo tiene bind mounts: `cleanup.sh` no busca ni elimina Docker volumes. No usa
ningún `prune`, comodín ni coincidencia parcial.

```bash
./cleanup.sh --all           # exige escribir la frase mostrada
./cleanup.sh --all --yes     # automatización explícita, sin pregunta
./cleanup.sh --all --include-base
```

`--all` pide la frase exacta `ELIMINAR halostrix-llamafactory SIN RECUPERACION`.
Consulta las opciones con `./cleanup.sh --help` (también `-h`).

**Aviso irreversible:** `--all` elimina también modelos, datasets,
adaptadores/checkpoints, configuraciones, logs y todas las cachés dentro de
`data/{hf-cache,models,datasets,outputs,cache,config,logs}`, además de los
recursos Docker exactos del proyecto. **No hay recuperación** salvo copia
externa. `--yes` solo no borra; necesita `--all`; `--dry-run` domina cualquier
orden o combinación, incluso `--all --yes`. Si Docker no está disponible,
`--all` puede limpiar explícitamente sólo esos datos, lo registra como fallo y
termina nonzero. Los fallos Docker se aíslan: los demás recursos que aún puedan
revalidarse y los paths contenidos siguen procesándose, y el resumen informa
la limpieza parcial antes de devolver nonzero.

La base ROCm compartida se conserva siempre, salvo que se añada
`--include-base` a `--all`. En modo interactivo esto requiere una segunda frase
con su digest exacto. Intencionalmente, `--yes` omite tanto la confirmación
general como esta segunda confirmación, pero sólo al combinarse con ambos flags
explícitos `--all --include-base`. La referencia y el ID se validan contra
`RepoDigests` de nuevo inmediatamente antes de borrarla.
El script no administra Lemonade, procesos, puertos ni servicios ajenos.
Después de limpiar: `cp .env.example .env` si falta, `./build.sh` y
`./start.sh`.

- `permission denied /dev/kfd` o render: revisa GID/permisos y vuelve a entrar
  en sesión tras cualquier cambio de grupos; no uses `privileged`.
- GPU ausente: `docker compose ...` debe mostrar sólo `/dev/kfd` y el render
  configurado. Comprueba dentro con
  `docker compose exec llamaboard python3 -c "import torch; print(torch.version.hip, torch.cuda.is_available(), torch.cuda.get_device_name(0))"`.
- UI `unhealthy`: usa `./logs.sh`, revisa puerto ocupado y espacio con
  `df -h`; el arranque puede tardar durante el primer build.
- OOM: reduce modelo, longitud, batch y muestras.
- Detener/eliminar sólo el contenedor: `./stop.sh` y luego
  `docker compose --env-file .env rm -f llamaboard`.
- Eliminar una imagen concreta, preservando datos:
  `docker image rm halostrix-llamafactory:v0.9.5-rocm7.14`.

No se usa red host, socket Docker, `ipc:host`, `/opt/rocm` del host, reinicio
automático ni mapeo completo de `/dev/dri`.

## Pruebas locales sin GPU ni daemon real

La plataforma de referencia es **Linux con Bash/utilidades GNU y symlinks
reales**. Desde este workspace:

```bash
for script in ./*.sh scripts/*.sh tests/*.sh; do bash -n "$script" || exit; done
bash tests/test-cleanup.sh
docker compose --env-file .env.example config --quiet
```

La última orden sólo valida Compose y requiere el plugin, no arranca Docker
workloads. El runner usa un Docker falso y datos sintéticos en
`tests/.sandbox`, que elimina al salir. Reserva esa ruta para tests. Comprueba
dry-run en ambos órdenes, continuación tras fallo parcial (3 intentos Docker,
2 correctos, 1 fallido), rechazo de recursos ajenos, ausencia de volúmenes,
layouts portables, espacios y symlinks. No ejecuta el cleanup sobre datos reales.
`PASS: cleanup, ...` indica éxito; cualquier aserción fallida termina nonzero.
Los diagnósticos de los scripts Bash se mantienen en español.

### Tests sandbox desde Windows

Git Bash sólo sirve para estos tests offline si crea **symlinks nativos reales**.
Su `ln -s` predeterminado puede copiar el directorio: no constituye un fixture
válido de rechazo de enlaces. El runner ahora falla antes de llamar Docker con
`ERROR: cleanup tests require real symlinks` cuando falta este requisito.
No interpretes ese fallo como regresión de cleanup ni como test pasado/omitido.

Desde PowerShell en la raíz del repo, con Git Bash ya instalado:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -c 'export MSYS=winsymlinks:nativestrict; bash workspaces/llama-factory/tests/test-cleanup.sh'
```

`winsymlinks:nativestrict` exige enlaces nativos y falla en vez de copiar.
**No concede permisos** de symlink en Windows. Si la cuenta o filesystem
actual no los permite, usa un entorno Linux autorizado ya disponible; no
cambies políticas, eleves privilegios ni sustituyas enlaces por copias para
hacer pasar la prueba. Esto no implica soporte del workload Linux/ROCm en Git Bash.

## Licencias y publicación

LLaMA-Factory upstream se distribuye bajo Apache-2.0; verifica las licencias y
avisos del commit y de cada dependencia/modelo/dataset antes de redistribuir.
La licencia de una herramienta no concede derechos sobre pesos, datasets o
resultados. No publiques `.env`, `data/`, `.last-built-image`, credenciales,
logs privados ni imágenes con datos locales.
Las reglas locales de Git y del contexto Docker excluyen configuraciones
privadas, datos y marcadores de imagen; `.env.example` sigue siendo publicable.
`.gitattributes` conserva LF en los scripts Bash al clonar desde Windows.
