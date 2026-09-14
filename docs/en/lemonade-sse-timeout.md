# Lemonade streaming timeout: September 10, 2026

[English index](README.md) | [Spanish summary](../incidente-sse-lemonade.md) |
[Parameter dictionary](lemonade-parameter-reference.md) |
[Project status](project-status.md) |
[Diagnostic scripts](../../scripts/README.md)

This dated incident is separate from the
[September 4 configuration baseline](configuration-reference.md). It does not
change the interpretation of older measurements or resolve the unidentified
September 4 HTTP 403 report.

**Outcome:** the lab service was upgraded to **11.9.0-1**, with managed Vulkan
**b10723-010be9683** and persisted `global_timeout = 1200`. Both resident models
and their saved profiles were restored. This is a dated maintenance result,
not live monitoring.

> **Provenance warning:** the available session history contains an earlier
> checkpoint where 11.9.0 was prepared but not installed. This documentation
> task did not perform an independent audit. The report retains an assumed
> later result, which does not prove the host's current state.

## Observed failure

Lemonade 11.8.1 was serving a resident Qwen3.8-27B `UD-Q4_K_XL` on Vulkan,
with one slot and a 65,536-token context. Four streaming requests were
cancelled while llama-server was still processing input:

| Server log time | Time from task launch | Prefill progress at the last sample |
| --- | ---: | ---: |
| 12:39:25 | 126.063 s | 91% |
| 13:26:41 | 126.056 s | 85% |
| 13:37:41 | 126.054 s | 91% |
| 14:06:54 | 126.050 s | 74% |

The contiguous log windows contained ongoing prefill progress, then
`CURL error: Timeout was reached`, task cancellation approximately one second
later, and slot release with `truncated = 0`. No decode events occurred in
these requests. Their slots started promptly; these windows do not establish
queueing as the cause. Both model processes remained available afterward.

This was **not** the earlier 32k context exhaustion, which had ended with
`n_tokens = 32767, truncated = 1`. It was also separate from a recorded
client disconnection at 12:40; that event does not establish whether the
client cancelled manually or reached its own timeout.

## Cause and official correction

In 11.8.1 the streaming HTTP client used libcurl's low-speed policy:

```text
LOW_SPEED_LIMIT = 1 byte/second
LOW_SPEED_TIME = 120 seconds
```

This is a low-transfer condition, not a precisely 120-second total deadline.
It explains the roughly 126 seconds actually observed. GPU progress during
prefill does not produce response bytes, and downstream SSE pings from
Lemonade do not reset the upstream connection's low-speed timer.

The old streaming branch did not use `global_timeout`. Raising that setting
alone therefore did not fix 11.8.1.

**Official Lemonade 11.9.0 fixes this behavior** in commit
`bb39eafc22aa7e57fc7aeb8b7d384d70b44a4531`. Its streaming low-speed interval
uses the configured timeout. The lab's selected global value is **1200
seconds**; in 11.9.0 this also controls the streaming silence tolerance.

This official solution does **not** implement separate 600-second prefill and
120-second post-token idle limits. It uses the configured interval for both.
It is still bounded, retains client cancellation, and does not impose that
interval as a total deadline on a healthy stream continuously transferring
data. Non-streaming requests use a total backend-transfer timeout instead.

## Upgrade and rollback boundaries

Use a supported, verified package for the host distribution, or a traceable
local build of the official source. Do not install a Debian package directly
on CachyOS, replace a binary without checking its dependencies, or perform an
unrelated whole-system/driver upgrade to fix this incident.

The installed lab artifact was a **local unsigned Arch package**, not an
official signed Arch binary or a hermetic build:

| Item | Recorded value |
| --- | --- |
| Source | Official v11.9.0 commit above; no custom C++ timeout patch |
| Package | `lemonade-server-11.9.0-1-x86_64.pkg.tar.zst` |
| Package SHA-256 | `5c7521451f378e9d76fd06a151a2ba6b447835b797010ef9b3ae50744c5c57c7` |
| Build limits | Four build jobs, nice level 10 |
| TLS integration | Upstream-supported OpenSSL mode, private header-only build prefix |
| Web assets | Official release frontend assets plus KaTeX fonts; not rebuilt from frontend source |
| System dependencies | No system package installation/update needed for the build |
| Previous package retained for rollback | `lemonade-server-11.8.1-1.1-x86_64_v4.pkg.tar.zst` |

The package and private backup contents are not distributed in this
repository. On the maintained Linux host, the versioned build and rollback
artifacts are retained under `$HOME/.local/state/lemonade-maintenance/`.
Do not disable signature verification globally: use the
distribution's existing policy and independently verify any locally built
artifact you choose to install.

Before service replacement, preserve the installed package, managed backend
tree, configuration, user unit/drop-ins, current resident model identities,
effective options and pin state. Keep backups private and do not copy
credentials or host topology into public reports. Check both service health
and actual slot activity immediately before stopping the user service.

Keep the rollback package available locally so recovery does not depend on a
download. If upgrade acceptance fails, stop the new service, restore the old
package/backend/configuration as needed, restart the same user service and
explicitly restore the former resident set. Do not assume startup reloads
models automatically.

### Version-specific compatibility checks

- v11.9.0 advertises managed Vulkan llama.cpp **b10723**, rather than the
  previous **b10375**. Preserve the old backend and record which version is
  actually running after restoration. Do not enable experimental HRX or MTP
  as part of this timeout fix.
- The legacy `LEMONADE_ALLOWED_ORIGINS` setting is deprecated and migrates
  into `allowed_origins`. Preserve the existing policy; verify the legitimate
  browser origin rather than replacing the allowlist with a wildcard.
- Reserved directories under `extra_models_dir` change discovery behavior.
  Review the release notes and inspect exact catalog IDs
  before and after, not just model display names.
- The effective configuration also exposes new logging defaults
  (`log_file: auto`, `log_max_file_size_mb: 10`, `log_max_files: 5`) and HRX options. These
  newly exposed defaults are distinct from changes to user-saved settings;
  an HRX configuration section does not mean an HRX model was loaded.
- Preserve effective context, slot count, custom arguments, resident limits
  and pins. Configuration migration is not permission to retune a model.

## Restored September 10 profile

| Setting | Coder | Thinker |
| --- | --- | --- |
| Exact resident ID | `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` | `Qwen3.8-27B-GGUF-UD-Q4_K_XL` |
| Effective total context | 196608 | 65536 |
| Slots | 3 | 1 |
| Backend | Vulkan | Vulkan |
| Pinned | Yes | Yes |
| K/V cache | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| Saved `merge_args` | `true` | `true` |

`max_loaded_models` remains **2**. Coder's unified context is a total shared
pool, not 196608 tokens per slot. The 27B context is 65536 in the actual
recipe; its advertised maximum is not evidence of a larger allocated window.

Literal Coder UI arguments:

```text
--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0
```

Literal 27B UI arguments:

```text
--parallel 1 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --spec-type none --reasoning on --reasoning-budget 4096 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --chat-template-kwargs '{"reasoning_effort":"medium","preserve_thinking":true}'
```

Set the context in the model's context setting, separately from these
argument strings. **Do not insert literal backslashes before the JSON
quotation marks when pasting into the UI.** A serialized API JSON payload
needs normal JSON escaping; the UI field needs the literal argument text.

These are preserved settings, not a claim that every value is optimal.
The timeout maintenance did not change the 27B's normal reasoning budget,
enable MTP, or increase its context.

## Reproduce the streaming acceptance condition

The [synthetic SSE probe](../../scripts/test-lemonade-sse.py) requires an
explicit origin and an already-resident exact model ID. Its
[English usage guide](../../scripts/README.md#synthetic-streaming-regression-probe)
documents activity checks, sizing, time limits and failure behavior.

Reserve an idle service and tokenize the generated synthetic prompt with the
target model before selecting a large record count. On the inference host,
the resident backend's `/tokenize` endpoint can be used for this purpose.
Obtain `backend_url` from health, keep its scheme/host/port and remove its
OpenAI base path before appending `/tokenize`, `/props` or `/slots`; these
are native backend routes, not `/v1` routes. Do not assume a port. That loopback
URL belongs to the host, not to a remote Windows client. Allow for the chat
template and generated output in addition to raw text tokens.

A representative invocation from the repository root on Windows is:

```powershell
python -B .\scripts\test-lemonade-sse.py --base-url 'http://<HALO_HOST>:13305' --model 'Qwen3.8-27B-GGUF-UD-Q4_K_XL' --records 2221 --minimum-first-token-seconds 130 --timeout-seconds 1400
```

On Linux, use the same Python script and arguments with that platform's
filesystem path. The base URL is an **origin**, not an OpenAI `/v1` base URL.

Acceptance requires a first actual model delta after at least **130 seconds**
and a complete `READY` response, `finish_reason: stop`, and `[DONE]`. A short
successful response, HTTP 200, an initial role-only event, or an SSE ping is
not sufficient. Correlate the timing with backend prefill progress and the
absence of queueing. Check memory headroom and verify that both models remain
healthy after the request.

The script's short mode (`--records 1 --minimum-first-token-seconds 0`) is
useful for checking each restored model, but explicitly reports smoke-only
coverage. Neither probe certifies model quality, general long-context
stability or fine-tuning support.

### Recorded acceptance results

The long trials used **2221 synthetic records**, a fresh leading nonce,
`max_tokens: 16`, `reasoning_effort: "none"` and
`chat_template_kwargs: {"enable_thinking": false}`. The explicit template
override was necessary: the original short probe could consume its output
budget on reasoning without producing `READY`. This is a per-request
override only; the saved thinker profile above remained unchanged.

| Measurement | On-host trial | Independent Windows-to-Lemonade trial |
| --- | ---: | ---: |
| Prompt tokens reported by backend | 44500 | 44497 |
| Completion tokens | 2 | 2 |
| First model content | 214.735 s | 214.866 s |
| Total client elapsed time | 214.839 s | 214.980 s |
| Completion | `READY`, `stop`, `[DONE]` | `READY`, `stop`, `[DONE]` |

Small token-count differences come from the fresh nonce. The independent
trial's backend log showed **214.640 s of prompt evaluation**, approximately
207.31 prompt tokens/s, with progress continuing past 120 and 130 seconds.
It finished with `truncated = 0`; this was not a queued wait disguised as
prefill or an initial SSE ping counted as a token.

The on-host trial's 44 memory samples peaked at **48,695,287,808 bytes
(45.351 GiB) GTT** and **2,040,217,600 bytes VRAM**. That left approximately
16.380 GiB of the observed GTT capacity. These are sampled peaks for this
workload, not guarantees for concurrent inference or training.

Both models also completed short requests and retained their process IDs,
pins, effective profiles and idle slots after the independent long trial.
The installed and running daemon matched the approved package's binary.
The persisted configuration retained `global_timeout: 1200`; its only key
change was the upstream `allowed_origins` migration. Six other backed-up
configuration/unit files were byte-identical. Legitimate browser GET/OPTIONS
requests and the Web UI worked; an unconfigured browser origin returned 403.

An initial service-stop guard triggered recovery before package replacement.
The retry proceeded after confirming the old processes had exited. The
existing user unit was retained rather than weakened to bypass the guard.

**Remaining limits:** this removes Lemonade's old fixed streaming stall
window. It does not speed up a 44k-token prefill, shorten reasoning, compact
client history, or extend a client/reverse-proxy timeout. Keep those limits
explicit and retain cancellation; do not replace them with unbounded waits.

## Sources

- [Official v11.9.0 release and migration notes](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0)
- [Official timeout correction commit](https://github.com/lemonade-sdk/lemonade/commit/bb39eafc22aa7e57fc7aeb8b7d384d70b44a4531)
- [11.8.1 HTTP client](https://github.com/lemonade-sdk/lemonade/blob/v11.8.1/src/cpp/server/utils/http_client.cpp)
- [11.9.0 HTTP client](https://github.com/lemonade-sdk/lemonade/blob/v11.9.0/src/cpp/server/utils/http_client.cpp)
- [Upstream timeout regression tests](https://github.com/lemonade-sdk/lemonade/blob/v11.9.0/test/cpp/test_http_client_timeout.cpp)
