# Plan final — Halo Strix / CachyOS / IA local

> **English:** [operational guide](en/setup-guide.md#scope-and-gates) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

**Fecha de research:** 2026-08-25  
**Estado:** diseño y research únicamente. **Todavía no se ha conectado, ejecutado comandos ni modificado el host.**  
**Alcance:** preparación de inferencia local con llama.cpp y Lemonade Server, y adaptación/entrenamiento con Unsloth y alternativas ROCm, en un PC “Halo/Strix” con CachyOS, 128 GB de RAM y SSD de 2 TB.

## 1. Resumen ejecutivo

### Decisiones recomendadas

1. **No asumir SKU ni target.** “Halo/Strix + 128 GB” solo es una hipótesis. El inventario debe detectar CPU, iGPU y target `gfx*`; **solo** si confirma Ryzen AI Max/Max+ Strix Halo aplicará `gfx1151`. Si el target no es `gfx1151` o no aparece en las matrices compatibles de la pila elegida, se detiene el plan y se replantea antes de instalar o medir.
2. **Vulkan será el baseline de inferencia.** Es la ruta inicial verificable y el fallback permanente.
3. **HIP/ROCm será el candidato de producción**, no la ruta inicial: se promoverá únicamente tras pasar los gates de kernel/KFD/CWSR, estabilidad y benchmark frente a Vulkan.
4. **No mezclar ROCm.** Se elegirá tras el inventario una sola pila coherente:
   - paquetes nativos CachyOS/Arch compatibles entre sí, **o**
   - runtime ROCm aislado de Lemonade/contenedor AMD.

   Nunca paquetes ROCm Arch 7.2 con userspace AMD 7.14 en el host.
5. **Entrenamiento primario:** contenedor AMD PyTorch ROCm fijado + Transformers/PEFT/TRL. Depende del kernel/driver del host, pero aísla userspace.
6. **Unsloth Desktop/Studio no es ruta primaria.** Se tratará como beta/experimento posterior; solo se aceptará para entrenamiento tras un POC exitoso en esta APU.
7. **No reparticionar** el SSD recién instalado sin conocer primero particiones, cifrado, Btrfs, espacio y recuperación.
8. **Memoria:** UMA de BIOS pequeña; GTT/TTM dinámico. Empezar con el valor observado, normalmente ~64 GB; probar 80 GB y solo después 96 GB con margen medido.

### Lo que no haremos

- No instalar `amdgpu-pro`, AMDGPU DKMS ni `HSA_OVERRIDE_GFX_VERSION`.
- No aceptar una clave de host SSH nueva automáticamente (`StrictHostKeyChecking=accept-new` queda prohibido).
- No modificar BIOS, kernel, particiones, bootloader ni firmware antes de backup/rollback probado.
- No abrir Lemonade, llama.cpp ni Unsloth a Internet/LAN por defecto.
- No lanzar entrenamiento 32B/70B como primer POC.
- No inferir que un “EVO-X2/X3” concreto ni Unsloth Desktop funcionarán sin evidencia local.

## 2. Incógnitas críticas e inventario futuro

### Datos requeridos para una futura sesión SSH

- Alias o FQDN/IP aprobado en `~/.ssh/config`.
- Usuario SSH autorizado y **clave SSH ya configurada**; no contraseñas, tokens ni claves privadas por chat.
- Antes de conectar, una persona verificará por un canal fiable la huella pública del host. La primera conexión usará `StrictHostKeyChecking=yes` y `UserKnownHostsFile` controlado; una discrepancia o clave desconocida detiene la sesión. Nunca usar `accept-new`, `no` ni sobrescribir una clave conocida.
- Confirmación de ventana de mantenimiento antes de reinicios/cambios.
- Método de recuperación local o consola física disponible antes de tocar kernel/arranque.
- Destino de backup externo y capacidad disponible.

Los informes que se compartan fuera del equipo de operación redactarán hostname, FQDN, IP, MAC, seriales, UUID, rutas locales/remotas, topología, SSID y demás datos de red. No se solicitarán ni pegarán secretos por chat; las credenciales siguen los canales aprobados y no forman parte del informe.

### Inventario solo lectura

#### Sistema, CPU, RAM y arranque

```bash
hostnamectl
uname -a
cat /etc/os-release
lscpu
free -h
cat /proc/cmdline
findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS /
lsblk -e7 -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS
efibootmgr -v
```

#### APU, GPU, KFD, CWSR, ROCm y Vulkan

```bash
lspci -nnk
cat /sys/module/ttm/parameters/pages_limit
grep -E 'cwsr_size|ctl_stack_size' /sys/class/kfd/kfd/topology/nodes/*/properties
rocminfo
rocm-smi
vulkaninfo --summary
```

#### Red, temperatura y almacenamiento

```bash
ip -br link
nmcli -f GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,GENERAL.HWADDR device show
sensors
```

#### Requieren `sudo`, pero siguen siendo solo lectura

```bash
sudo dmidecode -t system -t baseboard -t bios -t memory
sudo smartctl -a /dev/nvme0
sudo nvme smart-log /dev/nvme0
```

Los comandos sobre NVMe se ajustarán al dispositivo real detectado por `lsblk`. La auditoría debe capturar también versiones de kernel, Mesa, firmware, Lemonade, llama.cpp, Python, PyTorch y cualquier ROCm existente.

La fase 0 es **solo inventario**: no certifica salud de RAM. El gate de Memtest86+ de cuatro pasadas exige consola local, reinicio y aprobación humana en una fase posterior. Además, antes de cargas sostenidas se ejecutará una prueba Linux de RAM de 60 minutos, limitada al 50 % de `MemAvailable` al inicio y sin agotar el margen operativo reservado; cualquier error, swap inesperado u OOM falla el gate.

## 3. Arquitectura objetivo

```text
SSH con clave / túnel SSH
          │
Firewall: SSH permitido; APIs solo loopback
          │
┌──────────────── CachyOS ────────────────┐
│ kernel >= 6.18.4 o CWSR backport         │
│ amdgpu in-tree + KFD                     │
│ linux-firmware / amd-ucode / Mesa RADV   │
│                                           │
│ llama.cpp Vulkan  ── baseline/fallback    │
│ llama.cpp HIP     ── candidato medido     │
│ Lemonade :13305   ── 127.0.0.1 únicamente │
│ vLLM ROCm         ── experimental         │
│                                           │
│ Contenedor AMD PyTorch ROCm fijado        │
│ Transformers + PEFT + TRL                 │
│ Unsloth Core/Desktop ─ experimento        │
└───────────────────────────────────────────┘
             │
 /srv/ai/{models,datasets,recipes,runs,exports,cache}
```

### Aislamiento recomendado

- **Inferencia:** builds Vulkan e HIP independientes, identificados por commit, flags, runtime y checksum.
- **Lemonade:** inicialmente backend Vulkan o `system` solo si el `llama-server` validado y sus librerías HIP son coherentes. Puerto OpenAI `13305` en `127.0.0.1`.
- **Entrenamiento:** imagen oficial AMD/PyTorch ROCm fijada por digest; el contenedor usa `/dev/kfd` y `/dev/dri`, pero no sustituye el kernel ni `amdgpu` del host.
- **Recursos:** inferencia y entrenamiento no coexistirán salvo prueba explícita. Entrenar debe detener el servicio de inferencia para liberar GTT/RAM.
- **Manifiesto de experimento:** todo experimento que use ROCm/HIP fija una única combinación exacta de kernel, paquete y commit de backport CWSR si aplica, firmware, Mesa, ROCm, PyTorch y binarios. Un supuesto “backport equivalente” sin referencia verificable falla el gate; no se mezclan componentes de pilas distintas.

## 4. Plan por fases

| Fase | Objetivo y acciones | Gate | Rollback | Entregable |
|---|---|---|---|---|
| **0. Auditoría** | Ejecutar únicamente inventario de lectura; identificar APU, `gfx*`, kernel, CWSR, GTT, almacenamiento, Btrfs, SSD y red. Antes de la primera carga, identificar y registrar los sensores GPU edge/hotspot disponibles, sus límites `critical`/`max` expuestos por hwmon o firmware, y la telemetría disponible de clocks y potencia. | CPU, iGPU y target quedan documentados; si el target no es `gfx1151` o no está en la matriz compatible, detener y replanificar. Antes de cualquier carga, el manifiesto fija un umbral de parada GPU conservador y verificable a partir de los límites realmente expuestos. Si firmware no expone límites fiables o no hay telemetría continua de temperatura, clocks y potencia, no se ejecuta carga sostenida. No declara saludable la RAM. | N/A | Informe SSH redactado, matriz de compatibilidad real y manifiesto térmico previo a carga. |
| **1. Backup/rollback y salud física** | Definir copia externa cifrada; guardar configuración, inventario, particiones y versiones. Si ya existe Btrfs, configurar snapshots de sistema, excluyendo pesos/datasets/runs. Ensayar recuperación. Con consola local, reinicio y aprobación humana: Memtest86+ cuatro pasadas; además prueba Linux de RAM limitada y documentada. | Restore probado; Memtest86+ termina cuatro pasadas sin errores; prueba Linux sin errores dentro de sus límites; presupuesto de almacenamiento de peor pico cabe y deja >=20 % libre. | Restauración externa/snapshot. | Runbook de recuperación, evidencia RAM y presupuesto de capacidad. |
| **2. Plataforma** | Confirmar kernel con CWSR/KFD; usar amdgpu in-tree, `linux-firmware`, `amd-ucode`, Mesa/RADV. Mantener kernel previo arrancable. Configurar zram; desactivar zswap si zram está activo. Validar antes de carga que los sensores, límites y telemetría térmica registrados en fase 0 siguen disponibles. | Target auditado compatible; KFD/CWSR y Vulkan funcionales; arranque alternativo disponible; umbral térmico GPU conservador y verificable fijado en manifiesto. Si faltan límites fiables de firmware o se pierde telemetría de temperatura, clocks o potencia, bloquear carga sostenida. | Arrancar kernel anterior; revertir configuración de memoria. | Baseline de plataforma aprobado. |
| **3. Vulkan baseline** | Compilar/instalar llama.cpp Vulkan versionado. Probar modelo pequeño y después un GGUF de referencia. Medir con una sola variable por ejecución. | 20 min GPU y 2 h baseline: cero errores de kernel/AER/OOM/reset amdgpu; variación interréplica <=5 %; telemetría continua. Parada inmediata al alcanzar el umbral térmico fijado, reset, error térmico, pérdida de telemetría o caída sostenida de clocks. | Deshabilitar binario/servicio; CPU solo diagnóstico. | Baseline, SLO y perfil reproducible. |
| **4. HIP candidato** | Construir llama.cpp HIP/ROCm separado. No usar overrides HSA. Cada ejecución fija un manifiesto con kernel, firmware, Mesa, ROCm, PyTorch, binarios, y paquete o commit verificable del backport CWSR si aplica. | Una pila coherente; cero errores kernel/AER/OOM/reset amdgpu; variación <=5 %; p95 TTFT/TPOT no supera en >5 % al baseline ni al SLO del perfil; calidad determinista equivalente con prompt set congelado. | Volver a Vulkan; eliminar runtime aislado. | Decisión HIP: aprobado o descartado con manifiesto. |
| **5. Lemonade y servicio** | Instalar versión auditada — candidato informado: Lemonade 11.7.0— con backend validado. systemd endurecido, usuario dedicado, loopback, logs rotados, healthcheck y túnel SSH si se requiere acceso. Definir antes del run el SLO de solicitudes válidas y la comprobación de respuesta correcta para el conjunto de prueba congelado; medir y presupuestar por separado el tiempo de carga del modelo. | Sólo loopback y cero listeners no autorizados. En el baseline exactamente de 2 h y el soak candidato exactamente de 8 h: 0 errores inesperados (HTTP 5xx, crash o timeout fuera del SLO) y 100 % de solicitudes válidas correctas. Tras 20 ciclos de carga/descarga o requests, RAM/GTT no recuperada <=5 % respecto al estado estable. Cada restart llega a healthcheck listo en <=60 s, más el tiempo de carga de modelo medido y presupuestado separadamente. | `systemctl disable --now`; volver a llama.cpp directo. | Servicio local, evidencia de gates y runbook operativo. |
| **6. Entrenamiento base** | Contenedor AMD PyTorch ROCm fijado; validar HIP real sobre el target auditado, no CPU. POC QLoRA 1.5–4B. Definir antes del run dataset/prompt de evaluación, métrica, baseline y umbral comparativo. | Loss y eval_loss finitas, sin NaN/Inf, en 20/200/1000 pasos; checkpoint y resume producen estado y métrica dentro del umbral predefinido; >=20 GB RAM libres. | Eliminar contenedor/runs; conservar base y datos intactos. | POC reproducible con adaptador, manifiesto y evaluación. |
| **7. Escalado entrenamiento** | 8–14B tras POC; 32B solo con presupuesto de memoria validado. Exportar adapter → merge FP16 → GGUF → validación. | 3 h soak sin NaN/Inf ni reset; checkpoint recuperable; evaluación con métrica y diferencia admisible definidas antes del run. | Revertir al adaptador/checkpoint previo. | Pipeline reproducible de adaptación. |
| **8. Unsloth experimental** | Evaluar Core/Studio; Desktop/AppImage beta solo como UI/prueba. Repetir POC sin sustituir la ruta de contenedor. | HIP real, atención correcta, memoria estable y resultados equivalentes. | Quitar AppImage/entorno; volver al contenedor. | Decisión explícita: adoptar o mantener experimental. |
| **9. Estabilización** | Soak 8 h, actualización controlada, telemetría, límites térmicos, backup periódico y revisión de seguridad. | Sin errores ni throttling sostenido; rollback ensayado. | Kernel/runtime/snapshot conocidos. | Operación estable y calendario de mantenimiento. |

## 5. Configuración inicial prudente

### Plataforma

- Kernel: **>= 6.18.4** o con un backport CWSR/KFD cuyo paquete y commit estén referenciados y verificables; “equivalente” sin esa referencia no es aceptable.
- Driver: `amdgpu` incluido en kernel; sin DKMS ni `amdgpu-pro`.
- Firmware: `linux-firmware` y `amd-ucode` actuales y registrados.
- Vulkan: Mesa + RADV/vulkan-radeon.
- Memoria:
  - UMA BIOS: mínima disponible, idealmente ~0.5 GB.
  - GTT: registrar valor inicial; normalmente ~64 GB.
  - Escalado: 80 GB tras baseline; 96 GB solo después de evidencia.
- Swap: zram sí; no zswap simultáneo; no HugeTLB como optimización inicial.
- Temperaturas:
  - objetivo CPU/APU: `<90 °C`; detener investigación térmica a `>=95 °C`;
  - NVMe: objetivo `<60 °C`; pausar a `>=70 °C`.
  - GPU: antes de la primera carga, registrar sensores edge y/o hotspot **solo si existen en este hardware**, sus valores y límites `critical`/`max` expuestos por hwmon o firmware, junto con clocks, indicadores de throttling y potencia AC medida. No se fija una temperatura GPU universal.
  - El manifiesto fija antes del benchmark un umbral de parada GPU conservador y verificable derivado de los límites realmente expuestos. Si firmware no expone límites fiables o se pierde telemetría de temperatura, clocks o potencia, no se ejecuta carga sostenida.
  - detener inmediatamente la carga al alcanzar el umbral fijado, ante reset, error térmico, pérdida de telemetría o caída sostenida de clocks respecto del perfil estable; investigar, corregir y reiniciar la validación antes de reanudar.

### Inferencia

- Backend inicial: Vulkan.
- HIP: candidato posterior y separado.
- Perfil inicial de prueba:
  - capas GPU: todas las que admita el modelo;
  - contexto: 32k;
  - concurrencia: 1;
  - KV cache: `q8_0`;
  - Flash Attention: medir activado/desactivado, no asumir beneficio;
  - bind: `127.0.0.1`.
- Modelos progresivos:
  1. modelo pequeño de salud;
  2. Qwen3 30B-A3B Q6/Q8;
  3. Qwen3/Qwen2.5-Coder 32B Q5;
  4. Llama 3.3 70B Q4 únicamente como prueba de capacidad, no compromiso de rendimiento.

### Entrenamiento

- POC: QLoRA 1.5–4B; luego 8–14B.
- Parámetros iniciales: NF4, double quant, BF16 si la validación HIP lo confirma, `r=16`, `alpha=32`, microbatch 1, acumulación 8–16, contexto 2k.
- No asumir Flash Attention/atención ROCm funcional: verificar kernels y corrección.
- Layout reproducible:

  ```text
  /srv/ai/datasets
  /srv/ai/recipes
  /srv/ai/runs
  /srv/ai/exports
  ```

- Mantener pesos base inmutables; datasets, runs y caches fuera de snapshots Btrfs de sistema.

### Almacenamiento

- No reparticionar hasta la fase 1.
- Antes de cualquier descarga o run, aprobar un presupuesto cuantificado de: modelos base, cache, datasets, checkpoints, merged FP16, GGUF, temporales, logs y backups/snapshots.
- El peor pico documentado debe caber y conservar **>=20 % libre**; si no cabe, no se descarga ni entrena.
- Cuotas o presupuesto explícito para pesos, cache, datasets, checkpoints y exports.
- Cifrado y backup externo para datos sensibles; no exponer datasets por API.

## 6. Matriz resumida de benchmarks y gates

| Gate | Prueba | Criterio |
|---|---|---|
| **A — Salud** | SMART/NVMe; después de aprobación, Memtest86+ 4 pasadas y prueba Linux de RAM limitada | Memtest86+ cuatro pasadas y prueba Linux sin errores; fase SSH no certifica RAM. |
| **B — Plataforma** | KFD/CWSR, Vulkan, `rocminfo`, Torch HIP | Target real auditado y presente en matriz; no fallback CPU ni DKMS. Si no es `gfx1151`, replanificar Strix Halo. |
| **C — Térmica** | 20 min CPU, 20 min RAM, 20 min GPU, 60 min combinada | Antes de cargar: sensores edge/hotspot disponibles, límites `critical`/`max` de hwmon/firmware, clocks/potencia y umbral GPU conservador verificable quedan registrados en el manifiesto. Sin límites fiables o sin telemetría continua de temperatura, clocks y potencia no hay carga sostenida. Parada inmediata al alcanzar el umbral, reset, error térmico, pérdida de telemetría o caída sostenida de clocks; potencia AC registrada. |
| **D — Inferencia** | Backend × modelo × contexto × concurrencia | Tres réplicas; cero errores kernel/AER/OOM/reset amdgpu; variación <=5 %; p95 TTFT/TPOT <= baseline ×1,05 y <= SLO del perfil; prompt set congelado con calidad determinista equivalente. |
| **E — Servicio** | API, reinicio, recuperación, fugas; definir antes del run SLO y criterios de corrección de solicitudes válidas | Puerto sólo loopback y cero listeners no autorizados. Baseline exactamente 2 h y soak candidato exactamente 8 h: 0 HTTP 5xx, crashes o timeouts fuera del SLO; 100 % de solicitudes válidas correctas. Tras 20 ciclos de carga/descarga o requests, RAM/GTT no recuperada <=5 % respecto al estado estable. Restart hasta healthcheck listo <=60 s más el tiempo de carga de modelo medido y presupuestado por separado. |
| **F — Entrenamiento** | 20/200/1000 pasos, 60 min, 3 h soak, resume | Loss/eval_loss finitas, sin NaN/Inf; checkpoint/resume válido; métricas, baseline y diferencia admisible definidos antes del run. |

Metodología: una variable por experimento, warmup descartado, tres réplicas, mediana/p5/p95/desviación y medición a 1–2 s; variabilidad objetivo `<=5 %`. El baseline y el SLO de TTFT/TPOT se fijan antes de comparar candidatos. No se promueve una pila con regresión >5 % frente al baseline, salvo tradeoff explícito aprobado y documentado.

## 7. Backlog priorizado

1. **Auditoría SSH solo lectura + informe.**
2. **Backup, rollback y prueba de recuperación.**
3. Validación de kernel/KFD/CWSR, Vulkan, firmware y salud térmica/SSD/RAM.
4. llama.cpp Vulkan baseline y benchmark.
5. llama.cpp HIP candidato y decisión de promoción.
6. Lemonade local endurecido, con API loopback y túnel SSH.
7. Contenedor AMD PyTorch ROCm y POC QLoRA 1.5–4B.
8. Escalado a 8–14B y pipeline adapter/merge/GGUF.
9. Evaluación limitada de Unsloth Core/Studio/Desktop.
10. Soak, operación, actualizaciones y recuperación recurrente.

## 8. Riesgos y decisiones que requieren aprobación humana

### Requieren aprobación explícita

- Actualizar kernel, BIOS/UEFI, firmware, Secure Boot o microcode.
- Cambiar GTT/TTM, límites de potencia o ventilación.
- Crear/modificar particiones, cifrado o bootloader.
- Instalar contenedores/runtimes externos y aceptar sus licencias.
- Descargar modelos/datasets con restricciones de licencia.
- Publicar una API fuera de loopback, habilitar VPN/reverse proxy o túneles.
- Retención, backup y tratamiento de datos de entrenamiento.

### Riesgos principales

- Incompatibilidad CachyOS/ROCm binario.
- Falta de CWSR.
- Presión de RAM unificada.
- Degradación térmica.
- Combinación incoherente de userspace ROCm.
- Entrenamiento AMD aún inmaduro.
- Exposición accidental de APIs, modelos o datasets.

## 9. Fuentes primarias seleccionadas

- AMD, **AMD RDNA3.5 system optimization**, ROCm **7.14.0** — GPUVM, GTT/TTM, UMA y requisito kernel:  
  <https://rocm.docs.amd.com/en/latest/reference/system-optimization/rdna3-5.html>

- AMD, **Use ROCm on Radeon and Ryzen**, documentación hasta ROCm **7.2.1** — alcance de Ryzen AI APU y matrices:  
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/>

- AMD, **llama.cpp on ROCm documentation**, `b5997`, **2026-07-24**:  
  <https://rocm.docs.amd.com/projects/llama-cpp/en/docs-25.08/>

- Lemonade Server, **llama.cpp Backend Options** — ROCm, Vulkan, system backend y canales:  
  <https://lemonade-server.ai/docs/guide/configuration/llamacpp/>

- Lemonade Server, **vLLM Backend Options** — `gfx1151` validado, backend experimental:  
  <https://lemonade-server.ai/docs/guide/configuration/vllm/>

- Lemonade Server, **Strix Halo Linux kernel requirement** — CWSR, kernel 6.18.4+ y conflicto DKMS:  
  <https://lemonade-server.ai/gfx1151_linux.html>

- Unsloth, **Train & run models on AMD GPUs with Unsloth** — soporte AMD/Strix Halo declarado:  
  <https://unsloth.ai/docs/basics/amd>

- Unsloth, **Unsloth Requirements** — requisitos y mínimos publicados de fine-tuning:  
  <https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements>
