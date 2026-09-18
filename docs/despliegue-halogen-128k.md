# Despliegue en el Halo: Halogen 128K y llama-swap

[English](en/halogen-128k-deployment.md) |
[Workspace](../workspaces/inference/README.md) |
[Continuación inicial](continuacion-en-halo.md) |
[Estado documental](estado-proyecto.md)

**Registro de intervención: 2026-09-17.** Resume el trabajo iniciado con el
checkout `a9a6e3f`, el preflight y las actuaciones autorizadas de septiembre
16-17. Las fechas de archivos privados y relojes de distintas sesiones no se
usan para construir una cronología de segundos común. Son observaciones
fechadas, no monitorización permanente ni una receta universal.

No sustituye el baseline histórico de Lemonade del 4 de septiembre ni cierra
el 403 histórico, el incidente SSE o los ensayos anteriores. No se publican
logs crudos, direcciones privadas, usuarios, credenciales, configuraciones de
agentes ni el contenido de `data/`. Los ejemplos siguientes son sanitizados.

## 1. Resultado y alcance

**Actualización posterior del mismo día:** el perfil C ya está aplicado con
cuatro slots y pool KV 524288. La sección 10 añade sus pruebas y una revisión
de logs; las secciones anteriores conservan las etapas de un slot y sus
medidas originales. No se ejecutó una nueva carga para revisar estos logs.

| Capa | Estado al cierre de la intervención |
| --- | --- |
| Hardware | Halo real confirmado, Linux nativo y GPU `gfx1151` |
| llama-swap | v255, servicio de usuario habilitado y activo |
| Modelo servido | Solo `flash-halogen`, Halogen W4B Quality, contexto 131072 |
| Salida | Máximo configurado 8192, compartiendo contexto con la entrada |
| Paralelismo | Perfil C: cuatro slots, pool KV 524288, concurrencia global y por modelo 4; inicialmente un slot/pool 131072 |
| Lemonade | 11.9.0 conservado; servicio de usuario deshabilitado e inactivo |
| Coder Vulkan | Probado a 32K y 128K; retirado del catálogo activo, no borrado del disco |
| Cockpit | TUI instalada y utilizada; no controla el contenedor gestionado final |
| Red final | HTTP en una dirección LAN autorizada, TCP/18080, sin API key por petición expresa |
| TLS | Probado localmente con certificado de ensayo y luego retirado; no desplegado en LAN |
| Arranque | `linger` ya activo; servicio configurado para iniciar sin login, sin reinicio del host probado |

**Implementado**: control de runtimes, adaptador Cockpit, perfiles, publicación
de límites, pruebas y ejemplos. **Probado offline**: validaciones y gateway
real con backend sintético. **Validado en el Halo**: carga GPU, chat/SSE,
herramientas, alternancia y pruebas largas descritas abajo. La configuración
privada del servicio no se instala automáticamente al clonar el repositorio.

## 2. Preflight observado, no supuesto

- GMKtec EVO-X2, Ryzen AI Max+ 395, Radeon 8060S, `gfx1151`.
- BIOS EVO-X2S 1.13; kernel `7.2.5-1-cachyos`; RADV Mesa `26.2.2-arch3.2`.
  `vulkaninfo --summary` y `rocminfo` reconocieron la GPU.
- Aproximadamente 123,5 GiB de RAM visible, 2 GiB de VRAM y 61,73 GiB de GTT.
  Al inicio había unos 121 GiB disponibles y 1,28 TiB de disco libre.
- `/dev/kfd` y el nodo render eran accesibles; se observaron permisos amplios
  existentes. No se crearon reglas de dispositivos ni cambios UMA/GTT/IOMMU.
- Docker/Compose 29.8.0/5.5.1. Primero faltaban GitHub CLI y acceso al socket;
  después se instaló/autenticó `gh` y se añadió el operador al grupo Docker.
  Una nueva sesión o `newgrp docker` fue necesaria para renovar los grupos.
- Lemonade 11.9.0 devolvía HTTP 200, sin residentes ni pins. Había conexiones
  de clientes: servicio sin modelos no equivale a ventana reservada.
- La configuración real estaba bajo `$HOME/.config/lemonade/`, incluidos
  `config.json`, `recipe_options.json` y `user_models.json`, no en la ruta
  histórica de caché. Se respaldaron configuración, unidades y respuestas de
  catálogo/salud/configuración efectiva en privado, verificando hashes.

Ejecutar el workspace con `sudo` cambia la identidad y hace fallar la exigencia
de propietario y modo 0700. No resolverlo con `chmod 777` ni cambiando el dueño
de `data/`. El grupo Docker da autoridad equivalente a root sobre el host.

## 3. Artefactos y correcciones de compatibilidad

| Artefacto | Referencia comprobada |
| --- | --- |
| llama-swap | v255, commit informado `7761aa1`; archivo y binario contrastados con el SHA256 fijado por el instalador |
| Cockpit | `6959d068c020f3f33bfb8ef743e7ba44a6390dda`, versión 2026.9.16.1218 |
| Toolbox Vulkan | `docker.io/kyuz0/amd-strix-halo-toolboxes@sha256:c96266e8b29164f37e82b6b8a31f1ca4a044dc0b0c77c7ea5fefc861c9b541ef` |
| llama.cpp de esa imagen | build 11011, commit `aa39d7a3e`, versión informada 0.4.1-dev |
| Halogen | `ghcr.io/peonist-ai/halogen-flash-server@sha256:760691880fecbf07f25e6b067cb5cc70e6a9ae11f280ca4725d3878e68821bd2`, versión 0.11.3 |

La revisión `8215baa74dab` anunciada por la imagen Halogen no pudo resolverse
por la API de GitHub. Se extrajo e inspeccionó su entrypoint sin arrancar GPU;
la documentación upstream consultada por separado no se presenta como fuente
exactamente emparejada con ese commit. No se recompiló el motor cerrado.

Correcciones incorporadas al workspace:

1. La imagen Vulkan rechaza `--no-mmap`. `load_mode: "none"` selecciona
   `--load-mode none`; omitirlo conserva el contrato de builds anteriores.
2. Cockpit pasaba los nombres `video` y `render` a Docker. La imagen Halogen
   no define `render`: se reprodujo el fallo con `/bin/true`, sin GPU ni pesos.
   El adaptador del launcher sustituye esos nombres por los GID de los
   dispositivos del host, sin modificar el código instalado de Cockpit.
   La adaptación está limitada a la topología inicial de GPU única.
3. Reducir Context a 32768 y Slots a 1 dejaba **KV Pool en 524288** en la TUI.
   Se configuró el pool explícitamente antes del primer arranque correcto.
4. Los perfiles admiten `halogen_overlay`, `halogen_tokenizer` y
   `halogen_max_tok`, con validación de rutas relativas, contención de symlinks,
   existencia de `tokenizer.json` y límites de la arena de prefill.
5. El generador publica contexto y presupuesto de salida en el catálogo.

La instalación de Cockpit resolvió dependencias en un venv y conservó su
manifiesto privado. `pip check` pasó; el aviso de que `huggingface_hub` ya no
ofrece el extra `cli` no impidió instalación ni descarga. No se promete una
resolución transitiva reproducible byte a byte.

## 4. Modelos, memoria y pruebas reales

Coder reutilizó el GGUF Q4_K_M existente, 18556689568 bytes, con cabecera GGUF
válida y SHA256 local guardado; ese hash no se contrastó independientemente
con un checksum upstream. Se probó inferencia directa, luego gateway, auth,
UI, SSE, herramientas con argumentos y respuesta posterior, cancelación del
cliente, descarga y recuperación de memoria. Reiniciar Lemonade recuperó su
estado observado sin residentes; después se retomó Docker. Su configuración
original se conservó byte a byte durante ese rollback.

Cockpit descargó el bundle **W4B Quality**: ocho archivos, 117,88 GiB, HGN,
overlay y tokenizer. Se verificaron tamaños y completitud según su catálogo,
no hashes integrales de los 118 GiB. El sidecar de visión no estaba descargado;
no se anuncia soporte visual validado. Descargar la imagen no descarga pesos.

Primera carga Halogen: contexto/pool 32768, un slot, arena 32768. El motor
informó unos 68 GiB de pesos registrados, 0,9 GiB KV y 21 GiB de trabajo,
89,9 GiB en conjunto. Chat directo respondió en aproximadamente 1,8 s.
Después se migraron los artefactos explícitos al control exclusivo de
llama-swap y se verificó Halogen → Coder → Halogen, SSE y herramientas reales.

**Corrección de la estimación inicial:** comparar directamente 68 GiB de pesos
registrados con 61,73 GiB de GTT no bastaba para declarar imposible la carga.
Halogen registra mappings de pesos; se observó arranque correcto sin ampliar
GTT. A la inversa, `MemAvailable` sobreestima el margen cuando contabiliza
pesos registrados como caché recuperable. Se usan diagnósticos del motor,
memoria del driver, presión y comportamiento real, no una sola cifra.

### Ampliación a 128K

Se conservaron salida 8192 y concurrencia 1. Halogen pasó a contexto/pool
131072 y arena de prefill **16384**: aproximadamente 68 GiB de pesos,
3,6 GiB KV y 12,2 GiB de trabajo, **83,7 GiB totales** y unos 30,2 GiB restantes
según el diagnóstico de arranque. Menor arena reduce memoria de trabajo;
no reduce la ventana de conversación ni el presupuesto de salida.

| Ensayo sintético SSE | Entrada real | Salida real | Primer contenido | Total |
| --- | ---: | ---: | ---: | ---: |
| Halogen | 105074 tokens | 34 tokens, 27 de razonamiento | 77,63 s | 77,73 s |
| Coder Vulkan | 120033 tokens | 6 tokens | 1452,46 s | 1452,81 s |

Ambos devolvieron la clave de control del comienzo y `[DONE]`. Se usó el mismo
texto repetitivo; los tokenizadores produjeron cantidades distintas. No es
benchmark causal de motores equivalentes, ni calidad de recuperación general,
ni validación de la ventana completa 131072, ni soak. Coder resultó demasiado
lento en ese caso largo y se retiró por decisión del operador, conservando
pesos, imagen y backups. Solo Halogen permanece en el catálogo final.

## 5. Contexto publicado y clientes

`/v1/models` devuelve para Halogen:

```json
{
  "id": "flash-halogen",
  "context_length": 131072,
  "context_window": 131072,
  "meta": {
    "n_ctx": 131072,
    "llamaswap": {"max_output_tokens": 8192, "type": "model"}
  }
}
```

Llama-swap v255 transforma `capabilities.context` y `metadata` en esos campos.
Los tests comprueban la respuesta del binario real, no solo el JSON generado.
Publicarlos no recorta `max_tokens`. A 32K se rechazaron entradas de 24732 y
25188 tokens con salida solicitada 8192: entrada, herramientas, historial,
razonamiento y respuesta comparten la ventana.

Publicar límites no eliminó el problema en el cliente del operador. Se revisó
código upstream de OpenCode, no su versión/configuración remota efectiva.
Se prepararon fragmentos privados, sin sustituir archivos del equipo cliente:

- OpenCode: modelo `halo/flash-halogen`, contexto 131072, límite de entrada
  122880, salida 8192, compactación automática y poda activadas.
- Crush: ventana de cliente conservadora 122880, salida principal 8192,
  resumen 4096, auto-resumen activo. Modelo principal y de resumen Halogen,
  evitando cambiar de motor durante compactación. Discovery desactivado en
  ese fragmento para fijar el margen explícito.

La sintaxis del fragmento Crush fue comprobada; ni esto ni el catálogo prueban
compactación automática end-to-end en un equipo remoto. Resultados de
herramientas muy grandes aún pueden desbordar la ventana. Incorporar estos
ajustes privadamente y no reemplazar configuraciones enteras.

## 6. Red y excepción de laboratorio

El diseño público continúa siendo loopback con claves y frontal TLS filtrado.
Durante la intervención se probaron un certificado temporal para localhost,
validación de confianza/nombre, inferencia HTTPS y rechazo de claves erróneas
y rutas administrativas; el frontal de ensayo fue retirado. No se desplegó
TLS LAN ni se instaló una CA en clientes remotos.

Después el operador pidió acceso HTTP directo a la UI desde la LAN y quitar
la API key. La configuración privada final escucha en `<HALO_LAN_IP>:18080`,
con regla UFW TCP limitada a `<LAN_CIDR>` hacia esa dirección. UFW no se
desactivó; el operador aplicó la regla desde su terminal cuando la herramienta
no permitía ese comando. Se confirmó acceso desde otro equipo.

**Es una excepción aceptada para este laboratorio, no un default seguro:**
HTTP no cifra prompts ni respuestas; todo equipo admitido por la regla puede
inferir y administrar el gateway sin contraseña. No se realizó una auditoría
de NAT/router ni se garantiza ausencia de exposición externa a partir de una
regla local. Las claves anteriores se conservaron en privado para rollback.
El generador público sigue creando configuración autenticada y `start.sh`
sigue seleccionando la configuración estándar loopback; el servicio real
utiliza un launcher privado distinto. No ejecutar ambos simultáneamente.

## 7. Persistencia, operación y rollback

Los primeros gateways dependían de una sesión: sus logs mostraron señal de
interrupción y cierre limpio cuando la UI dejó de responder. Se sustituyó ese
arranque por **`llama-swap.service` de usuario**, enlazado a una unidad privada
bajo `data/` y habilitado en `default.target`. `linger` ya estaba activo.

Propiedades aplicadas: `Restart=always`, `RestartSec=10`,
`StartLimitIntervalSec=0`, `TimeoutStartSec=30`, `TimeoutStopSec=120`,
`KillMode=control-group`, `UMask=0077`, directorio de trabajo privado.
`ExecStartPre` comprueba Docker; `ExecStopPost` detiene únicamente el contenedor
Halogen con etiqueta de propietario mediante `runtime.py stop`. El launcher
preserva 128K, la dirección LAN y la excepción sin clave. No incluye secretos
en argumentos de procesos.

El gestor de usuario conservaba grupos anteriores a la autorización Docker.
`sg` no estaba instalado; se verificó `/usr/bin/newgrp docker -c` y se usó
para los comandos del servicio. No se ejecuta el gateway como root ni se
relajan permisos del socket. Docker de sistema estaba habilitado; si Docker
o la IP aún no están disponibles durante arranque, el servicio reintenta.
Revisar el journal si persiste ese bucle.

`lemond.service` de usuario quedó **disabled/inactive**; la unidad de sistema
ya estaba deshabilitada. No se desinstaló ni se enmascaró Lemonade: todavía
puede iniciarse manualmente. Antes de hacerlo, parar llama-swap y comprobar
que sus contenedores han salido y liberado memoria.

Comandos de operación desde una terminal del operador, sin sudo:

```bash
systemctl --user status llama-swap.service
journalctl --user -u llama-swap.service -n 100 --no-pager
systemctl --user stop llama-swap.service
systemctl --user start llama-swap.service
```

Para una prueba manual en Cockpit, cerrar admisión/parar el servicio, esperar
la descarga y abrir `manage.py cockpit` desde la raíz del repositorio. Cerrar
servidores y TUI antes de volver a iniciar el servicio. El lock es cooperativo;
no protege frente a Docker manual, otros usuarios o entrenamiento ajeno.
`manage.py unload` usa el endpoint loopback estándar y no debe suponerse
operativo para el bind LAN privado: usar la UI o parar el servicio.

Rollback a Lemonade: parar/deshabilitar llama-swap, verificar contenedores y
memoria, comparar archivos originales con el snapshot privado, restaurar solo
si fueron alterados y volver a habilitar/iniciar la unidad Lemonade observada.
No cargar a ciegas el par del baseline histórico. No usar `prune`, borrar pesos
ni sobreescribir archivos privados. Clonar este repositorio no reproduce la
unidad privada, los enlaces systemd, claves, perfiles activos ni firewall.

Al revalidar para este informe: Lemonade disabled/inactive; llama-swap
enabled/active, cero reinicios registrados, catálogo exclusivo Halogen
131072/8192 y 21 chats HTTP 200 en una muestra reciente de 200 líneas del
journal. Durante la prueba inicial del servicio hubo 429 por concurrencia 1;
no se interrumpieron las peticiones del operador para forzar el smoke.
**No se reinició el host:** arranque automático configurado, cold boot y
recuperación tras caída real aún pendientes. Halogen carga bajo demanda.

## 8. Logs, optimizaciones propuestas y límites

En una muestra previa de una hora: backend con 61 peticiones, sin HTTP 4xx/5xx,
OOM ni reinicios; journal de kernel sin fallos GPU/OOM coincidentes. Otra
muestra del gateway tuvo 72 chats, mediana 9,3 s y máximo 58,2 s; son tiempos
totales heterogéneos, no TTFT ni benchmark. Hubo cinco expulsiones de caché KV
por falta de espacio, recuperables pero con posible coste de nuevo prefill.
PSI de memoria instantáneo nulo no prueba ausencia de presión durante cargas.
Tctl observado 77-84 °C y sensor GPU 37 °C: no son medidas equivalentes ni
prueba de throttling; registrar temperaturas bajo carga antes de aumentar N.

Plan inicial, antes de aplicar el perfil C. El ensayo N=4/pool 524288 se
actualiza en la sección 10; las demás alternativas no se ejecutaron:

| Paso | Propuesta | Validación necesaria |
| --- | --- | --- |
| N=2 | Pool 262144, dos slots, contexto 131072 | Aproximadamente +3,6 GiB KV respecto al pool actual, más estado; medir TTFT y velocidad individual/agregada |
| N=4 moderado | Pool 262144, presupuestos aproximados 64K por petición | No prometer cuatro peticiones de 128K simultáneas; medir expulsiones/cancelación |
| N=4 largo | Pool 524288 | Validar margen de RAM, caché de archivos y latencia antes de promover |
| Caché persistente | Directorio privado separado | Beneficio tras reinicios, escritura, privacidad y limpieza |
| Servicio | Reinicio del host y recuperación controlada | API tras boot, nueva carga, Docker/grupos/red, fallos de motor |

El controlador inicial fijaba un slot, pool igual al contexto y concurrencia 1
en gateway/modelo. La ampliación posterior añade `slots` y `kv_pool` validados
para Halogen y ajusta la admisión del gateway; ver sección 10. No basta con
editar Slots en Cockpit ni con incrementar el contexto anunciado.
No se amplió GTT ni se desactivó IOMMU para obtener concurrencia.

## 9. Pruebas de repositorio y publicación

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

En la entrega inicial pasaron 28 tests de inferencia/control; tras el perfil C
son 29. Los 14 tests documentales también pasan,
incluyendo pruebas opcionales con llama-swap instalado. Se verificó la unidad
privada con `systemd-analyze --user verify`. El build completo del sitio sigue
fallando por el enlace EngramHalo a `.dockerignore`, no permitido. No se amplió
el allowlist ni se presenta el éxito de fixtures como éxito de publicación.

Pendientes: cold boot, soak, comparación N=1/N=2/N=4 y cuatro contextos largos
simultáneos, calidad de tareas largas,
compactación del cliente real, TLS LAN si cambia el alcance, otros runtimes,
visión y entrenamiento. No hay inferencia ROCm Coder/vLLM promovida ni prueba
visual Halogen. Los archivos locales antiguos y backups conservan sus nombres
históricos aunque solo Halogen sea servido al cierre.

## 10. Perfil C aplicado y revisión posterior de logs

### Configuración efectiva y contrato de concurrencia

El operador eligió directamente C, sin ejecutar antes un barrido comparativo:

| Parámetro | Valor aplicado |
| --- | ---: |
| Contexto máximo por petición | 131072 |
| Pool KV compartido | 524288 |
| Slots del motor | 4 |
| Arena de prefill | 16384 |
| Máximo de salida | 8192 |
| Concurrencia global llama-swap | 4 |
| Concurrencia del modelo llama-swap | 4 |

El backend y el gateway se mantienen bajo el servicio de usuario existente,
sin clave según la excepción LAN previa. Se guardó un backup privado del
perfil de un slot y del gateway antes del reinicio controlado. Solo Halogen
permanece en el catálogo. La unidad sigue habilitada y el pool completo fue
confirmado en el log de arranque: no se observó ajuste automático a la baja.

La implementación admite `slots` de 1 a 8 y `kv_pool` desde `context` hasta
1048576, solo para Halogen. Se rechazan booleanos, cadenas, valores fuera de
rango y esos campos en otros motores. Si faltan, se conserva un slot y pool
igual a contexto. La admisión por modelo sigue sus slots, y la global toma el
máximo de los perfiles habilitados, conservando exclusión entre motores.
El catálogo sigue anunciando contexto **por petición**, no el tamaño del pool.

El motor declaró al arrancar 68,0 GiB de pesos registrados, 14,4 GiB de KV y
12,5 GiB de trabajo, **94,8 GiB en total**, con aproximadamente **19,3 GiB**
restantes. Son cifras del diagnóstico del motor, no una lectura equivalente
de GTT o de `MemAvailable`. El pool admite en presupuesto cuatro peticiones
de 128K incluyendo salida, pero no se ha probado llenar las cuatro a la vez.

### Prueba sincronizada de cuatro agentes

Dos rondas consecutivas, cuatro peticiones lanzadas mediante barrera al
mismo endpoint de llama-swap. Cada petición tuvo 7775 tokens de entrada y
512 de salida, incluidos 26-27 de razonamiento. Se verificaron contenido no
vacío, uso de tokens y cierre SSE `[DONE]`: **8/8 completadas**.

| Ronda | Primer contenido por petición | Duración por petición | Tiempo del lote |
| --- | --- | --- | ---: |
| Inicial | 28,19-28,41 s | 54,67-54,89 s | 54,90 s |
| Repetición | 1,33-1,53 s | 26,90-27,10 s | 27,11 s |

La segunda ronda informó **7775 tokens cacheados por petición**. El primer
contenido no cuenta como primer token de razonamiento; los tiempos de lote
no son velocidad de decode. Las ventanas de respuesta se solaparon. Esto
valida un smoke de concurrencia real y reutilización de esos prefijos, no
cuatro agentes de 128K ocupados, fairness, calidad de código, un benchmark
contra N=1 o estabilidad prolongada. No se declara que C sea el óptimo.

### Ventana observada y errores

Revisión de solo lectura el **2026-09-17 a las 13:51:32 UTC**, con ventana
solicitada **12:51:32-13:51:32 UTC**. El contenedor actual arrancó a las
13:07:01 UTC, por lo que sus logs cubren unos 44 minutos; el journal del
servicio abarca también actividad anterior al cambio. No comparar los
conteos como si fueran idénticas poblaciones ni atribuirlos todos al perfil C.

| Fuente | Resultado de la ventana consultada |
| --- | --- |
| Backend actual | 366 líneas; 92 accesos HTTP 200, de ellos 90 chats; ningún HTTP 4xx/5xx registrado |
| Gateway | 373 líneas; 361 accesos HTTP 200, de ellos 105 chats; ningún HTTP 4xx/5xx registrado |
| Duraciones chat gateway | n=105, mínimo 3,17 s, mediana 10,61 s, máximo 211,86 s |
| Contenedor | running, `OOMKilled=false`, cero reinicios del contenedor |
| Journal kernel | Sin coincidencias GPU reset, ring timeout, GPU fault u OOM en esa ventana |
| Caché backend | Ninguna línea `forgot the region` o `no room` en la muestra del contenedor actual |

Los chats son tráfico heterogéneo del laboratorio y pruebas, no prompts
emparejados. El máximo de 211,86 s no identifica por sí solo una regresión ni
su causa. La ausencia de errores HTTP/log no prueba calidad de respuestas ni
éxito de cada herramienta, y cero reinicios de contenedor no equivale a
validación de recuperación del servicio o del host.

Había un **`DeprecationWarning` de la API Python upstream**, no un fallo de
inferencia. Dos líneas contenían la palabra `failed`: una informó cero fallos
al fijar pesos y otra **69 esperas de compactación de memoria, 12 fallidas**
al reservar KV. El arranque terminó con éxito; esos contadores no son
peticiones fallidas, OOM ni errores de compactación de conversación. Justifican
vigilar fragmentación/margen en futuros arranques, no ocultar los avisos.

En la lectura final: GTT usado **35711561728 bytes, aproximadamente 33,26 GiB**,
GPU ocupada 96%; PSI de CPU y memoria con medias de 10/60/300 segundos en cero.
PSI de I/O `some` 0,59/0,96/0,85 y `full` 0,59/0,94/0,83 por ciento. Hay esperas
de I/O durante actividad, sin demostrar saturación ni causa de latencia. No
se extrapola esta lectura a toda la ventana ni a una garantía de margen RAM.

### Qué publican los endpoints

En la consulta del backend interno `/health` se observó:

```json
{
  "status": "ok",
  "slots": 4,
  "slot_ctx": 131072,
  "kv_pool_positions": 524288,
  "in_flight": 1,
  "queued": 0,
  "busy": false,
  "busy_for_s": 25.9,
  "max_tokens_cap": 8192
}
```

`busy=false` coexistió con `in_flight=1`; no interpretarlo como ausencia de
peticiones ni como cuatro slots libres. Slots configurados, peticiones en
vuelo, cola y posiciones KV son magnitudes diferentes. Incluso `slots` menos
`in_flight` no garantiza admisión: es una instantánea y también importa el KV.

En llama-swap, `/v1/models` sigue publicando contexto 131072 y salida 8192,
pero **no slots totales, slots libres, cola ni pool KV**. Halogen sí ofrece los
campos dinámicos anteriores en su endpoint loopback interno. No se ha abierto
ese puerto a la LAN ni creado un endpoint público agregado. Publicar capacidad
estática y exponer estado dinámico serían trabajos distintos; ningún cliente
debe deducir paralelismo disponible solo del catálogo actual.

### Siguientes comprobaciones, sin aplicar cambios ahora

1. Comparar N=1/N=2/N=4 con entradas y salidas emparejadas, caché fría y caliente,
   percentiles de latencia y velocidad individual/agregada.
2. Probar cuatro entradas progresivamente más largas y una quinta petición,
   verificando cola/rechazo, cancelación y recuperación sin sobrepasar el pool.
3. Soak y seguimiento de memoria real, compactación del kernel, I/O y térmicas.
4. Probar cold boot y recuperación del servicio en una ventana reservada.
5. Diseñar publicación de slots totales y estado dinámico sin anunciar
   disponibilidad ficticia ni exponer administración accidentalmente.

Esta revisión no reinició servicios, cambió slots, cargó modelos nuevos ni
modificó firewall, BIOS, GTT o IOMMU. Los resultados y backups crudos siguen
privados; no se incluyeron prompts, claves, direcciones ni logs completos.
