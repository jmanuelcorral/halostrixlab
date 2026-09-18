# Inferencia: Cockpit + llama-swap + runtimes Docker

[English](README.en.md) |
[Investigación y arquitectura](../../docs/investigacion-docker-toolboxes-halogen.md) |
[Proyecto](../../README.md)

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
