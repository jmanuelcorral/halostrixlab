# Image, video and audio generation on Strix Halo through llama-swap

[Español and complete source list](../investigacion-multimedia-halo.md) |
[Index](README.md) | [Inference](../../workspaces/inference/README.en.md)

## Scope and recommendations

Primary-source research, not a deployment or a new inference benchmark. Reviewed
llama-swap v255 source and upstream documentation available in September 2026.
No models were downloaded; no services, GPU settings, kernel or BIOS were changed.
The pinned local Gufo image's help was inspected without GPU devices.

llama-swap routes requests and manages processes; it does not generate media.
Each candidate needs a compatible backend and lifecycle policy. Generic ROCm
support is not evidence of gfx1151-specific optimization or local performance.

Recommended order:

1. Kokoro-82M CPU for speech alongside a GPU LLM without swapping the GPU.
2. Qwen3-TTS 12Hz 1.7B through Gufo for expressive/designed voices, one variant first.
3. Keep existing Qwen Image 2512/Edit 2511 in ComfyUI; test FLUX.2-klein-4B or
   Z-Image-Turbo for lighter image workloads. Gufo Qwen-Image-2.1 offers a direct
   Images API but its weights have a non-commercial research license.
4. Video: start with Wan2.2-TI2V-5B or LTX-2.3 distilled through ComfyUI and a
   job-aware adapter. Do not promise complete video generation in seconds.
5. Music: ACE-Step 1.5 2B turbo, PyTorch ROCm, initially without its optional LM
   or with a small LM. Test bounded instrumentals before long songs.

## Candidate matrix

B means 10^9 parameters. Checkpoint storage is not runtime RAM/GPU demand.

| Use | Model / proposed backend | Evidence and cost | Recommendation |
| --- | --- | --- | --- |
| Existing images/editing | Qwen Image 2512 / Edit 2511, ComfyUI | Image generated locally; Edit weights/graphs validated; operator reported iris-color drift | Retain; graph validity does not prove likeness |
| Fast images | FLUX.2-klein-4B, ComfyUI or stable-diffusion.cpp Vulkan | Apache-2.0, nominal 4B; main weights 7.75 GB, encoder 8.04 GB, VAE 0.168 GB in inspected files | Compact POC; no local Vulkan-vs-HIP winner established |
| Fast images | Z-Image-Turbo, ComfyUI or stable-diffusion.cpp | Apache-2.0, 6B family, distilled few-step recipe | Candidate, not a verified Halo latency claim |
| Image API | Qwen-Image-2.1, Gufo native HIP | Documented ~33.1 GB BF16 download, Qwen3-VL encoder and RGBA VAE | Direct Images API, but non-commercial Qwen Research License |
| Initial video | Wan2.2-TI2V-5B, ComfyUI | Apache-2.0, 5B dense; inspected official files ~20.00 GB DiT + 11.36 GB encoder + 2.82 GB VAE | Smaller main-model POC; generic support is not Halo measurement |
| Video + audio | LTX-2.3 22B distilled, ComfyUI | Halo toolbox recipe; distilled checkpoint ~46.15 GB plus recipe-specific encoder/components | Promising audiovisual option, proprietary LTX terms |
| Heavier video | Wan2.2 A14B, ComfyUI | Halo four-step recipe, high/low-noise experts | Second phase; active parameters alone do not establish memory fit |
| Alternative video | HunyuanVideo1.5, ComfyUI | Halo 720p/four-step recipe and historical complete runs | License excludes EU, UK and South Korea; not recommended there without additional rights |
| Experimental video | MiniMax H3, Gufo | Native gfx1151, reviewed text-only FL2VA path, phased loading | Not first choice; complete qualified benchmark missing |
| Efficient speech | Kokoro-82M, Kokoro-FastAPI CPU | Apache-2.0, 0.082B, 327 MB main weights plus voices, Spanish available | Best LLM coexistence candidate; measure CPU RTF locally |
| Expressive speech | Qwen3-TTS 12Hz 1.7B, Gufo | Native gfx1151 BF16; Apache-2.0 model; CustomVoice 3.833 GB + audio tokenizer 0.682 GB | GPU exclusive initially; LLM slots do not imply TTS batching |
| Music/songs | ACE-Step1.5 turbo, PyTorch ROCm API | MIT; 2B DiT or 4B XL, optional 0.6/1.7/4B LM; AMD Ryzen AI Max+ evidence | Preferred music POC, job lifecycle integration required |
| Effects/ambience | Stable Audio Open, ComfyUI | Small up to 11 s, 1.0 up to 47 s stereo; specific Stability license | Exploratory, no verified Halo benchmark found |

Official repositories can contain FP32 weights, duplicate formats and alternative
checkpoints. Do not infer disk size from parameters multiplied by two bytes.
For example, inspected Z-Image transformer shards total ~24.62 GB; that is not
measured BF16 runtime memory. Avoid downloading both FLUX monolithic and Diffusers
copies. Build a pinned file manifest before downloading any candidate.

## What the performance evidence actually says

### Gufo

Gufo targets Linux gfx1151 with native HIP kernels. The local pinned image lists
image/video/TTS/ASR subcommands, but help is not a model execution test. Current
upstream documentation is newer than the installed 9cad139 executable.

- Qwen3-TTS upstream: 5.12 seconds of audio produced in 2.018 s CustomVoice,
  2.024 s VoiceDesign or 2.234 s Base ICL. Resident models, 64 frames, median of
  three requests after warmup. First PCM ~0.201 s or ~0.345 s Base. Two queued
  requests finish ~2.025/4.046 s: serial execution, not two-slot batching.
  Spanish is supported by the original model, but Gufo multilingual/long-form
  quality is still unqualified. Test actual Spanish pronunciation and prosody.
- Qwen-Image-2.1: 1024-square **two-step** development control takes ~5.838 s.
  Normal 40-step generation benchmark is TODO. Do not call this six-second
  production-quality generation. Readiness can be metadata-only, with deferred
  loading on the first request. Separate masks and `input_fidelity` are unsupported,
  so it does not automatically fix portrait identity drift.
- MiniMax H3: 91 s is **one denoiser evaluation**, all 50 blocks at 1344×768×124,
  not a finished video. The exact schedule requires 49 evaluations and subsequent
  decoding. The 40.01 GiB retained peak applies only to that component control.
  Phase inventory includes ~62.13 GiB encoder, 24.35 GiB precompute, 37.38 GiB
  core plus VAEs; these are neither simultaneous residency nor a minimal download
  manifest. Complete-generation performance and quality remain pending.

### Halo ComfyUI toolbox

Includes Qwen Image/Edit, Wan2.2, HunyuanVideo1.5, LTX-2.3 and H3. New GGUF recipes
are explicitly described as development-channel work pending hardware validation.
BF16 is LTX-2.3's default because gfx1151 supports native BF16 matrix operations;
FP8 is not automatically faster.

Public JSON contains LTX2-T2V-BF16 ~615 s, Hunyuan T2V ~929 s and Wan2.2 T2V A14B
~2007 s, cold rows with warm_run_seconds=0. The LTX2 timestamp is **2026-02-13**,
not December. The rows do not establish exact weights/image/resolution/frame
identity; use them only as a warning that video can take minutes, not a quality
comparison or a benchmark attributed to **LTX-2.3**. January Wan records exceed
8300 s, illustrating strong environment/configuration sensitivity.

Do not copy upstream `--gpu-only`: it already caused a local BF16 LoRA OOM.
Preserve reviewed CPU offload/reserve settings. Do not apply gfx1100 overrides,
BIOS/GTT changes or another Radeon model's variables as universal optimizations.

### ACE-Step and Kokoro

AMD reports ~1.8x generation-vs-listening speed on Ryzen AI Max+, versus ~4x on
R9700. Text lacks enough configuration detail for a precise local latency promise.
ACE-Step's async API, PyTorch `pt` backend and soundfile fallback need a dedicated
ROCm deployment; generic ROCm6 documentation does not qualify gfx1151 or justify
downgrading the existing environment.

Kokoro's published CPU latency comes from other CPUs. Measure local RTF, first
chunk and competition with Laya. CPU-only does not mean free shared RAM/bandwidth.

## Exact llama-swap v255 integration boundaries

Verified in `internal/server/server.go` at v255:

| Endpoint | Gateway support |
| --- | --- |
| POST /v1/images/generations | JSON model dispatch |
| POST /v1/images/edits | Multipart model dispatch |
| POST /v1/audio/speech | JSON model dispatch, binary/stream-capable client needed |
| POST /v1/audio/transcriptions | Multipart; recognition, not generation |
| GET /v1/audio/voices | Query model selection |
| /v1/videos and job-specific queries | Not native model-dispatch routes in v255; passthrough/adapter required |
| /upstream/ALIAS/... | Generic forwarding, not contract conversion or automatic result-URL rewriting |
| /comfyui/... | Special fixed comfyui_auto integration, not configured in our deployment |

Gufo Image and TTS are the direct integrations. ComfyUI uses prompt/history/view/
queue/WebSocket rather than the Images API. ACE-Step uses release_task,
query_result and v1/audio?path=... . Result URLs need rewriting or explicit
adapter retrieval. Test binary WAV/MP4 integrity, multipart, cancellation and
range downloads. Old Gufo help and new docs differ on video paths; pin and test
the actual executable before publishing an API contract.

**Async job hazard:** HTTP can finish with a job ID while the GPU keeps running.
An empty gateway inflight list or concurrencyLimit=1 does not prove an empty
backend queue. ttl=0 does not prevent another model forcing a swap. Hold a
job-lifetime lease and check backend queues; block switches from both panel and
direct clients. Use a synchronous completion adapter or a coordinator with
admission/reservations, not merely another catalog button.

Local integration work still required:

- runtime.py currently constructs text-only Gufo commands. Add strict modality
  launchers rather than arbitrary flags or pretending a text profile serves images.
- ComfyUI has a separate manual unit/GPU lease. Do not introduce a competing
  comfyui_auto owner without deliberately migrating lifecycle/stop behavior.
- control.http reads at most 2 MB and treats responses as JSON/text; it is not a
  general media client. Add bounded binary streaming and private output storage.
- Public Caddy allowlists only text/model routes; multimedia returns 403 there.
  Add reviewed paths, never blanket public upstream access.
- Catalog metadata must include modality, resolution/frames/duration, batch,
  active jobs, format, license and measured memory. Tokens/slots are insufficient.

## Coexistence and proposed qualification

One GPU owner initially: Halogen or Gufo text or image/video/music/GPU TTS.
Laya and Kokoro CPU can be proposed as persistent nonexclusive workers with
quotas, subject to measured shared-memory/bandwidth impact. Do not initially
co-load GPU TTS with Halogen; CPU TTS enables spoken answers without GPU swapping.
No automatic text/image/video/voice pipeline exists in this repository.

POC budgets, not claimed native limits: Kokoro Spanish short/long speech; Qwen TTS
CustomVoice or VoiceDesign 10–20 s; images 1024-square batch1; Wan5B/LTX short
480p clip before 720p; ACE-Step 30 s instrumental before long songs/optional LM.
Measure cold loading, three warm runs, RTF or full latency, memory/PSI, output
quality, cancellation/failure and restoration. Do not lose async jobs on switching.
Voice cloning requires consent and rights. Code licenses do not grant rights to
voices, music or likenesses. Review Hunyuan territorial exclusions, Qwen Image2.1
non-commercial terms and LTX/Stable Audio/MiniMax specific licenses.

## Source revisions

Research refs, not deployed upgrades: Gufo b93bd5cff2196deeae51e4df8a9d31550acdeada;
toolbox 7e77f04c2926153fdb7265752192a1029503149f;
ACE-Step ca1e85fe9430179831e6bc6be790c332190a3866;
Kokoro-FastAPI b4ef64b1ce60682debda4fe0a066259e284eb1b4; llama-swap v255.
Gufo HEAD moved during research; upstream benchmark claims are not observations
of our installed image. The [Spanish report](../investigacion-multimedia-halo.md#fuentes-y-trazabilidad)
contains primary repository, model-card, benchmark and license links.
