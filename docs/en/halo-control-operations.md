# Halo Control, ComfyUI and Laya: September 24, 2026 consolidation

[Español](../halo-control-operacion.md) | [Project](../../README.en.md) |
[Halo Control manual](../../workspaces/halo-control/README.en.md) |
[Inference and ComfyUI](../../workspaces/inference/README.en.md)

This report consolidates implementation, observations and fixes from September
22-24. It does not replace the [September 17 Halogen deployment](halogen-128k-deployment.md)
or the historical Lemonade baseline. It is not a permanent audit: inspect current
status and logs before operating. No private configuration is published here and
this report does not authorize changes on another host.

## 1. Architecture and access surfaces

- **Halo Control** is a Cockpit Linux extension using React/TypeScript,
  PatternFly 6, ECharts and xterm.js. Cockpit authenticates Linux users through
  PAM and runs fixed Python controller operations as that user.
- **kyuz0 AI Toolbox Cockpit** is a separate model/runtime-management TUI,
  not the Cockpit Linux web server.
- **llama-swap** serves Halogen GPU and Laya CPU through one gateway. ComfyUI, Studio and
  LlamaBoard use manual launchers/units sharing a cooperative GPU lease.
- Operations are serialized supervised user-systemd jobs with SQLite records.
  Settings use fixed source adapters and stdin payloads, not a freeform command editor.
- Updates/reboots use an installed root-owned helper. Mutable repository code
  is not elevated from the panel.
- The public website is static documentation, not the control plane. Credentials,
  private inventories, telemetry, screenshots and `data/` are excluded.

| Service | Documented access | Security boundary |
| --- | --- | --- |
| Cockpit Linux | `https://<PRIVATE_LAN_IP>:9090` | PAM/TLS; verify certificate |
| llama-swap | `http://<PRIVATE_LAN_IP>:18080/ui/` | Private LAN exception, not public default |
| Laya | Same origin on 18080, `/upstream/laya/v1/systemone` | Inherits Halogen access policy; backend 18181 loopback only |
| ComfyUI | `http://<PRIVATE_LAN_IP>:8188` | No own authentication or TLS |
| Unsloth Studio | Container binding, normally port 8888 | Studio's own login |
| LlamaBoard | `http://<PRIVATE_LAN_IP>:7860` | No own authentication or TLS |
| Metrics | Loopback 19100, 19101, 19090 | Collector, node_exporter, Prometheus |

Cockpit login does not protect direct AI UI ports. Do not expose them to the
Internet. A Docker-capable operator already has root-equivalent authority; the
panel does not sandbox that account.

## 2. ComfyUI image generation

A kyuz0 image was pinned by digest: ComfyUI 0.31.0, PyTorch
`2.14.0a0+rocm7.15.0a20260721`, with 30 bundled workflows. Observed image size
was 21.8 GB; `latest` does not guarantee these versions. The pin and persistent
files stay private under `workspaces/inference/data/comfyui/`.

An isolated Qwen Image 2512 BF16 downloader was added. It uses no GPU, runs the
pinned image's helpers, has its own lock and never mounts the real HOME.

| Model file | Approximate observed size |
| --- | --- |
| `diffusion_models/qwen_image_2512_bf16.safetensors` | 40.86 GB |
| `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors` | 9.38 GB |
| `vae/qwen_image_vae.safetensors` | 0.25 GB |
| `loras/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors` | 0.85 GB |

Total: 51.35 decimal GB, approximately 47.82 GiB. Safetensors headers/lengths
were inspected, not independently verified cryptographic hashes. The private
workflow referenced the wrong Edit-2511 LoRA; it was changed to Image-2512 and
graph links were checked. Upstream workflow copies are not modified automatically.

The first `--gpu-only` generation exhausted GTT during LoRA patching and exited
139. CPU offload and 4 GiB reserve fixed the tested case without BIOS, kernel or
GTT changes. A real 1024-square, batch-one, four-step run produced a valid PNG in
about 45 seconds of server execution. Halogen was subsequently restored and an
HTTP 200 response checked. This does not prove sustained stability, training,
GPU cancellation or simultaneous capacity for both engines.

## 3. Engine operations and settings

| Button / operation | Behavior |
| --- | --- |
| `ON graceful` on Halogen | Rejects busy ComfyUI, stops it, starts gateway and loads Halogen with a short request |
| `ON graceful` on ComfyUI | Drains gateway requests, stops gateway and starts ComfyUI |
| Switch to Studio | Prevalidates Studio, checks/stops ComfyUI and gateway; active LlamaBoard blocks |
| Switch to LlamaBoard | Prevalidates destination, checks/stops ComfyUI/gateway, stops Studio and verifies before starting |
| Start Laya | Loads CPU through the existing active gateway, without switching GPU engines |
| Stop Laya | Refuses active gateway requests and unloads only Laya; later requests may reload it |
| Plain start | Must not be interpreted as permission to stop another engine |
| Stop training UI | Can interrupt work; no authenticated complete all-job idle detection exists |

`ON graceful` was a label change only. It does not mean waiting on every possible
queue: busy ComfyUI blocks switching, while the gateway has external-client races
and a llama-swap-limited final drain. Studio blocks switching to text/images;
the explicit exception is switching to LlamaBoard, which may interrupt Studio
training. Do not run external launchers alongside the panel.

There are six cards. The original five detail pages show configuration,
available environment and logs; Laya adds status, start/stop and shared logs,
not a dedicated settings editor. Secrets
are revealed on demand inside Cockpit, not persisted in browser storage or audit
values. Logs combine journal and verified containers, up to 250 lines per source
and 80 KB, with pause/filter. Redaction does not guarantee removal of arbitrary
secrets or prompts from logs.

The editor accepts validated fields only while stopped. Halogen also requires
the gateway stopped and follows the active command's profile rather than an old
reference. It creates a new profile, validates the candidate gateway and atomically
changes its pointer with private backups. ComfyUI/LlamaBoard read private options
on startup.

Studio must be recreated while stopped to apply allowed environment edits. Image
ID, UID/GID, devices, mounts, credentials, environment and network are preserved.
The old container and private transaction records remain. Pending transactions
block further starts/edits. Both containers share data: **this is not a data
backup**. Recreation alone proves neither HTTP health nor training.

LlamaBoard failed creating `llamaboard_cache` in a non-writable `/workspace`.
Persistent cache/config directories were mounted at its expected relative paths,
without running as root or exposing the entire workspace as writable. Non-root
startup and HTTP 200 were verified. The configured link is now always visible,
with stopped, HTTP pending and available states distinguished. Training remains pending.

## 4. Laya CPU alongside Halogen

Laya 0.3.9 multilingual (322M) runs in Docker with PyTorch 2.8.0 CPU and
Transformers 4.57.6. Source/weights use pinned revisions and runtime uses an
immutable image ID. It has a 4-CPU quota, 8 GiB limit, non-root execution, no GPU
devices or Docker socket, read-only weights and temporary tokenizer/config copies
for compatibility. Offline inference prevents downloads, not all network egress.

The initial deployment used a separate proxy. **This was corrected:** Laya now
belongs to the original llama-swap, in a persistent non-exclusive CPU group.
`halo-laya.service` was archived and port 18081 closed. Halogen commands/profile
and private access policy were retained. Applying the migration required an idle
check, gateway stop and Halogen reload. Global concurrency accommodates its four
slots plus one CPU request; request-body capture is disabled.

Real simultaneous responses, both catalog entries, and Laya stop/start without
changing Halogen's container ID/start time were checked. Stopping the shared
gateway unloads both, including switches to ComfyUI/Studio/LlamaBoard. Laya's
buttons do not implicitly start the gateway. Panel polling never autoloads a
stopped Laya; green HTTP health does not establish decision accuracy.

Initial observations: about 1.62 GiB container memory, 4.3-5.4 s cold load and
56-80 ms warm synthetic requests. Historical samples, not an SLA. No Laya-to-Halogen
pipeline, automatic engine selection, fine-tuning or business calibration is
implemented; composition belongs to another project.

[Full Laya test guide](laya-testing.md): synthetic tests, live `choice`/`score`/`noul`,
422/413 errors, optional coexistence, panel controls and troubleshooting.
[Deployment manual](../../workspaces/inference/LAYA.en.md).

## 5. UI and telemetry

- Cockpit light/dark/automatic theme, PatternFly colors/fonts, no independent
  toggle. Charts and terminal repaint without reconnecting the console.
- Six cards with local official artwork, pinned provenance and license/trademark
  notices. No CDN, cropping or filters; Laya/Studio use light/dark variants.
- Icon/text status: green active/loaded, red stopped/failed, orange paused,
  transitioning or unconfirmed, gray unknown. Text contrast is at least 4.5:1.
  Spanish parado/detenido are synonyms, not invented backend distinctions.
- Spacing fixes for cards, grids, headings, legends and zoom; collision tests
  at widths 390, 768, 1024 and 1440 pixels. Chart series contrast at least 3:1.
- PatternFly toast notices, no additional Toastr library: eight seconds, twelve
  for errors, manual close, up to four visible, deduplicated by text/type.
  Critical states and maintenance/reboot progress stay visible.
- CPU, GPU, RAM, GTT, temperatures, load, PSI and disk; 15-day history, five-second
  samples and bounded queries. GTT and RAM are not separate physical memory pools.
- Disk capacity, activity, MiB/s and NVMe/drivetemp sensors. Manual low-priority
  `du` scans have limits and show permission-partial results; Docker is separate.
  Do not add parent/child directories, reflinks or shared layers as independent data.
- Receive/transmit per interface in Mbit/s, without packet capture or Internet
  speed tests. Virtual/physical interfaces are not summed. Missing samples stay gaps.

## 6. Updates, reboot and web recovery

Package checking does not update the host. Full update opens a visible privileged
console on Updates with stdout/stderr, prompts and errors; navigation does not
close it. `access-denied` requires enabling Cockpit **Administrative access**;
that authorization is not automatically requested or bypassed.

Reboot requires confirmation. It checks permissions and maintenance, stops
managed engines, verifies their state and invokes the helper. AI jobs can be
interrupted, but package managers are not killed. An accepted command is not a
reboot; a changed boot identifier confirms it after reconnection.

The added reconnect screen counts down to five-second retries for up to ten
minutes, above Cockpit's iframe even when hidden on disconnect. It probes boot ID
without privileges and falls back to uncached same-origin web checks if the
bridge drops. Web recovery (or availability after 30 seconds) triggers at most
one reload to restore the bridge, not reboot confirmation. A changed boot ID
triggers refresh after two seconds. A credential-free sessionStorage receipt
survives refresh; Cockpit may require login. No reboot is resent and no engines
are automatically started. Closing monitoring does not cancel the reboot.
These paths were fixture-tested, not validated through another real host reboot.

One recorded attempt completed service stops but did not reboot. A live maintenance
tmux server was observed, consistent with an open-session blocker; its root
session could not be inspected from the CLI. The panel now checks before stopping
engines and offers **Ver sesión de actualización existente** without starting a
new update. Press Enter only when the finished session explicitly asks for it.

The operator subsequently rebooted and a new boot was observed. Cockpit failed
with `Cannot assign requested address`: its socket started before Wi-Fi acquired
the address. A saved UFW rule allowed LAN access to 9090 and no recent blocks
were logged; this was not a complete active-ruleset inspection without root.
There was no listener on 9090.

The operator ran the repair and confirmed that the website recovered:

```bash
sudo bash workspaces/halo-control/repair-cockpit.sh
```

The script adds `FreeBind=yes` in a separate drop-in, preserves address/port and
unrelated files, reloads systemd, enables/restarts the socket and queries UFW
without changing rules. It neither reboots nor updates packages. New installations
also use FreeBind. Keep a DHCP reservation: FreeBind does not assign the address.
No further reboot was performed after the repair to certify future startup.

The collector was inactive after reboot and was started manually. The three
telemetry services are not automatically enabled at boot. The manual describes
optional enablement; do not confuse monitoring with manually started GPU engines.

## 7. Verification and outstanding work

Reproducible commands are in the linked manuals. September 24 revision: 101 Halo
Control Python tests, 57 inference tests, 50 frontend unit tests, 40 Playwright
tests and 14 site fixtures. These are test results, not permanent health promises.
Playwright simulates the authenticated bridge, without real updates, training or
reboots. The queried npm audit reported zero vulnerabilities, not a penetration test.

The full site still rejects the pre-existing `scripts/engramhalo/.dockerignore`
link outside its publication allowlist. `node_modules`, `test-results` and
`playwright-report` exclusions were added, not broader publication permissions.
Private files remain ignored and must never be force-added to Git.

Outstanding: real Studio/Factory training, repeated generation stability, LAN TLS
and a correctly identified trusted certificate, sustained concurrency/soak
(point-in-time Laya/Halogen coexistence was verified), Laya quality/calibration
on operator data, service verification after another reboot, and data recovery independent of
retained containers. Updates/reboots are not performed merely as installation
smoke tests to close these gaps.
