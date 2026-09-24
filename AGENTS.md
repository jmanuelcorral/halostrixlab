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
refresh dated evidence. Six cards exist, but only the original five have editors.
Gateway edits require reviewed active config, drained requests, stopped gateway,
settings lease, validation and backup. Do not recreate a parallel proxy.

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
