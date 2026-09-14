# Comparativa Qwen3.8 en Halo Strix — 2026-09-04

> **English:** [operational guide](en/model-guide.md) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

> Documento de consolidación (equipo tecnico). Reúne la investigación y las
> parametrizaciones ya validadas sobre los modelos Qwen desplegados o
> evaluados en el host Halo Strix, sin contradecir
> `docs/validacion-lemonade-vulkan.md`, `docs/plan-configuracion-halo-strix.md`
> ni `docs/validacion-entrenamiento-rocm.md`. Cada afirmación va etiquetada
> **HECHO** (medido/observado con evidencia directa), **ESTIMACIÓN**
> (fuente externa razonable, no medido en este host) o **POC** (plan de
> prueba propuesto, no ejecutado).

## 1. Resumen ejecutivo y recomendación

- **Mantener como baseline recomendado en la fecha del informe** el par
  **Qwen3-Coder-30B-A3B-Instruct**
  (rol coding, non-thinking) + **Qwen3-30B-A3B-Thinking-2507** (rol
  razonamiento, always-thinking) cargados simultáneamente bajo
  `max_loaded_models=2`. Es la única combinación con evidencia de servicio
  estable, tamaños de contexto grandes y consumo de GTT medido con margen
  sobre el límite físico. **HECHO**.
- **Qwen3.8-27B (`unsloth/Qwen3.8-27B-GGUF`, `UD-Q4_K_XL`)** es el candidato
  de **POC** más razonable como sustituto potencial de Thinking-2507: es un
  modelo denso 27B, multimodal, con thinking configurable, ya descargado
  íntegro en el host (17.22 GiB); este informe posterior lo describió como
  **no cargado en la evidencia que consultó**, pero otra fuente histórica
  registra una carga. La contradicción permanece abierta. No sustituye a
  Coder ni debe cargarse junto a los dos modelos actuales en esta fase.
  **POC, no ejecutado**.
- **Qwen3.8-Flash-Next (`unsloth/Qwen3.8-Flash-Next-GGUF`, `UD-Q4_K_XL`)**
  queda **exclusivamente en fase futura/experimental**. Es incompatible con
  el backend administrado actual (arquitectura GGUF `qwen4exp` desconocida
  para `b10375`), pesa 104.53 GiB (no cabe en los 61.73 GiB de GTT
  disponibles) y su soporte upstream en llama.cpp sigue evolucionando. No se
  planifica para producción ni para el siguiente ciclo de POC. **HECHO
  (bloqueo) / POC futura**.

## 2. Hardware y stack medidos

| Elemento | Valor | Estado |
| --- | --- | --- |
| Equipo | GMKtec EVO-X2 (SKU `EVO-X2-001`, firmware `EVO-X2S 1.13`) | HECHO |
| APU/iGPU | AMD Ryzen AI Max+ 395 w/ Radeon 8060S, destino `gfx1151` (RDNA 3.5 Strix Halo) | HECHO |
| Memoria | 128 GiB UMA (`Range Size: 128 GiB` ×8 en DMI) | HECHO |
| GTT total | `mem_info_gtt_total = 66,283,167,744 B` ≈ **61.73 GiB** | HECHO |
| VRAM dedicada | `mem_info_vram_total = 2,147,483,648 B` ≈ 2.0 GiB | HECHO |
| Lemonade Server | `11.8.1` (paquete `/usr/bin/lemonade`), sucesor auditado de `11.7.0` | HECHO |
| Backend llama.cpp gestionado | Vulkan, binario administrado `version: 10375 (ba360efe1)`, fecha de build `2026-08-12` | HECHO |
| `max_loaded_models` | `2` (elevado desde el default `1`) | HECHO |
| systemd user linger | Habilitado en el host para sostener `lemond.service` sin sesión de login activa. Esto **actualiza** el estado histórico `Linger=no` registrado en `docs/validacion-lemonade-vulkan.md` y `docs/auditoria-ssh-inicial.md` (gate 2026-08-25); se **reconfirmó en una nueva conexión SSH** independiente: `loginctl show-user -p Linger` devolvió `Linger=yes`, `lemond.service` activo, el listener LAN (`<HALO_HOST>:13305`) presente y `GET /api/v1/health` respondió HTTP 200 | HECHO |

El listener HTTP de Lemonade en este host es exclusivamente LAN:

```text
LISTEN 0 128 <HALO_HOST>:13305   users:(("lemond",pid=1215,fd=12))
LISTEN 0 4096 <HALO_HOST>:9000   users:(("lemond",pid=1215,fd=10))
LISTEN 0 512  127.0.0.1:8001       users:(("llama-server",pid=1600,fd=4))  # Coder
LISTEN 0 512  127.0.0.1:8002       users:(("llama-server",pid=1696,fd=4))  # Thinking
```

No existe listener `127.0.0.1:13305`: solo los hijos `llama-server` (Coder,
Thinking) escuchan en loopback, en sus puertos internos 8001/8002. **HECHO.**

## 3. Estado histórico observado de modelos simultáneos (2026-09-04)

### 3.1 Qwen3-Coder-30B-A3B-Instruct (Q4_K_M)

```bash
$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server \
  -m $HOME/ai/lemonade/models/models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF/snapshots/b17cb02dd882d5b6ab62fc777ad2995f19668350/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf \
  --ctx-size 196608 --port 8001 --jinja --metrics \
  --parallel 3 --kv-unified --flash-attn on --cache-reuse 256 \
  --cache-type-k q8_0 --cache-type-v q8_0
```

- Contexto: 196,608 tokens es el **pool KV total** (`--kv-unified`),
  compartido dinámicamente entre los 3 slots (`--parallel 3`); **no** son
  196,608 tokens por slot. Con las tres peticiones activas simultáneamente,
  la capacidad efectiva aproximada por petición es **~65,536 tokens**
  (196,608 ÷ 3), aunque el reparto real es dinámico y no una partición fija
  en bloques iguales.
- KV cache cuantizado Q8 en K y V.
- **Non-thinking** por diseño del modelo (familia `Qwen3-Coder`, sin tags
  `<think>` en su plantilla oficial); `--reasoning-format auto` es el
  **default** de este binario `llama-server` y no fuerza razonamiento (ver
  §5).
- Tamaño en disco del GGUF: 18,556,689,568 bytes ≈ 17.28 GiB.

### 3.2 Qwen3-30B-A3B-Thinking-2507 (Q4_K_M)

```bash
$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server \
  -m $HOME/ai/lemonade/models/models--unsloth--Qwen3-30B-A3B-Thinking-2507-GGUF/snapshots/a9b37aaac12b2bd0098783a443429543dd76a14d/Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf \
  --ctx-size 98304 --port 8002 --jinja --metrics \
  --parallel 1 --kv-unified --flash-attn on \
  --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384
```

- Contexto: 98,304 tokens, KV unificado, **1 slot**.
- KV cache Q8 K/V, presupuesto de razonamiento 16,384 tokens
  (`--reasoning-budget`).
- **Always-thinking**: la familia `Thinking-2507` siempre emite bloque de
  razonamiento; no es configurable por request como en Qwen3.8.

### 3.3 GTT/VRAM medidos con ambos modelos residentes

| Proceso | PID | Puerto | GTT medido | Notas |
| --- | --- | --- | --- | --- |
| Coder Q4_K_M | 1600 | 8001 | **25.62 GiB** | ctx 196608, parallel 3 |
| Thinking-2507 Q4_K_M | 1696 | 8002 | **22.40 GiB** | ctx 98304, parallel 1 |
| **Total GTT usado** | — | — | **48.02 GiB** de 61.73 GiB (≈77.8 %) | `mem_info_gtt_used = 51,557,068,800 B` = 48.02 GiB, coincide exactamente con la suma por proceso |
| VRAM dedicada | — | — | ≈1.9 de 2.0 GiB | `mem_info_vram_used = 2,043,170,816 B` |

Ambos procesos aparecen con `pinned:false` en `/api/v1/health`
(`pinned_models.llm = 0`). Este es el dato relevante como evidencia de
Coder/Thinking; `pinned_helper_models.llm` pertenece a otro *pool*
(modelos auxiliares/helper, no Coder ni Thinking) y no debe citarse como
evidencia de estos dos procesos. **No hay evidencia de que Coder o
Thinking estén pinneados**; no debe afirmarse lo contrario sin una nueva
comprobación de `/internal/config` o `/api/v1/health`. **HECHO.**

## 4. Configuración de `max_loaded_models=2` y CLI vs API

El CLI oficial (`lemonade ... config set max_loaded_models=2`) **no
alcanza al servidor en este host**, porque el cliente por defecto se
conecta a `127.0.0.1:13305` y `lemond` sólo escucha en
`<HALO_HOST>:13305` (§2). El intento documentado terminó así:

```text
$ lemonade config set max_loaded_models=2
Error setting config: Could not connect to Lemonade server (Could not establish connection).
Make sure the server is running and try again.
```

La configuración se aplicó correctamente contra el endpoint interno
`/internal/set`, en la misma LAN autorizada:

```text
curl -sS -X POST http://<HALO_HOST>:13305/internal/set \
  -H 'Content-Type: application/json' \
  --data '{"max_loaded_models":2}'
# -> {"status":"success","updated":{"max_loaded_models":2}}
```

Verificación posterior (nueva conexión, 8 s después, sin reiniciar
`lemond`):

- `GET /internal/config` → `max_loaded_models = 2`.
- `GET /api/v1/health` → `max_models.llm = 2`, `status:"ok"`.
- `config.json` (línea 41) → `"max_loaded_models": 2,`.

No se necesitó reiniciar `lemond.service`; el cambio es en caliente. La
persistencia se confirmó en disco (no fue sólo estado en memoria). **HECHO.**

Para cargar cada modelo con las opciones descritas en §3 desde la UI o vía
API, el patrón es:

```text
curl -sS -X POST http://<HALO_HOST>:13305/api/v1/load \
  -H 'Content-Type: application/json' \
  --data '{
    "model_name": "Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M",
    "ctx_size": 196608,
    "llamacpp_backend": "vulkan",
    "llamacpp_args": "--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0",
    "merge_args": true,
    "save_options": true
  }'
```

> **Aviso de nombre exacto:** `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`
> corresponde en este host al registro de usuario `user.*` ya existente en
> el catálogo (`user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`), **no** al
> ID base/built-in `Qwen3-Coder-30B-A3B-Instruct-GGUF`. Ambos IDs coexisten
> sin alias para el mismo repo/artefacto. **No sustituir este `model_name`
> por el ID base sin antes consultar el catálogo** (`GET /v1/models` o
> Model Manager), por la colisión de IDs documentada en
> `docs/validacion-lemonade-vulkan.md` (registro base vs registro de
> usuario, mismo repo/namespace compartido).

```text
curl -sS -X POST http://<HALO_HOST>:13305/api/v1/load \
  -H 'Content-Type: application/json' \
  --data '{
    "model_name": "Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M",
    "ctx_size": 98304,
    "llamacpp_backend": "vulkan",
    "llamacpp_args": "--parallel 1 --kv-unified --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384",
    "merge_args": true,
    "save_options": true
  }'
```

No se incluyen credenciales ni cabeceras de autenticación porque esta LAN
no las requiere (riesgo aceptado y documentado en
`docs/auditoria-ssh-inicial.md`). **HECHO.**

## 5. `--reasoning-format auto`: qué hace y qué no hace

`--reasoning-format` es un **parser/formateador de salida**, no un
interruptor de modo de razonamiento. Según la ayuda oficial del binario
administrado (`llama-server --help-all`, backend `b10375`):

```text
--reasoning-format FORMAT   controls whether thought tags are allowed and/or
                             extracted from the response, and in which
                             format they're returned:
                             - none: deja el pensamiento sin parsear en message.content
                             - deepseek: pone el pensamiento en message.reasoning_content
                             - deepseek-legacy: conserva <think> en content y también
                               rellena reasoning_content
                             (default: auto)
```

`auto` **ya es el valor por defecto** de este binario; no hace falta
pasarlo explícitamente y, aunque se pase, **no activa razonamiento en un
modelo non-thinking ni lo desactiva en uno always-thinking**. Es
puramente cómo se extrae/etiqueta el bloque `<think>` si el modelo lo
produce:

- **Coder** es oficialmente **non-thinking**: su plantilla no emite
  `<think>`, así que `--reasoning-format auto` no tiene efecto observable.
- **Thinking-2507** es **always-thinking**: siempre emite razonamiento;
  `--reasoning-format auto` sólo decide cómo se reporta ese bloque en el
  JSON de respuesta (`reasoning_content` vs `content`), no si se genera.

### Recomendaciones para agentes OpenCode que consumen este endpoint

- Configurar `steps` del agente en **≥50 o sin límite superior explícito**
  para tareas agenticas largas (PR completo, refactor multi-archivo). El
  campo `steps` es oficial en `AgentConfig` (frontmatter de agente OpenCode)
  y, al alcanzarlo, OpenCode retira las herramientas y pide un resumen en
  texto; no es un límite de tokens.
- Definir el criterio de terminación de la tarea por evento observable
  (por ejemplo, aparición de una **URL de PR** en la respuesta o en la
  salida de una herramienta `git`/`gh`), no por conteo de turnos.
- Observar `finish_reason` (`stop`, `length`, `tool_calls`) y el número de
  `tool_calls` por turno como señales de progreso/atasco, en vez de
  inferir estado del agente sólo por el texto.
- **No afirmar que `max_tokens` es un campo de `AgentConfig`.** La
  documentación pública de OpenCode no respalda `max_tokens` a nivel de
  agente; el control de tokens de salida que sí existe se aplica a nivel de
  proveedor/modelo (por ejemplo `budgetTokens` dentro de las opciones
  `thinking` de un modelo concreto en `opencode.json`), no como campo de
  `AgentConfig`. Ver fuentes en §11.

## 6. Qwen3.8-27B — candidato de POC para sustituir Thinking

| Campo | Valor |
| --- | --- |
| Repo / variante | `unsloth/Qwen3.8-27B-GGUF`, `UD-Q4_K_XL` |
| Snapshot | `4ca720788d1e01f1bff70c033e0d0028fd02e502` |
| Arquitectura GGUF | `qwen35` (v3, 65 bloques, 866 tensores) |
| Arquitectura HF | `Qwen3_5ForConditionalGeneration` (`model_type: qwen3_5`) |
| Tipo | Denso 27B, capa MTP adicional (`nextn_predict_layers=1`, 64+1 capas) |
| Multimodal | Sí: `mmproj-BF16.gguf` (`clip.projector_type=qwen3vl_merger`), visión nativa imagen/vídeo |
| Thinking | Configurable por request (`enable_thinking`, `reasoning_effort`, `preserve_thinking` en la plantilla oficial); no siempre-on como Thinking-2507 |
| Tools | Sí (`tool_call` presente en la plantilla Jinja, 29 ocurrencias) |
| Contexto | 262,144 nativo, extensible a 1M (YaRN) |
| Tamaño en disco | 17,559,178,144 B (16.35 GiB) pesos + 931,146,432 B (0.87 GiB) mmproj = **17.22 GiB** total |
| Estado de carga | Este informe no encontró una carga en el journal consultado; otra fuente histórica sí registra una. **Contradicción abierta**, no “nunca cargado” absoluto. |

### Beneficios hipotéticos frente al par del baseline

- Un único proceso multimodal (visión + texto + tools) podría cubrir el
  rol de Thinking y parte del rol de asistencia general, con contexto
  nativo mucho mayor (262K vs 98,304 de Thinking-2507).
- Thinking configurable por request reduce el coste de razonamiento en
  tareas donde no se necesita.

### Limitaciones y riesgos

- **No hay benchmark directo publicado que compare Qwen3.8-27B contra
  Qwen3-30B-A3B-Thinking-2507 ni contra Qwen3-Coder-30B-A3B-Instruct** en
  ninguna fuente consultada; sólo existen benchmarks oficiales de Unsloth/
  Qwen contra Qwen3.8-Flash-Next, Qwen3.7-Plus, DeepSeek-V4-Flash y
  Claude-Opus-4.6 (§7, tabla oficial). No se debe presentar una cifra de
  "mejora" frente a los modelos actuales sin medirla en este host.
  **ESTIMACIÓN de aptitud, no de rendimiento comparado.**
- **Riesgo llama.cpp issue [#27431](https://github.com/ggml-org/llama.cpp/issues/27431)**
  (abierto, sin confirmar, creado 2026-08-20): *"llama-cli and llama-server
  both crash when running `unsloth/Qwen3.8-27B-UD-Q4_K_M.gguf` on Vulkan
  (AMD R9700) on Windows"*. El crash ocurre tras completar el prefill de un
  prompt largo (~99.8 % de progreso), en una tarjeta AMD discreta distinta
  (2×Radeon AI PRO R9700, no Strix Halo), con `--flash-attn auto
  --cache-type-k q8_0 --cache-type-v q8_0`, la misma familia de
  cuantización dinámica Unsloth (capas `IQ4_XS`, presentes también en
  nuestro `UD-Q4_K_XL`: 70 tensores `IQ4_XS` en el histograma). No hay
  confirmación de que el mismo crash ocurra en Vulkan/RADV sobre `gfx1151`,
  pero el patrón (Vulkan + AMD + prompt largo + capas Unsloth Dynamic) es
  suficientemente cercano para tratarlo como riesgo real antes del POC.
- **PR relacionada [#28102](https://github.com/ggml-org/llama.cpp/pull/28102)**,
  *"CUDA/HIP: Flash Attention tuning (gfx1201)"* (abierta, asignada,
  2026-08-31): ajustes de *flash-attention* para el backend CUDA/HIP en
  `gfx1201` (RDNA4 discreta), **no** para Vulkan ni para `gfx1151`. Se
  referencia como evidencia de que el trabajo de estabilización de
  flash-attention en tarjetas AMD sigue activo en llama.cpp, pero **no es
  una corrección directa aplicable a nuestro backend Vulkan/Strix Halo**;
  no debe citarse como solución al riesgo de #27431.
- La arquitectura `qwen35` ya era soportada por llama.cpp **antes** de
  `b10375` (a diferencia de `qwen4exp`, ver §7), así que la carga en sí no
  debería fallar por "arquitectura desconocida". El riesgo es específico de
  la combinación Vulkan/AMD/prompt largo con esta cuantización, y exige POC
  antes de promoción a producción.

### POC propuesta (no ejecutada)

1. **Sustituir temporalmente sólo Thinking-2507** (no tocar Coder mientras
   dure la prueba); mantener `max_loaded_models=2` sin cargar ambos modelos
   nuevos a la vez.
2. **Descargar explícitamente Thinking-2507 antes de cargar Qwen3.8-27B**,
   usando el nombre exacto ya documentado en §3.2
   (`Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M`) y el endpoint
   `/api/v1/unload` (no `/api/v1/delete`, que borraría el modelo de disco):

   ```text
   curl -sS -X POST http://<HALO_HOST>:13305/api/v1/unload \
     -H 'Content-Type: application/json' \
     --data '{"model_name": "Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M"}'
   ```

3. Carga con **1 slot**, contexto 32,768, backend Vulkan:

   ```text
   curl -sS -X POST http://<HALO_HOST>:13305/api/v1/load \
     -H 'Content-Type: application/json' \
     --data '{
       "model_name": "Qwen3.8-27B-GGUF-UD-Q4_K_XL",
       "ctx_size": 32768,
       "llamacpp_backend": "vulkan",
       "llamacpp_args": "--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384",
       "merge_args": true,
       "save_options": false
     }'
   ```

4. Casos de prueba, en este orden, con medición de memoria (GTT/VRAM),
   tok/s de prompt y generación, y errores/`device lost`:
   - Prompt corto (~2K tokens).
   - Prompt medio (~8K tokens).
   - Prompt largo (~32K tokens, el límite de contexto de esta POC) — este
     es el escenario que reproduce el patrón de #27431; abortar y
     restaurar Thinking-2507 ante cualquier crash o `device lost`.
   - Tool calling (al menos un ciclo function-call → tool-result → respuesta).
   - Entrada de visión (imagen simple vía `mmproj-BF16.gguf`).
   - Un PR end-to-end representativo del uso real con OpenCode (criterio de
     éxito: aparición de URL de PR, sin errores HTTP 5xx).
5. Sólo declarar el POC como PASS si las seis pruebas completan sin OOM,
   sin `device lost` y con calidad de salida verificada manualmente (no
   sólo tok/s). Cualquier fallo → rollback inmediato (§10).

## 7. Qwen3.8-Flash-Next — sólo futuro/experimental

| Campo | Valor |
| --- | --- |
| Repo / snapshot | `unsloth/Qwen3.8-Flash-Next-GGUF` @ `178b998806b7b406c311a3e6174aa99cf6304eaf` |
| Variante | `UD-Q4_K_XL`, 4 shards + `mmproj-BF16.gguf` |
| Tamaño en disco | 4 shards = 103.68 GiB + mmproj 0.845 GiB = **104.53 GiB** |
| Arquitectura GGUF | `qwen4exp` (v3, `512x56B`, 48 bloques) |
| Parámetros | 125B principales / **6B activos** por token, + 51B de *n-gram embedding*, + 4B MTP |
| Expertos | 512 totales, 10 *routed* + 1 *shared* activos por token |
| Mecanismos propios | Gated DeltaNet + Qwen Sparse Attention (QSA), *Gated Residual*, PLE (*n-gram embedding* con `heads_per_ngram=8`, `ngram_size=3`) |
| Multimodal | Sí (mmproj compartido con la familia Qwen3.8) |
| Thinking | Seleccionable por request (igual que Qwen3.8-27B) |
| Tools | Sí (misma plantilla Jinja con `tool_call`) |
| Contexto | 262,144 nativo, extensible a 1M |
| Estado de carga | **Bloqueado**: `llama_model_load: error loading model: unknown model architecture: 'qwen4exp'` en el binario administrado `b10375` |

### Beneficios frente a Qwen3.8-27B (benchmarks oficiales Qwen/Unsloth)

Tabla oficial de benchmarks del model card (idéntica en HF y en la guía de
Unsloth), columnas relevantes:

| Benchmark | Qwen3.8-Flash-Next | Qwen3.8-27B |
| --- | --- | --- |
| Toolathlon Verified (Pass@1) | **73.5** | 67.1 |
| SWE-bench Pro (harness Claude Code) | **62.5** | 61.7 |
| Multilingual software engineering | **81.0** | 73.8 |
| DeepSWE 1.1 (mejor de dos harnesses) | **58.7** | 42.2 |

**Disclaimer obligatorio:** estas cifras comparan Flash-Next contra
Qwen3.8-27B **según el propio proveedor**; no existe ninguna comparación
oficial ni medida en este host contra Qwen3-Coder-30B-A3B-Instruct ni
contra Qwen3-30B-A3B-Thinking-2507. No debe inferirse una mejora
equivalente frente al par en producción. **ESTIMACIÓN (fuente oficial
Unsloth/Qwen), no verificado localmente.**

### Bloqueos técnicos

- Nuestro binario administrado `b10375` (2026-08-12) es **anterior** a
  todo el trabajo de soporte de `qwen4exp`.
- **PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742)**,
  *"model: add Qwen3.8-Flash-Next (qwen4exp)"* (Unsloth/danielhanchen):
  añade el soporte base de la arquitectura. Es la PR que falta por completo
  en `b10375`.
- **PR [#27941](https://github.com/ggml-org/llama.cpp/pull/27941)**,
  *"qwen4exp: follow up fixes"* (mismo autor, **fusionada 2026-09-01**):
  corrige errores críticos posteriores al soporte base — claves del
  indexador perdidas al copiar secuencias, bloques de KV mal indexados bajo
  `--kv-unified`, corrupción de bloques de imagen bajo M-RoPE, aborts por
  metadatos malformados, y un abort de CUDA en contexto largo
  (`n_kv=262144` excede el límite `gridDim.y` de 65535). Cualquier build
  usado para Flash-Next debe ser **posterior** a esta fusión; nuestro
  `b10375` es muy anterior (agosto 12 vs fusión el 1 de septiembre).
- No cabe en GTT: 104.53 GiB de modelo frente a 61.73 GiB de GTT total.
  Sólo es viable con *offload* parcial CPU/GPU o *split* en solitario, sin
  ningún otro modelo residente.
- **Rendimiento comunitario en Strix Halo (no oficial, no verificado por
  este equipo)**: reportes de terceros (por ejemplo el repositorio público
  `drluoto/flash-next-strix-halo`, descrito por su propio autor como *"17
  → 47 tok/s"*) sitúan el rendimiento **sin** *speculative decoding* en
  torno a **17–21 tok/s**, y **con** forks experimentales que añaden MTP
  nativo y parches ROCm específicos en **24–47 tok/s**. Estas cifras usan
  **ROCm**, no Vulkan, y builds de llama.cpp con parches no oficiales; se
  citan únicamente como referencia de rango, **claramente etiquetadas como
  ESTIMACIÓN/comunidad, no reproducidas en este host**.

### POC futura (no antes de tener un build con #27941 fusionada)

1. Obtener/compilar un build de llama.cpp posterior a la fusión de #27941
   (2026-09-01), con soporte Vulkan para `gfx1151`; validar `--version` y
   la ausencia del error `unknown model architecture: 'qwen4exp'` antes de
   cualquier otra prueba.
2. Entorno **aislado** (no el `lemond` de producción, o una instancia con
   `max_loaded_models=1` dedicada), para no arriesgar Coder/Thinking.
3. 1 slot, contexto 16K–32K inicial (no 262K), **sin** `--kv-unified` en el
   primer intento (para descartar interacciones con el bug de bloques KV
   corregido en #27941 antes de habilitarlo).
4. Medir: memoria real (GTT/VRAM, *offload* CPU si aplica), corrección de
   salida (no sólo tok/s), tool calls, entrada de visión, y estabilidad
   sostenida (sin crash tras varios turnos largos).
5. No planificar esta POC en el mismo ciclo que la POC de Qwen3.8-27B del
   §6; son experimentos independientes y no deben solaparse en el tiempo
   ni en el host.

## 8. Tabla comparativa de los cuatro modelos

| | Qwen3-Coder-30B-A3B-Instruct | Qwen3-30B-A3B-Thinking-2507 | Qwen3.8-27B | Qwen3.8-Flash-Next |
| --- | --- | --- | --- | --- |
| Rol en el informe | **Baseline** (coding) | **Baseline** (razonamiento) | POC | Futuro/experimental |
| Parámetros activos | ~3B (MoE A3B) | ~3B (MoE A3B) | 27B (denso) | ~6B activos (+51B n-gram, +4B MTP de 125B totales) |
| Tamaño en disco (Q4_K, cuant. dinámica) | 17.28 GiB | ~17–18 GiB (no medido exacto en este doc) | 17.22 GiB | 104.53 GiB |
| Thinking | No (non-thinking) | Sí, siempre-on | Configurable por request | Configurable por request |
| Coding/agentic | Alto (especializado) | Medio-alto | Alto (según benchmarks oficiales) | Muy alto (según benchmarks oficiales) |
| Tools | Sí | Sí | Sí | Sí |
| Visión | No | No | Sí (mmproj) | Sí (mmproj) |
| Contexto nativo | 262,144 (cargado a 196,608\*) | 262,144 (cargado a 98,304) | 262,144 (hasta 1M) | 262,144 (hasta 1M) |
| Slots configurados | 3 | 1 | 1 (POC) | 1 (POC futura) |
| Soporte llama.cpp `b10375` | Sí | Sí | Sí (`qwen35`) | **No** (`qwen4exp` desconocido) |
| GTT medido en este host | 25.62 GiB | 22.40 GiB | No cargado | No cargado (no cabría con los otros dos) |
| Recomendación | Mantener | Mantener (mientras no se valide sustituto) | POC controlada, aislada | No perseguir hasta build posterior a #27941 y con GTT/offload validado |

\* Los 196,608 tokens de Coder son el **pool KV total** compartido
dinámicamente por los 3 slots (`--parallel 3`, `--kv-unified`), no
196,608 por slot. Con tres peticiones simultáneas activas, la capacidad
efectiva aproximada es **~65,536 tokens por petición** (196,608 ÷ 3),
aunque el reparto real entre slots es dinámico, no una partición fija
(ver §3.1).

## 9. Tamaño en disco vs footprint en GTT en tiempo de ejecución

**El tamaño del GGUF en disco no es el consumo de memoria en tiempo de
ejecución.** El GGUF sólo cuenta pesos cuantizados; el proceso
`llama-server` añade encima:

- El **KV cache** (dimensionado por `--ctx-size`, número de slots/`--parallel`
  y tipo de cuantización K/V), que crece con el contexto configurado, no
  con el contexto realmente usado en cada request.
- Buffers de cómputo, *batching* continuo y estructuras internas de Vulkan.

Esto explica que Coder (17.28 GiB en disco, contexto 196,608, 3 slots) use
**25.62 GiB de GTT** (+48 % sobre el disco) y que Thinking (~17–18 GiB en
disco, contexto 98,304, 1 slot) use **22.40 GiB**. Cualquier estimación de
capacidad debe basarse en el **GTT medido con el proceso corriendo**, no en
el tamaño del archivo.

Reglas de margen para este host (61.73 GiB de GTT total):

- Conservar **siempre ≥8 GiB o ≥10 %** de GTT libre sobre el total físico
  (lo que sea mayor) frente al conjunto de modelos residentes. Con
  48.02 GiB usados de 61.73 GiB, el margen actual es ~13.71 GiB (~22 %):
  dentro de la regla, pero sin holgura para añadir un tercer modelo grande.
- **Dos modelos activos ya compiten por ancho de banda de memoria UMA**;
  no se recomienda una tercera carga simultánea de un modelo de tamaño
  comparable (30B+ o denso 27B+) sin volver a medir tok/s con contraste
  N=1/N=2/N=3, siguiendo la misma metodología que
  `docs/validacion-lemonade-vulkan.md` (§"Diagnóstico de concurrencia").
- **Regla operativa medida: máximo 3 solicitudes/generaciones activas
  combinadas entre Coder y Thinking** (hasta 3 en Coder, `--parallel 3`, más
  las que Thinking pueda atender con su único slot, sin exceder 3 en total
  entre ambos), **no** tres modelos residentes. El host mantiene **dos**
  modelos residentes (`max_loaded_models=2`); no se sugiere cargar un
  tercer modelo auxiliar de clasificación/enrutado para cubrir esta regla.

## 10. Procedimientos de rollback

1. **Volver a Coder + Thinking** (estado de producción):
   - Confirmar `max_loaded_models=2` sigue vigente (`GET /internal/config`).
   - Cargar Coder con los argumentos exactos del §3.1 y Thinking con los
     del §3.2, usando `save_options:true` para persistir.
   - Verificar `GET /api/v1/health` → ambos `backend_health:"ready"`,
     `device:"gpu"`, `pinned:false` (a menos que se decida pinnear tras
     evidencia adicional).
2. **Descargar cualquier modelo experimental** (Qwen3.8-27B tras su POC, o
   Qwen3.8-Flash-Next si llega a probarse):
   - `POST /api/v1/unload` con el `model_name` exacto.
   - No usar `POST /api/v1/delete` salvo que se quiera liberar disco; no
     borrar el modelo activo de producción por error de nombre (ver el
     incidente de colisión de IDs documentado en
     `docs/validacion-lemonade-vulkan.md`).
3. **Comprobar salud tras cualquier rollback**:

   ```text
   curl -sS http://<HALO_HOST>:13305/api/v1/health
   ```

   Criterio de éxito: HTTP 200, `status:"ok"`, los dos modelos de
   producción listados en `all_models_loaded` con `backend_alive:true`.
4. **No tocar Qwen3.8-Flash-Next en el servicio del baseline**:
   no cargarlo en el `lemond` que sirve Coder/Thinking, ni siquiera para
   una prueba rápida, mientras no exista un build validado posterior a la
   fusión de #27941 y una POC aislada aprobada (§7).

## 11. Fuentes primarias

- Unsloth — model card Qwen3.8-27B:
  <https://huggingface.co/unsloth/Qwen3.8-27B-GGUF>
- Unsloth — guía Qwen3.8-27B: <https://unsloth.ai/docs/models/qwen3.8>
- Unsloth — model card Qwen3.8-Flash-Next:
  <https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF>
- Unsloth — guía Qwen3.8-Flash-Next:
  <https://unsloth.ai/docs/models/qwen3.8-next>
- llama.cpp — issue #27431 (crash Vulkan/AMD, prompts largos, UD-Q4_K_M):
  <https://github.com/ggml-org/llama.cpp/issues/27431>
- llama.cpp — PR #27742 (soporte base `qwen4exp`):
  <https://github.com/ggml-org/llama.cpp/pull/27742>
- llama.cpp — PR #27941 (correcciones críticas `qwen4exp`, fusionada
  2026-09-01): <https://github.com/ggml-org/llama.cpp/pull/27941>
- llama.cpp — PR #28102 (*Flash Attention tuning*, `gfx1201`,
  CUDA/HIP, no Vulkan/`gfx1151`):
  <https://github.com/ggml-org/llama.cpp/pull/28102>
- Lemonade Server — configuración general:
  <https://lemonade-server.ai/docs/guide/configuration/>
- Lemonade Server — soporte multi-modelo (`max_loaded_models`):
  <https://lemonade-server.ai/docs/guide/configuration/multi-model/>
- Lemonade Server — modelos personalizados:
  <https://lemonade-server.ai/docs/guide/configuration/custom-models/>
- Lemonade Server — API (`/v1/pull`, `/v1/downloads`):
  <https://lemonade-server.ai/docs/api/lemonade/#post-v1pull>
- OpenCode — configuración de agentes (`steps`, `AgentConfig`):
  <https://opencode.ai/docs/agents>
- OpenCode — modelos y opciones de proveedor (`budgetTokens`, no
  `max_tokens` a nivel de agente): <https://opencode.ai/docs/models/>
- Referencia comunitaria no oficial de rendimiento Flash-Next en Strix
  Halo (ESTIMACIÓN, no reproducida en este host):
  <https://github.com/drluoto/flash-next-strix-halo>
- Las observaciones de septiembre de 2026 se resumen de forma anonima en
  las secciones anteriores. Los registros privados originales no forman
  parte de la publicacion ni se requieren para leer estas conclusiones.
