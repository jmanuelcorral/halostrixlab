# Halo deployment: Halogen 128K and llama-swap

[Español](../despliegue-halogen-128k.md) |
[Workspace](../../workspaces/inference/README.en.md) |
[English index](README.md) | [Project status](project-status.md)

**Intervention record: 2026-09-17.** This records the authorized September
16-17 preflight and deployment starting from checkout `a9a6e3f`. Private file
timestamps and clocks across sessions are not treated as a common precise
timeline. These are dated observations, not continuous health monitoring.
The September 4 Lemonade baseline and previous 403/SSE incidents remain
separate evidence tracks; this deployment does not close them.

No raw logs, private addresses, usernames, credentials, agent configuration
or runtime `data/` contents are published. Examples below are sanitized.

## 1. Outcome and evidence classes

**Later same-day update:** profile C is now applied with four slots and KV
pool 524288. Section 10 adds its tests and a subsequent log review; earlier
sections retain the original one-slot stages and measurements. Reviewing logs
did not initiate another model load.

| Layer | State at intervention close |
| --- | --- |
| Hardware | Actual Halo confirmed, native Linux and `gfx1151` |
| llama-swap | v255, enabled and active user service |
| Served model | Only `flash-halogen`, W4B Quality, context 131072 |
| Output | Configured maximum 8192, sharing context with input |
| Concurrency | Profile C: four slots, KV pool 524288, gateway/global model limits 4; initially one slot/pool 131072 |
| Lemonade | 11.9.0 retained; user service disabled and inactive |
| Coder Vulkan | Tested at 32K and 128K, removed from active catalogue; weights/image retained |
| Cockpit | Installed terminal UI used for exploration; no ownership of final managed runtime |
| Final network | Authorized LAN address, HTTP TCP/18080, API key removed at operator request |
| TLS | Tested on loopback with a test certificate, then removed; no LAN TLS deployment |
| Startup | Existing linger retained; login-independent startup configured, host reboot not tested |

**Implemented:** runtime lifecycle, Cockpit adapter, profile validation,
discovery limits and regression tests. **Offline-tested:** configuration and
real gateway with a synthetic backend. **Actually validated on Halo:** GPU
loads, chat/SSE, tools, model switching and long synthetic prompts below.
Cloning the repository does not install the private service or transfer tools,
weights, keys, profiles, firewall rules or client configuration.

## 2. Observed preflight

- GMKtec EVO-X2, Ryzen AI Max+ 395, Radeon 8060S, `gfx1151`.
- BIOS EVO-X2S 1.13; kernel `7.2.5-1-cachyos`; RADV Mesa `26.2.2-arch3.2`.
  Both `vulkaninfo --summary` and `rocminfo` recognized the GPU.
- Approximately 123.5 GiB visible RAM, 2 GiB VRAM and 61.73 GiB GTT.
  Initially about 121 GiB available RAM and 1.28 TiB free disk space.
- KFD/render devices were accessible with existing broad permissions. No
  device rules, firmware, UMA, GTT or IOMMU settings were changed.
- Docker/Compose 29.8.0/5.5.1. GitHub CLI and Docker permissions initially
  blocked installation. After CLI authentication and Docker group membership,
  a refreshed login or `newgrp docker` was required for the operator shell.
- Lemonade 11.9.0 health returned HTTP 200 with no residents or pins, but
  client connections existed. Empty residency does not reserve a maintenance
  window or establish absence of clients.
- Current Lemonade configuration was under `$HOME/.config/lemonade/`, with
  `config.json`, `recipe_options.json` and `user_models.json`, rather than the
  historical cache location. Private configuration, unit and API snapshots
  were saved with copy hashes verified.

Launching the workspace with sudo changes identity and fails private-directory
ownership checks. Do not work around that with world-writable permissions or
ownership changes. Membership of the Docker group is effectively root authority.

## 3. Exact artifacts and compatibility fixes

| Artifact | Verified reference |
| --- | --- |
| llama-swap | v255, reported commit `7761aa1`; archive and installed binary checked against the installer's pinned SHA256 |
| Cockpit | `6959d068c020f3f33bfb8ef743e7ba44a6390dda`, version 2026.9.16.1218 |
| Vulkan toolbox | `docker.io/kyuz0/amd-strix-halo-toolboxes@sha256:c96266e8b29164f37e82b6b8a31f1ca4a044dc0b0c77c7ea5fefc861c9b541ef` |
| Image's llama.cpp | build 11011, commit `aa39d7a3e`, reported version 0.4.1-dev |
| Halogen | `ghcr.io/peonist-ai/halogen-flash-server@sha256:760691880fecbf07f25e6b067cb5cc70e6a9ae11f280ca4725d3878e68821bd2`, version 0.11.3 |

The Halogen image label's revision `8215baa74dab` did not resolve through the
GitHub API. Its actual entrypoint was extracted and inspected without GPU
execution. Separately consulted upstream documentation is not represented as
source precisely matched to that revision. The closed engine was not rebuilt.

Repository changes:

1. The selected Vulkan binary rejects `--no-mmap`; private `load_mode: "none"`
   selects `--load-mode none`, while omission retains the older contract.
2. Cockpit passed named `video` and `render` Docker groups. This Halogen image
   lacks `render`; the failure was reproduced using `/bin/true`, no GPU or
   weights. The launcher adapter maps them to host device GIDs without editing
   the installed upstream package. It targets the initial single-GPU topology.
3. Setting Context 32768 and Slots 1 in Cockpit left **KV Pool at 524288**.
   The pool was explicitly corrected before the first successful load.
4. Profiles support explicit `halogen_overlay`, `halogen_tokenizer` and
   `halogen_max_tok`, validating relative paths, symlink containment,
   `tokenizer.json` presence and prefill-arena limits.
5. Generated discovery now announces effective context and output budgets.

Cockpit dependencies were resolved in a private venv and recorded in a private
manifest. `pip check` passed. The warning that `huggingface_hub` no longer
provides the `cli` extra did not prevent installation/downloads. Transitive
resolution is not claimed to be byte-reproducible.

## 4. Real inference and memory

Coder reused its existing 18556689568-byte Q4_K_M GGUF. Its header and local
SHA256 were checked, but the hash was not independently matched to upstream.
Direct GPU inference, gateway auth/UI, SSE, tool calls and follow-up, client
disconnect, unload and memory reclamation were exercised. Restarting Lemonade
restored the observed empty resident state, then Docker serving resumed.
Original Lemonade configuration remained byte-identical during this rollback.

Cockpit downloaded **W4B Quality**, eight files totalling 117.88 GiB: HGN,
quality overlay and tokenizer. Completeness/file sizes were checked against
the catalogue, not full hashes of all 118 GiB. The vision sidecar was absent;
vision inference is not validated. Pulling an image is not downloading weights.

Initial Halogen load: context/pool 32768, one slot, arena 32768. Startup
reported approximately 68 GiB registered weights, 0.9 GiB KV and 21 GiB work
memory, 89.9 GiB combined. Direct chat returned in about 1.8 seconds. The
explicit artifacts were then migrated to llama-swap; Halogen → Coder → Halogen
exclusive switching, SSE and real tool calls/follow-up passed.

**Correction to the initial estimate:** comparing 68 GiB registered weights
directly with 61.73 GiB reported GTT did not prove loading impossible. Halogen
registers mapped weights; it loaded without increasing GTT. Conversely,
`MemAvailable` can count registered weights as reclaimable cache and overstate
headroom. Use engine diagnostics, driver memory, pressure and observed behavior
rather than one number.

### 128K trial

Output stayed 8192 and concurrency stayed 1. Halogen context/pool increased
to 131072 while its prefill arena decreased to **16384**: startup reported
68 GiB weights, 3.6 GiB KV, 12.2 GiB work memory, **83.7 GiB total**, about
30.2 GiB left. A smaller prefill arena is not a smaller conversation window
or response budget.

| Synthetic SSE trial | Actual input | Actual output | First content | Total |
| --- | ---: | ---: | ---: | ---: |
| Halogen | 105074 tokens | 34 tokens, including 27 reasoning | 77.63 s | 77.73 s |
| Coder Vulkan | 120033 tokens | 6 tokens | 1452.46 s | 1452.81 s |

Both recalled a control key from the beginning and completed with `[DONE]`.
The same repetitive text produced different tokenizer counts. This is not a
causal comparison of equivalent engines, broad retrieval quality, full-window
131072 validation or soak. Coder was too slow for that long case and was
removed from serving at the operator's request; its image, weights and backups
remain. Only Halogen is served in the final configuration.

## 5. Discovery and client context budgets

Halogen's `/v1/models` entry includes:

```json
{
  "id": "flash-halogen",
  "context_length": 131072,
  "context_window": 131072,
  "meta": {
    "n_ctx": 131072,
    "llamaswap": {"max_output_tokens": 8192, "type": "model"}
  }
}
```

v255 transforms `capabilities.context` and `metadata` into these response
fields. Regression tests check the real binary's response, not only generated
configuration. Publication does not clamp `max_tokens`: at 32K, requests with
24732 and 25188 input tokens plus 8192 requested output were rejected. Input,
history, tools, reasoning and output share the context window.

Publishing limits did not resolve the operator's client issue on its own.
Upstream OpenCode code was inspected, not the remote installed version and
effective configuration. Private fragments were prepared without replacing
remote client files:

- OpenCode: `halo/flash-halogen`, context 131072, input limit 122880, output
  8192, automatic compaction and pruning enabled.
- Crush: conservative client window 122880, primary output 8192, summary
  output 4096, automatic summarization. Halogen fills both slots to avoid
  switching engines for summaries; discovery is disabled in that fragment
  to retain explicit client headroom.

Crush fragment syntax was checked, not remote compaction behavior. Arbitrarily
large tool results can still overflow context. Merge private client changes;
do not replace unrelated providers or whole client configurations.

## 6. Network and laboratory exception

Public defaults remain authenticated loopback plus a filtered TLS edge.
Tests exercised a localhost certificate, trust/name validation, HTTPS inference
and rejection of wrong keys/administrative routes. That test edge was removed;
no LAN TLS deployment or remote client CA installation is claimed.

The operator subsequently requested direct LAN HTTP UI access and removal of
the API key. Private serving binds `<HALO_LAN_IP>:18080`; UFW allows TCP only
from `<LAN_CIDR>` to that address. The firewall was not disabled. The operator
applied the rule from an authorized terminal after the tool rejected that
command. Access from another computer was confirmed.

**This is an accepted laboratory exception, not a safe deployment default.**
HTTP does not encrypt prompts/responses and any permitted client can infer
and administer without a password. No router/NAT audit was performed; a local
rule does not establish absence of external exposure. Previous keys were kept
privately for rollback. The public generator still enables authentication and
`start.sh` still selects standard loopback configuration; the actual service
uses a separate private launcher. Never launch both simultaneously.

## 7. Persistent service and rollback

Early foreground gateways disappeared with their session; logs showed an
interrupt signal and clean shutdown rather than firewall failure. They were
replaced with an enabled **user `llama-swap.service`**, linked to a private
unit under `data/` and pulled in by `default.target`. Linger already existed.

Applied settings: `Restart=always`, `RestartSec=10`,
`StartLimitIntervalSec=0`, `TimeoutStartSec=30`, `TimeoutStopSec=120`,
`KillMode=control-group`, `UMask=0077`, private working directory.
`ExecStartPre` checks Docker; `ExecStopPost` uses ownership-checked
`runtime.py stop` for Halogen only. The launcher retains 128K, the approved
LAN bind and no-key exception, without putting secrets in process arguments.

The user manager had stale groups predating Docker authorization. `sg` was
absent; `/usr/bin/newgrp docker -c` was verified and used for unit commands.
The gateway is not run as root, and socket permissions were not loosened.
System Docker was already enabled. If Docker or the chosen IP is not ready
at boot, the unit retries; persistent failures require journal inspection.

User `lemond.service` is **disabled/inactive**; system Lemonade was already
disabled. Lemonade was neither removed nor masked, so manual starts remain
possible. Stop llama-swap, verify owned containers exited and memory recovered
before starting it. Do not allow competing lifecycle owners.

Operator terminal commands, without sudo:

```bash
systemctl --user status llama-swap.service
journalctl --user -u llama-swap.service -n 100 --no-pager
systemctl --user stop llama-swap.service
systemctl --user start llama-swap.service
```

For Cockpit experiments, stop admission/the service, wait for unload, then
run `manage.py cockpit` from the repository root. Close servers and TUI before
restarting serving. The cooperative lock does not isolate manual Docker,
training or other users. `manage.py unload` targets standard loopback and
must not be assumed to work for the private LAN bind; use the UI or stop the
service instead.

Lemonade rollback: stop/disable llama-swap, verify containers and reclaimed
memory, compare originals against the private snapshot, restore only changed
files, then enable/start the observed Lemonade unit. Do not blindly restore
historical model residency, prune volumes or delete weights. A clone does not
recreate private units, systemd links, keys, active profiles or firewall rules.

Revalidation for this report found Lemonade disabled/inactive, llama-swap
enabled/active with zero recorded restarts, Halogen-only 131072/8192 discovery
and 21 successful chats in a recent 200-line service journal sample. Initial
post-service smoke attempts received 429 while concurrency 1 was occupied;
operator traffic was not interrupted to force a test. **No host reboot was
performed:** cold boot and real crash recovery remain unverified. Halogen
loads on demand rather than being preloaded by the unit.

## 8. Logs and proposed optimizations

An earlier one-hour sample had 61 backend requests, no HTTP 4xx/5xx, OOM or
restarts, and no matching kernel GPU/OOM faults. A separate gateway sample
had 72 chats, median 9.3 s and maximum 58.2 s: heterogeneous wall times, not
TTFT or a benchmark. Five KV cache evictions were recoverable but can require
prefill again. Zero instantaneous memory PSI does not prove pressure-free
operation throughout a workload. CPU Tctl 77-84 °C and GPU sensor 37 °C are
not equivalent measurements or evidence of throttling; measure under load.

Initial plan before profile C. Section 10 updates the N=4/pool 524288 trial;
the other alternatives were not executed:

| Step | Proposal | Required evidence |
| --- | --- | --- |
| N=2 | Pool 262144, two slots, context 131072 | About +3.6 GiB KV plus slot state; measure TTFT and per-request/aggregate throughput |
| Moderate N=4 | Pool 262144, roughly 64K per simultaneous request | Not four guaranteed 128K requests; test cache eviction/cancellation |
| Long N=4 | Pool 524288 | Validate RAM, file cache and latency headroom before promotion |
| Persistent cache | Separate private directory | Restart benefit, writes, privacy and cleanup |
| Service | Host reboot and controlled recovery | Boot API, fresh load, Docker/groups/network and engine-failure behavior |

The initial runtime hardcoded one slot, pool equal to context and concurrency
1 in gateway/model. The later extension adds validated Halogen `slots` and
`kv_pool` and updates gateway admission; see section 10. Editing Cockpit Slots
or advertised context alone is insufficient. GTT was not expanded and IOMMU
was not disabled to obtain concurrency.

## 9. Repository validation and publication

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

The initial handoff passed 28 inference/control tests; profile C brings that
to 29. All 14 documentation tests also pass,
including optional installed-binary checks. The private unit passed
`systemd-analyze --user verify`. The complete site still fails on the existing
EngramHalo `.dockerignore` link outside its publication allowlist. The
allowlist was not broadened and fixture success is not site-build success.

Remaining work: cold boot, soak, matched N=1/N=2/N=4 comparison and four long
simultaneous contexts, long coding-task quality, actual client
compaction, LAN TLS if scope changes, other runtimes, vision and training.
Coder ROCm/vLLM and Halogen vision were not promoted. Older private files and
backups retain historical names even though only Halogen is served at close.

## 10. Applied profile C and subsequent log review

### Effective configuration and admission contract

The operator selected C directly, without first executing a comparative sweep:

| Parameter | Applied value |
| --- | ---: |
| Maximum context per request | 131072 |
| Shared KV pool | 524288 |
| Engine slots | 4 |
| Prefill arena | 16384 |
| Maximum output | 8192 |
| llama-swap global concurrency | 4 |
| llama-swap model concurrency | 4 |

Backend and gateway remain under the existing user service, without API keys
under the preceding LAN exception. A private backup of the one-slot profile
and gateway was saved before the controlled restart. Only Halogen is listed.
The service remains enabled; startup logs confirmed the full pool without an
observed automatic downsize.

Implementation accepts Halogen `slots` from 1 to 8 and `kv_pool` from `context`
to 1048576. Booleans, strings, out-of-range values and these fields on other
engines are rejected. Omission retains one slot/pool equal to context. Model
admission follows slots, global admission takes the maximum across enabled
profiles, and exclusive engine switching is retained. Discovery context is
still **per request**, not the shared pool size.

At startup, the engine reported 68.0 GiB registered weights, 14.4 GiB KV and
12.5 GiB work memory, **94.8 GiB total**, with approximately **19.3 GiB** left.
These are engine diagnostics, not equivalent GTT or `MemAvailable` readings.
The pool budgets four 128K requests including output; filling all four at once
has not been tested.

### Synchronized four-agent smoke

Two consecutive rounds of four barrier-launched requests through llama-swap.
Each request had 7775 input tokens and 512 output tokens, including 26-27
reasoning tokens. Nonempty content, usage and SSE `[DONE]` were checked:
**8/8 completed**.

| Round | First content per request | Per-request duration | Batch wall time |
| --- | --- | --- | ---: |
| Initial | 28.19-28.41 s | 54.67-54.89 s | 54.90 s |
| Repeated | 1.33-1.53 s | 26.90-27.10 s | 27.11 s |

The second round reported **7775 cached tokens per request**. First content
is not the first reasoning token, and batch wall time is not decode speed.
Response intervals overlapped. This validates a concurrent smoke and reuse of
those prefixes, not four occupied 128K contexts, fairness, coding quality, an
N=1 comparison or soak. C is not claimed to be the optimum.

### Observation window and error classification

Read-only review on **2026-09-17 at 13:51:32 UTC**, requested window
**12:51:32-13:51:32 UTC**. The current container started at 13:07:01 UTC, so
its logs cover about 44 minutes; the service journal includes earlier activity
before the profile switch. Counts are not matching populations and must not
all be attributed to profile C.

| Source | Result within the requested window |
| --- | --- |
| Current backend | 366 lines; 92 HTTP 200 accesses including 90 chats; no recorded HTTP 4xx/5xx |
| Gateway | 373 lines; 361 HTTP 200 accesses including 105 chats; no recorded HTTP 4xx/5xx |
| Gateway chat durations | n=105, minimum 3.17 s, median 10.61 s, maximum 211.86 s |
| Container | running, `OOMKilled=false`, zero container restarts |
| Kernel journal | No GPU reset, ring timeout, GPU fault or OOM pattern matches in that window |
| Backend cache | No `forgot the region` or `no room` lines in the current-container sample |

Chats mix laboratory traffic and tests rather than matched prompts. The
211.86-second maximum alone identifies neither a regression nor its cause.
HTTP/log success does not establish response quality or every tool's success;
zero container restarts does not validate service/host crash recovery.

One **upstream Python API `DeprecationWarning`** was present, not an inference
failure. Two lines contained `failed`: one reported zero failures while
pinning weights, the other **69 memory-compaction stalls with 12 failed
attempts** when reserving KV. Startup succeeded. These counters are not failed
requests, OOM events or conversation-compaction failures. They justify watching
fragmentation and headroom on future starts rather than hiding the warnings.

Final instantaneous reading: GTT used **35711561728 bytes, about 33.26 GiB**,
GPU busy 96%; CPU/memory PSI 10/60/300-second averages zero. I/O PSI `some`
0.59/0.96/0.85 and `full` 0.59/0.94/0.83 percent. There were I/O stalls during
activity, not proof of saturation or latency causation. This snapshot is not
extrapolated to the entire window or a RAM-headroom guarantee.

### What the endpoints expose

The internal backend `/health` returned:

```json
{
  "status": "ok",
  "slots": 4,
  "slot_ctx": 131072,
  "kv_pool_positions": 524288,
  "in_flight": 1,
  "queued": 0,
  "busy": false,
  "busy_for_s": 25.9,
  "max_tokens_cap": 8192
}
```

`busy=false` coexisted with `in_flight=1`; it must not be read as no requests
or four free slots. Configured slots, in-flight requests, queues and KV
positions are different quantities. Even slots minus in-flight requests is
not an admission guarantee: it is a snapshot and KV capacity also matters.

llama-swap `/v1/models` still exposes context 131072 and output 8192, but
**not total/free slots, queues or KV pool size**. Halogen exposes the dynamic
fields above on its internal loopback endpoint. That port was not opened to
the LAN, and no public aggregate endpoint was added. Publishing static capacity
and exposing dynamic state would be separate tasks; clients cannot infer
available concurrency from the current catalogue alone.

### Next checks, not changes applied by this review

1. Compare N=1/N=2/N=4 with matched input/output, cold/warm cache, latency
   percentiles and individual/aggregate throughput.
2. Exercise four progressively longer inputs and a fifth request, checking
   queue/rejection, cancellation and recovery within pool capacity.
3. Soak while tracking actual memory, kernel compaction, I/O and temperatures.
4. Test cold boot and service recovery in a reserved maintenance window.
5. Design total-slot discovery and dynamic state without fictional availability
   or accidental administrative exposure.

This review did not restart services, change slots, load new models or modify
firewall, BIOS, GTT or IOMMU. Raw results/backups remain private; no prompts,
keys, private addresses or complete logs were included.
