# Validación Lemonade Server Vulkan — 2026-08-25

> **English:** [operational guide](en/configuration-reference.md) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

## Resultado

**Gate final histórico (2026-08-25): PASS con criterio de backend
gestionado.** El servicio de usuario `lemond` quedó `enabled` y `active`; la
unidad de sistema permaneció `disabled`/`inactive`, `Linger=no` y entonces el
API HTTP escuchaba exclusivamente en `127.0.0.1:13305`. Las validaciones
posteriores se realizan contra el endpoint LAN autorizado.

La conclusión PASS sustituye los FAIL históricos de este documento. Se obtuvo
evidencia directa del ejecutable administrado, su dispositivo Vulkan, el hijo
que cargó el modelo y una respuesta OpenAI-compatible. Las secciones
históricas se conservan para trazabilidad.

## Incidente — Qwen3.8-Flash-Next `UD-Q4_K_XL` — 2026-08-27

### Resultado: bloqueado por incompatibilidad de backend (no PASS)

`qwen3.8-flash` no es el Qwen3.8-27B ya operativo. El artefacto recién
descargado es **Qwen3.8-Flash-Next**, una vista multimodal MoE experimental de
125B parámetros (6B activos), la arquitectura previa a Qwen4. El modelo
concreto e íntegro es:

| Campo | Evidencia |
| --- | --- |
| ID de Lemonade | `Qwen3.8-Flash-Next-GGUF-UD-Q4_K_XL` (`user.` internamente) |
| Repo / revisión | `unsloth/Qwen3.8-Flash-Next-GGUF` @ `178b998806b7b406c311a3e6174aa99cf6304eaf` |
| Variante | `UD-Q4_K_XL`, cuatro GGUF divididos, más `mmproj-BF16.gguf` |
| Arquitectura GGUF | `qwen4exp`, v3, `512x56B`, 48 bloques, 512 expertos/10 activos, PLE n-gram, QSA y contexto nativo 262144 |
| Ruta principal | `$HOME/ai/lemonade/models/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/178b998806b7b406c311a3e6174aa99cf6304eaf/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf` |
| Tamaño descargado | 112,242,197,728 bytes (104.53 GiB): pesos 111,334,654,784 bytes + proyector 907,542,944 bytes |

La cabecera se leyó localmente sin cargar pesos: `general.architecture =
"qwen4exp"`, `split.count=4`, `split.tensors.count=1224`,
`qwen4exp.context_length=262144`. Los cuatro tamaños locales son exactamente
los del manifiesto HF/LFS (10,946,624; 49,859,583,136; 49,376,141,504;
12,087,983,520 bytes); sus SHA-256 LFS publicados son respectivamente
`444818...ec8082`, `3f342f...19a6c9`, `56758f...d9cbd3` y
`753bda...3510a`. Lemonade registró **Hash verified** para cada pieza y el
proyector, seguido de “All files downloaded and validated from Hugging Face”.
No hay `.partial`, `.incomplete` ni `.lock` en el repositorio objetivo. Los
ficheros son regulares `0644`, `operador:operador`; había 1.754 TB libres.

### Reproducción segura y causa

Antes de la prueba, `/api/v1/health` indicaba `model_loaded:null`,
`all_models_loaded:[]` y no había ningún `llama-server`; por ello no había una
generación que interrumpir ni un modelo previo que restaurar. Se hizo **un**
POST oficial de la UI a `http://<HALO_HOST>:13305/api/v1/load`, con
`Origin` correcto, `save_options:false`, Vulkan, un único slot
(`--parallel 1`) y contexto transitorio 8192. El servidor aceptó el origen,
creó el hijo Vulkan (PID 6927; reintento propio PID 6970) y devolvió:

```text
HTTP/1.1 500 Internal Server Error
model_load_error: Failed to load model
'Qwen3.8-Flash-Next-GGUF-UD-Q4_K_XL': llama-server failed to start

llama_model_load: error loading model: unknown model architecture: 'qwen4exp'
```

Por tanto el fallo ocurre en **metadata/arquitectura GGUF**, antes de
tokenizer, chat template, mmap, asignación Vulkan/GTT, KV/contexto o
generación. No es un alias, ruta, permiso, descarga, UI “loading” ni OOM.
`llama-server --version` confirma el backend administrado
**b10375 (`ba360efe1`)** y no contiene el símbolo `qwen4exp`.

La compatibilidad que falta no está publicada aún en un backend estable:
llama.cpp PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742),
**abierto** el 2026-08-26, añade `qwen4exp`; su primer commit de soporte de
formato es
[`6e5b8b7e4d88b0cdbfab6d2e6bc531cddab46065`](https://github.com/ggml-org/llama.cpp/commit/6e5b8b7e4d88b0cdbfab6d2e6bc531cddab46065)
y el HEAD probado de la rama es
[`6c5afc86ae84448ae4d744e357017e2c490ad9c3`](https://github.com/ggml-org/llama.cpp/commit/6c5afc86ae84448ae4d744e357017e2c490ad9c3),
2026-08-27. El [modelo oficial de Unsloth](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF)
y su [guía](https://unsloth.ai/docs/models/qwen3.8-next) requieren
explícitamente esa PR.

No se actualizó Lemonade, llama.cpp, Mesa, ROCm ni el kernel, ni se tocaron
binarios, rutas, firewall, modelo o configuración persistente. La carga de
8192/1 slot usó `save_options:false`; al final, las opciones persistentes
siguen en 262144 y vacías de argumentos. Aunque hay ~126.6 GiB de RAM
disponible y ~61.7 GiB GTT, el modelo Q4 pesa ~104.5 GiB; tras disponer de
soporte, se deberá validar por separado una carga de 8192/1 slot y offload
parcial, pues el error actual es anterior a cualquier asignación.

### Estado final y plan seguro

Tras el fallo, `lemond` sigue `active/running` (PID 1258), sin proceso hijo,
sin OOM, GPU reset ni `device lost`; `/api/v1/health` responde HTTP 200 y
ningún modelo queda cargado. No se puede demostrar chat/Vulkan/offload para
este modelo mientras no exista un backend con `qwen4exp`, así que este
incidente queda **INCOMPATIBLE, no PASS**. La última comprobación registrada
de UFW sigue `active` con la regla LAN 13305 y cero contenedores; en esta
sesión la consulta privilegiada se rechazó por requerir contraseña y no se
alteró UFW.

Ruta de corrección propuesta, no ejecutada: esperar una versión de Lemonade
que empaquete llama.cpp con #27742 (o su equivalente **merged/released**),
revisar changelog/SHA y compatibilidad Vulkan antes de actualizar el backend
gestionado mediante el mecanismo oficial. Hacer copia de las opciones del
modelo, probar primero `ctx_size=8192`, `--parallel 1` y una política de
offload parcial reversible; sólo declarar éxito tras hijo Vulkan, health,
modelo cargado y chat corto HTTP 200/SSE. Si falla, descargar/restaurar las
opciones previas y cargar el modelo previo conocido. No descargar otra
variante automáticamente; si se necesita menor presión de memoria tras
soporte, el mismo repo ofrece `UD-IQ1_S` (72.5 GB) y no soluciona la
incompatibilidad `qwen4exp`.

### Restauración posterior del modelo previo — 08:12–08:13 CEST

La traza elimina la ambigüedad: el modelo activo inmediatamente antes de la
primera carga Flash (08:04:14) era **ninguno**. A las 08:03:54 Lemonade inició
la expulsión de `Qwen3-Coder-30B-A3B-Instruct-GGUF` y a las 08:03:56 confirmó
`Evicted model`; entre esa marca y la carga Flash sólo hay descarga/validación.
Por tanto, el último modelo activo anterior —y el que procedía restaurar— fue
el ID base `Qwen3-Coder-30B-A3B-Instruct-GGUF`, no su alias de usuario
`...-Q4_K_M`.

Antes de restaurar se verificó `model_loaded:null`, ningún hijo
`llama-server` y `/api/v1/downloads` sin trabajos en curso (`running:false`;
el único registro cancelado era histórico). Se restauró mediante el POST
oficial LAN `/api/v1/load`, `Origin` correcto, con sus opciones previamente
guardadas e inalteradas: Vulkan, `ctx_size=262144`, `merge_args=true`,
`save_options=false`. Respondió HTTP 200 `status:"success"`.

La validación completa confirma el hijo PID 7138
`.../llamacpp/vulkan/llama-server`, `libvulkan_radeon.so` y
`libvulkan.so.1.4.357` mapeadas, y FD `/dev/dri/renderD128`. El health
posterior informa `device:"gpu"`, `backend_alive:true`, `backend_health:"ready"`
y el ID restaurado como `model_loaded`; GTT usado subió a 43,032,989,696 bytes
y VRAM a 2,103,660,544 bytes, evidencia de offload Vulkan. `/v1/models`
respondió HTTP 200. El chat SSE LAN devolvió HTTP 200, `data: [DONE]`,
`Streaming completed - 200 OK` y el texto `Restaurado.`. No se produjo OOM,
reset ni `device lost`. El modelo Flash permanece íntegro, descargado y sin
alteraciones; sigue incompatible con b10375.

## Incidente de visibilidad — Qwen3-Coder-30B-A3B-Instruct Q4_K_M — 2026-08-26

### Estado confirmado

**RECUPERADO Y VALIDADO — 14:49:55–14:52:55 CEST.** Las subsecciones que
documentan el parcial y su ausencia del catálogo son históricas: se
conservaron durante la transferencia precisamente para no declarar una falsa
recuperación. Tras la finalización, Lemonade validó el SHA-256, publicó ambos
IDs como descargados y cargó el modelo Vulkan sin intervención manual.

| Elemento | Valor observado |
| --- | --- |
| Registro exacto | `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` |
| Origen/variante | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q4_K_M` |
| Revisión HF | `b17cb02dd882d5b6ab62fc777ad2995f19668350` |
| SHA-256 esperado (manifest) | `fadc3e5f8d42bf7e894a785b05082e47daee4df26680389817e2093056f088ad` |
| Ruta parcial única | `$HOME/ai/lemonade/models/models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF/snapshots/b17cb02dd882d5b6ab62fc777ad2995f19668350/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf.partial` |
| Tamaño esperado | 18,556,689,568 bytes (18.56 GB decimal) |
| Progreso muestreado | 8,640,876,544 → 8,875,982,848 bytes en 45 s (46.56% → 47.83%) |
| Comprobación final durante transferencia (14:11:09 CEST) | 11,124,862,976 bytes (59.95%); misma inode y `mtime` avanzando |

La misma inode `14089` creció sin renombrado y su `mtime` avanzó durante la
muestra. `lemond` (PID 1258) mantuvo una conexión TLS establecida a
Hugging Face; no se reinició, canceló, movió, borró ni reanudó manualmente
ninguna transferencia. A la tasa puntual de ~5.22 MB/s, los ~9.68 GB
restantes darían una estimación orientativa de ~31 minutos; la tasa de red no
está garantizada.

### Causa raíz y recuperación

El reinicio no dejó un artefacto completo sin indexar ni cambió los directorios:
la configuración efectiva conserva las rutas absolutas
`models_dir=$HOME/ai/lemonade/models` y
`extra_models_dir=$HOME/ai/models/smoke`, ambas escribibles y propiedad
de `operador`. Hay ~1.876 TB libres. Tampoco se observaron errores de solo
lectura, permisos o espacio, ni contenedores.

El journal establece la causa inmediata: tras el arranque de `lemond` a las
13:38:55 CEST, a las 13:40:35 el Model Manager ejecutó `Deleting model`,
eliminó únicamente la variante anterior y la marcó `not downloaded`. A las
13:40:52 se solicitó su carga y Lemonade inició automáticamente la descarga
del mismo repo, revisión, variante y manifest. Por tanto la ausencia del
catálogo es el comportamiento esperado para ese `.partial`, no un filtro de
UI, un path regresado o un fallo de indexación. El journal no atribuye el
origen de la operación de borrado a un cliente concreto.

La recuperación mínima oficial es **no intervenir**: permitir que el proceso
actual termine, compruebe el SHA-256 del manifest y actualice
`downloaded=1`/`resolved_path`. Sólo después verificar `/v1/models` para el
ID exacto, `downloaded: true`, el checkpoint exacto y una ruta final `.gguf`
sin `.partial`; entonces podrá aplicarse un refresh/rescan oficial si aún no
se publica. No cargar el 30B mientras haya sesiones activas. Si el proceso se
detiene, preservar esta parcial y verificar primero el soporte de reanudación
oficial de Lemonade contra este mismo manifest; no iniciar una descarga nueva
ni desde cero.

**Rollback:** no hubo cambio que revertir. Si se hace posteriormente un
rescan/import oficial y no valida, revertir sólo esa operación en el Model
Manager; conservar el manifest y la parcial original, no borrar caché ni
datos del modelo.

### Auditoría posterior de colisión/borrado — 14:02 CEST

El dato de que se borró otro modelo **no se correlaciona con una
normalización de prefijo hacia el 30B**. El journal conserva dos operaciones
distintas, separadas exactamente por 60 s:

1. A las 13:39:35, `POST /api/v1/delete` pidió
   `Qwen3-1.7B-Q8_0` (`extra.Qwen3-1.7B-Q8_0`,
   `$HOME/ai/models/smoke/Qwen3-1.7B-Q8_0.gguf`). Lemonade la rechazó
   con 500 porque es un modelo del directorio extra gestionado por el usuario;
   el archivo sigue presente y descargado.
2. A las 13:40:35, una segunda operación eliminó explícitamente
   `Qwen3-Coder-30B-A3B-Instruct-GGUF`, con checkpoint completo y la ruta
   exacta de la variante Q4_K_M descrita arriba. Sólo se eliminó esa variante
   compartida y se marcó no descargada.

La Web App 11.7 llama a `/delete` con el cuerpo
`{"model_name": e}`: pasa el ID de la entrada seleccionada, no un texto de
display ni una coincidencia de prefijo. El CLI confirma igualmente que el
argumento es un *model name*. El servicio no guardó IP de origen ni el cuerpo
de los POST exitosos, por lo que no es posible atribuir el segundo POST a un
cliente concreto, pero la traza descarta que el intento fallido sobre el 1.7B
haya sido transformado en el 30B.

Sí hay una fuente de ambigüedad visual que conviene evitar: el catálogo tiene
dos IDs sin alias para el mismo repo/artefacto:
`Qwen3-Coder-30B-A3B-Instruct-GGUF` (registro base, con filename explícito) y
`Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` (registro de usuario). Ambos
apuntan a `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` y a la misma Q4_K_M;
comparten el directorio de caché, no son dos copias. No hay alias compartido
con `Qwen3-1.7B-Q8_0` ni con `Qwen3-Coder-Next-GGUF-Q8_0`.

`/api/v1/downloads` publica de forma incoherente una entrada
`model:user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` como
`cancelled`/0 bytes mientras el fichero crece y `lemond` mantiene la conexión
HF. Es un estado de seguimiento/UI desactualizado, no una cancelación del
transfer real; no se usó para cancelar, borrar ni reanudar. La Papelera XDG
no contiene una entrada Qwen/Coder y Lemonade no expone un `undelete`;
el rollback seguro sigue siendo conservar la parcial y su manifest.

### Auditoría de punteros y artefacto compartido — 14:05 CEST

No hay puntero POSIX que explique una eliminación indirecta. El recorrido
físico (sin seguir enlaces) de `models_dir` y `extra_models_dir` devolvió
**cero symlinks**; el actual `.gguf.partial` es un fichero regular `0644`,
inode `14089`, `nlink=1`, y la búsqueda por inode no encontró ninguna otra
ruta. Tampoco hay grupos de hardlinks entre ficheros de ambos directorios.

El volumen `/home` es Btrfs. La consulta de metadatos
`btrfs filesystem du` del parcial informa 9.34 GiB exclusivos y 0 B
compartidos; `filefrag` no marca extents compartidos. Esto descarta reflink
para los bytes ya descargados. No es posible observar los extents del archivo
final que ya se eliminó, pero no existe otra ruta, stub, manifest ni alias
local que apunte a dicho filename: sólo `user_models.json`, el registro del
repo y el manifest oficial lo referencian.

Por tanto, el DELETE no retiró sólo metadata ni un enlace: el journal dice
que eliminó la ruta física final
`.../Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf`, y el descargador creó después
el fichero regular `.partial` actual en esa misma variante. “Main repo shared”
significa que los dos registros de catálogo comparten el namespace/repo de
caché; el servicio limitó la eliminación a **esa variante**, no a un objetivo
de enlace ni a todo el repositorio.

### State machine de carga/pull atascada en UI — 14:08 CEST

La etiqueta **“cargando”** no representa un `llama-server` del 30B ni un
backend intentando abrir una ruta inexistente. La Web App mantiene un `Set`
local de IDs en carga: añade el ID antes de `ensureModelReady`; ese flujo hace
`POST /pull`, espera su seguimiento y sólo entonces emite `POST /load`.
La App no usa SSE para esta tarea: `connectServerEvents()` sólo inicia polling
de `/api/v1/downloads` cada 2 s.

El endpoint oficial devuelve una combinación de estado incoherente para el
job exacto:

```text
id:         model:user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M
model_name: user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M
status:     cancelled
running:    true
bytes:      0 / 0
```

El polling de la UI sólo considera `cancelled` terminal cuando `running` no
es `true`; por ello deja el `Set` de carga esperando indefinidamente. A las
14:02:10 Lemonade aceptó de nuevo el pull del mismo ID y variante, pero el
catálogo sigue con ambos registros `downloaded=false`; `/v1/models` no publica
parciales. Es un **pull parcial útil etiquetado como loading por un tracker
API/UI contradictorio** (casos **b + e**), no un job servidor huérfano
independiente.

La evidencia de proceso lo confirma: el parcial creció
10,424,266,752 → 10,531,250,176 bytes en 30 s; `lemond` mantiene FD 15 sobre
él y no hay locks ni archivo `.lock`. No existe `llama-server` con el 30B.
El único hijo relevante es `sd-server` Vulkan para SDXL; también heredó FD 15
del servicio, pero su argumento `-m` apunta al `.safetensors` de SDXL, no al
GGUF parcial. No hay errores posteriores de apertura/path/hash para el 30B.

No se invocó `/downloads/control`, cancelación, limpieza ni reinicio: el job
visible está mal descrito, pero el descriptor y los bytes prueban que su
transferencia es útil. Cualquier `remove`/cancel oficial podría afectar la
misma descarga, por lo que no es seguro limpiar sólo el estado hasta que
termine o se detenga.

### Snapshot tras la desaparición observada en UI — 14:09 CEST

La desaparición visual comunicada para las 14:01 **no fue el fin de la
transferencia servidor**. La captura inmediata posterior halló exactamente el
mismo parcial (inode `14089`) creciendo a 10,808,082,432 bytes, con `mtime`
14:09:35; permanecen el manifest, `refs/main` y el registro, sin lock.
`lemond` sigue activo; no existe proceso `llama-server` del 30B y el catálogo
mantiene ambas entradas como `downloaded=false`.

No hay en el journal entre 14:00 y 14:02 ningún `complete`, hash validado,
cancelación, fallo, delete cascade ni error de ruta del 30B. A las 14:02:10
se registró un nuevo `Pulling model:
user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` que utiliza la misma variante;
no creó un segundo parcial ni cambió su inode. Los únicos 404 posteriores son
consultas a la ruta inexistente `/api/v1/pulls`, no un fallo del artefacto.

Por ello **no existe código final de tarea que limpiar**: el único objeto de
estado publicado sigue siendo el registro contradictorio
`cancelled + running=true, 0/0`, mientras la transferencia real continúa.
La explicación compatible con toda la evidencia es que la UI descartó o
reinicializó su estado local de carga; no hubo éxito con desregistro, cancel,
fallo, cascada de borrado ni path missing. El parcial es actualmente útil y
reanudable de facto por el proceso activo; se conserva sin iniciar otra
descarga.

### Monitorización read-only de la nueva solicitud exacta — 14:10–14:11 CEST

Se mantuvo observación sin enviar pull, cancelación ni control de job. La
solicitud exacta debe resolver al manifest ya preservado:

```text
repo:    unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF
variant: Q4_K_M
archivo: Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
URL:     https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/resolve/b17cb02dd882d5b6ab62fc777ad2995f19668350/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
```

En 45 s el parcial existente pasó de 10,920,206,336 a 11,124,862,976 bytes
(+204,656,640 bytes; ~4.55 MB/s), conservando la ruta absoluta, inode
`14089` y snapshot `b17cb02dd882d5b6ab62fc777ad2995f19668350`. No apareció
otro parcial, GGUF, directorio de repo, lock ni job ID: la operación reutiliza
la transferencia existente, no empieza desde cero ni duplica 18.56 GB.
`lemond` mantiene TLS a HF y quedan ~1.874 TB libres. El endpoint de jobs
sigue publicando el mismo ID contradictorio; no es una señal válida para
cancelar una transferencia que demuestra crecimiento físico.

La causa previa se mantiene: el DELETE eliminó el fichero físico de la
variante exacta en el namespace compartido de repo, no un target de symlink,
hardlink o reflink. **No se declara recuperado** hasta que se complete el
SHA-256 del manifest, se renombre a `.gguf` y el catálogo publique
`downloaded=true`.

### Gate de reinicio autorizado — detenido por transferencia real — 14:11 CEST

Antes del reinicio autorizado se capturó el job, procesos, FDs, locks, journal
y dos muestras separadas por 20 s. Aunque `/api/v1/downloads` continúa
publicando `cancelled + running=true, 0/0`, el parcial **no estaba quieto**:

```text
14:11:49  11,235,487,744 bytes
14:12:09  11,285,934,080 bytes
delta      +50,446,336 bytes en 20 s (~2.52 MB/s)
```

La inode seguía siendo `14089`; `lemond` (PID 1258) y su hijo `sd-server`
(PID 2818, FD heredado) mantenían el descriptor abierto. No había lock de
archivo ni error de journal que justificara tratar el parcial como muerto.
Por tanto **no se ejecutó** `systemctl --user stop lemond.service`, no se
envió TERM/KILL y no se limpió estado mediante endpoint: hacerlo habría
interrumpido una descarga útil y violado el requisito explícito de confirmar
ausencia de escritura antes de parar.

El reinicio seguro queda condicionado a observar dos muestras consecutivas
sin crecimiento, sin FD de escritura y con el job ya no activo. Hasta entonces
el parcial y manifest se preservan; no se crea una descarga nueva ni se edita
estado/DB manualmente.

### Resolución final y validación — PASS

El monitor read-only completó sin observar dos intervalos estancados; por eso
no ejecutó reinicio, cancelación, limpieza, rescan ni import. La descarga
creció de forma continua hasta que, a las 14:49:55, Lemonade registró:
`Hash verified`, `All files downloaded and validated from Hugging Face` y
`downloaded=1` con `resolved_path` exacta.

| Verificación | Resultado |
| --- | --- |
| Archivo final | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` |
| Ruta | `$HOME/ai/lemonade/models/models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF/snapshots/b17cb02dd882d5b6ab62fc777ad2995f19668350/` |
| Tamaño / permisos | 18,556,689,568 bytes; inode `14089`; `operador:operador`; `0644`; sin `.partial` |
| SHA-256 manifest y cálculo completo | `fadc3e5f8d42bf7e894a785b05082e47daee4df26680389817e2093056f088ad` — **coinciden** |
| Catálogo | `/api/v1/models?show_all=true` y `/v1/models` publican `Qwen3-Coder-30B-A3B-Instruct-GGUF` y `...-Q4_K_M` con `downloaded=true` |
| Carga | `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` lista en Vulkan; `llama-server` PID 3779, `ctx_size=262144`, cuatro slots sin procesar |
| Smoke de chat | Previamente sin slots ocupados; `POST /v1/chat/completions` devolvió HTTP 200 en 0.271 s (14 tokens) |
| Servicio/UI | `lemond` enabled/active; listener LAN `<HALO_HOST>:13305`; UI HTTP 200; rutas absolutas correctas |
| Red/contenedores | UFW activo, política/rules LAN 13305 intactas; Docker 0 contenedores; Podman no instalado |

El objeto histórico de `/api/v1/downloads` queda como `cancelled` pero ya con
`running=false`; es basura de tracker, no una tarea que deba limpiarse. No se
hizo ninguna limpieza oficial porque el catálogo y la carga ya se
autocorrigieron. La causa raíz permanece: el DELETE previo retiró el archivo
físico de la variante exacta; la recuperación oficial posterior reutilizó el
parcial, validó el hash y restauró metadata/catálogo.

Los resultados necesarios se resumen en este documento; los registros privados no se publican ni son una dependencia de lectura.

## Diagnóstico de concurrencia Lemonade/OpenCode — 2026-08-26

### Resultado

**La evidencia descarta una serialización estricta de los slots lógicos.**
El journal y `/slots` muestran dos secuencias lógicas con actividad de decode
solapada. Esto basta para separar `max_loaded_models=1` de la concurrencia de
peticiones: ese límite controla modelos residentes, no slots del mismo modelo.
No demuestra por sí solo simultaneidad física en GPU, TTFT ni una mejora de
wall-clock.

No se reinició el servicio ni se alteró su configuración: durante toda la
ventana había trabajo ajeno activo. Tras esperar tres minutos, `/slots` y
`/metrics` internos no respondieron en 8 s, lo que confirma carga sostenida y
hace inseguro inyectar el benchmark controlado solicitado. No se canceló ni
limitó ninguna petición existente.

### Identidad exacta y configuración efectiva observada

| Elemento | Valor observado |
| --- | --- |
| Lemonade | `11.7.0` (paquete `11.7.0-2.1`) |
| Backend | `llamacpp:vulkan`, binario administrado `b10375` |
| GPU | Radeon 8060S / RADV Strix Halo |
| Modelo realmente cargado | `Qwen3.8-27B-GGUF-UD-Q4_K_XL` |
| Checkpoint/variante | `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, Q4_K Medium, 17.2 GiB, con `mmproj-BF16.gguf` y draft MTP |
| Catálogo adicional | `Qwen3-1.7B-Q8_0` y `PathProbe-Qwen3-0.6B-UD-IQ1_S` estaban descargados, pero **no** cargados |
| Contexto del proceso | `--ctx-size 262144`; no es el default histórico de 32768 |
| Slots efectivos | 4 (`id` 0–3), elegido automáticamente al no pasar `--parallel` |
| Batching | continuo habilitado por defecto; no se pasó `--no-cont-batching` |
| Batch / ubatch | defaults de este binario: 2048 / 512 |

La confusión “Qwen3.8” no se refiere a un supuesto Qwen3 de 8B. El ID servido
por `/v1/models`, la telemetría y la línea de comandos coinciden en la variante
Qwen3.8 de **27B** indicada arriba.

La ayuda del `llama-server` exacto confirma `--parallel N` como “number of
server slots” (`-1 = auto`) y `--cont-batching` como batching continuo,
habilitado por defecto. `/props` confirma `total_slots: 4`. El KV usa el
contexto unificado indicado por `--ctx-size 262144`; el `n_ctx: 262144`
expuesto por cada objeto de `/slots` no debe sumarse como cuatro asignaciones
independientes de 262k. Cualquier cambio de slots o contexto exige validar
memoria KV y latencia con cargas reales.

Hay una discrepancia documental de topología de puertos: el resumen histórico
inicial conserva una comprobación de loopback, pero esta captura observó la
API de Lemonade en su listener LAN configurado y el hijo `llama-server` en su
puerto interno. No hubo discrepancia de backend (sigue siendo Vulkan b10375)
ni se modificó configuración alguna.

### Medición real y correlación

La captura se inició a las 09:24:45 CEST, antes de cualquier prueba, y halló
dos conexiones streaming ajenas desde el cliente `<CLIENT_HOST>`; el PC de inspección
es `<INSPECTION_CLIENT_HOST>`. A las 09:25:33:

* `/slots` interno informó `is_processing=true` en los slots 0 y 2; 1 y 3
  estaban libres.
* `/metrics` informó `requests_processing=2`, `requests_deferred=0` y
  `n_busy_slots_per_decode=1.41229`. Este último es un promedio histórico del
  backend, útil como señal de utilización; no es una prueba aislada de
  simultaneidad GPU ni de TTFT.
* El journal muestra prefill y decode intercalados: por ejemplo, para los
  slots 0 y 2 hay líneas de decode alternas entre 09:06:41 y 09:07:51. En ese
  intervalo el slot 0 avanzó de 100 a 801 tokens y el 2 de 216 a 1036,
  mientras ambos seguían activos. Prueba solapamiento de secuencias lógicas
  de decode, no una atribución aislada de ejecución física GPU.
* La telemetría agregada del instante fue 83.05 tok/s de prompt y 10.14 tok/s
  de generación. Una degradación de TTFT por contexto/carga compartida es una
  **hipótesis**, pendiente de compararla con baseline N=1/N=2/N=4. El único
  límite de generación observado/documentado en los slots fue 32 000 tokens.

La carga no cedió en la espera de tres minutos: a las 09:29:54, dos consultas
internas consecutivas agotaron 8 s sin bytes y seguían dos conexiones ajenas
establecidas. Por ello no se ejecutaron N=1/N=2/N=4 ni una operación multiagente sintética:
hacerlo habría añadido cola y degradado trabajo del usuario. Consecuentemente,
**no se reclama una mejora de wall-clock controlada**; la evidencia disponible
se limita a dos secuencias lógicas de decode solapadas.

Un recheck posterior del gate, entre 09:38:36 y 09:39:10 CEST, tampoco fue
idle: no hubo cambios locales de OpenCode, pero el puerto interno previamente
observado rechazó las siete consultas y una inspección inmediatamente posterior
encontró el mismo modelo en un nuevo puerto interno, con registros continuos
de prefill de una tarea ajena. Es evidencia adicional de actividad; no se
inyectó ningún request de benchmark.

### OpenCode local

En este Windows, `opencode --version` devolvió `1.18.18`, no había proceso
OpenCode activo y su configuración resuelta no contiene proveedor/end-point
Lemonade. La base local conserva ejecuciones multiagente históricas (un padre
con tres hijos en varias ejecuciones 1.17.x), pero sus metadatos de modelo
incluyen `ollama/qwen3:8b`, no una llamada demostrable al endpoint LAN
Lemonade actual. Por tanto no es válido atribuir las dos peticiones activas
del cliente `<CLIENT_HOST>` a esta instalación local ni inventar un límite de
concurrencia de OpenCode.

No existe en esta configuración local una opción oficial de proveedor que se
pueda modificar con seguridad para aumentar concurrencia. Antes de diagnosticar
OpenCode en una futura ventana libre, capturar desde el mismo cliente la hora,
el proveedor/modelo y el número de `POST /v1/chat/completions`; correlacionar
cada POST con `slot launch_slot_` y `/metrics`. No usar el número de agentes
como sustituto del número de requests HTTP: los turnos de herramientas y las
dependencias padre/hijo pueden serializarse.

### Recomendación y rollback

1. Mantener los cuatro slots auto y batching continuo actuales; no añadir
   `--parallel` ni reiniciar mientras haya streams largos.
2. Recomendación provisional para código interactivo: **dos agentes que
   realmente emitan requests independientes**, hasta 32k de contexto por
   agente, compactación alrededor de 24k y salidas de 64–128 tokens. No
   recomendar 3–4 agentes para TTFT hasta medirlos.
3. En una ventana sin `requests_processing`, medir el mismo prompt streaming
   con barrera N=1, N=2 y N=4, registrando start, TTFT, wall-clock, HTTP y
   tokens/s, mientras se muestrean `/slots`, `/metrics` y GPU. Sólo
   recomendar N=4 si esa comparación controlada mejora wall-clock sin errores
   ni presión de memoria.
4. Si posteriormente se prueba una opción oficial, hacer copia de la
   configuración de Lemonade y de los argumentos del modelo, cambiar primero
   a dos slots, reiniciar sólo en idle y revertir restaurando esa copia y los
   argumentos actuales (`--ctx-size 262144`, Vulkan y el mismo modelo).

La evidencia publica de procesos, slots, metricas y limites de esta ventana
se resume en esta seccion; no depende de registros privados.

## Registro histórico — reintento entonces requerido

Antes del cierre PASS, una sesión autorizada nueva debía empezar de cero y guardar el raw desde el
precheck. Debe comprobar primero que los servicios system y user están
`disabled`/`inactive` y que el puerto `127.0.0.1:13305` está libre. Solo
después puede aplicar y verificar la configuración con la CLI, instalar
`llamacpp:vulkan` si falta, y ejecutar el load-only y el chat monitorizados.

La promoción exige evidencia persistida de: paquete Lemonade 11.7.0,
configuración Vulkan, artefacto con hash, bind exclusivo loopback, modelo GGUF
local identificado por `/v1/models`, carga de contexto 2048, respuesta
OpenAI-compatible válida, logs Vulkan/offload, estado térmico y restart
saludable.

## Registro histórico — bloqueo de configuración CLI

La inspección posterior confirmó paquete instalado, Vulkan disponible, GGUF
local y unidades `lemond` de sistema/usuario disabled/inactive. Se creó
únicamente el directorio autorizado de modelos bajo `~/ai/lemonade/models`.

La CLI instalada exige un servidor activo: `lemonade config set`, `config
get`, `backends --all` e instalación de `llamacpp:vulkan` devolvieron “Could
not connect to Lemonade server” mientras se respetaba la prohibición de
iniciarlo en esta etapa. No se editó JSON manualmente, no se descargó backend
ni modelo y no se creó listener.

El orden solicitado es incompatible con esta CLI: no permite configurar o
administrar backends con `lemond` inactivo. Se detiene antes de habilitar el
daemon con defaults no validados. Los resultados de ese bloqueo se conservan
en este resumen anonimo.

## Registro histórico — orden cliente-servidor adaptado

Se inició temporalmente solo la unidad user, se obtuvo health y bind
`127.0.0.1:13305`, y se aplicaron por CLI las claves confirmadas de loopback,
puerto, broadcast, límites, directorios, Llama.cpp Vulkan builtin y preferencia
de backend. Tras reiniciar la unidad user, el bind loopback se confirmó de
nuevo. `llamacpp:vulkan` se instaló por la CLI con el daemon activo.

La carga del GGUF, API OpenAI-compatible, evidencia de offload, restart
posterior y gate final aún no se ejecutaron; el servicio no se promueve hasta
completar esas pruebas. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Gate funcional histórico

**FAIL.** El GGUF extra local no apareció en `/v1/models`. No se copiaron
modelos ni se editó JSON; la unidad user se deshabilitó y detuvo, preservando
configuración y cache. No se ejecutaron carga, chat, restart funcional ni
promoción. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Gate final histórico — 2026-08-25 17:31 CEST

**Gate final: FAIL de evidencia obligatoria; servicio user deshabilitado y
detenido. No promover.**

Esta ejecución corrigió el diagnóstico anterior de importación: el directorio
extra absoluto persistió a través de reinicios, el scanner descubrió un GGUF y
el catálogo publicó `Qwen3-1.7B-Q8_0` como modelo descargado de llama.cpp
(1.71 GiB). La configuración efectiva seleccionó
`llamacpp.backend=vulkan` y el backend administrado
`llamacpp:vulkan b10375` estaba instalado.

### Ejecución verificada

- `lemonade load Qwen3-1.7B-Q8_0 --ctx-size 2048` terminó con código 0.
  El journal confirma el contexto 2048, la resolución al GGUF extra y
  `Using LlamaCpp Backend: vulkan`.
- La primera petición no streaming OpenAI-compatible respondió HTTP 200 en
  0.395 s. Qwen3 consumió los 32 tokens disponibles en razonamiento, por lo
  que no llegó al literal solicitado; no hubo error y el resultado semántico
  fue válido conforme al criterio de smoke.
- Tras `systemctl --user restart lemond.service`, health quedó listo dentro de
  60 s, el listener volvió a ser exclusivamente `127.0.0.1:13305`, el catálogo
  conservó el modelo y una segunda petición respondió HTTP 200 en 1.758 s.
  La recarga automática usó el `ctx_size` global de 32768.
- No aparecieron OOM, reset amdgpu ni error térmico en el journal de kernel
  capturado. La temperatura edge de GPU pasó de 29 °C a 33 °C; Tctl de
  30 °C a 34.1 °C; el NVMe composite permaneció en 31.9 °C. El sensor 2 del
  NVMe ya estaba en 77.8 °C antes de la carga y no varió; sus límites expuestos
  no son físicamente fiables para usarlo como sensor de parada.
- El GTT usado aumentó de aproximadamente 18 MiB a 571 MiB tras load y a
  aproximadamente 3.87 GiB durante la recarga/chat. Esto es consistente con
  actividad GPU, pero no sustituye el gate de logs.

### Motivo exacto del FAIL

El backend bundled, con la verbosidad que Lemonade 11.7.0 fija en esta
configuración, no emitió una línea que identificase el dispositivo Radeon ni
una línea `offloaded X/X layers`. Solo se capturó la selección `vulkan`,
la carga correcta y métricas de GTT. Dado que el gate exige evidencia explícita
de **Vulkan + Radeon + offload**, no se infiere ni se promociona el offload a
partir de GTT.

Al fallar esa condición, se ejecutó `systemctl --user disable --now
lemond.service`. El estado final comprobado fue user `disabled`/`inactive`,
unidad system `disabled`/`inactive` y `Linger=no`; no quedó listener ni proceso
de servicio gestionado persistente. El código 3 de la comprobación final
corresponde al estado esperado `inactive`, no a un error de cleanup.

Los resultados se resumen aqui; rutas e identificadores privados se omiten.

## Cierre de evidencia del backend gestionado — 2026-08-25 17:42 CEST

**Gate final: PASS.** Se corrigió un falso FAIL de la orquestación anterior:
`pgrep -f llama-server` también seleccionaba el shell de inspección porque la
propia línea de comandos contenía ese texto. La comprobación final recorrió
únicamente descendientes del `MainPID` de `lemond` y exigió un único ejecutable
cuyo basename fuese exactamente `llama-server`.

### Identidad y dispositivo

- La configuración efectiva fue `llamacpp.backend=vulkan`; `llamacpp:vulkan`
  figura instalado en la versión `b10375`.
- El ejecutable administrado reside en el árbol de caché de Lemonade para
  `llamacpp/vulkan`. Su SHA-256 es
  `25672ba989ee823b39502f87a7f0c00edfeb80e9148bb12eabb1ef728655d788`
  (17 896 bytes, ELF PIE dinámico). `ldd` confirma sus bibliotecas
  `libllama*` y `libggml*` hermanas; el backend puede cargarse desde esas
  bibliotecas y no se exige una `libggml-vulkan.so` separada.
- La ejecución independiente y acotada de ese binario con `--list-devices`
  terminó con código 0 e informó `Vulkan0: AMD Radeon 8060S Graphics (RADV
  STRIX_HALO)`, con 65 258 MiB visibles y 65 082 MiB libres.
- Durante la carga hubo exactamente un hijo `llama-server` del proceso
  `lemond`, bajo el mismo usuario, con el GGUF local, `--ctx-size 2048` y
  puerto interno loopback. El health final lo identificó como
  `recipe=llamacpp`, `llamacpp_backend=vulkan`, `device=gpu`, listo y con el
  mismo PID.

### Carga, API y rendimiento

- El catálogo y `/v1/models` publicaron `Qwen3-1.7B-Q8_0` desde el directorio
  extra; `lemonade load … --ctx-size 2048` terminó con código 0. El journal
  registró el backend Vulkan, lanzó el hijo y quedó listo en menos de un
  segundo desde su inicio.
- Una petición no streaming a `/v1/chat/completions` devolvió HTTP 200 y una
  respuesta semánticamente válida. Qwen3 agotó los 64 tokens en
  `reasoning_content`, comportamiento permitido por el gate.
- La respuesta midió 108.22 tok/s de generación (0.627 s total), comparable
  con el baseline nativo Vulkan de 114.39 tok/s. La diferencia se documenta,
  pero no se interpreta como una regresión sin una campaña controlada.
- Lemonade no emitió el literal `offloaded X/X layers`. No es un requisito de
  este gate: la selección Vulkan, la enumeración directa Radeon/Vulkan del
  binario exacto, el hijo gestionado, `device=gpu`, GTT y la respuesta medida
  constituyen la evidencia adaptada de offload.

### Seguridad y estado del host

- Antes/después del chat: edge GPU 29→34 °C, Tctl 30.6→36.4 °C y NVMe
  Composite 31.9 °C. El sensor NVMe secundario fijo en 77.8 °C, con límites
  absurdos, sigue excluido como telemetría no fiable.
- GTT usado aumentó de aproximadamente 18 MiB a 575 MiB; no hubo OOM, reset
  AMDGPU ni apagado térmico en el journal capturado. La memoria disponible
  después fue aproximadamente 120.5 GiB.
- El listener HTTP final fue exclusivamente `127.0.0.1:13305`; no hubo
  wildcard para ese puerto. La unidad system siguió `disabled`/`inactive` y
  no se habilitó linger.
- El journal del `llama-server` avisa que CORS permite cualquier origen y no
  hay API key. El bind loopback limita la exposición actual; no debe exponerse
  ni reenviarse el puerto sin revisar autenticación y CORS.

Los resultados publicados arriba no requieren acceso a registros privados.

## Extensión LAN directa — 2026-08-25 18:05 CEST

**Gate LAN: PASS con advertencia de inventario SSH.** Lemonade queda accesible
directamente sólo desde la subred Wi-Fi local, sin túnel SSH, sin cambios de
router y sin exposición WAN. Se conservan el servicio de usuario, el puerto,
el catálogo y el backend existentes.

### Dirección y configuración efectiva

- La dirección IPv4 real del host Linux en `wlan0` es
  **<LAN_CIDR>**. Se configuró un bind explícito a esa dirección, no
  wildcard: `host=<HALO_HOST>`, `port=13305`, `broadcast=false`,
  `ctx_size=32768`, el directorio extra de modelos y
  `llamacpp.backend=vulkan` permanecieron sin cambios.
- Tras `systemctl --user restart lemond.service`, la unidad quedó
  `active/running` y en 5 s escuchaba solamente en
  `<HALO_HOST>:13305`; ya no existe un listener `127.0.0.1:13305`.
- El inventario local de sesión se corrigió para que su host SSH apunte al
  host Lemonade; se preservaron sus demás líneas y no se exponen sus valores.
  Esto no crea forwarding ni cambia la ruta de cliente: la URL LAN funcional
  sigue siendo `http://<HALO_HOST>:13305`.

### Firewall y alcance de red

UFW estaba activo con política de entrada `drop` y sólo permitía SSH, por lo
que se añadió exactamente la regla mínima:

```text
sudo ufw allow in on wlan0 from <LAN_CIDR> to <HALO_HOST> \
  port 13305 proto tcp comment 'Lemonade LAN TCP 13305'
```

La regla permite únicamente TCP/13305 entrante desde `<LAN_CIDR>` por
`wlan0`; no se añadió regla IPv6, wildcard, regla de router ni exposición
fuera de esa LAN.

### Clientes reproducibles y resultados

**curl**:

```text
curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  http://<HALO_HOST>:13305/v1/models

curl --noproxy '*' --connect-timeout 5 --max-time 90 \
  -H 'Content-Type: application/json' \
  --data '{"model":"Qwen3-1.7B-Q8_0","messages":[{"role":"user","content":"Reply only with LAN_OK."}],"temperature":0,"max_tokens":16,"stream":false}' \
  http://<HALO_HOST>:13305/v1/chat/completions
```

**PowerShell (incluido el terminal integrado de VS Code)**:

```text
$uri = 'http://<HALO_HOST>:13305'
curl.exe --noproxy '*' --connect-timeout 5 --max-time 15 "$uri/v1/models"
$body = @{ model = 'Qwen3-1.7B-Q8_0'; messages = @(@{ role = 'user'; content = 'Reply only with LAN_OK.' }); temperature = 0; max_tokens = 16; stream = $false } | ConvertTo-Json -Compress
curl.exe --noproxy '*' --connect-timeout 5 --max-time 90 -H 'Content-Type: application/json' --data-binary $body "$uri/v1/chat/completions"
```

**VS Code REST Client** (archivo `.http`):

```http
GET http://<HALO_HOST>:13305/v1/models

POST http://<HALO_HOST>:13305/v1/chat/completions
Content-Type: application/json

{"model":"Qwen3-1.7B-Q8_0","messages":[{"role":"user","content":"Reply only with LAN_OK."}],"temperature":0,"max_tokens":16,"stream":false}
```

Desde este PC Windows, `/v1/models` directo a `<HALO_HOST>` devolvió el
modelo existente `Qwen3-1.7B-Q8_0` (`recipe=llamacpp`, 1,71 GiB). La petición
OpenAI-compatible devolvió un objeto `chatcmpl`, con el mismo modelo y 30
tokens totales. El límite de 16 tokens terminó dentro de
`reasoning_content` (`finish_reason=length`), pero la respuesta confirma el
acceso directo y el uso del modelo existente.

El hijo gestionado actual es `llama-server` desde el árbol
`.../llamacpp/vulkan`, con el GGUF existente y contexto 32768; el journal
registró explícitamente `Using LlamaCpp Backend: vulkan` y readiness. La
comprobación final de Docker devolvió cero contenedores.

### Prueba Windows historica y contrato actual del script

**Historico del 2026-08-25:** una tarea local de VS Code lanzaba el script
con endpoint y modelo predeterminados, incluido `Qwen3-1.7B-Q8_0`. Esa tarea
no forma parte de la publicacion; se conserva aqui el resultado historico.

**Contrato del repositorio desde 2026-09-07:** `scripts\test-lemonade.ps1`
requiere `-BaseUrl` y `-Model`, sin defaults. No se necesita una extension;
invocarlo directamente desde PowerShell en la raiz, solo tras confirmar un
modelo residente y autorizar la inferencia:

```text
powershell -File scripts\test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

Sustituir el placeholder citado. El ID anterior es el baseline posterior;
no cambia el modelo pequeno usado en las mediciones historicas siguientes.

El script evita proxies, valida primero `/models` y confirma que el modelo
solicitado está publicado. Después envía una petición OpenAI-compatible a
`/chat/completions`, con timeout de 90 segundos, y termina con código distinto
de cero ante cualquier fallo. La ejecución real desde este PC Windows terminó
con `Lemonade LAN test: PASS`; confirmó ese endpoint y modelo, y recibió una
respuesta no vacía de Qwen3. En este muestreo el límite de tokens se consumió
en el razonamiento del modelo, lo que igualmente valida la conexión LAN
directa y el chat.

**Revalidación 2026-08-25 18:10 CEST:** tras el aviso de firewall, se ejecutó
de nuevo la misma tarea directamente desde Windows, sin túnel. `/models` y
`/chat/completions` respondieron con `PASS` para
`http://<HALO_HOST>:13305/v1` y `Qwen3-1.7B-Q8_0`; por tanto el puerto LAN
13305 estaba respondiendo al finalizar esta comprobación. Esta revalidación no
cambió el firewall ni el bind.

**Revalidación final 2026-08-25 18:11 CEST:** después de recargar y verificar
la regla UFW mínima por separado, se repitió la tarea desde Windows contra la
misma URL LAN directa. Volvió a terminar con `Lemonade LAN test: PASS`:
catálogo y chat respondieron para el modelo configurado. No se usó
`<HALO_HOST>` (corresponde al PC cliente), ni túneles, ni se cambió firewall
o bind durante esta prueba.

### Rollback a loopback

```text
lemonade config set host=127.0.0.1
systemctl --user restart lemond.service
sudo ufw delete allow in on wlan0 from <LAN_CIDR> to <HALO_HOST> port 13305 proto tcp
```

Después del rollback, verificar `127.0.0.1:13305` y que no permanezca un
listener LAN. Evidencia raw redactada:
`registros privados no publicados`.

No se inició, instaló ni evaluó Unsloth, QLoRA, datasets ni pasos de
entrenamiento posteriores.

## Interfaz web oficial Lemonade — 2026-08-25 18:17 CEST

**Conclusión: PASS.** Lemonade Server **11.7.0** ya incluye y estaba sirviendo
su interfaz web oficial; no fue necesario activar un flag, instalar paquetes,
reiniciar el servicio ni abrir otro puerto. La URL directa desde la LAN es:

```text
http://<HALO_HOST>:13305/
```

Es la aplicación oficial **“Lemonade Web App” / “AI Model Manager”**, no Open
WebUI ni otro cliente de terceros. La documentación oficial describe
explícitamente la GUI integrada para gestionar y probar modelos:
<https://lemonade-server.ai/docs/guide/>. La versión instalada se verificó
como `lemonade-server 11.7.0-2.1` (binarios `lemonade` y `lemond`, y
`lemonade-web-app.desktop` propiedad de ese mismo paquete); `lemonade
--version` informó `11.7.0`. El paquete desktop se identifica como
`ai.lemonade_server.webapp`, nombre “Lemonade Web App”, resumen “Web
Interface” y nombre genérico “AI Model Manager”.

La release oficial de esa versión confirma las operaciones de modelo relevantes,
incluidos `POST /v1/models/register` y opciones por modelo:
<https://github.com/lemonade-sdk/lemonade/releases/tag/v11.7.0>. La referencia
oficial de API documenta que sus extensiones sirven a clientes UI para descargar,
precargar y descargar de memoria modelos:
<https://lemonade-server.ai/docs/api/lemonade/>. Esto es distinto de
**Open WebUI** (una integración/cliente separado) y de gestores comunitarios:
ninguno se instaló ni configuró.

### Alcance real y comprobación de rutas

- El servidor `lemond` de la unidad de usuario está `active/running`,
  habilitado, y escucha exclusivamente en `<HALO_HOST>:13305`; no se cambió
  `host`, `port`, `broadcast`, contexto, directorio de modelos ni el backend.
  La configuración persistente sigue siendo `host=<HALO_HOST>`,
  `port=13305`, `broadcast=false`, `ctx_size=32768` y
  `llamacpp.backend=vulkan`.
- Desde este PC Windows, sin SSH forwarding, túnel ni proxy, `/` devolvió
  **HTTP 200**, `Content-Type: text/html`, título **“Lemonade App”** y los
  recursos `favicon.ico` y `renderer.bundle.js`. Ambos recursos estáticos se
  descargaron por LAN con HTTP 200 (126 745 y 3 384 035 bytes,
  respectivamente).
- El servidor es una SPA: `/docs`, `/redoc`, `/swagger`, `/swagger-ui`,
  `/ui`, `/web`, `/dashboard` y `/models` devuelven la misma aplicación, no un
  explorador Swagger. `/openapi.json` devolvió **404**. Por tanto, no se
  presenta Swagger/OpenAPI como una UI de gestión; la UI oficial real es la
  aplicación de raíz.
- La UI permite inventario, detalles/opciones, carga/activación, descarga e
  importación de modelos mediante las rutas de gestión de Lemonade. No se
  probó descarga ni borrado para no transferir ni modificar modelos. En
  particular, la UI no sustituye el API y no añade autenticación: el firewall
  LAN existente sigue siendo el límite de acceso.

### Validación funcional por LAN

Se realizaron solicitudes equivalentes a las operaciones de su Model Manager,
directamente desde Windows hacia la URL anterior y usando **solamente**
`Qwen3-1.7B-Q8_0`:

| Operación | Resultado |
| --- | --- |
| HTML de la UI y recursos estáticos | HTTP 200; título `Lemonade App`; `renderer.bundle.js` HTTP 200 |
| Listar modelos (`GET /v1/models`) | HTTP 200; el modelo local está presente, `downloaded=true`, receta `llamacpp` |
| Leer opciones (`GET /v1/models/Qwen3-1.7B-Q8_0/options`) | HTTP 200; backend efectivo `vulkan`, contexto resuelto `32768` |
| Activar el modelo ya local (`POST /v1/load`) | HTTP 200; `status=success`, sin pull, descarga ni cambio de opciones |
| Readiness posterior (`GET /v1/health`) | HTTP 200; versión `11.7.0`, modelo `ready`, `device=gpu`, backend `vulkan` |
| Chat OpenAI-compatible (`POST /v1/chat/completions`) | HTTP 200; una elección con `reasoning_content` no vacío; el límite de tokens terminó en `length`, sin error de inferencia |

La prueba de activación fue idempotente sobre el modelo que ya estaba cargado;
no descargó, importó, eliminó ni cambió su recipe. El proceso hijo continúa
siendo `llama-server` bajo `llamacpp/vulkan`. UFW permanece activo con la única
regla específica `[2] <HALO_HOST> 13305/tcp on wlan0 ALLOW IN from
<LAN_CIDR>`; no se añadió IPv6, wildcard, regla de router ni puerto de UI.
`docker ps -a` ejecutado en lectura como administrador no devolvió
contenedores.

### Persistencia y rollback

No se realizaron cambios remotos en esta comprobación: la UI ya venía embebida
en el paquete y se publica en el mismo listener/API existente. Por ello no hay
un flag, archivo o paquete adicional que revertir para la UI. Para retirar el
acceso desde la LAN completo (API y GUI embebida), aplicar el rollback de
loopback y UFW de la sección anterior; la raíz web dejará de ser accesible
desde Windows. No se añadió tarea de VS Code: el navegador directo es el
acceso más simple y la tarea LAN existente sigue cubriendo el API.

Los resultados necesarios se resumen en este documento; los registros privados no se publican ni son una dependencia de lectura.

## Corrección del chat de Lemonade Web App por LAN — 2026-08-25 18:30 CEST

**Causa raíz confirmada: validación de origen de Lemonade, no inferencia,
modelo, autenticación ni firewall.** Al servir la Web App desde la dirección
LAN, el navegador envía `Origin: http://<HALO_HOST>:13305`. La configuración
por defecto acepta orígenes loopback, pero el origen LAN no estaba autorizado.
El flujo real devolvía HTTP 403 con:

```json
{"error":"Origin not allowed"}
```

Los logs de `lemond` en el mismo instante registraron `Error 403: POST
/v1/chat/completions`. La reproducción con el mismo payload y cabeceras del
navegador produjo 403 tanto con el origen LAN como con el origen del PC
Windows; el mismo endpoint con `Origin: http://localhost:13305` devolvió SSE
HTTP 200. Esto descarta API key, CSRF, modelo no cargado, ruta equivocada y
Vulkan como causa. Antes de la corrección no había clave API/admin ni
`LEMONADE_ALLOWED_ORIGINS` en el entorno del proceso.

### Contrato real de la aplicación y fuente oficial

El `renderer.bundle.js` servido por la versión instalada llama
`serverFetch("/chat/completions", ...)`; en la aplicación web esto se resolvió
a:

```text
POST http://<HALO_HOST>:13305/api/v1/chat/completions
Content-Type: application/json
Origin/Referer: http://<HALO_HOST>:13305/
```

El cuerpo real observado fue JSON con `model=Qwen3-1.7B-Q8_0`, `messages` y
`stream=true`. No llevaba `Authorization` ni cookies. La configuración oficial
de Lemonade 11.7 documenta `LEMONADE_ALLOWED_ORIGINS` como una lista separada
por comas de **orígenes de la página cliente**, no de URL de destino; también
advierte contra `*`:
<https://lemonade-server.ai/docs/guide/configuration/#allowed-origins>.

### Cambio persistente mínimo

La unidad empaquetada `lemond.service` ya declara
`EnvironmentFile=-%E/lemonade/conf.d/*.conf`. Se creó únicamente este archivo,
propiedad del usuario de servicio y con permisos `0600`:

```ini
# ~/.config/lemonade/conf.d/allowed-origins.conf
LEMONADE_ALLOWED_ORIGINS=http://<HALO_HOST>:13305
```

No se usó wildcard, no se añadió el origen del cliente como si fuera servidor,
no se habilitó autenticación insegura, no se alteró UFW, bind, puerto,
backend, modelo ni configuración de entrenamiento. Fue necesario un único
`systemctl --user restart lemond.service` para que systemd reaplicase el
entorno; la recarga exige volver a activar el modelo local ya existente.

### Verificación de UI real desde Windows

Se abrió una sesión limpia de Microsoft Edge sin datos previos del sitio y se
interactuó con la Web App real, no sólo con una llamada manual:

1. La página LAN cargó `Lemonade App`, mostró
   `Qwen3-1.7B-Q8_0` como activo y el control **Send**.
2. Se escribió un mensaje en el `textarea` de la aplicación y se pulsó
   **Send**.
3. La solicitud real interceptada de la página fue el `POST /api/v1/chat/completions`
   descrito antes; devolvió **HTTP 200**, `Content-Type: text/event-stream` y
   `Access-Control-Allow-Origin: http://<HALO_HOST>:13305`.
4. La propia UI renderizó el prompt y texto/razonamiento de respuesta. La API
   directa posterior también devolvió HTTP 200.

El preflight CORS del navegador ahora responde HTTP 204, permite
`Content-Type` y devuelve el origen LAN exacto. Tras la prueba, health informó
Lemonade 11.7.0, `Qwen3-1.7B-Q8_0` `ready`, `device=gpu` y backend `vulkan`;
la unidad user quedó `active/running`, el listener sigue siendo sólo
`<HALO_HOST>:13305`, UFW conserva exclusivamente su regla LAN TCP/13305 y
`docker ps -a` privilegiado no devolvió contenedores.

### Uso, caché y rollback

operador debe recargar `http://<HALO_HOST>:13305/` con **Ctrl+F5** y usar el
chat normalmente. La sesión limpia ya demostró que no depende de caché ni
service worker. Si un perfil concreto aún conserva estado anómalo, borrar sólo
los datos de ese sitio: abrir el icono de controles del sitio junto a la URL,
**Configuración del sitio** y **Eliminar datos** para
`http://<HALO_HOST>:13305`; no borrar datos generales del navegador.

Rollback del cambio de origen (restaura la política sólo-loopback; no toca
UFW ni Vulkan):

```bash
rm ~/.config/lemonade/conf.d/allowed-origins.conf
systemctl --user restart lemond.service
```

Después del rollback, el chat LAN volverá a rechazarse deliberadamente con
403. La evidencia completa y redactada se actualizó en
`registros privados no publicados`.

## Revisión independiente de Model Manager y `pull/variants` — 2026-08-25 18:26–18:40 CEST

**Resultado: el catálogo/activación/chat para modelos compatibles pasa; no se
declara PASS para intentar instalar los repositorios Qwen incompatibles.** No
se cambió configuración, caché, paquete, servicio, backend, firewall ni
modelo. La causa no es el modelo local, Vulkan, autenticación, rate limiting,
un `model_name` Lemonade mal usado ni un registro persistido.

### Correlación de los 500 y separación de otros estados

El journal de `lemond` no registra la query string, por lo que para los cuatro
eventos históricos sólo puede afirmarse el `checkpoint` que el propio
manejador imprimió; el método/ruta, el repositorio y la respuesta están
correlacionados sin inferir un `source` que no quedó logueado. Son `GET` sin
cuerpo, no `POST /pull`, y no registraron ni descargaron modelos:

| Hora CEST | Request correlacionado | Repositorio | Respuesta/registro completo disponible |
| --- | --- | --- | --- |
| 18:26:50.596 | `GET /api/v1/pull/variants?checkpoint=Qwen/Qwen1.5-0.5B-Chat-GPTQ-Int8` | `Qwen/Qwen1.5-0.5B-Chat-GPTQ-Int8` | `ERROR in handle_pull_variants: No supported model files found ... Supported repository types: GGUF models (*.gguf), ONNX RyzenAI models, and Lemonade Omni collections ...`; seguido de `Error 500: GET /api/v1/pull/variants`. |
| 18:26:50.616 | `GET /api/v1/pull/variants?checkpoint=Qwen/Qwen1.5-7B-Chat` | `Qwen/Qwen1.5-7B-Chat` | El mismo error, con el manifiesto esperado `Qwen1.5-7B-Chat.json`; seguido de HTTP 500. |
| 18:26:50.830 | `GET /api/v1/pull/variants?checkpoint=Qwen/Qwen1.5-0.5B-Chat` | `Qwen/Qwen1.5-0.5B-Chat` | El mismo error, con el manifiesto esperado `Qwen1.5-0.5B-Chat.json`; seguido de HTTP 500. |
| 18:26:52.139 | `GET /api/v1/pull/variants?checkpoint=Qwen/Qwen1.5-72B-Chat-GPTQ-Int4` | `Qwen/Qwen1.5-72B-Chat-GPTQ-Int4` | El mismo error, con el manifiesto esperado `Qwen1.5-72B-Chat-GPTQ-Int4.json`; seguido de HTTP 500. |

No hubo `Traceback`, backtrace, token ni otra excepción adicional junto a
esas líneas: las dos líneas anteriores son el **stack/log completo emitido**
por el servicio con nivel `info`, redactado de rutas de usuario en la
evidencia. La reproducción desde Windows a las 18:36 confirmó el contrato:

```text
GET /api/v1/pull/variants?checkpoint=Qwen/Qwen1.5-0.5B-Chat
Origin: http://<HALO_HOST>:13305
```

devolvió HTTP 500 con el mismo JSON `error` y sin payload. El Browse real de
la Web App 11.7 también usa `source=modelscope`; a las 18:38 se observaron
las mismas respuestas para `Qwen/Qwen1.5-7B-Chat`,
`Qwen/Qwen1.5-0.5B-Chat` y
`Qwen/Qwen1.5-0.5B-Chat-GPTQ-Int8`. Esto demuestra una incompatibilidad real
de formato: son checkpoints Transformers/GPTQ sin GGUF, ONNX RyzenAI ni
manifiesto Omni, no un repositorio inexistente (404), un problema de CORS
(403), ni una limitación de red (429).

Los 404 históricos de 18:19 (`/openapi.json` y `/api/models`) corresponden a
rutas no expuestas, no a Model Manager. El 403 de chat de 18:32 y el de la
prueba negativa posterior son la política CORS correcta para un origen
malicioso. El chat same-origin actual devolvió 200 SSE. Una comprobación
accidental de `/api/v1/` a las 18:36 devolvió 404 y se clasifica asimismo como
ruta raíz de API inexistente, no como fallo de catálogo.

### Contrato oficial, uso correcto y alcance de la corrección

La documentación oficial 11.7 define `GET /v1/pull/variants` para inspección
de **un repositorio de GGUF** y dice que el parámetro es `checkpoint=<owner/repo>`;
el resultado ofrece las cuantizaciones para construir después un
`POST /v1/pull`. La búsqueda es un paso distinto:
`GET /v1/registry/search?...&format=gguf`. El formato es un sesgo/metadata de
catálogo; no sustituye la validación de ficheros de `pull/variants`.

El paquete Web App servido verificadamente implementa Browse como:

1. `GET /registry/search?source=modelscope&query=<texto>&limit=14&format=gguf`;
2. hasta cuatro `GET /pull/variants?source=modelscope&checkpoint=<repo>` en
   paralelo;
3. si `response.ok` es falso, devuelve `null` y **no añade** ese candidato a
   los resultados visibles.

Por tanto la UI queda estable incluso cuando ModelScope devuelve metadata
etiquetada `gguf` para un repositorio que no lo contiene. No persiste la
entrada errónea: el bundle 11.7 no contiene llamadas
`localStorage.getItem/setItem` ni `sessionStorage.getItem/setItem` para este
flujo y el servidor no tiene `~/.cache/lemonade/user_models.json`. No hubo
estado seguro que limpiar. El manejador de servidor, sin embargo, clasifica
la incompatibilidad esperable como 500; ése es un defecto de semántica/log
upstream, no corregible localmente sin parchear el paquete, acción prohibida
en esta revisión.

La ruta segura para operador es **Browse/Manual model** → seleccionar sólo una
tarjeta que haya recibido variantes → elegir la cuantización → iniciar el
pull. Para Hugging Face, el ejemplo pequeño validado es
`unsloth/Qwen3-0.6B-GGUF`: su inspección devolvió HTTP 200, receta
`llamacpp`, `Q4_K_M` y 26 variantes (Q4_K_M: 396 705 472 bytes), sin ejecutar
`POST /pull` ni descargar datos. Para Browse de ModelScope, la selección
compatible validada fue `unsloth/Qwen3-30B-A3B-GGUF`, HTTP 200, 26 variantes
y `Q4_K_M`; también fue sólo metadata, no una descarga de ese modelo grande.
No introducir los repositorios `Qwen/Qwen1.5-*-Chat`/`*-GPTQ-*` en la forma
manual como modelos llama.cpp.

La fuente oficial es la [API Lemonade 11.7](https://lemonade-server.ai/docs/api/lemonade/#get-v1pullvariants),
la guía de [modelos personalizados](https://lemonade-server.ai/docs/guide/configuration/custom-models/)
y las [release notes v11.7.0](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.7.0).
No se localizó un issue público existente con esta firma. Si se reporta, usar
el formulario upstream
<https://github.com/lemonade-sdk/lemonade/issues/new/choose> con los cuatro
repositorios y solicitar que “unsupported repository layout” sea 4xx (o que
el buscador de ModelScope descarte esos candidatos antes de sondearlos).

### Validación final y rollback

Desde Windows se validaron `/models` (200), opciones del modelo local (200,
`llamacpp_backend=vulkan`, contexto 32768), activación idempotente de
`Qwen3-1.7B-Q8_0` (200), health (11.7.0, `ready`, `device=gpu`, Vulkan),
chat same-origin (200 SSE) y origen malicioso (403). El journal desde una
marca limpia `18:39:39` quedó vacío de `pull/variants`, `Error 5xx`,
`Traceback` y excepciones durante la selección compatible de ModelScope
(HTTP 200). El journal anterior ya registra `Using LlamaCpp Backend: vulkan`
y carga correcta.

`lemond.service` permanece `active` y `enabled`, escuchando únicamente en
`<HALO_HOST>:13305`. La relectura privilegiada actual de UFW y Docker no
fue posible porque `sudo -n` exige contraseña; no se modificaron y permanece
la evidencia privilegiada de las 18:30 (UFW activo con la regla LAN mínima y
cero contenedores). No hay rollback: no se aplicó ningún cambio. Si se crea
una entrada manual incompatible por error en el futuro, no editar paquetes:
eliminar sólo ese modelo desde Model Manager/`POST /v1/delete` y volver a
empezar con un repositorio que haya devuelto variantes 200.

Los resultados necesarios se resumen en este documento; los registros privados no se publican ni son una dependencia de lectura.

## Corrección de resolución de directorio de descargas — 2026-08-26

### Causa raíz y correlación

Se reprodujo el flujo equivalente a **Model Manager → Pull** y se correlacionó
con el journal de `lemond`:

```text
Pulling model: user.Qwen3.8-27B-GGUF-UD-Q4_K_XL
Downloading model: unsloth/Qwen3.8-27B-GGUF (variant: UD-Q4_K_XL)
Failed to create directory '/usr/bin/~/ai/lemonade/models': Read-only file system
```

La configuración efectiva de Lemonade 11.7 contenía el único valor de
directorio de modelos no absoluto:

```text
models_dir = ~/ai/lemonade/models
extra_models_dir = <HOME>/ai/models/smoke
```

`models_dir` es el caché de descargas de Hugging Face/ModelScope; en cambio,
`extra_models_dir` es un directorio secundario que Lemonade escanea
recursivamente para descubrir GGUF. La documentación oficial de configuración
de 11.7 define explícitamente esta separación y permite cambiar ambas claves
en tiempo de ejecución mediante `POST /internal/set` (la CLI `lemonade config
set` usa esa configuración oficial).

El proceso y la unidad user tenían `cwd`/`WorkingDirectory=<HOME>`, mientras
que su ejecutable es `/usr/bin/lemond`. Por tanto, el prefijo `/usr/bin` no lo
aportó systemd ni fue un cambio de permisos: el resolvedor de descargas de
Lemonade trató el `~` literal como un path relativo y lo resolvió respecto a
su ubicación ejecutable. El path emitido por el error es la evidencia directa
de esa resolución; Lemonade 11.7 no expande `~` para `models_dir`.

### Cambio mínimo persistente

Se obtuvo el HOME real del usuario remoto y se creó/validó el destino
`<HOME>/ai/lemonade/models`, propiedad de dicho usuario y con modo `0755`
(el patrón existente). Había aproximadamente 1.8 TiB libres. Antes de
cambiar nada se preservó una copia de atributos del archivo afectado:

```text
<HOME>/.cache/lemonade/config.json
→ <HOME>/.cache/lemonade/config.json.bak-20260826T072912+0200 (0600)
```

El único cambio fue oficial y en tiempo de ejecución:

```text
lemonade --host <HALO_HOST> --port 13305 --no-discovery \
  config set models_dir=<HOME>/ai/lemonade/models
```

La CLI confirmó la actualización y tanto el archivo persistido como
`lemonade config` mostraron la ruta absoluta. No se requirió reiniciar
`lemond`. `extra_models_dir` se dejó en
`<HOME>/ai/models/smoke`: ya era absoluto, legible y es la ruta del GGUF
local activo `Qwen3-1.7B-Q8_0`; cambiarlo habría ocultado innecesariamente
ese modelo de descubrimiento. No quedaron valores de descarga/modelos con
`~`, rutas relativas ni `/usr/bin/~/...`.

### Pull real desde Windows y resultado

Desde Windows se ejecutó el contrato same-origin de Model Manager contra
`http://<HALO_HOST>:13305`:

1. `GET /api/v1/pull/variants?checkpoint=unsloth/Qwen3-0.6B-GGUF` con
   `Origin` LAN devolvió 200. Se eligió `UD-IQ1_S`, variante GGUF compatible
   de 214 643 392 bytes (menor de 1 GiB).
2. `POST /api/v1/pull` con
   `model_name=user.PathProbe-Qwen3-0.6B-UD-IQ1_S`,
   `checkpoint=unsloth/Qwen3-0.6B-GGUF:UD-IQ1_S`,
   `recipe=llamacpp`, `stream=true` y `subscribe=false` devolvió 200 y creó
   el job de descarga.
3. `GET /api/v1/downloads` observó progreso real de 158 022 826 bytes (73%)
   y el job terminó `completed`, 100%, con 214 643 392 bytes descargados.
   No fue necesario cancelarlo ni limpiar parciales.

El journal verificó los hashes del GGUF y de `config.json`, y publicó el
destino bajo
`<HOME>/ai/lemonade/models/models--unsloth--Qwen3-0.6B-GGUF/snapshots/<id>/`.
La consulta de archivos del API confirmó el GGUF completo (214 643 392 bytes,
propietario del usuario, modo `0644`); el directorio raíz sigue en `0755`.
Desde la corrección no aparecieron en el journal errores `read-only`,
`permission denied`, creación de directorio ni rutas `/usr/bin`.

El GGUF local preexistente no se movió ni eliminó y siguió activo como
`Qwen3-1.7B-Q8_0`; health informó `ready`, `device=gpu` y
`llamacpp_backend=vulkan`. También se verificaron `/v1/models` (200) y chat
desde Windows con `Origin` LAN (200 SSE y el CORS origin exacto). La unidad
user quedó `enabled`/`active`, con listener exclusivo
`<HALO_HOST>:13305`. Una inspección privilegiada de solo lectura confirmó
UFW activo sin cambios (SSH y la regla LAN preexistente para TCP/13305 en
`wlan0`) y `docker ps -a` vacío.

### Rollback

Para volver exactamente al estado anterior, restaurar la copia y reiniciar
solo la unidad de usuario:

```text
cp -p <HOME>/.cache/lemonade/config.json.bak-20260826T072912+0200 \
  <HOME>/.cache/lemonade/config.json
systemctl --user restart lemond.service
```

El pull de prueba terminó correctamente, así que no existe parcial que
limpiar. Si no se desea conservar el modelo de prueba completo, eliminar
**solo** `user.PathProbe-Qwen3-0.6B-UD-IQ1_S` desde Model Manager o mediante
`POST /api/v1/delete`; no borrar directorios de caché ni el GGUF activo a
mano.

Fuentes oficiales: [Server Configuration](https://lemonade-server.ai/docs/guide/configuration/),
[Custom Models](https://lemonade-server.ai/docs/guide/configuration/custom-models/)
y [Lemonade API — Pull/Downloads](https://lemonade-server.ai/docs/api/lemonade/#post-v1pull).
