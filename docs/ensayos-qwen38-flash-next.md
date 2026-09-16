# Ensayos Qwen3.8-Flash-Next: matriz 64K N1-N4 (2026-09-15)

[English version](en/qwen38-flash-next-trials.md) |
[Guía de modelos (comparativa)](comparativa-qwen38-halo-strix.md) |
[Estado documental](estado-proyecto.md) |
[Perfil JSON](../config/halo-strix.reference.json)

**Procedencia:** registro operativo sanitizado de sesión más artefactos de
medición (`result.json`, `summary.json`, `checkpoint.json` de la corrida),
no una auditoría nueva realizada al redactar este documento. Los números
citados aquí provienen de esas corridas puntuales del **2026-09-15**
(ventana real `07:26:12Z`–`07:35:25Z`, ~9m13s de ejecución activa) y de
hallazgos de investigación previos fechados. Nada aquí es una comprobación
de salud del host en el momento de lectura.

Este documento es un informe **fechado y aditivo**: no sustituye ni
contradice el [baseline positivo del 2026-09-04](configuracion-reutilizable-halo-strix.md)
(Coder + Thinking, 3+1 slots) ni cierra el
[HTTP 403 abierto](estado-proyecto.md) de esa misma fecha, ni el
[incidente SSE del 2026-09-10](incidente-sse-lemonade.md). Es una línea de
evidencia nueva y separada sobre un candidato experimental ya catalogado
como bloqueado (`Qwen3.8-Flash-Next`, arquitectura `qwen4exp`), que pasa de
"no soportado por el build antiguo" a "cargado y respondido con éxito bajo
condiciones acotadas", sin que eso implique una validación completa ni una
promoción a modelo residente permanente.

## Resumen de qué cambió respecto al estado documentado previamente

| Aspecto | Estado documentado hasta 2026-09-10 | Observación nueva 2026-09-15 |
| --- | --- | --- |
| Soporte de arquitectura `qwen4exp` | Rechazado por el build gestionado `b10375` (`unknown model architecture: 'qwen4exp'`) | El build vivo posterior `b10723@010be9683` **sí** incluye el soporte base (PR upstream #27742), verificado por inspección de fuente, no solo por versión anunciada |
| Ejecución real de una carga | Ninguna carga exitosa registrada | Cuatro perfiles (`N1..N4`) cargados, sirvieron inferencia real y se restauraron correctamente |
| Riesgos conocidos de la arquitectura | Sin datos locales | El PR de correcciones upstream #27941 (seq_cp, block keying, M-RoPE, abort en CUDA) **no** está incluido en el build vivo; se mitigó evitando el KV unificado, no por parche aplicado |

Nada de esto reabre ni cierra el 403 de septiembre 4, ni el incidente SSE de
septiembre 10; son líneas de evidencia paralelas sobre asuntos distintos.

## 1. Compatibilidad de arquitectura verificada por código fuente

El build gestionado vivo en el momento de estos ensayos era
`llama.cpp` Vulkan **`b10723`, commit `010be9683`**. Se verificó por
inspección directa del código fuente publicado (no solo por el número de
versión anunciado):

- **PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742)**
  (soporte base de la arquitectura `qwen4exp` / Qwen3.8-Flash-Next,
  fusionado 2026-08-27): **incluido**. El archivo `src/models/qwen4exp.cpp`
  existe en el commit `010be9683` del repositorio.
- **PR [#27941](https://github.com/ggml-org/llama.cpp/pull/27941)**
  (correcciones posteriores: `seq_cp`/indexado de caché, "block keying",
  M-RoPE, un caso de aborto en CUDA): **NO incluido**. Comparación oficial
  de la API de GitHub entre `010be9683` y el commit de fusión de ese PR
  (`36b1015...`) confirma que el build vivo queda por detrás de esos ocho
  archivos de corrección.

Esto significa: el modelo **carga y genera** en el build vivo (soporte base
presente), pero **sin** las correcciones de robustez de #27941. La mitigación
identificada para operar en este estado es usar `--no-kv-unified` (KV
particionado por slot, en vez de pool compartido dinámico), lo que evita el
patrón de riesgo conocido de mezcla de secuencias en el pool unificado. Esto
es una **mitigación de un riesgo conocido, no una garantía general de
ausencia de fallos** de una arquitectura sin sus correcciones upstream. No
se ha validado localmente ningún escenario multi-secuencia adversarial,
tool calling, entrada de visión, ni contexto sostenido largo bajo esta
combinación.

## 2. Cronología de los ensayos (todos fechados, ninguno es salud permanente)

### 2026-09-14: ensayo conservador N1/ctx4096 (real, exitoso)

Primer ensayo real (no simulado), con autorización **humana** registrada
por el coordinador (respuesta «Autorizo este ensayo» citada del checkpoint
de aprobación; el coordinador registra y transmite esa autorización, no es
quien autoriza por sí mismo), alcance: liberar la residencia (sin borrar
archivos) de Coder y Qwen3.8-27B, cargar Flash-Next con un perfil
conservador (`--cpu-moe`, PLE en CPU vía
`--override-tensor '^per_layer_token_embd[.]weight$=CPU'`, Vulkan, `--mmap`,
KV en `f16`, un slot, contexto 4096), servir dos respuestas cortas y
restaurar.

- **Carga:** 24.1 s, todos los flags aplicados exactamente según
  `launch_command` verificado (sin `-ngl`/`--n-gpu-layers`, no solicitado).
- **Prueba 1** (JSON exacto `{"sum":4}`): `finish_reason: stop`, contenido
  correcto. `prompt_ms 8843.7` (sin caché, `cache_n=0`), `predicted_ms
  3671.2` (49 tokens, ≈13.35 tok/s), **~12.5 s de pared total**.
- **Prueba 2** (`READY` exacto): `finish_reason: stop`, contenido correcto.
  `cache_n 42` (reutilizó caché), `prompt_ms 1591.3`, `predicted_ms 1992.7`
  (32 tokens, ≈16.06 tok/s), **~4.2 s de pared total**.
- **Restauración:** verificada exacta byte a byte contra los valores
  guardados de Coder (196608/parallel 3) y Qwen3.8-27B (65536/parallel 1),
  `restore_verified_ok: true`.
- No se probó SSE/streaming en este ensayo (se pidió explícitamente "sin
  umbral SSE"); no se probaron slots 2-4; una sola muestra N=1/ctx4096 no
  permite inferir "mejor configuración".

### 2026-09-14/15: primer intento N1 a 64K dentro del plan de matriz (bloqueado por un bug de instrumentación, NO por incompatibilidad de modelo)

Este intento **no** ejecutó la matriz completa N1-N4: fue un subconjunto
reducido, deliberadamente acotado a un único perfil `N1` (`ctx_size 65536`,
`parallel 1`, deadline de 300 s, una sola repetición), como primer paso
dentro del plan de la matriz aprobada
(`N1..N4`, `ctx_total = 65536×N`, `parallel = N`, con
`--no-kv-unified --cpu-moe --override-tensor
'^per_layer_token_embd[.]weight$=CPU' --cache-type-k f16 --cache-type-v f16
--mmap --spec-type none`) usando un runner automatizado.

- **Preflight:** coincidencia exacta contra el snapshot aprobado; sin
  drift. Unload de ambos modelos originales: correcto.
- **Fallo real:** al arrancar el primer perfil (N1), el runner lanzó una
  excepción de Python al intentar pasar un objeto `Deadline` (que contiene
  un `threading.Event`) a un proceso hijo vía `multiprocessing` en el
  intérprete remoto **Python 3.14**: `TypeError: cannot pickle
  '_thread.lock' object`. Es un defecto de serialización del *runner* de
  pruebas (objetos con locks no son picklables por diseño de
  `multiprocessing`), **no** una incompatibilidad del modelo, del backend
  Lemonade/llama.cpp, ni un fallo de autorización o de gate de seguridad.
- **La restauración sí se ejecutó** (bloque `finally` del runner) y se
  verificó correcta por dos comprobaciones independientes entre sí (la
  del propio runner, más una consulta de salud separada hecha por el
  mismo operador tras la finalización del proceso, sin reutilizar datos
  cacheados del runner — no una auditoría por una persona distinta):
  ambos modelos originales recargados con argumentos idénticos byte a
  byte a los guardados antes del ensayo.
- **No se obtuvo ninguna métrica de latencia/tokens/TPS** en este intento:
  el fallo ocurrió antes de la primera petición HTTP de inferencia real.
- **Corrección aplicada realmente** (no solo propuesta): se implementó
  `Deadline.__getstate__`/`__setstate__` para que el objeto serialice
  únicamente el valor `float` de la fecha límite (`monotonic()` deadline)
  al pasar por `pickle` hacia el proceso hijo, sin transportar nunca el
  `threading.Event`/`Condition` subyacente; el hijo reconstruye el objeto
  `Deadline` a partir de ese valor. Se confirmó que los objetivos pasados a
  `multiprocessing` (incluido el propio `Worker`/función de entrada) son
  importables por nombre bajo los métodos de arranque `spawn` y
  `forkserver` (se corrigió además el problema de invocar el script como
  archivo principal en vez de módulo con nombre-con-guion). **No** se
  aplicó ni se afirma como arreglo un cambio a `WORKER_MODE="thread"` ni un
  "fallback" a hilos: esa opción se mencionó únicamente como alternativa
  hipotética en el hallazgo original, no como lo que se implementó.

### 2026-09-15: reintento de N1 con la corrección aplicada (real, exitoso, ejecución independiente)

Tras aplicar la corrección al objeto `Deadline` (verificada por revisión
de seguridad, con GO condicional, contra los métodos de arranque `spawn` y
`forkserver` reales), se repitió **solo el perfil N1** como validación
puntual del arreglo, con éxito: `status=completed`, `restore_verified_ok:
true`. **Esta fue una corrida independiente**, con su propio tiempo de
carga (`load_elapsed_s=3.18`) y sus propias dos rondas de inferencia
(prompts reales de `88` y `201` tokens; `predicted_per_second` de
`15.486` y `16.559` tok/s respectivamente) — **no** son los mismos
números que el perfil `N1` de la matriz completa final de la siguiente
sección (que tiene su propio tiempo de carga de `10.40` s y su propio
conjunto de 6 rondas). Este reintento validó únicamente el fix de
instrumentación en un ciclo N1 aislado; sus métricas no se combinan ni se
promedian con las de la matriz completa, que fue una ejecución posterior
y separada (ver [sección 3](#3-resultados-de-la-matriz-completa-n1-n4-2026-09-15)).

### 2026-09-15: matriz completa N1-N4 (real, exitoso, ventana `07:26:12Z`-`07:35:25Z`)

Con el runner corregido, se ejecutó la matriz completa de los cuatro
perfiles aprobados en una sola corrida continua. Ver la
[sección 3](#3-resultados-de-la-matriz-completa-n1-n4-2026-09-15) para los
números completos.

## 3. Resultados de la matriz completa N1-N4 (2026-09-15)

**Configuración común a los cuatro perfiles:** Vulkan, `--no-kv-unified`
(KV particionado por slot, no compartido), `--cpu-moe`, `--override-tensor
'^per_layer_token_embd[.]weight$=CPU'` (embedding por capa fijado a CPU),
`--cache-type-k f16 --cache-type-v f16` (sin cuantización de KV en este
ensayo, a diferencia del baseline Coder/Thinking que usa `q8_0`), `--mmap`,
`--spec-type none` (sin decodificación especulativa). `ctx_size` es el
**total** del backend para ese perfil; con `--no-kv-unified` cada slot
recibe una partición fija de **65536 tokens** independientemente de `N`
(no un reparto dinámico del pool, a diferencia del baseline Coder). Cada
perfil ejecutó 3 repeticiones × 2 prompts sintéticos fijos = 6 rondas de
inferencia, con `N` peticiones concurrentes despachadas por el cliente en
cada ronda cuando `N>1`.

| Perfil | ctx total / slots (parallel) | Tiempo de carga (s) | Peticiones OK / planificadas | `predicted_per_second` por petición (servidor, tok/s): mín–media–máx |
| --- | --- | ---: | --- | --- |
| N1 | 65536 / 1 | 10.40 | 6 / 6 | 15.23 – **16.13** – 16.71 |
| N2 | 131072 / 2 | 2.78 | 12 / 12 | 10.87 – **12.38** – 13.31 |
| N3 | 196608 / 3 | 3.08 | 18 / 18 | 8.87 – **10.02** – 11.53 |
| N4 | 262144 / 4 | 3.31 | 24 / 24 | 7.33 – **8.68** – 9.61 |

`predicted_per_second` es el throughput de generación (decode) reportado
por el propio servidor llama.cpp para **cada petición individual**
(`server_timings.predicted_per_second`); no es un agregado de cliente ni
un throughput de sistema completo, y no incluye tiempo de prefill/cola.

Todas las **60 rondas de petición** (3 repeticiones × 2 prompts × hasta 4
perfiles con distinto `N`) pasaron verificación de contenido
(`content_verified=true`) con `finish_reason=stop` real, sin forzar el
tope de tokens. Tokens de prompt reales (dos prompts sintéticos fijos,
cortos): rango **88–201** tokens. Tokens de completado reales (tope
configurado 256, parada real siempre antes de ese tope):

| Perfil | Rango de tokens de completado (real) |
| --- | --- |
| N1 | 112–147 |
| N2 | 111–190 |
| N3 | 100–247 |
| N4 | 80–196 |

### Latencia de pared por petición y por ronda (cliente)

| Perfil | `wall_s` por petición, mín–máx | `round_wall_s` por ronda, mín–máx | Suma de las 6 rondas del perfil |
| --- | --- | --- | ---: |
| N1 | 12.235–18.293 | 12.27–18.52 | 84.597 s |
| N2 | 15.357–21.780 | 17.77–22.02 | 115.864 s |
| N3 | 18.729–30.501 | 20.77–30.54 | 161.418 s |
| N4 | 14.285–32.591 | 16.52–32.78 | 139.403 s |

Duración total de la ventana activa de ejecución (los cuatro perfiles,
incluyendo carga/descarga y restauración final): **≈551.3 s (~9.2 min)**,
dentro de un presupuesto de 1800 s (quedaron ~1248.7 s de margen sin usar).

### Throughput agregado ponderado por perfil

La forma correcta de calcular un throughput agregado cuando las rondas
tienen duraciones distintas es
`suma(tokens_completado) / suma(round_wall_s)` — **no** multiplicar la
media de tokens/s por el número de peticiones, ni promediar las razones
por ronda:

| Perfil | Throughput agregado ponderado (tok/s) |
| --- | ---: |
| N1 | 9.27 |
| N2 | 14.17 |
| N3 | 17.24 |
| N4 | 22.22 |

**Interpretación explícita:** el throughput agregado por pared crece con
`N` (esperable: más peticiones concurrentes por ronda), pero el
`predicted_per_second` **por petición individual** decrece de forma
monótona de N1 (~16.1 tok/s de media) a N4 (~8.7 tok/s de media),
consistente con contención de cómputo/memoria compartida entre slots bajo
esta configuración `cpu-moe + mmap + Vulkan`. Esta es una observación
puntual de esta corrida concreta del 2026-09-15, **no** un baseline de
rendimiento permanente ni una proyección de valor óptimo para otras
cargas de trabajo.

El campo `overlap_label` distingue: para N1 fue
`client_scheduled_no_overlap_detected`; para N2-N4 fue
`client_scheduled_overlap`, es decir, el **cliente** despachó las `N`
peticiones de cada ronda de forma concurrente. **Esto no certifica solape
real de ejecución en el backend**, solo que el cliente las lanzó juntas;
el runner no instrumenta el backend para confirmar solape físico de
cómputo.

### Guardas de recursos durante todo el ciclo (275 muestras, ~2 s de intervalo)

| Métrica | Mínimo observado | Máximo observado | Guarda configurada |
| --- | ---: | ---: | ---: |
| Memoria disponible (GiB) | 75.194 | 120.910 | 16.0 |
| GTT libre (GiB) | 16.482 | 61.714 | 4.0 |

Ningún guarda se disparó en ningún momento (`breach_reason: null`). Estas
son muestras del **proceso completo** (los cuatro perfiles seguidos,
incluyendo cargas/descargas intermedias), no un desglose por perfil ni una
prueba de un pico de asignación exclusivo de Flash-Next a contexto 64K
completo. La CPU y la GPU comparten memoria unificada en este equipo; no
se puede sumar memoria de GPU y de sistema como si fueran recursos
independientes.

### Restauración (verificada por dos comprobaciones independientes entre sí)

1. **El propio runner** (`restore.phase="finally"`,
   `restore.restore_verified_ok=true`, `restore.mismatches=[]`): descargó
   Flash-Next, confirmó su ausencia, y recargó Coder (6.62 s) y
   Qwen3.8-27B (6.78 s) con sus argumentos guardados.
2. **Consulta de salud separada**, realizada por el mismo operador
   después de que el proceso terminara, sin reutilizar datos del runner:
   Coder (`pinned=true`, `ready`, `ctx_size=196608`, argumentos idénticos
   byte a byte al preflight) y Qwen3.8-27B (`pinned=true`, `ready`,
   `ctx_size=65536`, argumentos idénticos byte a byte, incluyendo el
   bloque `--chat-template-kwargs`). `pinned_models.llm=2`,
   `max_models.llm=2`, sin cambios. Flash-Next ausente de residentes.

**Conclusión de restauración: completa y correcta**, confirmada por dos
comprobaciones que no comparten código y coinciden exactamente con el
estado previo a la mutación. **Precisión importante:** ambas
comprobaciones fueron realizadas por el mismo operador en la misma sesión
(una desde dentro del runner, otra como consulta manual posterior); no
constituye una auditoría independiente por una segunda persona ni por un
tercero externo, solo dos lecturas técnicas separadas que no comparten
código entre sí.

## 4. Ejemplo ilustrativo de cuerpo de carga (NO un comando ejecutado ahora)

El siguiente bloque es un **ejemplo copiable de referencia** del perfil N3
de la matriz (`196608` de contexto total, 3 slots), tal como fue verificado
en `effective_llamacpp_args` durante el ensayo del 2026-09-15. **No es una
llamada HTTP automática, no debe pegarse contra un host sin revisión
propia, y el ID de modelo, ruta y host son ilustrativos:**

```json
{
  "model_name": "Qwen3.8-Flash-Next-GGUF-UD-Q4_K_XL",
  "ctx_size": 196608,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 3 --no-kv-unified --cpu-moe --override-tensor '^per_layer_token_embd[.]weight$=CPU' --cache-type-k f16 --cache-type-v f16 --mmap --spec-type none",
  "merge_args": false,
  "save_options": false,
  "pinned": false
}
```

Este cuerpo se documenta como referencia porque fue efectivamente el que
produjo el perfil N3 medido arriba, no porque se recomiende aplicarlo sin
revisión: requiere liberar antes la residencia (sin borrar archivos) de
cualquier modelo grande residente,
verificar memoria/GTT libres, y restaurar manualmente al finalizar (ver
la sección siguiente).

## 5. Restauración manual de referencia (Coder + Qwen3.8-27B)

Los cuerpos de carga exactos usados para restaurar el par original tras
cada ensayo de esta línea de trabajo (`save_options: false` en ambos, para
no sobrescribir la configuración `saved` del catálogo durante los
ensayos). Esta captura es una instantánea fechada del **2026-09-14**,
tomada antes del ensayo, y **no** es la misma fuente de datos que el
[perfil JSON](../config/halo-strix.reference.json) (que registra un
`baseline` histórico distinto, fechado el 2026-09-04, con
`save_options: true`, para la pareja Coder+Thinking, no Coder+Qwen3.8-27B)
ni que la [configuración reutilizable](configuracion-reutilizable-halo-strix.md)
(que documenta la semántica general de `save_options`, no estos payloads
exactos). En particular, los argumentos completos de razonamiento de
Qwen3.8-27B (`--chat-template-kwargs` con `reasoning_effort`/
`preserve_thinking`) **no** están reproducidos palabra por palabra en
ninguno de esos otros dos documentos; se citan aquí como referencia
propia de esta línea de ensayos, no como una repetición de datos ya
publicados en otro lugar:

```json
{
  "model_name": "Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M",
  "ctx_size": 196608,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0",
  "merge_args": true,
  "save_options": false,
  "pinned": true
}
```

```json
{
  "model_name": "Qwen3.8-27B-GGUF-UD-Q4_K_XL",
  "ctx_size": 65536,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --spec-type none --reasoning on --reasoning-budget 4096 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --chat-template-kwargs '{\"reasoning_effort\":\"medium\",\"preserve_thinking\":true}'",
  "merge_args": true,
  "save_options": false,
  "pinned": true
}
```

**Advertencia explícita:** esta pareja fue la observada residente y
restaurada el 2026-09-15 con estos argumentos exactos; **no es una
recomendación de que la próxima carga deba usar overrides idénticos sin
revisión propia**. `save_options` se dejó en `false` en ambas llamadas de
restauración, deliberadamente, para no sobrescribir la configuración
`saved` que el catálogo del servicio ya tenía persistida antes del ensayo.
Ningún modelo quedó pineado con garantía de no-desalojo permanente:
`pinned=true` bloquea el desalojo LRU automático mientras se mantenga así,
pero no es lo mismo que un límite físico de memoria; un `unload` explícito
con aprobación sigue siendo la única vía documentada para liberar un
modelo pineado intencionalmente.

## 6. Lo que NO se afirma (límites explícitos de esta línea de ensayos)

- **No se probó contexto largo real (~60K tokens de prompt) ni TTFT.** Los
  prompts reales usados fueron cortos (88-201 tokens); el runner usado no
  implementa medición de TTFT en streaming ni prompts de tamaño completo
  de contexto. La etiqueta "contexto 64K por slot" describe el
  **presupuesto configurado**, no un contexto de entrada completado y
  validado.
- **El solape de backend no está probado.** `client_scheduled_overlap`
  confirma solo que el cliente despachó peticiones concurrentes; no hay
  instrumentación de backend que confirme paralelismo físico real de
  cómputo en la GPU/CPU compartida.
- **No hay "mejor perfil global".** Los cuatro perfiles pasaron bajo las
  mismas condiciones de contención de recursos del host en ese momento
  puntual; no se puede generalizar a otras cargas, tamaños de prompt,
  patrones de tool calling, entrada de visión o ejecución sostenida
  (soak) de larga duración — ninguno de esos escenarios fue ejercitado.
- **Cache fría/caliente mixta.** Las muestras de esta corrida mezclan
  peticiones con caché de prefijo fría (`cache_n=0`) y caliente
  (`cache_n>0`); no se reclama un estado de "carga en frío" puro para
  toda la matriz.
- **No se toca el estado permanente del host.** No se cambiaron
  `max_loaded_models`, CORS, red, credenciales, ni se realizaron
  actualizaciones o reinicios de servicio en ninguno de estos ensayos.
- **El estado restaurado observado el 2026-09-15 no es una comprobación
  de salud permanente.** No promueve a Qwen3.8-27B ni a Flash-Next a
  modelo residente validado, ni cierra el 403 de septiembre 4 ni el
  incidente SSE de septiembre 10; son líneas de evidencia separadas.
- **"Todos los ensayos sin mutación" es incorrecto como generalización.**
  El intento bloqueado por el bug de `multiprocessing` (2026-09-14/15) sí
  llegó a descargar (`unload`) ambos modelos originales antes de fallar en
  el primer round de inferencia; la restauración real ocurrió y se
  verificó, pero hubo una ventana real de mutación, no una ausencia total
  de cambio de estado.

## 7. Próximas medidas recomendadas (propuesta, no ejecutadas)

Estas son recomendaciones explícitas para una futura sesión autorizada, no
un plan ya aplicado:

1. **N2/N3 con entradas reales de mayor tamaño** (8K/32K/60K tokens,
   contados con el tokenizer real, no caracteres), midiendo TTFT en modo
   streaming además del throughput de decode ya medido aquí.
2. **Instrumentación de solape real de backend** (métricas internas de
   slots/tiempos por GPU, no solo el despacho concurrente del cliente).
3. **Prueba sostenida (soak)** de duración larga bajo carga mixta, no solo
   seis rondas cortas por perfil.
4. **Tool calling y entrada de visión** con Flash-Next, ninguno validado
   hasta ahora en este equipo.
5. **Reevaluación tras el merge del PR upstream #27941** (correcciones de
   `seq_cp`, indexado de bloques, M-RoPE y el caso de aborto en CUDA), que
   podría cambiar los riesgos y habilitar el pool KV unificado sin la
   mitigación actual de `--no-kv-unified`.
6. **Ensayo de contexto largo "sweet spot": aprobado 2026-09-15, no
   ejecutado / 0 peticiones por bloqueo de transporte (sin valores de
   resultado porque no llegó a correr):**
   - Estado real: la aprobación humana exacta para este ensayo se
     confirmó el **2026-09-15** (registro operativo sanitizado de
     autorización y captura previa, sin rutas ni referencias de archivo
     privadas), con el mismo alcance y presupuesto descritos abajo. La
     ejecución **no ocurrió**:
     0 peticiones de inferencia, 0 cargas/descargas de modelo. El bloqueo
     fue exclusivamente de transporte (canal SSH/ControlMaster hacia el
     runner remoto), no del modelo, no del backend Lemonade/llama.cpp y no
     de un rechazo de la aprobación.
   - Un primer intento chocó con un límite de argumentos del sistema al
     transportar el runner comprimido vía el argumento del comando remoto
     (`E2BIG`/"Argument list too long"), antes de abrir ejecución alguna
     del runner o hacer preflight contra la API pública; no hubo mutación
     de Halo.
   - Un segundo intento preparó la transferencia de archivos temporales
     locales (diff real, solo local) sobre el ControlMaster autorizado
     (sin código en el argv del comando remoto), pero el comando remoto
     mínimo para crear un directorio privado de trabajo no devolvió en
     60 s y fue cancelado por el límite local; no
     se ejecutó ninguna transferencia SCP, no hubo petición HTTP alguna,
     y la creación de ese directorio remoto **no quedó confirmada** (no se
     afirma "ningún archivo creado" como hecho verificado; solo que la
     ejecución del ensayo no llegó a iniciarse ni a producir peticiones).
   - Puntos de prompt real a medir (una vez que el canal de transporte se
     resuelva y se repita bajo su propia aprobación): `8K`, `16K`, `32K` y
     hasta `~60K` tokens reales de entrada actual (contados con el
     tokenizer real, no caracteres), con un slot de `64K` de contexto
     configurado por perfil, salida SSE con un tope máximo configurado de
     `512` tokens (incluye cualquier token de razonamiento; no es un
     tamaño de salida exacto ni garantizado).
   - Perfil de control: `N1` (un slot), comparado contra `N2`/`N3` (dos y
     tres slots respectivamente, sin relación con el reparto de slots
     3+1 del baseline Coder+Thinking, que es una configuración distinta)
     para observar degradación de throughput bajo concurrencia con
     prompts largos reales
     (no solo los prompts cortos ya medidos en la matriz de esta sección).
   - Presupuesto de tiempo total aprobado: máximo **16 solicitudes** en
     total en una ventana de **60 minutos** (incluye las rondas de control
     y de comparación), más el tiempo de restauración final.
   - Métricas a capturar cuando se ejecute: TTFT (streaming; definido como
     el tiempo desde el envío de la petición hasta el primer delta de
     contenido real no vacío, separado de cualquier delta de razonamiento
     previo; los eventos de rol o los `ping` de mantenimiento de conexión
     no cuentan como ese primer delta y no se exige un `ping` previo como
     condición) y
     comportamiento de SSE mediante prompts de recuperación ("needles") y
     JSON con **contenido real** verificado, `finish_reason=stop` y
     `[DONE]` reales, sin aceptar un evento de rol como éxito. Este ensayo
     **no** exige el literal `READY` ni un umbral de retraso adicional
     como criterio propio: ese requisito (`READY` tras umbral) pertenece
     exclusivamente al contrato del probe histórico sintético
     `scripts/test-lemonade-sse.py`, no a este ensayo de contexto largo.
     También se captura calidad de contenido verificada, y memoria/GTT en
     frío (`cache_n=0`) y en caliente (`cache_n>0`) por separado.
   - Este ensayo, cuando se ejecute, **no** sería una prueba de operación
     continua 24x7: una validación de 24x7 real requeriría una prueba de
     tipo *soak* (sostenida, de larga duración: 2h, 8h y 24h evaluadas por
     separado) posterior, con su propia aprobación explícita, y no está
     certificada por este ensayo de contexto largo ni por la matriz ya
     ejecutada en este documento. Un candidato provisional para 24x7 sería
     2 slots balanceados basado únicamente en los perfiles cortos ya
     medidos y en la recomendación de 3 de concurrencia del baseline; el
     valor para contexto largo es provisional y no óptimo, y requiere
     antes TTFT real de prefill largo, relleno real de 64K,
     aislamiento/cancelación y soak de 2h/8h/24h evaluados por separado.
   - Ningún valor numérico de resultado se incluye aquí porque el ensayo
     no llegó a ejecutarse (0 peticiones): este punto documenta el estado
     de aprobación y bloqueo de transporte, no un resultado medido.

Ninguna de estas medidas está autorizada por este documento; requieren su
propia aprobación explícita siguiendo el flujo descrito en
[`estado-proyecto.md`](estado-proyecto.md) y la política operativa del
equipo.

## 8. Adenda 2026-09-16: comparación de offload Q4_K_M (`--cpu-moe` todo-CPU vs `--n-cpu-moe 40`)

**Esta es una línea de evidencia separada, posterior y solo aditiva.** No
revisa, reemplaza ni sustituye la matriz N1-N4 de la sección 3 (2026-09-15),
no cierra el HTTP 403 del 2026-09-04 ni el incidente SSE del 10 de
septiembre, y **no** es una comprobación de salud vigente en el momento de
la lectura. Tampoco pertenece a la tabla de Unsloth `UD-Q4_K_XL` ya
documentada en otras partes de esta línea (sección 5 y la
[guía de modelos](en/model-guide.md) en inglés): esta adenda trata sobre
una cuantización Q4_K_M distinta y ambas no deben mezclarse en una sola
tabla.

**Nota de identidad del modelo:** el modelo Q4_K_M residente de esta adenda
está publicado por **Bartowski** en el repositorio público de Hugging Face
[`bartowski/Qwen3.8-Flash-Next-GGUF`](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF),
ID de catálogo `Qwen3.8-Flash-Next-GGUF-Q4_K_M`, distinto de las variantes
Unsloth `UD-Q4_K_XL`/`UD-IQ4_XS` ya referenciadas en este documento. Esta
identidad de repositorio ya fue comprobada contra el catálogo público
vigente (no se requirió una nueva consulta independiente para este pase);
quien lea esto debería reverificar con su propia consulta de catálogo si
ha pasado tiempo antes de reutilizarlo.

### Qué se comparó

Ambos perfiles mantuvieron fija la configuración ya residente del modelo
salvo el flag de offload de MoE: `ctx_size 131072`, `parallel 2`, Vulkan,
`--no-kv-unified`, override de token-embedding por capa fijado a CPU
(`--override-tensor '^per_layer_token_embd[.]weight$=CPU'`), caché KV
`f16`, `--mmap`, `--spec-type none`. La única variable cambiada fue el
offload de capas expertas MoE:

- **`--cpu-moe` (base, "todo-CPU")**: todas las capas expertas MoE
  descargadas a CPU; este perfil ya estaba residente, así que no hubo
  recarga para él.
- **`--n-cpu-moe 40`**: mantiene los pesos MoE de las **primeras 40
  capas** fijados en CPU, dejando el resto elegible para GPU. Esto **no**
  es "40 capas en GPU"; es un parámetro de conteo de capas en CPU, y los
  dos flags nunca se combinaron en una misma carga.

### Resultados medidos (una ronda barrera válida de N=2 solicitudes concurrentes por perfil — no dos rondas por perfil — mismo prompt de 81 tokens)

| Perfil | Carga | Solicitudes | Tokens completion | Decode tok/s servidor | Wall cliente (s) | Wall ronda (s) | Wall agregado (s) | Contrato |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- |
| `--cpu-moe` (base) | ya residente, sin recarga | 2 | 75, 98 | 13.216, 14.233 (media 13.7245) | 12.547, 13.763 | 13.763 | 26.311 | 2/2 HTTP 200, `stop`, JSON exacto PASS |
| `--n-cpu-moe 40` | HTTP 200, **8.590 s** | 2 | 100, 98 | 13.987, 13.971 (media 13.979) | 11.122, 10.986 | 11.122 | 22.108 | 2/2 HTTP 200, `stop`, JSON exacto PASS |

- Media decode tok/s servidor: **+1.85%** para `n-cpu-moe 40` frente a la
  base (diferencia pequeña, no es el único criterio).
- Media latencia wall cliente: **-16.1%** para `n-cpu-moe 40` frente a la
  base (13.155 s -> 11.054 s).
- Una razón ingenua "tokens aceptados / wall de ronda" da 173/13.763 =
  **12.57 tok/s** para la base vs 198/11.122 = **17.80 tok/s** para
  `n-cpu-moe 40`. **Esto no es una afirmación limpia de +42% de velocidad
  de decode**: esa razón mezcla tiempo de prefill y cola con el decode, y
  los dos perfiles no produjeron el mismo número de tokens de completion
  (173 vs 198), por lo que las salidas no están emparejadas en longitud.
- Restauración: HTTP 200 en **6.640 s**, `restore_match_actual: true`
  contra health/`launch_command` en vivo (el campo `saved` del catálogo
  permaneció vacío `{}` durante todo el proceso y no se usó como fuente de
  verificación).

### Por qué esto no es una comparación causal limpia

- **Una descarga gestionada estuvo activa durante ambos perfiles**: una
  descarga de catálogo de `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS` (tres
  archivos GGUF, `93.682.584.224` bytes en total, ≈93,68 GB / ≈87,25 GiB)
  estaba en `status="downloading"`, `running=true` durante estas
  solicitudes y seguía sin terminar en la última consulta de estado
  (**2026-09-16T11:02:26Z**, aún corriendo; no hay una cifra de progreso
  en bytes posterior disponible en esta evidencia). Esta descarga es un
  factor de confusión real de I/O/caché para ambos perfiles; **no se
  afirma un speedup causal** para `n-cpu-moe 40`.
- **Los conteos de tokens de completion difieren** entre perfiles (75+98
  vs 100+98), por lo que no es una comparación de salida idéntica.
- **Una sola ronda por perfil** (N=2, una repetición) no establece
  robustez estadística; ambas rondas sí pasaron el contrato de contenido
  (4/4 solicitudes: `stop` real, contenido JSON/marcador exacto, sin
  truncamiento forzado).
- **Cuatro solicitudes anteriores del mismo día quedan excluidas de esta
  comparación**: un intento previo con tanto `--cpu-moe` como
  `--n-cpu-moe 40` usó un **tope de 32 tokens de completion** y ambos
  terminaron en `finish_reason=length` sin el marcador esperado. Es un
  **resultado inconcluso causado por el tope de tokens que forzó el
  truncamiento**, no evidencia de que alguno de los perfiles no sea
  soportado; por ese resultado inconcluso, el plan explícitamente no
  escaló a probar una variante `--n-cpu-moe 32` en esa misma sesión.
- **Un perfil `--n-cpu-moe 32` quedó sin ensayar**, no "32 solicitudes
  adicionales no ejecutadas": el plan preveía una ronda barrera válida
  más (4 solicitudes: 2 para una segunda ronda de base, 2 para un perfil
  candidato `--n-cpu-moe 32`), pero un fallo de transporte (SSH/
  ControlMaster) hacia el runner remoto ocurrió antes de poder enviar
  cualquiera de esas 4 solicitudes — **no** un rechazo del modelo o del
  backend, ni un hallazgo de causa raíz sobre los modelos mismos.
- **Total de solicitudes en todo este conjunto de evidencia: 12
  planificadas, 8 ejecutadas** (4 inconclusas por el tope de 32 tokens + 4
  válidas, reportadas arriba), con **4 solicitudes planificadas sin
  ejecutar** por el fallo de transporte anterior.

### Recursos (instantáneas puntuales, no un barrido continuo de guardas)

| Punto de control | MemAvailable (GiB) | GTT libre (GiB) |
| --- | ---: | ---: |
| Inicial (antes de ambos perfiles) | 111.27 | 52.64 |
| Durante `n-cpu-moe 40` | 98.08 | 39.43 |
| Final (tras restaurar) | 111.20 | 52.64 |

Son puntos de control discretos frente a una guarda configurada de 16 GiB
MemAvailable / 4 GiB GTT libre (ambas respetadas en cada punto muestreado);
esto **no** es un monitor continuo de "todo momento", y el número de
muestras/intervalo para un barrido completo de guardas en esta ventana no
está disponible en esta evidencia. No se infiere aquí la huella total de
memoria/GTT del GGUF completo ni el GTT adicional que la descarga IQ4_XS
en curso pudiera requerir eventualmente.

### La descarga UD-IQ4_XS: iniciada, no completada

Descargar `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS` bajo el nombre de
catálogo `user.Qwen3.8-Flash-Next-UD-IQ4_XS` es explícitamente una
**operación mutable de disco/red** (no una comprobación de solo lectura).
Se inició con aprobación humana como descarga gestionada
(`stream=true`, `subscribe=false`); **no** se cargó, y no se solicitó
ninguna otra cuantización ni artefacto MTP draft. Su estado real al
momento de esta adenda:

- Tamaño total: 3 archivos, **93.682.584.224 bytes** (≈93,68 GB /
  ≈87,25 GiB).
- Identidad pública de catálogo: `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS`,
  un identificador técnico de catálogo, no un dato privado/personal.
- Una muestra temprana mostró **368.148.732 bytes** (≈0,39%) descargados,
  en una marca de tiempo temprana no especificada; esto **no** es el
  último estado.
- En la última consulta de estado (**2026-09-16T11:02:26Z**), el trabajo
  seguía en `status="downloading"`, `running=true`; la última cifra de
  progreso en bytes no estaba disponible en esta evidencia porque un
  refresco de estado posterior quedó bloqueado por un fallo de transporte
  SSH.
- **No completada, sin verificación de hash, sin tamaño final confirmado.**
  No se borró ningún archivo parcial. No se intentó cargar `UD-IQ4_XS` ni
  ninguna otra cuantización.

### `--cpu-moe` como elección inicial, no como mandato de arquitectura

El perfil conservador `--cpu-moe` (offload MoE todo-CPU) usado antes en
esta línea de ensayos fue una elección inicial conservadora para una
primera prueba segura, no un requisito de arquitectura; `--n-cpu-moe N`
es un control de offload distinto y más fino (primeras `N` capas expertas
fijadas en CPU, el resto elegible para GPU) y ambos son alternativas, no
una combinación. Una futura A/B limpia queda explícitamente **pendiente**,
para ejecutarse solo después de que esta descarga IQ4_XS se complete (o
deje de estar activa) y solo bajo su propia aprobación separada; esta
adenda **no** autoriza esa continuación, no cambia la configuración de
backend/hilos ahora, y no es una afirmación 24x7 ni de rendimiento
sostenido.

### Qué NO afirma esta adenda

- **Ningún speedup causal para `n-cpu-moe 40`.** El menor wall de cliente
  observado y el decode tok/s ligeramente mayor están confundidos por la
  descarga IQ4_XS concurrente y por longitudes de salida no emparejadas.
- **Ninguna finalización de la descarga IQ4_XS**, sin verificación de
  hash/tamaño, sin carga de esa u otra cuantización.
- **Ningún cambio a `max_loaded_models`, pines más allá de lo ya
  establecido, red, CORS o configuración de servicio.**
- **Ninguna resolución del resultado inconcluso previo del tope de 32
  tokens**; eso sigue siendo un artefacto de runner/configuración (tope de
  tokens que fuerza truncamiento), no un hallazgo de soporte de modelo, y
  `--n-cpu-moe 32` deliberadamente no se probó en esa misma sesión.
- **Ninguna reapertura ni cierre del 403 del 2026-09-04 ni del incidente
  SSE del 10 de septiembre.**

### Nota 2026-09-16: intento posterior de barrido baseline / `--n-cpu-moe 32`/`24` NO ejecutado

Con posterioridad a la comparación anterior, se autorizó un intento
separado para buscar un máximo estable entre un perfil baseline (`--cpu-moe`)
y candidatos `--n-cpu-moe 32`/`24` sobre el mismo Q4_K_M residente. **Este
intento no se ejecutó**: el paso previo de comprobación de canal de
comandos hacia el host remoto no dio un resultado fiable — el transporte
usado mostró un comportamiento intermitente (a veces respuesta inmediata,
a veces cuelgue indefinido sin salida, con el mismo comando y el mismo
entorno), lo cual se trata aquí como **timeouts/intermitencia de la
herramienta de transporte usada**, no como una causa raíz atribuida a la
red del host, al proceso maestro remoto ni al servidor Lemonade/backend.

En consecuencia:

- **Cero peticiones de inferencia** se enviaron para baseline, `32` ni
  `24` (ni para ningún refinamiento `20`/`16` previsto).
- **Ningún cambio de modelo, pin, argumento activo ni `saved`** se
  realizó; no hubo carga ni descarga de ningún modelo.
- **Ninguna restauración fue necesaria**, porque no hubo mutación alguna
  sobre el host.
- **No se pudo verificar el estado de la descarga UD-IQ4_XS ni la salud
  actual del host** en este intento; la última cifra conocida sigue
  siendo la ya registrada arriba (**2026-09-16T11:02:26Z**,
  `status="downloading"`, `running=true`), citada como última
  observación disponible, **no** como estado vigente confirmado ahora.

Este intento no invalida ni confirma nada sobre los perfiles `--cpu-moe`,
`--n-cpu-moe 40`, `32`, `24`, `20` o `16`; los resultados de la comparación
`--cpu-moe` vs `--n-cpu-moe 40` documentados arriba (media decode
+1.85%, confundida por la descarga IQ4_XS concurrente) siguen siendo la
última observación de rendimiento disponible sobre este offload, no un
nuevo estado ni un máximo estable encontrado. No se reabre la matriz N1-N4
de la sección 3, ni el 403 del 2026-09-04, ni el incidente SSE del 10 de
septiembre.

### Nota 2026-09-16T12:42:05Z–12:44:03Z (~118 s): barrido baseline / `--n-cpu-moe 32`/`24` EJECUTADO CON ÉXITO

**Esta subsección es posterior y solo aditiva respecto a la nota anterior
("intento posterior... NO ejecutado").** No la reemplaza ni la borra: esa
nota documenta un intento previo bloqueado por un fallo de transporte
distinto y fechado; esta subsección documenta un **segundo intento**, en
una ventana posterior, que sí se completó. Ambas notas coexisten como
evidencia fechada independiente.

En esta ventana (**2026-09-16T12:42:05Z–12:44:03Z**, ~118 s de mutación
real, muy por debajo del presupuesto autorizado) se ejecutaron **6/6
solicitudes reales** (2 por perfil × 3 perfiles: control `--cpu-moe`,
`--n-cpu-moe 32`, `--n-cpu-moe 24`) sobre el mismo Q4_K_M residente de
Bartowski, con `ctx_size=131072`, `--parallel 2`, `--no-kv-unified`,
override de token-embedding por capa en CPU, caché KV `f16`, `--mmap`,
`--spec-type none` fijos en los tres perfiles; la única variable cambiada
fue el flag de offload MoE (todo-CPU vs primeras `N` capas fijadas en CPU),
sin combinar nunca ambos flags en una misma carga. No se probaron
variantes `16`/`20` en esta ventana.

**Resultados (una ronda barrera de N=2 solicitudes concurrentes por
perfil, mismos dos prompts sintéticos fijos: JSON exacto y palabra
`READY`):**

| Perfil | Recarga | Tokens prompt | Tokens completion | Decode tok/s servidor (min–max) | Wall cliente (s, min–max) | Wall de ronda (s) | `cache_n` |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| control (`--cpu-moe`) | ya residente, sin recarga | 88, 83 | 64, 223 | 11.03 – 14.87 | 14.503 – 23.722 | 23.723 | 0, 0 |
| `--n-cpu-moe 32` | HTTP 200 en 6.559 s | 88, 83 | 61, 223 | 13.08 – 15.56 | 13.458 – 22.424 | 22.424 | 0, 0 |
| `--n-cpu-moe 24` | HTTP 200 en 15.436 s | 88, 83 | 61, 280 | 11.36 – 15.69 | 14.556 – 27.052 | 27.053 | 0, 0 |

Todas las seis solicitudes terminaron en `finish_reason=stop` real, con
contenido exacto verificado (JSON `{"sum":4}` y `READY`, sin
truncamiento), 6/6 PASS de contrato. `cache_n=0` en las seis indica caché
KV fría por solicitud/perfil (cada recarga reinicia el estado del
backend); esto **no** es una garantía de caché de archivo/RAM fría a nivel
de sistema operativo, y ninguna solicitud `N=1` aislada se ensayó aquí
para separar ese efecto.

Throughput agregado por ronda (suma de `completion_tokens` dividida entre
el wall de ronda; no es un promedio de razones por solicitud, que
mezclaría prefill/cola con decode de forma distinta por solicitud):

- control: (64+223)/23.723 = **12.10 tok/s**
- `n-cpu-moe 32`: (61+223)/22.424 = **12.67 tok/s**
- `n-cpu-moe 24`: (61+280)/27.053 = **12.60 tok/s**

**Interpretación explícitamente acotada:** con una sola ronda de 2
solicitudes por perfil, los tres valores agregados (~12.1–12.7 tok/s)
quedan dentro de un margen de ruido similar entre sí; esto **no**
establece un "perfil ganador" estadísticamente robusto, ni valida
contexto lleno de 131072 tokens (los prompts reales fueron 83 y 88
tokens), ni un "máximo estable" de offload. Ambos candidatos (`32` y `24`)
fueron aceptados por el servidor (`launch_command` efectivo verificado
tras cada carga contiene literalmente `--n-cpu-moe 32`/`--n-cpu-moe 24`,
sin `--cpu-moe`, y sin rechazo del servidor en ningún momento), pero eso
solo confirma aceptación del flag, no una ganancia de rendimiento
demostrada frente al control en esta muestra puntual.

**Puntos de control de memoria/GTT (instantáneas discretas, no un barrido
continuo):**

| Punto | MemAvailable (GiB) | GTT libre (GiB) | Guarda (Mem≥16 / GTT≥4) |
| --- | ---: | ---: | --- |
| Inicial | 111.33 | 52.64 | cumple |
| Tras ronda control | 110.85 | 52.62 | cumple |
| Tras ronda `n-cpu-moe 32` | 85.31 | 27.12 | cumple |
| Tras ronda `n-cpu-moe 24` | 73.44 | 15.13 | cumple |

El punto más ajustado observado (`n-cpu-moe 24`, 15.13 GiB GTT libre) pasó
la ronda corta ensayada sin disparar guarda, pero esto **no** demuestra
beneficio estadístico frente a `32` ni establece cuál perfil es "ganador":
con una sola ronda por perfil no hay robustez estadística, y no se validó
contexto lleno ni un objetivo de 30 tok/s.

**Restauración:** al finalizar, se liberó el modelo y se recargó el
perfil original (`--cpu-moe`, `ctx_size=131072`, `--parallel 2`, resto de
flags idénticos, `pinned=true` preservado), con HTTP 200 en **14.255 s**;
el `launch_command` efectivo tras restaurar coincidió exactamente con el
del snapshot previo a la mutación (mismo binario, mismo `.gguf`, mismo
`mmproj`, mismos flags). El campo `saved` del catálogo permaneció vacío
durante todo el proceso y no se usó como fuente de verificación; esta
subsección no formula ninguna afirmación nueva sobre ese campo más allá de
que no se usó.

**Descarga `UD-IQ4_XS`:** `GET /api/v1/downloads` devolvió lista vacía en
el momento de esta consulta puntual. **Esto no demuestra que la descarga
esté completa, fallida ni cancelada**; solo que en ese instante concreto
no había trabajos activos reportados por ese endpoint. No se cargó ni se
verificó por hash/tamaño ninguna cuantización `IQ4_XS` u otra; el estado
público de descarga previamente registrado (última cifra conocida
**2026-09-16T11:02:26Z**, `status="downloading"`, `running=true`) no se
actualiza ni se revierte por esta consulta vacía puntual.

**Qué NO afirma esta subsección:**

- No hay perfil "ganador" estadísticamente robusto entre `--cpu-moe`,
  `--n-cpu-moe 32` y `--n-cpu-moe 24`; una ronda de N=2 por perfil no basta.
- No se validó contexto lleno de 131072 tokens de entrada real, ni un
  objetivo de 30 tok/s.
- No se tocó ningún otro modelo, driver ni servicio; no hubo cambio de
  `max_loaded_models`, red, CORS ni configuración de servicio; no se
  promovió ningún candidato automáticamente a configuración por defecto.
- No se confirma ni se descarta la finalización de la descarga
  `UD-IQ4_XS`.
- No reabre la matriz N1-N4 de la sección 3, ni el 403 del 2026-09-04, ni
  el incidente SSE del 10 de septiembre.
- No es una afirmación de salud actual del host más allá del momento de
  esta ventana fechada (2026-09-16T12:42:05Z–12:44:03Z).

## Fuentes y procedencia técnica

- Artefactos de medición de la corrida del 2026-09-15: `result.json`,
  `summary.json` y `checkpoint.json` del runner (técnicos, ya
  sanitizados; no incluyen host/IP/credenciales reales).
- Inspección de código fuente de `llama.cpp` en GitHub:
  [`src/models/qwen4exp.cpp` en `010be9683`](https://github.com/ggml-org/llama.cpp/blob/010be9683afabe14ce299197b38c329f94bae568/src/models/qwen4exp.cpp),
  PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742) (soporte
  base, fusionado 2026-08-27), PR
  [#27941](https://github.com/ggml-org/llama.cpp/pull/27941) (correcciones,
  no incluidas en el build vivo verificado).
- Registro operativo sanitizado de autorización y captura previa (sin
  rutas de archivo ni referencias de nombres de archivo privadas; no se
  reproduce ningún dato privado, host, IP, usuario, socket ni ruta de
  sesión).
- [Comparativa de modelos](comparativa-qwen38-halo-strix.md) y
  [guía de modelos en inglés](en/model-guide.md), sección
  Qwen3.8-Flash-Next, para el contexto previo bloqueado por
  incompatibilidad de arquitectura en el build antiguo `b10375`.

Ningún artefacto privado (rutas de sesión, sockets, host/IP real,
credenciales) se reproduce en este documento. Todos los números citados
son técnicos y ya estaban sanitizados en el origen consultado.
