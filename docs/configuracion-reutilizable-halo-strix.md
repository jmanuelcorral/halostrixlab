# Halo Strix: configuracion reutilizable

> **English:** [operational guide](en/configuration-reference.md) (equivalente operativo, no traduccion literal de logs).
> **Diccionario completo:** [parámetros Lemonade](referencia-parametros-lemonade.md).
> **Cronología posterior:** [estado documental del proyecto](estado-proyecto.md).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

Consolidado: **2026-09-07**. Ultimo baseline positivo documentado:
**2026-09-04**. Fuentes locales del 2026-08-25 al 2026-09-04; **no es una
auditoria en vivo**. No se consulto el host ni se modificaron servicios,
modelos, paquetes o credenciales para crear esta referencia.

**Incidencia posterior abierta:** el 2026-09-04 a las 18:47:07.402Z se
reporto HTTP **403**, sin respuesta/resolucion recuperable. No se conoce
endpoint, cliente ni causa. El PASS anterior no certifica salud posterior;
no atribuir este reporte automaticamente al CORS corregido el 2026-08-25.
Procedencia: reporte historico del operador, anonimizado aqui; no se
publican identificadores ni registros privados. Las propuestas previas
del 2026-08-26 y 2026-09-03 no son configuracion final.

Etiquetas: **OBSERVADO** = evidencia historica positiva; **CONFIGURADO** =
persistencia o plantilla documentada; **RECOMENDACION** = accion futura;
**PENDIENTE** = no demostrado o contradictorio. Ninguna significa "vivo".

El [perfil JSON](../config/halo-strix.reference.json) es un esquema documental
propio, **no una exportacion ni un formato importable de Lemonade**.
Sus `load_request_reference` son ejemplos de cuerpos de API, no ordenes
ejecutadas ahora. `<HALO_HOST>` y `$HOME` son placeholders: al restaurar,
resolver el HOME del usuario del servicio a una ruta Linux **absoluta**.
Ni Lemonade ni JSON deben recibir literalmente `~`, `$HOME` o placeholders.

## 1. Inventario historico y eleccion de backend

| Elemento | Ultima evidencia local pertinente |
| --- | --- |
| Equipo | GMKtec EVO-X2; Ryzen AI Max+ 395, 32 CPU logicas; Radeon 8060S, `gfx1151` (RDNA 3.5) |
| Firmware / disco | BIOS `EVO-X2S 1.13` (2026-06-26); NVMe nominal 2 TB (~1.8-1.9 TiB), raiz Btrfs |
| Memoria | 128 GiB fisicos; BIOS `iGPU Configuration=UMA_SPECIFIED`, `UMA Frame Buffer=2 GiB` |
| Memoria visible | ~123.5 GiB RAM; VRAM fija 2147483648 B; GTT 66283167744 B (~61.73 GiB) |
| SO / GPU, observado 2026-08-25 | CachyOS; kernel `7.2.0-1-cachyos`; Mesa / `vulkan-radeon` `3:26.2.1-1`; firmware/ucode `20260810-2` |
| Inferencia, consolidado 2026-09-04 | Lemonade `11.8.1` (antes `11.7.0`, paquete `11.7.0-2.1`); backend `llamacpp:vulkan`, `b10375` / `ba360efe1`, build 2026-08-12 |
| ROCm del host, 2026-08-25 | `7.2.4`, experimental para inferencia HIP; distinto del userspace ROCm `7.14` de los contenedores |
| Docker, 2026-08-25 | Engine `29.7.2`; operacion documentada con sudo, sin alta del usuario en grupo docker |

**OBSERVADO:** la UMA de 2 GiB persistio tras apagado/encendido el
2026-08-26. El estado previo Auto (~62 GiB RAM / ~31 GiB GTT) no es el
baseline a restaurar. No se incremento manualmente el limite TTM/GTT.

**Backend elegido:** Vulkan/RADV. Benchmark corto del 2026-08-25 sobre
Qwen3-1.7B-Q8_0: Vulkan PP512/TG128 = 5263.79/114.39 tok/s; HIP =
5448.84/102.51 tok/s. HIP mejoro PP ~3.5% y empeoro TG ~10.4%, por lo que
no se promovio. No extrapolar esas cifras a los modelos 30B ni a un soak.
Versiones y revisiones son inventario fechado, **no instrucciones de
instalacion, actualizacion ni pines eternos**. Fuentes [F1]-[F5].

## 2. Lemonade: servicio, red y persistencia

**OBSERVADO/CONFIGURADO, 2026-09-04:** `lemond.service` de
`systemd --user`, enabled/active; `Linger=yes` reconfirmado en otra conexion.
Esto supera `Linger=no` del 25-26 de agosto, pero no demuestra una prueba
actual de arranque en frio ni que los modelos se precarguen tras reiniciar.

| Uso / archivo | Referencia sanitizada |
| --- | --- |
| Binarios | `/usr/bin/lemonade`, `/usr/bin/lemond` |
| Configuracion persistida | `$HOME/.cache/lemonade/config.json` |
| Catalogo de usuario evidenciado | `$HOME/.cache/lemonade/user_models.json` (no editar/borrar para resolver colisiones) |
| Modelos descargados (`models_dir`) | `$HOME/ai/lemonade/models` |
| GGUF locales (`extra_models_dir`) | `$HOME/ai/models/smoke` (escaneo recursivo; no es el cache de descargas) |
| Backend gestionado | `$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server` |
| CORS persistido | `$HOME/.config/lemonade/conf.d/allowed-origins.conf`, modo 0600 |
| Backup de config documentado | `$HOME/.cache/lemonade/config.json.bak-20260826T072912+0200`, modo 0600; existencia actual no comprobada |

`host=<HALO_HOST>`, `port=13305`, `broadcast=false`. El ultimo listener
documentado era **solo en IP LAN**, no en `127.0.0.1:13305`; `9000` era
auxiliar, **no baseURL del cliente**. Hijos gestionados en loopback
`127.0.0.1:8001` (Coder) y `127.0.0.1:8002` (Thinking): puertos observados,
no API publica ni garantia de asignacion tras una recarga.

La regla UFW documentada limita TCP/13305 a la LAN de confianza y la
interfaz autorizada; no se guarda aqui la topologia privada. HTTP plano,
sin API key ni proxy dedicado evidenciado; **TLS no validado**. Esto es
descripcion historica del riesgo, no autorizacion para exponer servicios.

La unidad empaquetada lee `EnvironmentFile=-%E/lemonade/conf.d/*.conf`.
El archivo CORS autorizaba exactamente
`LEMONADE_ALLOWED_ORIGINS=http://<HALO_HOST>:13305`. Es el **origen de la
pagina cliente** (esquema, host, puerto), no una URL con `/v1` ni la IP de
cualquier PC que consume el servicio. Lista separada por comas si procede;
no usar `*`. Su correccion historica requirio reiniciar el servicio para
releer el entorno; no extrapolar su PASS al 403 posterior. Fuentes [F1],
[F4] y [F6].

**Residencia:** `max_loaded_models=2`, aplicado en caliente con
`POST /internal/set` y cuerpo `{"max_loaded_models":2}`. Persistencia
confirmada en `config.json`; lecturas `/internal/config` y
`/api/v1/health` (`max_models.llm=2`) coincidieron. No requirio reinicio.
Son **dos modelos**, no dos solicitudes/slots. Ambos tenian `pinned:false`;
no confundir `pinned_helper_models` con el pool LLM principal. [F1]

**Trampa CLI:** el `lemonade config set` sin direccion explicita intento
localhost y fallo con el listener LAN. No equivale a servicio caido. Se
documento antes CLI con `--host <HALO_HOST> --port 13305 --no-discovery`;
para restaurar, comprobar el contrato de la version instalada y preferir
la API del listener verificado, no repetir ciegamente la CLI default. [F6]

## 3. Par residente y parametros exactos

| Parametro | Coder | Thinking |
| --- | --- | --- |
| `model_name` de carga | `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` | `Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M` |
| Checkpoint | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q4_K_M` | `unsloth/Qwen3-30B-A3B-Thinking-2507-GGUF:Q4_K_M` |
| Cuantizacion de pesos | `Q4_K_M` | `Q4_K_M` |
| `ctx_size` total | **196608** | **98304** |
| `--parallel` | **3** | **1** |
| Contexto orientativo por peticion a plena concurrencia | **65536** (pool compartido dinamico, no particion fija) | **98304** |
| KV K / V | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| GTT medido | 25.62 GiB | 22.40 GiB |
| Razonamiento | non-thinking | always-thinking; `--reasoning-budget 16384` |

`llamacpp_args` exactos del payload Coder:

```text
--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0
```

`llamacpp_args` exactos del payload Thinking:

```text
--parallel 1 --kv-unified --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384
```

En ambos payloads: `llamacpp_backend="vulkan"`, `merge_args=true`,
`save_options=true`, mas el `ctx_size` de la tabla. El proceso gestionado
anadia `-m <GGUF> --ctx-size <total> --port <interno> --jinja --metrics`.
No lanzar ese proceso a mano junto a Lemonade ni agregar flags de otras
pruebas. Payloads y rutas GGUF con revision HF exacta estan en el
[JSON documental](../config/halo-strix.reference.json). [F1]

**Identidad:** el Coder de esta receta corresponde al registro
`user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`, distinto del built-in
`Qwen3-Coder-30B-A3B-Instruct-GGUF`. Comparten repo/artefacto; no son alias
intercambiables para operaciones de catalogo. Verificar IDs publicados
antes de usar `model`/`model_name`; no borrar ninguno como "limpieza". [F6]

**Semantica y limites:**

- `--kv-unified` comparte el pool KV; 196608 no son tokens por cada slot.
  Slots 3+1 no garantizan cuatro generaciones eficientes simultaneas.
  El runbook recomienda como politica provisional **maximo 3 solicitudes
  activas combinadas**, no es un limite automatico de Lemonade. [F4]
- KV Q8 no cambia la cuantizacion Q4_K_M de los pesos. `--cache-reuse 256`
  solo esta explicitado para Coder. No hay un valor final documentado de
  `cache_prompt`, `--cache-prompt` o cache RAM que deba inventarse.
- La reutilizacion de prefijos KV es independiente de HTTP keep-alive.
  El ~99% citado en el historico es un resumen de sesion sobre una
  configuracion anterior de 4 slots, no un benchmark del par 3+1. [F4]
- `--reasoning-format auto` era el default del binario, un parser de
  salida: no activa thinking en Coder ni lo desactiva en Thinking.
  Revisar `content`, `reasoning_content` y `finish_reason`; el presupuesto
  16384 no equivale a contexto total ni a limite de pasos del agente. [F1]
- **Persistencia/precedencia:** `save_options=true` solicita guardar
  opciones; `false` fue usado para POC/restauraciones sin sobrescribirlas.
  `merge_args=true` aparece en las cargas documentadas, pero las fuentes
  locales consultadas no especifican el algoritmo de merge, prioridad de
  flags duplicados ni orden completo global/modelo/request. **PENDIENTE**:
  no asumir que reenviar el payload elimina opciones previas. Leer opciones
  resueltas y contrastar el proceso. El `ctx_size=32768` global de agosto
  y Coder 262144/4 slots son historicos, no el perfil final. [F1][F6]

La propuesta monomodelo del 2026-09-03 (65536 con Flash Attention
y cache reuse; 98304/Q8 como prueba posterior) tampoco sustituye el par
3+1 confirmado el 2026-09-04. Los **65536 por peticion** de la tabla son
196608/3, no una recuperacion de aquel contexto total propuesto.

**Capacidad observada:** GTT total usado 51557068800 B = 48.02 GiB de
61.73 GiB; VRAM usada 2043170816 B (~1.9 GiB de 2). Quedaban ~13.71 GiB
de GTT en aquella captura. No es presupuesto para un tercer modelo 30B
ni para entrenamiento concurrente; tamano GGUF en disco != memoria de
ejecucion (pesos + KV + buffers). [F1]

## 4. Clientes y comprobacion manual de solo lectura

API OpenAI compatible: **`http://<HALO_HOST>:13305/v1`**.
En OpenCode, usar esa URL como `baseURL` del proveedor compatible y un ID
exacto devuelto por `/v1/models`. Es **RECOMENDACION de conexion**, no
evidencia de una configuracion OpenCode local ya aplicada. No inventar una
clave ni copiar credenciales para completar ejemplos. [F6]

| Ruta | Finalidad |
| --- | --- |
| `GET /` | Web App oficial integrada / Model Manager, no Swagger |
| `GET /api/v1/health` | Salud y modelos realmente cargados |
| `GET /v1/models` | Catalogo; presencia/descarga no prueba residencia |
| `GET /v1/models/<ID>/options` | Opciones resueltas del ID exacto (ruta validada en 11.7; comprobar en la version instalada) |
| `GET /internal/config` | Configuracion efectiva; endpoint interno dependiente de version |
| `POST /v1/chat/completions` | Inferencia; puede autocargar/expulsar modelos, no es read-only |
| `POST /api/v1/load` | Carga con los cuerpos referenciados; operacion mutable |

**RECOMENDACION, no ejecutada:** primero estas lecturas, localmente en
el host Linux por el operador; revisar resultados sin publicar datos
personales. Sustituir `<HALO_HOST>` antes de usar las URL:

```text
systemctl --user show lemond.service -p ActiveState -p SubState -p UnitFileState
loginctl show-user -p Linger
ss -ltn
grep -E '^(MemTotal|MemAvailable):' /proc/meminfo
grep -H . /sys/class/drm/card[0-9]*/device/mem_info_{gtt,vram}_{total,used}
curl --fail-with-body -sS 'http://<HALO_HOST>:13305/api/v1/health'
curl --fail-with-body -sS 'http://<HALO_HOST>:13305/v1/models'
```

Comparar `/internal/config` y opciones de ambos IDs con el perfil, sin
volcar configuraciones completas a chats. Comprobar que health lista ambos
en `all_models_loaded`, `backend_alive:true`, `backend_health:"ready"`,
`device:"gpu"`, `status:"ok"` y HTTP 200. No basta con una SPA o un catalogo
HTTP 200. Si hay 403, identificar hora, metodo, ruta, cliente, `Origin` y
cuerpo de error sanitizados antes de cambiar nada. No registrar tokens,
cookies ni cabeceras de autorizacion.

El [test existente](../scripts/test-lemonade.ps1) **no es read-only**:
envia chat. **Contrato del repositorio actualizado el 2026-09-07: `-BaseUrl`
y `-Model` son obligatorios, sin valores por defecto.** Pasar ambos solo
tras confirmar residencia y autorizar smoke:

```text
powershell -File scripts\test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

**Historico, no contrato actual:** la version anterior elegia una direccion
y `Qwen3-1.7B-Q8_0` por defecto, con riesgo de expulsar Coder/Thinking por
LRU. Ahora omitir parametros no selecciona automaticamente ningun destino
ni modelo. Seleccionar explicitamente un modelo no residente aun puede
autocargarlo y expulsar otro. Este smoke de 16 tokens valida
conectividad/chat, no calidad ni rendimiento; admite
`reasoning_content` cuando no hay `content`. [F7]

## 5. Workspaces ROCm: conservar, no confundir con entrenamiento validado

**OBSERVADO, 2026-08-25:** smoke PyTorch 2.12/ROCm 7.14 con matmul,
backward y gradientes finitos FP16/BF16; **no fine-tuning LLM**. [F5]
Los dos workspaces son experimentales y usan userspace ROCm en Docker;
no mezclarlo con ROCm del host ni entrenar sobre el par residente sin
planificar recursos con el especialista.

| Workspace | Estado y stack guardado | UI / health / persistencia relativa al workspace |
| --- | --- | --- |
| [LLaMA-Factory](../workspaces/llama-factory/README.md) | CONFIGURADO; v0.9.5, commit `7af909522a951e3ad9f022ea6f88b6755257eaa5` (2026-08-31); PyTorch `2.12.0+rocm7.14.0`. Sin entrenamiento ni smoke GPU de LlamaBoard demostrado. | Default `127.0.0.1:7860`, `GET /`; `data/{hf-cache,models,datasets,outputs,cache,config,logs}`. |
| [Unsloth Studio](../workspaces/unsloth-studio/README.md) | UI/imports/GPU/SPA validados 2026-09-01; commit `e18a069c15cde98c7af77ccdb952254db8b0315d`; PyTorch `2.11.0+rocm7.14.0`, HIP `7.14.60850`, Triton `3.7.1+git0263a6a6.rocm7.14.0`. Sin entrenamiento real. | Default `127.0.0.1:8888`, `GET /api/health`; `data/{studio,hf-cache,projects,tmp}`. `data/studio` incluye auth/DB, outputs, exports y runs: es dato privado a preservar, no a leer/copiar a esta referencia. |

Compose: [LlamaBoard](../workspaces/llama-factory/compose.yaml) /
[Studio](../workspaces/unsloth-studio/compose.yaml). Bases AMD fijadas por
digest **diferentes**, recogidas en el JSON y los README; no intercambiar
Torch 2.12 y 2.11 (Unsloth exige `<2.12` en esa fuente).
`WEB_BIND=127.0.0.1`, puertos 7860/8888 y `SHM_SIZE=16g` son defaults de
plantilla, **no afirmacion del despliegue LAN actual**. GPU minima:
`/dev/kfd` + render node configurado (default `/dev/dri/renderD128`).
Revalidar GID del dispositivo; no copiar IDs de usuario/grupo de otro host.
**Contrato de plantillas actualizado el 2026-09-07:** LLaMA-Factory puede
autodetectar `DEVICE_GID` si queda vacio. Unsloth Studio lo deja vacio en
`.env.example`, exige un valor explicito en Compose y **no lo autodetecta**.
Medir `stat -c '%g' "$RENDER_DEVICE"` con el render node seleccionado y
guardar privadamente ese numero como `DEVICE_GID` antes de arrancar Studio.
No confundir este grupo suplementario con el UID/GID del propietario.

Persistencia por bind mounts, no volumen anonimo. Mapas completos en los
README/Compose. Unsloth usa UID/GID del propietario host y autentica el
bootstrap de Studio; la variable privada se retira del proceso largo si
ya existe admin. No guardar ni recuperar su valor en estos artefactos.
`bitsandbytes` ausente: **QLoRA 4-bit no disponible**; FLA avisa fallback
CPU; LoRA BF16 sigue sin validacion end-to-end. La
[plantilla LoRA BF16](../workspaces/llama-factory/examples/poc-lora-bf16.yaml)
es solo propuesta, con `CHANGE_ME`, no entrenamiento ejecutado.

Scripts existentes: [estado LlamaBoard](../workspaces/llama-factory/status.sh),
[estado Studio](../workspaces/unsloth-studio/status.sh),
[arranque LlamaBoard](../workspaces/llama-factory/start.sh) y
[arranque Studio](../workspaces/unsloth-studio/start.sh).
Ambos separan build/arranque; `start.sh` no reconstruye, pero **muta**
contenedores/directorios (Studio tambien propiedad de datos). Para rollback
manual autorizado conservar imagen local por ID: LlamaBoard guarda
`.last-built-image`; Studio guarda `.last-built-image` y
`.previous-built-image`, admite `RUN_IMAGE=last`/`previous`. El mismo ID
recupera una imagen, no host, firmware ni datos; reconstruir desde fuentes
no es reproducible byte a byte. No se ejecutaron esos scripts aqui. [F8][F9]

## 6. Restauracion manual y pendientes

**RECOMENDACION, requiere una ventana y autorizacion propias:**

1. Hacer primero las lecturas de la seccion 4; comparar versiones, rutas,
   catalogo, opciones, memoria, salud y cargas en curso. El repo no contiene
   binarios, GGUF ni copia verificable de todos los archivos vivos.
2. Preservar fuera de esta referencia copias privadas de configuracion,
   catalogo/opciones y datos, con sus permisos; conservar imagenes por ID.
   No leer secretos para completar el perfil ni sobrescribir archivos sin
   backup. No reconstruir servicios solo por diferencias historicas.
3. Si se acuerda volver a este baseline, resolver rutas absolutas, bind y
   origen de confianza, verificar `max_loaded_models=2` y revisar los dos
   `load_request_reference`. Confirmar opciones resueltas antes/despues;
   el merge puede conservar opciones anteriores. No importar el JSON entero.
4. Aplicar solo los cambios necesarios via API/UI soportada; no retocar
   drivers, BIOS, runtimes o parametros nuevos. Habilitar linger o reiniciar
   para cambios de entorno seria una operacion manual separada, no hecha
   por este runbook. Guardar opciones no garantiza precarga tras reinicio.
5. Revalidar health, argumentos efectivos del backend y GTT; solo entonces
   smoke con un ID residente. Si falla, revertir el cambio concreto desde
   su copia y repetir lecturas. No borrar modelos ni datos para "restaurar".

**Alternativas no promovidas / incertidumbres:**

- HIP como inferencia: benchmark inferior en TG; queda experimental.
  vLLM: investigado, con segfault nativo resumido en el historico;
  no baseline validado ni sustituto de Vulkan. [F3][F4]
- Netdata nativo fue recomendado y Cockpit opcional el 2026-08-26;
  la instalacion quedo en espera, sin evidencia posterior en los
  documentos consultados. No incluirlos como servicios instalados.
- Qwen3.8-27B UD-Q4_K_XL: no promover. [F1] no encontró una carga en la
  evidencia que consultó, pero [F6] lo identifica como cargado en
  un diagnostico anterior. **Contradiccion sin resolver**: no afirmar
  "nunca ejecutado" ni deducir soporte estable/estado actual de ella.
- Qwen3.8-Flash-Next UD-Q4_K_XL: incompatibilidad `qwen4exp` con b10375 y
  ~104.53 GiB en disco frente a ~61.73 GiB GTT. Estado fechado, no consulta
  del soporte upstream actual; no cargar en el servicio del par. [F1]
- HTTP 403 posterior sin resolucion; TLS/proxy no validados; falta prueba
  actual de salud, arranque en frio, precarga, rendimiento sostenido y
  entrenamiento real. Defaults antiguos y recomendaciones no son hechos.
- No consta en estas fuentes una copia reutilizable de los payloads en
  archivos independientes del host, ni el nombre exacto del archivo donde
  Lemonade persiste todas las opciones por modelo. No inventar esas rutas;
  el unico fichero nuevo de parametros es el perfil documental del repo.

## Fuentes locales y precedencia

Se prioriza la ultima evidencia explicita de **cada tema**, no el primer
PASS ni un titulo que diga "actual". Una contradiccion se conserva como
pendiente. Los archivos originales son historicos y pueden contener rutas
privadas: no copiarlos en bloque al reutilizar esta referencia.

- **[F1]** [Comparativa 2026-09-04](comparativa-qwen38-halo-strix.md):
  secciones 2-4 hardware, servicio, rutas/payloads y par; 5 reasoning;
  10 rollback y health.
- **[F2]** [Auditoria inicial](auditoria-ssh-inicial.md): inventario y
  secciones de UMA/post-traslado (2026-08-25/26).
- **[F3]** [Vulkan](validacion-llamacpp-vulkan.md): seccion final, gate corto;
  [HIP](validacion-llamacpp-hip.md): seccion final, comparativa.
- **[F4]** [Setup historico completo](setup-completo-halo-strix.md):
  secciones 2, 4, 7-10, 13-16; particularmente 16.10 para cache/keep-alive.
- **[F5]** [Entrenamiento ROCm](validacion-entrenamiento-rocm.md):
  seccion de smoke aislado del 2026-08-25.
- **[F6]** [Validacion Lemonade](validacion-lemonade-vulkan.md):
  secciones de catalogo y concurrencia/OpenCode;
  UI/opciones, CORS, rutas y backup.
- **[F7]** [Test PowerShell](../scripts/test-lemonade.ps1): bloque de parametros,
  listado/modelo/POST y validacion de contenido.
- **[F8]** [LLaMA-Factory README](../workspaces/llama-factory/README.md),
  [.env.example](../workspaces/llama-factory/.env.example) y Compose.
- **[F9]** [Unsloth README](../workspaces/unsloth-studio/README.md),
  [.env.example](../workspaces/unsloth-studio/.env.example), Compose y
  [entrypoint](../workspaces/unsloth-studio/scripts/container-entrypoint.sh).
