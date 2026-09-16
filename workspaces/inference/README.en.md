# Cockpit, llama-swap and independent Docker runtimes

[Spanish operational guide](README.md) |
[Architecture research](../../docs/en/docker-toolboxes-halogen.md)

**2026-09-16: repository implementation, not a completed Halo migration.**
The isolated tools were installed on the local development workstation.
The inspected local CPU is not Ryzen AI Max; the runtime launcher refuses
GPU model starts there. Lemonade was not stopped or changed. No inference
images or model weights were downloaded. A small Caddy validation image was
pulled and used without networking; no persistent service was started.

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

```bash
python3 workspaces/inference/manage.py status
python3 workspaces/inference/manage.py unload
python3 workspaces/inference/manage.py cockpit
```

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
- Halogen keeps the shipped `all` entrypoint, one slot, explicit context/pool,
  no download and a 16384 prefill arena. Complete HGN or supported GGUF with
  tokenizer/sidecars is required. Q4_K_M and UD-Q4_K_XL are not substitutes.
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

## Tests and pending deployment

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
Compose parsing and Caddy configuration adaptation were validated; actual
certificates, TLS handshakes, edge route enforcement and disconnect propagation
on the target network remain pending.

The whole-site build already fails on an EngramHalo `.dockerignore` link outside
the publication allowlist; this work does not broaden that security boundary.

**External blocker:** an authorized execution session on the real Halo and
verified model paths/image digests are not available here. DNS, TLS certificate
and the authorized bind address must also be configured before remote access.
Run this workspace on the Halo to complete preflight, first Coder inference,
TLS validation and an explicit Lemonade cutover. No live migration is claimed.
