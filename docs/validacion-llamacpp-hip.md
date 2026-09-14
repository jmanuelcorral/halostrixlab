# Validación llama.cpp HIP — 2026-08-25

> **English:** [operational guide](en/setup-guide.md#vulkan-and-hip) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

## Resultado

**Gate: FAIL antes de configurar.** Tras la espera requerida se realizó una
única conexión SSH de solo lectura/preparación. Se verificaron sensores,
espacio, memoria/GTT, `rocminfo` con `gfx1151`, `hipconfig` y ausencia de
procesos llama.cpp antes de intentar la configuración.

La construcción se detuvo porque la salida consultada de `hipconfig -l` no
confirmó de forma inequívoca la ruta de compilador `HIPCXX` exigida por el
encargo. No se adivinó una ruta, no se configuró CMake, no se creó `build-hip`,
no se compiló, no se ejecutaron load-only, smoke o benchmark, y no se añadió
ningún workaround como `HIP_DEVICE_LIB_PATH` u override HSA.

## Estado y siguiente paso

- ROCm 7.2.4 y `rocminfo`/`gfx1151` siguen validados por la fase previa.
- Vulkan conserva el baseline ganador.
- No hay comparación HIP ni decisión de promoción.
- Rollback no requiere acción: `build-hip` no existe. ROCm no se desinstala.
- Una futura sesión autorizada deberá recuperar la ruta exacta de compilador
  que expone HIP y volver a ejecutar el configure individual con esa ruta,
  sin inferirla manualmente.

Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Reintento con diagnóstico equipo tecnico

Se realizó la espera de 120 s y una única conexión adicional. Se consultaron
`hipconfig -l/-R/-p/-c`, propietario Pacman y versión de `hipcc` antes de
CMake, pero el gate estricto no pudo confirmar la ruta ejecutable
`$(hipconfig -l)/clang` con propiedad `rocm-llvm 7.2.4`. Conforme al encargo,
se detuvieron todas las fases posteriores: no configure, build, offload,
smoke, benchmark, manifiesto ni cambios de variables de entorno.

Vulkan sigue siendo el único baseline promovido; el build HIP permanece pendiente de
resolver esa comprobación de ruta sin adivinarla ni aplicar hacks.

## Gate literal y fallo de dependencias de desarrollo

El gate literal **PASS**: `/opt/rocm/lib/llvm/bin/clang` ejecuta, pertenece a
`rocm-llvm 2:7.2.4-2.1` y la versión instalada es 7.2.4. Se usó esa ruta
literal y `HIP_PATH=/opt/rocm`, sin variables adicionales.

CMake detectó HIP Clang 22.0.0 y completó sus pruebas ABI, pero se detuvo en
`ggml-hip`: falta la configuración de desarrollo **hipblas**
(`hipblasConfig.cmake`/`hipblas-config.cmake`). No se instalaron dependencias
ni se ajustó `CMAKE_PREFIX_PATH`; se detuvieron build, offload, smoke y
benchmark. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## hipBLAS — preflight detenido

La siguiente sesión completó las consultas read-only de `hipblas`, `rocblas`,
su plan Pacman y actualizaciones. El control local rechazó conservadoramente el
plan antes de instalar porque su detector textual encontró `linux` dentro de
una URL de repositorio, no un paquete kernel. No se ejecutó Pacman de
instalación, no se modificó CMake ni se borró `build-hip`.

Esto es un falso positivo del preflight, no evidencia de conflicto ROCm. Una
revisión posterior deberá inspeccionar los **nombres de paquetes** del plan,
no texto de URLs, antes de autorizar `hipblas`. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## hipBLAS instalado y build HIP completado

El preflight corregido analizó exclusivamente pares nombre/versión de Pacman,
sin URLs. No había updates pendientes ni paquetes kernel, Mesa, DKMS o
AMDGPU-Pro en el plan. `hipblas` se instaló con su cohorte ROCm 7.2.4 y
`rocblas`; `hipblasConfig.cmake` quedó bajo `/opt/rocm` y pertenece al paquete
esperado.

`cmake --fresh` con el compilador HIP literal validado y los flags autorizados
terminó correctamente, seguido de `cmake --build ... --parallel` con éxito.
Las etapas posteriores de offload, smoke y benchmark no se ejecutaron en esta
conexión; siguen siendo necesarias antes de comparar o promover HIP. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Runtime HIP — gate de dispositivo

La validación runtime se detuvo antes de load-only: el criterio estricto que
exigía que `llama-cli --list-devices` contuviera simultáneamente las cadenas
HIP y `gfx1151`/Radeon no se cumplió con su salida real. No se infirió backend
a partir de otros artefactos y, por tanto, no se ejecutaron smoke ni benchmark
HIP. El build permanece disponible, pero **Vulkan conserva el ganador** hasta
que una auditoría posterior clasifique la salida exacta de dispositivos sin
relajar el gate. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Linkage HIP

La auditoría posterior de `ldd`/`readelf`/CMakeCache/`rocminfo` se detuvo en
su gate de linkage antes de load-only: no se confirmó con el localizador
estricto una biblioteca `libggml-hip.so` y la cadena directa/transitiva
`libamdhip64` con hipBLAS/rocBLAS. No se ejecutaron smoke ni benchmark HIP.
El build queda sin promover y Vulkan sigue ganador. Los resultados necesarios se resumen en este documento; registros privados excluidos.

## Runtime, smoke y benchmark HIP directos

Con la reclasificación autorizada del enlace (ROCm0/Radeon8060S y la cadena de
bibliotecas HIP), el load-only real fue **PASS** e informó `offloaded 29/29
layers`. El smoke síncrono terminó RC 0 con texto coherente, sin stderr, y el
benchmark terminó RC 0 sin procesos residuales ni eventos AMDGPU/KFD/OOM/reset
en los journals filtrados. Sensores y memoria/GTT se capturaron antes/después;
la comprobación térmica es corta/provisional, no un soak.

| Backend | PP512 tok/s | TG128 tok/s |
|---|---:|---:|
| Vulkan baseline | 5263.79 ± 10.83 | 114.39 ± 0.24 |
| HIP/ROCm | 5448.84 ± 173.67 | 102.51 ± 0.17 |

HIP mejora PP ~3.5 %, por debajo del umbral de promoción del 5 %, y regresa TG
~10.4 %, superando la regresión permitida. **Decisión: Vulkan permanece
ganador; HIP queda disponible experimentalmente, no promovido.** Los resultados necesarios se resumen en este documento; registros privados excluidos.
