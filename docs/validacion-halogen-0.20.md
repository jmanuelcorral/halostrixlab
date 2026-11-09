# Validación de Halogen 0.20.0 en el Halo

[Investigación Docker, toolboxes y Halogen](investigacion-docker-toolboxes-halogen.md) |
[English summary](en/validation-halogen-0.20.md) |
[Índice principal](../README.md)

**Fecha de la prueba: 2026-11-09. Estado: validado en el Halo con carga sintética,
configuración de servicio no promovida a documentación de referencia.**
Los valores de direcciones, usuarios y rutas privadas se sustituyen por
placeholders (`<HALO>`, `<GATEWAY>`, `<DATA>`). Los números son mediciones de esa
sesión; no son un benchmark publicado ni un compromiso de rendimiento.

## 1. Resumen

| Punto | Resultado |
| --- | --- |
| Versión | Halogen **0.20.0** (API y motor, coincidentes en `/health`). Antes: 0.11.3 |
| Checkpoint | `qwen38-flash-next-v2.hgn` (62.11 GiB). El `w4b` anterior se conserva en disco |
| Arranque | Motor escuchando a los 34 s en arranque en frío |
| Concurrencia | 8 slots sobre un pool de 1 048 576 posiciones. 8 peticiones simultáneas correctas |
| Contexto 128k | 8 peticiones de 128 949 tokens de prompt terminaron correctamente, con un prefill serializado de ~68 s cada una |
| Decode | 57 tok/s con un flujo de 128k solo; ~16 tok/s por flujo con 8 flujos cortos |
| Gateway | llama-swap sirve `flash-halogen` en estado `ready`; `concurrencyLimit` pasa de 4 a 8. Alias `halogen-qwen3.8-flash-next` |
| NPU | Activo: `decider-0.8b`, `qwen3-embedding-0.6b`, `qwen3-reranker-0.6b` en `/dev/accel/accel0`, con el reloj de GPU fijado a 2000 MHz |
| Endpoints por gateway | Chat, completions, responses, messages, embeddings, rerank y los tres modelos del NPU (sección 4.2) |
| Endpoints fuera del gateway | `/v1/systemone`, `/v1/moderations`, `/tokenize`, `/detokenize`, `/slots`, `/cache`, `/halogen/handles` (sección 4.3) |
| GTT | Sin cambios: 61.73 GiB. No ha sido necesario para esta versión (ver sección 6) |

## 2. Versiones, digests y rollback

| Elemento | Valor | Notas |
| --- | --- | --- |
| Imagen nueva | `ghcr.io/peonist-ai/halogen-flash-server@sha256:2d2c55a17e71f1aaf812b4e4cf0783dc5a8258461f8b3d9d7d84a9697fcfe637` | Etiqueta local `0.20.0`; la etiqueta `org.opencontainers.image.version` es `0.20.0` |
| Imagen de rollback | `ghcr.io/peonist-ai/halogen-flash-server:latest`, digest `sha256:760691880fecbf07f25e6b067cb5cc70e6a9ae11f280ca4725d3878e68821bd2` | Versión `0.11.3`; sigue en disco |
| Checkpoint activo | `qwen38-flash-next-v2.hgn` + `qwen38-flash-next-ngram.hgn` + `qwen38-flash-next-mtp.hgn` + tokenizer | Descargados desde `peonist-ai/halogen-qwen3.8-flash-next` con `hf download` dentro de la imagen 0.20.0 |
| Checkpoint de rollback | `qwen38-flash-next-w4b.hgn` (115.55 GiB) + overlay | Ya existía en el Halo desde septiembre |

**Backups previos al cambio** (fuera del repo, permisos restrictivos):
- Historial completo del repo en un bundle, con `HEAD` y estado.
- Ficheros ignorados y de estado local (`.env`, `workspaces/inference/data`, `.opencode`, `.crush`), con SHA256.

**Backups en el Halo** (sufijo `.bak-…-20261109`):
- `data/profiles.json` (restaurado al original; ver sección 7).
- `data/profiles-halogen-c.json` (el que usa llama-swap), antes de cada cambio.
- `data/gateway-coder-halogen-noauth.yaml`, antes de subir el `concurrencyLimit`.

## 3. Cambios en el repositorio

Rama `halogen-0.20-upgrade`, PR contra `master`:
- `workspaces/inference/profiles.example.json`: imagen 0.20.0 por digest.
- `workspaces/inference/runtime.py`: `HALOGEN_KV_POOL_POSITIONS = contexto + salida` y muestreo de la model card (`HALOGEN_TEMPERATURE=1.0`, `HALOGEN_TOP_P=0.95`, `HALOGEN_TOP_K=20`).
- `scripts/tests/test_inference_workspace.py`: expectativas actualizadas. 23 tests pasan.
- Este documento y las notas de la investigación.

**Desfase importante:** el runtime desplegado en el Halo (`28690f9`) no coincide con el de la rama. Tiene campos que la rama no tiene (`slots`, `kv_pool`, `halogen_max_tok`, `load_mode`), y en su bloque de Halogen el pool por defecto es el contexto, no contexto + salida. Tampoco pasa las variables de muestreo. Antes de fusionar, hay que reconciliar ambos runtimes. Hasta entonces, la configuración real del servicio es la del Halo, no la de la rama.

## 4. Configuración del servicio en el Halo

Perfil de llama-swap (`data/profiles-halogen-c.json`, entrada `flash-halogen`):

| Campo | Valor |
| --- | --- |
| `image` | 0.20.0 por digest (sección 2) |
| `halogen_checkpoint` | `qwen38-flash-next-v2.hgn` |
| `context` | 131072 |
| `output` | 8192 |
| `slots` | 8 |
| `kv_pool` | 1048576 |
| `halogen_max_tok` | 16384 |
| `halogen_tokenizer` | `tokenizer` |

Sin `halogen_overlay`: `v2` no usa el sidecar del `w4b`.

Gateway de llama-swap (`data/gateway-coder-halogen-noauth.yaml`): `flash-halogen` con `concurrencyLimit: 8` (antes 4), alias `halogen-qwen3.8-flash-next` y `globalConcurrencyLimit` en 8.

### 4.1. NPU

Perfil `flash-halogen`: campo `npu_models: ["decider-0.8b", "qwen3-embedding-0.6b", "qwen3-reranker-0.6b"]`.

El runtime del Halo se parcheó para aceptar `npu_models`. Solo con esa clave añade:
- `--device /dev/accel/accel0`.
- `--mount type=bind,src=/sys,dst=/host/sys`, que permite al motor fijar el reloj de GPU mientras corre el NPU.
- `HALOGEN_NPU_MODELS=<lista>`.

Los pesos de los modelos del NPU se descargaron antes del arranque, con el mismo `hf download` dentro de la imagen, a `~/halogen-models/npu/<id>/`: 2.6 GiB, 0.85 GiB y 0.79 GiB. `/models` sigue montado en solo lectura, y el motor no necesita escribir allí para estos tres modelos.

Línea de arranque del NPU:

```text
halogen: holding the GPU's fabric clock ... held at its top speed (2000Mhz) while the server runs
halogen npu: device /dev/accel/accel0 (crw-rw-rw- root:UNKNOWN), driver amdxdna (the kernel's own), XRT 2.25.37 (this image's)
npu_api: decider-0.8b on the NPU engine at 127.0.0.1:8740 ...
npu_api: qwen3-embedding-0.6b (embeddings) on the NPU engine ...
npu_api: qwen3-reranker-0.6b (rerank) on the NPU engine ...
```

Memoria: el motor anuncia hasta ~4.2 GiB de host para estos modelos, pinned, además del presupuesto de Flash.

### 4.2. Gateway: alias y modelos del NPU

Alias `halogen-qwen3.8-flash-next` → `flash-halogen`. Comprobado: una petición con ese nombre devuelve 200.

Entradas de llama-swap para los modelos del NPU: `decider-0.8b`, `qwen3-embedding-0.6b` y `qwen3-reranker-0.6b`. Todas apuntan a `http://127.0.0.1:18100`, con `useModelName` igual al nombre del modelo. Llama-swap exige un comando por modelo, así que cada entrada lanza un proceso auxiliar que no hace nada (`python3 -c "import time; time.sleep(10**9)"`). Esas tres entradas están en el grupo `npu-aux`, con `swap: false`, `exclusive: false` y `persistent: true`, así que pedir un modelo del NPU no descarga Halogen.

Dependencias de este truco:
- Si el contenedor de Halogen no está arriba, las tres rutas del NPU fallan igual que las de Halogen. El proceso auxiliar no sustituye al motor.
- El `ready` del auxiliar lo da el `/health` del backend de Halogen, no el propio proceso.

Salida real de `GET /v1/models` del gateway:

```text
decider-0.8b
flash-halogen
gufo-qwen38-27b
laya
qwen3-embedding-0.6b
qwen3-reranker-0.6b
winnow-12b-cpu
```

El alias no aparece en la lista; llama-swap no lista aliases. `laya`, `gufo-qwen38-27b` y `winnow-12b-cpu` son de otros servicios del mismo gateway y no se han tocado.

### 4.3. Endpoints: gateway frente a backend

Resultado de la prueba (`200` correcto, `404` no enrutado, el backend se consulta directo en `127.0.0.1:18100`):

| Endpoint | Backend | Gateway | Notas |
| --- | --- | --- | --- |
| `GET /health` | 200 | 200 | El del gateway es el de llama-swap, no el del motor |
| `GET /v1/models` | 200 | 200 | Lista de arriba |
| `GET /props?model=flash-halogen` | 200 | 200 | Sin `?model=` falla: llama-swap no identifica el modelo |
| `GET /metrics` | 200 | 200 | Gateway: métricas de llama-swap. Halogen: en el backend |
| `POST /v1/chat/completions` (Flash) | 200 | 200 | |
| `POST /v1/chat/completions` (`decider-0.8b`, `json_schema`) | 200 | 200 | Decisión por chat |
| `POST /v1/completions` | 200 | 200 | |
| `POST /v1/responses` | 200 | 200 | |
| `POST /v1/messages` y `/count_tokens` | 200 | 200 | |
| `POST /v1/embeddings` (`qwen3-embedding-0.6b`) | 200 | 200 | |
| `POST /v1/rerank` (`qwen3-reranker-0.6b`) | 200 | 200 | El documento relevante puntúa 0.986, el irrelevante 4e-5 |
| `POST /v1/systemone` (`decider-0.8b`) | 200 | 404 | llama-swap no tiene esa ruta |
| `POST /v1/moderations` | 400 | 404 | Backend: `qwen3guard` no está activado. Gateway: sin ruta |
| `GET /slots`, `/cache`, `/halogen/handles` | 200 | 404 | Sin ruta en llama-swap |
| `POST /tokenize`, `/detokenize` | 200 | 404 | Sin ruta en llama-swap |

Llama-swap enruta por una tabla fija de rutas. Un modelo nuevo en el gateway no añade rutas; por eso `/v1/systemone`, `/v1/moderations` y las rutas de estado de Halogen siguen fuera. Para exponerlas hace falta un proxy delante (Caddy) con reglas por ruta, o acceso directo al backend.

Arranque del motor (línea real del log):

```text
8 slots over ONE 1048576-position KV pool, each request up to 131072
memory: 62.1 GiB of weights locked in RAM, 28.8 GiB of KV pool, 8.8 GiB of working memory, 99.7 GiB in all
host memory left for everything else: 20.5 GiB
```

## 5. Mediciones

Todas las pruebas se hicieron contra el servicio en el Halo: directas al puerto del backend o a través del gateway, según la fila.

### 5.1. Concurrencia con prompts cortos (200 tokens de salida)

| Configuración | Simultáneas | Resultado | Pared | Agregado |
| --- | --- | --- | --- | --- |
| Directo, pool 524 288, 4 slots | 4 | 4/4 | 7.8 s | 102.6 tok/s |
| Directo, pool 524 288, 4 slots | 8 | 8/8; 4 esperan en cola | 14.8 s | 108.1 tok/s |
| Gateway, `concurrencyLimit` 4 | 4 | 4/4 | 7.7 s | 103.9 tok/s |
| Gateway, `concurrencyLimit` 4 | 8 | 4/8; 4 con HTTP 429 inmediato | 7.4 s | 108.1 tok/s |
| Gateway, `concurrencyLimit` 8 | 8 | 8/8; 4 esperan en cola | 14.9 s | 107.4 tok/s |
| Gateway, pool 1 048 576, 8 slots | 8 | 8/8, todas en ~12.5 s | 12.6 s | 127.0 tok/s |

El 429 viene del gateway (`concurrencyLimit`), no de Halogen. Con 8 slots y pool de 1M, las 8 corren a la vez.

### 5.2. Contexto de 128k: 8 peticiones simultáneas

Cada petición: prompt de 128 949 tokens y salida máxima de 2 048. Prompt + salida = 130 997, dentro de los 131 072 del contexto.

| Medida | Valor |
| --- | --- |
| Resultado | 8/8 correctas, todas con `finish_reason: stop` |
| Pared por petición | 101.6 s a 555.7 s |
| Pared total | 555.7 s |
| Prefill por petición | ~65–70 s, entre 1 840 y 1 976 tok/s |
| Pico de ocupación del pool | 922 112 de 1 048 576 (88 %) |
| Expulsiones | 1 entrada de caché de prompts (4 608 posiciones) para dar sitio a la octava |
| Decode durante prefills activos | ~5–6 tok/s por flujo |
| Último flujo, ya sin prefills | ~77 tok/s |

Los prefills se hacen en serie, así que el cuello de botella es el prefill (~1 900 tok/s) y no el pool. Las 8 peticiones tardan ~9 minutos en conjunto. Esta prueba no mide la calidad de las respuestas.

### 5.3. Decode aislado

| Prueba | Resultado |
| --- | --- |
| A: una petición de 128 899 tokens, sola | 57.2 tok/s de decode (64 tokens generados) |
| B: 8 peticiones cortas simultáneas, 400 tokens cada una | 16.1 tok/s de media por flujo (~128 tok/s agregado) |

Con concurrencia el servidor usa el camino *batched*, que la documentación de Halogen describe sin especulación por flujo. Un flujo solo con contexto largo va más rápido que cada uno de los 8 cortos. Además, un flujo corto solo en el calentamiento dio ~16 tok/s con `head off` en el log. Eso sugiere que la especulación no se activa con prompts cortos y no solo con concurrencia. No he probado un flujo corto solo en la misma tanda, así que queda sin confirmar.

## 6. GTT y memoria

- GTT del Halo: 61.73 GiB (`ttm.pages_limit` por defecto). No se ha cambiado.
- La documentación upstream dice que los pesos son memoria del host registrada y **no cuentan contra el GTT**. Hay que medir el GTT en uso durante la carga, no estimarlo por el tamaño de los pesos. Durante las pruebas el GTT usado estuvo entre ~17 GB y ~41 GB.
- En el arranque con pool de 1M, el motor reporta 20.5 GiB libres para el resto del sistema. El Halo es de uso exclusivo para inferencia, así que se acepta ese margen.
- Si el arranque falla por memoria, la primera palanca es `halogen_max_tok` (ya en 16384). La siguiente es reducir `kv_pool`.

## 7. Errores corregidos durante la sesión

- **Mi cálculo de capacidad a 128k era erróneo.** Dije 3 conversaciones para pool 524 288 y 7 para 1 048 576. Lo correcto es 4 y 8: la reserva por petición es `prompt + max_tokens` ≤ 131 072, no 128k + 8k. En la prueba, 8 peticiones de 130 997 caben en 1 048 576 (margen ~600 posiciones), pero la caché de prompts ocupó espacio y hubo una expulsión.
- **Mi análisis de GTT era erróneo.** Dije que los pesos debían caber en el GTT. Upstream dice lo contrario, y la medición lo confirma.
- **Primera carga de `v2` en el perfil equivocado.** Los cambios iniciales fueron a `data/profiles.json`, que no usa llama-swap. Se restauró y el perfil correcto es `profiles-halogen-c.json`.
- **Contenedor lanzado a mano.** Se paró con la herramienta del workspace (que comprueba la etiqueta de propietario) y llama-swap lo arrancó después con su configuración.

## 8. Pendientes

1. **Reconciliar runtime de la rama y del Halo** (sección 3) antes de fusionar el PR. El Halo ya tiene `npu_models` y la rama no.
2. **Gateway sin autenticación en la LAN.** `gateway-coder-halogen-noauth.yaml` escucha en la red local. Cualquier equipo de la red puede usar todos sus modelos sin clave, incluidos los del NPU.
3. **Rutas fuera del gateway** (`/v1/systemone`, `/v1/moderations`, `/tokenize`, `/slots`, `/cache`, `/halogen/handles`). Hace falta Caddy o acceso directo al backend. Caddy no está corriendo en el Halo.
4. **Moderación:** `qwen3guard-gen-0.6b` no está activado. Para usarlo, añadirlo a `npu_models` y descargarlo.
5. **Muestreo:** la rama fija los valores de la model card, pero el servicio en el Halo sigue en greedy hasta que se reconcilie el runtime.
6. **Decode de flujo corto solo** no confirmado (sección 5.3).
7. **Calidad de respuesta** en concurrencia, con contexto largo y con NPU activo: no medida.
8. **`HALOGEN_CACHE_ENTRIES`:** reducirlo podría evitar la expulsión de la séptima u octava petición de 128k. No probado.
9. **Coexistencia GPU+NPU bajo carga:** el reloj de GPU está fijado, pero no se ha medido bajo carga sostenida con Flash y el NPU a la vez.

## 9. Procedimiento de rollback

1. Parar el servicio con `runtime.py stop flash-halogen --config <DATA>/profiles-halogen-c.json`.
2. Restaurar `profiles-halogen-c.json` desde su backup `.bak-…-20261109` anterior al cambio que se quiera revertir. Los backups relevantes son `…bak-pre-npu-20261109` (sin `npu_models`) y `…bak-pre-slots8-20261109`, `…bak-pre-pool1m-20261109`. La entrada del 0.11.3 usa `w4b`, con `halogen_overlay`.
3. Restaurar `gateway-coder-halogen-noauth.yaml` desde `…bak-pre-alias-npu-20261109` (sin alias ni NPU) o `…bak-pre-npu-aux-20261109` (con alias, sin entradas del NPU). Luego reiniciar `llama-swap.service`.
4. Para quitar el NPU sin tocar el resto: restaurar `runtime.py` desde `runtime.py.bak-pre-npu-20261109`, o dejar el runtime y quitar `npu_models` del perfil.
5. Arrancar con llama-swap, que lanza `runtime.py start` con el perfil restaurado.

La imagen 0.11.3 y el `w4b` siguen en disco; no hay que descargar nada para volver atrás.
