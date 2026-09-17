# Halo Strix Lab

[Espanol](README.md) | **English**

A local LLM inference and training experimentation lab built on **AMD Strix
Halo**: a GMKtec EVO-X2 with 128 GiB of memory, Radeon 8060S graphics and
CachyOS.

This repository brings together configurations, measurements, incident
reports and workspaces for exploring a unified-memory APU with **Lemonade
Server, llama.cpp, Vulkan and ROCm**. Its purpose is to preserve what was
actually tried, explain its limits and help others adapt the work to their
own hardware.

**[English documentation](docs/en/README.md)**
| **[Configuration reference](docs/en/configuration-reference.md)**
| **[Lemonade parameter dictionary](docs/en/lemonade-parameter-reference.md)**
| **[Documentary status](docs/en/project-status.md)**
| **[Setup guide](docs/en/setup-guide.md)**
| **[Parameter profile](config/halo-strix.reference.json)**
| **[Static website / GitHub Pages](site/README.md)**

> **Status: experimental lab.** The historical reference configuration
> dates from **September 4, 2026**, consolidated on September 7. This is not a
> live host audit or a support guarantee for other versions, devices or workloads.

Later operational work is recorded separately in the
[September 10 SSE timeout report](docs/en/lemonade-sse-timeout.md), including
the official Lemonade correction and a reproducible streaming probe. The
[September 15 Qwen3.8-Flash-Next trials](docs/en/qwen38-flash-next-trials.md)
record, separately, a real 64K load/inference/restore matrix for a
previously blocked experimental candidate; it does not close the 403 or the
SSE incident, and it is not a permanent health claim.

## What is included

- CachyOS preparation, hardware inventory and UMA memory configuration.
- llama.cpp Vulkan versus HIP/ROCm comparisons.
- Lemonade operations: an OpenAI-compatible API, resident models, context,
  concurrency and KV cache.
- Docker workspaces for LLaMA-Factory/LlamaBoard and Unsloth Studio, including
  persistent data and operational scripts.
- Diagnostics, recovery and rollback procedures, with measured results and
  explicitly documented gaps.

This is not an automatic server installer or a model distribution. Model
weights, built container images and training data must be obtained or
generated separately.

## Visual website and GitHub Pages

The website includes a bilingual landing page, model profiles, memory
information, training workspaces and a searchable reader with the complete
guides. It needs no backend, CDN or connection to the Halo host; the generated
artifact is one self-contained HTML file.

Follow the [build and deployment guide](site/README.md) to generate
`site/dist/index.html` and enable **Settings > Pages > Source: GitHub Actions**.
The workflow uploads only the generated directory, never the entire checkout
or its ignored private files.

## Reference hardware

| Component | Documented configuration |
| --- | --- |
| System | GMKtec EVO-X2 |
| APU | AMD Ryzen AI Max+ 395, 32 logical CPUs |
| Integrated GPU | Radeon 8060S, `gfx1151` |
| Physical memory | 128 GiB |
| Storage | Nominal 2 TB NVMe, Btrfs root filesystem |
| Operating system | CachyOS |
| BIOS UMA reservation | `UMA_SPECIFIED`, 2 GiB |
| Visible RAM after adjustment | Approximately 123.5 GiB |
| GPU GTT capacity | Approximately 61.73 GiB |

128 GiB of physical memory **does not mean 128 GiB is available to load models
onto the GPU**. Firmware reservations, GTT limits, weights, KV cache and
backend buffers all affect the usable capacity.

Read the [platform and memory setup guide](docs/en/setup-guide.md) before
applying the same settings to different hardware or firmware.

## Inference: Lemonade + llama.cpp

The selected inference path is **llama.cpp with Vulkan/RADV**, managed by
Lemonade Server. HIP/ROCm was evaluated but did not replace Vulkan: in the
recorded short benchmark, prompt processing improved while token generation
regressed. These measurements are not universal performance claims.

Lemonade was documented as a user-level `lemond.service` with `linger`
enabled and **`max_loaded_models=2`**. This setting limits resident models,
not concurrent requests.

### Coder + Thinking profile

| Setting | Coding | Reasoning |
| --- | --- | --- |
| Model | Qwen3-Coder-30B-A3B-Instruct | Qwen3-30B-A3B-Thinking-2507 |
| Weight quantization | `Q4_K_M` | `Q4_K_M` |
| Total context | 196608 tokens | 98304 tokens |
| Slots (`--parallel`) | 3 | 1 |
| K/V cache | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| Flash Attention | Enabled | Enabled |
| Reasoning budget | Not applicable: non-thinking model | 16384 tokens |

With `--kv-unified`, Coder's context is a **shared pool**: 196608 tokens in
total, or approximately 65536 per request if three active slots share it
equally. It is not 196608 tokens per slot. Four slots across the two models
also do not guarantee four efficient simultaneous generations.

The [configuration reference](docs/en/configuration-reference.md) contains
the exact arguments, catalog IDs, model revisions and memory observations.
The [JSON profile](config/halo-strix.reference.json) is for reference and
comparison: **it is not a native Lemonade configuration file and cannot be
imported as a whole**.

### Client connection

For an OpenAI-compatible client, including a configured OpenCode provider,
the reference base URL is:

```text
http://<HALO_HOST>:13305/v1
```

Replace `<HALO_HOST>` with an address in your own environment and select an
exact model ID from the catalog. `GET /api/v1/health` reports health and
loaded models; `GET /v1/models` lists the catalog but does not prove residency.

The historical deployment used plain HTTP on a trusted LAN. **Publishing
this repository does not mean exposing its services to the Internet.**
Configure authentication, TLS and appropriate network controls before
enabling external access.

## New deployment: Halogen 128K and llama-swap

The [September 17 deployment report](docs/en/halogen-128k-deployment.md)
records real GPU/SSE/tool tests, Halogen W4B Quality at 128K, an enabled user
llama-swap service and disabled Lemonade. Coder was tested and removed from
the active catalogue without deleting weights. The private lab uses an
operator-authorized LAN HTTP/no-key exception, not a public default or an
Internet recommendation. Cold boot and additional concurrency remain pending.
The [inference workspace](workspaces/inference/README.en.md) retains safer
public defaults; cloning it does not reproduce private service configuration.
This dated deployment does not overwrite the earlier Lemonade baseline.

## Training: Docker/ROCm workspaces

The training environments are separate from inference. Their scripts do not
stop or reconfigure Lemonade, but concurrent workloads still compete for
GPU, GTT and RAM.

| Workspace | Purpose | Documented status | Default bind |
| --- | --- | --- | --- |
| [LLaMA-Factory / LlamaBoard](workspaces/llama-factory/README.en.md) | Web UI and a BF16 LoRA proof-of-concept template | Configured; end-to-end LLM fine-tuning not validated | `127.0.0.1:7860` |
| [Unsloth Studio](workspaces/unsloth-studio/README.en.md) | Web UI for model experimentation | UI, imports and GPU discovery validated; training pending | `127.0.0.1:8888` |

Each workspace includes a `Dockerfile`, `compose.yaml`, `.env.example`,
build/start/stop/status/log/cleanup scripts and bind-mounted persistence under
`data/`. Read its full English README before building or starting it: the
ROCm/PyTorch bases and constraints differ between environments.

The PyTorch smoke exercise covered FP16/BF16 operations and gradients,
**not a complete LLM training run**. Four-bit QLoRA is unavailable in the
documented Unsloth stack. Base images are pinned by digest and sources by
commit, but builds are not byte-for-byte reproducible; retain built image IDs
when exact image rollback matters.

## Getting started

1. Read the [English documentation](docs/en/README.md) and
   [configuration reference](docs/en/configuration-reference.md) to distinguish
   observations from proposals and unresolved incidents.
2. Compare your hardware, firmware, memory and versions with the inventory.
   Workspace scripts run on Linux with Bash, Docker and Compose v2, with
   access to the documented AMD device nodes.
3. Choose inference or a training workspace. Follow the corresponding guide
   and review prerequisites before modifying the host.
4. Adapt the templates. Placeholders are not executable values; Lemonade
   requires absolute model paths.
5. Check health, memory and resident models first. Schedule loads, restarts
   and generation tests so they do not interrupt other work.

To test an **already installed** Lemonade instance from Windows, use the
[PowerShell smoke-test guide](scripts/README.md). After confirming that the
chosen model is resident, run from the repository root:

```powershell
powershell -File .\scripts\test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

Replace the host and, when necessary, the model ID with your own values.
**This sends a generation request; it is not read-only.** Both `-BaseUrl` and
`-Model` are required, with no host or model default. Choosing a nonresident
model can evict another model. The script does not install Lemonade or
measure model quality or performance.

## Documentation map

| Document | Contents |
| --- | --- |
| [English documentation index](docs/en/README.md) | Workflow coverage and source references |
| [Configuration reference](docs/en/configuration-reference.md) | Parameters, persistence, API operations and limitations |
| [Lemonade parameter dictionary](docs/en/lemonade-parameter-reference.md) | Function, scope, values, interactions, risks and evidence for every configured parameter |
| [Documentary project status](docs/en/project-status.md) | September 4/8/10 chronology, training, tests and pending work |
| [Setup guide](docs/en/setup-guide.md) | Platform preparation, serving, containers and recovery |
| [JSON profile](config/halo-strix.reference.json) | Structured values and provenance |
| [LLaMA-Factory guide](workspaces/llama-factory/README.en.md) | Setup, operation, LoRA preparation, persistence and cleanup |
| [Unsloth Studio guide](workspaces/unsloth-studio/README.en.md) | Setup, GPU access, authentication, operation and rollback |
| [Client script guide](scripts/README.md) | Windows client parameters, behavior and errors |
| [Spanish documentation map](README.md#mapa-de-documentacion) | Original technical reports and incident history |

The English guides cover the documented operational workflows. The original
historical reports remain in Spanish, with private identifiers redacted;
English guides are not line-by-line translations of every diagnostic log.
Historical records preserve superseded decisions and failures. Prefer dated
evidence for the specific topic; an old PASS does not establish current health.

## Limitations and pending work

- The latest HTTP 403 report, dated September 4, 2026, has no confirmed cause
  or resolution in the available evidence.
- End-to-end LLM fine-tuning, sustained stability and real combined
  inference/training workloads still need validation.
- vLLM, HIP inference and the Qwen3.8 candidates are not part of the selected
  profile. Their recorded status describes tested versions, not current
  upstream support.
- Saved Lemonade options and enabled `linger` do not demonstrate automatic
  model preloading after a cold boot.

## Sharing and contributing

Useful comparisons report hardware, versions, model and quantization, total
context, slots, effective arguments, memory and measurement conditions.
Distinguish proposals from applied changes and short smoke tests from
sustained workloads.

Do not contribute passwords, tokens, SSH keys, real `.env` files,
authentication databases or private datasets. Use placeholders and reviewed
`.env.example` templates; check logs and screenshots too.

Public examples replace access details with placeholders. Local agent/editor
configuration, private environment files, credentials, runtime data and model
weights are excluded through `.gitignore` and remain on the local machine.
Installed Squad workflows that depend on local agent state are excluded too.

Publish the reviewed Git file set, **not a ZIP of the entire working folder**,
and do not bypass exclusions with `git add -f`. Review `git status --short`
and `git diff --cached` before each publication. `.gitignore` neither removes
secrets from existing history nor prevents new private values inside otherwise
publishable files.

Third-party models and projects retain their own licenses. Review their
terms before downloading or redistributing weights, images and modifications.
