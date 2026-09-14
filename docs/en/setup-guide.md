# Halo Strix staged setup and recovery guide

[English index](README.md) |
[Spanish historical setup](../setup-completo-halo-strix.md) |
[Exact configuration](configuration-reference.md) | [Model guide](model-guide.md)

This is an English operational equivalent of the platform, inference and
training work documented between **2026-08-25 and 2026-09-04**, prepared on
2026-09-07. It is not a new installation log or a live inspection. All commands
are examples for an authorized operator; none were run on the host during
documentation work. A later September 4 HTTP **403 remains unresolved**.

## Scope and gates

Work in stages: read-only inventory, backup/recovery, platform, bounded Vulkan
validation, optional HIP comparison, Lemonade, then isolated training. Stop at
a failed prerequisite. Do not mix historical proposals with completed gates.

| Area | Completed evidence | Still not established |
| --- | --- | --- |
| Hardware/UMA | `gfx1151`, 2 GiB UMA, about 123.5 GiB RAM/61.73 GiB GTT, power-cycle persistence | Full RAM health certification |
| Vulkan/HIP | Both built/offloaded and benchmarked; Vulkan retained | Prolonged thermal soak or general HIP superiority |
| Lemonade | LAN API/UI, historical CORS repair, user service with linger, dual models | Current health after the later 403, cold-boot model preloading, TLS |
| Docker/ROCm | Exact-image Torch FP16/BF16 backward smoke | Real LLM training |
| LLaMA-Factory | Workspace, persistence, UI launch recipe and BF16 POC template | LlamaBoard GPU smoke or completed fine-tuning |
| Unsloth Studio | UI/imports/GPU/health/SPA | LoRA BF16 completion; QLoRA 4-bit availability |

The original plan proposed longer gates: four Memtest86+ passes, a 60-minute
Linux RAM test capped at 50% of initial `MemAvailable`, thermal stages of
20 minutes CPU/RAM/GPU and 60 minutes combined, a 2-hour inference baseline,
an 8-hour candidate soak, and training checkpoints at 20/200/1000 steps.
Those are **proposed acceptance criteria, not achieved results**.
It also proposed experimental GTT increases and QLoRA: neither supersedes
the final untouched GTT limit or the unavailable bitsandbytes stack.

The original service proposal required zero unexpected HTTP 5xx, crashes or
out-of-SLO timeouts during the 2-hour baseline and 8-hour candidate soak;
100% correctness on a predefined valid-request set; no more than 5%
unrecovered RAM/GTT after 20 load/unload/request cycles; and restart health
within 60 seconds, **plus separately measured model-loading time**.
TTFT/TPOT and quality targets must be defined before testing. These checks
were not all completed by a short PASS.

Before downloads/builds/training, budget the worst simultaneous footprint:
base weights, cache, datasets, checkpoints, merged FP16, GGUF exports,
temporary files, logs and backups. Preserve at least 20% free storage.
Use measured GTT, not disk size, for runtime admission. The original
training plan reserved at least 20 GB free RAM. No sustained load without
reliable sensor limits and temperature/clock/power monitoring.

CPU/APU goals in the original plan were below 90 C, with thermal investigation
stopped at 95 C; NVMe goals below 60 C, pause at 70 C. The bounded Vulkan
experiment used stricter stop points of CPU 90 C, NVMe 65 C and GPU edge
85 C. These are **historical test settings, not universal safe limits**.
Set a conservative GPU threshold from actual firmware/hwmon limits. Stop on
sensor loss, reset, OOM, thermal error or sustained clock collapse. The unusual
secondary NVMe sensor reading near 77.8 C had inconsistent limits and must
not be used as a universal thermal gate.

## Preflight and backup

### SSH trust and operator preparation

Use an authorized account and already provisioned authentication. Verify the
host-key fingerprint through a trusted independent channel before connecting.
Never publish fingerprints tied to this host, private keys or network values.
Do not accept a changed key automatically. The early laboratory record used
an explicitly authorized isolated TOFU file; that exception is not a public
deployment recommendation.

Example from a Bash client, after replacing all quoted placeholders:

```bash
HALO_HOST='<HALO_HOST>'
SSH_USER='<SSH_USER>'
SSH_PORT='<SSH_PORT>'
KNOWN_HOSTS_FILE='<VERIFIED_KNOWN_HOSTS_FILE>'
for value in "$HALO_HOST" "$SSH_USER" "$SSH_PORT" "$KNOWN_HOSTS_FILE"; do
  case "$value" in ''|*'<'*|*'>'*) echo 'Replace connection placeholders first' >&2; exit 1;; esac
done
ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
  -p "$SSH_PORT" "${SSH_USER}@${HALO_HOST}"
```

Do not use `StrictHostKeyChecking=no`/`accept-new`, overwrite a known key or
retry authentication blindly. Preserve console/local recovery access before
any boot, firmware, memory or networking change. The instructions below are
for Bash; the early Fish shell rejected POSIX syntax. Select the appropriate
shell rather than repeatedly executing a partially failed command.

### Minimal read-only inventory

Run these on the Linux host only in an authorized inspection. Review full
output privately: inventory tools can expose serials, hostnames and UUIDs.

```bash
uname -r
cat /etc/os-release
lscpu
free -h
cat /proc/cmdline
findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS /
lsblk -e7 -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
lspci -nnk
cat /sys/module/ttm/parameters/pages_limit
grep -E 'cwsr_size|ctl_stack_size' /sys/class/kfd/kfd/topology/nodes/*/properties
vulkaninfo --summary
sensors
ss -ltn
```

If already installed, inspect `rocminfo`, `hipconfig -R`, `hipconfig -l` and
`rocm-smi`. Their initial absence was not a hardware failure. Identify the
actual NVMe device before using privileged `smartctl`/`nvme smart-log`;
inspect BIOS/memory with `sudo dmidecode -t bios -t memory` only when needed.
Do not export raw results. A read-only SSH check is not a RAM stress test.

Expected historical inventory: GMKtec EVO-X2, Ryzen AI Max+ 395, Radeon
8060S, `gfx_target_version=110501`/`gfx1151`, Btrfs root. The full dated
software inventory is in the [reference](configuration-reference.md#hardware-and-dated-software-inventory).
If a different target is found, stop and reassess compatibility before using
this platform-specific recipe.

### Backup and rollback gate

Record installed packages and relevant configuration, partition/mount layout,
versions and model/image manifests privately. Keep an encrypted external
backup and test selective recovery before invasive changes. Keep weights,
datasets and runs outside system snapshots.

Historically, Snapper/Btrfs inspection returned permission/operation errors
even with elevation. Do not infer filesystem corruption, remount blindly or
claim manual snapshots were validated. Pacman hooks reported PRE/POST
snapshots, but they were not independently enumerated/recovered.

The verified fallback was a mode-0700 directory beneath the service user's
home, `halostrix-baseline-20260825`, containing `packages-explicit.txt`,
`packages.txt`, `etc.tar.zst`, checksums and subsequent package inventories.
The archive was mode 0600. **It may contain secrets and must never be
published.** Check its checksum and contents locally without logging them;
restore only selected files from a recovery console after preserving the
current configuration. Package lists inform a reviewed reconstruction, not
an automatic reinstall. A fresh installation needs its own backup; this
repository does not contain that private archive.

## UMA configuration

1. Confirm memory reporting before changing firmware. DMI was internally
   inconsistent: one capacity field reported 64 GiB, while eight memory
   entries summed to 128 GiB. The kernel exposed only about 62 GiB with a
   64 GiB firmware GPU carve-out; that did not prove missing RAM.
2. With explicit approval and physical console access, record the existing
   BIOS screens privately. Set `iGPU Configuration` to `UMA_SPECIFIED` and
   `UMA Frame Buffer` to **2 GiB**, the minimum available in this firmware.
   The original 512 MiB goal was unavailable.
3. Reboot and check `MemTotal`, VRAM and TTM/GTT as in the reference.
   Historical PASS: about 123.5 GiB visible RAM, 2 GiB fixed VRAM and
   61.7 GiB GTT; this persisted through a later power cycle.
4. Do not raise TTM/GTT just because a planning document mentioned 80/96 GB.
   If a newly measured regression is attributable to UMA, the documented
   rollback is restoring the prior BIOS Auto setting with approval and
   another reboot. It was not needed after the positive gate.

## Vulkan and HIP

### Native platform packages

Inspect existing package versions and the proposed transaction first. The
historical diagnostic installation added only `vulkan-tools`, `nvme-cli` and
`libnvme`; `lm_sensors` was already present. The coherent native ROCm
installation was `rocm-hip-runtime` and its 7.2.4 cohort, later including
`hipblas`/`rocblas` for development.

Do not replay an old full-upgrade command merely to reproduce these versions.
Review **package names and versions**, not the presence of `linux` inside a
repository URL. That substring caused a false-positive preflight rejection.
Use in-tree `amdgpu`; no AMDGPU-Pro, DKMS or `HSA_OVERRIDE_GFX_VERSION`.
Do not combine native ROCm 7.2.x with container userspace 7.14 on the host.
Kernel/firmware changes require their own compatibility review and boot rollback.
The original dated plan requested kernel >=6.18.4 or a specifically verifiable
CWSR/KFD backport; it is not an independently checked present-day support
matrix. Record the actual package/commit instead of calling a backport
"equivalent". Zram without simultaneous zswap, no initial HugeTLB tuning and
preserving the old bootable kernel were planning recommendations, not new
changes to apply during restoration.

### Vulkan source build and bounded test

The standalone build used the upstream llama.cpp `v0.3.0` release tarball
dated 2026-08-25. It is **not** the managed Lemonade b10375 binary.
Recorded configuration: Release, `GGML_VULKAN=ON`, `GGML_NATIVE=ON`,
`LLAMA_CURL=ON`, `CMAKE_DISABLE_FIND_PACKAGE_Git=TRUE`.
Prerequisites included CMake, Ninja, a compiler, Vulkan headers/loader,
shaderc and SPIR-V headers. Missing dependencies were installed only after
a clean reviewed transaction.

For a separately approved rebuild from already obtained, verified source,
the equivalent CMake configuration is:

```bash
SOURCE_DIR='<VERIFIED_LLAMA_CPP_SOURCE>'
case "$SOURCE_DIR" in ''|*'<'*|*'>'*) echo 'Set verified source path first' >&2; exit 1;; esac
BUILD_DIR="$HOME/ai/build/llama-cpp-vulkan"
cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON -DGGML_NATIVE=ON \
  -DLLAMA_CURL=ON -DCMAKE_DISABLE_FIND_PACKAGE_Git=TRUE
cmake --build "$BUILD_DIR" --parallel
```

This is a reconstruction of the recorded flags, not proof of a hermetic
rebuild. The final archive/binary/model manifest was not recovered as a
published artifact. Verify hashes against trusted upstream metadata and
retain a new manifest; do not invent missing checksums.

The public smoke artifact was `Qwen/Qwen3-1.7B-GGUF`,
`Qwen3-1.7B-Q8_0.gguf`, **1834426016 bytes**, Apache-2.0, public access.
Q4_K_M was not offered in that observed revision. Use an already verified
local copy; no download is necessary to check the existing installation.

Read the exact binary's help and enumerate devices first. A bounded
load-only check used `-ngl 999 -c 2048 -n 0 --single-turn --no-warmup`
with prompt `x`; the final log showed **29/29 layers offloaded** to
`Vulkan0: AMD Radeon 8060S Graphics (RADV STRIX_HALO)`.

The first generation attempt ran away, timed out and created a multi-GiB
log. Do not reproduce it. Use a prompt argument, no shared script stdin,
finite tokens, timeout and bounded log files. Example after checking paths,
an idle GPU and active thermal monitoring:

```bash
BIN="$BUILD_DIR/bin"
MODEL="$HOME/ai/models/smoke/Qwen3-1.7B-Q8_0.gguf"
LOG="$HOME/ai/logs/vulkan-check"
mkdir -p "$LOG"
test -x "$BIN/llama-cli" && test -r "$MODEL" || exit 1
timeout --foreground --signal=TERM --kill-after=10s 120s \
  bash -c 'ulimit -f 131072; exec "$1" -m "$2" -p "Reply briefly." \
    -ngl 999 -c 2048 -n 64 --temp 0 --single-turn --no-warmup --log-disable' \
  _ "$BIN/llama-cli" "$MODEL" >"$LOG/smoke.stdout" 2>"$LOG/smoke.stderr"
```

The historical runbook described its cap as 64 MiB per output file; verify
the active shell's `ulimit -f` units before reuse rather than assuming that
block counts mean bytes or the same size in every shell. Check exit status, nonempty
coherent output, GPU offload and post-run kernel events. A literal marker
was ultimately not required for functional PASS. Do not leave background
monitors unmanaged; if stopping is necessary, identify the exact process
first, not a name-wide kill.

Only after smoke/offload/thermal gates pass, benchmark the same model,
GPU offload, prompt 512, generation 128 and three repetitions:

```bash
"$BIN/llama-bench" -m "$MODEL" -ngl 999 -p 512 -n 128 -r 3
```

Historical Vulkan PP512 = **5263.79 +/- 10.83 tok/s**; TG128 =
**114.39 +/- 0.24 tok/s**. These were aggregate results, not individually
published samples. The final short gate was PASS; a long soak remained pending.

### HIP candidate and comparison

HIP configuration initially stopped at compiler-path/dependency gates.
The verified compiler was `/opt/rocm/lib/llvm/bin/clang`, owned by
`rocm-llvm 2:7.2.4-2.1`, with `HIP_PATH=/opt/rocm`. Validate ownership,
executable version and `hipblasConfig.cmake` before configuring a separate
build directory. The source records successful `cmake --fresh` and build,
but not a complete copy-ready HIP configure invocation: do not invent one
or assume the Vulkan flags are sufficient.

Check `rocminfo` for `gfx1151`, CMake cache, `ldd`/`readelf` linkage to
`libggml-hip.so`, `libamdhip64`, hipBLAS and rocBLAS. An overly literal
device-name gate originally missed a valid ROCm0/Radeon8060S identification;
correlate independent evidence rather than bypassing compatibility checks.
The final HIP load also offloaded 29/29 layers and passed a bounded smoke.

With the same benchmark workload, HIP PP512 =
**5448.84 +/- 173.67**, TG128 = **102.51 +/- 0.17 tok/s**.
PP improved about 3.5%, below the promotion threshold, while TG regressed
about 10.4%. **Keep Vulkan; HIP remains experimental for inference.**
Future comparisons need a frozen prompt set, three repeats, memory/error
checks, controlled concurrency and TTFT/TPOT/quality targets defined first.
Do not confuse logical overlap with simultaneous GPU execution.

## Lemonade installation and networking

### Package and user service

The historical package was `lemonade-server 11.7.0-2.1` from
`cachyos-extra-znver4`; the later observed runtime was **11.8.1**.
An approved install should first inspect `pacman -Si lemonade-server`,
the transaction plan, existing units and rollback inventory, then use the
package manager's supported installation path. No current repository version
or dependency resolution was checked for this publication.

The manual package transaction, **only after the plan and rollback are
approved and the distribution's update state is consistent**, is:

```bash
pacman -Si lemonade-server
pacman -Sp --print-format '%n %v' lemonade-server
```

Review that output first. If it matches the separately approved plan, install:

```bash
sudo pacman -S --needed lemonade-server
```

This does not pin 11.8.1 or reproduce a past repository snapshot. Stop if the
transaction unexpectedly changes kernel, firmware or other unapproved
components; do not force an old package into an incompatible dependency set.

The package supplied `lemonade`, `lemond`, user/system units and defaults
under `/usr/share/lemonade(-server)/resources`. Choose the **user**
`lemond.service`; do not enable both copies. Inspect `lemond --help`,
installed configuration documentation and the unit before startup. Establish
that the initial bind is restricted to loopback before starting; if that
cannot be established safely from the installed contract, stop.

The historical CLI required a **running daemon** for config/backend
administration. Trying to configure it while stopped failed. The successful
sequence was: start only the user unit temporarily, immediately verify
loopback health/bind, apply supported settings and managed Vulkan backend
selection, then restart/recheck before enabling persistent operation.
A complete native config dump/unit replacement and complete backend-install
CLI invocation are not supplied; inspect the installed help rather than
inventing them or importing the documentary JSON. Downloading a missing
managed backend is a separate reviewed action.

After preparation, temporary startup is an explicit state-changing operation:

```bash
systemctl --user start lemond.service
systemctl --user status lemond.service --no-pager
ss -ltn
curl --fail-with-body -sS 'http://127.0.0.1:13305/api/v1/health'
```

Only after the initial loopback/configuration gate passes should the operator
enable persistence and proceed with the approved LAN transition:

```bash
systemctl --user enable lemond.service
loginctl show-user -p Linger
```

With separate approval, `loginctl enable-linger "$USER"` enables persistence
for the current service account; verify its result rather than assuming it.
The sources record `Linger=yes`, not execution of that exact enable command.
A user service being active after login does not prove unattended boot or
automatic model loading.

### Absolute model paths and listener changes

Set `models_dir` to the expanded service-home download cache and retain
`extra_models_dir` for local recursive GGUF discovery. Make only the intended
directory, owned by the service user, and back up config before changing it.
Do not enter literal `~` or `$HOME` in a JSON config string.

For the historically supported CLI syntax, after verifying the actual listener:

```bash
lemonade --host "$HALO_HOST" --port 13305 --no-discovery \
  config set "models_dir=$HOME/ai/lemonade/models"
```

Use the connection variables from the
[reference](configuration-reference.md#placeholders-and-command-safety).
The original path correction was live/persistent without restart.
CLI defaults can still fail against localhost when only the LAN address
is listening; use the explicit endpoint or supported API.

The final settings were `host=<HALO_HOST>`, `port=13305`,
`broadcast=false`. Changing a listener is separate from changing runtime
model limits; plan access/rollback before restarting.

### LAN firewall, CORS and web UI

Do not copy private network values or open all interfaces by default.
The historical exposure used a specific LAN listener and a narrow UFW rule,
not a reverse proxy. For an independently authorized matching UFW setup:

```bash
LAN_CIDR='<LAN_CIDR>'
LAN_INTERFACE='<LAN_INTERFACE>'
for value in "$HALO_HOST" "$LAN_CIDR" "$LAN_INTERFACE"; do
  case "$value" in ''|*'<'*|*'>'*) echo 'Set approved network values first' >&2; exit 1;; esac
done
sudo ufw status numbered
sudo ufw allow in on "$LAN_INTERFACE" from "$LAN_CIDR" to "$HALO_HOST" \
  port 13305 proto tcp comment 'Lemonade authorized LAN'
```

This is a **mutation**, not a command to run during publication or audit.
Do not modify SSH access, open router ports or add a wildcard IPv6 rule as
a side effect. Container port exposure must be reviewed separately against
the actual Docker/firewall configuration.

Lemonade serves its official Web App at `/` on the API port. No extra
WebUI installation is required. SPA routes can return the same HTML; the
historical `/openapi.json` response was 404, not a missing Swagger installation.

For the observed LAN-origin issue, the packaged unit already read
`EnvironmentFile=-%E/lemonade/conf.d/*.conf`. After a backup and an idle window,
write the **resolved exact browser page origin**, not an unevaluated variable:

```bash
LEMONADE_ORIGIN="http://${HALO_HOST}:13305"
umask 077
mkdir -p "$HOME/.config/lemonade/conf.d"
printf 'LEMONADE_ALLOWED_ORIGINS=%s\n' "$LEMONADE_ORIGIN" \
  > "$HOME/.config/lemonade/conf.d/allowed-origins.conf"
chmod 600 "$HOME/.config/lemonade/conf.d/allowed-origins.conf"
systemctl --user restart lemond.service
```

Do not overwrite an existing file without reviewing/preserving it. If the page
comes from another approved origin, explicitly review that origin; do not
substitute a client IP merely because requests originate there. No `*`.

The August 25 browser preflight returned 204 and chat SSE 200 after the fix;
an unauthorized origin returned 403. A read-only/preflight check is:

```bash
curl -i -sS -X OPTIONS "$LEMONADE_URL/api/v1/chat/completions" \
  -H "Origin: $LEMONADE_ORIGIN" \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type'
```

Inspect CORS headers as well as status. A successful preflight does not prove
chat health or close the later unknown 403. Recheck the browser's exact method,
route and origin. Restore model residency after a restart only when authorized.

**Proxy/TLS:** no dedicated reverse proxy, certificate, renewal or HTTPS
configuration is validated by the sources. `<UNSLOTH_ORIGIN>` is a placeholder,
not evidence of a public Studio domain. Loopback plus an approved SSH tunnel
or a separately designed TLS/authenticated proxy are future options, not
existing deployments. Do not invent certificate or proxy instructions.

### Clients, models and catalog operations

Use the [reference](configuration-reference.md#clients-and-read-only-checks)
for OpenAI/OpenCode baseURL, exact IDs, GET checks and optional smoke.
Use its exact load payloads for the final 3+1 pair, not older single-model
options. Set `max_loaded_models=2` through the verified API and compare its
persisted value; slots are a separate control.

For Model Manager, distinguish three operations:

- **Variants:** `GET /api/v1/pull/variants?checkpoint=<REPO>` expects a
  Hugging Face repository identifier, not an arbitrary GGUF file/path.
- **Pull:** the observed API body used `model_name`, a
  `checkpoint` in `repo:variant` form, `recipe:"llamacpp"`,
  `stream:true`, `subscribe:false`. This downloads/registers data and may
  require model-license acceptance; do not use it as a health check.
- **Load:** loads a catalog ID and may initiate a missing download. A
  `downloaded:true` flag and complete hash-verified GGUF still do not prove
  a compatible architecture or a healthy backend.

Monitor `GET /api/v1/downloads`, available disk space and exact filename.
The download-path fix was verified with a 214643392-byte probe; no new
probe download is required for routine restoration. A growing `.partial`
is an active transfer, not a reason to restart the daemon. Confirm supported
resume behavior against the existing manifest before any new download.

## ROCm container smoke

Docker Engine **29.7.2** was installed/enabled historically; the account was
not added to the `docker` group and commands used sudo. Inspect Docker/Compose
availability and permissions before planning changes. Do not loosen the
Docker socket or enable privileged containers to bypass device errors.

The retained smoke base was:

```text
rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad
```

It reported Torch `2.12.0+rocm7.14.0`, HIP `7.14.60850` and `gfx1151`.
The historical smoke temporarily stopped Lemonade, ran once, and restored
Lemonade afterward. Schedule exclusive GPU use; do not stop other users'
work automatically. If an approved stop is needed, record the prior service
state and arrange restoration even when the test fails.

This command reproduces the **workload**, not an installation procedure.
It starts a container and GPU computation; review devices, image availability
and thermal/memory limits first. `--pull=never` deliberately prevents an
unexpected registry download; the exact image must already be available.

```bash
cat <<'SMOKE' | sudo docker run --rm -i --pull=never \
  --device=/dev/kfd --device=/dev/dri --shm-size=8g \
  rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad bash
set -euo pipefail
rocminfo | grep -F gfx1151
python3 - <<'PY'
import torch
assert torch.version.hip and torch.cuda.is_available()
assert torch.cuda.device_count() >= 1
print(torch.__version__, torch.version.hip, torch.cuda.get_device_name(0))
for dtype in (torch.float16, torch.bfloat16):
    a = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
    b = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
    loss = (a @ b).float().square().mean()
    loss.backward()
    torch.cuda.synchronize()
    assert torch.isfinite(loss) and torch.isfinite(a.grad).all()
    assert torch.isfinite(b.grad).all()
    print(dtype, loss.item())
PY
SMOKE
```

The input attachment flag is explicit so the script actually reaches Bash.
The historical broad `/dev/dri` mapping belongs only to this smoke; workspace
recipes use one render node. Neither needs `--privileged`, host IPC/network,
Docker socket, host `/opt/rocm` mounts or HSA target overrides.

Historical losses were 2047.4448 FP16 and 2047.9354 BF16, with finite gradients,
no remaining containers and no filtered AMDGPU/KFD/OOM/reset events.
Random inputs make those numeric losses observations, not expected exact
assertions for another run. Restore the previous Lemonade service state and
verify the **actual configured** listener on port 13305; the old smoke's
loopback listener does not replace the later LAN baseline. This validates
matmul/backward, **not** a dataset, checkpoint, fine-tuning or Unsloth support.

## Workspace operation

Use the English workspace manuals for complete dependency, preparation,
build, startup, ownership, tests, persistence and update details:

- [LLaMA-Factory / LlamaBoard](../../workspaces/llama-factory/README.en.md)
- [Unsloth Studio](../../workspaces/unsloth-studio/README.en.md)

Both are self-contained and do not administer Lemonade. Run `status.sh` first.
`build.sh` and `start.sh` are separate; startup uses `--no-build`. Only copy
`.env.example` into a private local environment file if absent, never overwrite
an existing one. Secrets stay private; no password-retrieval commands belong
in a public report.

LlamaBoard's v0.9.5 revision is
`7af909522a951e3ad9f022ea6f88b6755257eaa5`, using the Torch 2.12 base above.
The template binds loopback:7860 and health-checks `/`. Its seven bind mounts
map host directories `data/hf-cache`, `models`, `datasets`, `outputs`,
`cache`, `config`, `logs` to `/workspace/hf-cache`, `models`, `data`,
`saves`, `cache`, `config`, `logs`, respectively.

The proposed first BF16 LoRA run is SFT/LoRA, batch 1, accumulation 8,
sequence length 1024, at most 100 samples, output
`/workspace/saves/poc-lora-bf16`. Place an unquantized model in `data/models`,
dataset/catalog in `data/datasets`, and review the
[template](../../workspaces/llama-factory/examples/poc-lora-bf16.yaml)
after replacing both `CHANGE_ME` values. Do not enable 4/8-bit quantization
and call it BF16 LoRA. Require finite loss, real GPU use, bounded temperatures
and a resumable checkpoint. **This run has not been validated.**

The earlier long-term plan proposed QLoRA on 1.5-4B first, then 8-14B and
only a separately budgeted 32B experiment. Its tentative NF4/double-quant,
BF16, LoRA rank 16/alpha 32, microbatch 1, accumulation 8-16 and 2k context
settings were **not validated and are not usable as evidence that the
current bitsandbytes-free stack supports QLoRA**. The smaller BF16 LoRA
workspace template is a different proposed gate. A future export pipeline
was adapter -> FP16 merge -> GGUF -> evaluation, retaining immutable base
weights and a resumable checkpoint. No completed training/export command
sequence or quality result exists here; require a separate validated recipe
before attempting scaling, merging or deployment.

Studio uses commit `e18a069c15cde98c7af77ccdb952254db8b0315d` and a
**different** base:

```text
rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80
```

Torch 2.11 is within the documented Unsloth `<2.12` constraint. Build/imports,
`pip check`, GPU detection, health and the SPA passed on September 1;
`bitsandbytes` is absent and FLA warned of CPU fallback. These results do
not establish training support. The official UI command is
`unsloth studio -H 0.0.0.0 -p 8888`, without `--api-only`; container binding
is separate, default host `127.0.0.1:8888`, health `/api/health`.

Studio maps `data/studio` to `/home/unsloth/.unsloth/studio`, `data/hf-cache`
to `/workspace/hf-cache`, `data/projects` to `/workspace/projects` and
`data/tmp` to `/workspace/tmp`. `/home/unsloth` is the image's documented
container account, not a private host username. Data includes auth and runs.
Startup uses the host data owner's UID/GID, a validated supplemental render
GID and the managed venv link. It can correct ownership; do not solve errors
with global write permissions. The bootstrap password is unset before the
long-lived process once an admin already exists.
The recorded Unsloth Core license is Apache-2.0; Studio/CLI are AGPL-3.0-only.
Preserve notices and review corresponding-source obligations before
redistributing an image or modification.

Defaults are `SHM_SIZE=16g` and `/dev/dri/renderD128`; verify the real render
node and its GID, do not transplant personal UID/GIDs. **As of the repository
template update on 2026-09-07, Studio requires an explicit `DEVICE_GID`:**
its template leaves it empty and Compose rejects a missing value. Studio
does not autodetect this group. Set `RENDER_DEVICE` to the selected existing
node, then inspect it without changing permissions:

```bash
stat -c '%n GID=%g group=%G permissions=%A' "$RENDER_DEVICE"
```

Privately set `DEVICE_GID` to the numeric GID shown before startup. In
contrast, LLaMA-Factory's `start.sh` can determine `DEVICE_GID` when it is
empty. Neither behavior changes the meaning of Studio's host data-owner
`HOST_UID`/`HOST_GID` settings. Native and container ROCm are distinct.
No default wildcard LAN exposure, automatic restart,
privileged mode, host IPC/network or host ROCm mount is supplied.

## Incidents and recovery

| Symptom | Evidence and safe next step |
| --- | --- |
| Later HTTP 403 | Unknown cause; collect sanitized method/path/origin/error/time, distinguish browser/API/proxy/auth, do not declare fixed |
| August 25 browser chat 403 | Confirmed exact-origin rejection; CORS repair and browser SSE passed then, not proof about the later incident |
| CLI cannot connect | Check actual bind; default localhost does not reach a LAN-only listener |
| User service disappears after logout | Check `Linger` and unit scope; historic `no` was later `yes`; do not infer cold-boot preload |
| Model options or resident count differ | Compare `/internal/config`, exact-ID options and child command line; old global contexts do not override the final profile |
| Catalog entry disappears | Shared base/user IDs and an actual delete caused re-download; preserve artifacts and the active `.partial`, do not delete the other entry |
| UI load/pull seems stuck | Compare download-job state, file progress, available space and backend readiness before any restart; a changing transfer is real work |
| Model Manager 500 | Confirm the variants/pull contract and separate metadata/API failures from architecture/load errors; do not blame all failures on Vulkan |
| Download path beneath `/usr/bin/~/...` | Use expanded absolute `models_dir`; preserve correct `extra_models_dir` |
| Flash-Next `qwen4exp` unknown | Unsupported by b10375; do not retry in the dual-model service |
| vLLM native segfault | Historical report involved 0.20.1/ROCm 7.12/Torch 2.10 hybrid initialization; not promoted and must be independently revalidated |
| Agent requests queue | Compare actual simultaneous HTTP requests with slots; seven requests over four old slots meant queuing, not broken KV keep-alive |
| Runaway log or hung smoke | Bound tokens/time/output; inspect exact process and stop only that process with approval |
| Shell or workspace failures | Use Bash for POSIX examples, LF for `.sh`, correct exec bits/ownership; do not assume GPU/daemon errors from malformed local scripts |
| Snapper permission failure | Preserve verified fallback; no unproven remount, filesystem-repair or automatic package rollback |

The old concurrency diagnosis showed overlapping decode in logical slots,
not GPU parallelism or improved wall-clock/TTFT. Before raising concurrency,
use a controlled barrier N=1/N=2/N=4, real independent requests, identical
prompts and recorded start/TTFT/wall-clock/HTTP/tokens/s, plus `/slots`,
`/metrics` and GPU memory. Keep internal backend ports private. Do not run
a benchmark while other users are generating.

## Cleanup and rollback

Start with inventory and private backups. Nothing here authorizes destructive
cleanup or downloads during an audit.

- **Models:** use exact-ID `POST /api/v1/unload` to release residency, not
  `/api/v1/delete`, which removes disk artifacts and can affect shared entries.
  Reload the documented Coder/Thinking requests and recheck health/GTT.
- **Lemonade:** restore the specific configuration change from its backup.
  Reverting a LAN bind requires coordinated client/firewall changes; do not
  remove SSH access. Restore the prior CORS file and restart only in an idle
  window. Never transplant this documentary JSON as a native config.
- **UMA:** physical BIOS rollback to the recorded setting, only with approval
  and a demonstrated regression; no automatic firmware action.
- **Packages:** review dependencies and package inventories before removal;
  do not run broad autoremove/upgrade/downgrade commands. Keep a bootable
  prior kernel and an independently verified system restore path.
- **Images:** preserve the built image by immutable ID before rebuilding.
  LlamaBoard can use `RUN_IMAGE` with its saved full image ID; Studio accepts
  `RUN_IMAGE=last` or `previous` after ownership checks. Start does not rebuild.
  Mutable package repositories prevent bit-for-bit reproduction from sources.
- **Workspace data:** `stop.sh` preserves bind mounts. `cleanup.sh` defaults
  to inventory; run only `./cleanup.sh --dry-run` for a read-only cleanup
  preview. Review its English README before any destructive mode.
  `--all` can irreversibly remove models, datasets, checkpoints, auth/DB,
  configuration and caches belonging to that workspace; `--yes` is not a
  safety check. No global Docker prune or blanket data-directory removal.
  The shared ROCm base is retained unless explicitly included after review.

Post-rollback success means health at the actual port/listener, correct
resident IDs/options/backend, expected memory and a separately approved small
chat smoke. An image ID alone does not restore data, firmware or host runtime.

## Deferred work and sources

Pending: later 403, current health/cold boot/model preload, TLS/proxy,
prolonged soak, exact full option-merge precedence, full per-model options
storage, verified system snapshot recovery, real LoRA/QLoRA and controlled
concurrency comparison. Netdata and optional Cockpit were recommended only;
installation is not evidenced. vLLM and Qwen3.8 alternatives require an
isolated specialist-led evaluation, not a silent runtime upgrade.

The [English coverage index](README.md#coverage-of-the-historical-sources)
maps every historical source. Instructions and conclusions are reproduced
here or in the linked English reference/model/workspace guides; readers do
not need Spanish logs or unpublished files to follow this runbook.
