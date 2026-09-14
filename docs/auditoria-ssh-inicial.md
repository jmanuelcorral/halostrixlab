# Auditoría SSH inicial — Fase 0

> **English:** [operational guide](en/setup-guide.md#preflight-and-backup) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

**Fecha:** 2026-08-25  
**Estado:** inventario Fase 0, verificación UMA y herramientas de plataforma completados; ROCm, Lemonade, llama.cpp e inferencia/entrenamiento permanecen fuera de alcance.  
**Alcance:** se creó el fallback de rollback autorizado y se instaló exclusivamente el conjunto aprobado de herramientas de diagnóstico. No hubo reinicio ni cambios de BIOS, firewall, listeners, servicios, kernel, mounts o configuración manual. Los identificadores, credenciales, direcciones, MAC, seriales, UUID, rutas privadas, SSID y puertos están redactados.

## Preflight y sesión SSH

| Comprobación | Resultado | Evidencia redactada |
|---|---|---|
| Variables de conexión | **PASS** | Host, usuario y password no vacíos; puerto entero válido. |
| Resolución DNS/IP | **PASS** | Un único intento completado. |
| TCP al puerto configurado | **PASS** | Apertura dentro de 10 s. |
| Banner SSH sin autenticación | **PASS** | Banner SSH válido recibido dentro de 5 s. |
| TOFU de laboratorio | **PASS** | Se autorizó exclusivamente para el archivo `<VERIFIED_KNOWN_HOSTS_FILE>` del estado de sesión; no se tocó el `known_hosts` global. |
| Huella pública | **REGISTRADA** | `<SSH_HOST_KEY_FINGERPRINT>` (sin asociación a host, IP ni usuario). |
| Autenticación Paramiko | **PASS** | Un único intento, timeout de 15 s, sin exponer password. |

Paramiko 5.0.0 se instaló solo en un entorno aislado de herramientas mediante `pip --target`; Python global y el repositorio no se modificaron.

## Inventario confirmado

| Área | Evidencia observada | Gate |
|---|---|---|
| Equipo, firmware y CPU | Plataforma **GMKtec EVO-X2**; BIOS `EVO-X2S 1.13`, 2026-06-26. CPU confirmada: **AMD Ryzen AI Max+ 395 con Radeon 8060S**; 32 CPU lógicas. | **PASS** |
| CachyOS y kernel | CachyOS; kernel `7.2.0-1-cachyos`. `amd-ucode` y `linux-firmware`/`linux-firmware-amdgpu`: `20260810-2`. | **PASS** |
| GPU y target | Controlador AMD Strix Halo/Radeon integrado detectado. KFD expone un nodo GPU con `gfx_target_version=110501`, consistente con GFX 11.5.1 / `gfx1151`; el nodo no-GPU expone cero. | **PASS** para gate Strix Halo/`gfx1151`; `rocminfo` no está disponible para una segunda confirmación. |
| KFD y CWSR | KFD disponible; nodo GPU con `cwsr_size=19185664` y `ctl_stack_size=16384`. | **PASS** |
| GTT/TTM | `pages_limit=8182406`, aproximadamente 31.2 GiB con página de 4 KiB; el driver anuncia ~31.2 GiB de GTT. | **PASS** como baseline bajo la configuración actual de UMA Auto; no elevarlo antes del gate de firmware. |
| RAM, swap y zram | Dato humano confirmado: BIOS iGPU/UMA está en **Auto**. El SO informa ~62 GiB utilizables; swap y zram están presentes. El patrón de 128 GiB DMI, ~62 GiB visibles, VRAM/BAR de 64 GiB y GTT ~31.2 GiB es consistente con un carve-out UMA de firmware. | **PENDING**: el requisito de 128 GiB utilizables no queda verificado hasta la prueba reversible de firmware. Fase 0 no certifica salud de RAM. |
| Almacenamiento y filesystem | Un SSD de ~1.8 TiB; raíz Btrfs. SMART aprobado y temperatura puntual de 32 °C. | **PASS** de salud SMART puntual; `nvme` no está disponible, por lo que su log queda **PENDING/no instalada**. |
| Mesa/RADV | Mesa y `vulkan-radeon` `3:26.2.1-1`. | **PASS** de paquetes instalados. |
| ROCm y herramientas | `vulkaninfo` ya está disponible y valida RADV/Mesa sobre Radeon 8060S/Strix Halo. `rocminfo`, `rocm-smi` y `amd-smi` siguen ausentes; no se trata como fallo de hardware. No se instalaron paquetes ROCm, Lemonade ni llama.cpp. | **PASS** para Vulkan; **PENDING** para ROCm/HIP. |
| Energía y térmica | `amd_pstate=active`; `sensors` está disponible y publica sensor GPU edge. No se observó sensor hotspot/junction ni indicador de throttling en esta lectura. No se midió potencia AC. | **PENDING** para gate térmico de carga. |
| Listeners y firewall | Se observaron 6 listeners TCP wildcard/no específicos y ninguno de loopback en el resumen; puertos y procesos se han redactado. No se ejecutó `nft list ruleset`. | **FAIL** respecto al objetivo de APIs solo loopback; requiere atribución de servicios antes de cambiar nada. Firewall **PENDING**. |

## Ejecución `sudo -S` de solo lectura

`dmidecode` y `smartctl` se completaron una vez y sin eco. El comando `nvme smart-log` falló porque la herramienta `nvme` no está instalada/disponible; conforme al límite de una ejecución y parada ante fallo, **no se ejecutó** `nft list ruleset`. Esto es un bloqueador de herramienta, no un diagnóstico de fallo de hardware o firewall.

## Diagnóstico de discrepancia de memoria

**Segunda auditoría targeted, solo lectura:** reutilizó el `known_hosts` TOFU exclusivo de sesión y realizó una única autenticación Paramiko. La huella observada coincide con la ya registrada: `<SSH_HOST_KEY_FINGERPRINT>`. No se modificaron ficheros, firmware, BIOS ni configuración remota.

### Evidencia

| Fuente | Hallazgo redactado |
|---|---|
| CPU | `lscpu -J` y `/proc/cpuinfo` confirman **AMD Ryzen AI Max+ 395 con Radeon 8060S**. |
| Kernel | `MemTotal=65459248 kB` (~62.4 GiB), `MemAvailable=62856328 kB` (~59.9 GiB) y swap ~62.4 GiB. |
| Arranque | Kernel: `65233232K/66739012K` disponibles; solo `1480072K` reservados y `0K` CMA reservados. No se observó `mem=`, `memmap=`, `amdgpu.*`, `ttm.*` ni override IOMMU relevante en la línea de arranque. |
| Mapa firmware/ACPI | `/proc/iomem` enumera ~63.64 GiB de `System RAM` en nueve segmentos, no un mapa de ~128 GiB con 64 GiB ocultos. Las direcciones se mantienen exclusivamente en el raw de sesión. |
| DMI | Type 16 declara **Maximum Capacity: 64 GiB**, mientras Type 17 publica ocho entradas de 16 GiB. Es una SMBIOS internamente inconsistente; no permite por sí sola decidir entre RAM física ausente y memoria retirada antes de que el kernel reciba e820/ACPI. |
| AMDGPU | Driver: `VRAM: 65536M`, `BAR: 65536M` y GTT ~31962M. En una APU UMA estos valores describen el espacio que el driver mapea/gestiona; no prueban que exista un segundo banco físico de 64 GiB aparte del RAM que ya ve el kernel. |
| Debug/PCI | Las consultas `amdgpu_*_mm` de debugfs y el detalle PCI extendido no estuvieron disponibles en esta sesión; no se montó debugfs ni se modificó nada. |

### Conclusión con niveles de certeza

- **~95 % de confianza — hipótesis principal revisada:** con iGPU/UMA en **Auto**, el firmware está aplicando un carve-out de ~64 GiB antes del arranque. Eso explica conjuntamente DMI que suma 128 GiB, `MemTotal` ~62 GiB, `System RAM` ~63.64 GiB, VRAM/BAR AMDGPU de 64 GiB y GTT/TTM ~31.2 GiB. Un carve-out pre-boot no se presenta como reserva ordinaria del kernel ni como CMA: por eso los ~1.4 GiB reservados y `0K` CMA no contradicen la hipótesis.
- **La VRAM/GTT no contradicen UMA:** AMD documenta que los nombres VRAM, carve-out, GART, GPU memory dedicado y memoria reservada por firmware se usan para la memoria físicamente compartida. GTT es una ventana dinámica, recuperable por el SO, y su límite por defecto es aproximadamente el 50 % de la RAM visible; ~31.2 GiB es exactamente consistente con los ~62 GiB que hoy ve Linux.
- **Contrapeso residual:** DMI Type 16 con máximo de 64 GiB sigue siendo una señal contradictoria, pero la propia SMBIOS también enumera ocho módulos de 16 GiB. Con el dato humano de UMA Auto y el patrón 64+64 del equipo, no se debe tratar Type 16 como prueba concluyente de que solo haya 64 GiB físicos.
- **Descartado como causa primaria:** no hay parámetro `mem=`/`memmap=` ni evidencia de que el kernel haya retirado 64 GiB; tampoco GTT (~31.2 GiB) ni CMA (`0K`) justifican una diferencia de 64 GiB.

### Siguiente gate

**Gate reversible de firmware — aún no ejecutado; lo realizará físicamente el usuario:**

1. Fotografiar las pantallas BIOS actuales donde figuren `iGPU Configuration`, `UMA Frame Buffer` y capacidad de memoria.
2. Cambiar **solo** `iGPU Configuration` de `Auto` a `UMA_SPECIFIED`.
3. Fijar `UMA Frame Buffer` al mínimo disponible: preferencia **512 MiB**; si esa opción no existe, usar el mínimo ofrecido, por ejemplo **2 GiB**.
4. Reiniciar y repetir las lecturas de `MemTotal`, VRAM/BAR AMDGPU, GTT/TTM y CMA.

**Resultado esperado:** aproximadamente 125 GiB de `System RAM`/RAM utilizable, con VRAM fija reducida al valor elegido; GTT seguirá siendo dinámico. Si no aparece esa memoria, se reabre la hipótesis de capacidad física/SKU o SMBIOS defectuosa. **Rollback:** volver `iGPU Configuration` a `Auto` y reiniciar. No se recomienda ni se ha ejecutado ningún cambio de BIOS en esta auditoría.

### Fuentes para esta revisión

- **Primaria — GMKtec:** la publicación de EVO-X2 describe la configuración de fábrica como **64 GB RAM + 64 GB VRAM** y documenta la variante de 128 GB: referencia publica del fabricante (enlace omitido)
- **Primaria — AMD ROCm 7.14:** memoria RDNA3.5, carve-out/VRAM de firmware y GTT dinámico: <https://rocm.docs.amd.com/en/latest/reference/system-optimization/rdna3-5.html>
- **Primaria — kernel Linux:** base de la asignación GTT-backed citada por AMD: <https://github.com/torvalds/linux/commit/759e764f7d587283b4e0b01ff930faca64370e59>
- Las fuentes comunitarias pueden orientar experiencias de BIOS, pero se consideran **secundarias** y no fundamentan este diagnóstico ni el gate.

## Verificación posterior al cambio UMA

**Estado: PASS.** El host respondió en el primer probe TCP tras el reinicio esperado; banner SSH, huella de sesión y una única autenticación Paramiko fueron válidos. `uptime` informó menos de un minuto, coherente con el reinicio.

| Comprobación | Valor redondeado | Resultado |
|---|---:|---|
| `MemTotal` | **123.5 GiB** | PASS: dentro del objetivo aproximado de 125 GiB. |
| `MemAvailable` | **121.4 GiB** | PASS: RAM recuperada y disponible para el SO. |
| Swap total | **123.5 GiB** | Registrado; no forma parte del gate UMA. |
| CMA total/libre | **0 GiB / 0 GiB** | Consistente con que el carve-out no sea una reserva CMA del kernel. |
| VRAM AMDGPU | **2 GiB** | **Confirmado por el usuario:** `UMA_SPECIFIED` con el mínimo disponible de 2 GiB; coincide con el valor observado por AMDGPU. |
| TTM/GTT | **61.7 GiB** | PASS: aproximadamente 50 % de la RAM visible, como espera AMD para el límite GTT dinámico. |

La combinación de ~123.5 GiB de RAM visible, VRAM de 2 GiB y TTM/GTT ~61.7 GiB confirma la hipótesis de carve-out Auto previa y demuestra que el host dispone de la capacidad de memoria esperada cuando el frame buffer fijo se reduce. El usuario confirma que seleccionó explícitamente `UMA_SPECIFIED` con 2 GiB; el gate se considera **PASS**. No se obtuvo un atributo sysfs `mem_info_gtt_*`; el límite TTM y el registro AMDGPU son la evidencia disponible.

**Rollback condicionado:** no procede rollback tras este PASS. Si una carga posterior mostrase regresión atribuible al cambio, el usuario podrá volver físicamente `iGPU Configuration` a `Auto` y reiniciar; esa acción no se ha realizado ni se recomienda mientras la configuración actual pase los gates.

## Baseline y herramientas de plataforma

**Estado: PASS.** El fallback de rollback se verificó antes de la transacción. Se revalidó el plan sin modificar el host: `checkupdates` no devolvió actualizaciones, `pacman -Qu` no listó upgrades y `pacman -Sup --needed` resolvió solo `vulkan-tools`, `nvme-cli` y la dependencia ordinaria `libnvme`; no aparecieron kernel, bootloader, conflictos ni intervención manual. El modo de planificación `pacman -Syu --print-format` sin privilegios fue rechazado por Pacman, por lo que no se usó como evidencia de conflicto.

| Comprobación | Resultado |
|---|---|
| Raíz | Btrfs, subvolumen `@`, opciones `noatime`, `compress=zstd:1`, `discard=async` y `space_cache=v2`; ~1.9 TiB libres. |
| Uso Btrfs | `btrfs filesystem usage /`: **PASS**. |
| Snapper | `snapper` y `btrfs-assistant` están instalados, pero `sudo snapper -c root get-config` y `sudo snapper -c root list` devolvieron **Sin permisos**. No se creó snapshot PRE manual durante el gate de rollback. |
| Verificación de subvolumen | **PENDING/restricción de contexto:** `btrfs subvolume show /` devolvió `Could not search B-tree: Operation not permitted`; `sudo btrfs subvolume list /` devolvió `can't perform the search: Operation not permitted`. `sudo id` sí confirmó elevación; no se infiere corrupción ni se modificó el montaje. |
| Herramientas existentes tras transacción | `vulkan-tools` `1.4.357.0-1.1`, `nvme-cli` `2.16-2`, `libnvme` `1.16.2-2.1` y `lm_sensors` `1:3.6.2-1.1` (ya presente). Mesa y `vulkan-radeon` permanecen `3:26.2.1-1`; kernel `7.2.0-1-cachyos`, `linux-firmware` y `amd-ucode` permanecen `20260810-2`. |
| Transacción autorizada | `sudo pacman -Syu --needed --noconfirm vulkan-tools nvme-cli lm_sensors`: **exit 0**. Instaló solo `vulkan-tools`, `nvme-cli` y `libnvme`; `lm_sensors` ya estaba actualizado. No hubo actualización de kernel/bootloader ni conflicto. |
| Fallback de rollback | **PASS:** bajo HOME del usuario se creó `halostrix-baseline-20260825/` (modo 700) con `packages-explicit.txt`, `packages.txt`, `etc.tar.zst` y su SHA-256. El archivo `/etc` fue creado mediante `sudo tar --zstd`, transferido a propiedad del usuario, protegido modo 600 y validado con `tar -tf`. |
| Lista posterior de paquetes | **PASS:** se añadió `packages-post-ai-tools.txt` y su SHA-256 al mismo fallback, sin sobrescribir las listas PRE. |

El error Btrfs/Snapper puede indicar una restricción de capacidades o política del contexto aunque `sudo` esté disponible; no se diagnostica como corrupción sin una investigación posterior aprobada. El primer intento de fallback no llegó a ejecutar `tar` porque el shell remoto era Fish y rechazó sintaxis POSIX; se detuvo, se corrigió usando `/bin/sh`, y el fallback posterior quedó verificado. No se creó ningún snapshot manual. La transacción activó automáticamente hooks de Pacman/Snapper que informaron un PRE `root: 9` y POST `root: 10`; no se intentó crear ni cerrar snapshots manualmente y no se ha vuelto a enumerarlos, pues la sesión previa no tenía permiso para hacerlo.

**Restauración conceptual (no ejecutada):** desde una ventana de mantenimiento, verificar primero el SHA-256 y contenido de `etc.tar.zst`; restaurar selectivamente o mediante `tar --zstd -xpf` desde una consola de recuperación, tras guardar la configuración vigente. Las listas de paquetes sirven para reconstrucción revisada, no para una reinstalación automática. Para retirar el baseline cuando deje de ser necesario: borrar el directorio `halostrix-baseline-20260825/` bajo HOME del usuario. El fallback es el mecanismo de rollback verificado; el PRE/POST que informó el hook de Pacman no ha podido validarse ni administrarse manualmente desde esta sesión.

### Validación posterior

| Área | Resultado redactado | Gate |
|---|---|---|
| Vulkan | `vulkaninfo --summary` terminó con **exit 0**: GPU integrada **AMD Radeon 8060S Graphics (RADV STRIX_HALO)**, driver **Mesa RADV 26.2.1**, API de dispositivo **1.4.354** e instancia **1.4.357**. El aviso de falta de `DISPLAY` solo omitió información de superficies en esta sesión SSH sin escritorio; no es error del driver. | **PASS** |
| Sensores | `sensors` terminó con **exit 0** y expuso categorías de red cableada, GPU, ACPI, red inalámbrica, CPU y NVMe. Lectura puntual: GPU edge ~31 °C, GPU PPT ~20.9 W, CPU ~36.6 °C y NVMe composite ~32.9 °C. No se expuso hotspot/junction. Un sensor secundario NVMe informó ~77.8 °C con umbrales incoherentes; queda para atribución y repetición bajo carga, sin usarlo como umbral térmico universal. | **PASS** de disponibilidad; **PENDING** gate térmico bajo carga. |
| SMART NVMe | Controlador NVMe detectado a partir de `lsblk` y consultado con `nvme smart-log`: `critical_warning=0`, `media_errors=0`, `num_err_log_entries=0`, `percentage_used=0%`, spare disponible `100%` (umbral `10%`) y temperatura SMART 33 °C. Serial y modelo se mantienen fuera del informe y del raw. | **PASS** |
| Journal de prioridad 3 | Tras la transacción aparecen cuatro mensajes: TDX no soportado, dos avisos de multicast de Wi-Fi y un reset SSH preautenticación. No hay AER, OOM, reset AMDGPU ni error de kernel atribuible a la instalación. No existía en los raws previos una captura equivalente de journal para una comparación temporal estricta; por tanto no se atribuyen esos mensajes a Pacman. | **PASS** para ausencia de errores nuevos relevantes observables; seguimiento no causal de los avisos existentes. |
| Espacio y reinicio | Raíz Btrfs: ~1.9 TiB libres, 1 % utilizado tras la transacción. No se actualizó kernel ni bootloader; **reinicio pendiente: no**. | **PASS** |

**Gate de herramientas de plataforma: PASS.** La transacción finalizó correctamente, Vulkan reconoce la GPU mediante RADV/Mesa, SMART no reporta aviso crítico ni errores de medio, hay sensores utilizables y no se observan errores relevantes nuevos de kernel. El fallback PRE y su lista POST con hash permiten revisar o reconstruir la modificación. Esto no habilita todavía ROCm/HIP, Lemonade, llama.cpp, cambios TTM/GTT ni cargas de IA.

## Candidatos ROCm/HIP — auditoría de repositorios

**Estado: PENDING/no instalar aún.** La repetición robusta ejecutó cada
consulta Pacman como un comando remoto independiente y completó las lecturas
sin descargar ni modificar el host.

| Área | Evidencia verificable | Evaluación |
|---|---|---|
| ROCm ya instalado | No hay ROCm/HIP/HSA/PyTorch ROCm instalados; solo LLVM 22.1.8 y OpenCL Mesa 26.2.1 de la plataforma gráfica. | Runtime ROCm **ausente**, no fallo de hardware. |
| Candidato coherente | `rocm-hip-runtime`, `hip-runtime-amd`, `rocm-core`, `rocm-llvm`, `rocm-device-libs`, `hsa-rocr` y `rocminfo` existen. `pacman -Sp rocm-hip-runtime` resuelve componentes ROCm **7.2.4**. Los repositorios CachyOS/extra difieren, pero los componentes resueltos tienen la misma serie; no apareció 7.14. | Pila candidata **coherente 7.2.4**; no mezclar manualmente otras series. |
| Dependencias/tamaño | El metapaquete añade runtime de lenguaje, HIP, HSA, rocminfo, LLVM, comgr y CMake. `rocm-llvm` domina: descarga ~1.40 GiB e instalación ~7.19 GiB; HIP instala ~32.8 MiB. | Total exacto **PENDING**: `-Sp` confirmó URLs, no tamaños por artefacto. |
| Nodos/permisos | `/dev/kfd` y render son `root:render`, `crw-rw-rw-`; el usuario no pertenece a `render`, pero el modo actual permite acceso. | **PASS** de acceso actual; revisar al endurecer permisos. |
| Plataforma/contenedores | Kernel `7.2.0-1`, firmware `20260810-2`, Mesa/RADV `26.2.1`, ~1.9 TiB libres. Docker, Podman y Distrobox no están instalados (exit 127). | Evaluación nativa posible; sin contenedor disponible. |

La metadata Pacman no enumera ISA. Las fuentes AMD ya documentadas sitúan
Strix Halo/RDNA 3.5 en `gfx1151`, pero esta auditoría no prueba que HSA/LLVM
7.2.4 lo cargue. El gate final es `rocminfo`/HIP post-instalación con una sola
pila aprobada; esa comprobación se realizó en la instalación controlada que
sigue.

## Candidato Lemonade

**Estado: PENDING/no instalar.** `lemonade-server` está disponible en
`cachyos-extra-znver4` como **11.7.0-2.1** (4.85 MiB descarga, 14.78 MiB
instalado), Apache-2.0. Su plan resuelve `libev`, `libwebsockets`, `mbedtls` y
el servidor; no declara conflictos. Las dependencias opcionales son
`fastflowlm` y `llama-cpp`, ninguna seleccionada.

El paquete no está instalado: `pacman -Ql` y `pacman -Fl` no dieron listado de
archivos disponible, los binarios `lemonade`/`lemonade-server` no están en
PATH y no aparecen unidades systemd de sistema o usuario. Por ello no hay
puertos por defecto ni documentación/configuración instalada que atribuir.
Los listeners existentes permanecen sin cambios y no se inició servicio.

No había upgrades pendientes; hay ~1.8 TiB libres. Antes de una instalación
futura habrá que revisar los archivos que entregue el paquete, su configuración
de bind/autenticación y los nuevos listeners, sin asumir puertos por defecto.

### Instalación y validación ROCm 7.2.4

**Gate: PASS.** Tras confirmar que no había upgrades pendientes, se guardó
`packages-rocm-pre.txt` con SHA-256 en el fallback y se ejecutó únicamente
`pacman -S --needed --noconfirm rocm-hip-runtime`. La transacción resolvió 20
paquetes ROCm 7.2.4/7.2.4-1.1/2:7.2.4-2.1 coherentes, sin kernel, Mesa, DKMS
ni AMDGPU-Pro; descargó **1487.61 MiB** e instaló **7581.89 MiB**. No requiere
reinicio. Los hooks de Pacman informaron snapshots Snapper PRE/POST
automáticos; no se administraron manualmente.

`hipcc`, `hipconfig -R/-l` y `rocminfo` finalizaron correctamente. HIP informa
7.2.53211 y `rocminfo` enumera por separado agentes CPU y un agente GPU
**`gfx1151`** (`amdgcn-amd-amdhsa--gfx1151`), confirmando el target local sin
override HSA. No se observaron `HSA_OVERRIDE_GFX_VERSION` ni
`LD_LIBRARY_PATH` que mezclasen pilas; `/opt/rocm` es la ruta coherente
reportada por HIP. `ldd rocminfo` resolvió bibliotecas del sistema/ROCm sin
dependencias faltantes, los nodos KFD/render siguieron accesibles y el journal
filtrado no mostró AMDGPU/KFD/OOM/reset.

Se añadió `packages-rocm-post.txt` con SHA-256 al fallback. **Rollback
documentado, no ejecutado:** revisar primero dependencias y huérfanos y solo
entonces considerar `pacman -Rns rocm-hip-runtime`; no borrar snapshots ni
hacer rollback automático.

### Lemonade — instalación de paquete y contenido

**Gate paquete: PASS; servicio: PENDING/no iniciado.** Se instaló únicamente
`lemonade-server 11.7.0` tras plan limpio y baseline pre; no se descargaron
backends, no se ejecutó `config set` ni se inició servicio. Pacman informó
snapshots Snapper PRE/POST automáticos y se guardó lista post con hash.

El paquete aporta `lemonade`, `lemond`, unidades systemd de sistema y usuario,
y defaults bajo `/usr/share/lemonade(-server)/resources`. Ambas unidades están
**disabled/inactive**. `lemond --help` expone host/puerto como overrides de
`config.json`; los defaults usan backend `auto` y fuente Hugging Face. No se
asume bind ni se permiten descargas. No apareció proceso `lemond` ni listener
nuevo. Antes de habilitarlo se deben definir explícitamente backend, bind,
autenticación y modelo bajo un gate de servicio separado.

## Gates y divergencias con el plan

| Gate | Estado | Motivo |
|---|---|---|
| A — Conectividad y SSH | **PASS** | Preflight, TOFU de sesión, huella registrada y una autenticación completada. |
| B — SKU/target/KFD/CWSR | **PASS** | Strix Halo, KFD, CWSR y valor de target local compatibles con `gfx1151`. |
| B — Memoria utilizable | **PASS** | `UMA_SPECIFIED` con 2 GiB, confirmado por el usuario, recuperó ~123.5 GiB de RAM visible; TTM/GTT ~61.7 GiB. |
| Baseline/rollback y herramientas | **PASS (fallback)** | Fallback PRE de paquetes y `/etc`, lista POST con hash, transacción controlada y validación de Vulkan/NVMe/sensores completadas. Snapper/Btrfs sigue pendiente de investigación. |
| B — Runtimes ROCm/Vulkan | **PASS (Vulkan); PENDING (ROCm/HIP)** | Vulkan RADV/Mesa valida Radeon 8060S/Strix Halo. No se instalaron ni validaron runtimes ROCm/HIP. |
| C — Térmica | **PENDING** | Solo lectura puntual de sensores; faltan carga, clocks, throttling y potencia AC. |
| D — Inferencia | **PENDING** | No se ejecutaron benchmarks ni prompt set congelado. |
| E — Servicio | **FAIL** | Hay listeners wildcard/no específicos; faltan atribución, revisión de firewall y comprobación de bind loopback. |
| F — Entrenamiento | **PENDING** | No se ejecutaron cargas, checkpoints, resume ni evaluaciones. |

### Blockers prioritarios

1. **Cerrado — gate UMA:** `UMA_SPECIFIED` con frame buffer de 2 GiB, confirmado por el usuario, recuperó la RAM esperada. Conservar las fotos BIOS y no volver a `Auto` salvo rollback deliberado.
2. Investigar la restricción Snapper/Btrfs antes de depender de snapshots; el fallback verificado satisface el rollback de la fase de herramientas.
3. Atribuir los seis listeners wildcard/no específicos y validar reglas de firewall cuando esté disponible `nft`; no modificar servicios durante esta Fase 0.
4. Antes de decidir HIP, modificar TTM/GTT o instalar runtimes, seleccionar una pila ROCm coherente y verificar sus matrices de compatibilidad.
5. Memtest86+ de cuatro pasadas y prueba Linux limitada siguen siendo gates posteriores; este inventario SSH no certifica RAM.

## Artefactos y garantías

- Evidencia publica: resultados anonimizados en este documento; los registros
  privados de ejecucion no se distribuyen ni son una dependencia de lectura.
- Known hosts TOFU: archivo privado aislado, sin modificar el archivo global.
- Las modificaciones remotas autorizadas fueron el baseline de rollback bajo HOME del usuario, su lista POST con hash y la instalación de `vulkan-tools`, `nvme-cli` y la dependencia `libnvme`; Pacman también informó snapshots PRE/POST automáticos de sus hooks. No se modificaron manualmente snapshots, servicios, firewall, BIOS, kernel, almacenamiento de sistema ni archivos de configuración.
- No se ejecutaron Git ni reinicios.

## Chequeo post-traslado y arranque físico — 2026-08-26

**Veredicto: APROBADO CON AVISOS.**

**Ventana verificada:** apagado confirmado a las 13:33:48 CEST; SSH LAN
disponible a las 13:38:07 CEST. Se usó exclusivamente el host esperado
`<HALO_HOST>`, con validación estricta del `known_hosts` de sesión. No se
aplicaron cambios de configuración, firewall, paquetes, BIOS, ROCm ni
servicios: `lemond.service` ya estaba habilitado y activo, por lo que no hizo
falta recuperación.

| Área | Estado | Evidencia post-arranque |
|---|---|---|
| Identidad y boot limpio | **PASS** | GMKtec EVO-X2 / Ryzen AI Max+ 395; CachyOS `7.2.0-1-cachyos`; nuevo boot ID, inicio `13:37:50` y uptime de ~1 minuto durante la primera captura. `systemctl --failed` de sistema y usuario no devolvió unidades fallidas. |
| Hora y red | **PASS con aviso mDNS** | `Europe/Madrid`; NTP habilitado y sincronizado en la relectura tras estabilizar el arranque. `wlan0` obtuvo `<HALO_HOST>` en `<LAN_CIDR>`, ruta por `<LAN_GATEWAY>` y DNS `<LAN_DNS>`. Desde Windows: 4/4 ping, 0 % pérdida, 3–8 ms (media 6 ms), y TCP 13305 directo. El aviso mDNS es conflicto **local** Avahi + systemd-resolved en 5353 IPv4/IPv6; no hubo colisión remota ni afectó la resolución desde Windows. |
| UMA y memoria | **PASS** | `MemTotal` 123.5 GiB y `MemAvailable` 121.3 GiB; swap 123.5 GiB, CMA 0. El boot registra VRAM fija 2048 MiB y GTT 63212 MiB (~61.7 GiB), por lo que la configuración `UMA_SPECIFIED` de 2 GiB persistió. |
| CPU, GPU y Vulkan/ROCm | **PASS** | AMD Radeon 8060S / `gfx1151`; KFD y render presentes, usuario en `video`, y nodos KFD/render accesibles. `rocminfo` nativo enumeró el agente `gfx1151` sin override; RADV/Mesa 26.2.1 enumeró Radeon 8060S. En reposo: GPU 32 °C / 7.51 W / 635 MHz y CPU 34.5 °C. |
| Almacenamiento | **WARN** | Raíz, HOME y Docker resuelven al Btrfs del NVMe; 1.8 TiB libres. SMART: salud aprobada, `critical_warning=0`, spare 100 %, uso 0 %, errores de medio y log de errores 0. Crucial E100: Composite bajó de 35.9 a 34.9 °C; Sensor 2 se mantuvo en 77.8 °C, sin flags ni errores. Crucial no documenta la ubicación física de Sensor 2, por lo que no se atribuye a controlador o NAND ni se infiere un umbral crítico. Acción: ventilar/revisar montaje; detener I/O alto si Composite ≥75 °C; apagar si Composite ≥80 °C o aparece `critical_warning`. |
| Journal del boot | **PASS con avisos benignos** | Sin reset/timeout AMDGPU, errores KFD, OOM, segfault, AER/PCIe, I/O/NVMe ni filesystem/thermal throttle. El boot limpio contiene inicialización normal AMDGPU/KFD y Btrfs. Se clasifican como benignos el soporte TDX ausente, truncado de nombre workqueue, P2P Wi-Fi/multicast, bloques UFW multicast y avisos Avahi. |
| Firewall | **PASS** | UFW activo, política incoming/routed deny y outgoing allow; SSH permitido. La única excepción TCP 13305 es `<LAN_CIDR>` hacia `<HALO_HOST>` sobre `wlan0`; no se amplió ninguna regla. |
| Docker | **PASS** | `docker` enabled/active; cero contenedores en ejecución o detenidos. Imagen `rocm/pytorch` retenida por digest `sha256:c38e…db9ad`; usuario `operador` no pertenece al grupo `docker`. No se lanzó contenedor GPU. |
| Lemonade | **PASS con avisos deliberados** | `lemond.service` de usuario enabled/active, PID supervisado por user manager y escucha exactamente `<HALO_HOST>:13305`. `Linger=no`: el user manager y el servicio arrancaron después del login SSH de esta comprobación, así que un siguiente boot sin login no los iniciará; no se habilitó linger. Configuración preservada: rutas absolutas y escribibles para `models_dir` y `extra_models_dir`, backend `llamacpp:vulkan`, binario Vulkan `llama-server` b10375. Model Manager y `/v1/models` enumeraron los modelos actuales. El frontal aplicó CORS correcto: Origin LAN exacto respondió 200 con ACAO y `evil.invalid` recibió 403. El `*` del log pertenece únicamente al hijo llama.cpp en loopback; no describe CORS amplio del frontal. La ausencia de API key es un riesgo LAN deliberadamente aceptado, no un fallo de CORS. |
| UI y API por LAN (sin túnel) | **PASS** | Desde Windows: `GET /` 200 (UI inline), `/v1/models` 200 con Origin LAN exacto/ACAO, `evil.invalid` 403, y `POST /api/v1/chat/completions` SSE 200 con `[DONE]`. El chat usó un modelo ya presente, completó a 200 y lo descargó de memoria después; el journal posterior no mostró reset/OOM/5xx de ese flujo. |

### Advertencia operacional abierta

Durante la ventana se detectó una descarga Hugging Face de **18.56 GiB** iniciada
antes de la prueba LAN registrada a las 13:41:04. En la relectura de equipo tecnico
avanzaba normalmente al **32 %** (**5.75 GiB**), sin señal de atasco y con 1.8
TiB libres; no se interrumpió. También constan solicitudes previas de borrado
de modelos que generaron un 500 esperado por intentar borrar un modelo de
`extra_models_dir`. No se originaron ni alteraron esas operaciones en este
chequeo, y no se detuvo el servicio ni se borraron artefactos sin autorización.
Por ello el subgate “sin descarga de modelo activa” queda **AVISO
CONTROLADO**. No había procesos q38rocm, Unsloth, QLoRA, datasets ni
entrenamiento; fuera de `lemond`, tampoco quedó `llama-server` tras el chat.

Las conclusiones de la comprobacion y de la validacion LAN estan resumidas
arriba. No se publican registros privados ni rutas para recuperarlos.
