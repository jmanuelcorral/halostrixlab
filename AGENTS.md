# Repository reference

Start with the [English documentation](docs/en/README.md) or the
[Spanish reference](docs/configuracion-reutilizable-halo-strix.md), and the
[documentary profile](config/halo-strix.reference.json).
Distinguish historical evidence, recommendations and live observations.
These files do not establish the host's current configuration or health.

Public examples must use placeholders, not private host addresses, usernames,
credentials, session identifiers or local agent state. Do not read real
environment files to populate documentation; use the reviewed `.env.example`
templates. Preserve ignored local files and never force-add them for publication.

## Documentation checks

Use the ignored `.venv-site` environment with `site/requirements.txt` installed:

```bash
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

The builder discovers Markdown under `docs/` recursively. New guides need index
links, not a hardcoded document list. A successful fixture test run does not
prove the complete site builds; run both commands and report unrelated source
publication failures without broadening the publication allowlist automatically.

The inference workspace uses `python3 -m unittest discover -s scripts/tests
-p 'test_inference*.py' -v` (run as one command). Optional tests use the pinned
binary in ignored `workspaces/inference/data/bin/llama-swap` against a synthetic
loopback backend; they do not validate GPU inference. All workspace credentials,
installed tools and generated configuration belong under its ignored `data/`.
Laya CPU shares the existing llama-swap gateway with Halogen; backend 18181 is
loopback only. The temporary proxy on 18081 and halo-laya.service are retired.
Use a non-exclusive persistent CPU group, preserve GPU routing and credentials,
and allow GPU slots plus CPU concurrency. Gateway stops unload both models.
Use `python3 -m unittest discover -s scripts/tests -p test_inference_laya.py -v`.
Keep pinned source, weights, image ID and evidence in `data/laya/`.
No decision-to-Halogen pipeline is implemented; clients compose them elsewhere.
Laya test procedures live in `docs/pruebas-laya.md` and `docs/en/laya-testing.md`:
separate synthetic suites, live typed API checks and optional lifecycle/GPU work.
Use the existing panel client to resolve private origins without printing secrets;
never read real environment files for documentation or restart engines just to
refresh dated evidence. Four service stacks are separate from three catalog models;
only the original five engine/settings adapters have editors. Catalog selections
allow one GPU model plus Laya CPU, never Halogen plus Gufo. Preflight fails closed
for busy gateway/other stacks; partial load failures may retain a loaded model.
Context/slots follow active profiles; disk weights are not RAM/GPU estimates.
Use `python3 -m unittest discover -s workspaces/halo-control/tests -p test_model_catalog.py -v`.
Gateway edits require reviewed active config, drained requests, stopped gateway,
settings lease, validation and backup. Do not recreate a parallel proxy.
Gufo Qwen3.8-27B uses the existing exclusive GPU group, not Laya's CPU group.
Use `python3 -m unittest discover -s scripts/tests -p test_inference_gufo.py -v`.
Its pinned target/drafter, profile and evidence stay in `data/gufo/`; setup and
trial limits are in `workspaces/inference/GUFO.md` and `GUFO.en.md`. Use `/ready`
for Gufo readiness, not process-only `/health`. GPU switches may take over a minute.
Gufo defaults to 131072 context per session and at most two slots. Halo Control's
catalog uses supervised gufo-load/gufo-unload actions; unload retains the alias.
Native llama-swap v255 UI Load hits backend `/`, which Gufo returns as 404; use
`/ready` through the catalog adapter. Upgrade immutable profiles only while the
existing gateway is stopped, preserving old profiles and validating the pointer.
Professional portrait workflows use Qwen Image Edit 2511 and its matching Edit
Lightning LoRA, not Image 2512. `portrait_workflow.py` installs a non-overwriting
single-photo workflow plus separate `--references 2` and `--references 3` variants;
`download_portrait_models.py` verifies pinned Edit weights. PORTRAIT.md/PORTRAIT.en.md
record the operator-reported iris-color drift separately from synthetic validation.
Multi-photo prompts specify blue-gray eyes for the reported case, not all subjects.
Face masking/original-pixel compositing is recommended but not implemented.
Run `python3 -m unittest discover -s scripts/tests -p test_inference_portrait.py -v`.
Never search private inputs for a person's photo; require explicit user selection.
Winnow/Ollaya research is in `docs/investigacion-winnow-ollaya.md` and its
English equivalent. The subsequently authorized CPU deployment is documented in
`workspaces/inference/OLLAYA.md` and `OLLAYA.en.md`. Use `ollaya_runtime.py`
for pinned download/build/configure/verify and gateway load/unload. Its fixed
`winnow-12b-cpu` alias exposes only typed decisions and readiness, not Ollaya admin
routes; backend 18182 is loopback. Keep `data/winnow/` private. Ollaya uses 8 CPU,
32 GiB memory cap, 8192 context/6144 state budget and one request (429 on overlap).
E4B is a different model; neither reviewed distribution qualifies AMD GPU serving.
Native Winnow decisions reject CPU-only execution. Preserve the sole llama-swap,
Laya CPU and exclusive GPU routing. Gateway install --restart is drained maintenance,
not hot reload; it restores previous residents. No Winnow Halo Control card exists.
Run `python3 -m unittest discover -s scripts/tests -p test_inference_ollaya.py -v`.
The Docker bridge disables outbound masquerading, not a universal firewall policy.
Observed small cgroup memory excludes some shared mmap/page-cache charges.

Halo Control uses `python3 -m unittest discover -s workspaces/halo-control/tests
-v`. In `workspaces/halo-control`, run `npm test`, `npm run build`,
`npm run test:browser` (Playwright Chromium required), and `npm audit`.
Private telemetry, package inventories and screenshots stay in its ignored
`data/`; browser fixtures do not prove a live Cockpit login or root operations.
Do not apply system updates or reboot as an installation smoke test.
Halo Control follows Cockpit's `shell:style` preference and `cockpit-style`/
`storage` events, with OS preference for auto. Use PatternFly 6 theme tokens and
`pf-v6-theme-dark`; do not add an independent theme toggle or hardcoded palette.
Theme changes must repaint charts and terminal without reopening console sessions.
Engine artwork stays local in `public/engine-art/`, unmodified with pinned
provenance and original notices in `ATTRIBUTION.txt`. Keep that inventory in the
installed package; do not infer artwork or trademark rights from code licenses.
Card status combines icon/text/color, distinguishes stopped from failed, and
must not equate gateway HTTP health with model inference readiness. Browser
checks cover local image loading, fallbacks and 4.5:1 status text contrast.
Reboot reconnection uses a credential-free sessionStorage receipt, bounded
read-only boot-ID probes and uncached same-origin web checks. Its countdown
must remain visible above Cockpit's hidden iframe after disconnection. Reload
the same-origin shell at most once per request, never resend reboot, and only
a changed boot ID confirms reboot. Test with fixtures, not a host reboot.

Engine details use fixed source adapters and stdin-only save payloads. Keep
secrets out of tool output, audit records and browser storage. Halogen edits
must follow the active gateway command, not a historical profile filename, and
require the gateway stopped plus the launcher settings lease. Validate candidate
gateway configuration before atomically changing its profile pointer. Unsloth
allowlisted edits recreate the stopped container through the local Docker API;
docker start alone does not apply env edits. Preserve immutable image, mounts,
credentials and runtime settings; keep the original container and private
transaction records. Pending recreation markers block starts and edits. Retained
containers share bind-mounted data and are not data backups. Do not interrupt
other GPU engines merely to health-check a stopped replacement.
When global Node is absent, the ignored `workspaces/halo-control/data/node` can
run `node_modules/typescript/bin/tsc --noEmit`, `node_modules/vitest/vitest.mjs
run frontend`, and `node_modules/vite/bin/vite.js build` from that workspace.
Browser tests additionally use `PLAYWRIGHT_BROWSERS_PATH` pointing at its private
`data/browsers` and put the workspace `data` directory on PATH.
