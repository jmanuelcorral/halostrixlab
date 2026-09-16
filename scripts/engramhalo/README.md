# EngramHalo — wrapper Docker invocable como `llama-server`

**Estado: experimental, NO desplegado.** Este directorio contiene únicamente
código y documentación de repositorio, validados con tests offline. Nada
aquí se ha ejecutado contra un host Halo real, un daemon Docker real, una
GPU real ni una imagen construida. No hay build de imagen incluido en este
cambio.

## Qué es

`llama-server` es un wrapper Python 3 (stdlib únicamente) que Lemonade
v11.9 puede invocar desde su directorio `rocm_bin`, donde espera encontrar
un ejecutable llamado exactamente `llama-server`. En vez de ejecutar el
motor `llama.cpp` directamente en el host, este wrapper traduce el `argv`
recibido a una invocación estrecha y auditable de `docker run`, apuntando a
una imagen **ya construida e instalada**, identificada por su digest o ID
inmutable (`sha256:...`). El wrapper **no construye, descarga ni instala**
esa imagen; eso es responsabilidad de un flujo de despliegue manual y
separado, fuera de este cambio.

## Por qué existe (contexto experimental)

Ejecutar el motor de inferencia dentro de un contenedor permite acotar
capacidades Linux (usuario no root, `--cap-drop=ALL`,
`--security-opt=no-new-privileges`), limitar qué directorios de modelos son
visibles (montajes de solo lectura explícitos) y evitar que el binario del
motor tenga acceso directo sin filtrar al resto del host. A cambio, no
elimina el hecho de que Docker en modo rootful requiere acceso equivalente
a root a nivel de administración del daemon; este wrapper no pretende ser
un sandbox completo de aislamiento de GPU o RAM, solo una capa de
contención de argumentos y capacidades más estrecha que invocar el binario
sin filtrar.

## Contrato del wrapper (v1)

### Entrada obligatoria: `ENGRAMHALO_CONFIG`

El wrapper **rehúsa arrancar** (antes de tocar Docker) si la variable de
entorno `ENGRAMHALO_CONFIG` no está definida, no es una ruta absoluta, no
apunta a un archivo real, no es JSON válido, o si el JSON no cumple el
esquema descrito abajo. El wrapper **nunca** lee `.env` reales del
repositorio ni de ningún otro sitio; toda configuración proviene
exclusivamente del archivo JSON señalado por esa variable.

Ver [`config.example.json`](./config.example.json) — usa únicamente
placeholders públicos con **sintaxis válida** (un digest `sha256` de
ejemplo, rutas de ejemplo bajo `/srv/engramhalo/...`), nunca una
configuración real ni auto-generada.

Campos requeridos:

| Campo | Requisito |
| --- | --- |
| `image` | `"<repo>@sha256:<64 hex>"` o `"sha256:<64 hex>"`. Tags mutables (`:latest`, nombres sin digest) se rechazan. |
| `engine` | Ruta absoluta al ejecutable Docker del host, debe existir y ser ejecutable. |
| `engine_server` | Ruta absoluta al binario `llama-server` **dentro** de la imagen (usado como `--entrypoint`). |
| `allowed_model_roots` | Lista no vacía de directorios absolutos permitidos para modelos. Se rechazan `/`, `/root`, `/home`, el `$HOME` actual, o cualquier ruta que contenga `.ssh`/`.config`. |
| `allowed_models` | Lista no vacía de `{ "model": <ruta absoluta>, "mmproj": <ruta absoluta o null> }`. Cada ruta debe resolver (tras `realpath`, sin escapes por symlink) dentro de `allowed_model_roots`. |
| `runtime_state_dir` | Directorio absoluto, ya existente, propiedad del usuario actual, modo `0700` exacto. Aquí viven `active.json`, los `.cid`, los locks (global y de puerto) y nada más. |
| `gpu_render_device` | Ruta absoluta al device file de render canónico, debe resolver (tras symlinks) exactamente a `/dev/dri/renderD<N>`. |
| `gpu_kfd_device` | Ruta absoluta al device file `/dev/kfd`; debe resolver exactamente a esa ruta. |
| `uid` / `gid` | Enteros positivos (no root, no `0`) que **deben coincidir** con el uid/gid real del proceso que invoca el wrapper (o un grupo suplementario para `gid`); no se permite suplantar un uid/gid arbitrario en el contenedor. |

`engine` se resuelve con `realpath` (los symlinks de distro tipo
`/usr/bin/docker -> docker-ce` son legítimos y se siguen), pero el binario
final debe ser un archivo regular, ejecutable por su dueño, propiedad de
`root` o del usuario actual, y **no** escribible por grupo u otros. El
propio archivo `ENGRAMHALO_CONFIG` recibe la misma comprobación de
propietario/permisos (root o usuario actual, sin escritura de grupo/otros),
además de no ser symlink.

Los dispositivos GPU se restringen a las rutas canónicas exactas
(`/dev/kfd`, `/dev/dri/renderD<N>`) tras resolver symlinks, y deben ser
character devices reales; cualquier ruta a un block device se rechaza
siempre. No existe ninguna variable de entorno ni flag en el wrapper que
relaje esta comprobación: los tests offline de este repo la ejercitan
mediante un monkeypatch de una función interna aislada
(`_gpu_canonical_ok`), no mediante un interruptor presente en el binario de
producción.

`allowed_models[].model` (y `.mmproj`, si se define) deben residir
**directamente** dentro de uno de los `allowed_model_roots` (un directorio
dedicado y aprobado por el operador), no en una subcarpeta anidada más
profunda; el wrapper monta de solo lectura el directorio contenedor
completo, así que ese directorio debe tratarse como dedicado a activos de
modelo aprobados, no como una carpeta general del host. Si el cliente no
pide explícitamente un `--mmproj`, el wrapper **no** añade automáticamente
el `mmproj` configurado para ese modelo, aunque exista en `allowed_models`.

No hay `allowlist` de modelos "abierta": cualquier `-m`/`--model` que no
coincida **exactamente** (tras resolver symlinks) con una entrada de
`allowed_models` se rechaza antes de invocar Docker.

### Flags de `llama-server` aceptados (whitelist estrecha v1)

| Flag | Notas |
| --- | --- |
| `-m` / `--model` | Obligatorio. Debe ser exactamente una entrada de `allowed_models`. |
| `--mmproj` | Opcional; debe coincidir con el `mmproj` aprobado para el modelo elegido. Nunca se añade automáticamente si el cliente no lo pide. |
| `--port` | Obligatorio, entero `1..65535`. |
| `--ctx-size` | Obligatorio, entero positivo. |
| `--parallel` | Obligatorio, debe ser exactamente `1` (no hay soporte para `N>=2` en v1). |
| `--host` | Opcional; si se omite se añade `127.0.0.1` automáticamente. Cualquier otro valor (incluido `0.0.0.0`) se rechaza: es el único binding permitido. |
| `--jinja`, `--metrics` | Flags booleanas sin valor. |
| `--flash-attn` | **Requiere valor**: `on`, `off` o `auto` (no es booleana). |
| `--mmap` / `--load-mode mmap` / `-lm mmap` | `mmap` es el único modo de carga soportado; el wrapper añade `--mmap` explícitamente en cada invocación aunque el cliente no lo pida, para que el comportamiento efectivo del motor nunca quede implícito. `--no-mmap` y cualquier otro `--load-mode` (`none`, `dio`, `vram`, ...) se rechazan. |
| `--cache-type-k` / `--cache-type-v` | Solo `f16` o `q8_0`. |
| `--spec-type` | Solo `none` (sin *speculative decoding* en v1). |
| `--no-kv-unified` | Flag booleana opcional. |
| `--cpu-moe` / `--n-cpu-moe` | Mutuamente exclusivas; `--n-cpu-moe` es un entero no negativo. |
| `--override-tensor` | Solo se acepta el valor exacto del perfil conocido `^per_layer_token_embd[.]weight$=CPU`; cualquier otro patrón se rechaza. |
| `-t`/`--threads`, `--threads-batch`, `-b`/`--batch-size`, `--ubatch-size`, `-ngl`/`--n-gpu-layers` | Enteros tipados, sin valores negativos donde no corresponde. |

Todo lo demás **falla cerrado**: no hay paso genérico de argumentos extra.
Se rechazan explícitamente (con mensaje claro, antes de Docker) flags como
`-hf`/`--hf-repo`/`-hfd` (descargas HuggingFace), `--model-url`, claves de
API, `--lora*`, `--draft*`/`--mtp*` (draft/MTP no autorizado en v1),
`--prompt-file`, `--prompt-cache*`, `--upload`, `--path`, `--rpc`, y
duplicados de cualquier flag (incluso si el valor repetido es idéntico).
Se admite la forma `--flag=valor` además de `--flag valor`.

### `--help` / `--version`

Si el único argumento recibido es `--help` o `--version`, el wrapper toma
un camino rápido: invoca `docker run --rm --pull=never --entrypoint
<engine_server> <image> --help` (o `--version`), **sin** dispositivos, sin
montajes, sin red explícita y sin locks de puerto ni cidfile. Aun así, el
lock **global** (ver más abajo) se adquiere antes que este camino rápido,
igual que antes de cualquier otra invocación del motor: un `--help`
concurrente con una invocación normal puede fallar por el lock, lo cual es
un comportamiento aceptado. Esto exige que la imagen ya exista localmente
(`--pull=never` siempre); si no existe, Docker fallará y el wrapper no
simula una respuesta de éxito.

### Invocación de `docker run` (camino normal)

Siempre: `--rm --init --sig-proxy=true --pull=never --network=host --user
<uid>:<gid> --group-add <gid del render> --group-add <gid del kfd>
--cap-drop=ALL --security-opt=no-new-privileges --device
<render>:<render> --device <kfd>:<kfd>`, montajes de solo lectura
únicamente de los directorios que contienen el modelo/mmproj elegidos,
`--entrypoint <engine_server>` (nunca el entrypoint por defecto de la
imagen), un `--name`/`--label engramhalo.run=<uuid>` únicos por invocación
(no PID), y `--cidfile` dentro de `runtime_state_dir`. Nunca `-it`, `-d`,
`--privileged`, `--cap-add`, montajes de `/`, del `$HOME` completo, ni de
`/var/run/docker.sock`.

Debido a que Lemonade espera un binding en `127.0.0.1`, y para simplificar
el diseño de red del PoC, se usa `--network=host` en Linux junto con
`--host 127.0.0.1` forzado en el propio `llama-server`; esto es un diseño
más simple que exponer `-p 127.0.0.1:<puerto>:<puerto>`, a costa de un
aislamiento de red más débil que un `bridge` (documentado aquí, no es un
sandbox de red).

### Ciclo de vida, bloqueo global y de puerto

- Antes de tocar el motor por cualquier camino (incluido `--help`/
  `--version`), el wrapper toma un `flock` exclusivo y no bloqueante
  **global**, único por `runtime_state_dir` (`locks/global.lock`),
  independiente del `flock` por puerto. Esto impone que solo exista una
  invocación activa del wrapper a la vez sobre ese `runtime_state_dir`,
  incluso en puertos distintos: no es solo un lock "por puerto".
- Antes de invocar `docker run` en el camino normal (no fastpath), se
  escribe de forma atómica un `active.json` dentro de `runtime_state_dir`
  con el `run_uuid`, `name`, ruta del `cidfile`, `engine`, `image`, puerto y
  PID de esta invocación. Si `active.json` **ya existe** de una ejecución
  previa, el wrapper **rehúsa arrancar**: no hay limpieza automática por
  puerto o por etiqueta; la recuperación es manual — inspeccionar a mano el
  `run_uuid`/`name`/`cidfile` registrados contra el estado real del motor
  configurado, y solo entonces borrar `active.json`.
- Se toma además un `flock` exclusivo, no bloqueante, por puerto sobre
  `runtime_state_dir/locks/port-<puerto>.lock` (rechaza symlinks). Si otra
  instancia del wrapper ya tiene el lock para ese puerto, se falla cerrado.
- Se hace además un *probe* best-effort de bind en loopback al puerto
  pedido (sujeto a TOCTOU, documentado como no perfecto; los tests
  monkeypatchean el socket).
- El `.cid` es un archivo nuevo y único por invocación (nombre `uuid4`),
  dentro de `runtime_state_dir/cids`; si ya existiera, se falla. El wrapper
  **nunca** pre-crea ese archivo (Docker rechaza un `--cidfile` que ya
  exista) y lo lee siempre con `O_NOFOLLOW`, verificando que es un archivo
  regular con un único enlace duro y propiedad del usuario actual antes de
  confiar en su contenido.
- Los manejadores de `SIGTERM`/`SIGINT` se instalan **antes** de lanzar
  `docker run`, y son estrictamente no bloqueantes: solo marcan una
  bandera interna. La detención real (`docker inspect` de propiedad,
  `docker stop -t 10`, y si sigue vivo `docker rm -f`) ocurre en el bucle
  principal, nunca dentro del propio manejador de señal (evita
  reentrancia y llamadas bloqueantes en el contexto de señal).
- Antes de detener o eliminar cualquier contenedor, el wrapper **verifica**
  (vía `docker inspect`) que el `--name` y la `--label
  engramhalo.run=<uuid>` coinciden exactamente con los de esta invocación.
  Si no coinciden, el wrapper **no toca nada**, lo reporta, y termina en
  fallo conservando `active.json` para recuperación manual — nunca hay un
  barrido por puerto o por nombre parecido.
- La limpieza final se ejecuta en **cualquier** camino de salida (código 0
  normal, fallo al lanzar Docker, señal, o error), no solo tras señal.
  Distingue explícitamente "contenedor no encontrado" (`docker inspect`
  reporta "no such object/container") de un error genérico del daemon: en
  el primer caso se asume ausencia verificada; en el segundo, no se puede
  afirmar que el contenedor esté ausente y el wrapper falla conservando
  `active.json`. Un cliente `docker run` que termina con éxito (`rc=0`)
  pero **nunca** llegó a escribir un `cid` se trata como fallo de arranque
  (código de salida no-cero), no como éxito.
- `active.json` y el `.cid` solo se eliminan tras una verificación exitosa
  de ausencia del contenedor propio; en cualquier otro caso (fallo de
  `stop`/`rm`, discrepancia de identidad, error de daemon irresoluble, o
  cid nunca observado) se conservan para inspección manual y el wrapper
  retorna un código de salida distinto de cero, incluso si el cliente
  `docker run` había retornado `0`.
- `--rm` en `docker run` no es por sí solo una garantía de limpieza: si el
  proceso `docker run` (cliente) recibe `SIGKILL` sin que el wrapper pueda
  reaccionar, el contenedor puede seguir vivo; el wrapper no intenta ningún
  vigilante en segundo plano para "arreglar" ese caso, documenta la
  limitación y confía en `active.json` (que sigue presente) para forzar una
  revisión manual en el siguiente arranque.
- El código de salida del `docker run` en primer plano se propaga tal
  cual (solo tras verificar limpieza exitosa); si el wrapper actuó por
  señal y la limpieza fue exitosa, propaga `128 + señal`.

### Qué NO hace este wrapper (v1)

- No construye ni descarga ninguna imagen (`--pull=never` siempre).
- No permite `-hf`/descargas de HuggingFace ni ningún flag de red de
  descarga de modelos.
- No soporta `--parallel` distinto de `1` (no hay `N=2` todavía).
- No soporta draft models ni MTP.
- No expone la red fuera de `127.0.0.1` vía el propio `llama-server`.
- No imprime en su propia salida el `argv` completo reenviado (los logs
  del propio servidor, heredados por stdout/stderr del contenedor, son
  responsabilidad de ese proceso, no del wrapper).
- No mezcla runtime local de agentes de openteam con este wrapper: es
  exclusivamente sobre la ruta de inferencia de Lemonade/llama.cpp.
- No soporta modelos partidos en *shards* (múltiples archivos GGUF por
  modelo) más allá de lo que permita compartir el mismo directorio
  dedicado del `allowed_model_roots`; no hay una lista explícita de
  archivos por modelo en el esquema v1 (limitación conocida, ver más
  abajo).

## Limitaciones conocidas (léelas antes de usar esto para algo real)

- Docker en modo rootful implica acceso administrativo equivalente a root
  sobre el daemon; este wrapper reduce la superficie del **proceso del
  motor**, no del daemon Docker en sí.
- No hay aislamiento perfecto de GPU/VRAM/GTT entre contenedores o entre
  el contenedor y el host: la contención de memoria/GTT descrita en la
  documentación de Halo Strix sigue aplicando dentro del contenedor. La
  configuración `max_loaded_models` en particular es un parámetro del
  propio servicio Lemonade (proceso residente en el host), no un límite de
  Docker ni una propiedad de este wrapper o de la imagen EngramHalo; un
  contenedor lanzado por este wrapper corre exactamente un motor
  `llama-server` por invocación y no tiene noción propia de "modelos
  residentes" — ese conteo y su desalojo LRU son responsabilidad exclusiva
  de Lemonade cuando actúa como orquestador aguas arriba.
- El *lock* de puerto y el *probe* de loopback no eliminan condiciones de
  carrera (TOCTOU); son mitigaciones, no garantías.
- No hay recompilación de EngramHalo con un commit fijo en este cambio:
  ese trabajo (imagen pineada, ABI de la librería empaquetada dentro del
  contenedor) es un prerequisito de despliegue posterior, explícito y
  manual, fuera del alcance de este PR.
- No existe todavía un flujo de "cargar N=1, descargar, verificar
  restauración de memoria" — eso requiere ventanas explícitas coordinadas
  por un humano contra un host real, documentadas aparte.
- `SIGKILL` sobre el propio wrapper (no interceptable) puede dejar el
  contenedor vivo sin que el wrapper lo sepa; la recuperación en ese caso
  es manual: usar `docker ps`/`docker inspect` con la etiqueta
  `engramhalo.run=<uuid>` reportada en `active.json` (que sigue en disco
  tras un `SIGKILL`) para localizarlo y decidir limpieza, nunca un barrido
  automático por puerto o nombre. El wrapper no ejecuta ningún vigilante
  en segundo plano para intentar "arreglar" ese caso automáticamente.
- El montaje de solo lectura del directorio del modelo/mmproj expone todo
  ese directorio al contenedor, no solo el archivo exacto seleccionado;
  por eso el esquema v1 exige que `allowed_models[].model`/`.mmproj` vivan
  directamente dentro de un `allowed_model_roots` dedicado (no en una
  subcarpeta general del host), pero sigue siendo responsabilidad del
  operador mantener ese directorio limitado a activos de modelo aprobados.
  Soportar *shards* con una lista de archivos explícita por modelo (en vez
  de un directorio completo) requeriría un cambio de esquema más amplio,
  fuera del alcance de este cambio.

## Build de la imagen (receta preparada, NO construida todavía)

Este cambio añade [`Dockerfile`](./Dockerfile), [`.dockerignore`](./.dockerignore)
y [`build-manifest.example.json`](./build-manifest.example.json) como
**receta de build únicamente**. Ninguno de estos archivos ha sido
construido, ninguna imagen ha sido generada ni pulled, y nada aquí ejecuta
`docker build`/`podman build` automáticamente. Preparar la receta es
explícitamente distinto de ejecutarla.

### Origen fijado (pin), verificado por lectura pública el 2026-09-16

- Fuente EngramHalo.cpp: `https://github.com/Aristo94/EngramHalo.cpp.git`,
  rama `strix-halo-qwen4exp`, commit exacto
  `15176583b358d791b7a73f210ef4ab9e167cfba7` (la rama es mutable; lo que
  ancla el build es el SHA completo, no el nombre de rama). `.gitmodules`
  en ese commit existe pero está vacío (`size=0`): no hay submódulos, y el
  `Dockerfile` lo vuelve a comprobar en build-time en vez de asumirlo.
- Parches de empaquetado (mismo commit exacto, repositorio distinto que
  comparte historia por relación de fork):
  `https://github.com/halo-box/strix-llama.cpp.git` @
  `15176583b358d791b7a73f210ef4ab9e167cfba7`,
  archivos `docs/strix-halo/llama-cpp-25992-rocm-host-buffer.patch` y
  `docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch`. El `Dockerfile`
  los aplica con `git apply --check` primero, detecta "ya aplicado" con
  `--reverse --check`, y falla explícitamente si ninguno de los dos casos
  aplica (el commit es fijo y conocido, así que una discrepancia aquí
  significa que el pin quedó obsoleto, no que sea un estado normal a
  ignorar con un warning).

  **Hallazgo verificado el 2026-09-16 (debug de un fallo real de `step15`
  de build):** el segundo parche
  (`llama-cpp-qwen38-per-buffer-mmap.patch`) deja de aplicar, tanto en
  sentido directo como inverso, contra el commit pineado exacto. La causa
  raíz (reproducida offline con un clon aislado y `git apply --check`, no
  supuesta) es que ese commit ya trae una funcionalidad de lectura
  perezosa de tensores (`TENSOR_READ_LAZY`) añadida de forma independiente
  aguas arriba, que generalizó justo la condición `if (use_mmap)` que el
  tercer *hunk* de ese parche reescribe; los otros dos *hunks* (cambio de
  `struct` en `llama-model-loader.h` y `buf_map` en `llama-model.cpp`)
  siguen aplicando con un simple desplazamiento de número de línea, sin
  conflicto de contenido. Se depositó un *rebase* revisado de ese único
  *hunk* en
  [`patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch`](./patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch)
  (ver la cabecera de ese archivo para el detalle completo), que el
  `Dockerfile` usa como *fallback* explícito y verificado por hash
  (`UPSTREAM_QWEN38_PATCH_SHA256` / `REVIEWED_QWEN38_OVERRIDE_SHA256`)
  únicamente si el parche verbatim de upstream no aplica ni en directo ni
  en inverso — nunca lo reemplaza silenciosamente. Este *rebase* es un
  **rebase de compatibilidad experimental**: revisado contra la fuente
  pineada, con las pruebas de aplicación y las aserciones estructurales en
  verde (ver
  [`../tests/test_engramhalo_qwen38_patch_rebase.py`](../tests/test_engramhalo_qwen38_patch_rebase.py)),
  pero **todavía no compilado ni validado en tiempo de ejecución**. No está
  pensado para despliegue de modelo: el siguiente paso requerido antes de
  confiar en el comportamiento que el parche original pretendía (mantener
  el tensor PLE disperso de Qwen3.8 Flash Next respaldado por mmap en CPU
  mientras los pesos densos se suben a GPU) es compilarlo con un
  compilador ROCm/HIP real, no una revisión humana externa adicional que
  no ha ocurrido.

- Imágenes base pineadas por digest (leídas anónimamente vía la API del
  registry de Fedora el 2026-09-16T13:52Z, sin publicar ni persistir ningún
  token): `fedora:44` →
  `sha256:61beafd34111e1cb85fb49377ceadeee0a53622dbc20670ed8ca303f0e17ed9c`;
  `fedora-minimal:44` →
  `sha256:dd3488a176bb158bde9deeef3f687023fc83aaad91f523e3ce81e078bf5bb473`.
  Ver [`build-manifest.example.json`](./build-manifest.example.json) para
  el detalle completo y cómo se verificó cada dato.

### Limitación de reproducibilidad documentada

Pinear el commit de origen y el digest de la imagen base **no** hace este
build bit-a-bit reproducible: el repositorio `repo.amd.com/rocm/packages-multi-arch/rhel10/x86_64`
es un repositorio dnf/yum mutable. El `Dockerfile` valida la firma GPG con
la clave ya existente de `repo.amd.com` (`gpgcheck=1`), pero no fija una
NEVRA de paquete exacta; reconstruir en otra fecha puede resolver
versiones de paquete ROCm distintas aunque el commit de origen y el digest
de la imagen base sean idénticos. Esta limitación se documenta, no se
resuelve, en este cambio.

### Decisiones deliberadas que se apartan de la receta upstream pineada

El `Dockerfile.rocm-7.14` upstream (pineado arriba, léelo en
`docs/strix-halo/Dockerfile.rocm-7.14` del commit fijado) usa
`-DGGML_RPC=ON` y deja enlazado `libcurl` sin `-DLLAMA_CURL=OFF`. Este
`Dockerfile` se aparta deliberadamente en dos puntos, documentados también
como comentarios inline:

- `-DGGML_RPC=OFF`: el wrapper `llama-server` de este directorio nunca
  reenvía `--rpc` y lo deniega explícitamente como flag peligroso; el
  servidor RPC del motor es superficie sin uso aquí.
- `-DLLAMA_CURL=OFF`: el wrapper ya deniega `-hf`/`--hf-repo`/
  `--model-url`/etc., pero quitar el soporte de descarga HTTP del propio
  binario del motor elimina esa ruta de código en el origen, no solo en el
  filtro de argv del wrapper.

Nada más se cambia respecto al pin upstream sin comentario explícito en el
`Dockerfile`.

### Qué NO hace esta receta

- No construye, no hace pull, no ejecuta ningún build de Docker/Podman por
  sí sola.
- No descarga, monta ni referencia ningún peso de modelo (`.gguf`,
  `.safetensors`, etc.); ver [`.dockerignore`](./.dockerignore) para las
  exclusiones defensivas del contexto de build.
- No fija una imagen por tag mutable en ningún ejemplo: el uso final
  (fuera de este cambio) requiere el digest `sha256` real obtenido
  **después** de construir, nunca un nombre de imagen sin pin.
- No toca `.opencode/agent/*.md`, el roster, ni ninguna configuración de
  host real.

### Instrucción mínima de build (fase futura, fuera de este cambio)

Solo para referencia — **no se ejecuta aquí**. Requiere Docker/Podman real,
GPU/ROCm real solo para *usar* la imagen resultante (no para construirla,
que corre en CPU), y aprobación humana explícita para invocar el build:

```sh
# Desde scripts/engramhalo/, con Docker o Podman real disponible:
docker build \
  --build-arg ENGRAM_COMMIT=15176583b358d791b7a73f210ef4ab9e167cfba7 \
  --build-arg PATCH_COMMIT=15176583b358d791b7a73f210ef4ab9e167cfba7 \
  --build-arg BUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t engramhalo:local-build \
  -f Dockerfile .
docker inspect --format '{{index .RepoDigests 0}}' engramhalo:local-build
# Luego: retag/usa SOLO por el sha256 real resultante, nunca por
# 'engramhalo:local-build'. Prueba primero con --help/--version, sin GPU
# ni modelo, como en scripts/engramhalo/README.md más abajo.
```

## Despliegue manual (fuera de este cambio)

Este cambio **no despliega nada**. Un despliegue real requeriría, como
mínimo y con aprobación humana explícita en cada paso:

1. Construir/instalar la imagen EngramHalo pineada a un commit fijo (no
   `latest`), obtener su digest `sha256` real, y verificarlo por separado.
2. Crear `runtime_state_dir` real con modo `0700` y propietario correcto.
3. Escribir un `ENGRAMHALO_CONFIG` real (nunca en el repositorio) con
   rutas y digests reales, y validar manualmente su contenido.
4. Enlazar/copiar `llama-server` al `rocm_bin` que Lemonade use, siguiendo
   un checklist operativo de preflight aprobado por el operador (fuera de
   este árbol de código público) y sin saltarse ningún gate de aprobación
   ahí descrito.
5. Probar primero con `--help`/`--version`, luego con una carga mínima
   `N=1` en una ventana coordinada, verificando memoria antes/después.

No hay copia de seguridad "por defecto" de la configuración del host en
este repositorio; cualquier backup es responsabilidad del operador fuera
de este árbol de código.

## Tests

Ver [`../tests/test_engramhalo_wrapper.py`](../tests/test_engramhalo_wrapper.py).
Todos los tests son offline: usan un motor (`engine`) **falso** —un script
Python de prueba que registra invocaciones sin crear contenedores reales—
y no requieren red, Docker real ni GPU. Ejecutar:

```sh
python3 -m unittest scripts/tests/test_engramhalo_wrapper.py -v
```
