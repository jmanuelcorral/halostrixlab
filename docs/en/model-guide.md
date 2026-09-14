# Models, concurrency and experimental candidates

[English index](README.md) | [Configuration and exact load requests](configuration-reference.md) |
[Setup and recovery](setup-guide.md) | [Spanish comparison](../comparativa-qwen38-halo-strix.md)

All support statements and measurements are historical, through **2026-09-04**.
No current upstream versions or live host state were queried for this guide.
The positive baseline is **Coder + Thinking, 3+1 slots**, not a proposed
replacement model. The later September 4 HTTP 403 remains unresolved.

## Supported baseline and identity

Keep the documented pair:

- `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`: coding, non-thinking;
  total context **196608**, parallel **3**, dynamically shared KV Q8,
  Flash Attention on, cache reuse **256**.
- `Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M`: reasoning, always-thinking;
  context **98304**, parallel **1**, KV Q8, Flash Attention on,
  reasoning budget **16384**.

Both use Vulkan, `--kv-unified`, and saved load options. See the exact
[payloads and persistence](configuration-reference.md#exact-resident-model-profile)
before acting. Never substitute the built-in Coder ID for the user entry just
because they share the same GGUF. Catalog deletion is not memory unloading.

Two resident models is not two slots. The measured total was 48.02 GiB GTT
of 61.73 GiB, about 1.9 GiB of 2 GiB dedicated VRAM, with neither model pinned.
GGUF file size does not include KV/compute buffers. The final profile is
not evidence that training or a third large model will fit.

## Reasoning and client behavior

`--reasoning-format` controls parsing/formatting, not whether the model thinks:

| Mode in the documented binary | Output handling |
| --- | --- |
| `none` | Thought text stays unparsed in `message.content` |
| `deepseek` | Thought text is extracted to `message.reasoning_content` |
| `deepseek-legacy` | Preserves think tags in content and also supplies reasoning content |
| `auto` | Default parser selection; does not enable/disable reasoning |

Coder's official template is non-thinking; Thinking-2507 always reasons.
A reasoning budget is neither a context size nor an agent-step limit.
Inspect `finish_reason` (`stop`, `length`, `tool_calls`) and actual tool calls,
not only response text.

For OpenCode, configure a compatible provider with baseURL
`http://<HALO_HOST>:13305/v1` and the exact catalog ID. No previously applied
local OpenCode configuration was demonstrated. Historical guidance suggested
`steps >= 50` or no explicit step cap for long agent tasks, with observable
completion criteria rather than a turn count. This is a recommendation, not
measured throughput. Do not invent `max_tokens` as an agent-level
`AgentConfig` field; output/thinking options belong to the appropriate
provider/model contract and must be checked against that client version.

## Cache and concurrency

The unified context is a shared pool: Coder's approximately **65536 tokens
per request** under three active requests is 196608/3, not an independently
reserved limit for every slot. KV cache quantization does not quantize model
weights again. No final explicit prompt-cache or RAM-cache setting is
documented beyond the exact flags.

HTTP keep-alive does not own the KV cache. The reported approximately 99%
prefix reuse and seven-request/four-slot queue were from an earlier setup,
not a performance result for the final pair. A single-model proposal from
September 3 is also superseded.

The runbook's conservative operating recommendation is at most **three
active requests combined**. An earlier interactive-code recommendation used
two real independent agents, contexts up to 32k, compaction around 24k and
small 64-128-token outputs. Neither recommendation configures an automatic
server limit. Validate concurrency using N=1/N=2/N=4 with a barrier, identical
work, TTFT, wall-clock, HTTP errors, tokens/s, memory and internal slot/metrics
correlation in an idle window. Logical decode overlap is not proof of physical
GPU parallelism or latency improvement.

## Qwen3.8-27B: unpromoted candidate

Historical candidate: `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, snapshot
`4ca720788d1e01f1bff70c033e0d0028fd02e502`.
Weights were 17559178144 bytes (16.35 GiB) plus a 931146432-byte BF16 vision
projector (0.87 GiB), approximately **17.22 GiB total**.
The recorded architectures were GGUF `qwen35` and HF
`Qwen3_5ForConditionalGeneration` / `qwen3_5`, dense 27B with an additional
MTP layer. Its template supported tools, vision and request-configurable
thinking, unlike always-thinking Thinking-2507. Native context was listed as
262144 with a larger YaRN extension; that is not a validated local runtime budget.

**Loading history is contradictory:** the later comparison found no load in
the journal evidence it consulted, while an earlier Lemonade concurrency
diagnosis identifies this model as loaded. Preserve both facts about the
documents; do not claim either stable support or "never executed" as settled.

No direct local benchmark establishes superiority over either baseline model.
The historical upstream issue
[#27431](https://github.com/ggml-org/llama.cpp/issues/27431) reported a
long-prompt Vulkan/AMD crash on different discrete hardware/Windows and a
related dynamic quantization. It is a risk signal, not proof of a Strix Halo
failure. PR [#28102](https://github.com/ggml-org/llama.cpp/pull/28102) concerned
CUDA/HIP `gfx1201`, not a Vulkan `gfx1151` fix.

### Proposed isolated POC, not executed as a validated procedure

Only with separate approval, backups, idle state and a current compatibility
review: temporarily replace **Thinking only**, preserve Coder, retain the
two-model limit and explicitly unload Thinking by its exact ID. Do not delete
its disk artifacts. The historical candidate load body was:

```json
{
  "model_name": "Qwen3.8-27B-GGUF-UD-Q4_K_XL",
  "ctx_size": 32768,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384",
  "merge_args": true,
  "save_options": false
}
```

Use the confirmed listener's `POST /api/v1/load`, with its supported origin
contract. This is not part of baseline restoration. Because merge precedence
is incompletely documented, verify resolved/effective options, including any
previously retained flags.

Test in order: a short prompt (~2k), medium (~8k), long (~32k within the
**total** context/output budget), one complete tool-call/result cycle, a
simple vision input using `mmproj-BF16.gguf`, then one representative
end-to-end coding task. Record GTT/VRAM, prompt/generation rate, HTTP/errors,
output correctness and any `device lost`. All six gates must pass without
OOM/crash and with manual quality review; tokens/s alone is insufficient.
Abort and restore Thinking on any failure. A GitHub PR URL was the historical
example completion criterion, not authorization to publish a PR.

## Qwen3.8-Flash-Next: blocked experimental path

Historical artifact: `unsloth/Qwen3.8-Flash-Next-GGUF:UD-Q4_K_XL`,
snapshot `178b998806b7b406c311a3e6174aa99cf6304eaf`.
Four shards plus vision projector occupied about **104.53 GiB**:
103.68 GiB weights + 0.845 GiB projector. The recorded architecture was
`qwen4exp`, with 125B main parameters/6B active per token plus n-gram
embedding/MTP components. Active parameters do not determine total residency.

Managed **b10375** failed with
`unknown model architecture: 'qwen4exp'`. It predates base-support PR
[#27742](https://github.com/ggml-org/llama.cpp/pull/27742) and follow-up
[#27941](https://github.com/ggml-org/llama.cpp/pull/27941), recorded as merged
2026-09-01. Follow-up fixes included sequence/KV indexing, image blocks and
long-context failure paths. Do not mistake a later support claim for a locally
validated upgrade.

The footprint exceeds approximately 61.73 GiB GTT. A future isolated
experiment would require verified newer architecture support, a reviewed
CPU/GPU split or partial offload, no other large resident model, one slot and
an initial 16k-32k context. The historical proposal omitted `--kv-unified`
initially to isolate related behavior, then required memory, correctness,
tools, vision and sustained-stability gates before any promotion.
No complete validated offload recipe is available; **do not invent one**.
Do not run this experiment in the service hosting Coder/Thinking or alongside
the Qwen3.8-27B evaluation.

Supplier benchmark claims compared Flash-Next with Qwen3.8-27B, **not** the
resident pair, and were not reproduced locally:

| Benchmark | Flash-Next | Qwen3.8-27B |
| --- | ---: | ---: |
| Toolathlon Verified | 73.5 | 67.1 |
| SWE-bench Pro | 62.5 | 61.7 |
| Multilingual software engineering | 81.0 | 73.8 |
| DeepSWE 1.1 | 58.7 | 42.2 |

Community ranges of 17-21 tok/s without speculative decoding and 24-47 with
experimental MTP/ROCm forks are unverified reports on other stacks, not
Vulkan baseline results or a performance promise.

## vLLM and return to baseline

The integrated historical report describes a vLLM **0.20.1 / ROCm 7.12 /
Torch 2.10** attempt using `Qwen3.6-27B-FP16-vLLM`: weights loaded, then native
hybrid-architecture initialization segfaulted. The report ruled out OOM and
corrupt download for that attempt, but a public independently reproducible
diagnostic is missing. A newer prerelease bundle was considered, not promoted.
GGUF remained experimental; AWQ/GPTQ support on this APU was unvalidated.
Potential batching/TTFT benefits are hypotheses, not measured decode gains.

For an authorized return from any experiment: inspect active work and
`max_loaded_models`, unload only the exact experimental ID through
`POST /api/v1/unload`, then restore both baseline load requests. Confirm
health, GPU backend, resolved contexts/arguments, expected GTT and a
resident-model smoke. Do not change drivers/runtimes, delete shared models
or load a third large model as part of that recovery.

## Sources

The [historical comparison](../comparativa-qwen38-halo-strix.md), sections
3-10, contains the identities, observations, supplier claims and POC plans.
The [Lemonade validation](../validacion-lemonade-vulkan.md) contains the
contradictory earlier loading/concurrency observation and catalog incidents.
The [integrated historical setup](../setup-completo-halo-strix.md), sections
9-11 and 16, preserves the vLLM/cache summaries. No private artifacts are
needed to read these conclusions, and no unresolved point is promoted to fact.
