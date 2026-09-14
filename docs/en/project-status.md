# Documentary project status

[Lemonade parameter dictionary](lemonade-parameter-reference.md) |
[Resumen en español](../estado-proyecto.md) |
[English index](README.md)

**Documentary cutoff: 2026-09-10. This is not live monitoring or a host audit.**
The reusable baseline remains dated September 4; later events do not overwrite it.

## Public material

- Bilingual READMEs, Spanish technical reports and English operational guides.
- A documentary, non-importable JSON profile.
- OpenAI/PowerShell smoke and Python/SSE probe with bounded contracts.
- A bilingual self-contained static site, builder and regression tests.
- Docker/ROCm workspaces for LLaMA-Factory/LlamaBoard and Unsloth Studio.

The site builder recursively discovers Markdown under `docs/` and `workspaces/`,
so these guides are included without a manual document list.

## Dated inference record

| Date | Evidence class | Record |
| --- | --- | --- |
| 2026-09-04 | **Positive historical baseline** | Lemonade 11.8.1, llama.cpp Vulkan b10375; Coder 196608/3 and Thinking-2507 98304/1; two unpinned residents; ~48.02 GiB combined GTT. |
| Later 2026-09-04 | **Open incident** | HTTP 403 with no known endpoint, client, cause or confirmed closure. |
| 2026-09-08 | **Dated live observation** | A Phi-4-mini request auto-loaded Phi and LRU-evicted Thinking at `max_loaded_models=2`. Coder+Phi remained unpinned; initiating client unknown. |
| 2026-09-10 | **Dated live observation** | Still 11.8.1. Coder+Thinking were resident, ready and pinned; max LLM 2. Qwen3.8-27B was downloaded/unpinned with saved 262144 context and other defaults. |
| 2026-09-10 | **Unvalidated recommendation** | A transient Qwen3.8 32768-context load failed according to the user. Cause and restoration were not closed; do not promote the recipe. |
| Later repository record | **Documentary evidence incompatible with an earlier checkpoint** | SSE reports state that 11.9.0/b10723 was installed, `global_timeout=1200`, profiles restored and two long probes passed. The earlier available checkpoint said prepared/not installed. This documentation task did not independently audit the host, so both provenances remain. |

## Training/workspace status

| Area | Documented result | Not demonstrated |
| --- | --- | --- |
| ROCm tensor smoke | Historical finite FP16/BF16 operations and backward pass. | LLM fine-tuning, long stability or quality. |
| LLaMA-Factory | Configured workspace and BF16 LoRA template. | End-to-end training or LlamaBoard GPU validation. |
| Unsloth Studio | Build, imports, GPU, health and SPA validated on September 1. | LLM training; documented stack lacked 4-bit QLoRA. |
| vLLM | Historical attempt/investigation retained. | Promoted or reusable validated backend. |

Only reviewed `.env.example` files are public templates. No real `.env`,
datasets, models, credentials or authentication databases were read.

## Test contracts

- `scripts/test-lemonade.ps1` requires `-BaseUrl` and `-Model`, performs
  discovery and one non-streaming chat request, and can trigger auto-load/LRU.
- `scripts/test-lemonade-sse.py` requires an origin without `/v1`, an exact
  already-resident model, ready backend and idle state. Its long gate requires
  model content after 130 seconds plus `READY`, `stop` and `[DONE]`.
- Offline fixtures use loopback only and require no Halo host, GPU or secrets.

## Explicit pending work

1. Cause/closure of the historical 403.
2. Old-source contradiction between Qwen3.8 “loaded” and “never loaded”.
3. Full global/model/request precedence, duplicate flags and per-model storage.
4. Cold boot and automatic preload.
5. TLS, authentication/proxy and exposure policy.
6. N=1/N=2/N=4 concurrency, soak, cancellation and memory pressure.
7. Real LLM fine-tuning and coexistence with inference.
8. Current reproducible vLLM validation.

Reuse the baseline only for comparison. Before operating, measure version,
health, catalog, residents/pins, effective options, process arguments, memory,
listeners and active work. Keep backups private and change the host only in an
authorized maintenance window.
