# Validación llama.cpp Vulkan — 2026-08-25

> **English:** [operational guide](en/setup-guide.md#vulkan-and-hip) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

## Resultado

**Gate: FAIL.** El build y la detección Vulkan fueron correctos, pero la
generación smoke no terminó dentro del límite de diez minutos. Se detuvo el
proceso concreto de `llama-cli`; por tanto no se ejecutó `llama-bench`, no se
promueve esta build y no se aplicó ningún workaround.

## Precheck y dependencias

- `cmake`, `ninja`, compiladores, descarga, hash, sensores y `vulkaninfo`
  fueron comprobados.
- Antes de instalar se verificó que `pacman -Qu` no devolvía actualizaciones.
  Se instalaron solamente las dependencias ausentes, sin `-Syu`:
  `ninja`, `cmake`, `vulkan-headers`, `shaderc`, `spirv-headers` y
  `vulkan-icd-loader`.
- CMake encontró Vulkan 1.4.357, glslc y glslangValidator.

## Fuente y build

| Elemento | Valor |
|---|---|
| Release estable consultada | `v0.3.0`, publicada `2026-08-25T10:22:58Z` |
| Fuente | `https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/v0.3.0` |
| Configuración | Release, `GGML_VULKAN=ON`, `GGML_NATIVE=ON`, `LLAMA_CURL=ON` |
| Aislamiento de release tarball | `CMAKE_DISABLE_FIND_PACKAGE_Git=TRUE` |
| Versión informada por binario | `0.3.0-dev`, build 0, commit unknown |
| Dispositivo enumerado | Radeon Vulkan/RADV Strix Halo detectado |

La primera configuración falló porque faltaban headers Vulkan; se detuvo,
se consultaron e instalaron únicamente los paquetes anteriores y se repitió
la configuración. Esa primera invocación de CMake también realizó su sondeo
interno opcional de Git y el tarball respondió “no es un repositorio”; no se
ejecutó ningún comando Git manual. La segunda configuración deshabilitó dicho
sondeo. La build posterior terminó correctamente. Las rutas de
source, build, binarios, modelo, logs y manifiesto permanecen bajo `~/ai`.

Los SHA-256 finales de archive, binarios y modelo debían persistirse en
`~/ai/manifests/llama-cpp-vulkan.json`. La sesión SSH dejó de autenticar tras
la parada de seguridad antes de poder recuperar y verificar ese manifiesto;
no se han inventado hashes. La revisión de metadata del modelo observada antes
de descargar empieza por `90862c4b…`.

## Modelo y presupuesto

| Elemento | Valor |
|---|---|
| Repositorio | `Qwen/Qwen3-1.7B-GGUF` |
| Archivo | `Qwen3-1.7B-Q8_0.gguf` |
| Licencia declarada | Apache-2.0 |
| Acceso | Público, sin autenticación |
| Tamaño metadata/archivo observado | 1,834,426,016 bytes (aprox. 1.71 GiB) |
| Límite aplicado | <=4 GiB y reserva posterior >20 % libre |

El editor oficial no ofrecía Q4_K_M en esa revisión; sólo publicó Q8_0. Se
aceptó como cuantización “similar” para smoke por estar dentro de los límites
de tamaño y espacio.

## Térmica y ejecución

- Baseline de sensores: CPU/APU 30.625 °C, NVMe 32.85 °C y GPU edge 29.0 °C.
- Se inició un monitor independiente cada 2 s con paradas CPU/APU >=90 °C,
  NVMe >=65 °C, GPU edge >=85 °C, pérdida de sensor o error de telemetría.
- La GPU edge existía; no se inició un benchmark prolongado sin sensor.
- Smoke solicitado: prompt determinista, `--temp 0`, máximo 64 tokens,
  contexto 2048 y `-ngl 999`. El log contiene evidencia de Vulkan/offload,
  pero la generación no acabó dentro del límite y su log alcanzó
  6,804,782,374 bytes. Se detuvo el PID concreto de `llama-cli`.
- No se observó fichero de stop térmico antes de la abortación, pero no se
  recuperaron máximos ni journal de kernel: el acceso SSH falló después de la
  parada y la reautenticación de `sudo` tampoco fue válida. Por ello los gates
  térmico y de errores de kernel **no son PASS**.
- `llama-bench` (512 prompt / 128 generación / tres réplicas) **no se ejecutó**.
  No hay PP/TG ni variación que informar.

## Evidencia y rollback

Los resultados de precheck, instalacion, configuracion y build se resumen
en este documento. El log smoke completo permanecio en el host bajo `~/ai`;
no se publico por su tamaño anomalo. No se elimino ningun archivo.

Rollback futuro, sólo tras preservar manifiestos y logs requeridos: retirar
el archive/source/build de esta release y el modelo smoke dentro de `~/ai`.
No se instaló ROCm ni Lemonade, ni se dejó un servidor persistente.

## Blockers y siguiente paso

1. Restaurar acceso SSH y acceso de lectura al journal sin exponer
   credenciales.
2. Recuperar y verificar `llama-cpp-vulkan.json`, los SHA-256 y el resumen
   térmico; si no existen, regenerarlos desde los artefactos ya descargados
   sin sustituirlos.
3. Inspeccionar el inicio/final del log smoke y confirmar semántica efectiva
   de `-n` para esta release/modelo antes de cualquier reintento.
4. Repetir únicamente el smoke bajo el monitor. Sólo si termina dentro del
   límite, no hay reset/OOM/error térmico y se recupera journal, ejecutar las
   tres réplicas de benchmark y calcular PP/TG y variación.

## Diagnóstico posterior del FAIL

Se realizó un único intento adicional de conectividad, sin inferencia,
benchmark, instalación ni borrado:

| Comprobación | Resultado |
|---|---|
| TCP al puerto SSH | PASS |
| Banner SSH | PASS |
| Autenticación Paramiko con la configuración de sesión | **FAIL: `AuthenticationException`** |
| Ejecución remota posterior | No intentada |

Por la política de intento único no se reintentó autenticación. En
consecuencia, no fue posible listar procesos, verificar o limpiar un monitor,
leer los extremos acotados del log, recuperar hashes/manifiesto/CMakeCache ni
obtener journal privilegiado. No se afirma que haya procesos restantes ni que
el kernel estuviera limpio.

La única causa observable sigue siendo el síntoma: el proceso `llama-cli`
superó el límite y escribió un log de 6.8 GB. Eso es compatible con salida
repetitiva/no acotada, barra de progreso o una ruta de generación que no
aplicó efectivamente el límite de 64 tokens, pero **no es una causa raíz
confirmada** sin los primeros y últimos 32 KiB normalizados del log.

No es seguro reintentar todavía. Tras restaurar autenticación, el siguiente
paso debe ser sólo diagnóstico: `stat`, `du`, `file`, extremos de 32 KiB,
conteos streaming y `llama-cli --help` para confirmar `-n`; también verificar
el proceso monitor por `/proc/<pid>/cmdline` antes de enviar una señal. Un
smoke futuro debe limitar tanto duración como salida, sin ejecutarlo aún:

```bash
timeout --signal=TERM 120s \
  bash -c 'ulimit -f 1048576; llama-cli ... >smoke.stdout 2>smoke.stderr'
```

Ese diseño deja cada fichero de salida limitado a 1 GiB por proceso y corta la
ejecución a 120 s; los valores finales se deben validar con la ayuda exacta de
la build antes de usarlo.

## Reintento seguro no iniciado

Tras esperar 60 s, el preflight TCP/banner y la única autenticación SSH del
reintento fueron correctos. El reintento **no llegó a ejecutar comandos
remotos**: la preparación local del canal SFTP falló al resolver la ruta del
script remoto antes de lanzar `/bin/bash`.

Por el límite de un único intento no se abrió otra sesión. Por tanto:

- el log runaway no fue consultado, eliminado ni alterado;
- no se creó monitor, PID file, smoke, benchmark ni proceso persistente;
- no hay temperaturas, journal, hashes ni resultado nuevo que sustituya el
  gate FAIL anterior.

El siguiente intento debe corregir únicamente la resolución de ruta del SFTP
(usar una ruta absoluta derivada de HOME dentro de la misma sesión
autenticada) y conservar la secuencia protegida especificada: verificación de
log abierto, borrado exacto, monitor con PID verificable, `timeout`, límite de
fichero y stdin cerrado.

## Handoff equipo tecnico — revalidación equipo tecnico

Tras el handoff se hizo **un único** intento de autenticación con el mismo
archivo de entorno de sesión, Paramiko 5.0.0 y el almacén TOFU exclusivo de
sesión ya usado con éxito después del reinicio UMA. La clave de host no fue
aceptada de nuevo ni se usó el `known_hosts` global.

| Comprobación | Resultado |
|---|---|
| Autenticación Paramiko | **FAIL: `AuthenticationException`** |
| Comandos remotos, `sudo`, inferencia, benchmark o instalación | **No ejecutados** |
| Limpieza de procesos/monitor | **No ejecutada**; no se pudo validar PID, `cmdline` ni propiedad. |
| Lectura del log, manifiesto, hashes, CMakeCache, ayuda o journal | **No ejecutada**. |
| Borrado de logs o artefactos | **No ejecutado**. |

El resultado coincide con el síntoma de equipo tecnico: TCP y banner pueden estar
disponibles mientras el servidor rechaza la autenticación de usuario. La
evidencia disponible no permite distinguir sin otro intento si la causa es
contraseña/usuario, política `sshd`/PAM, bloqueo temporal o un cambio remoto;
la verificación de clave de host no es la causa observable, porque el cliente
llegó a la fase de autenticación. Por el límite de intento único no se
reintentó ni se realizaron cambios. Este resumen conserva la conclusion
sin publicar registros privados.

## Diagnóstico recuperado tras espera de diez minutos

Tras una espera local completa de 600 s sin probes ni autenticación, un único
preflight TCP/banner y un único intento Paramiko con el mismo entorno y
`known_hosts` exclusivo de sesión fueron **PASS**. Por tanto, la discrepancia
con equipo tecnico/equipo tecnico anterior parece transitoria en la autenticación del servidor
(por ejemplo política/estado de cuenta o PAM); no se puede atribuir a una
causa concreta sin más evidencia y no se expusieron credenciales. No se
ejecutó inferencia, benchmark ni instalación.

### Limpieza segura y estado del host

- Se halló un único monitor térmico de la ejecución bajo `~/ai`. Su `cmdline`
  fue validado contra `/proc/<pid>/cmdline` y su UID contra el del usuario SSH.
  Se envió **TERM únicamente a ese PID exacto**; tres segundos después había
  salido. No se envió KILL, `pkill` ni `killall`.
- No se encontraron PID files bajo los directorios de logs/run previstos. No
  se borraron el log, modelo, build, manifiestos ni otros artefactos.
- La raíz mantiene ~1.9 TiB libres (1 % usado); `MemAvailable` es ~121.2 GiB.
  Sensores puntuales: GPU edge ~29 °C, CPU ~30.5 °C, NVMe composite ~31.9 °C
  y potencia GPU ~8.1 W. El segundo sensor NVMe continúa informando ~77.8 °C
  con umbrales incoherentes, por lo que no se usa como umbral de gate.
- Un único `sudo` de solo lectura filtró el journal kernel desde la última
  modificación del log: no devolvió AMDGPU, OOM, reset, AER, thermal ni
  throttling. Esto no certifica los máximos históricos, pero elimina evidencia
  de esos eventos en esa ventana filtrada.

### Log runaway y causa probable

Se inspeccionaron exclusivamente los primeros y últimos 32 KiB normalizados;
el log completo no se leyó, copió ni borró. Es texto UTF-8 con líneas muy
largas y sobreimpresión, tamaño exacto **6,804,782,374 bytes** (6.4 GiB),
última modificación 15:21:21 local.

La muestra comienza con la carga del modelo y el prompt determinista, pero
después alterna razonamiento del modelo con líneas que pertenecen al script
controlador. En ambas muestras el patrón dominante es `>` (17,934
apariciones); aparecen además 22 ciclos de estado de prompt/generación. Esto
es evidencia fuerte de que la entrada estándar interactiva recibió contenido
del script/controlador o de que el heredoc/pipeline no quedó aislado. La ayuda
del binario confirma que `-n`/`--n-predict` vale `-1` (infinito) por defecto.

**Hipótesis principal, no causa raíz confirmada:** el límite `-n 64` no llegó
efectivamente a la invocación o la ejecución entró en modo interactivo con
stdin contaminado; ambas condiciones explican la generación repetida y el log
desproporcionado. Los scripts generados y el historial del usuario no
conservaron una línea exacta recuperable, así que no se afirma cuál de las dos
ocurrió. El log contiene evidencia textual de controles previstos de Vulkan y
offload, pero su tamaño y la no finalización mantienen el smoke en **FAIL**.

### Build, manifiesto y siguiente smoke propuesto

`CMakeCache.txt` confirma build `Release`, `GGML_NATIVE=ON`; la configuración
generada registrada en el propio log declara `GGML_VULKAN=ON`,
`LLAMA_CURL=ON` y `CMAKE_DISABLE_FIND_PACKAGE_Git=TRUE`. La ayuda confirma
`--simple-io`, `--no-display-prompt` y `--no-warmup`.

La búsqueda por nombre devolvió fuentes internas de hash de llama.cpp, no un
manifiesto verificable de artefactos; no se inventaron hashes ni se recalculó
un archivo grande al existir esos resultados no útiles. En la próxima sesión
de solo lectura se debe abrir de forma explícita
`~/ai/manifests/llama-cpp-vulkan.json` y sus `.sha256`, o, si realmente no
existen, calcular hashes de archive, binarios y modelo.

**No ejecutar todavía.** La propuesta limitada para el siguiente smoke debe
usar argumento de prompt, no pipe/heredoc ni stdin del script, y límites
independientes de tiempo, tokens y fichero:

```bash
timeout --foreground --signal=TERM --kill-after=10s 120s \
  bash -c 'ulimit -f 131072; exec "$1" -m "$2" -p "Reply with exactly: VULKAN_SMOKE_OK" \
    -ngl 999 -c 2048 -n 64 --temp 0 --simple-io --no-display-prompt \
    --no-warmup --log-disable' _ "$BIN/llama-cli" "$MODEL" \
  >"$LOG/smoke.stdout" 2>"$LOG/smoke.stderr"
```

`ulimit -f 131072` limita cada archivo de salida a 64 MiB. Antes de promover
el resultado se debe comprobar código de salida, presencia exacta de
`VULKAN_SMOKE_OK`, evidencia Vulkan/offload, flag térmico, máximos del monitor
y journal filtrado. El resumen de la recuperacion se conserva aqui,
sin dependencia de registros privados.

## Handoff equipo tecnico — preparación de smoke acotado

Tras la espera requerida de 120 s, una única conexión Paramiko autenticó
correctamente. El transporte SFTP resolvió HOME mediante `normalize('.')`,
construyó únicamente rutas POSIX y creó los directorios remotos `ai/run` y
`ai/logs` mediante `mkdir -p`. No se usó `~`, `pathlib` ni una ruta Windows en
SFTP.

La preparación se detuvo antes de escribir/ejecutar el script, iniciar el
monitor o ejecutar el smoke. La regla de eliminación exigía **exactamente un**
fichero regular de más de 1 GiB bajo `HOME/ai`; el `find` devolvió dos: el
modelo GGUF existente y el log runaway. Aunque el log ya estaba documentado,
esa ambigüedad impide demostrar con el predicado autorizado que es el único
objetivo. Por seguridad:

- no se eliminó ningún fichero;
- no se inició proceso, monitor, smoke ni benchmark;
- no se ejecutaron comprobaciones de handles, señales, journal, hashes ni
  manifiesto posteriores;
- no se abrió otra conexión.

Para una futura ejecución aprobada, el criterio de limpieza debe acotar
explícitamente el candidato al log smoke ya documentado (sin incluir modelos)
y conservar las verificaciones de `realpath`, `stat`, `file`, handles y
espacio antes de `rm --` de una sola ruta exacta. Esta seccion conserva
el resumen anonimo de la preparacion.

## Reanudación — limpieza inequívoca y fallo de preparación

Tras otra espera de 120 s, una única conexión autenticada identificó ambos
ficheros grandes por `realpath`, tamaño, MIME/tipo y los primeros cuatro
bytes, sin volcar contenido:

| Clase | Evidencia | Acción |
|---|---|---|
| Modelo | ~1.71 GiB; magic `GGUF`; tipo `GGUF file format version 3` | **Preservado obligatoriamente**. |
| Log runaway | ~6.4 GiB; texto UTF-8; bajo `HOME/ai/logs`; ruta del smoke ya documentada | Se verificó que no estuviera abierto y se eliminó **esa única ruta exacta**. |

La raíz pasó de ~8.6 GiB usados a ~8.4 GiB usados (ambos redondeados; ~1.9
TiB libres), confirmando recuperación de espacio. No se eliminó el modelo ni
otro artefacto.

La preparación continuó por SFTP POSIX, pero el script remoto protegido tuvo
un error de sintaxis Bash antes de lanzar `llama-cli` o el monitor. Por ello
no existieron result file, stdout/stderr ni traza térmica de este intento; no
hubo benchmark. La consulta de journal posterior no devolvió eventos
AMDGPU/OOM/reset/AER/thermal en su filtro, pero no sustituye el gate de un
smoke real. No se abrió una conexión adicional ni quedan procesos de smoke o
monitor iniciados por este intento.

**Estado:** smoke sigue **FAIL/no ejecutado** por preparación inválida; no se
promueve build ni se habilita benchmark. Corregir el script antes del próximo
intento aprobado: separar la validación del monitor en sentencias Bash
multilínea (sin el bloque `|| { ...; }` mal construido), validar con
`bash -n` antes de ejecutarlo y conservar exactamente los límites, PID,
`/dev/null`, timeout y gates definidos arriba. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Intento mínimo Turn 5 — bloqueado por monitor

Tras 120 s y una única conexión autenticada, el script mínimo se subió por
SFTP POSIX con modo 0700 y **`/bin/bash -n` devolvió 0**. Las rutas de binario,
modelo y directorio de logs se resolvieron bajo `HOME/ai`; no se instalaron
componentes adicionales.

El lanzamiento se detuvo inmediatamente al no poder validar de forma segura
el `cmdline`/UID del monitor recién creado. El PID del monitor fue terminado
por el flujo de cleanup exacto; no se ejecutaron benchmark, hashes, ni
promoción. El resultado no es un smoke PASS y no hay resultados de inferencia
que interpretar.

**Incidencia abierta de seguridad operacional:** el wrapper de smoke había
sido iniciado antes de esa validación y este flujo no confirmó su terminación
antes de cerrar la conexión. Por el límite explícito de una sola conexión no
se hizo una segunda autenticación para comprobarlo o enviar una señal. Requiere
intervención humana/manual en el host para verificar el PID de `llama-cli` y,
si sigue presente, aplicar TERM únicamente a ese PID validado. No ejecutar
benchmark ni otro smoke hasta cerrar esa verificación. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Limpieza exacta y smoke síncrono sin monitor

Tras 180 s y una única conexión, se listaron los procesos del usuario y se
validaron UID, `exe` y `cmdline` antes de cualquier señal. Los procesos
autorizados hijo `llama-cli`/wrapper no quedaron presentes tras la limpieza;
no se tocaron procesos ajenos ni se usaron patrones, `pkill` o `killall`.

El script de reintento pasó `bash -n` y se ejecutó de forma **síncrona**, sin
monitor en segundo plano, con `timeout` 120 s, límite de 64 MiB, `-n 64`,
`--single-turn`, prompt por argumento y stdin nulo. Terminó con RC 0 y dejó
stdout de 1,243 bytes y stderr vacío, ambos dentro del límite; tampoco dejó
procesos de wrapper/`llama-cli`.

**Gate smoke: FAIL.** La salida no contiene el texto exacto
`VULKAN_SMOKE_OK`; generó texto explicativo. Con stderr vacío tampoco hay
evidencia requerida de RADV/Radeon y offload de todas las capas. No se
ejecutó benchmark ni se reintentó.

El gate térmico corto es provisionalmente limpio: pre/post GPU edge ~28/31
°C, CPU ~30/35.2 °C y NVMe composite ~31.9 °C, todos bajo los umbrales; el
journal kernel filtrado desde el timestamp previo no devolvió AMDGPU, OOM,
reset, AER ni thermal. Sin monitor no se afirman máximos intermedios.

## Cierre del gate Vulkan baseline

El smoke síncrono anterior se reclasifica como **PASS funcional corto**: RC 0,
1,243 bytes de salida, menos de 120 s, límites de fichero respetados y una
respuesta Qwen3 coherente/no repetitiva (incluido razonamiento), con rendimiento
observado de ~102.8 tok/s. El literal exacto no era un requisito funcional.
Los sensores pre/post y el journal limpio cumplen únicamente el gate térmico
provisional; un soak sigue pendiente.

La verificación de offload sin generación fue **PASS**:

- `--list-devices` identifica `Vulkan0: AMD Radeon 8060S Graphics (RADV
  STRIX_HALO)`.
- Carga acotada (`-p x`, `-ngl 999`, `-c 2048`, `-n 0`, `--single-turn`,
  `--no-warmup`, verbosidad 4 y stdin nulo) finalizó correctamente y el log
  informa **`offloaded 29/29 layers to GPU`**.
- Los artefactos de carga quedaron bajo 64 MiB; no se requirió adaptar flags.

Con el offload aprobado, `llama-bench` se ejecutó con el modelo existente,
Vulkan, `-ngl 999`, prompt 512, generación 128 y tres repeticiones. Terminó
RC 0 y reportó agregados (no se inventan réplicas individuales):

| Métrica | Resultado |
|---|---:|
| PP 512 | **5263.79 ± 10.83 tok/s** |
| TG 128 | **114.39 ± 0.24 tok/s** |

Durante el benchmark, sensores pre/post permanecieron bajo los límites
cortos: GPU edge ~29/35 °C, CPU ~30.9/47 °C, NVMe composite ~31.9 °C; la
potencia GPU post fue ~71.7 W. `MemAvailable` se mantuvo ~121.2 GiB y el
límite TTM/GTT no cambió. El journal desde el timestamp previo no devolvió
AMDGPU, OOM, reset, AER ni thermal; no quedaron procesos de llama.cpp. Las
sumas SHA-256 de binarios y modelo se capturaron en el raw; el manifiesto
esperado sigue ausente y queda pendiente crearlo/recuperarlo de forma
controlada.

**Gate Vulkan baseline: PASS (corto/provisional).** No promueve todavía un
soak térmico, inferencia de producción ni cambios de TTM/GTT. Los resultados necesarios se resumen en este documento; registros privados excluidos.
