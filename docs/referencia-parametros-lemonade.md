# Lemonade: diccionario público de parámetros

[Estado del proyecto](estado-proyecto.md) |
[English equivalent](en/lemonade-parameter-reference.md) |
[Configuración reutilizable](configuracion-reutilizable-halo-strix.md) |
[Perfil JSON](../config/halo-strix.reference.json)

Esta referencia explica la función y los riesgos de los parámetros que aparecen
en la documentación del laboratorio. **No es un volcado del host, no acredita
salud actual y no debe importarse como configuración.**

## Cómo leer la evidencia

- **BASELINE 2026-09-04:** observación positiva histórica con Lemonade 11.8.1,
  llama.cpp Vulkan b10375, Coder `ctx_size=196608`/`parallel=3`, Thinking
  `ctx_size=98304`/`parallel=1`, `max_loaded_models=2`, ambos `pinned=false` y
  GTT combinado aproximado de 48.02 GiB.
- **OBSERVACIÓN LIVE FECHADA:** lectura operativa atribuida a una fecha; sigue
  sin equivaler al estado de hoy.
- **CONFIGURADO:** valor guardado o incluido en una receta documentada.
- **RECOMENDACIÓN:** propuesta de prueba u operación, no resultado.
- **PENDIENTE:** semántica, precedencia o resultado no cerrados.

Las unidades de contexto y presupuestos son **tokens**; tiempos como
`global_timeout` se expresan en **segundos**; puertos son números TCP; tamaños
de caché dependen del backend. Los argumentos de llama.cpp son sensibles a la
versión: comprobar opciones resueltas y la línea real del proceso.

## Identidad, carga y persistencia

| Parámetro | Función y alcance | Valores documentados | Interacción o riesgo | Evidencia |
| --- | --- | --- | --- | --- |
| `model_name` | ID exacto de catálogo que Lemonade debe resolver/cargar; alcance por solicitud/modelo. | Coder y Thinking-2507 del baseline; Qwen3.8-27B en observaciones posteriores. | No es el nombre amigable ni necesariamente el checkpoint. IDs `user.*` y built-in pueden apuntar al mismo GGUF sin ser alias operativos. Un ID no residente puede provocar autocarga y expulsión LRU. | Baseline 2026-09-04; live 2026-09-08/10. |
| checkpoint / variant | Repositorio o fuente de pesos más variante/cuanti­zación, por ejemplo `repo:Q4_K_M`. Identifica el artefacto, no el registro de catálogo. | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q4_K_M`, `unsloth/Qwen3-30B-A3B-Thinking-2507-GGUF:Q4_K_M`; candidato Qwen3.8 `UD-Q4_K_XL`. | La variante cuantiza **pesos**; no determina la cuantización KV. Descargado/listado no significa cargado ni compatible. | Baseline y documentos históricos; contradicción Qwen3.8 conservada. |
| `ctx_size` | Tamaño total del contexto/KV asignado al backend del modelo, en tokens. | Baseline: Coder 196608, Thinking 98304. Qwen3.8 tenía opciones guardadas 262144 el 2026-09-10; el perfil restaurado del incidente documenta 65536. Prueba transitoria recomendada: 32768. | Con varios slots y `--kv-unified` es un pool total compartido, no contexto por slot. Debe dejar margen para prompt, plantilla, razonamiento y salida. Más contexto aumenta GTT/RAM y prefill. | Baseline; live/documental 2026-09-10; receta transitoria fallida, no válida. |
| `llamacpp_backend` | Selecciona la familia de backend gestionado por Lemonade. | `vulkan` en todas las recetas promovidas/documentadas aquí. | Cambiar backend cambia binario, compatibilidad, memoria y rendimiento. HIP no fue promovido por el benchmark histórico; no extrapolar. | Baseline 2026-09-04. |
| `llamacpp_args` | Cadena de argumentos adicionales entregada al llama-server gestionado, por modelo. | Cadenas literales del baseline y del perfil Qwen3.8 se documentan abajo. | Puede combinarse con defaults globales y opciones guardadas. Flags duplicados o incompatibles pueden sobrevivir a un merge; revisar opciones efectivas y proceso. | Configurado; precedencia completa pendiente. |
| `merge_args` | Solicita combinar argumentos enviados con los ya gestionados/guardados, en vez de asumir reemplazo total. | `true` en el baseline y perfiles restaurados; `false` en la recomendación transitoria Qwen3.8 del 2026-09-10. | El algoritmo exacto, orden y tratamiento de duplicados no están establecidos. `false` reduce la ambigüedad de una prueba, pero no prueba que todos los defaults desaparezcan. | Configurado; semántica completa pendiente. |
| `save_options` | Pide persistir las opciones del modelo para cargas posteriores. | `true` en baseline; `false` en pruebas transitorias. | Guardar opciones no precarga el modelo al arrancar y puede sobrescribir una receta útil. El archivo exacto de persistencia por modelo no está establecido públicamente. | Configurado; ubicación/precedencia pendientes. |
| `pinned` | Marca un modelo residente para protegerlo de la política normal de expulsión, si la versión lo respeta así. | Baseline 2026-09-04: Coder y Thinking `false`. Live 2026-09-08: Coder+Phi residentes, `false`. Live 2026-09-10: Coder+Thinking residentes, ready y `true`; Qwen3.8 descargado/opciones guardadas, `false`. | Un pin no crea memoria. Con el límite lleno puede impedir una carga o trasladar la presión al modelo no fijado. No confundir con `pinned_helper_models`. | Observaciones fechadas; no salud actual. |
| `max_loaded_models` | Límite global de modelos LLM residentes. Unidad: modelos, no slots ni peticiones. | `2`. | Al solicitar un tercero se puede aplicar LRU. El 2026-09-08 una petición Phi-4-mini cargó el modelo y expulsó Thinking; el cliente causante no quedó identificado. | Baseline y live 2026-09-08/10. |

### Cadenas históricas del baseline

Coder:

```text
--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0
```

Thinking-2507:

```text
--parallel 1 --kv-unified --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384
```

## Contexto, concurrencia, caché y atención

| Parámetro | Función y alcance | Valores documentados | Interacción o riesgo | Evidencia |
| --- | --- | --- | --- | --- |
| `--parallel` | Número de slots lógicos del proceso de un modelo. Unidad: solicitudes simultáneas admitidas por ese backend. | Coder 3; Thinking 1; Qwen3.8 1. | No garantiza escalado físico ni menor latencia. Multiplica competencia de KV/compute. Con KV unificada, los slots comparten el contexto total. | Baseline/live fechada. |
| `--kv-unified` | Habilita una reserva KV unificada y reparto dinámico entre slots. | Activado en ambos modelos del baseline; no figuró en la receta Qwen3.8 restaurada del incidente. | Evita interpretar `ctx_size` como una reserva independiente por slot. El reparto no es necesariamente igual ni fijo. Compatibilidad dependiente del backend. | Baseline; ausencia en otra receta no demuestra default. |
| `--flash-attn` | Activa/desactiva kernels de Flash Attention. | `on`. | Puede reducir memoria/mejorar rendimiento, pero depende de arquitectura, backend, cuantización KV y build. Debe validarse, no asumirse. | Baseline y recetas posteriores. |
| `--cache-reuse` | Umbral/tamaño de reutilización de prefijo KV gestionado por llama.cpp. | `256` solo para Coder. | No es HTTP keep-alive ni una caché RAM genérica. Puede mejorar prefijos repetidos; la semántica exacta puede variar por build. No añadirlo a otros modelos sin medir. | Baseline 2026-09-04. |
| `--cache-type-k` | Tipo de cuantización de la caché de claves KV. | `q8_0`. | Reduce memoria KV frente a tipos de mayor precisión; puede afectar calidad/rendimiento. No cambia pesos `Q4_K_M`/`UD-Q4_K_XL`. | Baseline y perfil 2026-09-10. |
| `--cache-type-v` | Tipo de cuantización de la caché de valores KV. | `q8_0`. | Mismas cautelas que K; algunas combinaciones/backend pueden imponer restricciones. | Baseline y perfil 2026-09-10. |
| `--spec-type` | Selecciona el modo de decodificación especulativa. | `none` en la receta Qwen3.8 restaurada y en la prueba transitoria recomendada. | `none` desactiva la ruta especulativa; no mezclar con `draft-mtp` sin una validación explícita. Los defaults guardados del Qwen3.8 incluían `draft-mtp`, creando una interacción que debía aislarse. | Documental/live 2026-09-10; validación pendiente. |

La recomendación operativa histórica de **máximo tres peticiones activas
combinadas** no configura un límite automático. Faltan pruebas N=1/N=2/N=4,
soak y correlación con slots/métricas.

## Razonamiento, muestreo y plantilla

| Parámetro | Función y alcance | Valores documentados | Interacción o riesgo | Evidencia |
| --- | --- | --- | --- | --- |
| `--reasoning` | Activa/desactiva la ruta de razonamiento soportada por el modelo/plantilla. | `on` para Qwen3.8; Coder es non-thinking; Thinking-2507 es always-thinking por su plantilla. | No todos los modelos obedecen el flag. Activarlo consume contexto/salida y no equivale a `reasoning_format`. | Perfil documental 2026-09-10; baseline por identidad de modelo. |
| `--reasoning-budget` | Presupuesto máximo/orientativo de tokens de razonamiento del backend/modelo. | Thinking-2507 16384; Qwen3.8 restaurado 4096; recomendación transitoria 8192. | Forma parte del contexto total y puede consumir el límite de salida visible. No es un número de pasos de agente. | Baseline; documental y recomendación 2026-09-10. |
| `--temp` | Temperatura de muestreo, adimensional. Menor suele reducir aleatoriedad. | Qwen3.8 restaurado `1.0`; la recomendación transitoria exigía muestreo explícito, sin promover un óptimo universal. | Interactúa con top-p/top-k/min-p. Un valor aislado no define toda la distribución. | Documental 2026-09-10. |
| `--top-p` | Muestreo nucleus: masa acumulada retenida, rango habitual 0–1. | `0.95` para Qwen3.8 restaurado. | Se combina con otros filtros; bajar demasiado puede degradar diversidad/corrección. | Documental 2026-09-10. |
| `--top-k` | Conserva como candidatos los K tokens más probables. Unidad: tokens candidatos. | `20`. | `0` puede significar desactivado según versión; verificar contrato. Interactúa con temperatura y top-p. | Documental 2026-09-10. |
| `--min-p` | Descarta tokens por probabilidad relativa mínima. | `0.0` en el perfil restaurado. | `0.0` suele desactivar el filtro; confirmar en el build. Puede ser redundante con otros filtros. | Documental 2026-09-10. |
| `--repeat-penalty` | Penalización adimensional a tokens repetidos. | `1.0` en el perfil restaurado. | `1.0` suele ser neutro. Valores altos pueden romper código, citas o formatos repetitivos. | Documental 2026-09-10. |
| `--chat-template-kwargs` | JSON literal pasado a la plantilla de chat. Alcance por modelo/carga o petición. | Qwen3.8: `{"reasoning_effort":"medium","preserve_thinking":true}`. El probe SSE usa por petición `{"enable_thinking":false}`. | En UI se pega JSON literal; en un payload JSON externo hay que escapar comillas una sola vez. Claves desconocidas pueden ignorarse o fallar según plantilla. | Perfil documental y contrato del probe. |
| `reasoning_effort` | Nivel solicitado a la plantilla/modelo, no un parámetro universal de llama.cpp. | Guardado `medium` para Qwen3.8; probe SSE `none`. | Solo funciona si la plantilla lo interpreta. No sustituye `--reasoning-budget`; puede contradecir otros overrides. | Documental 2026-09-10 y prueba SSE. |
| `preserve_thinking` | Pide conservar el razonamiento según el contrato de plantilla/salida. | `true` entre los defaults/opciones Qwen3.8 documentados. | Puede aumentar contenido de razonamiento expuesto o retenido. No garantiza el campo exacto; revisar `content` y `reasoning_content`. | Live/documental 2026-09-10. |
| `reasoning_format` | Controla cómo se analiza/formatea el razonamiento en la respuesta. | Default documentado `auto`; modos históricos: `none`, `deepseek`, `deepseek-legacy`, `auto`. | **No activa thinking.** Cambia dónde aparece el texto (`content`/`reasoning_content`) y puede afectar clientes. | Baseline/documentación del build. |

Receta restaurada documentada para Qwen3.8 en el informe SSE:

```text
--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --spec-type none --reasoning on --reasoning-budget 4096 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --chat-template-kwargs '{"reasoning_effort":"medium","preserve_thinking":true}'
```

## Servicio, red, rutas y timeout

| Parámetro | Función y alcance | Valores documentados | Interacción o riesgo | Evidencia |
| --- | --- | --- | --- | --- |
| `host` | Dirección donde escucha Lemonade. | `<HALO_HOST>`: dirección autorizada específica; no se publica la real. | `127.0.0.1` limita al host; wildcard amplía exposición. La CLI histórica intentó localhost aunque el servicio estaba ligado a LAN. | Baseline histórico. |
| `port` | Puerto TCP público del servicio. | `13305`. | Debe coincidir con firewall, clientes y origen CORS. No confundir con listeners internos. | Baseline histórico. |
| `broadcast` | Controla el anuncio/descubrimiento del servicio. | `false`. | Desactivarlo reduce descubrimiento accidental, pero no es firewall ni autenticación. | Baseline configurado. |
| CORS / `LEMONADE_ALLOWED_ORIGINS` | Lista de orígenes web permitidos: esquema+host+puerto, sin ruta API. | Históricamente `http://<HALO_HOST>:13305`; lista separada por comas. En 11.9.0 el informe documenta migración a `allowed_origins`. | No usar `*` como sustituto de diseño de acceso. Un origen no configurado puede recibir 403. CORS no autentica clientes no navegador. Cambios de entorno requieren reinicio. | Baseline y registro documental 2026-09-10. |
| `models_dir` | Caché/directorio principal de descargas gestionadas. Debe ser ruta absoluta. | `$HOME/ai/lemonade/models` como placeholder documental a expandir. | `~` literal causó resolución incorrecta en una versión histórica. No es igual a `extra_models_dir`. | Configurado históricamente. |
| `extra_models_dir` | Raíz adicional para escaneo recursivo de GGUF locales. | `$HOME/ai/models/smoke`, expandido privadamente. | Cambiarla altera descubrimiento y puede crear colisiones de catálogo. En 11.9.0 hay cambios para directorios reservados. | Configurado; compatibilidad por versión. |
| `global_timeout` | Timeout global del servidor, en segundos. | `1200` persistido según el informe de mantenimiento del 2026-09-10. | En 11.8.1 no gobernaba la rama SSE de baja transferencia de 120 s. El informe afirma que 11.9.0 la hace respetar el timeout configurado. No cambia timeouts de cliente/proxy ni acelera prefill. | Registro documental posterior; incompatible con un checkpoint de sesión anterior a la instalación, sin corroboración independiente aquí. |

### Listeners gestionados y argumentos añadidos

Lemonade creó procesos llama-server en loopback. El baseline observó
`127.0.0.1:8001` y `127.0.0.1:8002`; el puerto auxiliar `9000` también fue
observado. Son **asignaciones internas históricas**, no API pública ni contrato
estable. Consultar `backend_url` en health y no asumir un puerto.

Además de la receta del usuario, el proceso gestionado añadió:

- `--jinja`: habilita el motor de plantillas Jinja para aplicar chat templates.
  Riesgo: la plantilla efectiva cambia tokenización, herramientas y razonamiento.
- `--metrics`: expone métricas del backend en su listener interno. No implica
  que estén publicadas, monitorizadas o protegidas para acceso remoto.
- `-m`, `--ctx-size` y `--port`: Lemonade resuelve el GGUF, traduce `ctx_size`
  y asigna el listener. No duplicarlos a ciegas dentro de `llamacpp_args`.

## Endpoints relevantes

| Método y ruta | Contrato operativo | Riesgo/estatus |
| --- | --- | --- |
| `GET /` | Web App / Model Manager integrado. | HTML correcto no prueba backend ready. |
| `GET /api/v1/health` | Estado de servicio, residentes, backend y opciones de receta. | Lectura fechada; revisar `status`, `backend_alive`, `backend_health` y actividad. |
| `GET /v1/models` | Catálogo compatible con OpenAI. | Listado/descarga no implica residencia. |
| `GET /v1/models/<ID>/options` | Opciones resueltas por ID. | Ruta validada históricamente; revalidar por versión. |
| `GET /internal/config` | Configuración efectiva global. | Interno y dependiente de versión; no publicar el volcado. |
| `GET /api/v1/downloads` | Estado de descargas. | No interrumpir trabajos activos. |
| `POST /internal/set` | Cambia configuración, por ejemplo `max_loaded_models`. | Mutable; respaldar y verificar persistencia. |
| `POST /api/v1/load` | Carga/configura un modelo. | Puede consumir memoria, persistir opciones y expulsar otro modelo. |
| `POST /v1/chat/completions` | Inferencia compatible con OpenAI. | Puede autocargar y activar LRU; streaming usa SSE. |
| Backend `/tokenize`, `/props`, `/slots` | Rutas nativas del llama-server residente. | Solo mediante el `backend_url` observado en host; no añadir `/v1` ni exponerlas. |

## Cronología que limita la interpretación

1. **2026-09-04, baseline:** Coder+Thinking-2507, 3+1 slots, 48.02 GiB GTT,
   ambos `pinned=false`, Lemonade 11.8.1/b10375.
2. **2026-09-04, posterior:** se reportó un 403 sin ruta, cliente, causa ni
   resolución confirmados.
3. **2026-09-08, live fechada:** una petición Phi-4-mini activó autocarga y
   LRU al alcanzarse dos residentes; Thinking fue expulsado. Quedaron
   Coder+Phi, ambos sin pin. El cliente causante no fue identificado.
4. **2026-09-10, live fechada:** seguía 11.8.1; Coder+Thinking estaban
   residentes/ready y fijados, máximo LLM 2. Qwen3.8-27B aparecía descargado,
   `pinned=false`, con `ctx_size=262144`, `merge_args=true` y defaults guardados
   de sampling, `preserve_thinking`, `draft-mtp` y `parallel=1`.
5. **2026-09-10, recomendación fallida:** prueba transitoria Qwen3.8 con
   `ctx_size=32768`, Vulkan, `parallel=1`, Flash Attention on, KV Q8,
   `spec-type none`, reasoning on, budget 8192, sampling explícito,
   `preserve_thinking`, `merge_args=false`, `save_options=false`. El usuario
   informó que la carga falló; causa y restauración posterior no se cerraron.
   **No usar esta receta como procedimiento válido.**
6. **Registro documental posterior:** los informes SSE afirman instalación de
   Lemonade 11.9.0/b10723, restauración de perfiles, `global_timeout=1200` y dos
   PASS largos. El historial de sesión disponible contiene un checkpoint
   anterior donde 11.9.0 solo estaba preparado. Sin corroboración externa en
   esta tarea, ambos hechos se conservan con su procedencia y no se inventa una
   resolución adicional.

## Revalidación mínima antes de reutilizar

Confirmar versión, health, residentes/pins, catálogo exacto, opciones resueltas,
línea del proceso, contexto/slots, GTT, CORS y trabajo activo. Después, en una
ventana autorizada, probar un modelo ya residente. Siguen pendientes: precedencia
completa y archivo de opciones por modelo, cold boot/preload, TLS, 403, soak y
concurrencia, entrenamiento LLM real y vLLM.
