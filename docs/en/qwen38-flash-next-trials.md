# Qwen3.8-Flash-Next trials: the 64K N1-N4 matrix (2026-09-15)

[Versión en español](../ensayos-qwen38-flash-next.md) |
[English index](README.md) |
[Model guide](model-guide.md) |
[Project status](project-status.md) |
[JSON profile](../../config/halo-strix.reference.json)

**Provenance:** a sanitized operational session record plus measurement
artifacts (`result.json`, `summary.json`, the run's `checkpoint.json`), not a
fresh audit performed while writing this document. All numbers quoted here
come from those specific runs dated **2026-09-15** (real active window
`07:26:12Z`-`07:35:25Z`, ~9m13s) and from prior dated research findings.
Nothing here is a host health check at the time of reading.

This is a **dated, additive** report: it does not replace or contradict the
[positive 2026-09-04 baseline](configuration-reference.md) (Coder + Thinking,
3+1 slots), does not close the [open 2026-09-04 HTTP 403](project-status.md),
and does not close the [September 10 SSE incident](lemonade-sse-timeout.md).
It is a new, separate evidence line about an experimental candidate already
catalogued as blocked (`Qwen3.8-Flash-Next`, `qwen4exp` architecture), moving
it from "unsupported by the old build" to "loaded and answered successfully
under bounded conditions" — without implying full validation or promotion to
a permanent resident model.

## What changed relative to previously documented status

| Aspect | Documented status through 2026-09-10 | New 2026-09-15 observation |
| --- | --- | --- |
| `qwen4exp` architecture support | Rejected by the managed `b10375` build (`unknown model architecture: 'qwen4exp'`) | The later live managed build `b10723@010be9683` **does** include the base upstream support (PR #27742), confirmed by source inspection, not just an announced version string |
| Actually running a load | No successful load on record | Four profiles (`N1..N4`) loaded, served real inference and were restored correctly |
| Known architecture risks | No local data | Upstream fix PR #27941 (seq_cp, block keying, M-RoPE, one CUDA abort case) is **not** included in the live build; mitigated by avoiding the unified KV pool, not by an applied patch |

None of this reopens or closes the September 4 403, nor the September 10 SSE
incident; these are parallel evidence lines about different matters.

## 1. Architecture compatibility verified by source inspection

The live managed build at the time of these trials was `llama.cpp` Vulkan
**`b10723`, commit `010be9683`**. This was verified by direct inspection of
the published source (not only from the announced version string):

- **PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742)** (base
  `qwen4exp` architecture support / Qwen3.8-Flash-Next, merged 2026-08-27):
  **included**. The file `src/models/qwen4exp.cpp` exists at commit
  `010be9683` of the repository.
- **PR [#27941](https://github.com/ggml-org/llama.cpp/pull/27941)** (later
  fixes: `seq_cp`/cache indexing, block keying, M-RoPE, one CUDA abort case):
  **NOT included**. An official GitHub API compare between `010be9683` and
  that PR's merge commit (`36b1015...`) confirms the live build is behind
  those eight fix files.

This means: the model **loads and generates** on the live build (base support
present), but **without** the robustness fixes from #27941. The mitigation
identified to operate in this state is `--no-kv-unified` (KV partitioned per
slot instead of a dynamically shared pool), which avoids the known
cross-sequence risk pattern in the unified pool. This is a **mitigation of a
known risk, not a general guarantee of correctness** for an architecture
without its upstream fixes. No local validation was performed for any
adversarial multi-sequence scenario, tool calling, vision input, or
sustained long-context operation under this combination.

## 2. Trial chronology (all dated, none is permanent health)

### 2026-09-14: conservative N1/ctx4096 trial (real, successful)

The first real (not simulated) trial, with **human** authorization recorded
by the coordinator (response "Autorizo este ensayo" quoted from the
approval checkpoint; the coordinator recorded and relayed that
authorization, it did not authorize the trial itself), scoped to: release
the residency (without deleting files) of Coder and Qwen3.8-27B, load
Flash-Next with a conservative profile (`--cpu-moe`,
per-layer embedding pinned to CPU via `--override-tensor
'^per_layer_token_embd[.]weight$=CPU'`, Vulkan, `--mmap`, `f16` KV, one
slot, context 4096), serve two short responses and restore.

- **Load:** 24.1 s, all flags applied exactly as verified in the
  `launch_command` (no `-ngl`/`--n-gpu-layers`, not requested).
- **Test 1** (exact JSON `{"sum":4}`): `finish_reason: stop`, correct
  content. `prompt_ms 8843.7` (no cache, `cache_n=0`), `predicted_ms
  3671.2` (49 tokens, ≈13.35 tok/s), **~12.5 s total wall**.
- **Test 2** (exact `READY`): `finish_reason: stop`, correct content.
  `cache_n 42` (reused cache), `prompt_ms 1591.3`, `predicted_ms 1992.7`
  (32 tokens, ≈16.06 tok/s), **~4.2 s total wall**.
- **Restore:** verified byte-for-byte exact against the saved Coder
  (196608/parallel 3) and Qwen3.8-27B (65536/parallel 1) values,
  `restore_verified_ok: true`.
- No SSE/streaming was tested in this trial (explicitly requested "no SSE
  threshold"); slots 2-4 were not tested; a single N=1/ctx4096 sample does
  not allow inferring a "best configuration".

### 2026-09-14/15: first N1 attempt at 64K within the matrix plan (blocked by an instrumentation bug, NOT a model incompatibility)

This attempt did **not** run the full N1-N4 matrix: it was a reduced
subset, deliberately scoped to a single `N1` profile (`ctx_size 65536`,
`parallel 1`, 300s deadline, one repeat), as the first step within the
approved matrix plan
(`N1..N4`, `ctx_total = 65536×N`, `parallel = N`, with
`--no-kv-unified --cpu-moe --override-tensor
'^per_layer_token_embd[.]weight$=CPU' --cache-type-k f16 --cache-type-v f16
--mmap --spec-type none`) using an automated runner.

- **Preflight:** exact match against the approved snapshot; no drift.
  Unloading both original models: succeeded.
- **Real failure:** when starting the (single) N1 profile, the runner threw
  a Python exception while trying to pass a `Deadline` object (containing a
  `threading.Event`) to a child process via `multiprocessing` on the remote
  **Python 3.14** interpreter: `TypeError: cannot pickle '_thread.lock'
  object`. This is a serialization defect in the test *runner* (objects
  holding locks are not picklable by `multiprocessing` design), **not** a
  model incompatibility, not a Lemonade/llama.cpp backend failure, and not
  an authorization or security-gate failure.
- **Restoration did execute** (the runner's `finally` block) and was
  verified correct by two checks that are independent of each other (the
  runner's own check, plus a separate health query made by the same
  operator after the process finished, without reusing runner-cached data
  — not an audit by a different person): both original models were
  reloaded with arguments byte-for-byte identical to those saved before
  the trial.
- **No latency/token/TPS metrics were obtained** in this attempt: the
  failure occurred before the first real inference HTTP request.
- **Fix actually applied** (not merely proposed): `Deadline.__getstate__`/
  `__setstate__` was implemented so the object serializes only the `float`
  deadline value (the `monotonic()` deadline) when pickled to the child
  process, never transporting the underlying `threading.Event`/`Condition`;
  the child reconstructs the `Deadline` object from that value. It was also
  confirmed that the targets passed to `multiprocessing` (including the
  `Worker`/entry function itself) are importable by name under both the
  `spawn` and `forkserver` start methods (this also fixed the earlier issue
  of invoking the script as a hyphenated module name instead of as the main
  file). **No** switch to `WORKER_MODE="thread"` nor a thread-based
  "fallback" was applied or is claimed as the fix here: that option was
  mentioned only as a hypothetical alternative in the original finding, not
  as what was implemented.

### 2026-09-15: N1 retry with the fix applied (real, successful, independent run)

After applying the fix to the `Deadline` object (verified by security
review, with a conditional GO, against real `spawn` and `forkserver` start
methods), only the **N1 profile** was re-run as a point validation of the
fix, successfully: `status=completed`, `restore_verified_ok: true`. **This
was an independent run**, with its own load time (`load_elapsed_s=3.18`)
and its own two inference rounds (real prompts of `88` and `201` tokens;
`predicted_per_second` of `15.486` and `16.559` tok/s respectively) —
these are **not** the same numbers as the `N1` profile in the full final
matrix of the next section (which has its own load time of `10.40` s and
its own set of 6 rounds). This retry validated only the instrumentation
fix in an isolated N1 cycle; its metrics are not combined or averaged with
the full matrix, which was a later, separate run (see
[section 3](#3-full-n1-n4-matrix-results-2026-09-15)).

### 2026-09-15: full N1-N4 matrix (real, successful, window `07:26:12Z`-`07:35:25Z`)

With the fixed runner, the full four-profile approved matrix was executed
in one continuous run. See [section 3](#3-full-n1-n4-matrix-results-2026-09-15)
for the complete numbers.

## 3. Full N1-N4 matrix results (2026-09-15)

**Configuration common to all four profiles:** Vulkan, `--no-kv-unified`
(KV partitioned per slot, not shared), `--cpu-moe`, `--override-tensor
'^per_layer_token_embd[.]weight$=CPU'` (per-layer embedding pinned to CPU),
`--cache-type-k f16 --cache-type-v f16` (no KV quantization in this trial,
unlike the Coder/Thinking baseline which uses `q8_0`), `--mmap`,
`--spec-type none` (no speculative decoding). `ctx_size` is the **total**
backend context for that profile; with `--no-kv-unified` each slot gets a
fixed partition of **65536 tokens** regardless of `N` (not a dynamic pool
split, unlike the Coder baseline). Each profile ran 3 repeats × 2 fixed
synthetic prompts = 6 inference rounds, with `N` concurrent client-side
requests dispatched per round when `N>1`.

| Profile | Total ctx / slots (parallel) | Load time (s) | Requests OK / planned | `predicted_per_second` per request (server, tok/s): min-mean-max |
| --- | --- | ---: | --- | --- |
| N1 | 65536 / 1 | 10.40 | 6 / 6 | 15.23 - **16.13** - 16.71 |
| N2 | 131072 / 2 | 2.78 | 12 / 12 | 10.87 - **12.38** - 13.31 |
| N3 | 196608 / 3 | 3.08 | 18 / 18 | 8.87 - **10.02** - 11.53 |
| N4 | 262144 / 4 | 3.31 | 24 / 24 | 7.33 - **8.68** - 9.61 |

`predicted_per_second` is the decode throughput reported by the llama.cpp
server itself for **each individual request**
(`server_timings.predicted_per_second`); it is not a client-side aggregate
and does not include prefill/queue time.

All **60 request rounds** (3 repeats × 2 prompts × up to 4 profiles with
different `N`) passed content verification (`content_verified=true`) with
real `finish_reason=stop`, never forcing the token cap. Real prompt tokens
(two fixed short synthetic prompts): range **88-201** tokens. Real
completion tokens (configured cap 256, always stopped for real before that
cap):

| Profile | Completion token range (real) |
| --- | --- |
| N1 | 112-147 |
| N2 | 111-190 |
| N3 | 100-247 |
| N4 | 80-196 |

### Client wall latency per request and per round

| Profile | `wall_s` per request, min-max | `round_wall_s` per round, min-max | Sum of the profile's 6 rounds |
| --- | --- | --- | ---: |
| N1 | 12.235-18.293 | 12.27-18.52 | 84.597 s |
| N2 | 15.357-21.780 | 17.77-22.02 | 115.864 s |
| N3 | 18.729-30.501 | 20.77-30.54 | 161.418 s |
| N4 | 14.285-32.591 | 16.52-32.78 | 139.403 s |

Total duration of the active execution window (all four profiles,
including load/unload and final restore): **≈551.3 s (~9.2 min)**, within a
1800 s budget (~1248.7 s of unused margin remained).

### Weighted aggregate throughput per profile

The correct way to compute an aggregate throughput when rounds have
unequal durations is
`sum(completion_tokens) / sum(round_wall_s)` — **not** multiplying the mean
tokens/s by the request count, nor averaging per-round ratios:

| Profile | Weighted aggregate throughput (tok/s) |
| --- | ---: |
| N1 | 9.27 |
| N2 | 14.17 |
| N3 | 17.24 |
| N4 | 22.22 |

**Explicit interpretation:** wall-clock aggregate throughput grows with `N`
(expected: more concurrent requests per round), but the **per-request**
`predicted_per_second` decreases monotonically from N1 (~16.1 tok/s mean) to
N4 (~8.7 tok/s mean), consistent with shared compute/memory contention
between slots under this `cpu-moe + mmap + Vulkan` configuration. This is a
point-in-time observation of this specific 2026-09-15 run, **not** a
permanent performance baseline or a projection of an optimal value for
other workloads.

The `overlap_label` field distinguishes: N1 was
`client_scheduled_no_overlap_detected`; N2-N4 were
`client_scheduled_overlap`, meaning the **client** dispatched the `N`
requests of each round concurrently. **This does not certify real backend
execution overlap**, only that the client launched them together; the
runner does not instrument the backend to confirm physical compute overlap.

### Resource guards across the whole cycle (275 samples, ~2s interval)

| Metric | Minimum observed | Maximum observed | Configured guard |
| --- | ---: | ---: | ---: |
| Available memory (GiB) | 75.194 | 120.910 | 16.0 |
| Free GTT (GiB) | 16.482 | 61.714 | 4.0 |

No guard tripped at any point (`breach_reason: null`). These are samples
across the **entire process** (all four profiles in sequence, including
intermediate loads/unloads), not a per-profile breakdown nor proof of a
peak Flash-Next-only allocation at full 64K context. CPU and GPU share
unified memory on this device; GPU and system memory cannot be summed as
independent resources.

### Restoration (verified by two checks independent of each other)

1. **The runner itself** (`restore.phase="finally"`,
   `restore.restore_verified_ok=true`, `restore.mismatches=[]`): unloaded
   Flash-Next, confirmed its absence, and reloaded Coder (6.62 s) and
   Qwen3.8-27B (6.78 s) with their saved arguments.
2. **A separate health check**, performed by the same operator after the
   process finished, without reusing runner data: Coder (`pinned=true`,
   `ready`, `ctx_size=196608`, arguments byte-for-byte identical to
   preflight) and Qwen3.8-27B (`pinned=true`, `ready`, `ctx_size=65536`,
   arguments byte-for-byte identical, including the
   `--chat-template-kwargs` block). `pinned_models.llm=2`,
   `max_models.llm=2`, unchanged. Flash-Next absent from residents.

**Restoration conclusion: complete and correct**, confirmed by two checks
that do not share code and match exactly the pre-mutation state.
**Important precision:** both checks were performed by the same operator
in the same session (one from inside the runner, one as a later manual
query); this is not an independent audit by a second person or an external
party, only two separate technical reads that do not share code with each
other.

## 4. Illustrative load-body example (NOT a command executed now)

The following block is a **copyable reference example** of matrix profile
N3 (`196608` total context, 3 slots), as verified in
`effective_llamacpp_args` during the 2026-09-15 trial. **It is not an
automatic HTTP call, must not be pasted against a host without your own
review, and the model ID/path/host are illustrative:**

```json
{
  "model_name": "Qwen3.8-Flash-Next-GGUF-UD-Q4_K_XL",
  "ctx_size": 196608,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 3 --no-kv-unified --cpu-moe --override-tensor '^per_layer_token_embd[.]weight$=CPU' --cache-type-k f16 --cache-type-v f16 --mmap --spec-type none",
  "merge_args": false,
  "save_options": false,
  "pinned": false
}
```

This body is documented as a reference because it was in fact the one that
produced the measured N3 profile above, not because it is recommended for
unreviewed use: it requires releasing the residency (without deleting
files) of any large resident model beforehand,
verifying free memory/GTT, and manually restoring afterward (see the next
section).

## 5. Manual restore reference (Coder + Qwen3.8-27B)

The exact load bodies used to restore the original pair after each trial
in this trial line (`save_options: false` in both, so as not to overwrite
the catalog's `saved` configuration during the trials). This capture is a
dated snapshot from **2026-09-14**, taken before the trial, and it is
**not** the same data source as the
[JSON profile](../../config/halo-strix.reference.json) (which records a
different historical baseline, dated 2026-09-04, with `save_options: true`,
for the Coder+Thinking pair, not Coder+Qwen3.8-27B) nor the
[configuration reference](configuration-reference.md) (which documents the
general semantics of `save_options`, not these exact payloads). In
particular, Qwen3.8-27B's full reasoning arguments
(`--chat-template-kwargs` with `reasoning_effort`/`preserve_thinking`) are
**not** reproduced word-for-word in either of those other two documents;
they are quoted here as this trial line's own reference, not as a repeat
of data already published elsewhere:

```json
{
  "model_name": "Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M",
  "ctx_size": 196608,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0",
  "merge_args": true,
  "save_options": false,
  "pinned": true
}
```

```json
{
  "model_name": "Qwen3.8-27B-GGUF-UD-Q4_K_XL",
  "ctx_size": 65536,
  "llamacpp_backend": "vulkan",
  "llamacpp_args": "--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --spec-type none --reasoning on --reasoning-budget 4096 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --chat-template-kwargs '{\"reasoning_effort\":\"medium\",\"preserve_thinking\":true}'",
  "merge_args": true,
  "save_options": false,
  "pinned": true
}
```

**Explicit warning:** this pair was the one observed resident and restored
on 2026-09-15 with these exact arguments; **this is not a recommendation
that the next load must use identical overrides without your own review**.
`save_options` was deliberately left `false` in both restore calls, so as
not to overwrite the `saved` configuration the service catalog already had
persisted before the trial. No model was pinned
with a guarantee of permanent non-eviction: `pinned=true` blocks automatic
LRU eviction while it stays set, but that is not the same as a physical
memory limit; an explicit `unload` with approval remains the only
documented way to release an intentionally pinned model.

## 6. What is NOT claimed (explicit limits of this trial line)

- **No real long context (~60K prompt tokens) or TTFT was tested.** The
  real prompts used were short (88-201 tokens); the runner used does not
  implement TTFT measurement in streaming mode nor full-context-sized
  prompts. "64K context per slot" describes the **configured budget**, not
  a completed and validated full-length input.
- **Backend overlap is not proven.** `client_scheduled_overlap` only
  confirms the client dispatched concurrent requests; there is no backend
  instrumentation confirming real physical compute parallelism on the
  shared GPU/CPU.
- **There is no "best global profile".** All four profiles passed under the
  same resource contention conditions of the host at that specific moment;
  this cannot be generalized to other workloads, prompt sizes, tool-calling
  patterns, vision input or long-duration sustained (soak) operation — none
  of these scenarios were exercised.
- **Mixed cold/warm cache.** Samples in this run mix requests with a cold
  prefix cache (`cache_n=0`) and a warm one (`cache_n>0`); a pure "cold
  load" state is not claimed for the whole matrix.
- **No permanent host state was touched.** `max_loaded_models`, CORS,
  network and credentials were not changed, and no service
  update/restart occurred in any of these trials.
- **The restored state observed on 2026-09-15 is not a permanent health
  check.** It does not promote Qwen3.8-27B or Flash-Next to a validated
  resident model, and it does not close the September 4 403 or the
  September 10 SSE incident; these are separate evidence lines.
- **"All trials were mutation-free" would be an incorrect generalization.**
  The attempt blocked by the `multiprocessing` bug (2026-09-14/15) did
  actually unload both original models before failing on the first
  inference round; restoration did occur and was verified, but there was
  a real mutation window, not a total absence of state change.

## 7. Recommended next steps (proposal, not executed)

These are explicit recommendations for a future authorized session, not an
already-applied plan:

1. **N2/N3 with real larger inputs** (8K/32K/60K tokens, counted with the
   real tokenizer, not characters), measuring streaming TTFT in addition to
   the decode throughput already measured here.
2. **Real backend overlap instrumentation** (internal slot/GPU-time
   metrics, not just client-side concurrent dispatch).
3. **A sustained (soak) test** of long duration under mixed load, not just
   six short rounds per profile.
4. **Tool calling and vision input** with Flash-Next, neither validated so
   far on this device.
5. **Re-evaluation after upstream PR #27941 merges** (fixes for `seq_cp`,
   block indexing, M-RoPE and the CUDA abort case), which could change the
   risk profile and enable the unified KV pool without the current
   `--no-kv-unified` mitigation.
6. **"Sweet spot" long-context trial: approved 2026-09-15, not executed /
   0 requests due to a transport blocker (no result values because it
   never ran):**
   - Real status: exact human approval for this trial was confirmed on
     **2026-09-15** (sanitized operational record of authorization and
     prior capture, no private file paths or references), with the same
     scope and budget described below. Execution **did not happen**: 0
     inference requests, 0 model load/unloads. The blocker was
     exclusively a transport issue (SSH/ControlMaster channel to the
     remote runner), not the model, not the Lemonade/llama.cpp backend,
     and not a rejection of the approval.
   - A first attempt hit a system argument-length limit while
     transporting the compressed runner via the remote command's argument
     (`E2BIG`/"Argument list too long"), before opening any runner
     execution or doing preflight against the public API; no Halo
     mutation occurred.
   - A second attempt prepared the transfer of local temporary files
     (real diff, local only) over the authorized
     ControlMaster (no code in the remote command's argv), but the
     minimal remote command to create a private working directory did
     not return within 60s and was cancelled by the local limit; no SCP
     transfer ran, no HTTP request was made, and creation of that remote
     directory was **not confirmed** (this does not assert "no file was
     created" as a verified fact; only that trial execution never
     started and never produced requests).
   - Real prompt points to measure (once the transport channel is
     resolved and the trial is repeated under its own approval): `8K`,
     `16K`, `32K`, and up to `~60K` real input tokens (counted with the
     real tokenizer, not characters), with a `64K`-context slot
     configured per profile, and an SSE output cap of `512` tokens
     (a maximum, including any reasoning tokens; not an exact or
     guaranteed output size).
   - Control profile: `N1` (one slot), compared against `N2`/`N3` (two
     and three slots respectively, unrelated to the 3+1 slot split of the
     Coder+Thinking baseline, which is a different configuration) to
     observe throughput
     degradation under concurrency with real long prompts (not just the
     short prompts already measured in this section's matrix).
   - Approved total time budget: at most **16 total requests** within a
     **60-minute** window (including control and comparison rounds), plus
     final restore time.
   - Metrics to capture when run: TTFT (streaming; defined as the time
     from request send to the first non-empty real content delta,
     separate from any preceding reasoning delta; role events or
     keep-alive `ping`s do not count as that first delta and no prior
     `ping` is required as a precondition) and SSE
     behavior via retrieval ("needles") prompts and JSON with **real
     content** verified, real `finish_reason=stop` and `[DONE]`, never
     accepting a role event as success. This trial does **not** require
     the literal `READY` token nor an extra delayed threshold as its own
     criterion: that requirement (`READY` after a threshold) belongs
     exclusively to the historical synthetic probe contract
     `scripts/test-lemonade-sse.py`, not to this long-context trial. It
     also captures verified content quality, and cold (`cache_n=0`) vs.
     warm (`cache_n>0`) memory/GTT separately.
   - This trial, once run, would **not** be a 24x7 continuous-operation
     test: a real 24x7 validation would require a subsequent soak test
     (sustained, long-duration: 2h, 8h and 24h evaluated separately) with
     its own explicit approval, and is not certified by this long-context
     trial nor by the matrix already executed in this document. A
     provisional 24x7 candidate would be 2 balanced slots, based only on
     the short profiles already measured and on the baseline's
     concurrency recommendation of 3; the long-context value is
     provisional and not optimal, and requires prior real TTFT for long
     prefill, true 64K fill, isolation/cancellation, and 2h/8h/24h soak
     evaluated separately.
   - No result numbers are included here because the trial never ran (0
     requests): this item documents approval and transport-blocker
     status, not a measured result.

None of these steps are authorized by this document; they require their
own explicit approval following the workflow described in
[`project-status.md`](project-status.md) and the team's operational policy.

## 8. 2026-09-16 addendum: Q4_K_M offload comparison (`--cpu-moe` all-CPU vs `--n-cpu-moe 40`)

**This is a separate, later, dated evidence line, additive only.** It does
not revise, replace or supersede section 3's 2026-09-15 N1-N4 matrix, does
not close the 2026-09-04 HTTP 403 or the September 10 SSE incident, and it
is **not** a current-health check at the time of reading. It also does
**not** belong to the Unsloth `UD-Q4_K_XL` table already documented
elsewhere in this line (section 5 and the [model guide](model-guide.md)):
this addendum is about a different Q4_K_M quantization, and the two must
not be mixed into one table.

**Model identity note:** the resident Q4_K_M model for this addendum is
published by **Bartowski** at the public Hugging Face repository
[`bartowski/Qwen3.8-Flash-Next-GGUF`](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF),
catalog model ID `Qwen3.8-Flash-Next-GGUF-Q4_K_M`, distinct from the
Unsloth `UD-Q4_K_XL`/`UD-IQ4_XS` builds already referenced in this
document. This repository identity was already checked against the
current public catalog (no new independent fetch was required for this
pass); readers should still re-verify against their own catalog query
before reuse if time has passed.

### What was compared

Both profiles kept the model's already-resident configuration fixed except
for the MoE offload flag: `ctx_size 131072`, `parallel 2`, Vulkan,
`--no-kv-unified`, per-layer token-embedding override pinned to CPU
(`--override-tensor '^per_layer_token_embd[.]weight$=CPU'`), `f16` KV
cache, `--mmap`, `--spec-type none`. The only variable changed was the MoE
expert-layer offload:

- **`--cpu-moe` (baseline, "CPU-all")**: all MoE expert layers offloaded to
  CPU; this profile was already resident, so no reload occurred for it.
- **`--n-cpu-moe 40`**: keeps the MoE weights of the **first 40 layers**
  pinned to CPU, leaving the remainder GPU-eligible. This is **not** "40
  layers on GPU"; it is a CPU-layer-count parameter, and the two flags were
  never combined in the same load.

### Measured results (one valid barrier round of N=2 concurrent requests per profile — not two rounds per profile — same 81-token prompt)

| Profile | Load | Requests | Completion tokens | Server decode tok/s | Client wall (s) | Round wall (s) | Aggregate wall (s) | Contract |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- |
| `--cpu-moe` (baseline) | already resident, no reload | 2 | 75, 98 | 13.216, 14.233 (mean 13.7245) | 12.547, 13.763 | 13.763 | 26.311 | 2/2 HTTP 200, `stop`, exact JSON PASS |
| `--n-cpu-moe 40` | HTTP 200, **8.590 s** | 2 | 100, 98 | 13.987, 13.971 (mean 13.979) | 11.122, 10.986 | 11.122 | 22.108 | 2/2 HTTP 200, `stop`, exact JSON PASS |

- Mean server decode tok/s: **+1.85%** for `n-cpu-moe 40` vs baseline (a
  small difference, not the only criterion).
- Mean client wall latency: **-16.1%** for `n-cpu-moe 40` vs baseline
  (13.155 s -> 11.054 s).
- A naive "tokens accepted / round wall" ratio gives 173/13.763 = **12.57
  tok/s** for the baseline vs 198/11.122 = **17.80 tok/s** for `n-cpu-moe
  40`. **This is not a clean +42% decode-speed claim**: that ratio mixes
  prefill and queue time with decode, and the two profiles did not produce
  the same number of completion tokens (173 vs 198), so outputs are not
  length-matched.
- Restore: HTTP 200 in **6.640 s**, `restore_match_actual: true` against
  live health/`launch_command` (the catalog's `saved` options field
  remained empty `{}` throughout and was not used as the verification
  source).

### Why this is not a clean causal comparison

- **A managed download was actively running throughout both profiles**: a
  catalog pull of `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS` (three GGUF
  files, `93,682,584,224` bytes total, ≈93.68 GB / ≈87.25 GiB) was in
  `status="downloading"`, `running=true` at the time of these requests and
  remained unfinished at the last status query
  (**2026-09-16T11:02:26Z**, still running; no later byte-progress figure
  is available in this evidence). This download is a real I/O/cache
  confounder for both profiles; **no causal speedup is claimed** for
  `n-cpu-moe 40`.
- **Completion-token counts differ** between profiles (75+98 vs 100+98),
  so this is not an identical-output comparison.
- **A single round per profile** (N=2, one repeat) does not establish
  statistical robustness; both rounds did pass the content contract
  (4/4 requests: real `stop`, exact JSON/marker content, no forced
  truncation).
- **Four earlier same-day requests are excluded from this comparison**: a
  prior attempt at both `--cpu-moe` and `--n-cpu-moe 40` used a **32-token
  completion cap** and both ended `finish_reason=length` without the
  expected marker. This is an **inconclusive result caused by the token
  cap forcing truncation**, not evidence that either profile is
  unsupported; because of that inconclusive result, the plan explicitly
  did not escalate to testing an `--n-cpu-moe 32` variant that same
  session.
- **A `--n-cpu-moe 32` profile was left untested**, not "32 further
  requests not run": the plan called for one more valid barrier round
  (4 requests: 2 for a second baseline round, 2 for an `--n-cpu-moe 32`
  candidate profile), but a transport (SSH/ControlMaster) failure to the
  remote runner happened before any of those 4 requests could be sent —
  **not** a model or backend rejection, and not a root-cause finding about
  the models themselves.
- **Total requests across this whole evidence set: 12 planned, 8 executed**
  (4 inconclusive due to the 32-token cap + 4 valid, reported above), with
  **4 planned requests not run** due to the transport failure above.

### Resources (point-in-time snapshots, not a continuous guard sweep)

| Checkpoint | MemAvailable (GiB) | Free GTT (GiB) |
| --- | ---: | ---: |
| Initial (before either profile) | 111.27 | 52.64 |
| During `n-cpu-moe 40` | 98.08 | 39.43 |
| Final (after restore) | 111.20 | 52.64 |

These are discrete checkpoints against a configured guard of 16 GiB
MemAvailable / 4 GiB free GTT (both respected at every sampled point); this
is **not** a continuous "all times" monitor, and the sample count/interval
for a full guard sweep across this window is not available in this
evidence. No inference is made here about the total memory/GTT footprint
of the full GGUF or about extra GTT the in-progress IQ4_XS download might
eventually require.

### The UD-IQ4_XS download: started, not completed

Downloading `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS` under the catalog
name `user.Qwen3.8-Flash-Next-UD-IQ4_XS` is an explicitly **mutable
disk/network operation** (not a read-only check). It was started with
human approval as a managed pull (`stream=true`, `subscribe=false`); it
was **not** loaded, and no other quantization or MTP draft artifact was
requested. Its actual state at the time of this addendum:

- Total size: 3 files, **93,682,584,224 bytes** (≈93.68 GB / ≈87.25 GiB).
- Public catalog identity: `unsloth/Qwen3.8-Flash-Next-GGUF:UD-IQ4_XS`, a
  catalog technical identifier, not private/personal data.
- An early sample showed **368,148,732 bytes** (≈0.39%) downloaded, at an
  unspecified early timestamp; this is **not** the latest state.
- At the last status query (**2026-09-16T11:02:26Z**), the job was still
  `status="downloading"`, `running=true`; the latest byte-progress figure
  was not available in this evidence because a later status refresh was
  blocked by an SSH transport failure.
- **Not completed, not hash-verified, no final size confirmed.** No
  partial file was deleted. No load was attempted for `UD-IQ4_XS` or any
  other quantization.

### `--cpu-moe` as a starting choice, not an architecture mandate

The conservative `--cpu-moe` (all-CPU MoE offload) profile used earlier in
this trial line was an initial conservative choice for a first safe probe,
not an architectural requirement; `--n-cpu-moe N` is a different,
finer-grained offload knob (first `N` expert layers pinned to CPU, the
rest GPU-eligible) and the two are alternatives, not a combination. A
future clean A/B is explicitly **pending**, to run only after this
IQ4_XS download completes (or is otherwise no longer active) and only
under its own separate approval; this addendum does **not** authorize
that follow-up run, does not change backend/thread configuration now, and
is not a 24x7 or sustained-throughput claim.

### What this addendum does NOT claim

- **No causal speedup for `n-cpu-moe 40`.** The observed lower client wall
  time and slightly higher decode tok/s are confounded by the concurrent
  IQ4_XS download and by unmatched output lengths.
- **No completion of the IQ4_XS download**, no hash/size verification, no
  load of that or any other quantization.
- **No change to `max_loaded_models`, pins beyond what was already set, network, CORS, or service configuration.**
- **No resolution of the earlier 32-token-cap inconclusive result**; that
  remains a runner/config artifact (token cap forcing truncation), not a
  model-support finding, and `--n-cpu-moe 32` was deliberately not tried
  in this same session.
- **No re-opening or closing of the 2026-09-04 403 or the September 10 SSE
  incident.**

### 2026-09-16 note: later baseline / `--n-cpu-moe 32`/`24` sweep attempt NOT executed

Subsequent to the comparison above, a separate attempt was authorized to
look for a stable maximum between a baseline profile (`--cpu-moe`) and
`--n-cpu-moe 32`/`24` candidates on the same resident Q4_K_M model. **This
attempt was not executed**: the preceding command-channel check toward the
remote host did not produce a reliable result — the transport used showed
intermittent behavior (sometimes instant response, sometimes indefinite
hang with no output, for the identical command and environment), which is
recorded here as **timeouts/intermittency of the transport tooling used**,
not as a root cause attributed to host networking, the remote master
process, or the Lemonade/backend server.

As a result:

- **Zero inference requests** were sent for baseline, `32`, or `24` (or
  for any planned `20`/`16` refinement).
- **No model change, pin, active argument, or `saved` field** was
  touched; no model was loaded or unloaded.
- **No restore was necessary**, since no mutation occurred on the host.
- **The UD-IQ4_XS download state and current host health could not be
  verified** in this attempt; the last known figure remains the one
  already recorded above (**2026-09-16T11:02:26Z**,
  `status="downloading"`, `running=true`), cited as the last available
  observation, **not** as a confirmed current state.

This attempt does not invalidate or confirm anything about the
`--cpu-moe`, `--n-cpu-moe 40`, `32`, `24`, `20`, or `16` profiles; the
`--cpu-moe` vs `--n-cpu-moe 40` comparison results documented above (mean
decode +1.85%, confounded by the concurrent IQ4_XS download) remain the
last available performance observation on this offload, not a new state
or a found stable maximum. It does not reopen the section 3 N1-N4 matrix,
the 2026-09-04 403, or the September 10 SSE incident.

### 2026-09-16T12:42:05Z–12:44:03Z (~118 s) note: baseline / `--n-cpu-moe 32`/`24` sweep EXECUTED SUCCESSFULLY

**This subsection is later and purely additive relative to the prior note
("later attempt... NOT executed").** It does not replace or delete that
note: that note documents a first attempt blocked by a different, dated
transport failure; this subsection documents a **second attempt**, in a
later window, that did complete. Both notes coexist as independent dated
evidence.

In this window (**2026-09-16T12:42:05Z–12:44:03Z**, ~118 s of real
mutation, well under the authorized budget) **6/6 real requests** were
executed (2 per profile × 3 profiles: baseline `--cpu-moe`,
`--n-cpu-moe 32`, `--n-cpu-moe 24`) against the same resident Bartowski
Q4_K_M model, with `ctx_size=131072`, `--parallel 2`, `--no-kv-unified`,
per-layer token-embedding override pinned to CPU, `f16` KV cache,
`--mmap`, `--spec-type none` fixed across all three profiles; the only
changed variable was the MoE offload flag (all-CPU vs first `N` layers
pinned to CPU), never combining both flags in one load. No `16`/`20`
variants were tried in this window.

**Results (one barrier round of N=2 concurrent requests per profile, same
two fixed synthetic prompts: exact JSON and the word `READY`):**

| Profile | Reload | Prompt tokens | Completion tokens | Server decode tok/s (min–max) | Client wall (s, min–max) | Round wall (s) | `cache_n` |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| baseline (`--cpu-moe`) | already resident, no reload | 88, 83 | 64, 223 | 11.03 – 14.87 | 14.503 – 23.722 | 23.723 | 0, 0 |
| `--n-cpu-moe 32` | HTTP 200 in 6.559 s | 88, 83 | 61, 223 | 13.08 – 15.56 | 13.458 – 22.424 | 22.424 | 0, 0 |
| `--n-cpu-moe 24` | HTTP 200 in 15.436 s | 88, 83 | 61, 280 | 11.36 – 15.69 | 14.556 – 27.052 | 27.053 | 0, 0 |

All six requests finished with a real `finish_reason=stop`, exact verified
content (JSON `{"sum":4}` and `READY`, no truncation), 6/6 contract PASS.
`cache_n=0` on all six indicates a cold KV cache per request/profile (each
reload resets backend state); this is **not** a guarantee of cold
OS-level file/RAM cache, and no isolated `N=1` request was tried here to
separate that effect.

Aggregate throughput per round (sum of `completion_tokens` divided by the
round wall; not a mean of per-request ratios, which would mix
prefill/queue with decode differently per request):

- baseline: (64+223)/23.723 = **12.10 tok/s**
- `n-cpu-moe 32`: (61+223)/22.424 = **12.67 tok/s**
- `n-cpu-moe 24`: (61+280)/27.053 = **12.60 tok/s**

**Explicitly bounded interpretation:** with a single round of 2 requests
per profile, the three aggregate values (~12.1–12.7 tok/s) fall within a
similar noise margin of each other; this does **not** establish a
statistically robust "winning profile", does not validate a full
131072-token input context (the real prompts were 83 and 88 tokens), and
does not establish a "stable maximum" offload. Both candidates (`32` and
`24`) were accepted by the server (the effective `launch_command` verified
after each load literally contains `--n-cpu-moe 32`/`--n-cpu-moe 24`,
without `--cpu-moe`, with no server rejection at any point), but that only
confirms flag acceptance, not a demonstrated performance gain over
baseline in this one-off sample.

**Memory/GTT checkpoints (discrete snapshots, not a continuous sweep):**

| Point | MemAvailable (GiB) | GTT free (GiB) | Guard (Mem≥16 / GTT≥4) |
| --- | ---: | ---: | --- |
| Initial | 111.33 | 52.64 | met |
| After baseline round | 110.85 | 52.62 | met |
| After `n-cpu-moe 32` round | 85.31 | 27.12 | met |
| After `n-cpu-moe 24` round | 73.44 | 15.13 | met |

The tightest point observed (`n-cpu-moe 24`, 15.13 GiB GTT free) passed
the short round tried without tripping a guard, but this does **not**
demonstrate a statistical benefit over `32` or establish which profile is
"winning": a single round per profile has no statistical robustness, and
neither a full context nor a 30 tok/s target was validated.

**Restore:** at the end, the model was unloaded and the original profile
was reloaded (`--cpu-moe`, `ctx_size=131072`, `--parallel 2`, remaining
flags identical, `pinned=true` preserved), with HTTP 200 in **14.255 s**;
the effective `launch_command` after restore matched exactly the one from
the pre-mutation snapshot (same binary, same `.gguf`, same `mmproj`, same
flags). The catalog `saved` field remained empty throughout the process
and was not used as a verification source; this subsection makes no new
claim about that field beyond noting it was not used.

**`UD-IQ4_XS` download:** `GET /api/v1/downloads` returned an empty list
at the time of this point-in-time query. **This does not prove the
download is complete, failed, or cancelled**; it only indicates that at
that specific instant no active jobs were reported by that endpoint. No
`IQ4_XS` or other quantization was loaded or hash/size-verified; the
previously recorded public download status (last known figure
**2026-09-16T11:02:26Z**, `status="downloading"`, `running=true`) is
neither updated nor reversed by this one-off empty query.

**What this subsection does NOT claim:**

- No statistically robust "winning" profile among `--cpu-moe`,
  `--n-cpu-moe 32`, and `--n-cpu-moe 24`; a single round of N=2 per
  profile is not enough.
- No validation of a full 131072-token real input context, nor of a
  30 tok/s target.
- No other model, driver, or service was touched; no change to
  `max_loaded_models`, network, CORS, or service configuration; no
  candidate was automatically promoted to a default configuration.
- No confirmation or refutation of the `UD-IQ4_XS` download completion.
- Does not reopen the section 3 N1-N4 matrix, the 2026-09-04 403, or the
  September 10 SSE incident.
- Not a claim of current host health beyond the moment of this dated
  window (2026-09-16T12:42:05Z–12:44:03Z).

## Sources and technical provenance

- Measurement artifacts from the 2026-09-15 run: `result.json`,
  `summary.json` and `checkpoint.json` from the runner (technical, already
  sanitized; no real host/IP/credentials).
- `llama.cpp` source inspection on GitHub:
  [`src/models/qwen4exp.cpp` at `010be9683`](https://github.com/ggml-org/llama.cpp/blob/010be9683afabe14ce299197b38c329f94bae568/src/models/qwen4exp.cpp),
  PR [#27742](https://github.com/ggml-org/llama.cpp/pull/27742) (base
  support, merged 2026-08-27), PR
  [#27941](https://github.com/ggml-org/llama.cpp/pull/27941) (fixes, not
  included in the verified live build).
- Sanitized operational record of prior authorization and capture (no
  private file paths or references; no private data, host, IP, username,
  socket or session path is reproduced).
- [Model comparison (Spanish)](../comparativa-qwen38-halo-strix.md) and the
  [English model guide](model-guide.md), Qwen3.8-Flash-Next section, for
  the prior context blocked by architecture incompatibility on the old
  `b10375` build.

No private artifact (session paths, sockets, real host/IP, credentials) is
reproduced in this document. All numbers quoted are technical and were
already sanitized at their source.
