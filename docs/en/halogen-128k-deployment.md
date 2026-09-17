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

| Layer | State at intervention close |
| --- | --- |
| Hardware | Actual Halo confirmed, native Linux and `gfx1151` |
| llama-swap | v255, enabled and active user service |
| Served model | Only `flash-halogen`, W4B Quality, context 131072 |
| Output | Configured maximum 8192, sharing context with input |
| Concurrency | One slot, KV pool 131072, gateway/global model limits 1 |
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

The following plan is **not applied**:

| Step | Proposal | Required evidence |
| --- | --- | --- |
| N=2 | Pool 262144, two slots, context 131072 | About +3.6 GiB KV plus slot state; measure TTFT and per-request/aggregate throughput |
| Moderate N=4 | Pool 262144, roughly 64K per simultaneous request | Not four guaranteed 128K requests; test cache eviction/cancellation |
| Long N=4 | Pool 524288 | Validate RAM, file cache and latency headroom before promotion |
| Persistent cache | Separate private directory | Restart benefit, writes, privacy and cleanup |
| Service | Host reboot and controlled recovery | Boot API, fresh load, Docker/groups/network and engine-failure behavior |

Current runtime hardcodes one slot, pool equal to context and concurrency 1
in gateway/model. N=2 requires extending these contracts and tests, not merely
editing Cockpit Slots or increasing advertised context. No GTT expansion or
IOMMU disablement is proposed for concurrency.

## 9. Repository validation and publication

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

At handoff, 28 inference/control tests and 14 documentation tests pass,
including optional installed-binary checks. The private unit passed
`systemd-analyze --user verify`. The complete site still fails on the existing
EngramHalo `.dockerignore` link outside its publication allowlist. The
allowlist was not broadened and fixture success is not site-build success.

Remaining work: cold boot, soak, N=2/N=4, long coding-task quality, actual client
compaction, LAN TLS if scope changes, other runtimes, vision and training.
Coder ROCm/vLLM and Halogen vision were not promoted. Older private files and
backups retain historical names even though only Halogen is served at close.
