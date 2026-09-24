# Inferencia: Cockpit + llama-swap + runtimes Docker

[English](README.en.md) |
[Investigación y arquitectura](../../docs/investigacion-docker-toolboxes-halogen.md) |
[Proyecto](../../README.md) |
[Laya CPU concurrente con Halogen](LAYA.md) |
[Pruebas de Laya](../../docs/pruebas-laya.md)

**Estado fechado 2026-09-17:** [despliegue y pruebas en el Halo](../../docs/despliegue-halogen-128k.md)
completados para Halogen W4B Quality 128K, servido por llama-swap como servicio
de usuario. Lemonade quedó deshabilitado; Coder Vulkan se probó y se retiró
del catálogo activo sin borrar pesos. Cold boot, soak y paralelismo siguen
pendientes. La implementación del 16 de septiembre solo tenía pruebas offline.

Este README describe los **defaults públicos autenticados y loopback**.
El despliegue privado usa una excepción LAN HTTP sin clave autorizada por el
operador y una unidad/launcher privados; no se transfieren al clonar el repo.
Consultar el informe antes de ejecutar comandos sobre el servicio existente.

## Qué incluye

- [manage.py](manage.py): instalación aislada, inicialización, generación y
  validación de configuración, gateway, Cockpit, estado y descarga de residentes.
- [runtime.py](runtime.py): cuatro tipos de motor, Docker sin shell de usuario,
  digest obligatorio, pesos RO, puertos loopback y parada limitada a contenedores
  propios. Un lock cooperativo excluye Cockpit y los runtimes gestionados.
- [Perfiles de ejemplo](profiles.example.json): Coder Vulkan/ROCm, Halogen y
  vLLM. Todos deshabilitados hasta seleccionar artefactos reales.
- [Frontal TLS Compose](compose.yaml), plantilla `.env.example` y `Caddyfile`:
  API remota con rutas permitidas; interfaz administrativa solo en loopback.
- [Proveedor OpenCode](opencode.example.json): conexión por variables, sin
  modificar configuraciones locales existentes ni almacenar claves públicas.

Llama-swap se ejecuta en el host; cada runtime en un contenedor independiente.
El frontal Caddy usa red host para alcanzar el controlador loopback; no tiene
GPU ni socket Docker. La excepción `NET_BIND_SERVICE` se necesita para ejecutar
el binario de la imagen Caddy probada, que lleva esa file capability, incluso
usando un puerto alto. Se descartó `cap_drop=ALL` sin esta excepción después de
un `operation not permitted` reproducido. No se añade `privileged`.

## Instalación aislada

Desde la raíz del repositorio, en el host donde se quiera operar:

```bash
python3 workspaces/inference/manage.py install
python3 workspaces/inference/manage.py init
```

Requisitos: Linux x86_64, Python con venv/pip, Git, GitHub CLI con acceso al
repositorio/release y Docker con permisos del operador. No se usa sudo, no se
cambia la configuración de shell ni se instala un servicio de arranque.

La instalación descarga llama-swap **v255**, verifica SHA256 del tarball
`84aa0df0cf3e302a8591e39de347f64c0c7dce1c3a948df68723a82e1fb4f1d4`
y extrae únicamente el binario. Instala Cockpit desde commit
`6959d068c020f3f33bfb8ef743e7ba44a6390dda` en un venv independiente.
Las dependencias transitivas se resuelven al instalar y se registran en
`data/cockpit-packages.txt`: no se afirma reproducibilidad byte a byte.
Upstream pide el extra `huggingface_hub[cli]`, que su release actual ya no
ofrece; pip avisa, pero el import de Cockpit se verificó correctamente.

`init` crea sin sobrescribir:

- `data/profiles.json`, modo 0600, inicialmente sin modelos habilitados.
- `data/admin.key` y `data/client.key`, distintas, modo 0600, nunca impresas.
- Directorio `data/` modo 0700 e ignorado por Git y por el generador del sitio.

La configuración pública no se rellena leyendo secretos, `.env` reales ni
estado de agentes. No copiar `data/` al repositorio público o al sitio estático.

## Preparar un primer perfil en el Halo

1. Comprobar hardware real, GTT, RAM, kernel, espacio, permisos render/KFD y
   actividad de inferencia/entrenamiento. Conservar snapshot privado de
   Lemonade y confirmar cómo restaurar su estado actual, no el histórico.
2. Preparar la imagen y pesos en una ventana autorizada. Cockpit sirve para
   seleccionar modelos y obtener recetas, pero puede descargar imágenes/pesos.
   No trasladar `latest` al perfil permanente: resolver y registrar digest.
3. Editar **solo** `data/profiles.json`: ruta absoluta del directorio, archivo
   relativo exacto, digest y upstream ID. Activar inicialmente `coder-vulkan`.
   Los nombres/rutas de la plantilla no prueban la ubicación de tus modelos.
4. Mantener 32768 de contexto, 8192 de salida y un slot como punto de partida.
   Coder tiene `--jinja`, offload GPU, Flash Attention y `--no-mmap`; comprobar
   esos flags y el offload real en el build elegido. No es receta EngramHalo.
   Si el binario usa `--load-mode none` en lugar de `--no-mmap`, añadir
   `"load_mode": "none"` al perfil privado. Sin ese campo se conserva el
   contrato anterior; comprobar `--help` y el parser sin cargar pesos.
5. Detener/drenar Lemonade explícitamente antes de la primera carga. El launcher
   rehúsa arrancar si detecta `lemond`, `llama-server`, `flash_serve` o `vllm`.
   No detiene procesos ajenos ni cambia servicios automáticamente.

Para Halogen hacen falta checkpoint compatible, tokenizer, overlays/sidecars
según formato y memoria suficiente. HGN y GGUF IQ4_XS requieren preparaciones
diferentes; no usar Q4_K_M/UD-Q4_K_XL como sustitutos. Los campos opcionales
`halogen_overlay` y `halogen_tokenizer` fijan el overlay y el directorio del
tokenizer, relativos a `model_dir`; se comprueba también `tokenizer.json`.
`halogen_max_tok` controla la arena de prefill (16384 por defecto, hasta 32768),
no el presupuesto de respuesta. Para migrar una receta probada en Cockpit,
conservar explícitamente sus artefactos y su arena, y validar de nuevo.
No se descargan pesos al arrancar. Se conserva el entrypoint `all`.
Para Halogen, `slots` admite enteros de 1 a 8 (default 1) y `kv_pool` un pool
entre `context` y 1048576 (default igual a `context`). El generador deriva la
concurrencia por modelo de `slots` y la global del máximo de los perfiles,
conservando exclusión entre motores. El pool incluye entrada y salida de todas
las conversaciones; anunciar 128K no reserva 128K extra por slot.
El perfil C usa `context: 131072`, `kv_pool: 524288`, `slots: 4`,
`halogen_max_tok: 16384` y `output: 8192`. Requiere validación de memoria y
carga local; no se cambian BIOS, IOMMU ni kernel.

vLLM requiere un modelo HF exportado con todos sus archivos, no symlinks que
salgan del montaje, más caché RW separada. `vllm_args` permite parsers y flags
propios de una receta revisada, pero no cambiar red/identidad ni activar
`trust-remote-code`. Sigue pendiente la validación GPU/modelo específica.
Los dos motores especializados conservan el usuario de la imagen; no se
promete ejecución no-root de imágenes que no se han inspeccionado/probado.

## API y web administrativa

```bash
python3 workspaces/inference/manage.py generate
bash workspaces/inference/start.sh
```

`generate` valida los perfiles habilitados y ejecuta `llama-swap -validate`.
El fichero generado `data/llama-swap.yaml` usa JSON, subconjunto válido de YAML,
y solo referencias a claves del entorno. La API y web escuchan en
**127.0.0.1:18080**, sin ocupar el puerto 13305 de Lemonade.

El catálogo `/v1/models` publica el contexto efectivo del perfil como
`context_length`, `context_window` y `meta.n_ctx`; publica la salida configurada
como `meta.llamaswap.max_output_tokens`. El generador deriva estos campos de
`context` y `output`, no del máximo teórico de los pesos. Son metadatos de
descubrimiento: no recortan peticiones ni prueban que un cliente concreto los
consuma para compactar su historial.

La web está en `/ui/`, protegida por clave; también se admite HTTP Basic según
upstream. Acceso administrativo remoto mediante un túnel/VPN aprobado con
terminación local; **no publicar directamente el puerto 18080**.

```bash
python3 workspaces/inference/manage.py status
python3 workspaces/inference/manage.py unload
```

`unload` pide al gateway descargar sus residentes; no borra imágenes/pesos.
Ctrl+C detiene el gateway foreground. Si queda un contenedor propio tras un
fallo, inspeccionar estado y ejecutar la parada específica:

```text
python3 workspaces/inference/runtime.py stop <PERFIL> --config <CONFIG_PRIVADA>
```

La parada funciona aunque se haya retirado el archivo de configuración o los
pesos. Verifica etiqueta de propietario y usa el ID del contenedor. Nunca
invoca `prune`, parada global ni limpieza de modelos. No se instalan unidades
systemd hasta validar el ciclo completo en el Halo; un supervisor futuro debe
arrancar `start.sh`, conservar el directorio privado y respetar 90 s de parada.

## Cockpit sin competir con llama-swap

```bash
python3 workspaces/inference/manage.py unload
python3 workspaces/inference/manage.py cockpit
```

El launcher elige Docker y un `XDG_CONFIG_HOME` privado de este workspace.
El adaptador [cockpit_launch.py](cockpit_launch.py) traduce los grupos `video`
y `render` de Halogen a los GID de los dispositivos del host para Docker,
sin modificar la instalación upstream. Reiniciar Cockpit mediante `manage.py`
para aplicar la adaptación; la imagen puede no definir esos grupos por nombre.
En el primer ensayo, configurar tanto Context como KV Pool a 32768 y Slots a 1:
reducir Context o Slots no reduce el pool guardado anteriormente.
Mantiene el lock de GPU mientras la TUI está abierta, y rechaza entrar si hay
un contenedor gestionado activo. Cierra sus servidores y sal de Cockpit antes
de volver al gateway. No ejecuta la TUI automáticamente durante instalación.

Es un **lock cooperativo**, no un aislamiento de GPU: Cockpit lanzado por fuera,
Docker manual, entrenamiento o un servicio de otro usuario pueden saltárselo.
La detección por nombre de proceso tampoco cubre todos los entrenamientos.
No dejar esos trabajos corriendo; reservar el Halo antes de activar perfiles.
Una petición durante Cockpit puede fallar al arrancar; no implementa una cola
de mantenimiento que espere al cierre de la TUI. Las imágenes que Cockpit
actualice no cambian los digests fijados del servicio.

## ComfyUI manual para Strix Halo

`comfyui.py` prepara la imagen de
[kyuz0](https://github.com/kyuz0/amd-strix-halo-comfyui-toolboxes) y ofrece
arranque foreground, parada y estado sin añadir perfiles a llama-swap, unidades
systemd ni reinicio automático. No detiene Halogen por su cuenta.

```bash
python3 workspaces/inference/comfyui.py prepare
python3 workspaces/inference/comfyui.py start
```

`prepare` descarga `latest` la primera vez, guarda el digest privado y conserva
ese digest en ejecuciones posteriores. Copia los workflows incluidos sin
sobrescribir los existentes. No descarga pesos: los checkpoints, encoders,
VAE y LoRAs del workflow elegido deben prepararse por separado en
`workspaces/inference/data/comfyui/models/`. No ejecutar los descargadores con
el HOME real ni montar el directorio personal completo.

Antes de `start`, reservar una ventana sin peticiones, drenar y parar el servicio
LLM existente. En el despliegue documentado, los comandos manuales son:

```bash
systemctl --user stop llama-swap.service
python3 workspaces/inference/comfyui.py start
```

El arranque rechaza una GPU reservada o un contenedor gestionado activo;
no fuerza la descarga ni modifica el servicio. La interfaz escucha solamente
en `http://127.0.0.1:8188`, sin autenticación propia: usarla localmente o mediante
un túnel aprobado, no publicar el puerto directamente. Como excepción explícita
para una LAN de confianza, `start --bind <IP_LAN_PRIVADA>` publica el puerto
8188 solamente en esa IPv4 local. No añade autenticación ni TLS; cualquier
cliente que alcance ese puerto puede usar ComfyUI. No redirigirlo en el router.
El default sigue siendo loopback; se rechazan direcciones públicas y `0.0.0.0`.
Cambiar el bind requiere parar y arrancar, después de vaciar la cola de trabajos.
La opción debe repetirse en cada arranque; no cambia configuración persistente.
Detener con Ctrl+C o, desde otra terminal:

```bash
python3 workspaces/inference/comfyui.py status
python3 workspaces/inference/comfyui.py stop
systemctl --user start llama-swap.service
```

Restaurar el servicio LLM solo si estaba activo antes. La parada afecta únicamente
al contenedor propio y conserva modelos, entradas, salidas, workflows y cachés
en `data/comfyui/`, ignorado por Git. No hay conexión automática a llama-swap.

La receta usa ROCm/TheRock, dispositivos render/KFD con sus GID reales,
`--disable-mmap`, `--reserve-vram 4`, `--disable-smart-memory`, `--cache-none` y
`--bf16-vae`, con offload a CPU permitido. Se retiró `--gpu-only` después de un
OOM real al aplicar la LoRA BF16: los pesos originales y sus copias parcheadas
agotaron los 61,73 GiB disponibles para ROCm. La reserva de 4 GiB es margen
para el gestor de ComfyUI, no una partición de GPU garantizada para otro servicio.
Ejecuta con UID/GID del operador, pesos RO y volúmenes limitados,
sin socket Docker, HOME completo, `privileged` ni IPC del host. Conserva la
excepción upstream `seccomp=unconfined`; comparte kernel/driver y no es una
barrera frente a fallos de GPU. Las variables offline evitan descargas normales
de Hugging Face, pero no constituyen un bloqueo de red.

El lock cooperativo de `data/gpu.lock` impide que los launchers gestionados se
solapen mientras ComfyUI está abierto. Las peticiones LLM pueden fallar durante
esa reserva; no hay cola de mantenimiento. Procesos externos pueden ignorarlo.
Los workflows upstream se copian sin alterar: comprobar nombres de pesos y
LoRA, especialmente la receta Qwen Image 2512 de cuatro pasos que referenciaba
una LoRA de Edit 2511.

**Verificación inicial 2026-09-22:** imagen descargada y fijada localmente; ComfyUI
0.31.0, PyTorch 2.14.0a0 con ROCm 7.15.0 y 30 workflows incluidos. La interfaz
respondió HTTP 200 en una prueba temporal CPU sin dispositivos GPU y se detuvo.
El launcher rechazó correctamente el arranque con Halogen residente, sin
interrumpirlo. En esa primera prueba no se descargaron pesos ni se validó
generación GPU; las pruebas posteriores se describen abajo. Ejecutar
los tests `test_inference*.py` antes de modificar este control manual.

### Descarga de Qwen Image y opciones de ejecución

Después de preparar la imagen, desde la raíz del repositorio:

```bash
python3 workspaces/inference/download_comfyui_models.py
```

Usa los helpers de la imagen fijada para Qwen Image 2512 BF16, encoder, VAE y
LoRA Lightning de cuatro pasos. Son unos 51,35 GB adicionales a la imagen.
Ejecuta en primer plano, sin GPU ni cambios de servicios, con HOME aislado,
montajes limitados de caché/modelos y lock de descarga. Ctrl+C interrumpe;
repetir delega reanudación/omisión de archivos existentes al helper upstream.
No equivale a verificación criptográfica ni valida generación por sí mismo.
Preparar una ventana adecuada de red/disco y no cambiar pesos en uso.

`service_options.py` centraliza opciones estrictas de ComfyUI y LlamaBoard en
archivos privados de `inference/data/`. Los launchers leen esos archivos al
arrancar y mantienen un lock de ajustes durante su ejecución, heredado por el
cliente Docker. El [editor de Halo Control](../halo-control/README.md) comprueba
servicio detenido, revisión y bloqueos antes de guardar; no reinicia al guardar.
ComfyUI conserva por defecto reserva de 4 GiB y offload a CPU, no `--gpu-only`.
Cerrar la pestaña web Cockpit no libera la GPU: hay que detener el motor.

### Inventario, persistencia y recuperación

La imagen descargada ocupa **21825254570 bytes (21,8 GB decimales)** según
Docker; no es el tamaño de transferencia ni incluye pesos. Se inspeccionó
PyTorch `2.14.0a0+rocm7.15.0a20260721`. El digest real se conserva únicamente en
`data/comfyui/image.ref`, modo 0600; no se publica ni se cambia al ejecutar
`prepare` otra vez. El tag `latest` es mutable y no garantiza esas versiones
para instalaciones futuras. No hay actualización automática ni comando de
actualización: conservar el pin y los datos antes de evaluar otra imagen.

| Ruta relativa a `data/comfyui/` | Uso |
| --- | --- |
| `models/` | Pesos; montaje de solo lectura durante el servidor |
| `input/` | Imágenes de entrada y subidas desde la interfaz |
| `output/` | Imágenes y otros resultados guardados por los workflows |
| `user/` | Workflows, preferencias y base de datos de ComfyUI |
| `cache/` | HOME aislado y cachés de bibliotecas |
| `image.ref` | Referencia inmutable de la imagen instalada |

Los directorios superiores se crean con propietario actual y modo 0700.
`prepare` ejecuta un contenedor breve sin red ni GPU para copiar workflows;
`start` mantiene el terminal ocupado y sus logs visibles. Cerrar la ventana no
es el procedimiento de parada: utilizar Ctrl+C o `stop`, y comprobar `status`.
No hay modo daemon ni arranque al reiniciar la máquina. `stop` no requiere pesos
ni el fichero de pin, verifica la etiqueta de propietario y actúa sobre el ID
del contenedor; si no existe, no hace nada. No borra la imagen ni los datos.

| Situación | Acción segura |
| --- | --- |
| GPU reservada | Detener el motor propietario o drenar/parar el LLM; cerrar el navegador Cockpit no lo detiene. No borrar `gpu.lock` |
| Contenedor propio residual | Usar `stop`, comprobar `status` y reintentar |
| Nombre ocupado por otro propietario | Inspeccionarlo; el launcher se niega a detenerlo |
| Falta la imagen fijada | Recuperar exactamente la referencia de `image.ref` con Docker; no sustituir el pin a ciegas |
| Error de permisos | Usar el operador original; no ejecutar con sudo ni aplicar chmod 777 |
| Puerto 8188 ocupado | Liberar el servicio conflictivo de forma controlada; el launcher no lo para |
| Modelo no encontrado | Preparar todas las dependencias del workflow, respetando subdirectorios y nombres |
| OOM o fallo ROCm | Parar ComfyUI, inspeccionar logs y recursos antes de restaurar el LLM; no cambiar BIOS/kernel automáticamente |

La prueba HTTP se hizo temporalmente en el puerto loopback 18188 con `--cpu`
y sin `--gpu-only` ni dispositivos GPU; no modifica el modo normal del launcher.
La prueba inicial no ensayó descarga de pesos, generación, rendimiento,
cancelación GPU ni cambios Halogen-ComfyUI-Halogen reales. Posteriormente se
descargaron los cuatro pesos (51,35 GB), se corrigió la LoRA del workflow local,
se detuvo Halogen y arrancó ComfyUI con ROCm en la LAN autorizada. La primera
generación con `--gpu-only` agotó memoria al aplicar la LoRA y terminó en
segmentation fault (salida 139); el fallo no fue de conectividad LAN. No se
cambiaron BIOS, kernel ni GTT. Con offload a CPU y margen de 4 GiB, una petición
real de 1024x1024, cuatro pasos y batch uno terminó correctamente (unos 45 s de
ejecución servidor y 50 s de sondeo cliente), guardando un PNG verificado.
Después se restauró Halogen y se verificó una respuesta HTTP 200. Este smoke
único no prueba estabilidad repetida, resoluciones mayores ni cancelación GPU.
Los tests sintéticos no prueban GPU.
En la verificación inicial, las 38 pruebas de inferencia y las 14 del
sitio pasaron; el sitio completo sigue bloqueado por el enlace preexistente a
`scripts/engramhalo/.dockerignore`, fuera de su allowlist de publicación.

AI Toolbox Cockpit (la TUI de kyuz0) ya estaba instalado, pero su gestor de
modelos ComfyUI usa Toolbx/Distrobox; este procedimiento Docker manual no
necesita ninguno. No confundir esa herramienta con Cockpit Linux web, sobre
el que se desplegó posteriormente Halo Control. ComfyUI conserva su API de workflows, no implementa por esta
instalación `/v1/images/generations`. La alternativa investigada es
[stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp/tree/master/examples/server)
con Vulkan y llama-swap; no se ha desplegado. Tampoco se han cambiado los
permisos de rutas del frontal TLS para publicar imágenes o ComfyUI.

## OpenCode desde otra máquina

El proxy Caddy separa inferencia de administración, porque llama-swap por sí
solo trata todas las claves como equivalentes. La clave de cliente en acceso
directo a loopback también podría administrar: la separación depende de que
**solo el frontal TLS sea accesible al cliente remoto**.

Preparar de forma privada una configuración basada en `.env.example` y un
certificado `server.crt` con su `server.key` en `TLS_DIRECTORY`, legibles por
el UID del contenedor. El nombre debe coincidir con `HALO_API_NAME`; la CA debe
ser confiable en la máquina OpenCode. No desactivar verificación TLS.

Valores necesarios: UID/GID del operador, IP LAN/VPN autorizada, DNS, directorio
TLS y contenido de `data/client.key`. Mantener el archivo privado modo 0600.
Usar exactamente esa clave en el frontal y en OpenCode, no `admin.key`.

```text
docker compose --env-file <ENV_PRIVADO> -f workspaces/inference/compose.yaml config --quiet
docker compose --env-file <ENV_PRIVADO> -f workspaces/inference/compose.yaml up -d
docker compose --env-file <ENV_PRIVADO> -f workspaces/inference/compose.yaml down
```

El frontal escucha en la dirección elegida, puerto **18443**, con certificado
aportado; no hace ACME ni publica un panel administrativo. Solo permite la
clave de cliente y las rutas `/v1/models`, `/v1/chat/completions`,
`/v1/completions`, `/v1/responses`. Las demás rutas, incluidos `/ui`, `/api`,
`/logs`, `/metrics` y `/upstream`, reciben 403. No activar para Internet sin
política de firewall/VPN y evaluación adicional. No hay cambio de firewall
incluido ni servicio TLS activo en la estación local.

Incorporar únicamente el proveedor de [opencode.example.json](opencode.example.json)
al archivo del cliente; **no sobrescribir su configuración entera**. Definir
`HALO_BASE_URL` como la URL HTTPS aprobada que termina en `/v1` y
`HALO_CLIENT_KEY` mediante el mecanismo privado del cliente. Retirar de su lista
los perfiles aún deshabilitados y ajustar contexto/salida a los valores reales.
Seleccionar `halo/coder-vulkan` en OpenCode. Esta plantilla usa Chat Completions;
Responses requiere `@ai-sdk/openai` y validación del cliente por separado.

## Pruebas y límites

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
git diff --check
```

Pruebas de validación, montajes, perfiles, lifecycle y exclusión de recursos
ajenos. Si el binario instalado está disponible, se verifica configuración
mediante el propio llama-swap y se arranca temporalmente un gateway loopback
con backend HTTP sintético: auth, UI, discovery sin inferencia, reescritura,
tools como payload y passthrough Chat/Responses con/sin SSE. **No prueba calidad,
ciclo de herramientas real de un LLM, cancelación GPU ni fit.**

Se validó Compose sin desplegar y `caddy adapt` con la imagen fijada y red
Docker desactivada. Falta probar certificado, handshake TLS, bloqueo de rutas
con tráfico real y desconexión a través del frontal en la red destino.

Bloqueo de la web del repositorio ya existente: un enlace del README EngramHalo
a `.dockerignore` queda fuera del allowlist. No se amplía ese allowlist ni se
oculta el fallo como parte de este workspace. Los enlaces nuevos a archivos
sin extensión se muestran como texto para no introducir más incompatibilidades.

## Estado de entrega y operación privada

La [consolidación del 23 de septiembre](../../docs/halo-control-operacion.md)
reúne ComfyUI GPU, el panel Cockpit Linux, las fichas/editor, Studio/LlamaBoard,
los controles `ON graceful`, métricas, mantenimiento y reparación de la web tras
un reinicio. No sustituye los perfiles privados ni el baseline del 17.

El [informe de despliegue del 17 de septiembre](../../docs/despliegue-halogen-128k.md)
registra instalación, GPU, herramientas, 128K, cambio de modelos, excepción de
red y servicio persistente. Los comandos `generate`, `start.sh` y `unload`
siguen usando sus defaults públicos: no sustituyen al launcher privado del
servicio LAN. No arrancar un segundo gateway. Para operar el despliegue real,
usar su unidad de usuario y las instrucciones del informe. TLS LAN, cold boot,
soak y compactación en el cliente remoto no se dan por validados.

Fuentes: [llama-swap](https://github.com/mostlygeek/llama-swap),
[Cockpit](https://github.com/kyuz0/ai-toolbox-cockpit/tree/main),
[OpenCode](https://github.com/anomalyco/opencode) y la investigación enlazada.
