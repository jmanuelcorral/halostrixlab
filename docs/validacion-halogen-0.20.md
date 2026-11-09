# Validación de Halogen 0.20.0 en el Halo

[Investigación Docker, toolboxes y Halogen](investigacion-docker-toolboxes-halogen.md) |
[English summary](en/validation-halogen-0.20.md) |
[Índice principal](../README.md)

**Fechas de la prueba: 2026-11-09. Estado: en servicio en el Halo con el código de la
rama `halogen-0.20-upgrade` (commit `a9f2c17`), validado con carga sintética.**
Las direcciones, usuarios y rutas privadas se sustituyen por placeholders
(`<GATEWAY>`, `<DATA>`). Los números son mediciones de esa sesión; no son un
benchmark publicado ni un compromiso de rendimiento.

## 1. Resumen

| Punto | Resultado |
| --- | --- |
| Versión | Halogen **0.20.0** (API y motor coinciden en `/health`). Antes: 0.11.3 |
| Checkpoint | `qwen38-flash-next-v2.hgn` (62.11 GiB) con ngram y MTP. El `w4b` anterior se conserva en disco |
| Visión | **Activa**: sidecar `qwen38-flash-next-vision.hgn` (857 MiB). Probada con imágenes sintéticas azul y roja |
| NPU | Activo: `decider-0.8b`, `qwen3-embedding-0.6b`, `qwen3-reranker-0.6b` en `/dev/accel/accel0`, con el reloj de GPU fijado a 2000 MHz |
| Arranque en frío | Motor escuchando a los 34 s; primera petición de texto a los 17 s tras reiniciar |
| Concurrencia | 8 slots sobre un pool de 1 048 576 posiciones. 8 peticiones simultáneas correctas |
| Contexto 128k | 8 peticiones de 128 949 tokens de prompt terminaron bien; prefill serializado a ~68 s cada una |
| Decode | 57 tok/s con un flujo de 128k solo; ~16 tok/s por flujo con 8 flujos cortos |
| Gateway | llama-swap **v271** (antes v255), sin `apiKeys` por ser LAN de uso exclusivo |
| Endpoints | Todos los de Halogen accesibles, por el gateway y por `/upstream/flash-halogen/…` (sección 4.3) |
| Panel `halo-control` | Sin gufo ni laya; catálogo con Halogen y los peers del NPU (sección 4.4) |
| GTT | Sin cambios: 61.73 GiB. No ha sido necesario para esta versión (sección 6) |

## 2. Versiones, digests y rollback

| Elemento | Valor | Notas |
| --- | --- | --- |
| Imagen en servicio | `ghcr.io/peonist-ai/halogen-flash-server:0.20.0@sha256:2d2c55a17e71f1aaf812b4e4cf0783dc5a8258461f8b3d9d7d84a9697fcfe637` | Etiqueta `org.opencontainers.image.version=0.20.0` |
| Imagen de rollback | `ghcr.io/peonist-ai/halogen-flash-server:latest`, digest `sha256:760691880fecbf07f25e6b067cb5cc70e6a9ae11f280ca4725d3878e68821bd2` | Versión 0.11.3; sigue en disco |
| Checkpoint activo | `qwen38-flash-next-v2.hgn`, `-ngram.hgn`, `-mtp.hgn`, `-vision.hgn` y tokenizer | Descargados con `hf download` dentro de la imagen 0.20.0 |
| Checkpoint de rollback | `qwen38-flash-next-w4b.hgn` (115.55 GiB) y su overlay | Ya existían en el Halo desde septiembre |
| llama-swap en servicio | v271 (`06de675`), suma SHA256 comprobada | Binario anterior v255 en `bin/llama-swap.v255.bak` |

**Backups previos a los cambios** (fuera del repo, permisos restrictivos):
- Bundle completo del repo local y del estado de trabajo, con SHA256.
- Ficheros ignorados de estado local (`.env`, `workspaces/inference/data`, `.opencode`, `.crush`).
- Clon del Halo antes de la reconciliación: `~/backups/halo-clone-pre-reconcile-20261109/` (parche, tar de sin trackear, configuración de gateway y perfil).

**Backups en el Halo** (sufijo `.bak-…-20261109`, en `<DATA>`):
- `profiles-halogen-c.json` (el que usa llama-swap), antes de cada cambio.
- `gateway-coder-halogen-noauth.yaml`, antes de cada cambio del gateway.
- `runtime.py`, `control.py` y `model_catalog.py`, antes de sus cambios.

## 3. Repositorio

Rama `halogen-0.20-upgrade`, PR #1 contra `master`. Commits relevantes:
- `627b484`, `3be378e`: upgrade a 0.20.0, pool KV de contexto más salida, muestreo de la model card.
- `aae226d`, `6144967`, `8604d5d`: documentación, retirada de laya y de gufo del gateway.
- `fba80e7`: fusión del estado de trabajo del clon del Halo (rama `halo-working-state-20261109`). El único conflicto fue `runtime.py`: se mantuvo la versión del Halo y se reaplicaron el pool y el muestreo.
- `a9f2c17`: limpieza de gufo y laya en código, tests, frontend y documentación.

**Desfase resuelto:** el runtime del Halo y el de la rama coinciden ya: `npu_models`, `halogen_vision`, `slots`, `kv_pool`, pool por defecto de contexto más salida y muestreo.

Winnow y Ollaya no se han tocado en esta limpieza. Sus tests siguen en el repo.

## 4. Configuración del servicio

### 4.1. Perfil de Flash (`flash-halogen`)

| Campo | Valor |
| --- | --- |
| `image` | 0.20.0 por digest (sección 2) |
| `halogen_checkpoint` | `qwen38-flash-next-v2.hgn` |
| `halogen_vision` | `qwen38-flash-next-vision.hgn` |
| `halogen_tokenizer` | `tokenizer` |
| `npu_models` | `decider-0.8b`, `qwen3-embedding-0.6b`, `qwen3-reranker-0.6b` |
| `context` / `output` | 131072 / 8192 |
| `slots` / `kv_pool` / `halogen_max_tok` | 8 / 1048576 / 16384 |

Sin `halogen_overlay`: `v2` no usa el sidecar del `w4b`.

Líneas reales del arranque:

```text
8 slots over ONE 1048576-position KV pool, each request up to 131072
memory: 62.1 GiB of weights locked in RAM, 28.8 GiB of KV pool, 8.8 GiB of working memory, 99.7 GiB in all
host memory left for everything else: 20.5 GiB
halogen: vision ON, tower /models/qwen38-flash-next-vision.hgn (857M)
kv pool: vision tower configured, 1.97 GiB (0.84 resident weights + 1.14 worst-case scratch at HALOGEN_VISION_MAX_PIXELS), charged against the 1.5 GiB margin
halogen npu: holding the GPU's fabric clock ... held at its top speed (2000Mhz) while the server runs
halogen npu: device /dev/accel/accel0 (crw-rw-rw- root:UNKNOWN), driver amdxdna (the kernel's own), XRT 2.25.37 (this image's)
```

### 4.2. NPU

Los tres modelos del NPU se descargaron antes del arranque, a `~/halogen-models/npu/<id>/`: 2.6 GiB, 0.85 GiB y 0.79 GiB. `/models` está montado en solo lectura, y el motor no necesita escribir allí para estos modelos.

Con `npu_models` en el perfil, el runtime añade:
- `--device /dev/accel/accel0`.
- `--mount type=bind,src=/sys,dst=/host/sys`, que permite al motor fijar el reloj de GPU mientras corre el NPU.
- `HALOGEN_NPU_MODELS=<lista>`.

Memoria: el motor anuncia hasta ~4.2 GiB de host para estos modelos, pinned, además del presupuesto de Flash.

### 4.3. Gateway (llama-swap v271)

Configuración en `<DATA>/gateway-coder-halogen-noauth.yaml`:
- Modelo local `flash-halogen` con alias `halogen-qwen3.8-flash-next`, `concurrencyLimit: 8`, y grupo `gpu` con `swap` y `exclusive` solo para Halogen.
- Peer `halogen-npu` apuntando a `127.0.0.1:18100`, con los tres modelos del NPU. Sustituye a los procesos auxiliares que usábamos antes.
- Sin `apiKeys`: la red es LAN de uso exclusivo.

Salida real de `GET /v1/models` del gateway:

```text
flash-halogen
halogen-npu/decider-0.8b
halogen-npu/qwen3-embedding-0.6b
halogen-npu/qwen3-reranker-0.6b
```

Los modelos del NPU también responden sin prefijo mientras no haya ambigüedad. El alias no aparece en la lista: llama-swap no lista aliases.

Retirados del gateway el 9 de noviembre:
- `laya` y `winnow-12b-cpu`, con sus grupos `laya-cpu` y `winnow-cpu`.
- `gufo-qwen38-27b`, y su pertenencia al grupo `gpu`, para que ninguna petición pueda descargar Flash por error.

Sus datos y scripts siguen en el Halo, salvo lo indicado en la sección 4.5.

### 4.4. Endpoints por gateway y por `/upstream`

Resultados de la prueba (`200` correcto; `404` sin ruta):

| Endpoint | Backend directo | Gateway | Vía `/upstream/flash-halogen/…` |
| --- | --- | --- | --- |
| `GET /health`, `GET /v1/models` | 200 | 200 | — |
| `GET /props?model=flash-halogen` | 200 | 200 | 200 |
| `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/messages`, `/v1/messages/count_tokens` | 200 | 200 | — |
| `POST /v1/chat/completions` con imagen | 200 | 200 | — |
| `POST /v1/embeddings`, `/v1/rerank` (peers NPU) | 200 | 200 | — |
| `POST /v1/chat/completions` (`decider-0.8b`, `json_schema`) | 200 | 200 | — |
| `POST /tokenize`, `/detokenize` | 200 | 404 | 200 |
| `GET /slots`, `/cache`, `/halogen/handles` | 200 | 404 | 200 |
| `POST /v1/systemone` | 200 | 404 | 200 |
| `POST /v1/moderations` | 400 | 404 | 400 (esperado: `qwen3guard` no está activado) |

Llama-swap v255 enrutaba por una tabla fija; por eso estas rutas daban 404 por el gateway. La v271 expone `/upstream/<modelo>/<ruta>`, que pasa cualquier ruta al servidor del modelo y lo carga si hace falta.

### 4.5. Panel `halo-control`

- Sin acciones, selecciones ni interfaz para gufo ni laya.
- El catálogo muestra Halogen y los tres peers del NPU, y consulta el gateway. No llama a ningún motor retirado.
- `status()` reporta gufo y laya como retirados en lugar de sondearlos.
- Tests del panel: 100 ejecutados y 11 omitidos, todos de laya y de funcionalidad retirada.
- El test de navegador (Playwright) se reescribió para Halogen y **no se ha ejecutado**: no hay navegadores en el Halo.

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

Cada petición: prompt de 128 949 tokens y salida máxima de 2 048. Prompt más salida suman 130 997, dentro de los 131 072 del contexto.

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

Con concurrencia el servidor usa el camino *batched*, que la documentación de Halogen describe sin especulación por flujo. Un flujo solo con contexto largo va más rápido que cada uno de los 8 cortos. Además, un flujo corto solo en el calentamiento dio ~16 tok/s con `head off` en el log. Eso sugiere que la especulación no se activa con prompts cortos, y no solo con concurrencia. No se ha probado un flujo corto solo en la misma tanda, así que queda sin confirmar.

### 5.4. Visión y NPU tras el reinicio controlado

Reinicio de Halogen con el código de `a9f2c17`, arranque en frío:

| Prueba | Resultado |
| --- | --- |
| Texto (primera petición tras el arranque) | 200 en 17 s |
| Imagen azul de 128×128 | 200, respuesta «Azul» |
| Imagen roja de 128×128 (prueba previa) | 200, respuesta «Rojo» |
| Peer NPU `decider-0.8b` con `json_schema` | 200 |
| Peer NPU `qwen3-embedding-0.6b` | 200 |

## 6. GTT y memoria

- GTT del Halo: 61.73 GiB (`ttm.pages_limit` por defecto). No se ha cambiado.
- La documentación upstream dice que los pesos son memoria del host registrada y **no cuentan contra el GTT**. Hay que medir el GTT en uso durante la carga, no estimarlo por el tamaño de los pesos. Durante las pruebas el GTT usado estuvo entre ~17 GB y ~41 GB.
- En el arranque con pool de 1M y visión, el motor reporta 20.5 GiB libres para el resto del sistema. La visión descuenta 1.97 GiB del margen de 1.5 GiB que el motor reserva, así que el presupuesto de memoria es ajustado. El Halo es de uso exclusivo para inferencia, y se acepta ese margen.
- El motor avisa de que las imágenes mayores que 2560×1440 se reducen (`HALOGEN_VISION_MAX_PIXELS`). No está fijado en el perfil.
- Si el arranque falla por memoria, la primera palanca es `halogen_max_tok` (ya en 16384). La siguiente es reducir `kv_pool`.

## 7. Errores corregidos durante la sesión

- **Mi cálculo de capacidad a 128k era erróneo.** Dije 3 conversaciones para pool 524 288 y 7 para 1 048 576. Lo correcto es 4 y 8: la reserva por petición es `prompt + max_tokens` ≤ 131 072, no 128k + 8k. En la prueba, 8 peticiones de 130 997 caben en 1 048 576 (margen ~600 posiciones), pero la caché de prompts ocupó espacio y hubo una expulsión.
- **Mi análisis de GTT era erróneo.** Dije que los pesos debían caber en el GTT. Upstream dice lo contrario, y la medición lo confirma.
- **Primera carga de `v2` en el perfil equivocado.** Los cambios iniciales fueron a `data/profiles.json`, que no usa llama-swap. Se restauró y el perfil correcto es `profiles-halogen-c.json`.
- **Contenedor lanzado a mano.** Se paró con la herramienta del workspace (que comprueba la etiqueta de propietario) y llama-swap lo arrancó después con su configuración.
- **Comprobación de visión antes de la carga.** Consulté `/health` antes de que el modelo cargara. Llama-swap arranca Halogen solo al recibir una petición.
- **Petición de prueba de `/upstream` sin respuesta en 5 s.** Dejó dudas. Se repitió con el modelo cargado y las 14 rutas respondieron como se esperaba.
- **Clon del Halo con trabajo sin commitear.** Se reconcilió en la rama `halo-working-state-20261109`, se fusionó y se limpió antes de desplegar.

## 8. Pendientes

1. **Arranque con el código nuevo** (`a9f2c17`): verificado con un reinicio controlado. Repetir tras cualquier cambio de perfil.
2. **Test de navegador del panel** (Playwright): reescrito para Halogen, no ejecutado. Necesita navegadores instalados.
3. **Ollaya y Winnow:** siguen en el repo, y sus tests usan nombres de grupos de laya y gufo en sus datos de prueba. Fuera de esta limpieza.
4. **Gateway sin autenticación en la LAN.** Aceptado por uso exclusivo; revisar si cambia el uso.
5. **Documentos históricos:** algunas menciones narrativas a gufo y laya se conservan como historia. Los enlaces a documentos borrados ya son texto plano.
6. **Moderación:** `qwen3guard-gen-0.6b` no está activado.
7. **Decode de flujo corto solo** sin confirmar (sección 5.3).
8. **Calidad de respuesta** en concurrencia, con contexto largo y con visión y NPU activos: no medida.
9. **`HALOGEN_CACHE_ENTRIES`:** reducirlo podría evitar la expulsión de la séptima u octava petición de 128k. No probado.
10. **Coexistencia GPU+NPU bajo carga sostenida:** el reloj de GPU está fijado, pero no se ha medido con Flash y NPU a la vez.
11. **Visión:** solo probada con imágenes sintéticas de un color. No medida con fotos ni con texto en imagen.

## 9. Procedimiento de rollback

1. Parar Halogen con `runtime.py stop flash-halogen --config <DATA>/profiles-halogen-c.json`.
2. Código: volver al commit anterior del clon del Halo con `git switch halo-working-state-20261109` (`3f4d189`), o a `fba80e7` para la versión previa a la limpieza de gufo.
3. Gateway: restaurar `bin/llama-swap.v255.bak` como binario y `gateway-coder-halogen-noauth.yaml.bak-pre-v271-20261109` como configuración, y reiniciar `llama-swap.service`.
4. Halogen 0.11.3: restaurar `profiles-halogen-c.json` a su versión previa a 0.20.0 (con `w4b` y `halogen_overlay`) y usar la imagen `latest` por digest.
5. Arrancar con llama-swap, que lanza `runtime.py start` con el perfil restaurado.

La imagen 0.11.3 y el `w4b` siguen en disco; no hay que descargar nada para volver atrás.

## 10. Cambios posteriores en el servidor

Tras la validación, el 9 de noviembre se hicieron estos cambios en el Halo:

- **Panel `halo-control`:** el bundle instalado en la copia de Cockpit se actualizó al código de
  `51e2453` y `843f26a`. La copia anterior se conservó en
  `~/backups/halo-control-package-pre-rebuild-20261109/`. Gufo y laya ya no aparecen.
- **Colector de métricas:** `halo-metrics.service` estaba deshabilitado, y por eso las gráficas
  no tenían datos. Está habilitado y verificado tras un reinicio.
- **Mantenimiento semanal:** actualización del sistema y reinicio los domingos a las 20:00, con
  avisos por ntfy. Las imágenes de Docker no se actualizan. Detalles y rollback en
  [mantenimiento-semanal-halo.md](mantenimiento-semanal-halo.md).
- **Avisos:** de actualización, reinicio, arranque y apagado, por ntfy, con el topic guardado en un
  fichero privado del servidor.
