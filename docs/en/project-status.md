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
| 2026-09-15 | **Real trial, restored (not promoted)** | Full Qwen3.8-Flash-Next N1-N4 matrix (64K/slot, `--no-kv-unified`) loaded, served inference and restored Coder+Qwen3.8-27B with byte-for-byte verification. `qwen4exp` architecture support confirmed by source inspection on the live build `b10723@010be9683` (upstream PR #27742), but without PR #27941's fixes. See [Qwen3.8-Flash-Next trials](qwen38-flash-next-trials.md). Does not close the 403 or the SSE incident; not a permanent health claim or a resident-model promotion. |
| 2026-09-15 | **Long trial approved, not executed** | The "sweet spot" long-context trial (8K/16K/32K/~60K, N1 control vs N2/N3) was approved that same day but **never ran**: 0 requests, blocked by SSH/ControlMaster transport to the remote runner, not by the model. See [Qwen3.8-Flash-Next trials](qwen38-flash-next-trials.md), section 7, item 6. |
| 2026-09-16 | **Dated trial, confounded (not causal, not promoted)** | Q4_K_M offload comparison (`--cpu-moe` all-CPU baseline vs `--n-cpu-moe 40`, one valid barrier round of N=2 concurrent requests per profile, ctx 131072/parallel 2): `n-cpu-moe 40` showed -16.1% mean client wall latency and +1.85% mean decode tok/s, but a concurrently active managed `UD-IQ4_XS` download (started, not completed) and unmatched completion-token counts confound the sample; not a causal speedup claim. 4 prior same-day requests hit a 32-token cap (inconclusive, not an unsupported-model finding); a `--n-cpu-moe 32` candidate profile (4 further planned requests) was left untested after an SSH transport failure, not "32 requests not run" (that 32 was the `--n-cpu-moe` flag value, not a request count). Model: Bartowski `Qwen3.8-Flash-Next-GGUF-Q4_K_M` (public catalog: [bartowski/Qwen3.8-Flash-Next-GGUF](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF)). See [Qwen3.8-Flash-Next trials](qwen38-flash-next-trials.md), section 8. |
| 2026-09-16T12:42:05Z–12:44:03Z (~118s) | **Dated trial, executed successfully (not a robust winner, not promoted)** | Later, separate attempt at the baseline/`--n-cpu-moe 32`/`24` sweep noted above as "not executed" that same day: this second attempt ran to completion, 6/6 real requests (2 per profile), with byte-for-byte restore verified. Aggregate throughput (~12.1–12.7 tok/s across profiles) stayed within a similar noise margin; no statistically robust winning profile. Does not conflict with or invalidate the earlier same-day "not executed" row, which documents a separate, prior, blocked attempt. See [Qwen3.8-Flash-Next trials](qwen38-flash-next-trials.md), section 8, dated subsection. |

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
9. Real long context (~60K) and streaming TTFT for Flash-Next; real backend
   overlap (not only client-side concurrent dispatch); sustained soak; tool
   calling/vision; re-evaluation after upstream PR #27941. See
   [Qwen3.8-Flash-Next trials](qwen38-flash-next-trials.md), section 7.

Reuse the baseline only for comparison. Before operating, measure version,
health, catalog, residents/pins, effective options, process arguments, memory,
listeners and active work. Keep backups private and change the host only in an
authorized maintenance window.
