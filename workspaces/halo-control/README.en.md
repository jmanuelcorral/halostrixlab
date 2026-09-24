# Halo Control

[Español](README.md) | [Project](../../README.en.md) |
[September 24 consolidation](../../docs/en/halo-control-operations.md)

Private Cockpit Linux extension for Strix Halo. This is neither kyuz0's
AI Toolbox Cockpit nor the public static documentation site.

## Delivery status, consolidated 2026-09-23

Implemented React/TypeScript, PatternFly, ECharts and xterm.js UI, typed process
bridge, allowlisted operations, user systemd jobs, telemetry, logs and a separate
root maintenance helper. Built and tested with a real browser using fixtures.
Prometheus, node_exporter and the hardware collector were deployed on loopback.
Existing Halogen was not stopped for the initial panel installation. These units
must not be assumed active after reboot.

The initial installation lacked Cockpit and a pkexec authorization agent.
The operator subsequently installed Cockpit, tmux and the root helper and
confirmed PAM login over HTTPS. The Cockpit bridge was tested with the controller.
The operator subsequently rebooted and a new boot was observed. Cockpit required
the FreeBind recovery described below; the operator confirmed it restored access.
This does not validate training or every maintenance path. Deploying the UI does
not restart engines; explicit operations can. A supervised checkupdates job
completed; its result is time-dependent, not a permanent claim.

## Cockpit visual integration

Halo Control uses PatternFly 6 colors and typography, without a separate blue
palette, gradients or independent theme selector. It follows Cockpit's
`shell:style` preference (`light`, `dark`, `auto`), `storage`/`cockpit-style`
events and system preference in automatic mode, without changing that preference.
Charts, logs, forms and terminal update live; theme changes do not close console
sessions. Tests cover both themes, live switching, mobile width and at least
3:1 contrast between chart series and the plot background.

## Engine artwork and status

All six cards use original artwork from official repositories: the llama-swap
mascot, Halogen artwork, Laya logo, ComfyUI symbol, Unsloth Studio logo and
LLaMA-Factory header for LlamaBoard. Files are served from `public/engine-art/`, without CDN
or external requests, preserving proportions and using Studio and Laya's official
light/dark variants. Failed images retain the engine name and controls.
`public/engine-art/ATTRIBUTION.txt` records provenance, revisions and terms,
with original notices; artwork revisions do not upgrade installed engines.
It is also accessible from the attribution link below the cards.
Halogen retains its own terms and Peonist trademarks, not MIT/Apache licensing.
Identifying these integrations does not imply endorsement.

Status combines an icon, text and color with at least 4.5:1 text contrast:

- **Green:** running with HTTP available. Halogen displays **Cargado** when its
  container is present and the gateway responds; this does not verify completed
  model loading, inference or training.
- **Red:** stopped/unloaded or failed, distinguished by wording and icon.
  The Spanish terms parado and detenido both mean stopped; normal stops are not
  presented as failures.
- **Orange:** paused, starting/stopping, legacy instance active or HTTP readiness
  unconfirmed. A running process does not guarantee availability.
- **Gray:** unknown, missing or unconfigured, without assuming a stopped state.

Studio and LlamaBoard unit transitions/failures take priority over container
state. Labels explain their scope and update through existing polling; actions
and operational protections are unchanged. Browser tests cover local loading,
broken images, live theme/status changes, contrast and 390/768/1024/1440 widths.

## Laya on the shared gateway

Laya's card shows CPU status, official artwork, start/stop controls and shared
logs. It is the sixth card, not a sixth editable detail page. It uses Halogen's
original llama-swap; no parallel proxy or implicit gateway start is performed.
The gateway must be active. Stop refuses in-flight requests and unloads only Laya;
polling never loads a stopped container. New external requests may reload it.
Stopping the shared gateway unloads both models.
[Architecture](../inference/LAYA.en.md) and [step-by-step tests](../../docs/en/laya-testing.md).

## Temporary notifications

Global notices and editor results use PatternFly toasts, without another Toastr
library: eight seconds, twelve for errors, manual close and at most four visible.
They are deduplicated by message/type, follow Cockpit's theme and do not displace
widgets. Critical states, service blockers and maintenance/reboot progress remain
visible in their sections. Activity keeps operation records after a toast expires.
Notifications are not stored in browser storage.

## Network graphs and widget layout

Overview and Metrics include receive/transmit graphs in Mbit/s with an interface
selector and the shared history range. They use existing `/proc/net/dev` rates,
with no active speed test or packet capture. Physical interfaces, bridges and
veth traffic are not added together. Missing samples remain gaps rather than
zero. Initial selection prioritizes names other than loopback and common Docker
bridge interfaces.

Grid spacing, adaptable cards and wrapping headings keep widgets separated.
Chart legends sit above the plot, away from the bottom zoom control. Browser
checks cover collisions and horizontal overflow at 390, 768, 1024 and 1440 pixels.

## Disk activity, temperature and occupancy

Overview and Metrics show occupied/available space history (GiB), I/O active
time (%), read/write throughput (MiB/s), and accessible NVMe/drivetemp hwmon
sensors. Sensors are separate: controller and internal temperatures are not
interchangeable. Capacity describes the workspace filesystem, not all disks
combined. Throughput is per physical device, excluding duplicate partitions,
zram and device mapper. NVMe active time is not a saturation guarantee.

**Analizar ocupación** launches a manual read-only job at low CPU/I/O priority,
limited to 120 seconds per root and output depth 3. It scans metadata under the
user home, AI workspaces, caches, `/usr`, `/var` and `/opt` where present, without
following symlinks or crossing filesystems within each root. It never reads file
contents or deletes data. The panel ranks 25 large directories with bars and
path-based category hints, plus a separate `docker system df` inventory. Results
are privately cached; directory traversal is not repeated every five seconds.

Directories include descendants and some roots overlap: do not add rows or
Docker sizes (shared layers). Reflinks, snapshots, metadata and deleted-but-open
files explain differences from actual occupied space. Permissions/time limits
are marked partial, never interpreted as zero. The initial real scan encountered
partially readable roots; no root elevation was used. Path names are private too.

## Engine details, allowlisted editing and secrets

Every engine card opens **Ficha y logs** with saved configuration, observed
environment and logs. Docker environment describes the existing container;
there is no effective container environment when none exists. LlamaBoard can
show clearly identified historical-container logs. Halogen shares the gateway
journal and adds its current container logs.

| Engine | Editable fields, only while stopped |
| --- | --- |
| llama-swap | Health/unload timeouts and global concurrency |
| Halogen | Context, output, slots, KV pool and prefill arena |
| ComfyUI | GPU reserve, cache, BF16 VAE, smart memory, hipBLASLt and AOTriton |
| LLaMA-Factory | Shared memory, HF offline mode and tokenizer parallelism |
| Unsloth Studio | Shared memory, HF/Transformers offline and tokenizer parallelism; recreates the stopped container |

Halogen also requires llama-swap to be stopped because a request can load the
model again. Saving checks strict types/ranges, unit/container state, pending
jobs, launcher locks and the source revision. It never stops or starts services;
changes take effect on the next manual start. Commands, paths, images, network
settings and credentials are not freeform editable. Allowed maxima do not
promise that every combination fits in memory.

Studio recreation uses the local Docker API, with no secrets in command-line
arguments or logs. It preserves immutable image ID, Docker configuration, UID/GID,
groups, GPU devices, ports, mounts, environment, credentials and network settings.
Only requested allowlisted fields change. No image update or persistent-data
deletion occurs, and Studio database passwords are not reset. Unreviewed writable
layer changes cause rejection rather than silent data loss.

The replacement is created and verified while stopped before the original is
renamed as a retained backup. Rename failures attempt to restore the original
name; interrupted transactions block further starts/edits for operator review.
Private 0600 records live in `data/studio-recreation/`. Backups are not removed
automatically, even after a healthy start. Both containers share bind mounts:
the old container is **not a data backup** and cannot undo future data changes.
Never start both together. Compose can overwrite panel options; reconcile its
source before using it to recreate Studio.

Studio was stopped and recreated with its existing values. Image, environment,
mounts, permissions, devices and network settings were compared successfully.
The replacement was left stopped and the original retained during recreation,
without interrupting Halogen. Later successful `switch-studio` operations were
observed; their completion criterion includes `/api/health`. That is not training
validation or a permanent container-health guarantee.

ComfyUI and LlamaBoard read private options in `inference/data/` on every start.
The gateway adapter is deliberately limited to the reviewed private
`start-coder-halogen.py` launcher and `gateway-coder-halogen-noauth.yaml` JSON
configuration. It discovers the profile from the active command, not a historical
reference. The private launcher must hold `service_options.lease('gateway')`
and inherit its descriptor when executing llama-swap; mismatches fail closed.
That guard was added locally with a private backup, without restarting the gateway.
Other deployments require reviewing the source adapter and guard rather than
assuming a filename. Halogen edits create an immutable profile and atomically
replace the gateway configuration pointer, metadata and concurrency after
`llama-swap -validate`. Old profiles remain available. Replacements have private
0600 backups, with no automatic pruning. Audit records contain field names only.

**Mostrar secretos y valores privados** reveals available configured values
on demand within authenticated Cockpit. The gateway process environment is
included only when PID, executable and owner match. Studio password databases
and unrelated `.env` files are not read. Values clear when switching tabs or
leaving the detail page and are not stored in localStorage or audit history.
Logs refresh every three seconds, support pause/filter, and return up to 250
lines per source and 80 KB total. Redaction is best-effort: prompts and other
private data can remain and must be reviewed before sharing.

Tests cover synthetic private saves/conflicts, generated launch commands and
browser fixtures with a simulated bridge. All five detail/log queries were
checked on the host without printing secrets. Active Halogen settings were not
changed and no new GPU startup was validated by this work.

## Components

| Component | Purpose |
| --- | --- |
| `frontend/` | Dashboard, engine details, theme, charts, toasts, terminal and maintenance UI |
| `control.py` | Fixed operations, state, supervised jobs and SQLite audit |
| `engine_details.py` | Fixed sources, validation, optimistic revision, reveal and logs |
| `studio_recreate.py` | Stopped Studio recreation with private recovery records |
| `llamafactory.py` / `unsloth.py` | Manual launchers with ownership/GPU lease checks |
| `reboot.py` | Supervised stops, temporary reservation and final verification |
| `metrics.py` / `storage.py` | Telemetry and on-demand filesystem metadata inventory |
| `install.py` / `install_metrics.py` | User package/units and pinned monitoring tools |
| `maintenance.py` | Installed root-only update/report/reboot helper |
| `install-system.sh` | Root helper and explicit loopback/private Cockpit socket |
| `repair-cockpit.sh` | Idempotent FreeBind socket recovery without firewall changes |

## Installation

Host requirements: Linux, Python 3.12+, user systemd, Docker, journalctl and
checkupdates. Frontend requires Node 22.12+; use the lockfile. npm 11.6.0 was
used to work around a dependency resolver bug in npm 10.9.

From this workspace:

```bash
npm ci --ignore-scripts
npm test
npm run build
python3 install.py --start-metrics
```

The installer preserves existing inference services and rejects overwriting
conflicting units. ComfyUI remains manual, with no automatic boot startup.
Files are installed to `~/.local/share/cockpit/halo_control`. Build output and
node_modules are ignored. Vite's external cockpit.js warning is expected.

Edit private `data/config.json`, mode 0600, for the actual gateway origin,
ComfyUI bind, model ID, optional private admin-key file and SSH aliases. Defaults
use loopback. Never publish real addresses, credentials or runtime data. Changing
ComfyUI bind also requires reviewing its generated unit; conflicting units are
not overwritten silently. For remote clients, set the same `<PRIVATE_LAN_IP>`
in `comfyui_bind` and the ComfyUI unit's `--bind`, reload user systemd and restart
ComfyUI only after confirming its queue is empty. The UI link derives from that
configuration rather than a browser-local loopback address. Access is then
`http://<PRIVATE_LAN_IP>:8188`, without its own authentication or TLS; Cockpit
login does not protect this separate port. Trusted LAN only, no router forwarding.
Public defaults remain loopback; actual addresses belong only in private files.
Root helper executes only an installed root-owned copy.

### Administrative activation on a new host

In a local administrative terminal, review CachyOS news, active workloads and
recovery before a full distribution update. Do not partially upgrade Arch.
From the repository root, after reviewing both scripts:

```bash
sudo pacman -Syu --needed cockpit tmux
sudo bash workspaces/halo-control/install-system.sh
```

Authentication uses the **local Linux username/password through Cockpit PAM**,
not a separate password database. The installer requires `/etc/pam.d/cockpit`
without reading shadow or replacing PAM policies. Log in as the inference
operator whose home contains the user extension and units. Enter credentials
only into Cockpit HTTPS, never into chat.

For explicit LAN access pass a private IPv4 address to the reviewed installer:

```bash
sudo bash workspaces/halo-control/install-system.sh <PRIVATE_LAN_IP>
```

Wildcard/public addresses are rejected. The firewall is not modified: authorize
TCP 9090 only from the trusted subnet using local administration. Verify/trust
the certificate before entering credentials. Existing socket overrides are not
silently replaced. `FreeBind=yes` allows the socket to start before Wi-Fi/DHCP
assigns its configured private address without listening on all interfaces.
For older installations reporting `Cannot assign requested address`, add a
separate administrative socket drop-in containing `[Socket]` and `FreeBind=yes`,
reload systemd and restart `cockpit.socket`. Keep a DHCP reservation: FreeBind
does not ensure that the configured address will be assigned to this host.

The helper installer binds Cockpit to loopback port 9090 with TLS by default. Use an approved
SSH tunnel, or explicitly configure a trusted LAN bind and trusted certificate.
Do not expose it to the Internet, disable TLS checks or assume a passwordless
local login is a valid Cockpit credential. Firewall, router, accounts and polkit
policy are not changed automatically. Select **Tools → Halo Control** after login.
A standalone static preview fails closed, with no operational controls.

Actions execute with a single click, without a confirmation dialog or typed
confirmation, as requested for this lab. Duplicate submissions are blocked;
queue checks, GPU exclusion and backend permissions remain. Update and reboot
differ: update opens its console immediately, while reboot requires explicit
confirmation warning that active AI work will be interrupted. Cockpit still supplies authentication
and privilege authorization; PAM/polkit and interactive pacman prompts are not
bypassed. The terminal multiline-paste warning remains a separate safeguard.
There is no separate panel RBAC. A Docker-capable operator already has authority
equivalent to root; the panel is not a sandbox around that account.

## Metrics and persistence

The collector samples /proc, sysfs and hwmon every five seconds, without compute
GPU access. Metrics include CPU/core usage, load, RAM/cache/swap, GPU busy, GTT,
VRAM, temperatures, available power reading, disk capacity/I/O, network and PSI.
Do not add RAM, GTT and VRAM as independent physical memory. Missing readings
are unknown rather than zero; power may describe the package/APU.

The UI uses a bounded SQLite cache (15 days, at most 259200 samples), returning
roughly 900 points per query. Prometheus also retains standardized metrics for
15 days with a 2 GB limit. All data is ignored under `data/`.

Reproduce binary downloads from the repository root:

```bash
gh release download v1.12.1 -R prometheus/node_exporter -p node_exporter-1.12.1.linux-amd64.tar.gz -p sha256sums.txt --dir workspaces/halo-control/data/node-release
gh release download v3.14.0 -R prometheus/prometheus -p prometheus-3.14.0.linux-amd64.tar.gz -p sha256sums.txt --dir workspaces/halo-control/data/prometheus-release
python3 workspaces/halo-control/install_metrics.py
```

The installer checks SHA256 and extracts only expected regular binaries.
Collector listens on loopback 19100, node_exporter on 19101 and Prometheus on
19090. These units are started, not enabled at boot automatically. Review before
enabling persistence. ComfyUI should not be enabled on boot by default.

## Safe operations and limitations

Actions are serialized and run through supervised user systemd jobs. Jobs persist
beyond browser closure, with UID, result and error recorded. Halogen loads through
a small gateway request rather than a second independent engine. Unloading it
does not prevent a new request from loading it again. ComfyUI reuses the existing
cooperative GPU lock and corrected CPU-offload launcher.

ComfyUI queue checks reject stopping with queued/running jobs. Gateway activity
is checked through the SSE snapshot, waiting up to the configured timeout.
**There is no global admission gate on the existing direct gateway endpoint.**
A request can race with the final stop; v255 drains only up to 30 seconds after
SIGTERM. Reserve external clients before switching. The cooperative GPU lock
cannot constrain unrelated processes or containers. No silent force-cancel or
blind fallback startup is offered.

Old jobs display unknown; inspect journal/processes before retrying. Logs from
new units survive container removal subject to host journald retention. The UI
shows 250 lines, with filtering, pause and bounded export, not unlimited search.
Prompts may appear in private logs despite basic secret redaction.

## Existing Unsloth Studio

The Studio card adopts `halostrix-unsloth-studio-studio-1`, not a new installation.
`unsloth.py` verifies project/service labels, pinned source revision, image labels
and operator non-root UID. The status adapter reads only identity, state and
bindings. Engine details/recreation do inspect container environment, hide it by
default and preserve credentials without publishing them. Missing/foreign containers fail closed;
no image rebuild, database migration or credential reset is attempted.

Manual `halo-unsloth.service` attaches to `docker start` and holds the shared
inference GPU lock throughout the session. Stop targets the verified ID, retaining
the container and all persistent data. The UI URL derives from its existing
private LAN/loopback binding for port 8888; readiness uses `/api/health`. New logs
are captured in journald and exposed through the panel log selector. Studio keeps
its own login, independent from Cockpit; firewall and passwords are unchanged.

Start requires other GPU services stopped. Switch-to-Studio first validates the
existing container, then checks/stops ComfyUI and drains/stops the gateway.
Explicit Studio stop can interrupt training/exports/inference: finish those jobs
inside Studio first. There is no authenticated all-jobs idle detection contract.
While Studio is active, text/image switches still require explicit stop.
**Switch to LlamaBoard** is the deliberate exception: it explicitly stops Studio
and may interrupt training. Original scripts bypass the cooperative lock.
Stop Studio before updates; confirmed reboot stops it automatically. Generic
process checks are not sufficient protection for arbitrary training workers.

Observed inventory: approximately 51 GB local image, PyTorch 2.11/ROCm 7.14,
revision `e18a069c15cde98c7af77ccdb952254db8b0315d`, stopped container with existing
persistent data. No real `.env` was read. Historical evidence validates UI/GPU,
not training; bitsandbytes was absent, so 4-bit QLoRA is not promised. Tests cover
ownership, GPU lock, transition ordering and browser card/link. Studio was not
started and Halogen was not interrupted to add this integration.

## LLaMA-Factory / LlamaBoard

The card provides start, explicit stop, switch from inference/images, status,
logs and LAN link. `llamafactory.py prepare --bind <PRIVATE_LAN_IP>` inspects the
legacy container and records its immutable local image ID and data root in
private configuration, without reading real environment files or rebuilding.
It validates revision `7af909522a951e3ad9f022ea6f88b6755257eaa5`, upstream source
and legacy Compose labels. Only the seven reviewed bind mounts and operator-owned
writable directories are accepted; ownership is never changed automatically.
Startup additionally mounts cache/config at `/workspace/llamaboard_cache` and
`/workspace/llamaboard_config`, the relative paths used by the application,
without making the whole workspace writable.

The historical container remains stopped and intact. A separate ephemeral
`halostrix-llamaboard-panel` container runs non-root, with dropped capabilities,
no-new-privileges, explicit GPU devices and a concrete private IPv4 binding on
7860, instead of inheriting wildcard binding/root identity. It reuses the existing
approximately 50.4 GB image and data. Manual `halo-llamafactory.service` holds the
GPU lease and sends logs to journald. Stop never deletes models/datasets.

No built-in authentication: trusted LAN only, no Internet exposure. Cockpit
login does not protect port 7860. Opening the UI does not start training. Finish
training/export jobs before explicit stop; automatic queue detection is absent.
Active new or legacy LlamaBoard blocks panel switches to Halogen, ComfyUI or
Unsloth. Do not run the old launchers alongside the panel.

Switch-to-LlamaBoard stops ComfyUI and the gateway after activity checks, then
explicitly stops Studio before starting LlamaBoard. This may interrupt Studio
training; finish it before switching. Plain start still rejects active competing
engines. The configured link stays visible independently of HTTP health.

Actual non-root startup failed on permissions for `llamaboard_cache`; after
correcting its persistent mounts, startup and HTTP 200 were verified without
stopping other engines (already stopped). Training remains unvalidated. Mocked
tests cover stop ordering, failures and link visibility before HTTP readiness.

## Terminal, SSH and maintenance

xterm.js connects to Cockpit PTY as the authenticated user. Optional SSH targets
are preconfigured aliases with strict host-key verification and no agent
forwarding. Enroll known_hosts separately; do not trust unknown keys automatically.
The browser never stores SSH private keys. Terminal access grants the account's
actual permissions and is not restricted command execution.

**Aplicar actualización completa** opens and scrolls to a dedicated console on
the Updates page, not the generic SSH terminal. It displays connection status,
stdout/stderr, interactive pacman prompts and closure/exit details. If Cockpit
rejects permission, enable administrative access and reconnect; active inference
must be stopped explicitly before retrying. No output is never treated as success
or confirmation that an update started.

The console stays connected while navigating the panel and has no maintenance
idle timeout. Closing the viewer does not cancel tmux. Reconnect attaches when a
session exists but may start a new update after it ended; it is not a status-only
query. Output, rejection and interactive-input tests use a simulated bridge;
pacman was not executed to validate this interface.

Confirmed reboot checks administrative access before stopping anything and reads
the update report, first checking for an open update tmux session. A finished
update may still be waiting for Enter and therefore block reboot. **Ver sesión
de actualización existente** only attaches to that session, never starts pacman.
Press Enter only if the session shows completion and requests it; otherwise wait.
The panel does not kill tmux or send Enter automatically.
A supervised job stops the four AI units, owned inference
containers and verified Studio/LlamaBoard containers, including active legacy
LlamaBoard. This can interrupt generations/training rather than drain queues;
persistent containers and data are retained. Failed/unknown stop states prevent
the reboot request. Panel operations are temporarily reserved through preparation
and final verification. Package managers and arbitrary unrelated processes are
not stopped. The installed root helper retains its final process, package lock
and tmux checks; rejection is visible and is not reported as success.

Without Cockpit administrative access, no services are stopped. An accepted
reboot command is not proof of reboot: a changed boot ID confirms it after
reconnection. A countdown retries every five seconds for up to ten minutes.
It remains visible above the iframe even when Cockpit hides the disconnected
panel. Boot ID probes require no administrative privileges. If the bridge fails,
the panel checks the same-origin web page without cache. When the web returns
after an outage (or responds after 30 seconds), Cockpit reloads once to restore
the bridge; web availability alone does not confirm reboot. A changed boot ID
with a connected bridge triggers a refresh after two seconds. The reboot command
is never repeated and engines are not started automatically.
A credential-free sessionStorage receipt verifies the new boot after refresh.
Cockpit may require login again; authentication is never bypassed. Expiry shows
an actionable message without reload loops. Closing monitoring does not cancel
the requested reboot. Losing the browser session may lose automatic verification.
Reboot tests are simulated; the host was not restarted during deployment.

Maintenance requires the root-owned `/usr/local/libexec/halo-maintenance`, not
repository code executed as root. It accepts only update, internal update worker,
report and reboot. Stop/drain AI first; known inference processes block execution.
The helper also checks package locks and at least 10 GiB free disk space.
Updates run interactive `pacman -Syu` in a root tmux session: disconnection does
not kill the transaction, and reconnecting the maintenance terminal attaches to
it. No automatic prompt acceptance, AUR-as-root, lock deletion or rollback.
Last result is kept in `/var/log/halo-control/last-update.json`. Reboot rejects an
open update session. Process detection is a precaution, not isolation from other
administrators. Snapshot/boot recovery must be validated independently.

Image inspection reads remote manifests and local digests, without pulling or
switching images. It exposes evidence rather than assuming manifest-list and
architecture digests are comparable. System updates and container updates are
separate operations.

## Verification

From repository root:

```bash
python3 -m unittest discover -s workspaces/halo-control/tests -v
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
```

From workspace:

```bash
npm test
npm run build
npx playwright install chromium
npm run test:browser
npm audit
```

September 24 revision: 101 panel Python tests, 57 inference tests, 50 frontend
unit tests, 40 Playwright tests and 14 site fixtures. Coverage includes settings,
recreation, transitions, links, toasts, themes, responsive layout and simulated
confirmed reboot. The queried npm audit reported zero vulnerabilities, not a
penetration test or validation of live PAM, update safety or reboot.

Without global Node, use the already installed private binary from this workspace:

```bash
data/node node_modules/typescript/bin/tsc --noEmit
data/node node_modules/vitest/vitest.mjs run frontend
data/node node_modules/vite/bin/vite.js build
PATH="$PWD/data:$PATH" PLAYWRIGHT_BROWSERS_PATH="$PWD/data/browsers" data/node node_modules/@playwright/test/cli.js test
python3 install.py
```

Do not download tools or restart AI services merely to document results. The
installer copies frontend assets; collector changes require an explicit restart
of its telemetry unit, not AI engines.
The complete public site still fails on an unrelated pre-existing EngramHalo link
outside the publication allowlist; that boundary was not expanded.

## Recovery

### Website unavailable after reboot

In the observed September 23 reboot, Cockpit started before Wi-Fi acquired its
configured address and stayed failed with `Cannot assign requested address`.
The address arrived later but no process listened on 9090. A saved UFW rule
allowed LAN clients and no recent blocks were logged; the active ruleset could
not be inspected without root. The operator confirmed recovery after running
from the repository root:

```bash
sudo bash workspaces/halo-control/repair-cockpit.sh
```

The script creates `halo-freebind.conf` with `FreeBind=yes`, preserving address,
port and other overrides. It rejects symlinks, unsafe permissions and a differing
existing file; reloads systemd; enables/restarts `cockpit.socket`; and queries UFW.
It changes no firewall rules, certificates or credentials and never reboots.
Failures display status and journal. Keep a DHCP reservation; FreeBind does not
assign an address. No additional reboot was tested after this repair.

### Telemetry after boot

The collector was restored manually after reboot. To enable already installed
telemetry as the operator after reviewing its units:

```bash
systemctl --user enable --now halo-metrics.service halo-node-exporter.service halo-prometheus.service
```

This does not enable GPU engines. Startup without a logged-in session also needs
the operator's linger policy checked; it is not changed automatically. Cached
samples do not prove that Prometheus is currently running.

### Removing the panel without losing data

Stop the three telemetry units to remove monitoring. Preserve `data/` and existing
inference units. Remove only the owned Cockpit user extension after backup.
Do not stop Cockpit from its own terminal during maintenance: a tmux update may
continue after disconnection. No actual AI services were migrated automatically.

Sources: [Cockpit](https://cockpit-project.org/),
[ECharts](https://echarts.apache.org/), [xterm.js](https://github.com/xtermjs/xterm.js),
[Prometheus](https://github.com/prometheus/prometheus),
[node_exporter](https://github.com/prometheus/node_exporter).
