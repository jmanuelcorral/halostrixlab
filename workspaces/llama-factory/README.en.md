# LLaMA-Factory + LlamaBoard on Halo Strix

[Español](README.md) | [English](README.en.md)

Self-contained workspace to **build and start only the web interface** with
Docker and ROCm. It does not start training automatically or manage other host
services.

## Status and scope

Target: Linux with AMD Radeon 8060S Graphics (`gfx1151`) and ROCm. The base below
was validated in this repository; that does not certify every model, dataset,
or training combination. The POC below documents an existing recipe to review,
not a completed training validation. See the
[reusable configuration guide](../../docs/en/configuration-reference.md)
and the [English repository guide](../../README.en.md).

## Pinned versions

- Base validated in this repository:
  `rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`
  (PyTorch `2.12.0+rocm7.14.0`, HIP 7.14).
- LLaMA-Factory `v0.9.5`, commit
  `7af909522a951e3ad9f022ea6f88b6755257eaa5`.

Sources are downloaded by commit, without cloning `main`. This is **not a
byte-for-byte reproducible build**: APT and transitive Python dependencies are
resolved from live repositories during each build and can change. The base
digest and commit provide reasonable functional repeatability, not a hermetic
build. To reproduce or roll back the exact artifact, retain the built image
and its real `sha256` ID, which `build.sh` obtains from Docker and records in
`.last-built-image`. The same ID guarantees the same image, not the same
runtime environment: host, firmware, devices, and mounted data remain external.

## Preparation

Requirements: Linux, modern Bash (4.3+ for cleanup namerefs), GNU utilities
(`stat`, `readlink`, `find`, `sed`, `awk`, `du`, `grep`), Docker, Compose v2, and
enough space for images, models, and data. Building requires access to container
registries, GitHub, APT, and the configured Python index. These scripts do not
install or tune drivers.

From this directory on the server, for a **new installation only**:

```bash
cp .env.example .env
ls -l /dev/kfd /dev/dri/renderD*
readlink -f /dev/dri/by-path/*-render 2>/dev/null || true
stat -c '%n GID=%g group=%G permissions=%A' /dev/kfd /dev/dri/renderD128
```

Never overwrite an existing `.env`; retain local settings privately. Change
`RENDER_DEVICE` if your node is not `renderD128`. `DEVICE_GID` may remain empty:
`start.sh` detects the render node GID using `stat`; an explicit value is also
supported. The account must have access to the Docker daemon and both GPU
devices. If Docker requires privileges, use `sudo ./start.sh`; the script does
not enable or start the daemon.

### Variables

Exported environment variables take precedence over `.env` in build/start.
Do not use `.env` to store tokens.

| Variable | Example/default and purpose |
| --- | --- |
| `BASE_IMAGE` | Full AMD digest listed above |
| `LLAMAFACTORY_COMMIT` | Full upstream SHA listed above |
| `LLAMAFACTORY_IMAGE` | `halostrix-llamafactory:v0.9.5-rocm7.14`, local build tag |
| `RUN_IMAGE` | Empty; optionally a retained image ID for start |
| `PIP_INDEX_URL` | `https://pypi.org/simple`; no embedded credentials |
| `RENDER_DEVICE` | `/dev/dri/renderD128`; verify on the host |
| `DEVICE_GID` | Empty: start detects the render node's numeric GID |
| `WEB_BIND` / `WEB_PORT` | `127.0.0.1` / `7860` |
| `SHM_SIZE` | `16g`, container shared memory, not host RAM/GTT tuning |
| `LOG_TAIL` | Optional exported setting for logs; defaults to `100` lines |

## Build and operate

```bash
chmod +x build.sh start.sh stop.sh status.sh logs.sh scripts/common.sh
./build.sh
./start.sh
./status.sh
./logs.sh
./stop.sh
```

`build.sh` validates build inputs, builds with exact ownership labels
(`com.halostrix.project`, `com.halostrix.service`), upstream revision and base
digest, and saves the actual immutable image ID. `start.sh` validates Docker,
the local image, render node, permissions and port settings, creates persistent
directories, starts with `--no-build`, and waits for the healthcheck. Both are
fail-fast and idempotent. The initial `127.0.0.1:7860` binding is accessible only
from the host.

To start the exact last artifact without resolving APT/Python again:

```bash
RUN_IMAGE="$(cat .last-built-image)" ./start.sh
```

You may also set that ID as `RUN_IMAGE` in `.env`. `stop.sh`, `status.sh`, and
`logs.sh` only validate Docker/Compose and use neutral values when rendering
Compose. They can still manage an existing container when the GPU or `.env`
is missing, or startup configuration is invalid. Logs follow the selected
number of tail lines.

Do not run `docker image prune` if you need rollback. Before rebuilding, save
the old ID outside `.last-built-image` or add a local tag using
`docker image tag sha256:ID name:rollback`, replacing `sha256:ID` with the
complete retained ID. Both references identify the same local image content.

### LAN access

Set `WEB_BIND=0.0.0.0` in `.env` and change `WEB_PORT` if needed. Run
`./start.sh`, then open `http://HOST_IP:7860`, substituting your host address.
No LAN address is assumed. Restrict access to the trusted subnet through your
existing host firewall; this workspace does not change firewall rules.
LlamaBoard does not provide perimeter authentication: do not expose it to the
Internet, and do not put tokens in `.env`.

## First BF16 LoRA POC (not QLoRA)

Before training, manually stop any other GPU workload you choose to stop.
Concurrent training and inference compete for GPU/GTT/RAM. These scripts
**do not stop or reconfigure unrelated services**.

1. Place or download the unquantized model in `data/models/`.
2. Place the dataset in `data/datasets/` and add `dataset_info.json` there,
   following the LLaMA-Factory format.
3. In LlamaBoard select SFT, LoRA, BF16, batch 1, gradient accumulation 8,
   length 1024, up to 100 samples, and output `/workspace/saves/poc-lora-bf16`.
4. Verify that 4/8-bit quantization is not selected: that would be QLoRA.
5. Start training **only after reviewing** the model, template, and dataset.

Alternatively, copy `examples/poc-lora-bf16.yaml` to `data/config/`, replace
both `CHANGE_ME` values, and review it. Nothing invokes it automatically.
For the first gate, check finite loss, actual use of `AMD Radeon 8060S Graphics`,
temperature, memory, and a resumable checkpoint.

## Persistence

| Host | Container | Contents |
| --- | --- | --- |
| `data/hf-cache` | `/workspace/hf-cache` | Hugging Face cache |
| `data/models` | `/workspace/models` | Explicit models |
| `data/datasets` | `/workspace/data` | Datasets and catalog |
| `data/outputs` | `/workspace/saves` | Adapters/checkpoints |
| `data/cache` | `/workspace/cache` | Torch/Triton/compilation caches |
| `data/config` | `/workspace/config` | Local configurations |
| `data/logs` | `/workspace/logs` | `llamaboard.log` |

`docker compose down` does not delete these bind mounts, but use `./stop.sh`
as the normal interface. Never use `rm -rf data`, `down -v`, or
`docker system prune` without a backup and authorization.

## Updating and rollback

1. Stop the UI and back up `data/config` and `data/outputs`.
2. Verify a GitHub release/tag and resolve it to a full SHA through the primary
   API `.../repos/hiyouga/LlamaFactory/git/ref/tags/TAG`.
3. Change `LLAMAFACTORY_COMMIT` and use a **new** `LLAMAFACTORY_IMAGE`; retain the
   previous image name.
4. Run `./build.sh`, retain the image and reported ID, then run `./start.sh`
   and validate health/GPU before training.
5. For exact **image** rollback, set `RUN_IMAGE=sha256:...` to the retained full
   ID and run `./start.sh`. It neither rebuilds nor resolves dependencies again.

To change ROCm, use only a compatible AMD PyTorch image pinned by digest.
Do not use CUDA/NVIDIA variants or mix in host userspace.

## Diagnostics and safe cleanup

`cleanup.sh` is specific to this workspace and rejects roots, links, and
ambiguous paths. Approved layouts are `<repo>/workspaces/llama-factory` and
`$HOME/ai/llama-factory`, with no fixed personal account. For the latter, use
the owning account: `sudo` can change `HOME` and cause rejection.

Inventory only is the default:

```bash
chmod +x cleanup.sh
./cleanup.sh                 # equivalent to --dry-run
./cleanup.sh --dry-run
./cleanup.sh --help          # -h is also supported
```

The inventory shows contents of the seven allowed directories under `data/`
and only containers, the exact network, and images attributed through exact
labels. Images must also match the configured revision and immutable base.
A tag, `.env`, `RUN_IMAGE`, or `.last-built-image` only supplies candidates:
none proves ownership. Every resource is inspected again immediately before
deletion. This Compose file uses bind mounts only, so cleanup neither searches
for nor deletes Docker volumes. It uses no prune, wildcard deletion of Docker
resources, or partial identity matches.

```bash
./cleanup.sh --all           # requires the exact displayed confirmation
./cleanup.sh --all --yes     # explicit automation; no prompt
./cleanup.sh --all --include-base
```

The exact first confirmation remains
`ELIMINAR halostrix-llamafactory SIN RECUPERACION`.

**Irreversible:** `--all` also removes models, datasets, adapters/checkpoints,
configurations, logs, and all caches inside
`data/{hf-cache,models,datasets,outputs,cache,config,logs}`, plus the exact
project Docker resources. **There is no recovery** without an external backup.
`--yes` alone does not delete anything: it requires `--all`. `--dry-run`
dominates any order or combination, including `--all --yes`. If Docker is
unavailable, `--all` can explicitly clean only these data directories; this is
recorded as a failure and exits nonzero. Individual Docker failures are
isolated: other revalidatable resources and contained data paths are still
processed, and a partial-cleanup summary precedes the nonzero exit.

The shared ROCm base is preserved unless `--include-base` is combined with
`--all`. Interactive mode requires a second phrase containing its exact digest:
`ELIMINAR BASE ROCM sha256:...` (use the complete digest shown by the script).
`--yes` intentionally skips **both** confirmations, but removing the base still
requires both explicit flags: `--all --include-base --yes`.
The reference and ID are revalidated against `RepoDigests` immediately before
removal. Cleanup never manages Lemonade or unrelated processes, ports, or
services. To rebuild afterwards, copy `.env.example` to `.env` **only if
missing**, review it, then run `./build.sh` and `./start.sh`.

- `permission denied` for `/dev/kfd` or render: check GID/permissions and log in
  again after group changes; do not use `privileged`.
- GPU absent: the Compose device configuration should expose only `/dev/kfd`
  and the selected render node. Check inside the running container with
  `docker compose exec llamaboard python3 -c "import torch; print(torch.version.hip, torch.cuda.is_available(), torch.cuda.get_device_name(0))"`.
- UI `unhealthy`: use `./logs.sh`, check for an occupied port and inspect free
  space with `df -h`; initial setup can take time.
- OOM: reduce model size, sequence length, batch size, and sample count.
- Stop/remove only the container: `./stop.sh`, then
  `docker compose --env-file .env rm -f llamaboard`.
- Remove a specific image while preserving data:
  `docker image rm halostrix-llamafactory:v0.9.5-rocm7.14`.

This workspace does not use host networking, the Docker socket, `ipc:host`,
the host's `/opt/rocm`, automatic restart, or the entire `/dev/dri` tree.

## Local tests without a GPU or real daemon

The reference test platform is **Linux with GNU Bash/utilities and real symbolic
links**. From this workspace:

```bash
for script in ./*.sh scripts/*.sh tests/*.sh; do bash -n "$script" || exit; done
bash tests/test-cleanup.sh
docker compose --env-file .env.example config --quiet
```

The last command only validates Compose and requires its plugin; it starts no
workloads. The test runner uses fake Docker and synthetic data under
`tests/.sandbox`, removed on exit. Reserve that directory for tests. It checks
both dry-run flag orders, continuation after a partial failure (3 Docker
attempts, 2 successes, 1 failure), rejection of foreign resources, absence of
volume operations, portable layouts, paths with spaces, and symlinks. It does
not run cleanup on real workspace data. `PASS: cleanup, ...` indicates success;
failed assertions exit nonzero. Bash diagnostics remain in Spanish.

### Running the sandbox tests from Windows

Git Bash is suitable for these offline tests only when it creates **real native
symlinks**. Its default `ln -s` can copy a directory instead; that is not a valid
symlink-rejection fixture. The cleanup runner now fails before Docker calls
with `ERROR: cleanup tests require real symlinks` if this prerequisite is absent.
Do not treat that failure as a cleanup regression or a passing/skipped test.

From PowerShell at the repository root, using an existing Git Bash installation:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -c 'export MSYS=winsymlinks:nativestrict; bash workspaces/llama-factory/tests/test-cleanup.sh'
```

`winsymlinks:nativestrict` requests native symlinks and fails rather than copying.
It does **not** grant Windows symlink permission. If your existing account or
filesystem cannot create them, use an already-available authorized Linux test
environment; do not change security policy, elevate, or replace symlinks with
copies just to make the test pass. This is test-platform guidance, not support
for running the Linux/ROCm workload directly in Git Bash.

## Licensing and publication

Upstream LLaMA-Factory is Apache-2.0; check the pinned source's licenses/notices
and each dependency, model, and dataset before redistributing. A tool's license
does not grant rights to weights, datasets, or outputs. Do not publish `.env`,
`data/`, `.last-built-image`, credentials, private logs, or images containing
local data.
Local Git and Docker-context rules exclude private configurations, data, and
image markers; `.env.example` remains publishable. `.gitattributes` preserves
LF line endings in Bash scripts when cloning from Windows.
