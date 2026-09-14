# Lemonade public parameter dictionary

[Project status](project-status.md) |
[Referencia en español](../referencia-parametros-lemonade.md) |
[Configuration reference](configuration-reference.md) |
[Documentary JSON](../../config/halo-strix.reference.json)

This guide is the English operational equivalent of the Spanish parameter
dictionary. It explains the meaning, scope, documented values and risks of
every Lemonade/llama.cpp setting used by the lab. **It is not a live host dump,
an importable configuration or a current-health statement.**

## Evidence labels

- **2026-09-04 BASELINE:** Lemonade 11.8.1, managed llama.cpp Vulkan b10375,
  Coder `ctx_size=196608`/`parallel=3`, Thinking
  `ctx_size=98304`/`parallel=1`, `max_loaded_models=2`, both unpinned, and
  approximately 48.02 GiB combined GTT.
- **DATED LIVE OBSERVATION:** an operational reading on its stated date, not now.
- **CONFIGURED:** a saved value or documented recipe.
- **RECOMMENDATION:** an unproven future/transient action.
- **PENDING:** unresolved semantics, precedence or outcome.

Context and reasoning budgets use **tokens**; `global_timeout` uses **seconds**;
ports are TCP numbers. llama.cpp flag behavior is build-dependent, so compare
resolved options with the actual managed process.

## Identity, loading and persistence

| Parameter | Function and scope | Documented value(s) | Interaction / risk | Evidence |
| --- | --- | --- | --- | --- |
| `model_name` | Exact Lemonade catalog ID selected by a load/chat request. | Baseline Coder and Thinking-2507; later Qwen3.8-27B observations. | A display name or checkpoint is not necessarily the operational ID. `user.*` and built-in entries may share a GGUF without being aliases. A nonresident ID can auto-load and trigger LRU. | Baseline; dated live observations. |
| checkpoint / variant | Weight source plus variant/weight quantization, such as `repo:Q4_K_M`. | Coder and Thinking `Q4_K_M`; Qwen3.8 candidate `UD-Q4_K_XL`. | Weight quantization is distinct from KV quantization. Downloaded/listed does not mean loaded or supported. | Historical documents; Qwen3.8 contradiction retained. |
| `ctx_size` | Total backend context/KV capacity, in tokens. | Baseline 196608/98304. Qwen3.8 saved options showed 262144 on September 10; the restored incident profile records 65536. Failed transient recommendation: 32768. | With `--kv-unified`, slots share one total pool. Prompt, template, reasoning and output all consume it. Larger contexts increase memory and prefill cost. | Baseline; dated/documentary observations; failed recommendation. |
| `llamacpp_backend` | Selects Lemonade's managed llama.cpp backend family. | `vulkan`. | Changes binary, compatibility, memory and performance. The historical HIP result did not promote HIP. | Baseline. |
| `llamacpp_args` | Per-model string of additional llama-server flags. | Exact baseline and Qwen3.8 strings below. | May interact with global defaults and saved options. Duplicate/conflicting flags require effective-option/process inspection. | Configured; full precedence pending. |
| `merge_args` | Requests argument merging rather than assuming full replacement. | `true` in baseline/restored profiles; `false` in the failed transient Qwen3.8 recommendation. | Exact merge order and duplicate handling are not established. `false` does not independently prove that every default vanished. | Configured; semantics pending. |
| `save_options` | Requests persistence of model options. | `true` in baseline; `false` for transient trials. | Persistence does not preload on boot and may overwrite a useful recipe. The exact per-model storage file is unknown. | Configured; storage/precedence pending. |
| `pinned` | Protects a resident model from normal eviction, subject to version behavior. | Baseline: both false. September 8: Coder+Phi false. September 10: Coder+Thinking true; downloaded Qwen3.8 false. | Pinning creates no memory. At capacity it may block a load or leave the unpinned model as the eviction target. Not `pinned_helper_models`. | Dated observations, not current state. |
| `max_loaded_models` | Global resident-LLM count, not slots or requests. | `2`. | A third requested model can trigger LRU. On September 8, a Phi-4-mini request loaded Phi and evicted Thinking; the initiating client is unknown. | Baseline and dated live observations. |

Baseline Coder:

```text
--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0
```

Baseline Thinking-2507:

```text
--parallel 1 --kv-unified --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384
```

## Context, concurrency, cache and attention

| Parameter | Function and scope | Documented value(s) | Interaction / risk | Evidence |
| --- | --- | --- | --- | --- |
| `--parallel` | Logical request slots in one model backend. | Coder 3; Thinking and Qwen3.8 1. | Does not guarantee physical scaling. Slots compete for KV and compute. | Baseline/dated. |
| `--kv-unified` | Enables a unified dynamically shared KV pool. | Enabled for both baseline models. | `ctx_size` is not independently allocated per slot. Distribution is not guaranteed equal/fixed. | Baseline. |
| `--flash-attn` | Enables/disables Flash Attention kernels. | `on`. | Benefit and compatibility depend on GPU, backend, KV types and build. Validate. | Baseline/later recipes. |
| `--cache-reuse` | llama.cpp prefix-KV reuse threshold/size. | `256`, Coder only. | Not HTTP keep-alive or a generic RAM cache. Do not transfer it to other models without measurement. | Baseline. |
| `--cache-type-k` | Key-cache quantization. | `q8_0`. | Saves KV memory but may affect quality/performance; does not alter model weights. | Baseline/later profile. |
| `--cache-type-v` | Value-cache quantization. | `q8_0`. | Same cautions; backend combinations may have constraints. | Baseline/later profile. |
| `--spec-type` | Selects speculative decoding mode. | `none` in the restored Qwen3.8 recipe and failed transient recommendation. | Do not combine casually with saved `draft-mtp` defaults; isolate and verify effective options. | September 10 documentary/live evidence; validation pending. |

The historical “at most three combined active requests” guidance is an
operator recommendation, not a configured server limit. N=1/N=2/N=4,
slot-correlated concurrency and soak remain pending.

## Reasoning, sampling and templates

| Parameter | Function and scope | Documented value(s) | Interaction / risk | Evidence |
| --- | --- | --- | --- | --- |
| `--reasoning` | Enables/disables a model/template reasoning path when supported. | `on` for Qwen3.8; Coder is non-thinking; Thinking-2507 is always-thinking. | Not universally honored. Consumes context/output and differs from `reasoning_format`. | Baseline identity; September 10 profile. |
| `--reasoning-budget` | Reasoning token budget. | Thinking 16384; restored Qwen3.8 4096; failed recommendation 8192. | Counts inside total context and may consume visible output allowance. Not agent steps. | Baseline/documentary/recommendation. |
| `--temp` | Sampling temperature, dimensionless. | Restored Qwen3.8 `1.0`. | Works jointly with top-p/top-k/min-p; one value does not define sampling. | Documentary September 10. |
| `--top-p` | Nucleus probability mass, normally 0–1. | `0.95`. | Interacts with other filters; overly low values may damage output. | Documentary September 10. |
| `--top-k` | Keeps K highest-probability candidates. | `20`. | Meaning of zero is version-dependent; verify. | Documentary September 10. |
| `--min-p` | Relative minimum-probability filter. | `0.0`. | Usually disables the filter; verify build semantics. | Documentary September 10. |
| `--repeat-penalty` | Dimensionless repetition penalty. | `1.0`. | Usually neutral. Higher values can harm code and structured repetition. | Documentary September 10. |
| `--chat-template-kwargs` | Literal JSON passed to the chat template. | Qwen3.8 `{"reasoning_effort":"medium","preserve_thinking":true}`; SSE probe uses per-request `{"enable_thinking":false}`. | Paste literal JSON in a UI; escape it once when nesting in an API JSON payload. Unknown keys are template-dependent. | Documentary profile and probe contract. |
| `reasoning_effort` | Template/model effort level, not a universal llama.cpp flag. | Saved `medium`; SSE probe `none`. | Only works if the template implements it; does not replace a reasoning budget. | September 10/probe. |
| `preserve_thinking` | Requests preservation of thinking according to the template/output contract. | `true` in documented Qwen3.8 defaults. | May expose/retain reasoning; inspect both `content` and `reasoning_content`. | Dated/documentary September 10. |
| `reasoning_format` | Selects reasoning parsing/output formatting. | Default `auto`; historical modes `none`, `deepseek`, `deepseek-legacy`, `auto`. | **Does not enable reasoning.** It changes response-field treatment and client compatibility. | Baseline/build documentation. |

Restored Qwen3.8 incident profile:

```text
--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --spec-type none --reasoning on --reasoning-budget 4096 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --chat-template-kwargs '{"reasoning_effort":"medium","preserve_thinking":true}'
```

## Service, network, paths and timeout

| Parameter | Function and scope | Documented value(s) | Interaction / risk | Evidence |
| --- | --- | --- | --- | --- |
| `host` | Lemonade public listener address. | `<HALO_HOST>`, an operator-authorized specific address. | Loopback limits access; wildcard broadens exposure. The historical CLI tried localhost while the service used a LAN bind. | Baseline. |
| `port` | Public TCP port. | `13305`. | Must align with firewall, clients and CORS origin. Not an internal backend port. | Baseline. |
| `broadcast` | Controls service announcement/discovery. | `false`. | Reduces discovery but is not authentication or a firewall. | Baseline. |
| CORS / `LEMONADE_ALLOWED_ORIGINS` | Allowed browser origins: scheme+host+port, no API path. | Historically `http://<HALO_HOST>:13305`; comma-separated. The 11.9.0 report records migration to `allowed_origins`. | Avoid wildcard substitution. Unconfigured origins may receive 403. CORS does not authenticate non-browser clients. Environment changes require restart. | Baseline and September 10 repository record. |
| `models_dir` | Absolute managed-download directory. | `$HOME/ai/lemonade/models`, expanded privately. | Literal `~` was historically misresolved. Different from `extra_models_dir`. | Configured. |
| `extra_models_dir` | Recursive local-GGUF discovery root. | `$HOME/ai/models/smoke`, expanded privately. | Changes catalog discovery/collisions; 11.9.0 changed reserved-directory behavior. | Configured/version-dependent. |
| `global_timeout` | Global server timeout in seconds. | `1200` persisted according to the September 10 maintenance report. | In 11.8.1 it did not govern the fixed 120-second streaming low-speed branch. The report says 11.9.0 makes streaming honor it. It does not change client/proxy timeouts or prefill speed. | Later repository record; an earlier session checkpoint said 11.9.0 was only prepared, and this task did not independently corroborate installation. |

## Managed flags, listeners and endpoints

Lemonade historically created loopback llama-server listeners at
`127.0.0.1:8001` and `127.0.0.1:8002`; auxiliary port `9000` was also observed.
These are dated internal assignments, not stable public endpoints. Read
`backend_url` from health rather than assuming a port.

- Managed `--jinja` enables Jinja chat-template processing; the effective
  template affects tokenization, tools and reasoning.
- Managed `--metrics` exposes backend metrics on the internal listener; it
  does not prove remote publication, monitoring or access controls.
- Lemonade also supplies `-m`, `--ctx-size` and `--port`; do not duplicate them
  blindly in `llamacpp_args`.

| Method/path | Meaning | Risk/status |
| --- | --- | --- |
| `GET /` | Integrated Web App / Model Manager. | Working HTML does not prove a ready backend. |
| `GET /api/v1/health` | Service, residents, backend and recipe state. | Check status/readiness/activity; a dated result is not current health. |
| `GET /v1/models` | OpenAI-compatible catalog. | Listed/downloaded does not mean resident. |
| `GET /v1/models/<ID>/options` | Resolved model options. | Historically verified; recheck version compatibility. |
| `GET /internal/config` | Effective global configuration. | Internal/version-dependent; do not publish full dumps. |
| `GET /api/v1/downloads` | Download jobs. | Do not disrupt active downloads. |
| `POST /internal/set` | Mutates global settings. | Back up and verify persistence. |
| `POST /api/v1/load` | Loads/configures a model. | May persist, consume memory and evict another model. |
| `POST /v1/chat/completions` | OpenAI-compatible inference/SSE. | May auto-load and trigger LRU. |
| Backend `/tokenize`, `/props`, `/slots` | Native resident llama-server routes. | Use only the observed host-side `backend_url`; they are not `/v1` routes. |

## Dated chronology

1. **September 4 baseline:** Coder+Thinking-2507, 3+1 slots, about 48.02 GiB
   GTT, both unpinned, Lemonade 11.8.1/b10375.
2. **Later September 4:** HTTP 403 reported without a known route, client,
   cause or confirmed resolution.
3. **September 8 live observation:** a Phi-4-mini request auto-loaded Phi and
   LRU-evicted Thinking at the two-model limit. Coder+Phi remained unpinned.
   The initiating client was not identified.
4. **September 10 live observation:** still 11.8.1; Coder+Thinking were
   resident, ready and pinned; max LLM 2. Qwen3.8 was downloaded/unpinned with
   saved `ctx_size=262144`, `merge_args=true`, sampling, `preserve_thinking`,
   `draft-mtp` and `parallel=1` defaults.
5. **Failed September 10 recommendation:** transient Qwen3.8 at 32768 context,
   Vulkan, one slot, Flash Attention, Q8 KV, no speculative decoding, reasoning
   on/budget 8192, explicit sampling, `preserve_thinking`, `merge_args=false`,
   `save_options=false`. The user reported load failure; cause/restoration were
   not closed. **This is not a valid recipe.**
6. **Later repository record:** the SSE reports state that 11.9.0/b10723 was
   installed, profiles restored, `global_timeout=1200`, and two long probes
   passed. Available session history also has an earlier checkpoint where
   11.9.0 was prepared but not installed. Without independent corroboration in
   this documentation task, preserve both provenances and invent no resolution.

Before reuse, verify versions, health, exact IDs, residents/pins, resolved
options, actual process arguments, context/slots, memory, CORS and active work.
Pending: full precedence and per-model storage, cold boot/preload, TLS, the 403,
concurrency/soak, real LLM training and vLLM validation.
