# Unsloth Studio for Halo Strix (PyTorch 2.11 / ROCm 7.14)

[Español](README.md) | [English](README.en.md)

Local, self-contained workspace to build and operate the Unsloth Studio web
interface on a remote `gfx1151` host. It does not manage Lemonade or any other
host process, port, or service.

## Stack status: UI validated; training not validated

The official AMD/ROCm base is pinned to a complete registry digest:

`rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80`

Origin name/tag:
`rocm/pytorch:rocm7.14_ubuntu24.04_py3.12_pytorch_release_2.11.0`.
The build does not use that mutable tag: it uses only the digest above,
previously confirmed against Docker Registry and by local inspection.

Inspection inside the base returned PyTorch `2.11.0+rocm7.14.0`, torchvision
`0.26.0+rocm7.14.0`, torchaudio `2.11.0+rocm7.14.0`, triton
`3.7.1+git0263a6a6.rocm7.14.0`, and HIP `7.14.60850`. PyTorch 2.11 is within
Unsloth's upstream `<2.12` range; that permits the build, but is not in itself a
claim of functional support. Compatibility is accepted only after build,
imports, gfx1151 GPU detection, health, and UI checks pass.

Recorded validation on **2026-09-01**: build and `pip check` succeeded; the
resolver preserved the AMD stack; `import torch`, `import triton`,
`import unsloth`, health, and the SPA passed. Torch detected
`AMD Radeon 8060S Graphics`, `gfx1151`, and an available GPU.
`bitsandbytes` is not installed, so 4-bit QLoRA is unavailable. Unsloth Zoo
warned that its FLA path does not consider Triton supported on this platform
and would use the CPU for that path. No training was started: this validates
the Studio web interface and GPU detection, **not training compatibility**.

The configuration is identified by local tag `e18a069-rocm7.14-torch2.11` and
OCI label `com.halostrix.stack=pytorch-2.11-rocm-7.14-gfx1151`.
The build preserves the base's exact torch, torchvision, torchaudio, and triton
versions as normal resolver constraints, runs `pip check`, and fails if any
changes or any CUDA/NVIDIA package appears. It does not use `--no-deps`, modify
metadata, or force a stack outside upstream's declared range.
Source is installed with the official `huggingface` extra, which declares
`unsloth_zoo`, torchvision, and triton. The existing AMD stack remains pinned
by constraints, and its version manifest is compared byte for byte before and
after dependency resolution.

## Verified pins (2026-09-01)

- Unsloth signed commit selected during validation:
  `e18a069c15cde98c7af77ccdb952254db8b0315d`.
- Commit codeload tarball SHA-256:
  `52037b47de581f360e1db0a2072e65202d8993782e99f0300f181df93c63eeb8`.
- Node `22.12.0-bookworm-slim`, OCI index pinned by digest:
  `node@sha256:35531c52ce27b6575d69755c73e65d4468dba93a25644eed56dc12879cae9213`.
- `studio/frontend/package-lock.json` comes from the same tarball. The source
  does not include a prebuilt frontend: the Node stage runs
  `npm ci --ignore-scripts` and `npm run build`, then copies
  `studio/frontend/dist`.
- Headless CLI verified in source and the primary CI script:
  `unsloth studio -H 0.0.0.0 -p 8888`. Do not use `--api-only`: it disables the
  frontend.
- Actual healthcheck: `GET /api/health`.
- Storage paths verified in `studio/backend/utils/paths/storage_roots.py`.

Primary sources:

- <https://github.com/unslothai/unsloth/commit/e18a069c15cde98c7af77ccdb952254db8b0315d>
- <https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/pyproject.toml>
- <https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/studio/backend/utils/paths/storage_roots.py>
- <https://github.com/unslothai/unsloth/blob/e18a069c15cde98c7af77ccdb952254db8b0315d/.github/scripts/boot-studio-api-only.sh>

Core source (`unsloth/*`) is Apache-2.0. Studio and CLI (`studio/*`,
`unsloth_cli/*`) are AGPL-3.0-only. Original licenses remain in the
tarball/image. Redistributing an image or modification requires compliance
with those licenses, including AGPL corresponding-source obligations.

## Preparation and operation

Requirements: Linux AMD `gfx1151` host, `/dev/kfd` and a render node, Docker with
Compose v2 and authorized daemon access, Bash 4+, and GNU utilities (`stat`,
`readlink`, `find`, `sed`, `awk`, `grep`). Building needs access to registries,
GitHub/codeload, APT, npm, and the Python index. Reserve adequate space for
images and data. These scripts do not install or tune drivers.
See the [reusable configuration guide](../../docs/en/configuration-reference.md)
and [English repository guide](../../README.en.md).

On the remote Linux host, from this directory, copy the template **only for a
new installation**. Never overwrite an existing private `.env`:

```bash
cp .env.example .env
chmod 600 .env
ls -l /dev/kfd /dev/dri/renderD*
readlink -f /dev/dri/by-path/*-render 2>/dev/null || true
stat -c '%n GID=%g group=%G permissions=%A' /dev/kfd /dev/dri/renderD128
```

Privately configure `UNSLOTH_STUDIO_PASSWORD` with a long, random, unique value,
set `RENDER_DEVICE` to the actual render node, and set `DEVICE_GID` to its
observed numeric GID. **This workspace does not autodetect `DEVICE_GID`**:
the template leaves it empty and requires you to set it explicitly.

```bash
chmod +x build.sh start.sh stop.sh status.sh logs.sh cleanup.sh scripts/common.sh
./build.sh
./start.sh       # always uses --no-build
./status.sh
./logs.sh
./stop.sh
```

`build.sh` and `start.sh` are separate. A successful build atomically records
the actual immutable ID in `.last-built-image`; when it changes, the old ID is
moved to `.previous-built-image`. A failed build or inspect changes neither
marker, and rebuilding the same ID preserves the previous marker. Select
either image with:

```bash
RUN_IMAGE=last ./start.sh
RUN_IMAGE=previous ./start.sh
```

A complete image ID is also accepted. Before startup, every reference is
inspected and must carry the exact project, service, revision, and commit
labels. Foreign images are rejected.

`UNSLOTH_STUDIO_PASSWORD` is kept exclusively in private `.env` (mode 600) and
passed to Studio's official bootstrap. Consult credentials only through your
private local configuration; never print them, copy them into logs, or publish
them. When the persisted authentication DB already contains a user, the
entrypoint removes this variable from the startup process: editing `.env`
does not reset an existing password. Use Studio's official credential
management.

The default binding is `127.0.0.1:8888`. Change `WEB_BIND` only after establishing
appropriate authentication and network controls. The container runs with the
non-root UID/GID of the host data owner. `start.sh` uses `id -u`/`id -g`, or
`SUDO_UID`/`SUDO_GID` when invoked through `sudo`, repairs ownership of the four
bind mounts without world-writable permissions, and fails if it cannot make
them writable. The image retains UID/GID `10001` as its fallback.
Compose also adds the explicitly configured supplementary render GID, so
changing the primary user does not remove GPU group access. You can explicitly
export `HOST_UID` and `HOST_GID`.
Internal parent directories are traversable (`0755`) so the runtime UID/GID can
reach the mounts without making any parent writable. The local entrypoint
creates only the managed link `data/studio/unsloth_studio -> /opt/venv`, which
the official CLI requires to recognize a prepared installation. It rejects
any different existing object at that path.

It uses no `privileged` mode, Docker socket, host networking, `ipc:host`,
host `/opt/rocm`, `HSA_OVERRIDE_GFX_VERSION`, automatic restart, or full
`/dev/dri` mapping.

### Variables

| Variable | Example/default and purpose |
| --- | --- |
| `BASE_IMAGE` / `NODE_IMAGE` | Complete AMD/Node digests listed above |
| `UNSLOTH_COMMIT` / `UNSLOTH_TARBALL_SHA256` | Source SHA and checksum listed above |
| `UNSLOTH_IMAGE` | `halostrix-unsloth-studio:e18a069-rocm7.14-torch2.11` |
| `PIP_INDEX_URL` | `https://pypi.org/simple`; no embedded credentials |
| `UNSLOTH_STUDIO_PASSWORD` | Empty in template; required private bootstrap value |
| `RENDER_DEVICE` | `/dev/dri/renderD128`; verify on the host |
| `DEVICE_GID` | Empty in template; required numeric render GID |
| `HOST_UID` / `HOST_GID` | Optional exported non-root IDs; otherwise `SUDO_UID`/`SUDO_GID` or `id` |
| `WEB_BIND` / `WEB_PORT` | `127.0.0.1` / `8888` |
| `SHM_SIZE` | `16g`, container shared memory, not RAM/GTT tuning |
| `RUN_IMAGE` | Empty, `last`, `previous`, or a validated local reference/ID |

Build/start load the listed settings from `.env`, preferring exported values.
**Export `HOST_UID`/`HOST_GID`** when overriding identity; filling them in `.env`
alone is insufficient because start calculates them. `stop.sh`, `status.sh`,
and `logs.sh` use neutral Compose rendering values, but Compose still requires
the password variable (which it can obtain from local `.env`). Do not display
the full output of `docker compose config`: it can contain credentials.

`start.sh` requests container startup without waiting for health. Check with
`./status.sh`, `./logs.sh` (follows the last 200 lines), and, for the default
binding, `curl --fail http://127.0.0.1:8888/api/health`.
`stop.sh` runs `compose down`, preserving the bind mounts.

### GPU ownership, updates, and rollback

Before loading models or training, review GPU/GTT/RAM ownership and manually
stop any conflicting workloads you choose. These scripts never stop Lemonade
or other services. Training has not been validated: health/UI success is not
a LoRA compatibility test.

Retain images and back up all four data directories before updating. Do not
prune images needed for rollback. `RUN_IMAGE=previous ./start.sh`, or a retained
complete ID, rolls back **the image**, not data or DB migrations. Digests/SHAs
pin sources and bases, not all transitive APT/Python packages; builds are not
promised to be hermetic or byte-for-byte reproducible.

Changing the upstream revision requires coordinated review of pins, checksum,
`EXPECTED_REVISION` in `scripts/common.sh`, `REVISION` and the base in
`cleanup.sh`, labels, and tests. Merely changing the `.env` SHA is insufficient.
Do not use CUDA/NVIDIA or mix in host `/opt/rocm`.

## Persistence

| Host | Container | Meaning |
| --- | --- | --- |
| `data/studio` | `/home/unsloth/.unsloth/studio` | Complete Studio home: DB, auth, assets, outputs, exports, runs, caches, and binaries |
| `data/hf-cache` | `/workspace/hf-cache` | `HF_HOME`, hub, and Transformers |
| `data/projects` | `/workspace/projects` | `UNSLOTH_STUDIO_PROJECTS_HOME` |
| `data/tmp` | `/workspace/tmp` | Temporary files and recipe/validator caches |

These paths correspond to `studio_root`, `cache_root`, `outputs_root`,
`exports_root`, `tensorboard_root`, `project_workspaces_root`, and `tmp_root`
in the pinned commit. Data is not stored in anonymous Docker volumes.

## Safe cleanup

Approved layouts are `<repo>/workspaces/unsloth-studio` and
`$HOME/ai/unsloth-studio`. For the latter, use the owning account: `sudo` can
change `HOME` and cause layout rejection. Help: `./cleanup.sh --help` or `-h`.

Inventory without deletion (default):

```bash
./cleanup.sh
./cleanup.sh --dry-run
```

Interactive cleanup:

```bash
./cleanup.sh --all
# exact phrase: BORRAR HALOSTRIX UNSLOTH STUDIO
```

Deliberate automation, skipping confirmations:

```bash
./cleanup.sh --all --yes
```

**Irreversible:** `--all` removes the authentication DB, cached models, projects,
outputs/exports, runs, and temporary data inside the four permitted directories,
plus validated Docker resources. Recovery requires an external backup.
`--yes` without `--all` does not delete anything. Interactive confirmation
requires a TTY.

The ROCm base is preserved. To include **only the exact shared base digest**:

```bash
./cleanup.sh --all --include-base
# second exact phrase: BORRAR BASE ROCM COMPARTIDA
# or --all --include-base --yes for automation
```

`--dry-run` unconditionally overrides `--all` and `--yes`, in any order.
Containers are selected only when both Compose project
`halostrix-unsloth-studio` and service `studio` labels match.
The only eligible network must be named exactly
`halostrix-unsloth-studio_default` and carry the exact project and network
`default` labels. Compose defines only bind mounts, so cleanup neither
enumerates nor deletes Docker volumes.

Images are resolved to IDs and must simultaneously match the exact project,
service, OCI revision, and pinned commit labels. `.env`, `.last-built-image`,
and `.previous-built-image` are untrusted candidate sources, never deletion
authorization. Resources are revalidated immediately before removal.
An individual Docker failure does not stop independent resources or validated
data paths; the summary counts errors and the process exits nonzero. There is
no global cleanup.

Each real data path is validated before clearing only `data/studio`,
`data/hf-cache`, `data/projects`, and `data/tmp`. The workspace, `.env`,
documentation, and scripts remain. If Docker is missing or unresponsive,
cleanup reports that and can still clear those data directories. Requested
deletion without Docker produces a partial result and nonzero exit.
To rebuild, retain or restore private `.env` without overwriting it, review
GID/credentials, then run `./build.sh` and `./start.sh`.

## Local validation without a GPU or real daemon

The reference test platform is **Linux with GNU Bash/utilities and real symbolic
links**. The build/start runner also needs GNU `mktemp`: the existing atomic
image-marker writer creates its intermediate files inside the test workspace,
not in a system temporary directory. Do not run that runner in environments
that prohibit this operation; report it as **not run**, not passed.

```bash
for script in ./*.sh scripts/*.sh tests/*.sh; do bash -n "$script" || exit; done
bash tests/test-shell-files.sh
bash tests/test-build-start.sh
bash tests/test-cleanup.sh
bash tests/test-ownership.sh
# Synthetic validation values only; never use them to start Studio:
DEVICE_GID=0 UNSLOTH_STUDIO_PASSWORD=validation-only-not-a-credential \
  docker compose --env-file .env.example config --quiet
```

`test-shell-files.sh` is a binary gate: it rejects any CR byte in `.sh` files
outside `data/` and runs `bash -n`. The ownership test also limits its search to
publishable source files. Other tests replace Docker, `stat`, `id`, and `chown`
with fakes. They cover first/second build rotation, failure without marker
changes, same-ID rebuild, malformed ID and foreign image rejection, owned and
foreign previous-image candidates during cleanup, combined/reordered dry-run
flags, foreign images/tags, service filtering, partial failure with continuation
and nonzero exit, symlink rejection, absence of volumes/prune, exact labels, and
ownership under simulated sudo. They do not touch real resources or data.

Reserve `tests/sandbox`, `tests/build-start`, and `tests/ownership` for the test
runners: they create and delete them. Lines ending in `: OK` confirm success;
assertion or syntax failures exit nonzero. Compose config only validates
configuration; it does not prove build, health, GPU, or training compatibility.
Bash/Python diagnostics remain in Spanish. Do not publish `.env`, data, local
image markers, or private logs.
Local Git and Docker-context rules exclude private configurations, data, and
image markers; `.env.example` remains publishable. `.gitattributes` preserves
LF line endings in Bash scripts when cloning from Windows.

### Running the sandbox tests from Windows

Default Git Bash `ln -s` can copy directories instead of creating symlinks,
which invalidates cleanup's symlink-rejection tests. The cleanup runner checks
this capability before Docker calls and fails explicitly with
`ERROR: cleanup tests require real symlinks`. It never silently skips them.

From PowerShell at the repository root, with Git Bash already installed:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -c 'set -e; export MSYS=winsymlinks:nativestrict; for f in workspaces/unsloth-studio/tests/test-cleanup.sh workspaces/unsloth-studio/tests/test-build-start.sh workspaces/unsloth-studio/tests/test-ownership.sh workspaces/unsloth-studio/tests/test-shell-files.sh; do bash "$f"; done'
```

This complete workspace command requires all prerequisites above.
`winsymlinks:nativestrict` requests real native links, failing rather than
copying; it does **not** grant Windows permissions. If native symlink permission
or another required operation is unavailable, use an already-available
authorized Linux test environment. Do not change security policy, elevate,
install tools, replace symlinks with copies, or silently omit a runner to claim
the full suite passed. These are offline test accommodations, not support for
running the Linux/ROCm workload directly in Git Bash.
