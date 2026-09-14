# Halo Strix configuration reference

[English index](README.md) |
[Espanol](../configuracion-reutilizable-halo-strix.md) |
[Parameter dictionary](lemonade-parameter-reference.md) |
[Project status](project-status.md) |
[Staged setup](setup-guide.md) | [Models and experiments](model-guide.md)

**Positive historical baseline: 2026-09-04. Prepared for publication: 2026-09-07.**
This reference consolidates observations dated August 25 through September 4.
No host was contacted, packages changed, model loaded or service restarted to
prepare it. Versions are dated evidence, not perpetual installation pins.

**Open incident:** HTTP 403 was reported on **2026-09-04T18:47:07.402Z**, after
the positive baseline. No endpoint, client, cause or confirmed resolution is
available. Do not assume that it was the CORS issue corrected on August 25.
This anonymized report is preserved here without private record identifiers.

**Status vocabulary:** observed = historical measurement; configured =
persisted setting or supplied template; recommendation = future action;
pending = unverified, missing or contradictory. None means "currently live".

## Placeholders and command safety

Private topology and secrets are excluded. Replace values privately before
running any example; never send literal placeholders to Lemonade.

| Placeholder | Meaning |
| --- | --- |
| `<HALO_HOST>` | Authorized LAN listener address |
| `<SSH_USER>` | Authorized service/SSH account, not a bundled default user |
| `<LAN_CIDR>`, `<LAN_GATEWAY>`, `<LAN_DNS>` | Operator-managed network values, not installation defaults |
| `<CLIENT_HOST>` | Client address when diagnosing a request |
| `<LEMONADE_ORIGIN>` | Exact browser page origin: scheme, host and port, without an API path |
| `<UNSLOTH_ORIGIN>` | Separately authorized Studio page origin; no proxy or public domain is implied |
| `$HOME` | The Linux service user's home, expanded to an absolute path before saving configuration |

Linux command examples use **Bash**, not Fish or PowerShell. For read-only API
checks, set the following in the client shell, replacing the quoted value:

```bash
HALO_HOST='<HALO_HOST>'
case "$HALO_HOST" in ''|*'<'*|*'>'*) echo 'Set HALO_HOST first' >&2; exit 1;; esac
LEMONADE_URL="http://${HALO_HOST}:13305"
LEMONADE_ORIGIN="$LEMONADE_URL"
CODER='Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
THINKING='Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M'
```

This prepares variables only. POST requests, chat, startup, restarts and
configuration changes below require a separately approved maintenance window.
Do not publish complete configuration, logs, cookies, auth headers or backups.

## Hardware and dated software inventory

| Item | Evidence |
| --- | --- |
| Platform | GMKtec EVO-X2; AMD Ryzen AI Max+ 395, 32 logical CPUs |
| GPU | Radeon 8060S, `gfx1151`, RDNA 3.5 Strix Halo |
| BIOS | `EVO-X2S 1.13`, firmware date 2026-06-26 |
| Memory | 128 GiB physical; `iGPU Configuration=UMA_SPECIFIED`, frame buffer **2 GiB** |
| Visible RAM / GPU memory | Approximately **123.5 GiB** RAM; VRAM **2147483648 B**; GTT **66283167744 B**, approximately **61.73 GiB** |
| Storage | Nominal 2 TB NVMe, approximately 1.8-1.9 TiB; Btrfs root |
| Host stack, observed 2026-08-25 | CachyOS, kernel `7.2.0-1-cachyos`, Mesa/`vulkan-radeon` `3:26.2.1-1`, firmware/ucode `20260810-2` |
| Host ROCm / Docker, 2026-08-25 | ROCm **7.2.4**; Docker Engine **29.7.2** |
| Lemonade, documented 2026-09-04 | **11.8.1**, following 11.7.0/package `11.7.0-2.1` |
| Managed inference backend | `llamacpp:vulkan`, **b10375 / ba360efe1**, built 2026-08-12 |

UMA survived a power cycle on August 26. The earlier Auto setting exposed
approximately 62 GiB RAM and 31 GiB GTT; that is not the selected baseline.
No manual TTM/GTT increase was part of the final configuration.

Vulkan remained preferred after the short benchmark: PP512/TG128 were
5263.79/114.39 tok/s for Vulkan and 5448.84/102.51 for HIP, using the small
Qwen3-1.7B-Q8_0 model. HIP improved PP about 3.5% but regressed TG about 10.4%.
Do not extrapolate these rates to 30B models or claim a completed thermal soak.
Container ROCm 7.14 is **not** the host's native ROCm 7.2.4 installation.

## Service, network and persisted files

**Historically observed/configured:** `lemond.service`, **systemd user scope**,
enabled/active, `Linger=yes` reconfirmed on September 4. Earlier `Linger=no`
reports are superseded. This is not proof of current cold-boot readiness or
automatic model preloading after restart.

| Purpose | Sanitized path or setting |
| --- | --- |
| CLI / daemon | `/usr/bin/lemonade`, `/usr/bin/lemond` |
| Persistent configuration | `$HOME/.cache/lemonade/config.json` |
| User catalog | `$HOME/.cache/lemonade/user_models.json` |
| Download cache: `models_dir` | `$HOME/ai/lemonade/models` |
| Recursive local GGUF scan: `extra_models_dir` | `$HOME/ai/models/smoke` |
| Managed backend | `$HOME/.cache/lemonade/bin/llamacpp/vulkan/llama-server` |
| CORS environment file | `$HOME/.config/lemonade/conf.d/allowed-origins.conf`, mode 0600 |
| Historical config backup | `$HOME/.cache/lemonade/config.json.bak-20260826T072912+0200`, mode 0600; current existence unverified |

`models_dir` must be an **absolute expanded path**. Lemonade 11.7 treated
literal `~` as relative and attempted an invalid path beneath `/usr/bin`.
`extra_models_dir` has a different purpose; changing it can hide local GGUFs.
The exact storage file for all per-model options and any separately saved
host payload files are **not established** by the published evidence.

Historical network settings: `host=<HALO_HOST>`, `port=13305`,
`broadcast=false`. The API listened on a specific LAN IP, **not**
`127.0.0.1:13305`. Port 9000 was auxiliary. Managed backend listeners were
`127.0.0.1:8001` for Coder and `127.0.0.1:8002` for Thinking; these are
observed internal assignments, not stable public client endpoints.

The documented UFW rule limited TCP/13305 to an authorized LAN/interface.
HTTP was plaintext, without an API key or dedicated reverse proxy evidenced.
**TLS is not validated.** This describes a historical risk, not permission
to expose the service to an untrusted network.

The packaged user unit reads:

```ini
EnvironmentFile=-%E/lemonade/conf.d/*.conf
```

The CORS file's `LEMONADE_ALLOWED_ORIGINS` contained the exact allowed
browser page origin, historically `http://<HALO_HOST>:13305`. It is not the
client computer's address simply because that computer accesses the API.
The variable accepts comma-separated origins; do not use `*`. Changes to
this environment file require a user-service restart to take effect. Use the
[setup procedure](setup-guide.md#lemonade-installation-and-networking) rather
than writing literal variables into an environment file.

## Exact resident model profile

| Setting | Coder | Thinking |
| --- | --- | --- |
| Load `model_name` | `Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M` | `Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M` |
| Checkpoint | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q4_K_M` | `unsloth/Qwen3-30B-A3B-Thinking-2507-GGUF:Q4_K_M` |
| Weight quantization | `Q4_K_M` | `Q4_K_M` |
| Total `ctx_size` | **196608** | **98304** |
| `--parallel` slots | **3** | **1** |
| Approximate context per active request at full concurrency | **65536**, dynamically shared | **98304** |
| K/V cache | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| Measured GTT | 25.62 GiB | 22.40 GiB |
| Reasoning mode | non-thinking | always-thinking; budget **16384** |
| Pinning at the observation | `false` | `false` |

`max_loaded_models=2` limits **resident models**, not slots or requests. It
was changed in-place, persisted in `config.json` and checked against
`GET /internal/config` and health's `max_models.llm=2`; no restart was needed.
`pinned_helper_models` describes a separate pool and is not evidence of
Coder/Thinking being pinned.

The following are exact documented **mutable API requests**, not read-only
checks. Verify idle state, current catalog, memory, backups and resolved
options before using them. The URL variables are defined above.

```bash
curl --fail-with-body -sS -X POST "$LEMONADE_URL/internal/set" \
  -H 'Content-Type: application/json' --data '{"max_loaded_models":2}'

curl --fail-with-body -sS -X POST "$LEMONADE_URL/api/v1/load" \
  -H 'Content-Type: application/json' --data '{
    "model_name": "Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M",
    "ctx_size": 196608,
    "llamacpp_backend": "vulkan",
    "llamacpp_args": "--parallel 3 --kv-unified --flash-attn on --cache-reuse 256 --cache-type-k q8_0 --cache-type-v q8_0",
    "merge_args": true,
    "save_options": true
  }'

curl --fail-with-body -sS -X POST "$LEMONADE_URL/api/v1/load" \
  -H 'Content-Type: application/json' --data '{
    "model_name": "Qwen3-30B-A3B-Thinking-2507-GGUF-Q4_K_M",
    "ctx_size": 98304,
    "llamacpp_backend": "vulkan",
    "llamacpp_args": "--parallel 1 --kv-unified --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning-budget 16384",
    "merge_args": true,
    "save_options": true
  }'
```

The managed processes additionally had `-m <GGUF> --ctx-size <total>
--port <internal> --jinja --metrics`. Do not launch a competing standalone
server using those internal ports. Exact GGUF paths and HF revisions are
retained in the [JSON profile](../../config/halo-strix.reference.json):

- Coder revision `b17cb02dd882d5b6ab62fc777ad2995f19668350`;
  `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf`, 18556689568 bytes.
- Thinking revision `a9b37aaac12b2bd0098783a443429543dd76a14d`;
  `Qwen3-30B-A3B-Thinking-2507-Q4_K_M.gguf`; exact file size not recorded.

The Coder recipe addresses the user entry
`user.Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M`, not the built-in
`Qwen3-Coder-30B-A3B-Instruct-GGUF`. Both entries can reference the same
artifact. They are **not interchangeable aliases for catalog operations**.
Do not delete one to repair visibility; verify the exact published ID first.

## Context, cache, reasoning and precedence

- `--kv-unified` shares the **total** KV pool dynamically. Coder does not
  allocate 196608 tokens independently for each of three slots.
- The 3+1 layout is not evidence that four simultaneous generations improve
  latency. The historical runbook provisionally recommends **at most three
  active requests combined**; this is not an enforced Lemonade limit.
- KV Q8 does not change weight quantization. `--cache-reuse 256` was explicit
  only for Coder. No final `cache_prompt`, `--cache-prompt` or RAM-cache
  setting is documented; do not add one.
- Prefix KV reuse is independent of HTTP keep-alive. A historical report of
  approximately 99% prefix reuse concerned an earlier four-slot setup, not
  a benchmark of this dual-model profile.
- `--reasoning-format auto` was the managed binary's default output parser,
  not a reasoning switch. It cannot make Coder think or disable Thinking.
  Check both `content` and `reasoning_content`, plus `finish_reason`.
- `save_options=true` requests persistence. `false` was used for trials
  without overwriting saved options. `merge_args=true` was documented, but
  the **full global/model/request precedence and duplicate-flag merge
  algorithm are unknown**. Compare resolved options and process arguments;
  do not assume a request clears previous flags.
- The old global context 32768, Coder 262144/four slots and the September 3
  single-model proposal (65536, later 98304/Q8 as a trial) are not this
  baseline. Coder's 65536-per-request estimate here is **196608 / 3**.

The dual observation used **51557068800 B = 48.02 GiB GTT** and
**2043170816 B VRAM**, leaving approximately **13.71 GiB GTT**. Disk size is
not runtime memory: weights, KV and compute buffers all matter. Do not assume
room for another large model or concurrent training.

## Clients and read-only checks

**OpenAI-compatible base URL:** `http://<HALO_HOST>:13305/v1`.
Use it as the compatible provider's `baseURL` in OpenCode, with the exact
catalog ID. This is a connection recommendation, not proof that an OpenCode
installation was already configured. Do not invent an API key to fill a form.

| Method and route | Meaning |
| --- | --- |
| `GET /` | Integrated Lemonade Web App / AI Model Manager, not Swagger |
| `GET /api/v1/health` | Service and loaded-backend health |
| `GET /v1/models` | Catalog; downloaded/listed does not mean resident |
| `GET /v1/models/<ID>/options` | Resolved options; route verified in 11.7, recheck version compatibility |
| `GET /internal/config` | Effective configuration; internal, version-dependent |
| `GET /api/v1/downloads` | Download-job state; do not interrupt an active transfer |
| `POST /v1/chat/completions` | Inference; may auto-load or evict a model |

From the Linux service account, first inspect without changing anything:

```bash
systemctl --user show lemond.service -p ActiveState -p SubState -p UnitFileState
loginctl show-user -p Linger
ss -ltn
grep -E '^(MemTotal|MemAvailable):' /proc/meminfo
grep -H . /sys/class/drm/card[0-9]*/device/mem_info_{gtt,vram}_{total,used}
curl --fail-with-body -sS "$LEMONADE_URL/api/v1/health"
curl --fail-with-body -sS "$LEMONADE_URL/v1/models"
curl --fail-with-body -sS "$LEMONADE_URL/v1/models/$CODER/options"
curl --fail-with-body -sS "$LEMONADE_URL/v1/models/$THINKING/options"
```

Inspect `/internal/config` privately and compare only relevant settings.
Success requires HTTP 200, `status:"ok"`, both models in `all_models_loaded`,
`backend_alive:true`, `backend_health:"ready"` and `device:"gpu"`.
A successful HTML page or catalog alone is insufficient.

The CLI default historically attempted localhost while the API bound to LAN.
A connection failure from `lemonade config set` therefore did not prove that
the service was down. Explicit `--host`, `--port 13305`, `--no-discovery`
were used in the earlier path correction; verify the installed CLI syntax
before reuse, or use the API at the confirmed listener.

After an approved idle-window check, the existing Windows smoke can test a
resident model. **Repository contract updated on 2026-09-07: `-BaseUrl` and
`-Model` are required and have no defaults.** Supply both explicitly:

```powershell
powershell -File scripts\test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

Replace the quoted placeholder first. The script sends chat; it is **not
read-only**. Missing parameters do not select an endpoint or model.
Explicitly selecting a nonresident model can still trigger automatic loading
and evict a resident model by LRU. **Historical only:** the earlier script
had endpoint/model defaults, including `Qwen3-1.7B-Q8_0`; those defaults no
longer exist. The 16-token smoke validates connectivity and nonempty
content/reasoning, not model quality or sustained performance.

For a 403, first capture sanitized time, method, route, client behavior,
page origin and error body. Distinguish origin rejection, authentication,
proxy response and wrong route from inference failures before changing settings.

## Workspace persistence and limits

| Workspace | Dated status | Defaults and retained data |
| --- | --- | --- |
| [LLaMA-Factory](../../workspaces/llama-factory/README.en.md) | v0.9.5, commit `7af909522a951e3ad9f022ea6f88b6755257eaa5`, recorded 2026-08-31; Torch `2.12.0+rocm7.14.0`; configured, no LlamaBoard GPU smoke or real training established | `127.0.0.1:7860`, health `/`; `data/{hf-cache,models,datasets,outputs,cache,config,logs}` |
| [Unsloth Studio](../../workspaces/unsloth-studio/README.en.md) | Commit `e18a069c15cde98c7af77ccdb952254db8b0315d`; UI/imports/GPU/health/SPA validated 2026-09-01; Torch `2.11.0+rocm7.14.0`, HIP `7.14.60850`, Triton `3.7.1+git0263a6a6.rocm7.14.0`; no real training | `127.0.0.1:8888`, health `/api/health`; `data/{studio,hf-cache,projects,tmp}` |

Both templates use `SHM_SIZE=16g`, `/dev/kfd` and a configurable render node
(default `/dev/dri/renderD128`). They use different base-image digests; do not
swap Torch 2.12 into the documented Unsloth `<2.12` stack. These are template
defaults, not proof of a current LAN deployment.

**Template contract updated on 2026-09-07:** LLaMA-Factory can autodetect
`DEVICE_GID` when empty. Unsloth Studio's template also leaves it empty, but
Compose **requires an explicitly configured value and Studio does not
autodetect it**. After selecting the actual `RENDER_DEVICE`, measure
`stat -c '%g' "$RENDER_DEVICE"` and privately set `DEVICE_GID` to that numeric
result before starting Studio. No numeric render-group default is supplied
for Studio; do not confuse this supplemental group with the data owner's
`HOST_UID`/`HOST_GID`.

Bind mounts preserve data independently of the containers. Studio data includes
auth/DB, outputs, exports and runs: preserve it privately, never publish it.
Unsloth uses the host data owner's UID/GID and removes the bootstrap password
from the long-running process when an admin already exists. Do not retrieve
or include the password in this reference.

Unsloth has no installed `bitsandbytes`: **QLoRA 4-bit is unavailable**.
The FLA path warned of CPU fallback. LoRA BF16 remains unvalidated end-to-end.
The separate August 25 Torch matmul/backward smoke was not LLM fine-tuning.

Build and startup are separate. `start.sh` changes containers/directories,
and Studio startup can correct data ownership. LLaMA-Factory records
`.last-built-image`; Studio additionally records `.previous-built-image`
and accepts `RUN_IMAGE=last` or `previous`. An image ID restores the same
image, not identical firmware, host or data. Rebuilding is not bit-for-bit
reproducible because dependency repositories remain mutable.

## Manual restoration and unresolved work

1. Perform read-only checks first; compare versions, listeners, absolute
   paths, exact catalog IDs, resolved options, memory and running work.
2. Preserve private configuration/catalog/options backups with permissions,
   model artifacts, workspace data and built image IDs. Do not overwrite
   files or reconstruct services solely because they differ from this history.
3. In an approved window, restore only the necessary service/routing settings,
   confirm `max_loaded_models=2`, then review the two load requests above.
   Never import the whole documentary JSON into Lemonade.
4. Use the supported API/UI; verify merged options before and after loading.
   Environment changes may require restart; saving options does not prove
   automatic model preloading on boot.
5. Verify health, effective backend arguments and memory, then run a small
   resident-model smoke. If it fails, reverse the specific change from its
   backup and repeat read-only checks. Do not delete models/data as recovery.

Unresolved: the later 403; current health/cold boot/model preloading; prolonged soak;
real training; TLS/proxy; full option precedence; exact per-model options
storage. HIP inference and vLLM are not promoted. Qwen3.8-27B's loading
history is contradictory; Flash-Next's `qwen4exp` was unsupported by b10375.
See the [model guide](model-guide.md) before considering either.
Native Netdata and optional Cockpit were only recommended on August 26;
installation is not evidenced.

## Public source trail

- [Model comparison](../comparativa-qwen38-halo-strix.md), sections 2-5 and 10:
  hardware, final pair, exact requests, residency, reasoning and health.
- [Initial audit](../auditoria-ssh-inicial.md), inventory, UMA verification and
  post-move check: platform and persistence across power cycling.
- [HIP validation](../validacion-llamacpp-hip.md), final runtime/benchmark;
  [Vulkan validation](../validacion-llamacpp-vulkan.md), final short gate.
- [Lemonade validation](../validacion-lemonade-vulkan.md), catalog collision,
  concurrency/OpenCode, web UI, CORS and download-directory sections.
- [ROCm validation](../validacion-entrenamiento-rocm.md), container smoke.
- [Historical integrated setup](../setup-completo-halo-strix.md), sections
  7-16; [English workspace manuals](setup-guide.md#workspace-operation).

These sources retain dated historical results. Their conclusions do not
override a later unknown incident or resolve documentary contradictions.
