# Docker runtimes, toolboxes, Lemonade and Halogen

[English index](README.md) |
[Full research report and source register (Spanish)](../investigacion-docker-toolboxes-halogen.md)

**Research date: 2026-09-16. Proposal only, not a deployment or live Halo audit.**
Public documentation and selected source files were inspected. No GPU workload,
container, image download, weight download or host configuration change was
performed. No real environment files or private agent state were read.
Local documentation tests do not validate inference or hardware support.

This is an English operational summary. The Spanish report contains the full
comparison, migration stages, acceptance matrix and revision-pinned sources.
The historical September 4 baseline and later incidents remain separate.

## Recommendation

Use independent Docker runtime images with persistent model storage, and
**evaluate llama-swap as the initial LLM gateway and lifecycle owner**.
Keep Lemonade as a transitional service or an alternative, rather than a
mandatory hop in front of every runtime. Use AI Toolbox Cockpit for manual
experiments, not to manage containers already owned by the permanent service.

For a single Halo, start with one large profile active at a time. Halogen,
large DS4, training and heavy ComfyUI workloads should be mutually exclusive
until measured coexistence is established. Docker isolates userspace, not the
shared GPU, GTT, RAM or memory bandwidth.

```text
Coding agents / IDE
        |
Authenticated stable /v1 entry
        |
llama-swap + explicit lifecycle/resource policy
        |
        +-- Docker: llama.cpp Vulkan / Coder
        +-- Docker: llama.cpp ROCm and specialized forks
        +-- Docker: vLLM
        +-- Docker: Halogen (all, or engine + api)

Persistent read-only model mounts; separate writable caches.
ComfyUI and training retain their native APIs/job contracts.
```

## Toolboxes already contain API servers

| Project | Published serving interface | Important distinction |
| --- | --- | --- |
| llama.cpp toolboxes | `llama-server`, API Server Mode and Router Mode | The inspected Vulkan image defaults to a shell; override its command for serving |
| vLLM toolboxes | OpenAI-compatible server, `start-vllm` recipe helper | Preserve model-specific parsers, dtype, attention and AITER settings |
| DS4 toolbox | `ds4-server`, OpenAI chat/completions/models and Anthropic-compatible Messages | The reviewed toolbox documents a serial graph worker, not batching |
| ComfyUI toolboxes | ComfyUI server and API-format workflows | Native workflow API is not automatically OpenAI Chat or Images |
| Fine-tuning toolbox | Jupyter and notebooks | A training job environment, not an OpenAI inference server |
| AI Toolbox Cockpit | Interactive control of Docker/Podman servers | A TUI, not an always-on HTTP gateway |

Toolbx/Distrobox containers are unrelated to LLM **tool calling**. The model
returns structured tool requests; the coding agent executes them with its own
permissions. Do not mount development repositories, SSH keys or the Docker
socket into inference servers merely to support tool calls.

The reviewed toolboxes list Vulkan RADV, ROCm 10.0, TheRock and specialized
Flash-Next/EngramHalo/ROCmFPX builds. Some are experimental or manual-build
channels. The vLLM README explicitly separates its current Ubuntu image from
historical benchmarks. Published image names do not establish registry
availability or local model compatibility. Resolve a digest before testing.

Cockpit already integrates Halogen, including HGN bundles, optional vision,
read-only mounts and separate context/pool/slot controls. Its inspected
integration is still marked experimental, follows `latest` with
`--pull=always`, and launches foreground servers until Ctrl+C. File-size
validation is not checksum verification. Do not mistake that workflow for a
pinned, offline, automatically recovered deployment.

## Can Lemonade be the frontend?

There are three materially different designs:

1. **Lemonade inside Docker:** officially documented, with persistent volumes,
   an unprivileged user and GPU passthrough. This contains Lemonade and its
   managed backends; it does not automatically orchestrate sibling toolboxes.
2. **Lemonade HTTP relay:** the experimental `cloud` backend can target an
   OpenAI-compatible base URL. Local HTTP requires an explicit insecure-HTTP
   opt-in. The mechanism exists in inspected `v11.9.0`, not only `main`.
3. **Executable wrapper:** the repository's
   [experimental EngramHalo wrapper](../../scripts/engramhalo/README.md) maps a
   narrow `llama-server` command contract to Docker. It is not deployed or GPU
   validated, and is not a general adapter for Halogen.

Source-verified relay limitations:

- A provider key is mandatory even for model discovery. The upstream key is
  distinct from the key protecting Lemonade itself. Do not use a dummy token
  as evidence of authentication at an otherwise unauthenticated backend.
- `CloudServer::load()` records state and `unload()` clears it; neither stops
  external containers or frees their model memory. Local residency limits
  cannot enforce the external GPU budget.
- **Non-streaming Responses is explicitly unsupported** by
  `CloudServer::responses()` in `v11.9.0` and the inspected `main`.
  This is not a blanket claim about streaming: `Router::responses_stream()`
  in inspected `main` uses generic forwarding to `/v1/responses`. Both paths
  and error/cancellation behavior need independent end-to-end tests.
- The relay rewrites model IDs and may add token-budget aliases and streaming
  usage requests. It is not an entirely byte-transparent transport.
- Discovery can omit unavailable providers. A stopped backend is not a
  persistent profile catalog simply because Lemonade can query `/v1/models`.

Verdict: viable as a **Chat Completions relay POC** with external lifecycle
management, not yet a safe universal frontend assumption for Halogen/Codex.
The `system` llama.cpp backend means a local executable, not an arbitrary URL.

## Why llama-swap first, rather than LiteLLM?

llama-swap documents `cmd`/`cmdStop` for Docker/Podman, `checkEndpoint`,
`useModelName`, TTL, unload timeouts, groups/matrix coexistence and native
Chat/Responses routing. It directly addresses the single-machine swapping
problem. This is published support, not a locally tested Halogen integration.

Its limitations matter: gateway `/health` does not prove backend health; keys
have no per-user roles; passthrough probes may load models; concurrency limits
can return 429 rather than queue; startup feedback can inject reasoning text.
Do not configure independent automatic restarts against the lifecycle owner's
intentional unloads.

LiteLLM is an alternative when virtual keys, multiple users, quotas, remote
providers or broader gateway policy justify additional components. It still
needs a separate mechanism to start/stop Docker workloads and enforce memory
exclusion. Neither a reverse proxy nor Compose profiles alone schedule GPU RAM.

**Initial deployment choice:** a small host-side controller with Docker
runtimes avoids putting the daemon socket inside a public-facing container.
It is not fully containerized, and rootful Docker authority remains effectively
root authority. If everything must be containerized, initially use a gateway
without the socket and manually selected Compose profiles, or build a private
allowlisted controller. That separation is additional integration, not a
built-in distributed control API supplied by llama-swap. A read-only socket
mount does not make the Docker API read-only.

## Halogen findings

The inspected README advertises image `0.11.1`, specialized for native Linux,
`gfx1151` and Qwen3.8-Flash-Next. WSL2 `/dev/dxg` is unsupported. Kernel 7.0 is
the oldest reported working version, not a bisected compatibility boundary.

- API: `/v1/models`, Chat, Completions and Responses, streaming and non-streaming,
  tools, reasoning, `/health` and `/metrics`.
- Responses has no response store, retrieval by ID or `previous_response_id`.
  Send conversation history. Cancellation is by disconnect, including
  non-streaming since 0.10.2; verify the gateway propagates it.
- Vision is optional via a sidecar. It accepts data URLs/base64, not remote
  HTTP(S) image URLs. It reads images, not generates them.
- Structured output is a **subset** of JSON Schema: some numeric constraints
  are accepted without enforcement, `oneOf` behaves as `anyOf`, and schemas
  with sampling or images are restricted. Always validate client-side.
- The engine is closed-source under its own EULA. The inspected terms permit
  free commercial/production use and unmodified redistribution with notices,
  but restrict redistribution of modified images. Weights are separately
  licensed; this is not legal advice.

### Container topology and security

Use the default single-container entrypoint for an initial POC. The supplied
split Compose has `engine` and `api`, both requiring the same image version.
Only the engine needs GPU devices. Its unauthenticated protocol on 8730 must
never be published; API 8731 should remain on loopback/private networking.

The upstream Compose uses Podman's `keep-groups`, which Docker does not
support; resolve host device GIDs. Engine `ipc: host` is a documented measured
requirement, not replaced by `shm_size` in upstream tests. Unlimited memlock is
also specified. Do not automatically add privileged mode or unconfined seccomp;
Halogen removed the latter as unnecessary in its tested setup.

Readiness uses engine PING/PONG, not only TCP connection success. The split
API waits for engine health. The example grants 20 minutes of startup grace
and 60 seconds of stop grace. Apply API sampling/policy variables to the API
service when split, not only to the engine.

**Source inconsistency:** Compose comments mention different slot/pool defaults
from README/FLAGS and entrypoint. The inspected entrypoint defaults to four
slots and a pool of twice request context. Verify actual image logs/health
rather than copying those comments.

### Weights and memory

The native HGN quality bundle occupies about 118 GiB on disk. The alternative
GGUF path supports particular tensor formats, with Unsloth `UD-IQ4_XS` as its
measured example, plus Halogen's own approximately 1.4 GiB MTP head and tokenizer.
It does **not** accept arbitrary GGUFs: K-quants and `UD-Q4_K_XL` are refused.
Do not propose the lab's Bartowski Q4_K_M trial artifact as interchangeable.
The lab's mentioned IQ4_XS download was not established as complete.

Persistent GGUF repacking optionally consumes roughly another 70 GiB of disk
and requires write access. Prepare downloads separately; serve read-only with
`HALOGEN_DOWNLOAD` unset. The no-telemetry/no-outbound statement is upstream's
claim, not an independent binary/network audit.

The historical Halo profile has approximately **61.73 GiB GTT**, whereas the
Halogen reference host describes GTT/TTM near 124 GiB and dedicated-machine
operation. This is a real preflight gap; Docker cannot fix it. Halogen reports
roughly 68 GiB resident HGN weights or 72 GiB for its measured GGUF, plus pools,
buffers and disk-backed lookup-table pressure. These are not total memory
budgets or guarantees of fit. `MemAvailable` can overstate reclaimable memory
according to upstream's locked-weight explanation.

`HALOGEN_CTX` limits a request; `HALOGEN_KV_POOL_POSITIONS` sizes shared
capacity; `HALOGEN_KV_SLOTS` controls concurrency. Lowering slots alone does not
proportionally reduce pool allocation. `HALOGEN_MAX_TOK` controls a prefill
arena, not the output-token budget. Reasoning consumes generation budget.

Do not automatically copy the toolboxes' or Halogen's host-tuning instructions.
Disabling IOMMU removes DMA isolation and NPU support; large GTT limits need
host-specific memory margins. No kernel/firmware/device-permission changes
were authorized or performed in this study.

Published performance, including approximately 1424 prefill tok/s and 41.7
served decode tok/s in one 32K/256-token case, is vendor evidence under its
own version, power envelope and IOMMU settings. It is not a local benchmark,
a matched comparison of all competitors or a coding-quality guarantee.

## Migration and acceptance gates

1. Capture actual host state and a private rollback snapshot in a later
   authorized session. Restore that snapshot, not an obsolete historical pair.
2. Test Coder directly in one pinned Vulkan image, initially 16K-32K context
   and one concurrent request. Confirm GPU offload, tools, SSE and clean stop.
3. Add the gateway, alias mapping, authentication, backend readiness and
   explicit lifecycle. Keep the old service/port unchanged until cutover.
4. Evaluate Halogen alone after checking memory, kernel, license and complete
   compatible artifacts. Test directly first, then through the gateway.
5. Add ROCm forks/vLLM and other workloads only after measured exclusion and
   recovery. Promote profiles based on repeated coding tasks, not tokens/s alone.

Acceptance covers both Chat and Responses with/without streaming; multi-round
call/result tools; client-side JSON validation; disconnects during prefill and
decode; real 2K/8K/32K then 64K input; matched concurrency 1/2/4; cold/warm cache;
OOM and wedged engine handling; memory release; admin/API isolation; restart and
cold boot. Separate queue delay, load time, SSE heartbeat and first content token.

The full report records 12 primary source groups with commit IDs, detected
contradictions, storage/security requirements and explicit unverified claims.
No production-ready Compose is claimed: this task documents the architecture
and research, rather than deploying untested GPU recipes.
