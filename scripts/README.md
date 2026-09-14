# Lemonade diagnostic scripts

For repository setup, see the [English README](../README.en.md).
[Lemonade parameter dictionary](../docs/en/lemonade-parameter-reference.md) |
[Documentary project status](../docs/en/project-status.md)
This directory's `test-lemonade.ps1` checks an explicitly selected Lemonade
OpenAI-compatible API. It does not install software, change server settings,
request credentials, or manage host services.

## Requirements and parameters

- Windows PowerShell 5.1 or PowerShell 7, with `System.Net.Http`.
- An already-running, reachable Lemonade API authorized for your use.
- An explicitly chosen API base URL and **exact** advertised model ID.
- Review existing inference/training workloads before requesting chat:
  loading a different model can evict a currently loaded model or compete for
  GPU/GTT/RAM.

| Parameter | Required | Meaning |
| --- | --- | --- |
| `-BaseUrl` | Yes; no default | Absolute `http://` or `https://` URL with a valid host and optional port/base path, normally ending in `/v1` |
| `-Model` | Yes; no default | Exact model ID returned by that API's `/models` endpoint |

Trailing slashes are removed before appending endpoint paths. URL credentials,
whitespace, query strings, and fragments are rejected before any request.
There is no token/password parameter and no automatic authentication flow.
The client deliberately bypasses proxies; HTTPS uses normal certificate
validation. Use the approved network path rather than disabling TLS checks
or embedding credentials in a URL.

Built-in help, with no network activity:

```powershell
Get-Help .\scripts\test-lemonade.ps1 -Full
```

Run commands below from the repository root in a Windows PowerShell terminal.
Do not bypass your organization's execution policy; use an approved shell.

## Read-only discovery before chat

This example addresses **localhost only**. Change it only to an authorized
endpoint (for example, a separately established local tunnel); no remote host
is assumed. The command requires that an API already be listening there.

```powershell
$baseUrl = 'http://localhost:13305/v1'
Invoke-RestMethod -Uri "$($baseUrl.TrimEnd('/'))/models" -Method Get -TimeoutSec 15 |
    Select-Object -ExpandProperty data |
    Select-Object id
```

`GET /models` lists advertised IDs and does not request inference or select a
model. Server/proxy access logs may still record the request. Unlike the test
script's HttpClient, `Invoke-RestMethod` can inherit the shell's proxy settings;
use the appropriate approved route for your environment.
Listing a model does not prove it is loaded, GPU-compatible, or safe to load
alongside the current workload.

## Explicit chat test

After reviewing GPU ownership, replace `YOUR_MODEL_ID` with the intended ID
from discovery, then run:

```powershell
.\scripts\test-lemonade.ps1 `
    -BaseUrl $baseUrl `
    -Model 'YOUR_MODEL_ID'
```

For a separate, noninteractive PowerShell 7 process:

```powershell
pwsh -NoProfile -NonInteractive -File .\scripts\test-lemonade.ps1 `
    -BaseUrl 'http://localhost:13305/v1' `
    -Model 'YOUR_MODEL_ID'
```

Use `powershell.exe` instead of `pwsh` for Windows PowerShell 5.1.
Both arguments are mandatory: an interactive shell can prompt for omitted
values, whereas `-NonInteractive` fails instead of prompting. No endpoint or
model is silently selected.

The script performs:

1. `GET <BaseUrl>/models`, with a **15-second** timeout.
2. Exactly-one-match lookup of the requested model ID; missing/duplicate
   matches fail **before chat**.
3. `POST <BaseUrl>/chat/completions`, with a **90-second** timeout, one user
   message `Reply only with LAN_OK.`, `temperature: 0`, `max_tokens: 16`, and
   `stream: false`.
4. Extraction of the first choice's `message.content`, falling back to
   `message.reasoning_content` when content is empty/whitespace.

**The full script is not read-only.** Chat performs inference and can load
models, create backend caches/logs, or evict another model. There is no
discovery-only switch; use the separate GET command for read-only discovery.
The script disposes the HTTP response, request content, client, and handler
even on failure. It exits its process; do not dot-source it into another script.

## Expected output and failures

Success produces output such as:

```text
Lemonade LAN test: PASS
Endpoint: http://localhost:13305/v1
Model: YOUR_MODEL_ID
Response: LAN_OK
```

Success exits `0`. Any nonempty content or reasoning answer satisfies the
script: **PASS does not require literal `LAN_OK`**, certify GPU placement,
prove training compatibility, or measure performance. The name “LAN test”
also applies to loopback tests.

Request/response failures emit `Lemonade LAN test: FAIL` and exit nonzero.
Parameter-binding errors occur before that runtime diagnostic and also fail.
Typical causes:

- Missing arguments or an invalid base URL: supply both explicit parameters;
  remove credentials/query/fragment instead of adding secrets.
- Connection refused, timeout, or TLS failure: check endpoint availability,
  approved routing/firewall, and certificates. No retries are performed.
- HTTP non-success: the error includes status, reason, and endpoint; verify
  the API base path, server health, and access requirements.
- Model absent or duplicated: inspect discovery and select the intended ID.
- Missing model data, invalid chat choices, or empty content and reasoning:
  check the server's OpenAI-compatible response schema.

Outputs include the chosen endpoint, model, and response. Keep run output
private if those reveal local infrastructure or model data; do not paste it
into a public issue without reviewing it.

## Offline regression tests

The stdlib-only fixture needs an **existing** Python 3 installation and a
PowerShell executable. It binds to an ephemeral `127.0.0.1` port, invokes the
real script in noninteractive child processes, and shuts down afterward.
It uses no remote service, Docker, GPU, `.env`, or data directory and installs
no dependencies.

```powershell
python .\scripts\tests\test_lemonade.py --shell pwsh -v
# Optional compatibility run when Windows PowerShell 5.1 is available:
python .\scripts\tests\test_lemonade.py --shell powershell.exe -v
```

The runner covers 18 tests, including eight invalid-URL subcases, PowerShell
parsing, mandatory arguments without network requests, endpoint paths and chat
payload, trailing slashes, content/reasoning fallback, model lookup failures,
HTTP errors, and malformed/empty chat responses. Expect `Ran 18 tests` and
`OK`; failures report the specific assertion and exit nonzero. Timeouts and
resource-disposal behavior remain unchanged; the fixture does not wait for a
real 90-second timeout or validate a real GPU/server.

## Synthetic streaming regression probe

[`test-lemonade-sse.py`](test-lemonade-sse.py) is a separate, Python 3.9+
stdlib-only probe for the
[long-prefill streaming incident](../docs/en/lemonade-sse-timeout.md).
It sends synthetic text, never reads user prompt files, and does not install
software, change configuration or explicitly load/unload models.

The request disables reasoning with both `reasoning_effort: "none"` and
`chat_template_kwargs: {"enable_thinking": false}`. The latter is necessary
for the observed Qwen3.8-27B template: otherwise its reasoning can consume
the 16-token output budget without producing the required visible answer.
This override affects the probe request only, not the model's saved profile.

Unlike the PowerShell script, its `--base-url` is the **origin only**, without
`/v1` or `/api/v1`. The URL and exact model ID are mandatory. Connections are
direct, ignore proxy environment variables, reject embedded credentials and
do not follow redirects.

Before sending its single streaming chat request, it checks that the selected
model is already resident, `backend_alive` is true, `backend_health` is
`ready`, and an effective `recipe_options.ctx_size` is present. It rejects
reported active/queued work on any resident model. Missing activity telemetry
requires independent reservation of an idle server and the explicit
`--allow-unverified-idle` option; that option never overrides known activity.
This check is not an atomic reservation: prevent concurrent model changes and
new work during the probe.

**A large run is a GPU workload, not read-only.** Count the synthetic prompt
with the actual model tokenizer first, allowing for chat-template and output
overhead. The importable `build_prompt(records, nonce)` function lets an
operator count the same record format without generating a response.
Character count is not token count, and the default 2,000 records is not a
guarantee that a particular context window is sufficient.

After sizing the input and reserving the server, run from the repository root:

```powershell
python -B .\scripts\test-lemonade-sse.py --base-url 'http://<HALO_HOST>:13305' --model 'Qwen3.8-27B-GGUF-UD-Q4_K_XL' --records 2000 --minimum-first-token-seconds 130 --timeout-seconds 1400
```

This requires the first actual model delta to arrive **after at least 130
seconds**, followed by content `READY`, `finish_reason: stop` and `[DONE]`.
HTTP headers, role-only deltas and SSE pings do not count as a model token.
A response that arrives too quickly fails this regression gate rather than
claiming to cover the old 120-second failure. A new nonce reduces prefix
reuse, but client-observed timing alone does not prove isolated GPU prefill;
correlate the run with backend logs and ensure it was not waiting in a queue.

For a deliberately short smoke, use `--records 1
--minimum-first-token-seconds 0`. Its report explicitly says `smoke_only`;
it is not evidence that a long prefill survives.

The probe bounds the overall wait, cancels its HTTP connection on failure,
detects errors inside an HTTP-200 SSE response, and rejects missing completion
signals or truncated output. It does not retry. Its JSON report contains
timings and selected metadata, not the endpoint, original prompt or model
identifier. The server can still log the synthetic request normally.

Offline entrypoint tests use a loopback fixture and short delays, without a
GPU, real service, credentials or downloaded dependencies:

```powershell
python -B .\scripts\tests\test_lemonade_sse.py -v
```

See the [test source](tests/test_lemonade_sse.py) for checks of real health-field
names, preflight refusal, SSE framing/errors, first-token timing, timeouts and
connection cleanup.
