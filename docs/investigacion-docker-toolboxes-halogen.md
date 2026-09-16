# Investigación: runtimes Docker, toolboxes, Lemonade y Halogen

[Índice del proyecto](../README.md) |
[English summary](en/docker-toolboxes-halogen.md) |
[Baseline histórico](configuracion-reutilizable-halo-strix.md)

**Fecha de consulta: 2026-09-16. Estado: investigación y propuesta, no despliegue.**
Se consultaron documentación y código públicos mediante la web del proyecto y
la API de GitHub. No se consultó el Halo, no se arrancaron contenedores ni
modelos, no se descargaron imágenes o pesos y no se leyeron `.env` reales ni
estado privado de agentes. Las pruebas documentales locales no validan GPU.

Las etiquetas usadas aquí son **UPSTREAM** (lo que publica el proyecto),
**CÓDIGO** (contrato contrastado en fuente), **PROPUESTA** (decisión para este
laboratorio) y **PENDIENTE** (requiere prueba local). Ni una versión publicada
ni un benchmark ajeno establecen la configuración actual del Halo.
Las fuentes y sus revisiones se enumeran en la sección 12.

## 1. Conclusión y respuesta a la idea inicial

**Sí: separar los runtimes en contenedores y exponer una API estable es viable.**
No hace falta convertir una consola interactiva en API ni implementar otro
servidor de inferencia: llama.cpp, vLLM y Halogen ya tienen servidores HTTP.
La parte que falta resolver es quién los arranca, para, selecciona y protege.

Para un único Halo de desarrollo elegiría:

1. **Imágenes OCI independientes** para llama.cpp Vulkan, llama.cpp ROCm/forks,
   vLLM y Halogen; pesos persistentes fuera de las imágenes.
2. **llama-swap como primera opción de entrada LLM y cambio de modelo**, con
   control de procesos/contenedores y exclusión de cargas grandes.
3. **Lemonade conservado como alternativa o servicio de transición**, no como
   requisito delante de todos los motores.
4. **Cockpit como herramienta de exploración manual**, sin gestionar a la vez
   los contenedores que controla el servicio permanente.
5. Entrenamiento y ComfyUI como trabajos/servicios con sus APIs propias, sujetos
   a la misma reserva exclusiva de GPU cuando corresponda.

**Lemonade delante no es imposible:** su backend experimental `cloud` acepta
una base URL OpenAI compatible y puede apuntar a un servidor local en Docker.
Pero no administra ese contenedor, exige credenciales incluso para discovery
y tiene una limitación comprobada en Responses no streaming. No lo elegiría
como único frontal universal para Halogen/Codex sin superar esos contratos.

Esta decisión prioriza cambiar de runtime sin reconfigurar todos los clientes,
conservar herramientas y streaming, y evitar que Halogen compita con Coder,
un entrenamiento o una generación de imágenes.

## 2. Separar cuatro responsabilidades

| Capa | Responsabilidad | No implica |
| --- | --- | --- |
| Imagen/toolbox | Bibliotecas, binarios y recetas compatibles con `gfx1151` | Un servidor arrancado ni pesos incluidos |
| Runtime de inferencia | Cargar pesos y responder HTTP: `llama-server`, `vllm serve`, Halogen | Gestión global de otros runtimes |
| Gateway de inferencia | Entrada estable, selección por `model`, autenticación y streaming | Que los modelos quepan simultáneamente |
| Control de ejecución | Arranque, parada, readiness, drenaje, exclusión y recuperación | Que un proceso vivo sea una GPU sana |

Docker aísla principalmente el userspace. El kernel, `amdgpu`, dispositivos,
RAM, GTT y ancho de banda siguen siendo compartidos. Cambiar ROCm dentro de un
contenedor no cambia el driver del host ni elimina sus requisitos.

**Toolbox no significa tool calling.** Toolbx/Distrobox son entornos de
contenedores. Las llamadas a herramientas del modelo son mensajes de la API;
el agente de desarrollo las ejecuta con sus propios permisos. El servidor de
inferencia no necesita montar el repositorio, las claves SSH ni el socket de
Docker del agente para generar una llamada a herramienta.

## 3. Qué ofrecen realmente las toolboxes

### 3.1. Catálogo contrastado

| Proyecto | Servicio/API publicado | Encaje en la propuesta |
| --- | --- | --- |
| llama.cpp toolboxes [S2] | `llama-server`; README muestra Server Mode y Router Mode | Primera migración del Coder GGUF, luego comparación Vulkan/ROCm |
| vLLM toolboxes [S3] | Servicio OpenAI compatible en puerto 8000; `start-vllm` ayuda a construir la receta | Ensayos de batching/modelos HF con soporte específico |
| DS4/DwarfStar [S6] | `ds4-server`: chat, completions, models y Messages compatible con Anthropic | Backend especializado adicional, no motor genérico para cualquier GGUF |
| ComfyUI toolboxes [S4] | Servidor ComfyUI y workflows en formato API bajo `workflows/API` | API de workflows separada; no asumir Chat Completions |
| Fine-tuning toolbox [S5] | Notebooks y Jupyter Lab | Trabajo de entrenamiento; no es un servidor OpenAI de inferencia |
| AI Toolbox Cockpit [S7] | TUI que construye y ejecuta servidores en Docker/Podman | Plano de control interactivo, no gateway HTTP permanente |

La premisa «las toolboxes no exponen API» es, por tanto, incorrecta para los
runtimes de inferencia. Lo que puede ocurrir es que **la imagen por defecto
abra una shell**. El Dockerfile Vulkan revisado termina en `CMD ["/bin/bash"]`:
para un servicio se sustituye por `llama-server`, no se automatiza una sesión
`toolbox enter` ni se deja una TUI esperando entrada.

Para ComfyUI, el proxy puede conservar su API y WebSocket o emplear una
integración específica. Publicar un workflow no equivale a convertirlo en
`/v1/images/generations`; esa traducción necesitaría un contrato propio.
Para entrenamiento, una eventual API sería de trabajos: crear, consultar,
cancelar y recoger artefactos, con una lista cerrada de recetas, no ejecución
de shell arbitraria. No se propone implementarla antes de validar entrenamiento.

### 3.2. Imágenes y diferencias importantes

**UPSTREAM, no recomendaciones ya validadas en este Halo:**

- llama.cpp publica `docker.io/kyuz0/amd-strix-halo-toolboxes:vulkan-radv`
  y `:rocm-10.0`; las etiquetas se reconstruyen al cambiar upstream.
- También enumera `:rocm-10.0-qwen-3.8-flash-next`,
  `:rocm-10.0-engramhalo`, `:vulkan-radv-performance`, ROCmFPX y TheRock.
  Varios canales son experimentales y de build manual. Una etiqueta listada
  no demuestra que exista ya el artefacto exacto deseado en el registro.
- El port EngramHalo a ROCm 10.0 sigue descrito como experimental; la validación
  del fork citado era ROCm 7.14. No intercambiar esas evidencias.
- vLLM distingue `docker.io/kyuz0/vllm-therock-gfx1151:latest` y `:dev`.
  Su README advierte que los benchmarks antiguos no son resultados de la
  imagen Ubuntu actual. Sus recetas incorporan parsers, restricciones AITER,
  dtype y flags por modelo: un `vllm serve` genérico no conserva todo eso.
- No todos los GGUF ni todas las cuantizaciones son intercambiables entre
  llama.cpp, vLLM, DS4 y Halogen. Registrar artefacto, tokenizer, plantilla,
  cuantización y sidecars por perfil de ejecución.

**PROPUESTA:** seleccionar una imagen, resolver su digest, conservarlo con la
revisión fuente y validar ese conjunto. No hacer actualizaciones automáticas
ni usar `latest`/`edge` como pin de producción. No inferir soporte de Qwen3.8 en
vLLM a partir de una tabla de otros modelos Qwen.

### 3.3. Cockpit ya incluye Halogen

El README y `backends/halogen/runner.py` de Cockpit confirman que:

- Puede lanzar servidores con `docker run` o `podman run`, sin Toolbx.
- Reconoce Halogen como imagen de servidor, no toolbox interactiva.
- Selecciona bundles HGN, tokenizer, overlay y visión opcional; verifica
  presencia/tamaños, lo cual **no es verificación de checksum**.
- Genera bind local por defecto, montaje de modelos de solo lectura y flags
  separados para contexto, pool KV y slots.
- Su integración sigue marcada como experimental hasta validación remota.
- En la revisión consultada sigue `:latest` con `--pull=always`, requiere
  acceso al registro al arrancar y mantiene defaults de integración ligados
  a una versión anterior. No equivale a un servicio fijado y offline.
- Ejecuta el servidor en primer plano desde la TUI; Ctrl+C lo detiene.

No hace falta desarrollar un Cockpit nuevo. Sí hace falta elegir un único
propietario del ciclo de vida: **Cockpit para ensayos manuales o llama-swap/
servicio para operación**, no ambos controlando el mismo perfil.

## 4. Lemonade delante de Docker: tres diseños distintos

### 4.1. Meter todo Lemonade en un contenedor

**UPSTREAM:** hay imagen oficial
`ghcr.io/lemonade-sdk/lemonade-server`, etiquetas de versión y guía Docker [S9].
La guía describe usuario no privilegiado UID 10001, volúmenes persistentes,
GPU passthrough y publicación del puerto 13305.

Esto migra Lemonade y sus backends gestionados a un contenedor. Es una ruta
razonable si se quiere conservar casi toda la experiencia actual, pero **no
crea automáticamente un orquestador de toolboxes hermanas**. Tampoco permite
tratar Halogen como si fuese otro binario `llama-server`.

La documentación actual distingue cachés y configuración bajo
`/opt/lemonade/.cache/` y `/opt/lemonade/.config/`. La referencia histórica de
este laboratorio usa otras rutas. No montar encima del estado original ni
copiarlo a ciegas: primero comprobar migración de esquema, propietario,
catálogo, opciones por modelo y rutas absolutas en una copia independiente.

### 4.2. Lemonade como proxy HTTP de servidores Docker

**CÓDIGO:** se revisó `CloudServer` tanto en `v11.9.0` como en `main` [S8].
No es solo una función anunciada en la rama de desarrollo. La versión instalada
en el Halo sigue sin comprobarse.

El mecanismo es registrar un proveedor con su base URL y descubrir
`GET <base_url>/models`. Los modelos aparecen con namespace
`<provider>.<upstream-id>`. Aunque se llame `cloud`, el contrato de URL permite
un endpoint local HTTP con autorización explícita para HTTP sin TLS.

Esquema documental, no comando aplicado:

```text
lemonade cloud install <PROVEEDOR_LOCAL> --base-url <BACKEND_BASE_URL>
```

La URL debe resolver desde donde ejecuta `lemond`. En una red Docker sería el
nombre DNS del servicio; `localhost` dentro del frontal apunta al propio
frontal, no al host ni al contenedor del motor.

**Límites comprobados que condicionan la elección:**

1. **Clave obligatoria.** Sin una clave resoluble, discovery se omite y las
   peticiones se rechazan. Se resuelve desde
   `LEMONADE_<PROVIDER>_API_KEY` o autenticación de sesión. No confundirla con
   `LEMONADE_API_KEY`, que protege la entrada de Lemonade.
2. **HTTP requiere opt-in.** `allow_insecure_http=true` o
   `--allow-insecure-http` permiten enviar la clave por HTTP. Preferir TLS o
   una red local controlada con una credencial específica del backend. No
   reutilizar claves externas. Para Halogen no se encontró un mecanismo
   documentado de validación de claves en su API: habría que protegerlo con
   un proxy autenticado o validar otra solución, no fingir seguridad con un
   token de relleno.
3. **No controla residencia externa.** `load()` registra el ID y marca estado;
   `unload()` cambia `loaded_` a false. No invoca Docker ni descarga los pesos
   del backend remoto. Un `ready` de este objeto no prueba readiness del motor.
   El límite local `max_loaded_models=2` no presupuesta estos contenedores.
4. **Responses no streaming no está soportado en CloudServer.**
   `CloudServer::responses()` devuelve `UnsupportedOperationException` en
   ambas revisiones. **No significa que todo Responses esté bloqueado:**
   `Router::responses_stream()` en `main` usa el camino genérico
   `forward_streaming_request("/v1/responses", ...)`. Esa asimetría exige
   probar ambos modos y sus errores; no vender compatibilidad completa.
5. **El relay no es totalmente opaco.** Reescribe `model`, añade alias de
   presupuesto legacy y puede inyectar `stream_options.include_usage` y
   consumir el frame de usage inyectado. Conserva ciertos headers de sesión.
   Hay que comprobar tokens, herramientas, reasoning, SSE y cancelación.
6. **Discovery no es un inventario durable de perfiles apagados.** Un
   proveedor inaccesible se omite de forma best-effort. Confirmar cómo
   refrescar el catálogo tras arrancar motores; no arrancarlos todos solo
   para que aparezcan en `/v1/models`.

**Veredicto:** posible frontal de Chat Completions para servicios externos
controlados por otra capa. No recomendado como único frontal universal para
esta migración, especialmente si Responses/Codex es un requisito.

### 4.3. Wrapper de ejecutable que invoca Docker

El repositorio ya contiene un
[wrapper EngramHalo experimental](../scripts/engramhalo/README.md), que adapta
el contrato `llama-server` a un `docker run` estrecho, con allowlists, montajes
restringidos y pin inmutable. Su documentación dice explícitamente que no se
ha construido ni ejecutado en una GPU/daemon real.

Es una vía para un fork compatible con los argumentos y endpoints de
llama.cpp. Debe conservar señales, puertos, readiness, errores, paths y
limpieza de hijos. El backend `system` de Lemonade también significa un
binario local en PATH, **no una URL arbitraria de servidor externo**.

**No extendería ese wrapper para hacerse pasar por Halogen.** Halogen tiene
su propio entrypoint, variables, formato de pesos y protocolo engine/API.
Traducir todas esas diferencias al contrato de un ejecutable gestionado por
Lemonade añade mantenimiento innecesario cuando ya existe una API HTTP.

## 5. Comparación de frontales y decisión

| Opción | Ventaja | Coste o límite | Decisión propuesta |
| --- | --- | --- | --- |
| Lemonade Docker con motores propios | Menor cambio funcional y UI conocida | No da control genérico de contenedores hermanos | Ruta conservadora alternativa |
| Lemonade `cloud` delante de APIs Docker | Catálogo único conservando Lemonade | Claves, discovery, Responses asimétrico y ningún stop externo | POC opcional de chat |
| llama-swap + runtimes Docker [S10] | Selección por modelo, `cmd`/`cmdStop`, readiness, TTL, exclusión, Chat y Responses | Tiene autoridad de ejecución; requiere endurecer acceso y validar lifecycle | Primera opción para un Halo |
| LiteLLM [S11] + control de contenedores separado | Gateway con claves virtuales, cuotas, routing y observabilidad multiusuario | Más componentes; el gateway por sí solo no libera memoria de Docker | Si crece a varios usuarios/proveedores |
| Proxy HTTP por rutas | Poco acoplamiento; conserva API nativa | No selecciona automáticamente por `model` ni gestiona memoria | Primera POC o escape diagnóstico |

llama-swap se eligió por **gestión de ciclo de vida**, no por su nombre ni por
necesitar llama.cpp. Su documentación admite Docker/Podman mediante `cmd` y
`cmdStop`, reescritura con `useModelName`, readiness mediante `checkEndpoint`,
TTL y grupos/matriz de coexistencia. El README enumera `/v1/responses` y
`/v1/messages`, además de chat. Esto acredita soporte publicado, no una prueba
local del par llama-swap/Halogen.

Límites de llama-swap que deben mantenerse visibles:

- `/health` del gateway solo contesta que el gateway vive; no acredita cada
  modelo. Mantener probes directos de los backends sin activarlos por accidente.
- El router serializa cambios, pero una petición que supera
  `globalConcurrencyLimit` se rechaza con 429, no queda esperando. No confundir
  la cola de cambio/arranque con los límites de admisión.
- Sus claves son equivalentes: no hay permisos por clave ni roles. Separar
  el acceso administrativo de clientes de inferencia mediante red/proxy.
- El passthrough `/upstream/<model>/...` puede activar un modelo. No usarlo
  alegremente para monitorización periódica porque puede producir swaps.
- No descarga GGUF por sí solo. Preparar imágenes/pesos antes de la petición.
- `sendLoadingState` inyecta información de carga en reasoning: dejarlo
  apagado inicialmente y probarlo por cliente, no contaminar mediciones.

## 6. Arquitectura recomendada

```text
Agentes/IDE en la máquina de desarrollo
                |
        entrada autenticada /v1
                |
     llama-swap (gateway + política de perfiles)
                |
       dueño único de arranque/parada
                |
     +----------+----------+-----------+------------+
     |                     |           |            |
llama.cpp Vulkan     llama.cpp ROCm    vLLM       Halogen
contenedor Coder     forks separados  contenedor  all o engine+api
     |                     |           |            |
     +---------- pesos persistentes y cachés --------+
                |
     GPU/RAM/GTT del mismo host: presupuesto común

ComfyUI y entrenamiento: APIs/trabajos separados,
con reserva que excluya los perfiles grandes de inferencia.
Lemonade: transición o alternativa, fuera de la cadena obligatoria.
```

### 6.1. Ubicación del controlador

**Primera implementación recomendada:** llama-swap como servicio pequeño en el
host; runtimes y modelos ejecutados en Docker. No es «todo en Docker», pero
mantiene los userspaces pesados fuera del host y evita montar el socket del
daemon en un servidor HTTP dentro de un contenedor.

El usuario del controlador necesita autoridad para Docker: con daemon rootful
eso es poder equivalente a root aunque el proceso sea un usuario sin UID 0.
Limitar sus archivos/configuración, clientes y superficie administrativa.
No presentar esta opción como una frontera de seguridad completa.

**Si todo debe estar en Docker:**

- Gateway HTTP sin dispositivos GPU ni socket Docker.
- Motores en una red privada compartida, sin publicación LAN individual.
- Cambios de perfil manuales mediante Compose inicialmente, o un controlador
  privado con operaciones permitidas y perfiles predefinidos posteriormente.
- No inventar que esa separación viene implementada por llama-swap: su
  `cmd` nativo ejecuta procesos donde corre el propio llama-swap. Una separación
  HTTP/controlador necesita integración adicional explícita.
- Montar `/var/run/docker.sock` en el frontal es el atajo habitual, pero no
  la recomendación. Montarlo `:ro` no convierte la API del daemon en read-only.

Docker rootless/Podman reducen parte de la autoridad del daemon, pero acceso a
`/dev/kfd`, GIDs, memlock e IPC deben validarse. No sustituir Docker por Podman
sin medir el contrato del host; el usuario ha pedido Docker.

### 6.2. Contrato por perfil

Cada perfil debe registrar, sin secretos:

| Campo de diseño | Contenido |
| --- | --- |
| Identidad pública | Alias estable, por ejemplo `coder-local` o `flash-halogen`; son nombres propuestos |
| Identidad upstream | ID exacto de `/v1/models`; no reutilizar automáticamente el ID de Lemonade |
| Imagen | Registro, tag de procedencia y digest resuelto; revisión de fuentes |
| Artefactos | Pesos/shards, hashes/revisión, tokenizer, plantilla, mmproj/MTP/overlay |
| Arranque | Comando no interactivo, dispositivos, GIDs y variables específicas |
| Readiness | Endpoint real, presupuesto de arranque y fallo terminal |
| Parada | Nombre/CID propio, drenaje, señal, timeout y verificación de liberación |
| Capacidad | RAM/GTT observada, contexto de entrada+salida, pool, slots y coexistencia permitida |
| API | Chat, Responses, tools, reasoning, visión, JSON y límites comprobados |
| Persistencia | Pesos RO; directorios RW separados para compilación/KV/salidas |

En llama-swap los mecanismos correspondientes incluyen `cmd`, `cmdStop`,
`proxy`, `checkEndpoint`, `useModelName`, `ttl`, `unloadTimeout`,
`concurrencyLimit` y `routing`. Son claves verificadas en su documentación,
no un esquema de Compose ni claves que deban copiarse a Lemonade.

Para un controlador en el host, publicar cada backend **solo en loopback**
y hacer coincidir puerto de Docker con el `proxy` del perfil. Dentro del
contenedor el servidor escucha en `0.0.0.0`; es el binding del host el que
restringe exposición. Si el controlador vive en Docker, usar DNS de servicios,
no esos mismos loopbacks. No se necesita `network_mode: host` por defecto.

### 6.3. Política de memoria y arranque

**PROPUESTA inicial:** un solo perfil grande activo. Un perfil Halogen,
DS4 grande, entrenamiento o ComfyUI pesado excluye a los otros. Mantener Coder
más Thinking simultáneos solo después de repetir medidas con las nuevas
imágenes y contexto; no asumir el consumo del binario histórico.

Secuencia de cambio exigida:

```text
solicitud de perfil
  -> cerrar admisión incompatible y drenar lo activo con plazo
  -> parar contenedores propios del perfil anterior
  -> confirmar salida, ausencia de huérfanos y recuperación de memoria
  -> arrancar candidato fijado, sin descargas automáticas
  -> esperar readiness del motor, no solo un puerto abierto
  -> abrir admisión y registrar identidad efectiva
  -> si falla: mantener cerrado, limpiar candidato y restaurar perfil previo
```

No activar una política `restart: always` independiente para un contenedor
que el controlador está intentando descargar. Coordinar reinicios, watchdog y
parada con un único propietario. Los perfiles Compose seleccionan servicios,
**no implementan exclusión mutua ni un planificador de memoria**.

TTL corto puede destruir la caché entre tool calls, y alternar Coder/Thinking
en cada turno puede pasar más tiempo cargando que respondiendo. Empezar con
cambio explícito de perfil para Halogen y medir cold start antes de automatizar
el cambio por cada petición. Una reserva administrativa debe cubrir también
entrenamientos y servidores arrancados fuera del gateway.

## 7. Halogen: viabilidad específica para este Halo

### 7.1. Qué es y qué API tiene

**UPSTREAM [S12]:** motor especializado en `gfx1151` y la familia
Qwen3.8-Flash-Next, distribuido como binario en
`ghcr.io/peonist-ai/halogen-flash-server:0.11.1` en el README consultado.
No es otro backend genérico de llama.cpp ni un motor para cualquier Qwen.

| Capacidad | Publicada por Halogen | Límite a comprobar |
| --- | --- | --- |
| Discovery | `/v1/models`, ID por defecto `halogen-qwen3.8-flash-next` | Gateway puede publicar otro alias y reescribirlo |
| Chat/Completions | `/v1/chat/completions`, `/v1/completions`, streaming y no streaming | Presupuesto incluye razonamiento |
| Responses | `/v1/responses`, pensado para Codex, ciclo `function_call`/`function_call_output` | Sin almacén de respuestas ni `previous_response_id` |
| Tools | Contrato de herramientas y reasoning anunciado en `/health` | Validar ciclo real del cliente; las herramientas no se ejecutan en el motor |
| Cancelación | Por desconexión, incluyendo no streaming desde 0.10.2 | Verificar propagación a través del proxy |
| Salud/métricas | `/health` con capacidades/estado; `/metrics` compatible con nombres llama.cpp | API viva no debe ocultar engine bloqueado |
| Visión | Opcional, sidecar y `HALOGEN_VISION_TOWER` | Acepta base64/data URL; rechaza URL HTTP(S); no genera imágenes |
| JSON estructurado | Subconjunto de JSON Schema desde 0.8.0 | No equivale a validador completo de schema |

Ejemplos de límites relevantes para agentes: `n > 1`, `top_logprobs` y
`logprobs` con streaming se rechazan según README. Structured output requiere
greedy, rechaza schema con imagen; `oneOf` se trata como `anyOf`, y restricciones
numéricas como `minimum`/`maximum` se aceptan pero no se aplican. Validar el
resultado en el cliente, aunque el servidor anuncie JSON Schema.

En Responses no hay recuperación/cancelación por ID ni estado de conversación
persistido como en un proveedor con response store. Enviar historial. Algunas
herramientas no funcionales, como `web_search`, se ignoran; no anunciar al
agente capacidades que el backend no ejecuta.

### 7.2. Dos topologías ya publicadas

**Un contenedor (`all`, entrypoint por defecto):** engine + API, API en 8731,
engine en loopback 8730. Es la opción más simple para un primer perfil con
llama-swap; se arranca y para como una unidad.

**Dos contenedores (Compose upstream):** servicio `engine` con GPU y servicio
`api` que conecta a `engine:8730`. Ambos deben usar la **misma imagen y versión**.
Permite reiniciar el frontal sin recargar pesos. El puerto del protocolo del
engine **no tiene autenticación y nunca debe publicarse al host/LAN**.

El Compose publicado necesita adaptación antes de usar Docker:

- Usa `group_add: [keep-groups]`, extensión de Podman. Docker necesita grupos
  adecuados; preferir GIDs numéricos comprobados en el host, no asumir que
  `video` y `render` tienen el mismo número dentro de todas las imágenes.
- `ipc: host` figura como requisito medido por upstream; `shm_size` no lo
  sustituye en sus pruebas. Es una excepción de aislamiento para **engine**,
  no razón para dar host IPC/GPU al gateway.
- Mantiene memlock ilimitado y dispositivos `/dev/kfd` y `/dev/dri`.
  Desde 0.6.1 se retiró `seccomp=unconfined` por no aportar beneficio en ese
  caso. No copiar privilegios adicionales de otras toolboxes.
- `depends_on: condition: service_healthy` evita arrancar la API antes del
  engine. El healthcheck envía PING/PONG; abrir TCP no es suficiente.
- Se reserva `start_period: 20m` al engine y `stop_grace_period: 60s` para
  escribir caché al terminar. Son márgenes del ejemplo, no tiempos medidos aquí.
- El mapeo publicado `8731:8731` expone todas las interfaces. Adaptarlo a
  loopback o eliminar publicación si solo lo consume la red del gateway.
- Variables de sampling/política que lee la API deben llegar al servicio API
  cuando se divide; no basta con definirlas en `engine`.

**Inconsistencia detectada en fuente:** comentarios del Compose hablan de un
slot y también de un pool de cuatro contextos, mientras README, FLAGS y el
entrypoint establecen cuatro slots y pool por defecto de dos contextos.
Se contrastó `ENG_SLOTS=4` y el cálculo `ENG_POOL=ENG_CTX*2` del entrypoint.
No usar esos comentarios como contrato. Confirmar valores efectivos en logs y
`/health` de la imagen fijada; el entrypoint visible no permite auditar todos
los internals del motor cerrado.

### 7.3. Pesos: reutilizar no siempre es posible

**Ruta HGN propia:** aproximadamente 118 GiB en disco incluyendo el bundle de
calidad; tokenizer junto a los pesos, overlay específico y visión opcional de
~0.84 GiB. HGN es el formato de Halogen, no un GGUF genérico.

**Ruta GGUF desde 0.7.0:** admite GGUF de esta familia con combinaciones de
tipos soportadas. El caso medido por upstream es Unsloth `UD-IQ4_XS`, con
repack sin recuantizar y un MTP propio de ~1.4 GiB más tokenizer. Se necesitan
todos los shards. Un GGUF no aporta por sí solo el draft head que ejecuta Halogen.

**No permite reutilizar a ciegas los candidatos del laboratorio:** el README
rechaza K-quants (`Q4_K`, `Q5_K`, etc.), `UD-Q4_K_XL` e IQ2/IQ1. El perfil
Bartowski Q4_K_M ensayado aquí y el antiguo UD-Q4_K_XL no deben proponerse como
compatibles. La descarga UD-IQ4_XS mencionada en el histórico estaba iniciada,
no demostrada como completa: comprobar archivos/hashes antes de decidir.

`HALOGEN_GGUF_CACHE=1` puede persistir el repack, con coste aproximado adicional
de 70 GiB y necesidad de escritura. No habilitarlo sobre un volumen RO.
Separar descarga/transformación de serving: preparar artefactos en una ventana
controlada y arrancar con `HALOGEN_DOWNLOAD` desactivado y pesos RO.

### 7.4. Memoria y compatibilidad del host

El inventario histórico del laboratorio tiene 128 GiB físicos pero ~61.73 GiB
de GTT y UMA fija de 2 GiB. El proveedor de Halogen documenta una configuración
de GTT/TTM cercana a 124 GiB y recomienda máquina dedicada. **Es una diferencia
fundamental: Docker no la corrige y la receta no está lista para copiar.**

Halogen declara unos 68 GiB residentes para la ruta HGN, 72 GiB para su GGUF
medido, más buffers/pool y tabla n-gram consultada desde disco. Estas cifras
no son el tamaño total del proceso ni una garantía de fit en el GTT actual.
El README señala que `MemAvailable` puede contar pesos bloqueados como caché
recuperable y sobreestimar fuertemente la memoria disponible. Medir también
presión, I/O, memoria del driver y diagnóstico de arranque del motor.

Distinciones de configuración:

- `HALOGEN_CTX`: máximo por petición, 262144 por defecto publicado.
- `HALOGEN_KV_POOL_POSITIONS`: capacidad conjunta; por defecto dos contextos,
  con tope 1048576 y ajuste descendente si el motor detecta falta de margen.
- `HALOGEN_KV_SLOTS`: concurrencia, cuatro por defecto; reducir slots no
  reduce proporcionalmente la reserva del pool.
- `HALOGEN_MAX_TOK`: tamaño máximo de llamada prefill/arena, **no presupuesto
  de respuesta**. No subirlo al contexto total.
- `HALOGEN_MAX_TOKENS_DEFAULT` y `HALOGEN_MAX_TOKENS_CAP`: presupuesto de
  generación; el razonamiento consume parte de él.
- Extender contexto con YaRN o cambiar el presupuesto de atención cambia
  comportamiento numérico, no solo memoria. No incluirlo en la primera POC.

**UPSTREAM:** Linux nativo, stack amdgpu/KFD, solo `gfx1151`; WSL2 con `/dev/dxg`
no está soportado. Kernel 7.0 es el más antiguo reportado funcionando, no una
frontera de compatibilidad establecida por bisección. El inventario histórico
CachyOS menciona 7.2, pero no se ha comprobado el kernel actual.

Las guías externas proponen ampliar GTT/TTM y desactivar IOMMU. **No se aplica
ningún cambio de firmware/kernel en esta investigación.** Desactivar IOMMU
pierde protección DMA y soporte NPU; no debe ser un requisito automático de
la migración. Tampoco copiar reglas de dispositivos `0666`, `--privileged`,
`SYS_PTRACE` o seccomp desactivado de ejemplos genéricos. Reservar margen al
SO y a los servicios de desarrollo; evaluar memoria por separado y con rollback.

### 7.5. Rendimiento y licencia

El proveedor anuncia para una prueba de 32768 tokens de entrada y 256 de
salida aproximadamente 1424 tok/s de prefill y 41.7 tok/s de decode servido,
con ~29.1 s combinados. Son resultados publicados de una versión/configuración
concreta, a ~85 W de paquete sostenidos y con IOMMU desactivado. No son medidas
del EVO-X2 de este repositorio ni una promesa de «4x» para tareas de desarrollo.

Las cifras de competidores en la portada mezclan sus propias máquinas,
cuantizaciones y ajustes. Más concurrencia mejora throughput agregado, no
necesariamente latencia individual; Halogen desactiva la especulación por
stream al pasar al camino batched. Medir cold/warm prefill, cache hit, reasoning,
prompt, calidad y trabajo completo con condiciones emparejadas.

**Licencia:** motor cerrado con EULA propia, no licencia open source. El texto
consultado permite uso gratuito, comercial/producción, modificación privada,
benchmarks y redistribución sin modificar conservando avisos. Restringe
redistribuir imágenes modificadas a terceros. Los pesos tienen licencias
separadas. Conservar la imagen original y configuración externa evita crear
innecesariamente un derivado publicable; revisar términos antes de distribuir.
No es asesoramiento jurídico ni garantía de términos de versiones futuras.

El proveedor declara ausencia de telemetría y conexiones salientes con
`HALOGEN_DOWNLOAD` desactivado. Es una declaración upstream, no una auditoría
de binario o tráfico. La caché KV puede contener información derivada del
código/prompts: mantenerla privada, con permisos y retención, nunca publicarla.

## 8. Plan de migración por fases

### Fase 0: inventario y recuperación, sin cambiar servicio

En una intervención posterior autorizada, registrar versión efectiva de
Lemonade/llama.cpp, catálogo exacto, residentes/pins, argumentos, memoria,
listeners y procesos. Guardar copia privada de configuración real y su esquema,
no usar el JSON documental como importación. Registrar imágenes disponibles,
Docker/Compose, driver, dispositivos/GIDs, espacio libre y hashes de modelos.

Salida exigida: procedimiento de retorno al estado **observado entonces**, no
al par histórico del 4 de septiembre si el operador ya lo cambió después.
El 403 histórico y el incidente SSE no se consideran resueltos por migrar.

### Fase 1: primer servidor directo, Coder en Vulkan

Preparar una imagen fijada de la toolbox Vulkan y el mismo GGUF Coder; iniciar
solo en una ventana que libere memoria del servicio existente. Usar un contexto
conservador propuesto de 16K-32K y una petición concurrente. Verificar GPU
real, ausencia de fallback a CPU, plantilla de chat/tools, API, streaming,
parada y ausencia de contenedores huérfanos.

No trasplantar todos los flags históricos sin revisar `--help` del binario.
La guía genérica de toolboxes recomienda `--no-mmap`, pero EngramHalo tiene
una excepción explícita de SSD/mmap y Halogen otra arquitectura. **No hay una
política mmap única para todos los motores.**

### Fase 2: API estable y ciclo de vida

Con el backend directo validado, añadir llama-swap, alias estable y reescritura
de ID, clave de entrada, puerto local, readiness y parada explícita. Probar
interrupción del cliente y reinicio del controlador. No cargar un motor real
para responder a cada probe de catálogo.

Mantener el puerto histórico 13305 ocupado por Lemonade hasta el corte. Usar
un puerto de ensayo distinto aprobado; cambiar clientes o puerto una sola vez
tras validar. No ejecutar dos dueños del mismo puerto o modelo.

### Fase 3: Halogen como perfil exclusivo

Revisar primero memoria/kernel y aceptación de licencia. Elegir HGN o GGUF
realmente soportado y preparar artefactos fuera del serving. Comenzar con el
contenedor único, pool/contexto y concurrencia conservadores explícitos, sin
visión ni YaRN. Un pool menor ayuda, pero **no garantiza fit con 61.73 GiB GTT**.

Probar su API directamente y después por gateway, incluidos Chat y Responses,
con y sin streaming. Solo después evaluar split engine/API, contexto mayor,
visión, caché persistente y más agentes. Separar el experimento Halogen de los
ensayos ya documentados de Flash-Next sobre llama.cpp.

### Fase 4: otros runtimes

Comparar ROCm/EngramHalo y vLLM con una receta soportada, uno cada vez. Conservar
cachés de compilación por runtime/versión y no compartirlas indiscriminadamente.
Añadir DS4, ComfyUI y entrenamiento solo cuando exista reserva de GPU común.

### Fase 5: automatización y promoción

Después de validación reproducible, decidir qué perfiles son residentes,
cuáles manuales y cuáles on-demand. Ajustar TTL, cuotas, concurrencia y
precalentamiento. Valorar LiteLLM solo si hacen falta varios usuarios,
credenciales por cliente, proveedores remotos o políticas más complejas.
Nunca configurar fallback a nube por defecto para código privado.

## 9. Matriz de aceptación

| Prueba | Qué registrar | Criterio de aceptación propuesto |
| --- | --- | --- |
| Imagen/artefactos | Digest, revisión, hashes, licencia, dispositivos | Identidad exacta y sin descarga oculta |
| Arranque/parada | Cold start, health real, CID/procesos, memoria antes/después | Sin huérfanos ni memoria retenida que impida el siguiente perfil |
| Catálogo | Alias público, upstream ID, capabilities | Sin prometer modelos residentes o capacidades no verificadas |
| Chat normal y SSE | content, reasoning, finish_reason, usage, fin de stream | Resultado completo y errores interpretables |
| Responses normal y SSE | Eventos, tools, resultados, historial | Funciona con el cliente real o limitación explicitada |
| Herramientas | Dos o más rondas call/result con IDs y JSON válidos | El agente lee, edita y ejecuta tests en un repositorio desechable |
| Structured output | Schema soportado y casos rechazados | Validación local; sin confiar en keywords ignoradas |
| Contexto 2K/8K/32K y después 64K | TTFT real, prefill, decode, RAM/GTT/I/O | Sin OOM, bloqueo GPU o truncación silenciosa |
| Cancelación | Disconnect en prefill/decode, SSE y no SSE | Slot y reserva liberados en plazo definido |
| Cambio incompatible | Drenaje, stop, readiness siguiente | No superposición de pesos grandes ni muerte de tareas activas |
| Concurrencia 1/2/4 | Latencia por petición, throughput agregado, 429/503 | Límite explícito sin sobrepasar memoria ni reintentos en tormenta |
| Fallo de backend | Proceso caído y motor no respondiente | No health falso, rollback solo de recursos propios |
| Seguridad | Red, auth, admin, logs, mounts y salida a Internet | Sin acceso directo LAN a motores ni secretos en evidencia |
| Estabilidad | Sesión de desarrollo repetida, reinicio y cold boot | Recuperación repetible y tests del proyecto correctos |

Para comparar calidad, fijar tareas de programación, commit inicial, prompts,
seeds cuando proceda, presupuesto de salida/razonamiento y revisión de tests.
Un benchmark de 32K debe enviar realmente esa entrada; **configurar contexto
64K no demuestra haberlo llenado**. Contar por separado espera de cola,
arranque, primer byte SSE, primer token de contenido y duración completa.
Un heartbeat no es primer token. No reproducir el timeout largo de Lemonade
como un requisito indiscriminado de rendimiento de todos los backends.

## 10. Seguridad y operabilidad mínimas

- Solo el frontal autorizado se publica; para uso local, loopback. Acceso LAN
  requiere TLS/autenticación y política de red. CORS no sustituye autenticación.
  Verificar las reglas reales de publicación Docker, no asumir que UFW por sí
  solo limita todos los puertos publicados.
- Gateway sin GPU, modelos ni socket Docker si se desacopla el controlador.
  Control de ejecución nunca accesible al modelo ni a usuarios no autorizados.
- Pesos RO, cachés RW acotadas, sin HOME entero, `.ssh`, repositorios privados
  ni volúmenes Docker ajenos. Revisar symlinks de snapshots HF y montar sus
  blobs necesarios o una exportación plana; no copiar solo enlaces colgantes.
- Configuración declarativa confiable: ningún `model` recibido del cliente
  se transforma en comando/imagen/ruta arbitraria. Sin autodownload desde
  repositorios propuestos por el modelo.
- Secretos externos al repo mediante el mecanismo de despliegue apropiado;
  las variables del entorno también son visibles a administradores del daemon.
  Logs de prompts, tools, reasoning, headers de sesión y cachés son privados.
- Inicio/parada exclusivamente de contenedores identificados como propios.
  Nunca `docker stop` global, `prune`, borrado de pesos o de volúmenes como rollback.
- Fijar imagen por digest y revisar origen/licencias. Escanear imágenes no
  equivale a auditar kernels de un binario cerrado.
- Contenedores con GPU/host IPC no son sandboxes fuertes para código hostil.
  Los límites cgroup no equivalen a partición fiable de GTT/VRAM. Prevenir
  sobreasignación por política y mediciones, no solo por `mem_limit`.

## 11. Decisiones y preguntas técnicas pendientes

| Decisión | Estado |
| --- | --- |
| Separar runtime de modelo/almacenamiento | Recomendado, no aplicado |
| Reutilizar toolboxes como servidores no interactivos | Soportado por documentación/código upstream; pendiente GPU local |
| Gateway inicial llama-swap | Propuesto por lifecycle + API; no instalado |
| Mantener Lemonade en primera línea universal | No recomendado sin resolver Responses, auth y control externo |
| Halogen como alternativa exclusiva | Viable para la familia/hardware declarados; memoria actual sin validar |
| Cockpit para ensayos | Ya integra Halogen, pero su ciclo manual/latest no es el despliegue estable |
| Todo el control dentro de Docker | Posible, con tradeoff de socket o controlador adicional; no implementado |
| Aumentar GTT o desactivar IOMMU | No autorizado ni aplicado por este estudio |

Pendientes que solo resuelve una POC: digest descargable elegido y contenido
real de imagen; permiso GPU del usuario Docker; memoria efectiva; compatibilidad
de driver; tool calling del cliente; propagación de desconexión/error SSE;
readiness y cierre de Halogen; fairness de swaps; rendimiento y calidad de
programación; dependencia exacta de kernel; auth del backend Halogen y
superficie administrativa; recuperación tras fallo GPU, no solo proceso.

No se entrega un Compose «listo para producción» porque faltan esas
validaciones y el usuario pidió investigación. Sí quedan definidos componentes,
contratos, orden de migración, riesgos y pruebas para implementarlo sin
improvisar capacidades ni sobrescribir el baseline.

## 12. Fuentes primarias y trazabilidad

Se leyeron README y secciones relevantes mediante `gh api`; para Lemonade se
contrastó además la versión estable `v11.9.0` con `main`. Las URLs de commits
fijan la revisión examinada. Las etiquetas de imágenes citadas son las que
publican esos documentos; **no se resolvieron digests ni se verificó el registro**.

| ID | Fuente y revisión consultada | Evidencia usada |
| --- | --- | --- |
| S1 | [Strix Halo AI Toolboxes](https://strix-halo-toolboxes.com/#toolboxes), web consultada 2026-09-16 | Catálogo, Toolbx/Distrobox, host tuning y advertencias IOMMU |
| S2 | [llama.cpp toolboxes, fdd4ee05b402](https://github.com/kyuz0/amd-strix-halo-toolboxes/commit/fdd4ee05b402ea5873262da6e02314c7788a14a1) | README; `toolboxes/Dockerfile.vulkan-radv`; imágenes, Server Mode, forks y excepción mmap |
| S3 | [vLLM toolboxes, 0dfc5aa0dd2c](https://github.com/kyuz0/amd-strix-halo-vllm-toolboxes/commit/0dfc5aa0dd2c393cc14c3a3f16ef5d4006e372ca) | README; API, Docker, recetas, AITER y límites de benchmarks |
| S4 | [ComfyUI toolboxes, 7e77f04c2926](https://github.com/kyuz0/amd-strix-halo-comfyui-toolboxes/commit/7e77f04c2926153fdb7265752192a1029503149f) | README; workflows API, storage y arranque |
| S5 | [Fine-tuning toolbox, 093a23c0d494](https://github.com/kyuz0/amd-strix-halo-llm-finetuning/commit/093a23c0d49418aef08e5053aa19faf65b35236a) | README; notebooks/Jupyter, no contrato de serving OpenAI |
| S6 | [DS4 toolbox, 72532848ffd7](https://github.com/kyuz0/strix-halo-ds4-toolbox/commit/72532848ffd7f8b4f13e48e775bb2e022979909a) | README; `ds4-server`, endpoints y worker serial sin batching |
| S7 | [AI Toolbox Cockpit, 6959d068c020](https://github.com/kyuz0/ai-toolbox-cockpit/commit/6959d068c020f3f33bfb8ef743e7ba44a6390dda) | README; `ai_toolbox_cockpit/backends/halogen/runner.py`; Docker/Podman, Halogen y latest |
| S8 | [Lemonade main, c3a55b06dea5](https://github.com/lemonade-sdk/lemonade/commit/c3a55b06dea5d1a37f00123306a8e3af9919f99a), [v11.9.0](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0), [commit de v11.9.0](https://github.com/lemonade-sdk/lemonade/commit/bb39eafc22aa7e57fc7aeb8b7d384d70b44a4531) | `docs/guide/configuration/cloud.md`, `docs/guide/cli.md`, `cloud_server.cpp` en ambas revisiones; `router.cpp`, `http_client.cpp` y `llamacpp.md` de main |
| S9 | [Guía Docker oficial de Lemonade](https://lemonade-server.ai/docs/guide/install/docker) y fuente `docs/guide/install/docker.md` de S8 | Imagen, volúmenes, UID/GID, auth y diferencia entre contenerizar y orquestar |
| S10 | [llama-swap, 21bc145a6fa6](https://github.com/mostlygeek/llama-swap/commit/21bc145a6fa6198c4d856fbb0830845c472b0ae4) | README; `docs/config.example.yaml`; guías de cmd, grupos/matriz, capacidad, peers, passthrough, timeouts y autenticación |
| S11 | [LiteLLM, 9cd787386ea4](https://github.com/BerriAI/litellm/commit/9cd787386ea43aa9d6b18d8f31d7528a020a0622) | README; gateway, proveedores, endpoints y controles multiusuario; no POC local |
| S12 | [Halogen, 1c1a44a2b415](https://github.com/peonist-ai/halogen-flash-server/commit/1c1a44a2b415932737c76d4fee7f50a3c0245bca) | README, `docs/FLAGS.md`, `docker-compose.yml`, `deploy/entrypoint.sh`, `LICENSE.md`; versión de imagen anunciada 0.11.1 |

Contexto local utilizado: [referencia reutilizable](configuracion-reutilizable-halo-strix.md),
[estado documental](estado-proyecto.md), [ensayos Flash-Next](ensayos-qwen38-flash-next.md),
[wrapper EngramHalo](../scripts/engramhalo/README.md),
[guía del sitio y tests offline](../site/README.md).

### Mantenimiento de esta investigación

Para revisar una versión futura, repetir el contraste de README con código y
contrato de API. Actualizar fecha/revisión y dejar las observaciones anteriores
como históricas; no sustituir «pendiente local» por «validado» al cambiar una
etiqueta de imagen. Si la POC se ejecuta, publicar un informe separado con
condiciones, resultados y restauración, sin secretos ni estado privado.
