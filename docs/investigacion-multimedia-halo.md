# Imagen, vídeo y audio en Strix Halo con llama-swap

[English](en/multimedia-halo-research.md) | [Continuación](continuacion-en-halo.md) |
[Inferencia](../workspaces/inference/README.md)

## Alcance y conclusión

Investigación de fuentes primarias, no despliegue ni benchmark nuevo. Se consultó
el código de llama-swap v255 y documentación upstream de septiembre de 2026.
No se descargaron modelos ni se cambiaron servicios, GPU, kernel o BIOS.
Solo se ejecutó la ayuda de la imagen Gufo local, sin dispositivos GPU.

**llama-swap no genera multimedia:** enruta peticiones y administra procesos.
Necesitamos un servidor por modelo/modalidad con contrato HTTP compatible.
Soporte ROCm genérico no demuestra optimización gfx1151 ni rendimiento local.

Prioridad recomendada:

1. **Kokoro-82M CPU** para voz junto a un LLM sin intercambiar la GPU.
2. **Qwen3-TTS 12Hz 1.7B con Gufo** para voz expresiva/diseñada, primero una variante.
3. **Imagen:** conservar Qwen Image 2512/Edit 2511 en ComfyUI; probar FLUX.2-klein-4B
   o Z-Image-Turbo si se busca una alternativa más ligera. Qwen-Image-2.1 con Gufo
   es la integración API más directa, pero tiene licencia no comercial.
4. **Vídeo:** empezar con Wan2.2-TI2V-5B o LTX-2.3 distilled, uno cada vez,
   mediante ComfyUI y un adaptador de trabajos. No prometer generación en segundos.
5. **Música:** ACE-Step 1.5 turbo, backend PyTorch ROCm, primero sin LM o con LM pequeño.

No se propone ejecutar todos los modelos a la vez ni sustituir los actuales.

## Matriz de candidatos

B = mil millones de parámetros. Tamaño de checkpoint no equivale a memoria de
inferencia; los encoders, VAEs, cachés y activaciones son adicionales.

| Modalidad | Modelo / runtime propuesto | Evidencia y coste | Encaje / decisión |
| --- | --- | --- | --- |
| Imagen/edición existente | Qwen Image 2512 / Edit 2511, ComfyUI ROCm | Image ya generó 1024² localmente; Edit descargado y grafos validados. El operador comunicó deriva del color de ojos | Mantener. No confundir validez del grafo con fidelidad facial |
| Imagen rápida | FLUX.2-klein-4B / ComfyUI o stable-diffusion.cpp Vulkan | 4B nominales, Apache-2.0; principal 7,75 GB, encoder 8,04 GB y VAE 0,168 GB en archivos consultados | Buena prueba compacta; sin benchmark local ni victoria demostrada de Vulkan sobre HIP |
| Imagen rápida | Z-Image-Turbo / ComfyUI o stable-diffusion.cpp | Familia 6B, Apache-2.0, receta destilada de pocos pasos | Candidato, no cifra de latencia validada en este Halo; no deducir disco de 6B × 2 bytes |
| Imagen/edición API | Qwen-Image-2.1 / Gufo HIP nativo | Descarga documentada ~33,1 GB BF16; encoder Qwen3-VL y VAE RGBA, distintos a nuestros pesos | API Images directa; **Qwen Research License no comercial**, revisar uso profesional |
| Vídeo inicial | Wan2.2-TI2V-5B / ComfyUI ROCm | 5B dense, Apache-2.0; checkpoints oficiales consultados ~20,00 GB DiT + 11,36 GB encoder + 2,82 GB VAE | Primera prueba por menor modelo principal; soporte genérico no es benchmark Halo |
| Vídeo + audio | LTX-2.3 22B distilled / ComfyUI | Toolbox dedicado Halo; checkpoint distilled ~46,15 GB, además encoder/componentes según receta | Buena opción integrada audiovisual; licencia LTX propia, no asumir MIT/Apache |
| Vídeo más pesado | Wan2.2 A14B / ComfyUI | Receta Halo de 4 pasos; expertos de alta/baja fase, no basta contar 14B activos para residencia | Segunda fase. No descartar automáticamente por memoria, ni prometer velocidad |
| Vídeo alternativo | HunyuanVideo 1.5 / ComfyUI | Receta 720p/4 pasos del toolbox; benchmarks históricos completos | Licencia excluye UE, Reino Unido y Corea del Sur: no recomendar allí sin derechos adicionales |
| Vídeo experimental | MiniMax H3 / Gufo | HIP específico, FL2VA solo texto en el contrato revisado; componentes cargados por fases | No primera opción: falta benchmark end-to-end cualificado y la API mantiene trabajos |
| Voz eficiente | Kokoro-82M / Kokoro-FastAPI CPU | 0,082B; principal 327 MB + voces; Apache-2.0; español disponible | Mejor convivencia con LLM GPU. No afirmar RTF local; ROCm del wrapper es experimental |
| Voz expresiva | Qwen3-TTS 12Hz 1.7B / Gufo | HIP gfx1151, BF16, Apache-2.0 del modelo; CustomVoice principal 3,833 GB + tokenizer audio 0,682 GB | Buen candidato nativo. GPU exclusiva inicialmente; no trasladar dos slots del LLM al TTS |
| Música/canción | ACE-Step 1.5 turbo / API PyTorch ROCm | MIT, DiT 2B o XL 4B; LM opcional 0,6/1,7/4B; AMD publica prueba Ryzen AI Max+ | Mejor candidato musical, requiere adaptar cola y descarga; comenzar 2B turbo |
| Efectos/ambientes | Stable Audio Open / ComfyUI | Small hasta 11 s, 1.0 hasta 47 s, audio estéreo; licencia específica Stability | Exploratorio: sin benchmark Halo verificado; revisar licencia exacta antes de uso comercial |

Los checkpoints oficiales pueden contener FP32, variantes duplicadas o componentes
alternativos. Ejemplo FLUX: no descargar a la vez el archivo monolítico y su copia
Diffusers. La revisión consultada de Z-Image contiene ~24,62 GB de transformer;
no es una prueba de su consumo BF16. Preparar un manifiesto de archivos/revisiones
antes de cualquier descarga. No instalar todo un repositorio por defecto.

## Qué está realmente optimizado y medido

### Gufo

Gufo implementa kernels nativos para Linux gfx1151. La imagen local fijada anuncia
`serve image`, `serve video`, `serve tts` y `serve asr`; la ayuda no prueba ejecución
con esos pesos. La documentación actual no equivale al binario local 9cad139.

- **Qwen3-TTS:** upstream mide 5,12 s de audio en 2,018 s (CustomVoice), 2,024 s
  (VoiceDesign), 2,234 s (Base ICL), modelos residentes, 64 frames, mediana de tres
  peticiones tras warmup. Primer PCM ~0,201 s o ~0,345 s en Base. Son mediciones
  upstream, no de nuestro equipo. Dos peticiones terminan ~2,025/4,046 s: ejecución
  serial, no batching de dos slots. Español está soportado por el modelo, pero
  Gufo deja calidad multilingüe y voz larga sin cualificar. Probar español propio.
- **Qwen-Image-2.1:** ~5,838 s a 1024² con **dos pasos**, control de desarrollo.
  La receta normal usa 40 pasos y su tabla de rendimiento sigue TODO. No anunciar
  imágenes finales de calidad en seis segundos. `/ready` puede ser solo preparación
  de metadatos: primera petición incluye carga diferida. Sin máscaras separadas
  ni `input_fidelity`, por lo que no resuelve automáticamente el problema de rostro.
- **MiniMax H3:** 91 s corresponde a **una evaluación del denoiser**, 50 bloques,
  1344×768×124. La receta exacta necesita 49 evaluaciones y decodificación posterior.
  No es un vídeo terminado en 91 s. Pico retenido de ese control 40,01 GiB; no es
  pico end-to-end. Inventario por fases ~62,13 GiB encoder + 24,35 GiB precompute +
  37,38 GiB core + VAEs; no sumar como memoria simultánea ni confundir con descarga
  mínima. Calidad y tiempo del vídeo completo aún pendientes en la fuente revisada.

### ComfyUI para Halo

El toolbox kyuz0 incluye Qwen Image/Edit, Wan2.2, HunyuanVideo1.5, LTX-2.3 y H3.
Sus variantes GGUF nuevas se describen como **dev pendientes de validación en
hardware**; no todas las filas del catálogo son benchmarks aprobados. BF16 es el
default LTX-2.3 por soporte matricial nativo; FP8 no es automáticamente más rápido.

El JSON público de benchmarks contiene LTX2-T2V-BF16 ~615 s, Hunyuan T2V ~929 s
y Wan2.2 T2V A14B ~2007 s, filas frías con warm_run_seconds=0. El timestamp LTX2
se convierte a **2026-02-13**, no diciembre. El archivo no fija allí imagen,
resolución/frames y revisión completa de pesos: sirven para advertir que vídeo
puede costar minutos, no para comparar calidad ni atribuir el dato a **LTX-2.3**.
El registro de enero de Wan supera 8300 s: gran sensibilidad a configuración.

No copiar `--gpu-only` del ejemplo upstream: ya causó OOM local con LoRA BF16.
Preservar offload a CPU y reserva revisada. No aplicar overrides gfx1100, cambios
BIOS/GTT o variables de otra Radeon como supuesta optimización universal.

### ACE-Step y Kokoro

AMD publica ~1,8× tiempo real de generación frente a duración de escucha en Ryzen
AI Max+, distinto del ~4× en R9700. El texto no detalla lo suficiente para prometer
una latencia local concreta. La API oficial es asíncrona; ROCm tiene backend `pt`
y fallback de audio `soundfile`. La guía genérica ROCm 6 no valida por sí sola
nuestro gfx1151 ni aconseja degradar el PyTorch existente.

Kokoro-FastAPI ofrece Docker CPU y español. Su rendimiento CPU publicado corresponde
a otras CPUs: medir aquí RTF, primer audio y competencia con Laya antes de declarar
convivencia estable. La CPU también comparte RAM y ancho de banda con la GPU.

## Integración concreta con llama-swap v255

Se verificó `internal/server/server.go` de **v255**, no solo un README:

| Ruta | Soporte del gateway |
| --- | --- |
| `POST /v1/images/generations` | Despacho por `model` JSON |
| `POST /v1/images/edits` | Despacho multipart |
| `POST /v1/audio/speech` | Despacho JSON; cliente debe manejar audio binario/stream |
| `POST /v1/audio/transcriptions` | Despacho multipart; es reconocimiento, no generación |
| `GET /v1/audio/voices` | Selección por query `model` |
| `/v1/videos` y consultas por job | No están en la lista de rutas modelo de v255; usar passthrough/adaptador |
| `/upstream/ALIAS/...` | Reenvío genérico; no convierte contratos ni reescribe mágicamente resultados |
| `/comfyui/...` | Compatibilidad especial con modelo fijo `comfyui_auto`, no configurado en nuestro despliegue |

Qwen TTS y Gufo Image son la ruta más directa; ComfyUI usa `/prompt`, `/history`,
`/view`, `/queue`, WebSocket, no se convierte en API Images por ponerlo detrás del
proxy. ACE-Step usa `/release_task`, `/query_result` y `/v1/audio?path=...`.
Rutas de salida relativas/absolutas requieren reescritura o recuperación explícita
por el adaptador. Validar WAV/MP4 sin truncamiento, multipart, cancelación y rangos.
La ayuda antigua Gufo y los docs nuevos difieren en rutas vídeo: fijar versión y
probar el endpoint real antes de publicar un contrato.

**Problema crítico:** una petición HTTP puede terminar entregando un job_id mientras
la GPU sigue generando. `inflight=0` o `concurrencyLimit=1` en llama-swap **no**
prueban cola vacía, y `ttl=0` no impide que otro modelo fuerce el swap.
Se requiere un lease de trabajo hasta finalización/cancelación, consultar colas
de ComfyUI/ACE/H3 y bloquear tanto cambios desde el panel como clientes directos.
Opciones: adaptador que mantenga la petición viva hasta completar, o coordinador
con admisión y reservas; no basta añadir un botón al catálogo actual.

La infraestructura local tampoco está preparada automáticamente:

- `runtime.py` solo construye Gufo textual; añadir launchers multimodales estrictos,
  no flags arbitrarios ni reutilizar un perfil de LLM como si sirviera imagen.
- ComfyUI posee una unidad/manual GPU lease separado; no añadir un segundo dueño
  `comfyui_auto` sin migrar ciclo de vida y paradas. Primero conservarlo independiente.
- `control.http` lee hasta 2 MB y trata resultados como JSON/texto: **no sirve como
  cliente multimedia general**. Hace falta streaming binario, límites y descarga privada.
- El Caddy público solo permite rutas de texto/modelos: imagen/audio/vídeo dan 403.
  Añadir exclusivamente rutas revisadas; no abrir `/upstream/*` genérico al exterior.
- Catálogo debe mostrar modalidad, resolución/frames/duración, batch, jobs activos,
  formato, licencia y memoria observada; “tokens/slots” no basta para vídeo/audio.

## Convivencia y plan de prueba

- Un único motor GPU activo: Halogen **o** Gufo texto **o** imagen/vídeo/música/TTS GPU.
- Laya y Kokoro CPU pueden proponerse como persistentes no exclusivos, con cuotas
  propias, sin prometer rendimiento simultáneo antes de medirlo.
- TTS GPU junto a Halogen requiere una prueba de memoria específica. No lo habilitaría
  inicialmente: un asistente hablado podría usar Kokoro CPU mientras el LLM genera.
- No hay pipeline automático entre texto, imagen, vídeo y voz en el repo actual.

POC recomendado: Kokoro CPU (español corto/largo) y Qwen TTS CustomVoice o VoiceDesign
(10–20 s); imagen 1024² batch 1; Wan5B/LTX clip corto 480p antes de 720p; ACE-Step
30 s instrumental antes de canción larga/LM. Son presupuestos de prueba propuestos,
no límites nativos garantizados. Medir carga fría, tres repeticiones calientes,
RTF o tiempo completo, memoria/PSI, calidad y restauración del modelo anterior.
Probar fallo/cancelación y no perder trabajo al cambiar modelo.

Clonación de voz solo con consentimiento y derechos; no confundir licencia de
código con derechos sobre voces, música o retratos. Hunyuan tiene exclusiones
territoriales; Qwen-Image-2.1 es no comercial; LTX/Stable Audio/MiniMax requieren
revisar sus textos propios. No convertir `license: other` en permiso comercial.

## Fuentes y trazabilidad

Revisiones de investigación (no nuevos pins desplegados): Gufo
`b93bd5cff2196deeae51e4df8a9d31550acdeada`; toolbox
`7e77f04c2926153fdb7265752192a1029503149f`; ACE-Step
`ca1e85fe9430179831e6bc6be790c332190a3866`; Kokoro-FastAPI
`b4ef64b1ce60682debda4fe0a066259e284eb1b4`. HEAD cambió durante la consulta Gufo;
las métricas se atribuyen a sus páginas de benchmark, no al digest local instalado.

- [Gufo API](https://github.com/gufo-org/gufo/blob/main/docs/SERVER.md),
  [TTS](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3-tts/README.md),
  [benchmarks TTS](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3-tts/BENCHMARKS.md),
  [Image](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen-image-2.1/README.md),
  [benchmarks Image](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen-image-2.1/BENCHMARKS.md),
  [H3](https://github.com/gufo-org/gufo/blob/main/docs/models/minimax-h3/BENCHMARKS.md).
- [llama-swap](https://github.com/mostlygeek/llama-swap), código `internal/server/server.go`,
  `internal/server/api.go`, `internal/config/model_config.go`, ref v255.
- [Toolbox](https://github.com/kyuz0/amd-strix-halo-comfyui-toolboxes),
  [benchmarks](https://kyuz0.github.io/amd-strix-halo-comfyui-toolboxes/).
- [FLUX klein](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B),
  [Z-Image](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo),
  [Wan5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B),
  [LTX2.3](https://huggingface.co/Lightricks/LTX-2.3),
  [licencia Hunyuan](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE).
- [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp),
  [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI),
  [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M),
  [Qwen TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice).
- [ACE-Step](https://github.com/ace-step/ACE-Step-1.5),
  [AMD ACE-Step](https://www.amd.com/en/blogs/2026/commercial-grade-ai-music-generation-on-amd-ryzen-ai-and-radeon-ace-step-1-5.html),
  [Stable Audio](https://huggingface.co/stabilityai/stable-audio-open-1.0),
  [Stable Audio Small](https://huggingface.co/stabilityai/stable-audio-open-small).
