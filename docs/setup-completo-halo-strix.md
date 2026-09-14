# Setup completo Halo Strix (GMKtec EVO-X2) — documentación maestra y runbook

> **English:** [operational guide](en/setup-guide.md) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

> Para reutilizar parametros, empezar por la [referencia compacta y sus pendientes](configuracion-reutilizable-halo-strix.md). Este documento conserva el historico; no certifica el estado vivo.

> **Autor:** equipo tecnico (Lead técnico). **Ámbito:** consolidación de todo el trabajo
> realizado hasta la fecha sobre el host GMKtec EVO-X2 ("Halo Strix").
> Este documento **no sustituye** a los documentos fuente; los resume, los
> referencia por ruta y añade procedimientos operativos. Ante cualquier
> discrepancia, **el documento fuente citado prevalece**.
>
> **Convenciones de etiquetado usadas en todo el documento:**
>
> - **HECHO MEDIDO** — observado/ejecutado con evidencia directa en una sesión real.
> - **CONFIGURADO** — aplicado y persistido, pero sin una validación end-to-end completa registrada.
> - **RECOMENDACIÓN** — buena práctica o decisión sugerida, no necesariamente ejecutada.
> - **PENDIENTE/BLOQUEADO** — no ejecutado, incompatible o explícitamente fuera de alcance.
>
> **Nota de seguridad:** este documento no reproduce credenciales, contraseñas,
> tokens, claves privadas ni archivos privados de autenticacion. Las
> variables de conexión (`HALOSTRIX_HOST`, `HALOSTRIX_USER`, etc.) se
> documentan como patrón/placeholder, nunca con valores reales.

## Índice

1. [Objetivo y último estado histórico documentado](#1-objetivo-y-último-estado-histórico-documentado)
2. [Inventario de hardware, firmware, memoria, disco y SO](#2-inventario-de-hardware-firmware-memoria-disco-y-so)
3. [Preparación inicial de CachyOS y conexión SSH](#3-preparación-inicial-de-cachyos-y-conexión-ssh)
4. [Cambio de UMA en BIOS](#4-cambio-de-uma-en-bios)
5. [Validación de GPU: Vulkan frente a HIP/ROCm](#5-validación-de-gpu-vulkan-frente-a-hiprocm)
6. [Arquitectura final de servicios y puertos](#6-arquitectura-final-de-servicios-y-puertos)
7. [Lemonade Server: instalación y operación](#7-lemonade-server-instalación-y-operación)
8. [llama.cpp/Lemonade: modelos, parámetros y KV cache](#8-llamacpplemonade-modelos-parámetros-y-kv-cache)
9. [Estado Coder + Thinking, memoria y concurrencia](#9-estado-coder--thinking-memoria-y-concurrencia)
10. [Investigación vLLM](#10-investigación-vllm)
11. [Qwen3.8-27B y Flash-Next](#11-qwen38-27b-y-flash-next)
12. [Entrenamiento: Docker/ROCm/PyTorch validado](#12-entrenamiento-dockerrocmpytorch-validado)
13. [LLaMA-Factory / LlamaBoard](#13-llama-factory--llamaboard)
14. [Unsloth Studio](#14-unsloth-studio)
15. [Reverse proxies y HTTPS/TLS](#15-reverse-proxies-y-httpstls)
16. [Incidentes y troubleshooting](#16-incidentes-y-troubleshooting)
17. [Operación diaria](#17-operación-diaria)
18. [Rollback y limpieza segura](#18-rollback-y-limpieza-segura)
19. [Matriz de estado](#19-matriz-de-estado)
20. [Próximos pasos priorizados](#20-próximos-pasos-priorizados)
21. [Índice de documentos y artefactos del repo](#21-índice-de-documentos-y-artefactos-del-repo)

---

## 1. Objetivo y último estado histórico documentado

**Objetivo:** convertir un GMKtec EVO-X2 (AMD Ryzen AI Max+ 395 / Radeon
8060S, "Strix Halo") en un servidor local de inferencia y entrenamiento LLM
sobre CachyOS, accesible por LAN, con Lemonade Server como backend de
inferencia (llama.cpp/Vulkan) y contenedores Docker/ROCm como ruta de
entrenamiento.

**Último estado histórico recogido por este informe (HECHO MEDIDO en su fecha,
salvo indicación contraria; no acredita el estado actual):**

- CachyOS con kernel `7.2.0-1-cachyos`, UMA de BIOS reconfigurada
  (`UMA_SPECIFIED` a 2 GiB) para liberar ~123.5 GiB de RAM utilizable con
  ~61.7 GiB de GTT dinámico. Fuente: `docs/auditoria-ssh-inicial.md`.
- Backend de inferencia **Vulkan** (RADV/Mesa) promovido como ganador frente
  a HIP/ROCm tras benchmark comparativo. Fuente: `docs/validacion-llamacpp-hip.md`.
- **Lemonade Server** documentado en esa fecha como servicio systemd de usuario,
  escuchando en la LAN (`<HALO_HOST>:13305`), con dos modelos residentes
  simultáneos (`max_loaded_models=2`): Qwen3-Coder-30B-A3B-Instruct (coding)
  y Qwen3-30B-A3B-Thinking-2507 (razonamiento). Fuente:
  `docs/comparativa-qwen38-halo-strix.md`.
- **Docker Engine 29.7.2** validado con un smoke de entrenamiento PyTorch
  ROCm en contenedor (FP16/BF16, backward pass finito). Fuente:
  `docs/validacion-entrenamiento-rocm.md`.
- **LLaMA-Factory/LlamaBoard** y **Unsloth Studio** empaquetados como
  workspaces Docker/ROCm autocontenidos en `workspaces/llama-factory/` y
  `workspaces/unsloth-studio/`; UI de Unsloth Studio validada (build, imports,
  detección GPU), **sin** entrenamiento real ejecutado en ninguno de los dos.
- **Pendiente/bloqueado:** HTTPS/TLS en cualquier servicio (todo el acceso
  actual es HTTP plano sobre LAN confiada); QLoRA/bitsandbytes en Unsloth
  Studio; promoción de Qwen3.8-27B; soporte de Qwen3.8-Flash-Next
  en el backend gestionado; **consolidación de la investigación de vLLM**:
  se investigó y diagnosticó vLLM en sesión (segfault nativo con
  `Qwen3.6-27B-FP16-vLLM`), pero ese trabajo **no está consolidado en
  evidencia versionada** ni fue promovido a producción — ver §10.

---

## 2. Inventario de hardware, firmware, memoria, disco y SO

Fuente primaria: `docs/auditoria-ssh-inicial.md` (auditoría SSH inicial y
chequeo post-traslado).

| Elemento | Valor | Estado |
| --- | --- | --- |
| Equipo | GMKtec EVO-X2 | HECHO MEDIDO |
| Firmware/BIOS | `EVO-X2S 1.13` (2026-06-26) | HECHO MEDIDO |
| CPU/APU | AMD Ryzen AI Max+ 395 con Radeon 8060S, 32 CPU lógicas | HECHO MEDIDO |
| Target GPU | `gfx1151` (GFX 11.5.1, RDNA 3.5 Strix Halo), confirmado por `gfx_target_version=110501` y posteriormente por `rocminfo` nativo | HECHO MEDIDO |
| SO | CachyOS, kernel `7.2.0-1-cachyos` | HECHO MEDIDO |
| Firmware kernel | `linux-firmware` / `linux-firmware-amdgpu` y `amd-ucode` `20260810-2` | HECHO MEDIDO |
| Mesa/Vulkan | Mesa + `vulkan-radeon` `3:26.2.1-1` (RADV), API instancia `1.4.357`, dispositivo `1.4.354` | HECHO MEDIDO |
| RAM (post-UMA) | `MemTotal` ≈123.5 GiB, `MemAvailable` ≈121.3–121.4 GiB, swap ≈123.5 GiB, CMA 0 | HECHO MEDIDO |
| GTT/TTM | `pages_limit` ≈61.7 GiB (≈66,283,167,744 B exactos según `mem_info_gtt_total`) | HECHO MEDIDO |
| VRAM dedicada | 2 GiB fija (`UMA_SPECIFIED`, mínimo disponible) | HECHO MEDIDO |
| Disco | SSD NVMe ~1.8–1.9 TiB, raíz Btrfs, subvolumen `@`, `noatime`, `compress=zstd:1`, `discard=async`, `space_cache=v2` | HECHO MEDIDO |
| SMART | `critical_warning=0`, `media_errors=0`, spare 100 %, uso 0 %; sensor NVMe secundario informa ~77.8 °C con umbrales incoherentes (no usar como gate térmico) | HECHO MEDIDO |
| KFD/CWSR | Nodo GPU con `cwsr_size=19185664`, `ctl_stack_size=16384` | HECHO MEDIDO |
| Red | `wlan0` con direccion `<HALO_HOST>` en `<LAN_CIDR>`, gateway `<LAN_GATEWAY>`, DNS `<LAN_DNS>` | HECHO MEDIDO |
| Firewall | UFW activo, política de entrada `deny`/`drop`, SSH permitido | HECHO MEDIDO |
| Docker | `docker` 29.7.2, `enabled`/`active`; usuario no pertenece al grupo `docker` (se usa `sudo`) | HECHO MEDIDO |

**Nota sobre la discrepancia de memoria (DMI vs kernel):** antes del cambio
de UMA, el DMI Type 16 declaraba 64 GiB de capacidad máxima mientras Type 17
enumeraba ocho módulos de 16 GiB (128 GiB físicos). El diagnóstico atribuyó
la diferencia a un carve-out UMA de firmware con `iGPU Configuration=Auto`
(confianza ~95 %), confirmado después por el propio cambio de BIOS (ver §4).
Fuente: `docs/auditoria-ssh-inicial.md`, sección "Diagnóstico de discrepancia
de memoria".

---

## 3. Preparación inicial de CachyOS y conexión SSH

Fuente: `docs/auditoria-ssh-inicial.md`, `docs/plan-configuracion-halo-strix.md`.

### 3.1 Pasos realizados (HECHO MEDIDO)

- Preflight de variables de conexión, resolución DNS, apertura TCP y banner
  SSH antes de cualquier autenticación.
- TOFU (*trust-on-first-use*) de la clave de host **limitado a un almacén de
  `known_hosts` exclusivo de la sesión** (`<VERIFIED_KNOWN_HOSTS_FILE>`), nunca al
  `known_hosts` global del operador. Huella pública registrada:
  `<SSH_HOST_KEY_FINGERPRINT>`.
- Autenticación Paramiko 5.0.0, instalado únicamente en un directorio de
  estado de sesión (`pip --target`), sin tocar el Python global ni el
  repositorio.
- Baseline de rollback bajo el `HOME` del usuario remoto:
  `halostrix-baseline-20260825/` (modo `700`) con `packages-explicit.txt`,
  `packages.txt`, `etc.tar.zst` (vía `sudo tar --zstd`) y su SHA-256.
- Instalación controlada, únicamente tras verificar que no había upgrades
  pendientes, de `vulkan-tools`, `nvme-cli` (+ `libnvme`) y `lm_sensors` con
  `pacman -Syu --needed --noconfirm`.

### 3.2 Patrón de variables de conexión (placeholders, sin valores reales)

```text
HALOSTRIX_HOST=<ip-o-hostname-lan>
HALOSTRIX_USER=<usuario-ssh>
HALOSTRIX_SSH_PORT=<puerto>
# Autenticación por clave SSH, nunca contraseña en texto plano ni en chat.
```

Estas variables se resuelven privadamente por el operador; **este documento
no publica archivos ni valores de autenticacion**.

### 3.3 Prácticas recomendadas (RECOMENDACIÓN, algunas ya aplicadas)

- Nunca usar `StrictHostKeyChecking=accept-new` ni `=no`; verificar la huella
  del host por un canal fiable antes de la primera conexión
  (`docs/plan-configuracion-halo-strix.md`, §2).
- Mantener el `known_hosts` de la sesión de automatización separado del
  `known_hosts` interactivo del operador.
- Preservar el fallback de paquetes/`etc` antes de cualquier transacción de
  Pacman; añadir una lista `packages-post-*.txt` con hash tras cada cambio
  relevante (patrón ya usado en `packages-rocm-pre/post.txt`).
- Investigar la restricción de permisos que impidió usar `snapper`/`btrfs
  subvolume show` en la sesión auditada (quedó **PENDIENTE**, no se
  diagnosticó como corrupción); mientras tanto, el fallback de paquetes/`etc`
  es el mecanismo de rollback verificado.

---

## 4. Cambio de UMA en BIOS

Fuente: `docs/auditoria-ssh-inicial.md`, secciones "Diagnóstico de
discrepancia de memoria" y "Verificación posterior al cambio UMA".

| Estado | `iGPU Configuration` | `UMA Frame Buffer` | RAM visible | GTT/TTM |
| --- | --- | --- | --- | --- |
| **Inicial** | `Auto` | (implícito, no fijo) | ~62 GiB | ~31.2 GiB |
| **Final (HECHO MEDIDO)** | `UMA_SPECIFIED` | 2 GiB (mínimo disponible; el objetivo de 512 MiB no estaba disponible en este firmware) | **123.5 GiB** | **61.7 GiB** |

**Cambio ejecutado:** el usuario cambió físicamente en BIOS
`iGPU Configuration` de `Auto` a `UMA_SPECIFIED` y fijó `UMA Frame Buffer` al
mínimo disponible (2 GiB), tras fotografiar las pantallas BIOS previas. Se
reinició el equipo.

**Cómo verificar (comandos read-only, reproducibles):**

```bash
grep MemTotal /proc/meminfo
grep MemAvailable /proc/meminfo
cat /sys/module/ttm/parameters/pages_limit
# AMDGPU: VRAM/GTT anunciados por el driver, según herramienta disponible
```

**Criterio de PASS ya alcanzado:** `MemTotal` ≈123.5 GiB (objetivo ~125 GiB),
`MemAvailable` ≈121.4 GiB, VRAM AMDGPU fija en 2 GiB, TTM/GTT ≈61.7 GiB
(~50 % de la RAM visible, coherente con el límite dinámico documentado por
AMD). El chequeo post-traslado físico del 2026-08-26 reconfirmó que la
configuración persistió tras un apagado/encendido real (`MemTotal` 123.5
GiB, VRAM fija 2048 MiB, GTT 63212 MiB).

**Rollback (no ejecutado, documentado):** volver físicamente
`iGPU Configuration` a `Auto` y reiniciar. No se recomienda mientras la
configuración actual siga pasando los gates de memoria y estabilidad.

---

## 5. Validación de GPU: Vulkan frente a HIP/ROCm

Fuentes: `docs/validacion-llamacpp-vulkan.md`, `docs/validacion-llamacpp-hip.md`.

### 5.1 Vulkan — baseline (HECHO MEDIDO)

- Build propio de llama.cpp `v0.3.0` con `GGML_VULKAN=ON`, `GGML_NATIVE=ON`.
- Offload verificado: `offloaded 29/29 layers to GPU`, dispositivo
  `Vulkan0: AMD Radeon 8060S Graphics (RADV STRIX_HALO)`.
- Benchmark (`llama-bench`, modelo `Qwen3-1.7B-Q8_0.gguf`, `-ngl 999`,
  prompt 512 / generación 128, tres réplicas):

| Métrica | Resultado |
| --- | ---: |
| PP 512 | **5263.79 ± 10.83 tok/s** |
| TG 128 | **114.39 ± 0.24 tok/s** |

- Gate térmico corto (no soak): GPU edge ~29→35 °C, CPU ~30.9→47 °C, NVMe
  composite ~31.9 °C; sin AMDGPU/OOM/reset/AER/thermal en el journal
  filtrado.
- Calificado como **"PASS (corto/provisional)"**: no sustituye un soak
  térmico prolongado ni una carga de producción sostenida.

### 5.2 HIP/ROCm — candidato experimental, no promovido (HECHO MEDIDO)

Tras varios gates estrictos (ruta de compilador `HIPCXX`, dependencias
`hipblas`/`rocblas`, enlace `libggml-hip.so`/`libamdhip64`), el build HIP
finalmente compiló, cargó el modelo (`offloaded 29/29 layers`) y se
benchmarkeó frente a Vulkan:

| Backend | PP512 tok/s | TG128 tok/s |
| --- | ---: | ---: |
| Vulkan (baseline) | 5263.79 ± 10.83 | **114.39 ± 0.24** |
| HIP/ROCm | **5448.84 ± 173.67** | 102.51 ± 0.17 |

- HIP mejora PP ~3.5 % (por debajo del umbral de promoción del 5 %) y
  **regresa TG ~10.4 %** (por encima de la regresión tolerada).

**Decisión (RECOMENDACIÓN aplicada): Vulkan permanece backend ganador y en
producción; HIP/ROCm queda disponible como build experimental, no promovido
para el servicio Lemonade.** Fuente: `docs/validacion-llamacpp-hip.md`,
sección "Runtime, smoke y benchmark HIP directos".

ROCm sí quedó instalado y validado de forma independiente para el caso de
uso de **entrenamiento** en contenedor (ver §12), lo cual es una decisión
separada de la elección de backend de inferencia.

---

## 6. Arquitectura final de servicios y puertos

Fuentes: `docs/comparativa-qwen38-halo-strix.md` §2, `docs/plan-configuracion-halo-strix.md` §3.

```text
LAN <LAN_CIDR> (Wi-Fi, wlan0)
        │
        ├── UFW: entrada deny por defecto; SSH permitido; TCP/13305 permitido
        │         sólo desde <LAN_CIDR> hacia <HALO_HOST> (wlan0)
        │
        ▼
Host CachyOS <HALO_HOST> (GMKtec EVO-X2 / gfx1151)
├── lemond.service (systemd --user)         LISTEN <HALO_HOST>:13305  (HTTP, sin TLS)
│     ├── llama-server (Coder, Vulkan)      LISTEN 127.0.0.1:8001  (interno, gestionado)
│     └── llama-server (Thinking, Vulkan)   LISTEN 127.0.0.1:8002  (interno, gestionado)
├── (opcional, no residente por defecto) sd-server Vulkan (SDXL)
├── Docker Engine 29.7.2
│     ├── halostrix-llamafactory (LlamaBoard)   bind configurable, default 127.0.0.1:7860
│     └── halostrix-unsloth-studio (Studio)     bind configurable, default 127.0.0.1:8888
└── UFW activo (deny entrante por defecto, salvo reglas explícitas arriba)
```

**Puertos observados (HECHO MEDIDO, captura de `ss`/listeners):**

```text
LISTEN 0 128  <HALO_HOST>:13305   lemond (API OpenAI-compatible + Web App)
LISTEN 0 4096 <HALO_HOST>:9000    lemond (puerto auxiliar)
LISTEN 0 512  127.0.0.1:8001        llama-server (hijo Coder, interno)
LISTEN 0 512  127.0.0.1:8002        llama-server (hijo Thinking, interno)
```

No existía listener `127.0.0.1:13305` en la observación fechada: la API de
Lemonade sólo escucha en la IP LAN. LlamaBoard (7860) y Unsloth Studio
(8888) están **configurados con bind por defecto `127.0.0.1`**
(`workspaces/llama-factory/.env.example`, `workspaces/unsloth-studio/.env.example`);
cambiar `WEB_BIND=0.0.0.0` es una operación manual documentada en sus README,
no el estado por defecto.

**Todo el tráfico anterior es HTTP en texto plano.** No hay terminación TLS
en ningún punto de esta arquitectura (ver §15).

---

## 7. Lemonade Server: instalación y operación

Fuente principal: `docs/auditoria-ssh-inicial.md`, `docs/validacion-lemonade-vulkan.md`.

### 7.1 Instalación (HECHO MEDIDO)

- Paquete `lemonade-server` desde `cachyos-extra-znver4`, versión inicial
  **11.7.0-2.1**, posteriormente sucedida por **11.8.1** según
  `docs/comparativa-qwen38-halo-strix.md` (paquete `/usr/bin/lemonade`).
- Backend administrado: `llamacpp:vulkan`, binario `b10375 (ba360efe1)`,
  build `2026-08-12`.
- Directorios de modelos configurados con **rutas absolutas**:
  `models_dir=<HOME>/ai/lemonade/models` (caché de descargas HF/ModelScope) y
  `extra_models_dir=<HOME>/ai/models/smoke` (escaneo recursivo de GGUF
  propios). Ver incidente de resolución de `~` en §16.

### 7.2 Servicio systemd de usuario y `linger`

| Momento | `lemond` (user) | `Linger` | Consecuencia |
| --- | --- | --- | --- |
| Gate final 2026-08-25 (histórico) | `enabled`/`active` | `Linger=no` | El servicio sólo sobrevive mientras hay una sesión de login activa; un reinicio sin login no lo arranca. |
| Chequeo post-traslado 2026-08-26 | `enabled`/`active` (sin intervención) | seguía `Linger=no` | Avisado como riesgo: el user manager arrancó porque hubo login SSH durante la comprobación. |
| Estado reconfirmado (`docs/comparativa-qwen38-halo-strix.md`, 2026-09-04) | `enabled`/`active` | **`Linger=yes`** | **CONFIGURADO Y VALIDADO**: `loginctl show-user -p Linger` devolvió `Linger=yes` en una conexión SSH independiente, con `lemond.service` activo y `/api/v1/health` respondiendo HTTP 200 sin sesión de login previa necesaria. |

**Recuperación si Lemonade está parado (RECOMENDACIÓN operativa, basada en
los comandos ya usados en las validaciones):**

```bash
systemctl --user status lemond.service
systemctl --user start lemond.service
# Si tras un restart no vuelve a levantar el bind LAN esperado:
systemctl --user restart lemond.service
loginctl show-user -p Linger    # confirmar que persiste sin sesión activa
```

### 7.3 Listener LAN, firewall y CORS

- **Bind LAN directo** (no reverse proxy dedicado): `host=<HALO_HOST>`,
  `port=13305`, `broadcast=false`. Aplicado con:

  ```text
  lemonade config set host=<HALO_HOST>
  systemctl --user restart lemond.service
  ```

- **Firewall (UFW)**, regla mínima real aplicada:

  ```text
  sudo ufw allow in on wlan0 from <LAN_CIDR> to <HALO_HOST> \
    port 13305 proto tcp comment 'Lemonade LAN TCP 13305'
  ```

  Sólo TCP/13305 entrante desde `<LAN_CIDR>` por `wlan0`; sin IPv6, sin
  wildcard, sin regla de router.

- **CORS**: el origen LAN exacto (`http://<HALO_HOST>:13305`) se autorizó
  mediante un archivo de entorno leído por la unidad empaquetada
  (`EnvironmentFile=-%E/lemonade/conf.d/*.conf`):

  ```ini
  # ~/.config/lemonade/conf.d/allowed-origins.conf
  LEMONADE_ALLOWED_ORIGINS=http://<HALO_HOST>:13305
  ```

  Un origen distinto (`evil.invalid`) recibe **403** (`Origin not allowed`);
  el `Origin` LAN exacto recibe 200 con `Access-Control-Allow-Origin`
  correcto. **No hay API key**: es un riesgo LAN deliberadamente aceptado,
  documentado, no un fallo de CORS.

### 7.4 Reverse proxy

**No existe un reverse proxy dedicado (nginx/Caddy/Traefik) delante de
Lemonade en ninguna fuente autorizada.** El acceso LAN se logra por **bind
directo del propio proceso** a la IP LAN del host más una regla de firewall,
no por un proxy intermedio. Ver §15 para el estado de HTTPS/TLS.

### 7.5 Healthchecks

```text
curl -sS http://<HALO_HOST>:13305/api/v1/health
```

Criterio de éxito documentado: HTTP 200, `status:"ok"`, modelos de
producción listados en `all_models_loaded` con `backend_alive:true`
(`docs/comparativa-qwen38-halo-strix.md` §10). El script
`scripts/test-lemonade.ps1`, invocable directamente desde una terminal
PowerShell en la raiz del repositorio, automatiza un
healthcheck extendido: valida `/v1/models`, confirma que el modelo
solicitado está publicado y ejecuta un `POST /chat/completions` de smoke.

**Contrato actual del repositorio (2026-09-07):** `-BaseUrl` y `-Model`
son obligatorios y no tienen valores por defecto. Omitirlos no elige
automaticamente un destino ni un modelo.

**Advertencia historica:** la version anterior seleccionaba
`Qwen3-1.7B-Q8_0` y una direccion por defecto. Con Coder+Thinking residentes,
ese smoke podia expulsar uno por LRU. El riesgo de autocarga/expulsion
permanece si ahora se elige explicitamente un modelo no residente.
Para operacion diaria, confirmar residencia y pasar ambos argumentos:

```text
powershell -File scripts/test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

Verificar el `model_name` exacto en `/v1/models` (§16.5) antes de smoke
tests en un entorno con modelos de producción residentes.

### 7.6 Recuperación si el servicio está parado

```text
systemctl --user start lemond.service
sleep 5
curl -sS http://<HALO_HOST>:13305/api/v1/health
```

Si el bind vuelve a `127.0.0.1` tras una reinstalación/actualización,
reaplicar `host=<HALO_HOST>` (§7.3). Si `Linger` aparece como `no` tras un
cambio de sistema (actualización, reinstalación), volver a habilitarlo con
`loginctl enable-linger "${SSH_USER}"` y reconfirmar con `loginctl show-user -p
Linger` (comando estándar de systemd-logind; no se documenta una ejecución
local de este comando concreto en las fuentes, sólo su resultado
`Linger=yes` verificado — tratar como **RECOMENDACIÓN** si hay que
reaplicarlo).

---

## 8. llama.cpp/Lemonade: modelos, parámetros y KV cache

Fuente: `docs/comparativa-qwen38-halo-strix.md` §3, §4, §9.

### 8.1 Catálogo de modelos del baseline documentado

| Modelo | Rol | Tamaño en disco (GGUF) | Estado |
| --- | --- | ---: | --- |
| `Qwen3-Coder-30B-A3B-Instruct` (Q4_K_M) | Coding, non-thinking | 18,556,689,568 B ≈ **17.28 GiB** | HECHO MEDIDO — cargado |
| `Qwen3-30B-A3B-Thinking-2507` (Q4_K_M) | Razonamiento, always-thinking | ~17–18 GiB (no medido exacto en la fuente) | HECHO MEDIDO — cargado |

**El tamaño del GGUF en disco no es el consumo de memoria en runtime.** El
runtime añade KV cache (según `--ctx-size`, `--parallel` y cuantización K/V)
y buffers de cómputo Vulkan. Regla explícita de la fuente: cualquier
estimación de capacidad debe basarse en el **GTT medido con el proceso
corriendo**, no en el tamaño del archivo.

### 8.2 Parámetros exactos de carga (HECHO MEDIDO)

**Coder** (puerto interno 8001):

```bash
$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server \
  -m $HOME/ai/lemonade/models/models--unsloth--Qwen3-Coder-30B-A3B-Instruct-GGUF/snapshots/b17cb02dd882d5b6ab62fc777ad2995f19668350/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf \
  --ctx-size 196608 --port 8001 --jinja --metrics \
  --parallel 3 --kv-unified --flash-attn on --cache-reuse 256 \
  --cache-type-k q8_0 --cache-type-v q8_0
```

**Thinking** (puerto interno 8002):

```bash
$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server \
  -m $HOME/ai/lemonade/models/models--unsloth--Qwen3-30B-A3B-Thinking-2507-GGUF/snapshots/a9b37aaac12b2bd0098783a443429543dd76a14d/Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf \
  --ctx-size 98304 --port 8002 --jinja --metrics \
  --parallel 1 --kv-unified --flash-attn on \
  --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384
```

| Parámetro | Coder | Thinking |
| --- | --- | --- |
| Contexto (`--ctx-size`) | 196,608 (pool KV **total**, no por slot) | 98,304 |
| Slots (`--parallel`) | 3 | 1 |
| Capacidad efectiva aprox. por petición | ~65,536 tokens (196,608 ÷ 3; reparto dinámico, no partición fija) | 98,304 (slot único) |
| KV unificado | `--kv-unified` | `--kv-unified` |
| Flash Attention | `--flash-attn on` | `--flash-attn on` |
| Cache reuse | `--cache-reuse 256` | no configurado |
| KV cache K/V | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| Presupuesto de razonamiento | n/a (non-thinking) | `--reasoning-budget 16384` |

### 8.3 `max_loaded_models=2` (CONFIGURADO Y VALIDADO)

- El CLI oficial (`lemonade config set`) **no puede aplicar este cambio en
  este host**, porque el cliente por defecto apunta a `127.0.0.1:13305` y
  `lemond` sólo escucha en la IP LAN.
- Aplicado correctamente vía el endpoint interno:

  ```text
  curl -sS -X POST http://<HALO_HOST>:13305/internal/set \
    -H 'Content-Type: application/json' \
    --data '{"max_loaded_models":2}'
  ```

- Verificado en `GET /internal/config` (`max_loaded_models=2`), `GET
  /api/v1/health` (`max_models.llm=2`) y persistido en `config.json` (línea
  41). **No requirió reiniciar `lemond`**: el cambio es en caliente y
  persistente en disco.

### 8.4 Carga/descarga segura vía API

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

> ⚠️ **Colisión de IDs conocida:** `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`
> es el registro **de usuario** (`user.*`), distinto del ID base/built-in
> `Qwen3-Coder-30B-A3B-Instruct-GGUF`. Ambos coexisten sin alias para el
> mismo repo. **No sustituir `model_name` sin antes consultar el catálogo**
> (`GET /v1/models`), por el incidente documentado en
> `docs/validacion-lemonade-vulkan.md` (ver §16.5).

Descarga segura (nunca usar `/api/v1/delete`, que borra del disco):

```text
curl -sS -X POST http://<HALO_HOST>:13305/api/v1/unload \
  -H 'Content-Type: application/json' \
  --data '{"model_name": "<model_name-exacto>"}'
```

### 8.5 Smoke tests

- Chat OpenAI-compatible: `POST /v1/chat/completions` con `stream:false`,
  `max_tokens` bajo, verificando HTTP 200 y contenido no vacío
  (`content` o `reasoning_content`).
- Script reproducible ya existente en el repo:
  `scripts/test-lemonade.ps1`, que valida `/v1/models` y
  `/chat/completions` con timeout de 90 s. Desde 2026-09-07 requiere
  `-BaseUrl` y `-Model`, sin defaults; seleccionar un modelo no residente
  puede provocar una expulsion LRU. Ver §7.5.
- **No confundir una descarga completa (`downloaded=true`, hash verificado)
  con una carga/ejecución validada.** Varios modelos del catálogo están
  descargados sin una carga encontrada en la evidencia consultada entonces
  (ver §11 para la contradicción histórica de Qwen3.8-27B).

---

## 9. Estado Coder + Thinking, memoria y concurrencia

Fuente: `docs/comparativa-qwen38-halo-strix.md` §3.3, `docs/validacion-lemonade-vulkan.md` (Diagnóstico de concurrencia).

### 9.1 GTT/VRAM con ambos modelos residentes (HECHO MEDIDO)

| Proceso | Puerto | GTT medido | Notas |
| --- | --- | ---: | --- |
| Coder Q4_K_M | 8001 | **25.62 GiB** | ctx 196,608, `--parallel 3` |
| Thinking-2507 Q4_K_M | 8002 | **22.40 GiB** | ctx 98,304, `--parallel 1` |
| **Total** | — | **48.02 GiB** de 61.73 GiB (≈77.8 %) | `mem_info_gtt_used` coincide exactamente con la suma |
| VRAM dedicada | — | ≈1.9 de 2.0 GiB | — |

Margen libre resultante: ~13.71 GiB (~22 %), dentro de la regla operativa de
conservar **≥8 GiB o ≥10 %** de GTT libre, pero **sin holgura para un tercer
modelo grande**. Ambos procesos aparecen con `pinned:false` en
`/api/v1/health`.

### 9.2 Concurrencia recomendada

- **Regla operativa medida:** máximo **3 solicitudes/generaciones activas
  combinadas** entre Coder y Thinking (hasta 3 en Coder + las que Thinking
  atienda con su slot único, sin exceder 3 en total) — no 3 modelos
  residentes.
- El diagnóstico de concurrencia de `docs/validacion-lemonade-vulkan.md`
  (2026-08-26) demostró **solapamiento de decode entre dos secuencias
  lógicas** (slots 0 y 2 de un modelo con 4 slots, en una configuración
  histórica anterior), pero **no demuestra simultaneidad física en GPU, TTFT
  ni mejora de wall-clock**. Recomendación provisional para agentes de
  código interactivos: **dos agentes con requests independientes reales**,
  hasta 32k de contexto por agente, sin subir a 3–4 agentes sin medir antes
  N=1/N=2/N=4 con barrera controlada.
- No se recomienda cargar un tercer modelo de tamaño comparable (30B+ o
  denso 27B+) sin repetir esa misma metodología de contraste N=1/N=2/N=3.

### 9.3 Semántica de thinking/reasoning

- `--reasoning-format` (default `auto` en el binario `b10375`) es
  **exclusivamente un parser/formateador de salida** del bloque `<think>`;
  **no activa ni desactiva razonamiento**.
- **Coder** es *non-thinking* por diseño de plantilla (sin tags `<think>`).
- **Thinking-2507** es *always-thinking*: siempre emite razonamiento;
  `--reasoning-format` sólo decide si aparece en `content` o en
  `reasoning_content` del JSON de respuesta.
- Recomendaciones para agentes OpenCode que consuman este endpoint: `steps`
  del agente en ≥50 o sin límite superior explícito para tareas largas;
  terminar por evento observable (p. ej. URL de PR), no por conteo de
  turnos; usar `finish_reason` y número de `tool_calls` como señal de
  progreso. **No existe** un campo `max_tokens` a nivel de `AgentConfig` en
  OpenCode (el control de tokens de salida vive a nivel de
  proveedor/modelo, p. ej. `budgetTokens`).

---

## 10. Investigación vLLM

**Estado: investigado y diagnosticado en sesión, pero NO CONSOLIDADO EN
EVIDENCIA VERSIONADA ni promovido a producción.**

### 10.1 Lo que dicen las fuentes versionadas autorizadas

Se revisó `docs/*.md` y los workspaces `llama-factory` y
`unsloth-studio`.
**No existe en ninguna fuente autorizada (repositorio versionado) un
documento de investigación, diagnóstico o prueba de vLLM ejecutada en este
host**, ni un informe de un fallo de "Qwen3.6-27B FP16" bajo vLLM. Por lo
tanto, en lo que respecta al repositorio:

- **No se afirma** (con base en fuentes versionadas) que vLLM se haya
  instalado, ejecutado o fallado en este host.
- Lo único documentado en el repo sobre vLLM es su mención como **backend
  experimental de Lemonade** en el plan de research
  (`docs/plan-configuracion-halo-strix.md` §3, §9): la fuente oficial de
  Lemonade indica `gfx1151` como validado para su backend vLLM, pero esto
  es una referencia a documentación externa, **no una prueba local
  versionada**.

### 10.2 HECHO OBSERVADO EN SESIÓN — evidencia cruda no versionada

El siguiente es un resumen anonimo de trabajo historico reportado, sin
registros publicos independientes de reproduccion. Se distingue de las
validaciones de §10.1. **Debe revalidarse antes de usarse como procedimiento
reproducible**; esta publicacion no depende de archivos privados ni
proporciona rutas para recuperarlos:

- Se investigó vLLM para `gfx1151`; AMD lista Ryzen AI Max+ 395 como
  plataforma soportada.
- vLLM puede aportar mejor batching, scheduling/cola y TTFT
  (time-to-first-token) bajo concurrencia, pero **no hay evidencia local
  de que mejore el decode individual** frente a llama.cpp Vulkan (backend
  actual de producción, §5, §8).
- El soporte de GGUF en vLLM sigue siendo **experimental**; AWQ/GPTQ en
  `gfx1151` requería validación propia, no realizada.
- Se intentó cargar el modelo `Qwen3.6-27B-FP16-vLLM` desde Lemonade con
  **vLLM 0.20.1, ROCm 7.12 y PyTorch 2.10**.
- Los pesos **se cargaban correctamente**, pero el backend sufría un
  **segfault nativo durante la inicialización de la arquitectura
  híbrida**. Se descartó explícitamente que fuera un problema de **OOM**
  o de **descarga corrupta**.
- Se identificó un **bundle prerelease más reciente para `gfx1151`**, pero
  **no se promovió** a uso.
- **Recomendación final (de la sesión):** conservar **llama.cpp Vulkan**
  en el baseline y, si se retoma vLLM en el futuro, hacerlo como una **POC
  aislada**, sin sustituir el servicio de referencia durante la prueba.

### 10.3 Limitaciones GGUF relevantes (HECHO MEDIDO, aplicables a la ruta
llama.cpp/Lemonade actual, no específicas de vLLM)

- Las cuantizaciones dinámicas Unsloth (`UD-Q4_K_XL`, capas `IQ4_XS`) tienen
  reportes externos de crash en Vulkan/AMD con prompts largos (ver §11,
  issue #27431). Esto es evidencia contra una combinación
  Vulkan+GGUF+cuantización dinámica bajo ciertas condiciones, no contra
  GGUF en general.
- El formato GGUF exige que la arquitectura del modelo esté soportada por el
  binario `llama-server` exacto en uso; el bloqueo de Qwen3.8-Flash-Next
  (`qwen4exp` desconocido para `b10375`) es un ejemplo medido de esta
  limitación (§11, §16.8).

### 10.4 Recomendación consolidada

Combinando §10.1 (fuentes versionadas) y §10.2 (evidencia de sesión, no
versionada): si se requiere evaluar vLLM en este host, tratarlo como un
experimento nuevo e independiente, con su propio documento de validación
versionado (`docs/validacion-vllm-*.md`) que **revalide** el diagnóstico de
§10.2 y mida explícitamente FP16 vs GGUF, footprint de memoria real y
estabilidad, antes de cualquier afirmación de viabilidad o fallo como
procedimiento reproducible. La ruta recomendada actual sigue siendo
**llama.cpp vía Lemonade/Vulkan** (§5, §8), por tener evidencia medida de
estabilidad en este host.

---

## 11. Qwen3.8-27B y Flash-Next

**Documento fuente completo (no duplicado aquí):**
[`docs/comparativa-qwen38-halo-strix.md`](comparativa-qwen38-halo-strix.md).

### 11.1 Resumen — Qwen3.8-27B

- Repo: `unsloth/Qwen3.8-27B-GGUF`, variante `UD-Q4_K_XL`; **17.22 GiB en
  disco** (pesos + `mmproj-BF16.gguf`).
- Arquitectura GGUF `qwen35`, ya soportada por el `b10375` administrado (a
  diferencia de `qwen4exp`).
- **Descargado íntegramente y con hash verificado; este informe no encontró
  una carga en el journal consultado, pero otra fuente histórica sí registra
  una.** La contradicción sigue abierta.
- Riesgo identificado: issue upstream llama.cpp
  [#27431](https://github.com/ggml-org/llama.cpp/issues/27431) (crash
  Vulkan/AMD con prompts largos y cuantización dinámica Unsloth, en
  hardware distinto — R9700, no Strix Halo). Tratado como riesgo real, no
  descartado.
- **Recomendación:** POC controlada y aislada (no sustituir Coder; sólo
  reemplazar temporalmente Thinking-2507), con casos de prueba de prompt
  corto/medio/largo, tool calling y visión, antes de cualquier promoción.
  **No se ha ejecutado esta POC.**

### 11.2 Resumen — Qwen3.8-Flash-Next

- Repo: `unsloth/Qwen3.8-Flash-Next-GGUF`, variante `UD-Q4_K_XL`; **104.53
  GiB en disco** (4 shards + mmproj) — no cabe en los 61.73 GiB de GTT
  disponibles junto a ningún otro modelo.
- Arquitectura GGUF `qwen4exp`: **bloqueada** en el binario administrado
  `b10375` (`unknown model architecture: 'qwen4exp'`). Requiere un build
  posterior a la PR upstream
  [#27941](https://github.com/ggml-org/llama.cpp/pull/27941) (fusionada
  2026-09-01), posterior a nuestro build (2026-08-12).
- Rendimiento comunitario citado (17–47 tok/s según configuración) es
  **ESTIMACIÓN de terceros sobre ROCm, no reproducida en este host**.
- **Recomendación: no perseguir en el ciclo actual.** Queda exclusivamente
  como línea futura/experimental, condicionada a un build actualizado y una
  POC aislada independiente de la de Qwen3.8-27B.

### 11.3 Recomendación consolidada

**Mantener como baseline de este informe Coder + Thinking-2507.** Ninguno de
los dos modelos Qwen3.8 sustituye hoy a ese par; no existe benchmark local
que lo respalde y Flash-Next está técnicamente bloqueado.

---

## 12. Entrenamiento: Docker/ROCm/PyTorch validado

Fuente: `docs/validacion-entrenamiento-rocm.md`.

### 12.1 Docker Engine (HECHO MEDIDO)

- Se instaló únicamente `docker`, se habilitó/inició `docker.service` con
  `sudo`; **el usuario no se añadió al grupo `docker`** (se opera con
  `sudo docker ...`).
- `sudo docker version` confirmó Docker Engine **29.7.2** cliente y
  servidor.

### 12.2 Smoke de entrenamiento ROCm en contenedor (HECHO MEDIDO)

- Imagen retenida por digest exacto:
  `rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`
  (PyTorch `2.12.0+rocm7.14.0`, HIP `7.14.60850`, ≈18.04 GiB).
- Comando reproducible (una sola ejecución efímera con `--rm`, sin
  `--privileged`, sin `--ipc=host`, sin override de seccomp):

  ```bash
  cat <<'SMOKE' | sudo docker run --rm \
    --device=/dev/kfd --device=/dev/dri --shm-size=8g \
    rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad bash
  set -euo pipefail
  rocminfo | grep -m1 gfx1151
  python3 - <<'PY'
  import torch
  assert torch.version.hip and torch.cuda.is_available() and torch.cuda.device_count() >= 1
  print(torch.__version__, torch.version.hip, torch.cuda.get_device_name(0))
  for dtype in (torch.float16, torch.bfloat16):
      a = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
      b = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
      loss = (a @ b).float().square().mean()
      loss.backward()
      torch.cuda.synchronize()
      assert torch.isfinite(loss) and torch.isfinite(a.grad).all() and torch.isfinite(b.grad).all()
      print(dtype, loss.item(), torch.cuda.memory_allocated(), torch.cuda.memory_reserved())
  PY
  SMOKE
  ```

- Resultado: `rocminfo` detectó `gfx1151`; PyTorch confirmó `2.12.0+rocm7.14.0`,
  HIP `7.14.60850`, `AMD Radeon 8060S Graphics`; **FP16** pérdida
  `2047.4448` y **BF16** pérdida `2047.9354`, ambos con gradientes finitos
  tras `backward()` + `synchronize()`.
- Verificación posterior: 0 eventos AMDGPU/KFD/OOM/reset en journal filtrado,
  temperatura estable (32.0 °C antes/después), y `lemond.service` se detuvo
  temporalmente durante el smoke y se restauró correctamente al finalizar
  (bind exclusivo `127.0.0.1:13305` en esa validación puntual, healthcheck
  <5 s).

### 12.3 Alcance explícito de esta validación

**Por directiva del propietario, el alcance terminó tras el pull/smoke
PyTorch ROCm y la restauración de Lemonade.** No se iniciaron, instalaron ni
evaluaron Unsloth, QLoRA, datasets ni pasos posteriores de entrenamiento en
esta validación puntual (el trabajo posterior de LLaMA-Factory/Unsloth
Studio, descrito en §13–§14, es un desarrollo independiente y posterior).

---

## 13. LLaMA-Factory / LlamaBoard

Fuente: `workspaces/llama-factory/README.md`, `compose.yaml`, `Dockerfile`,
`.env.example`, `build.sh`, `start.sh`, `status.sh`, `stop.sh`, `logs.sh`,
`cleanup.sh`, `scripts/common.sh`.

### 13.1 Despliegue (CONFIGURADO)

- Base fijada por digest: `rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`
  (PyTorch `2.12.0+rocm7.14.0`, HIP 7.14 — la misma base validada en §12).
- LLaMA-Factory **v0.9.5**, commit `7af909522a951e3ad9f022ea6f88b6755257eaa5`,
  descargado por commit (no `main`) vía `codeload.github.com`.
- El workspace es autocontenido: **no arranca entrenamiento por sí solo ni
  administra otros servicios del host** (no toca Lemonade, red host, socket
  Docker, `ipc:host` ni `/opt/rocm` del host).
- Etiqueta el build como **no reproducible byte a byte** (APT y
  dependencias Python transitivas se resuelven en cada build); el ID
  `sha256` real de la imagen se persiste en `.last-built-image` para
  reproducibilidad funcional.

### 13.2 Paths y persistencia

| Host | Contenedor | Contenido |
| --- | --- | --- |
| `data/hf-cache` | `/workspace/hf-cache` | caché Hugging Face |
| `data/models` | `/workspace/models` | modelos explícitos |
| `data/datasets` | `/workspace/data` | datasets y catálogo |
| `data/outputs` | `/workspace/saves` | adaptadores/checkpoints |
| `data/cache` | `/workspace/cache` | Torch/Triton/compilación |
| `data/config` | `/workspace/config` | configuraciones locales |
| `data/logs` | `/workspace/logs` | `llamaboard.log` |

Todos son **bind mounts** (no volúmenes Docker anónimos); `docker compose
down` no los borra.

### 13.3 Comandos operativos (HECHO, tal como documentados en el README)

```bash
cp .env.example .env
chmod +x build.sh start.sh stop.sh status.sh logs.sh scripts/common.sh
./build.sh      # construye imagen, valida BASE_IMAGE por digest y commit SHA-40
./start.sh      # arranca sin reconstruir (--no-build), espera healthcheck ≤60 intentos de 2s
./status.sh     # docker compose ps con entorno de control neutro
./logs.sh
./stop.sh
```

Arrancar el último artefacto exacto sin resolver APT/Python de nuevo:

```bash
RUN_IMAGE="$(cat .last-built-image)" ./start.sh
```

Bind LAN (RECOMENDACIÓN documentada, no el default): en `.env`,
`WEB_BIND=0.0.0.0` + firewall del host ya administrado (el workspace no
modifica reglas).

Healthcheck del compose:

```yaml
test: ["CMD","python3","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=5).read(1)"]
interval: 15s
timeout: 8s
retries: 20
start_period: 45s
```

### 13.4 POC LoRA BF16 (no QLoRA) — CONFIGURADO, no ejecutado

El README documenta el procedimiento (SFT, LoRA, BF16, batch 1, acumulación
8, longitud 1024, hasta 100 muestras, salida
`/workspace/saves/poc-lora-bf16`) y provee una plantilla
`examples/poc-lora-bf16.yaml` con placeholders `CHANGE_ME` que **no se
invoca automáticamente**. **No hay evidencia en las fuentes de que este POC
se haya ejecutado**; se documenta como procedimiento disponible, no como
entrenamiento validado.

### 13.5 Limpieza segura

```bash
./cleanup.sh                 # inventario, igual que --dry-run
./cleanup.sh --dry-run
./cleanup.sh --all           # exige escribir una frase de confirmación
./cleanup.sh --all --yes     # automatización explícita
./cleanup.sh --all --include-base   # además borra la imagen base ROCm compartida
```

`cleanup.sh` valida ownership por **labels exactos**
(`com.halostrix.project`, `com.halostrix.service`) antes de borrar cualquier
recurso Docker, revalida cada recurso inmediatamente antes de eliminarlo, no
usa `prune` ni comodines, y sólo actúa sobre bind mounts (no hay volúmenes
Docker que gestionar). `--dry-run` domina cualquier combinación con `--all`
y `--yes`. **`--all` es irreversible** sobre `data/{hf-cache,models,datasets,
outputs,cache,config,logs}` salvo copia externa previa.

### 13.6 Estado documentado en la fecha del informe

**CONFIGURADO, sin entrenamiento real validado end-to-end.** El workspace
está completo y con tests (`tests/test-cleanup.sh`), pero no hay evidencia
en las fuentes autorizadas de una ejecución de entrenamiento real ni de un
smoke de GPU dentro del contenedor LlamaBoard.

---

## 14. Unsloth Studio

Fuente: `workspaces/unsloth-studio/README.md`, `compose.yaml`, `Dockerfile`,
`.env.example`, `scripts/common.sh`, `scripts/container-entrypoint.sh`,
`scripts/verify_stack.py`, `tests/*.sh`.

### 14.1 Estado del stack (HECHO MEDIDO, validación 2026-09-01)

> Título literal de la fuente: **"Estado del stack: UI validada;
> entrenamiento no validado."**

- Base fijada por digest completo:
  `rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80`
  (`rocm/pytorch:rocm7.14_ubuntu24.04_py3.12_pytorch_release_2.11.0`).
- Dentro de la base: PyTorch `2.11.0+rocm7.14.0`, torchvision
  `0.26.0+rocm7.14.0`, torchaudio `2.11.0+rocm7.14.0`, Triton
  `3.7.1+git0263a6a6.rocm7.14.0`, HIP `7.14.60850` — PyTorch 2.11 está
  dentro del rango soportado por Unsloth (`<2.12`), pero **eso habilita el
  build, no es en sí mismo una prueba de soporte funcional**.
- Validado: build y `pip check` correctos; `import torch`, `import triton`,
  `import unsloth`, healthcheck y SPA (frontend) pasaron; Torch detectó
  `AMD Radeon 8060S Graphics`, `gfx1151`, GPU disponible.
- **`bitsandbytes` no está instalado ⇒ QLoRA 4-bit NO está disponible en
  este stack.** No se afirma que QLoRA funcione.
- Unsloth Zoo avisó que su ruta FLA no considera Triton soportado en esta
  plataforma y usaría CPU para esa ruta (limitación conocida, no corregida).
- **No se inició entrenamiento**: el resultado valida la Studio web y la
  detección de GPU, **no** la compatibilidad de entrenamiento real (LoRA
  BF16 pendiente de una ejecución real, ver §14.5).

### 14.2 Fijaciones verificadas

| Elemento | Valor |
| --- | --- |
| Commit Unsloth | `e18a069c15cde98c7af77ccdb952254db8b0315d` |
| SHA-256 tarball codeload | `52037b47de581f360e1db0a2072e65202d8993782e99f0300f181df93c63eeb8` |
| Imagen Node (frontend) | `node@sha256:35531c52ce27b6575d69755c73e65d4468dba93a25644eed56dc12879cae9213` |
| CLI headless verificado en fuente/CI | `unsloth studio -H 0.0.0.0 -p 8888` (sin `--api-only`, que deshabilitaría el frontend) |
| Healthcheck | `GET /api/health` |
| Licencia Core (`unsloth/*`) | Apache-2.0 |
| Licencia Studio/CLI (`studio/*`, `unsloth_cli/*`) | **AGPL-3.0-only** (obligaciones de fuente correspondiente si se redistribuye) |

### 14.3 Reverse proxy HTTP y autenticación (sin exponer contraseña)

- **No hay un reverse proxy dedicado** (nginx/Caddy) documentado para
  Unsloth Studio; el patrón de exposición es el mismo que Lemonade y
  LlamaBoard: **bind directo del contenedor** vía `WEB_BIND`/`WEB_PORT`
  (`127.0.0.1:8888` por defecto), configurable a LAN cambiando `WEB_BIND` y
  protegiendo con el firewall ya administrado del host (el workspace no
  modifica reglas de firewall).
- **Autenticación:** `UNSLOTH_STUDIO_PASSWORD` se define únicamente en
  `.env` (modo `600`) y se entrega al bootstrap oficial de Studio. El
  entrypoint (`scripts/container-entrypoint.sh`) es explícito: si ya existe
  una base de autenticación (`auth.db`) con un usuario admin creado,
  **`UNSLOTH_STUDIO_PASSWORD` se `unset` antes de arrancar** — la contraseña
  sólo se usa para el bootstrap inicial, no se reenvía en cada arranque una
  vez que ya hay un admin. Esto es la mitigación documentada contra
  reexposición accidental de la contraseña en el entorno del proceso largo.
  **Este documento no reproduce ni ha leído el valor real de esa
  contraseña.**
- La recuperacion de acceso corresponde al operador mediante los mecanismos
  privados de autenticacion. No imprimir contraseñas ni copiar el archivo
  de secretos a registros o documentos publicos.

### 14.4 ROCm y ejecución como usuario no root

- El contenedor corre como el **UID/GID no-root del propietario host** de
  los datos (`start.sh` usa `id -u`/`id -g` o `SUDO_UID`/`SUDO_GID`),
  corrige la propiedad de los cuatro bind mounts y falla si no puede
  dejarlos escribibles. La imagen conserva UID/GID `10001` como fallback.
- Contrato actualizado el 2026-09-07: `.env.example` deja `DEVICE_GID`
  vacio y Compose exige configurarlo explicitamente. Studio **no autodetecta**
  ese GID: medirlo con `stat -c '%g' "$RENDER_DEVICE"` y guardar el numero
  observado en la configuracion privada. El antiguo GID predefinido no es
  un default vigente. Este grupo suplementario preserva acceso GPU aunque
  cambie el UID primario; es distinto de `HOST_UID`/`HOST_GID`.
- LLaMA-Factory si permite dejar `DEVICE_GID` vacio para que su `start.sh`
  lo detecte; no trasladar esa semantica al workspace de Studio.
- No usa `privileged`, socket Docker, red host, `ipc:host`, `/opt/rocm` del
  host, `HSA_OVERRIDE_GFX_VERSION` ni mapeo completo de `/dev/dri`.

### 14.5 Persistencia

| Host | Contenedor | Semántica |
| --- | --- | --- |
| `data/studio` | `/home/unsloth/.unsloth/studio` | Studio home completo: DB, auth, assets, outputs, exports, runs, caches, binarios |
| `data/hf-cache` | `/workspace/hf-cache` | `HF_HOME`, hub y Transformers |
| `data/projects` | `/workspace/projects` | `UNSLOTH_STUDIO_PROJECTS_HOME` |
| `data/tmp` | `/workspace/tmp` | temporales y caches de recetas/validadores |

### 14.6 Scripts, tests y limpieza

```bash
cp .env.example .env
chmod +x build.sh start.sh stop.sh status.sh logs.sh cleanup.sh scripts/common.sh
./build.sh
./start.sh       # siempre usa --no-build
./status.sh
./logs.sh
./stop.sh
```

Selección de imagen sin reconstruir:

```bash
RUN_IMAGE=last ./start.sh
RUN_IMAGE=previous ./start.sh
```

Validación local sin GPU/daemon real:

```bash
find . -name '*.sh' -print0 | xargs -0 -n1 bash -n
./tests/test-shell-files.sh     # gate: falla ante cualquier byte CR en *.sh + bash -n
./tests/test-build-start.sh
./tests/test-cleanup.sh
./tests/test-ownership.sh       # valida chown por sudo simulado hacia SUDO_UID/SUDO_GID
```

Limpieza:

```bash
./cleanup.sh                          # inventario, no borra
./cleanup.sh --all                    # interactivo, exige frase "BORRAR HALOSTRIX UNSLOTH STUDIO"
./cleanup.sh --all --yes              # automatización
./cleanup.sh --all --include-base     # + frase "BORRAR BASE ROCM COMPARTIDA"
```

Igual que en LlamaBoard: labels exactos de proyecto/servicio, revalidación
inmediata antes de borrar, sólo bind mounts (sin volúmenes Docker), sin
`prune` ni comodines.

### 14.7 Limitaciones explícitas (no inventar mejoras)

- **QLoRA/bitsandbytes: NO disponible/NO validado.** `bitsandbytes` no está
  instalado en la imagen; no se afirma que QLoRA funcione en este stack.
- **LoRA BF16: pendiente de entrenamiento real.** La UI, GPU y salud del
  stack están validadas, pero **no hay ningún entrenamiento LoRA BF16
  ejecutado y verificado end-to-end** en Unsloth Studio según las fuentes
  disponibles.
- La ruta FLA de Unsloth Zoo cae a CPU en esta plataforma (Triton no
  soportado para esa ruta específica).

---

## 15. Reverse proxies y HTTPS/TLS

### 15.1 Endpoints HTTP operativos (HECHO MEDIDO)

| Servicio | Bind por defecto | Bind LAN posible | Mecanismo de exposición LAN |
| --- | --- | --- | --- |
| Lemonade Server (API + Web App) | — (config explícita) | `<HALO_HOST>:13305` | Bind directo del proceso + regla UFW puntual (§7.3) — **validado históricamente** |
| LlamaBoard | `127.0.0.1:7860` | `0.0.0.0:${WEB_PORT}` vía `.env` | Bind directo del contenedor Docker; firewall del host a cargo del operador — **documentado, no confirmado como ejecutado en LAN** |
| Unsloth Studio | `127.0.0.1:8888` | `0.0.0.0:${WEB_PORT}` vía `.env` | Igual que LlamaBoard — **documentado, no confirmado como ejecutado en LAN** |

En **ningún caso** hay un reverse proxy dedicado (nginx, Caddy, Traefik,
etc.) en las fuentes autorizadas: la exposición LAN se logra siempre por
**bind directo del proceso/contenedor a la interfaz de red**, combinado con
reglas de firewall específicas por host y puerto.

### 15.2 HTTPS/TLS — PENDIENTE, no operativo

**No debe describirse HTTPS como operativo en ningún servicio de este
host.** Todas las fuentes confirman tráfico HTTP en texto plano:

- Lemonade: API y Web App servidos por `http://<HALO_HOST>:13305/`, sin
  certificado TLS, sin terminación HTTPS documentada en ninguna validación.
- LlamaBoard y Unsloth Studio: healthchecks y binds documentados
  explícitamente sobre `http://127.0.0.1:<puerto>/...`.
- El script actual `scripts/test-lemonade.ps1` requiere una URL HTTP(S)
  explicita y no aporta ningun esquema/destino por defecto. Los smokes
  historicos documentados usaron HTTP; admitir HTTPS como parametro no
  demuestra que exista TLS en el host.

**PENDIENTE (RECOMENDACIÓN, no ejecutado):** si se requiere cifrado en
tránsito para acceso remoto, las opciones evaluables (no evaluadas todavía
en este host) son: (a) túnel SSH ad-hoc hacia los puertos loopback
originales, ya mencionado como opción en `docs/plan-configuracion-halo-strix.md`
§3, o (b) desplegar un reverse proxy TLS dedicado delante de cada servicio,
lo cual requeriría un documento de validación propio (certificados,
renovación, cabeceras) antes de promoverlo. Ninguna de las dos está
configurada hoy.

---

## 16. Incidentes y troubleshooting

Fuente principal: `docs/validacion-lemonade-vulkan.md`,
`docs/comparativa-qwen38-halo-strix.md`, `workspaces/unsloth-studio/tests/`.

### 16.1 Lemonade detenido por `Linger=no`

**Síntoma:** el servicio de usuario `lemond` sólo sobrevivía mientras había
una sesión de login SSH activa; un reinicio del host sin login no lo
levantaba. **Causa:** `systemd --user` con `Linger=no` no persiste sin
sesión. **Resolución (HECHO MEDIDO, reconfirmado 2026-09-04):** `Linger=yes`
habilitado; verificado con `loginctl show-user -p Linger` en una conexión
SSH independiente, con el servicio ya activo antes del login. Ver §7.2.

### 16.2 CLI apuntando a `localhost`

**Síntoma:** `lemonade config set ...` y otras subórdenes de la CLI fallaban
con "Could not connect to Lemonade server". **Causa:** el cliente CLI usa
por defecto `127.0.0.1:13305`, pero `lemond` sólo escucha en la IP LAN.
**Workaround aplicado:** usar el endpoint interno HTTP directamente
(`POST /internal/set`) o pasar explícitamente `--host`/`--port` al CLI
cuando esté disponible esa opción (usado en la corrección de
`models_dir`, §16.7). Ver §8.3.

### 16.3 LRU con `max_loaded_models=1` (histórico)

Antes de elevar `max_loaded_models` a 2, el límite de un modelo residente
implicaba que cargar un segundo modelo forzaba la expulsión (`Evicted
model`) del anterior. Esto se documentó explícitamente en el incidente de
restauración del 2026-08-27 (`docs/validacion-lemonade-vulkan.md`): la
traza de journal mostró la expulsión de `Qwen3-Coder-30B-A3B-Instruct-GGUF`
justo antes de intentar cargar Qwen3.8-Flash-Next. **Resolución:** elevar
`max_loaded_models=2` (§8.3) permite mantener Coder + Thinking residentes
simultáneamente.

### 16.4 Fallos de carga dual / incompatibilidad de arquitectura

El intento de cargar **Qwen3.8-Flash-Next** (`qwen4exp`) en el backend
administrado `b10375` falló con:

```text
llama_model_load: error loading model: unknown model architecture: 'qwen4exp'
```

Esto ocurre en la fase de **metadata/arquitectura GGUF**, antes de
tokenizer, mmap o asignación Vulkan/GTT. No es un problema de ruta,
permisos, descarga ni OOM. Tras el fallo, `lemond` permaneció
`active/running` sin proceso hijo huérfano; se restauró el modelo anterior
(`Qwen3-Coder-30B-A3B-Instruct-GGUF`) mediante el mismo endpoint `/api/v1/load`
con sus opciones persistidas. Ver §11.2 y §16.8.

### 16.5 Colisión de IDs de catálogo

El catálogo de Lemonade puede tener **dos IDs sin alias** para el mismo
repo/artefacto: el registro base (`Qwen3-Coder-30B-A3B-Instruct-GGUF`) y el
registro de usuario (`...-Q4_K_M`). Comparten directorio de caché, no son
copias distintas. Un `POST /api/v1/delete` con el ID equivocado puede borrar
el archivo físico compartido de la variante activa. **Mitigación:**
consultar siempre `/v1/models` o `/api/v1/models?show_all=true` antes de
usar `model_name` en `/load`, `/unload` o `/delete`; nunca usar `/delete`
para simplemente descargar de memoria (usar `/unload`).

### 16.6 Flash-Next `qwen4exp` — bloqueo de arquitectura (detalle)

Ver §11.2 y §16.4. Requiere un build de llama.cpp posterior a la PR
[#27941](https://github.com/ggml-org/llama.cpp/pull/27941) (fusionada
2026-09-01); nuestro binario administrado (`2026-08-12`) es anterior.
**No se debe reintentar cargar este modelo en el `lemond` de producción**
mientras no exista ese build y una POC aislada aprobada.

### 16.7 Resolución de directorio de descargas (`~` no expandido)

**Síntoma:** al intentar descargar un modelo (`Pulling model:
user.Qwen3.8-27B-GGUF-UD-Q4_K_XL`), Lemonade falló con:

```text
Failed to create directory '/usr/bin/~/ai/lemonade/models': Read-only file system
```

**Causa raíz:** `models_dir` estaba configurado como `~/ai/lemonade/models`
(con tilde literal); Lemonade 11.7 **no expande `~`** para esta clave y la
resolvió como ruta relativa al directorio del ejecutable (`/usr/bin`), no al
`HOME` del proceso. **Corrección aplicada (HECHO MEDIDO):**

```text
lemonade --host <HALO_HOST> --port 13305 --no-discovery \
  config set models_dir=<HOME>/ai/lemonade/models
```

con backup previo de `config.json` (`.bak-<timestamp>`). Validado con una
descarga real de prueba (`unsloth/Qwen3-0.6B-GGUF:UD-IQ1_S`) completada al
100 %, hash verificado. **Lección operativa:** cualquier ruta de
configuración de Lemonade debe ser **absoluta**, nunca usar `~`.

### 16.8 vLLM segfault

**No documentado en fuentes versionadas autorizadas.** Ver §10.1: no
existe evidencia versionada de una ejecución de vLLM en este host.

**HECHO OBSERVADO EN SESIÓN — evidencia cruda no versionada** (ver §10.2
para el detalle completo y la advertencia de revalidación): se intentó
cargar `Qwen3.6-27B-FP16-vLLM` desde Lemonade con vLLM 0.20.1, ROCm 7.12 y
PyTorch 2.10; los pesos se cargaban, pero el backend sufría un segfault
nativo durante la inicialización de la arquitectura híbrida (descartado
OOM y descarga corrupta). Sin timestamps, paths ni stack traces
disponibles para reproducir; los informes crudos están en el workspace
local de sesión, no en este repositorio.

### 16.9 Colas agentic / slots

El diagnóstico de concurrencia (`docs/validacion-lemonade-vulkan.md`,
2026-08-26) documentó dos secuencias lógicas de decode solapadas
(`is_processing=true` en slots 0 y 2 de 4), `requests_processing=2` en
`/metrics`, sin poder demostrar simultaneidad física de GPU. Una espera de 3
minutos con `requests_processing` activo hizo inseguro inyectar un
benchmark controlado (las consultas internas de `/slots`/`/metrics`
agotaron 8 s sin respuesta bajo carga sostenida). Ver §9.2 para la
recomendación resultante.

### 16.10 HTTP keepalive vs KV cache

**HECHO OBSERVADO EN SESIÓN — evidencia cruda no versionada.** Se
investigó la aparente lentitud atribuida a la interacción entre HTTP
keep-alive y la reutilización de KV cache bajo carga agentic. Hallazgos:

- **No había presión de GPU, RAM, PSI ni swap** durante la medición.
- La **reutilización de prefijos KV sí funcionaba**: se observó
  aproximadamente **99% de reutilización** en un prefijo largo de un slot.
- **HTTP keep-alive no controla la permanencia/reutilización de la KV
  cache**: son mecanismos independientes.
- El **cuello principal era la cola**: 7 peticiones/agentes sobre 4 slots
  implicaban 4 activas y 3 en espera.
- **Recomendación (de la sesión):** limitar a **3 workers** y reservar
  **1 slot interactivo**; **no** aumentar a 7 slots ni usar contexto
  global `458752` sin medir.

Este resumen historico anonimizado no incluye registros independientes de
reproduccion. **Debe revalidarse** antes de tratarse como procedimiento
reproducible (ver criterio equivalente en §10.2 para vLLM); no requiere
acceso a archivos privados para consultar sus conclusiones.

### 16.11 CRLF / permisos / ownership en workspaces

- **Gate CRLF (CONFIGURADO Y VALIDADO):** `workspaces/unsloth-studio/tests/test-shell-files.sh`
  falla si detecta **cualquier byte `\r`** en cualquier `.sh` del workspace,
  además de ejecutar `bash -n` sobre cada script. Este gate forma parte de
  la validación local estándar (§14.6).
- **Ownership (CONFIGURADO Y VALIDADO por test):** `tests/test-ownership.sh`
  simula `sudo` (`SUDO_UID`/`SUDO_GID`) y confirma que `common.sh` ejecuta
  `chown -R <uid>:<gid>` sobre los bind mounts de datos antes de arrancar,
  y que `compose.yaml` fija `user: "${HOST_UID:-10001}:${HOST_GID:-10001}"`
  y añade el GID de render vía `group_add`. El test también confirma la
  ausencia de `chmod 777` en el repositorio.
- **Permisos de dispositivos GPU:** ambos workspaces validan que
  `/dev/kfd` y el nodo render configurado sean dispositivos de carácter
  legibles/escribibles por la cuenta que ejecuta `start.sh` antes de
  arrancar Compose (`prepare_start_environment` en
  `workspaces/llama-factory/scripts/common.sh`).

---

## 17. Operación diaria

### 17.1 Lemonade

**Usar `-BaseUrl` y `-Model`, ambos obligatorios y sin defaults desde
2026-09-07**, al invocar `scripts/test-lemonade.ps1`. Confirmar el ID
residente exacto: seleccionar otro modelo puede desalojar por LRU a Coder
o Thinking con `max_loaded_models=2` (ver §7.5).

```text
# Estado
systemctl --user status lemond.service
loginctl show-user -p Linger

# Logs
journalctl --user -u lemond.service -f

# Health
curl -sS http://<HALO_HOST>:13305/api/v1/health

# Catálogo de modelos
curl -sS http://<HALO_HOST>:13305/v1/models

# Smoke LAN completo desde una terminal PowerShell en Windows:
powershell -File scripts/test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

### 17.2 Cargar/descargar modelos

Ver §8.4 (`/api/v1/load`, `/api/v1/unload`). Verificar siempre el
`model_name` exacto en `/v1/models` antes de operar (§16.5).

### 17.3 Comprobar memoria (GTT/VRAM)

No hay un comando único citado en las fuentes para leer GTT/VRAM en
caliente fuera de las herramientas AMDGPU estándar ya usadas en las
validaciones (`mem_info_gtt_total`, `mem_info_gtt_used`,
`mem_info_vram_total`, `mem_info_vram_used`, expuestos por sysfs/AMDGPU
según `docs/comparativa-qwen38-halo-strix.md` §2). Complementar con
`/api/v1/health` de Lemonade para el estado lógico de modelos cargados.

### 17.4 LlamaBoard y Unsloth Studio

```bash
# LlamaBoard
cd workspaces/llama-factory
./status.sh
./logs.sh

# Unsloth Studio
cd workspaces/unsloth-studio
./status.sh
./logs.sh
```

### 17.5 Recuperación rápida (resumen)

| Síntoma | Acción |
| --- | --- |
| Lemonade no responde en LAN | `systemctl --user start lemond.service`; si el bind volvió a loopback, reaplicar `host=<HALO_HOST>` (§7.3) |
| `Linger` volvió a `no` tras actualización | Rehabilitar linger a nivel de sistema y reconfirmar con `loginctl show-user -p Linger` |
| 403 CORS en la Web App LAN | Confirmar `~/.config/lemonade/conf.d/allowed-origins.conf` con el origen LAN exacto; `systemctl --user restart lemond.service` |
| LlamaBoard/Unsloth Studio `unhealthy` | `./logs.sh`; revisar puerto ocupado y espacio en disco (`df -h`); el primer build puede tardar |
| GPU no detectada en contenedor | Verificar `/dev/kfd`/render node, permisos y `DEVICE_GID`; no usar `privileged` |

---

## 18. Rollback y limpieza segura

### 18.1 Lemonade

```text
# Volver la Web App/API a loopback (documentado en docs/validacion-lemonade-vulkan.md)
lemonade config set host=127.0.0.1
systemctl --user restart lemond.service
sudo ufw delete allow in on wlan0 from <LAN_CIDR> to <HALO_HOST> port 13305 proto tcp

# Revertir la autorización CORS LAN
rm ~/.config/lemonade/conf.d/allowed-origins.conf
systemctl --user restart lemond.service
```

Volver al par de producción tras cualquier experimento (§10 de
`docs/comparativa-qwen38-halo-strix.md`):

1. Confirmar `max_loaded_models=2` (`GET /internal/config`).
2. Recargar Coder y Thinking con los argumentos exactos de §8.2,
   `save_options:true`.
3. Verificar `GET /api/v1/health`: ambos `backend_health:"ready"`,
   `device:"gpu"`.
4. Descargar cualquier modelo experimental con `/api/v1/unload` (nunca
   `/api/v1/delete` salvo intención explícita de liberar disco).

### 18.2 UMA de BIOS

Volver físicamente `iGPU Configuration` a `Auto` y reiniciar (no
recomendado mientras la configuración actual siga pasando los gates; ver
§4).

### 18.3 Paquetes del sistema

Fallback verificado en `halostrix-baseline-20260825/` bajo el `HOME`
remoto: `packages-explicit.txt`, `packages.txt`, `etc.tar.zst` + SHA-256, más
listas `packages-post-*.txt` (incluye `packages-rocm-pre/post.txt`).
Restauración conceptual (no ejecutada): verificar SHA-256, restaurar
selectivamente desde consola de recuperación con `tar --zstd -xpf`, tras
salvaguardar la configuración vigente. Rollback documentado, no ejecutado,
de ROCm: revisar dependencias/huérfanos y sólo entonces
`pacman -Rns rocm-hip-runtime`.

### 18.4 LLaMA-Factory / Unsloth Studio

```text
# Inventario antes de borrar (ambos workspaces)
./cleanup.sh --dry-run

# Rollback de imagen sin reconstruir (LlamaBoard)
RUN_IMAGE=sha256:<id-conservado> ./start.sh

# Selección de imagen previa (Unsloth Studio)
RUN_IMAGE=previous ./start.sh
```

**Nunca** usar `rm -rf data`, `docker compose down -v`, ni
`docker system prune` sin copia y autorización explícita en ninguno de los
dos workspaces (instrucción explícita de ambos README).

### 18.5 Entrenamiento en contenedor (ROCm)

Rollback documentado, no ejecutado (`docs/validacion-entrenamiento-rocm.md`):
`sudo systemctl disable --now docker.service`, revisar dependencias/huérfanos
y considerar `sudo pacman -Rns docker`; preservar `/var/lib/docker` salvo
autorización explícita para eliminar datos.

---

## 19. Matriz de estado

| Área | Realizado/validado | Configurado, no validado end-to-end | Pendiente/bloqueado |
| --- | --- | --- | --- |
| UMA BIOS → RAM/GTT | ✅ Cambio ejecutado, verificado tras reinicio y tras traslado físico (§4) | | |
| Vulkan baseline | ✅ Build, offload 29/29 capas, benchmark 3 réplicas (§5.1) | | Soak térmico prolongado |
| HIP/ROCm inferencia | ✅ Build, offload, benchmark comparativo (§5.2) | | No promovido (regresión TG) |
| ROCm entrenamiento (contenedor) | ✅ Smoke FP16/BF16 backward finito (§12.2) | | Entrenamiento real (LoRA/QLoRA) |
| Lemonade LAN + firewall + CORS | ✅ Bind LAN, regla UFW, CORS, chat SSE 200 (§7.3) | | |
| Lemonade `Linger=yes` | ✅ Reconfirmado 2026-09-04 (§7.2) | | |
| `max_loaded_models=2` | ✅ Aplicado y persistido, GTT medido con ambos modelos (§8.3, §9.1) | | |
| Coder + Thinking como baseline | ✅ Parámetros exactos, GTT medido (§8.2, §9.1) | | |
| Concurrencia N=1/N=2/N=4 | | Recomendación provisional (2 agentes) | Medición controlada N=1/2/4 pendiente (§9.2) |
| LlamaBoard — UI/servicio | | ✅ Scripts, healthcheck, persistencia (§13) | Entrenamiento real vía LlamaBoard |
| Unsloth Studio — UI/GPU | ✅ Build, imports, GPU detectada, healthcheck (§14.1) | | QLoRA/bitsandbytes; LoRA BF16 real |
| Reverse proxy TLS | | | No existe ningún proxy TLS; HTTP plano en todos los servicios (§15) |
| Qwen3.8-27B | ✅ Descarga íntegra, hash verificado | | Carga contradictoria entre fuentes; POC de este informe no ejecutada (§11.1) |
| Qwen3.8-Flash-Next | ✅ Descarga íntegra, hash verificado; fallo de carga reproducido | | Bloqueado por arquitectura `qwen4exp` (§11.2) |
| vLLM | | 🟡 Investigado/diagnosticado en sesión (segfault con `Qwen3.6-27B-FP16-vLLM`), evidencia cruda no versionada (§10.2, §16.8) | Consolidar en documento versionado y revalidar antes de usar como procedimiento (§10.4) |

---

## 20. Próximos pasos priorizados

1. **HTTPS/TLS:** decidir y validar un mecanismo de cifrado en tránsito
   (túnel SSH puntual o reverse proxy TLS dedicado) antes de cualquier
   acceso fuera de la LAN confiada actual (§15.2).
2. **Medición controlada de concurrencia** N=1/N=2/N=4 en una ventana sin
   `requests_processing` activo, para confirmar o descartar el beneficio de
   más de 2 agentes concurrentes (§9.2).
3. **POC aislada de Qwen3.8-27B** como candidato a sustituir Thinking-2507,
   siguiendo el procedimiento de 6 casos de prueba de
   `docs/comparativa-qwen38-halo-strix.md` §6, sin tocar Coder mientras
   dure.
4. **Investigar la restricción Snapper/Btrfs** (`Operation not permitted`)
   detectada en la auditoría inicial, para habilitar snapshots como
   mecanismo adicional de rollback (§3.3).
5. **Ejecutar un POC real de entrenamiento** (LoRA BF16 en LLaMA-Factory, o
   evaluar bitsandbytes/QLoRA en Unsloth Studio) para cerrar el gap "UI
   validada, entrenamiento no validado" en ambos workspaces (§13.4, §14.7).
6. **Consolidar la investigación de vLLM realizada en sesión** (§10.2,
   §16.8: segfault con `Qwen3.6-27B-FP16-vLLM` en vLLM 0.20.1/ROCm
   7.12/PyTorch 2.10) en un documento de validación versionado
   (`docs/validacion-vllm-*.md`), revalidando el diagnóstico antes de
   tratarlo como procedimiento reproducible, y evaluar el bundle
   prerelease identificado para `gfx1151` sin sustituir el servicio
   estable actual. Extender igual criterio a cualquier evaluación futura
   de Qwen3.8-Flash-Next (tras build con PR #27941) (§10.4, §11.2).
7. **Soak térmico prolongado** de Vulkan/Lemonade bajo carga sostenida (el
   gate actual es corto/provisional, §5.1).

---

## 21. Índice de documentos y artefactos del repo

### Documentos fuente (`docs/`)

| Documento | Contenido principal |
| --- | --- |
| [`auditoria-ssh-inicial.md`](auditoria-ssh-inicial.md) | Inventario Fase 0, UMA, herramientas de plataforma, chequeo post-traslado |
| [`plan-configuracion-halo-strix.md`](plan-configuracion-halo-strix.md) | Plan de research original, arquitectura objetivo, matriz de gates y fases |
| [`validacion-llamacpp-vulkan.md`](validacion-llamacpp-vulkan.md) | Build, offload y benchmark Vulkan de llama.cpp |
| [`validacion-llamacpp-hip.md`](validacion-llamacpp-hip.md) | Build, offload y benchmark HIP/ROCm de llama.cpp; decisión de no promoción |
| [`validacion-lemonade-vulkan.md`](validacion-lemonade-vulkan.md) | Historial completo de Lemonade: gates, incidentes, LAN, CORS, UI, concurrencia |
| [`validacion-entrenamiento-rocm.md`](validacion-entrenamiento-rocm.md) | Docker Engine + smoke PyTorch ROCm en contenedor |
| [`comparativa-qwen38-halo-strix.md`](comparativa-qwen38-halo-strix.md) | Consolidación Coder/Thinking/Qwen3.8-27B/Flash-Next, `max_loaded_models`, reasoning-format |
| `setup-completo-halo-strix.md` (este documento) | Consolidación maestra y runbook |

### Workspaces (`workspaces/`)

| Ruta | Contenido |
| --- | --- |
| `workspaces/llama-factory/` | README, `compose.yaml`, `Dockerfile`, `.env.example`, `build.sh`, `start.sh`, `stop.sh`, `status.sh`, `logs.sh`, `cleanup.sh`, `scripts/common.sh`, `tests/test-cleanup.sh`, `examples/poc-lora-bf16.yaml` |
| `workspaces/unsloth-studio/` | README, `compose.yaml`, `Dockerfile`, `.env.example`, `build.sh`, `start.sh`, `stop.sh`, `status.sh`, `logs.sh`, `cleanup.sh`, `scripts/common.sh`, `scripts/container-entrypoint.sh`, `scripts/verify_stack.py`, `tests/test-build-start.sh`, `tests/test-cleanup.sh`, `tests/test-ownership.sh`, `tests/test-shell-files.sh` |

### Scripts y tareas de operador

| Ruta | Uso |
| --- | --- |
| `scripts/test-lemonade.ps1` | Smoke LAN reproducible de Lemonade (`/v1/models` + `/chat/completions`) |

Los registros internos de coordinacion no forman parte de la publicacion;
las conclusiones necesarias para operar se conservan en estos documentos.
