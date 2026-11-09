# Winnow and Ollaya behind the existing llama-swap

[Español](../investigacion-winnow-ollaya.md) | [Documentation index](README.md)

## Recommendation, September 28, 2026

Later update: [authorized deployment and CPU trials](../../workspaces/inference/OLLAYA.en.md).
The following preserves the earlier research, not current deployment state.

**Use Ollaya CPU in Docker for an initial functional Winnow-12B trial**, retaining
one existing llama-swap gateway and lifecycle owner. E4B is a smaller alternative,
not the same model. Neither reviewed distribution provides a qualified AMD
gfx1151 deployment; GPU acceleration would be a separate engineering phase.

This is source, manifest and remote metadata research, not local inference.
No weights or Docker layers were downloaded, no images built, and no services,
gateway configuration or GPU devices changed. The following is a proposal,
not permission to deploy or a record of completed deployment.

## Comparison

| Aspect | Native Winnow | Ollaya 0.7.5 | Existing Laya |
| --- | --- | --- | --- |
| Model | Winnow-12B, fine-tuned Gemma 4 12B IT | Explicit `winnow:12b` and `winnow:e4b` | Laya multilingual, approximately 322M parameters |
| Text weights | Q8_0, 12.670 GB | Same 12B Q8; E4B Q8, 8.005 GB | 0.644 GB checkpoint |
| CPU serving | Decision engine requires a GPU; CPU builds are not serving support | Explicit CPU llama.cpp runner | Existing CPU service |
| AMD gfx1151 | No reviewed HIP/Vulkan serving profile or AMD Docker image | No shipped HIP backend; Vulkan not shipped | No GPU needed |
| Docker | NVIDIA CUDA Dockerfile; upstream did not validate GPU inference inside Docker | Published CPU image, plus CUDA 12/13 variants | Keep existing deployment |
| API | Decisions, chat/SSE, vision and inspection | Decisions, not chat or Winnow's image extension | Typed decisions |
| Context | Upstream qualified CUDA 64K profile, not on Halo | 8192 tokens, state budget 6144 | Service `max_len=1024` |
| Optimizations | Selected-logit head and question branches | Full head, sequential questions, shared prefix | Small specialized encoder |

Sizes are decimal GB, not RAM/VRAM estimates. KV, buffers and activations cost
additional memory. Native 12B's projector adds 175.116 MB, totaling 12.845 GB.
Neither projector nor BF16 weights is needed for the initial CPU trial.

### Exact identity and artifact availability

Ollaya's 12B manifest and the native runtime pin different HF revisions but the
**same Q8 file**: 12,669,646,592 bytes, SHA-256:

```text
b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea
```

HF API LFS metadata confirms both revisions without downloading weights. The
native revision's card and NOTICE still claim weights are pending: stale release
text, not missing artifacts. A complete local checksum remains mandatory after
any future download. E4B is a different 8,005,437,472-byte model with different
prompt/calibration settings. Select explicit model tags, never infer identity
from the homepage or `latest`.

Reviewed Winnow weights and Ollaya declare Apache-2.0; the native Winnow runtime
is MIT. Preserve LICENSE, NOTICE and dependency notices in deployment artifacts.

### What Ollaya does and does not solve

Ollaya reproduces Winnow's prompt and reads logits through stock llama.cpp b11146
libraries. It does not run Winnow's patched server, so its CPU route bypasses
that engine's GPU requirement. It does not retain every optimization or semantic:
Ollaya recomputes confidence using its own rule; 12B uses T=1 and E4B a fitted
temperature around 1.2574. Conditional option probabilities are not universally
calibrated correctness estimates for our workload.

Configuration accepts only `auto`, `cpu`, `cuda`, `cuda:N` and `metal`. Linux
packages contain no HIP backend. Overriding libraries is not a supported AMD
recipe: ABI checks and new backend/parity validation apply. Upstream withheld
Vulkan after 501/505 matching decisions on RTX 4090 Windows. This is not an
AMD failure result, but rules out presenting Vulkan as a proven drop-in option.

The native launcher hardcodes `CUDA0` outside macOS and its build script exposes
only CUDA/Metal/CPU. A HIP port needs build flags, dependencies, device selection
and runtime packaging changes, not merely access to `/dev/kfd`.

### Performance and quality evidence

Ollaya reports median runner-only latency for five short questions of 154 ms
for 12B and 96 ms for E4B on RTX 4090; E4B takes 5.1 s on a 24-core x86 CPU.
**These are not Halo measurements.** Documented CPU parity covers E4B, 505/505;
12B CPU is explicitly not run. CPU execution exists in code, but loading and
measuring 12B here is an acceptance gate, not a completed validation.

Native Winnow reports 85.71% on the public JevBench subset, but 70.00% teacher
agreement on typed-decisions versus 76.75% for Laya Typed Decisions. That Laya
variant is not our multilingual model. No universal winner or fair local A/B
has been established; native CUDA latency and historical local Laya timings
are not directly comparable.

## Proposed deployment stages

### 1. Isolated, reproducible preparation

- Keep artifacts and evidence under ignored workspace `data/winnow/`.
- Pin the published 0.7.5 linux/amd64 CPU image, not `latest`:

```text
ghcr.io/ollaya-dev/ollaya@sha256:3fb6a50039bd97147e131844c21401f2b01aa648cd3749d4c8d8773f5f200fb5
```

- Its remote manifest exists and lists 65,501,633 compressed layer bytes. This is
  neither unpacked size nor an execution test. Initially reserve 20-25 GB disk
  for 12B, image and headroom, excluding build caches. Both models would total
  20.675 GB of weights before other storage.
- Download and verify weights, manifests and licenses in a separate preparation
  step. No client-triggered inference-time pulls. Do not duplicate Laya or enable
  Ollaya's automatic Laya router.

### 2. CPU trial container

- Non-root, no GPU devices or Docker socket, capabilities dropped,
  `no-new-privileges`, read-only root and bounded tmpfs. Identify necessary store
  writes and keep prepared weights immutable.
- Initial proposed limits: 8 CPUs, 32 GiB RAM, one active request. These are trial
  limits, not measured usage or guaranteed fit. Check available unified memory
  and existing workloads before starting.
- Set `OLLAYA_DEVICE=cpu`, `OLLAYA_MAX_LOADED_MODELS=1`, `OLLAYA_MAX_QUEUE=1`,
  `OLLAYA_KEEP_ALIVE=-1`. Keep stock 8192 context and 6144 state budget.
- Install/admit only `winnow:12b`. E4B is a separate deliberate trial when smaller
  downloads and prior CPU evidence matter, never a silent model substitution.
- Run supervised `ollaya serve`, without a host daemon, installer or independent
  Docker restart policy. Keep-alive retains the runner only while the container
  lives; llama-swap decides when to stop the backend.

### 3. Integrate with the one existing gateway

Proposed decision contract:

```text
Client -> existing llama-swap
       -> /upstream/winnow-12b-cpu/v1/systemone
       -> restricted adapter -> Ollaya CPU
```

- Use passthrough, not an assumed global model-dispatch `/v1/systemone` route.
  The adapter fixes/validates `model=winnow:12b`; gateway alias and backend model
  name differ.
- The adapter belongs to the backend, not a second gateway. Admit only fixed-model
  decisions and controlled readiness. Ollaya binds container-internal loopback;
  publish only the adapter on a verified free host loopback port. Do not expose
  pull/create/delete/copy through generic upstream forwarding. Add backend
  authentication where appropriate.
- Preload and complete a bounded synthetic decision before reporting readiness.
  Ollaya's `/` only establishes daemon responsiveness.
- Use a separate non-exclusive CPU group, concurrency 1 and bounded loading.
  Recalculate global concurrency without weakening existing Laya/Halogen/Gufo
  contracts. CPU isolation does not eliminate RAM or memory-bandwidth contention.
- Review Caddy for the exact decision route and method if external access is
  needed; never open `/upstream/*`. Preserve existing access policy.
- Gateway changes require an authorized maintenance window: inspect active config,
  drain, stop, acquire settings lease, back up, validate and atomically replace.
  Stopping the gateway unloads Laya and any resident GPU model too.
- Do not interrupt ComfyUI for research or preparation. If integrated tests need
  other stacks stopped under existing guards, defer them to an approved window
  rather than bypassing those guards.
- Halo Control uses a fixed catalog/selection map: explicitly add metadata,
  supervised actions, compatibility and tests if panel control is desired.
  A fourth configured model will not automatically become a working catalog card.

### 4. Acceptance gates and rollback

1. Pinned image/model, full hashes, non-root startup and verified CPU execution.
2. `noul`, `choice`, `score`, Spanish, Unicode, structured state, confidence
   semantics, option/context limits and truncation. Ollaya's SystemOne route
   returns an error for truncated state.
3. Invalid requests, authentication, body limits, saturation, timeout,
   cancellation and drained shutdown. Do not assume native and Ollaya error
   codes are identical.
4. Cold/warm latency, p50/p95, peak memory and CPU pressure. Compare against our
   Laya multilingual on held-out Spanish data fitting both services; evaluate
   long contexts separately. Fit calibration on data separate from final tests.
5. Gateway start/stop without orphan runners, remote downloads, exposed admin
   routes or Laya changes. Test GPU-engine coexistence only after preflight and
   a combined memory budget.
6. Stop rather than promote if load, correctness or latency gates fail. Retain
   private evidence and restore the validated gateway backup in maintenance;
   do not delete existing weights/data or present partial results as success.

### 5. Optional AMD GPU engineering phase

If CPU is adequate to evaluate quality but not latency, investigate a ROCm/HIP
image targeting gfx1151. Native Winnow is the more faithful candidate when chat,
vision and its optimizations matter, at the cost of maintaining a port. Start
text-only, 8K, one HTTP request and one decision branch, progressing to
16K/32K/64K and vision only after correctness and memory checks. Question branches
are not HTTP slots.

Require build/unit checks, explicit gfx1151 detection without CPU fallback,
selected/full-head and reference/optimized parity, cancellation and real model
switching. Use Halogen/Gufo's exclusive GPU group and respect ComfyUI/training
leases. Do not promise latency or change BIOS/GTT to force a pass. Ollaya HIP
would be another experimental port, not a switch enabled by its current image.

## Sources and pins

- [Winnow inference](https://github.com/EldanRing/winnow-inference),
  `77d14580c6732ca2f3745750c1dc1fd446d8bcee`: Dockerfile, runtime.lock.json,
  manifests/models.json, native/engine.h, scripts/build.py, scripts/serve.py,
  docs/API.md, docs/VALIDATION.md and docs/BENCHMARKS.md.
- [Ollaya](https://github.com/ollaya-dev/ollaya),
  `f42c89eb7436cfd0f02c582b54b182727118e438`: Dockerfile, registry/v2/library/winnow,
  docs/families/winnow.md, docs/distribution.md, scripts/llama-cpp.sh,
  server/config/http/scheduler and runner/llama sources. Release 0.7.5:
  `32acb6d2ea13f616b1e11d9dfb8260b305106847`; tree comparison changes only
  CLAUDE.md, not the reviewed components.
- HF `EldanRing/Winnow-12B`: native revision
  `b2b14213dfa252e6d6b543c8b334762e51772d29`, Ollaya revision
  `b6ac22b0d51b69b18200acacb3fbdd98073fffe8`; LFS metadata cross-checked.
- HF `EldanRing/Winnow-E4B`, Ollaya manifest revision:
  `734302fe5fbfeb3f21a7ece62653c9539be4aaf3`.
- [Local llama-swap routes and limits](multimedia-halo-research.md),
  Laya testing, and
  [catalog operations](../../workspaces/halo-control/README.en.md).
