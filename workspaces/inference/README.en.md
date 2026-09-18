# Cockpit, llama-swap and independent Docker runtimes

[Spanish operational guide](README.md) |
[Architecture research](../../docs/en/docker-toolboxes-halogen.md)

**Dated status, 2026-09-17:** [actual Halo deployment](../../docs/en/halogen-128k-deployment.md)
validated Halogen W4B Quality 128K under a persistent user llama-swap service.
Lemonade is disabled; Coder Vulkan was tested and removed from serving without
deleting its weights. Cold boot, soak and parallel slots remain pending.
The September 16 implementation had only offline/synthetic validation.

This README describes **authenticated loopback public defaults**. The private
lab deployment uses an operator-authorized LAN HTTP/no-key exception and a
private unit/launcher that a clone does not transfer. Read the deployment
report before running these commands against the existing service.

## Components

- [manage.py](manage.py): pinned isolated installation, private initialization,
  config generation/validation, foreground gateway, Cockpit, status and unload.
- [runtime.py](runtime.py): allowlisted runtime kinds, digest-required Docker
  images, read-only model mounts, loopback ports and owned-container shutdown.
- [profiles.example.json](profiles.example.json): disabled Coder Vulkan/ROCm,
  Halogen and vLLM profiles. Operator-supplied artifacts are required.
- [compose.yaml](compose.yaml): TLS API edge, with `.env.example` and `Caddyfile`.
- [opencode.example.json](opencode.example.json): provider fragment using private
  environment references, not a replacement for existing client configuration.

llama-swap runs on the host. Runtime servers run in independent Docker
containers. Caddy uses host networking to reach the loopback gateway but has
no GPU or Docker socket. Its pinned binary has a file capability requiring
`NET_BIND_SERVICE` in the container capability bounding set even with a high
port; dropping all capabilities without restoring that one failed in testing.
This is not a privileged container.

## Setup and operation

From the repository root on the target host:

```bash
python3 workspaces/inference/manage.py install
python3 workspaces/inference/manage.py init
```

Requires Linux x86_64, Python venv/pip, Git, authenticated/authorized GitHub CLI
access and Docker access. No sudo, shell-profile changes or system service
installation. llama-swap v255 is downloaded with a fixed SHA256 check; Cockpit
is installed at commit `6959d068c020f3f33bfb8ef743e7ba44a6390dda` in its own
venv. Transitive Python dependencies are resolved and recorded, not hash-locked.

`data/` is private mode 0700 and ignored by Git and the static site.
`data/profiles.json`, `admin.key` and `client.key` are created mode 0600 without
overwriting existing files or printing credentials. Never publish this directory.

On the actual Halo, review driver, GPU/GTT/RAM, current workloads and a private
Lemonade rollback snapshot. Prepare and inspect a pinned image and complete
model files; enable only the intended profile in the private configuration.
Start with Coder Vulkan, 32768 context, 8192 output and one slot. Explicitly
drain/stop the existing inference service before model activation. The launcher
refuses detected existing `lemond`, `llama-server`, `flash_serve` or `vllm`
processes; it does not stop unrelated services.

```bash
python3 workspaces/inference/manage.py generate
bash workspaces/inference/start.sh
```

Generated JSON is valid YAML and is checked using the real `llama-swap
-validate` command. No models preload. The gateway listens only on
**127.0.0.1:18080**; its authenticated web UI is `/ui/`. Port 13305 remains
untouched. Use an approved local tunnel for remote administration, not direct
LAN exposure of port 18080.

The `/v1/models` catalogue publishes each profile's effective context through
`context_length`, `context_window` and `meta.n_ctx`, and its configured output
budget through `meta.llamaswap.max_output_tokens`. These are derived from
`context` and `output`, not the weights' theoretical maximum. Discovery metadata
does not truncate requests or establish that a particular client consumes it
for automatic history compaction.

```bash
python3 workspaces/inference/manage.py status
python3 workspaces/inference/manage.py unload
python3 workspaces/inference/manage.py cockpit
```

The [Cockpit adapter](cockpit_launch.py) converts Halogen's named `video` and
`render` groups to host device GIDs for Docker without changing upstream files.
Restart Cockpit through `manage.py` to apply it. For the first trial, set both
Context and KV Pool to 32768 and Slots to 1; lowering Context or Slots alone
does not shrink a previously saved pool.

The Cockpit launcher selects Docker, isolates its XDG configuration and holds
the same cooperative GPU lease as managed runtimes. Unload managed models first;
close Cockpit's servers and exit the TUI before serving again. Raw Docker,
training and Cockpit launched outside this wrapper bypass the lease; it is not
GPU isolation or a complete detector of other workloads. Requests during the
manual Cockpit window can fail rather than wait for the TUI to close.

Ctrl+C stops the foreground gateway. Runtime shutdown checks ownership labels
and stops by container ID, never a global stop/prune. The specific `runtime.py
stop` action does not require surviving model/config files. A future service
supervisor must honor at least 90 seconds of shutdown and preserve private state;
no boot-time service is installed before actual Halo validation.

## Runtime-specific limits

- llama.cpp profiles use one slot, Jinja, Flash Attention, full GPU offload and
  no mmap. They are baseline candidates, not validated EngramHalo fork recipes.
  For binaries accepting `--load-mode none` instead of `--no-mmap`, set
  `"load_mode": "none"` in the private profile. Omitting this field preserves
  the older contract. Check `--help` and argument parsing without loading weights.
- Halogen keeps the shipped `all` entrypoint, no download and a 16384 prefill
  arena by default. Optional `slots` accepts integers 1-8 (default 1);
  `kv_pool` ranges from `context` to 1048576 (default `context`). Model admission
  follows `slots`; global admission uses the maximum across enabled profiles,
  preserving exclusive runtime switching. Pool capacity includes all requests'
  input and output. Profile C selects context 131072, pool 524288, four slots
  and output 8192; memory fit and concurrency still require local validation. Optional `halogen_overlay`
  and `halogen_tokenizer` select paths relative to `model_dir`; the latter
  must contain `tokenizer.json`. `halogen_max_tok` explicitly selects a prefill
  arena up to 32768, not the response budget. Preserve and revalidate the
  artifacts and arena of a working Cockpit recipe when migrating it.
  Complete HGN or supported GGUF with tokenizer/sidecars is required.
  Q4_K_M and UD-Q4_K_XL are not substitutes.
  A smaller pool does not prove fit with the historical 61.73 GiB GTT.
- vLLM uses a complete local model export and a separate writable cache.
  `vllm_args` carries reviewed model-specific parsers/settings, not network,
  identity or `trust-remote-code` overrides. Hardware/model support is pending.
- Halogen/vLLM retain the image's default user; no unverified non-root claim
  is made. ROCm/engine IPC and memlock requirements weaken isolation. Docker
  rootful authority remains effectively root authority.

## Remote OpenCode API

Configure a private environment based on `.env.example`: verified image digest,
operator UID/GID, authorized bind address, certificate DNS name, TLS directory
and the value of `data/client.key`. Supply `server.crt` and `server.key`, readable
by the container user, and trust the issuing CA on the client. Never disable TLS
verification or substitute `admin.key` for the client key.

```text
docker compose --env-file <PRIVATE_ENV> -f workspaces/inference/compose.yaml config --quiet
docker compose --env-file <PRIVATE_ENV> -f workspaces/inference/compose.yaml up -d
docker compose --env-file <PRIVATE_ENV> -f workspaces/inference/compose.yaml down
```

Caddy listens on the chosen address at **18443**, with a supplied certificate
and no ACME. Only the client bearer key plus `/v1/models`,
`/v1/chat/completions`, `/v1/completions` or `/v1/responses` is allowed.
All other routes, including admin/UI/logs/upstream access, return 403.
Firewall/VPN policy is still required and is not changed by these files.
The underlying llama-swap keys are equivalent; this separation depends on
remote clients being unable to bypass the edge and reach port 18080.

Merge only the provider fragment into OpenCode. Set `HALO_BASE_URL` to the
approved HTTPS base ending in `/v1`, and `HALO_CLIENT_KEY` privately. Remove
models that remain disabled and match actual context/output limits. This
provider uses Chat Completions; Responses requires a separately tested
`@ai-sdk/openai` configuration. No private OpenCode config was read or changed.

## Tests and deployment boundaries

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
git diff --check
```

Offline tests cover profile validation, mounts, command construction, ownership
and fail-closed behavior. Optional real-binary tests validate generated config
and run a temporary loopback llama-swap against a synthetic HTTP backend,
checking auth, UI, model IDs, tool payload passthrough and Chat/Responses SSE.
This is not a model-quality, GPU cancellation or memory-fit test.
Compose/Caddy and later loopback certificate, TLS handshake and route-rejection
tests passed as recorded in the deployment report. LAN TLS and remote-client
disconnect propagation through a deployed TLS edge remain unvalidated.

The whole-site build already fails on an EngramHalo `.dockerignore` link outside
the publication allowlist; this work does not broaden that security boundary.

The [September 17 deployment record](../../docs/en/halogen-128k-deployment.md)
covers actual GPU work, 128K, network exceptions and service startup. Standard
`generate`, `start.sh` and `unload` retain public defaults and are not the
private LAN service launcher. Do not start a second gateway. Use the existing
user unit for that deployment; cold boot, soak and remote client compaction
are still explicitly pending.
