# Winnow y Ollaya detrás del llama-swap existente

[English](en/winnow-ollaya-research.md) | [Continuación](continuacion-en-halo.md)

## Conclusión, 28 de septiembre de 2026

Actualización posterior: [despliegue autorizado y pruebas CPU](../workspaces/inference/OLLAYA.md).
El texto siguiente conserva la investigación previa, no el estado actual.

**Recomiendo Ollaya CPU en Docker para una primera prueba funcional de
Winnow-12B**, manteniendo llama-swap como único gateway y propietario del ciclo
de vida. E4B es una alternativa más pequeña, no el mismo modelo. Para baja
latencia en la Radeon gfx1151, ninguna de las dos soluciones revisadas ofrece
un despliegue AMD listo y validado: sería una segunda fase de adaptación.

Investigación de código, manifiestos y metadatos remotos, no inferencia local.
No se descargaron pesos ni capas Docker, no se construyeron imágenes y no se
cambiaron servicios, configuración del gateway o dispositivos GPU. Las fases
siguientes son propuestas, no autorización ni instrucciones ya ejecutadas.

## Comparación

| Aspecto | Winnow nativo | Ollaya 0.7.5 | Laya actual |
| --- | --- | --- | --- |
| Modelo | Winnow-12B, Gemma 4 12B IT ajustado | `winnow:12b` y `winnow:e4b`, explícitos | Laya multilingual, unos 322 millones de parámetros |
| Pesos para texto | Q8_0, 12,670 GB | Mismo Q8 de 12B; E4B Q8, 8,005 GB | Checkpoint de 0,644 GB |
| CPU | El motor de decisiones exige GPU; compilar CPU no habilita servicio | Runner llama.cpp con CPU explícita | Servicio CPU existente |
| AMD gfx1151 | Sin perfil HIP/Vulkan ni Docker AMD oficial revisado | Sin backend HIP distribuido; Vulkan no se distribuye | No necesita GPU |
| Docker | Dockerfile NVIDIA CUDA, no ejecución GPU en Docker validada por upstream | Imagen CPU publicada, más variantes CUDA 12/13 | Instalación existente, no sustituir |
| API | Decisiones, chat/SSE, visión e inspección | Decisiones; no chat ni extensión de imágenes Winnow | Decisiones tipadas |
| Contexto | Perfil CUDA 64K cualificado upstream, no en Halo | 8192 tokens; presupuesto de estado 6144 | Servicio configurado con `max_len=1024` |
| Optimización | Cabeza de logits seleccionados y ramas de preguntas | Cabeza completa, preguntas secuenciales y prefijo compartido | Encoder pequeño especializado |

GB decimales. Disco no equivale a RAM/VRAM; KV, buffers y activaciones son
adicionales. El proyector nativo de 12B añade 175.116 MB: texto más visión suma
12,845 GB. No hace falta descargar BF16 ni proyector para la prueba CPU.

### Identidad y disponibilidad verificadas

El manifiesto Ollaya de 12B y el runtime nativo apuntan a revisiones HF diferentes,
pero **al mismo archivo Q8**, con tamaño 12.669.646.592 bytes y SHA-256:

```text
b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea
```

La API HF confirmó tamaño y hash LFS en ambas revisiones, sin descargar los pesos.
La tarjeta y NOTICE de la revisión nativa todavía dicen que no hay pesos:
es documentación desactualizada, no ausencia del artefacto. La verificación
local del archivo completo seguirá siendo obligatoria tras una futura descarga.

Ollaya sí incluye `winnow:12b`, además de E4B; no deducir el modelo de su portada
ni de `latest`. E4B ocupa 8.005.437.472 bytes y usa otra plantilla/calibración.
Los pesos Winnow consultados y Ollaya declaran Apache-2.0; el runtime Winnow es
MIT. Conservar LICENSE, NOTICE y avisos de dependencias al preparar imágenes.

### Ollaya evita una restricción, no todas

Ollaya no ejecuta el servidor parcheado de Winnow: reproduce su plantilla y lee
logits con las bibliotecas de llama.cpp b11146. Por eso puede servir en CPU sin
la comprobación de GPU del motor original. No ofrece todas sus optimizaciones
ni idéntica semántica: recalcula confidence con su propia regla; 12B usa T=1,
y E4B una temperatura ajustada de aproximadamente 1,2574. Probabilidad entre
opciones no significa certeza universal ni calibración para nuestras tareas.

La configuración solo acepta `auto`, `cpu`, `cuda`, `cuda:N` y `metal`.
La distribución Linux no incluye HIP. Un override de bibliotecas no acredita
compatibilidad: hay comprobaciones de ABI y haría falta validar backend y paridad.
Upstream descartó distribuir Vulkan tras obtener 501/505 decisiones coincidentes
en una prueba RTX 4090 Windows. Eso no demuestra fallo en AMD, pero tampoco
permite recomendar Vulkan como sustitución transparente.

El launcher nativo también fija `CUDA0` fuera de macOS y solo expone CUDA/Metal/CPU
en su script de compilación. Una adaptación HIP necesita cambiar compilación,
dependencias, selección de dispositivo y empaquetado, no solo pasar `/dev/kfd`.

### Rendimiento y calidad: límites de la evidencia

Ollaya publica, para cinco preguntas cortas y sin HTTP, medianas de 154 ms para
12B y 96 ms para E4B en RTX 4090; E4B tarda 5,1 s en una CPU x86 de 24 cores.
**No son tiempos de Halo.** Su paridad CPU documentada es E4B 505/505; 12B CPU
figura como no ejecutado. El camino CPU existe en código, pero cargar y medir
12B aquí sigue siendo una puerta de aceptación, no un resultado obtenido.

Winnow nativo obtiene 85,71 % en el subconjunto público JevBench, pero solo
70,00 % de acuerdo con el profesor en typed-decisions, frente a 76,75 % de
Laya Typed Decisions en esa tabla. Ninguna fila es nuestro Laya multilingual.
No hay ganador universal ni comparación local justa todavía. Las latencias
CUDA de Winnow y los tiempos históricos de Laya aquí no son un A/B equivalente.

## Plan propuesto

### 1. Preparación aislada y reproducible

- Mantener todo artefacto/evidencia en el `data/winnow/` ignorado del workspace.
- Usar la imagen CPU 0.7.5 fijada por digest linux/amd64, no `latest`:

```text
ghcr.io/ollaya-dev/ollaya@sha256:3fb6a50039bd97147e131844c21401f2b01aa648cd3749d4c8d8773f5f200fb5
```

- Su manifiesto remoto existe; suma 65.501.633 bytes de capas comprimidas.
  No es tamaño descomprimido ni una prueba de ejecución. Reservar inicialmente
  20-25 GB de disco para 12B, imagen y margen, sin cachés de compilación; ambos
  modelos sumarían 20,675 GB de pesos antes del resto.
- Preparación separada para descargar y verificar modelo, manifiestos y licencias;
  no habilitar descargas bajo demanda desde clientes de inferencia.
- Mantener Laya existente. No descargar otro Laya ni activar el router Laya de Ollaya.

### 2. Contenedor de prueba CPU

- Usuario no root, sin dispositivos GPU, sin Docker socket, capabilities eliminadas,
  `no-new-privileges`, raíz de solo lectura y tmpfs acotado. Identificar y limitar
  las escrituras necesarias del almacén; pesos inmutables tras la preparación.
- Primera propuesta de presupuesto: 8 CPU y 32 GiB RAM, una petición activa;
  son límites de prueba, no consumo medido ni garantía de carga. Revisar memoria
  disponible y cargas existentes antes de arrancar, incluida la memoria unificada.
- `OLLAYA_DEVICE=cpu`, `OLLAYA_MAX_LOADED_MODELS=1`, `OLLAYA_MAX_QUEUE=1`,
  `OLLAYA_KEEP_ALIVE=-1`; contexto stock 8192 y estado hasta 6144.
- Solo `winnow:12b` instalado/admitido. E4B sería otro ensayo deliberado si se
  priorizan menor descarga y evidencia CPU previa; no reemplazo silencioso.
- Ejecutar `ollaya serve` supervisado, sin autoinstalador, daemon del host ni
  política Docker que reinicie al margen de llama-swap. Keep-alive conserva el
  runner mientras viva ese contenedor; llama-swap decide cuándo detenerlo.

### 3. Integración segura con el único llama-swap

Contrato propuesto para decisiones:

```text
Cliente -> llama-swap existente
        -> /upstream/winnow-12b-cpu/v1/systemone
        -> adaptador restringido -> Ollaya CPU
```

- El passthrough es necesario: no asumir despacho automático por `model` en una
  ruta global `/v1/systemone`. Fijar/validar `model=winnow:12b` en el adaptador;
  el alias del gateway y el nombre de Ollaya son distintos.
- El adaptador es parte del backend, no otro gateway. Solo admite decisiones del
  modelo fijo y readiness controlada. Ollaya queda en loopback interno del
  contenedor; publicar únicamente el adaptador en un puerto loopback del host
  previamente comprobado libre. No publicar `/api/pull`, create, delete o copy
  mediante el passthrough genérico. Autenticación local adicional si procede.
- Readiness debe precargar y ejecutar una decisión sintética acotada antes de
  indicar disponibilidad. `/` de Ollaya solo dice que el daemon responde.
- Grupo CPU no exclusivo, separado de Laya; empezar con concurrencia 1 y tiempo
  de carga acotado. Recalcular concurrencia global sin reducir el contrato de
  Laya/Halogen/Gufo. CPU evita exclusión GPU, no contención de RAM/ancho de banda.
- Revisar Caddy: permitir únicamente esta ruta y método si se necesita acceso
  externo; no abrir `/upstream/*`. Preservar la política de acceso existente.
- Cambiar el gateway solo en ventana autorizada: revisar configuración activa,
  drenar, parar, adquirir lease de ajustes, guardar backup, validar y reemplazar
  atómicamente. Pararlo descarga también Laya y cualquier modelo GPU residente.
- No detener ComfyUI para investigar o instalar. Si los guards exigen exclusión
  para la prueba integrada, aplazarla a una ventana aprobada, no eludirlos.
- Halo Control tiene catálogo y selecciones fijos: añadir explícitamente el
  modelo, acciones supervisadas, compatibilidad y pruebas si se quiere control
  desde el panel. No asumir que descubre una cuarta entrada automáticamente.

### 4. Puertas de aceptación

1. Imagen/modelo fijados, hashes completos, arranque no root y backend CPU real.
2. `noul`, `choice`, `score`, español, Unicode y estado estructurado; contratos
   de respuestas y confidence, límites de opciones/contexto y truncamiento.
   La ruta SystemOne de Ollaya devuelve error si el estado fue truncado.
3. Errores de validación, autenticación, exceso de cuerpo, saturación, timeout,
   cancelación y parada con peticiones drenadas; no copiar códigos del servidor
   nativo como si ambos backends fueran idénticos.
4. Carga fría/caliente, p50/p95, memoria pico y presión de CPU. Comparar con
   Laya multilingual usando un conjunto español retenido y entradas que quepan
   en ambos servicios; evaluar contexto largo por separado. No cambiar calibración
   sobre el mismo conjunto empleado para reportar calidad final.
5. Inicio/parada vía llama-swap sin runners huérfanos, sin descargas remotas,
   sin rutas administrativas accesibles y sin modificar Laya. Probar coexistencia
   con un motor GPU solo después del preflight y con presupuesto de memoria.
6. Si carga, corrección o latencia no son aceptables, detener la prueba y conservar
   evidencia privada. Restaurar el backup validado del gateway en mantenimiento;
   no borrar pesos ni datos existentes ni promover resultados parciales.

### 5. GPU AMD, solo como segunda fase

Si CPU permite evaluar calidad pero no cumple latencia, estudiar una imagen
ROCm/HIP para gfx1151. Para conservar chat, visión y optimizaciones específicas,
el runtime nativo es el candidato más fiel, a cambio de mantener una adaptación.
Empezar texto, 8K, una petición y una rama de decisión; después 16K/32K/64K y visión
solo si pasan memoria y corrección. Ramas de preguntas no son slots HTTP.

Exigir compilación/unidades, detección explícita gfx1151 sin fallback CPU,
paridad selected/full y reference/optimized, cancelación y alternancia real.
Integrarlo en el grupo GPU exclusivo de Halogen/Gufo y respetar el lease de
ComfyUI y entrenamiento. No prometer velocidad ni modificar BIOS/GTT para
hacer pasar la prueba. Adaptar Ollaya HIP sería otra vía experimental, no una
opción que su imagen actual habilite con una variable de entorno.

## Fuentes y revisiones

- [Winnow inference](https://github.com/EldanRing/winnow-inference),
  `77d14580c6732ca2f3745750c1dc1fd446d8bcee`: Dockerfile, runtime.lock.json,
  manifests/models.json, native/engine.h, scripts/build.py, scripts/serve.py,
  docs/API.md, docs/VALIDATION.md y docs/BENCHMARKS.md.
- [Ollaya](https://github.com/ollaya-dev/ollaya),
  `f42c89eb7436cfd0f02c582b54b182727118e438`: Dockerfile, registry/v2/library/winnow,
  docs/families/winnow.md, docs/distribution.md, scripts/llama-cpp.sh y fuentes
  server/config/http/scheduler y runner/llama. Release 0.7.5:
  `32acb6d2ea13f616b1e11d9dfb8260b305106847`; la comparación de árboles solo
  difiere en CLAUDE.md, no en esos componentes.
- HF `EldanRing/Winnow-12B`: nativo
  `b2b14213dfa252e6d6b543c8b334762e51772d29`, Ollaya
  `b6ac22b0d51b69b18200acacb3fbdd98073fffe8`; metadatos LFS cotejados.
- HF `EldanRing/Winnow-E4B`, manifiesto Ollaya:
  `734302fe5fbfeb3f21a7ece62653c9539be4aaf3`.
- [Rutas y límites locales de llama-swap](investigacion-multimedia-halo.md),
  pruebas Laya y
  [operación del catálogo](../workspaces/halo-control/README.md).
