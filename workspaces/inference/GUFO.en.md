# Gufo: Qwen3.8-27B through the existing gateway

[Español](GUFO.md) | [Inference](README.en.md)

## Current configuration: 128K and at most two slots

The catalog retains `gufo-qwen38-27b`, now with **131072 tokens per session and
two slots**. Runtime validation rejects more than two slots; llama-swap admits
at most two concurrent Gufo requests. Global concurrency is 7 to preserve Laya's
contract (Halogen 4 + Gufo 2 + Laya 1), though GPU engines alternate.
Image, weights, DFlash2 and default output budget 2048 are unchanged.

In Halo Control open **Servicios IA → Catálogo de modelos · llama-swap**.
**Activar Gufo** loads using `/ready`; **Desactivar Gufo** unloads only Gufo,
keeping its catalog entry. Operations are blocked while requests are active,
with a stopped gateway or incompatible configuration. Loading switches the GPU
away from Halogen; Laya stays on CPU. Unloading does not deny future requests:
they can reload the model. This is not permanent alias disablement.

CLI alternative from the repository root:

```bash
python3 workspaces/inference/gufo.py load
python3 workspaces/inference/gufo.py unload
```

The native v255 UI Load button requests `/upstream/MODEL/`; Gufo returns 404 for
`/` even after loading. Halo Control catalog buttons therefore use `/ready`
instead of misreporting that 404 as an inference failure. These are supervised
jobs; consult Activity and shared logs. No parameter editor or seventh engine
card was added.

Live expanded-profile validation, 2026-09-25 UTC:

- Loader: `sessions=2 context_tokens=131072`, 3.450 s; `/ready` load 4.385 s
  from a gateway without a resident GPU engine, not from loaded Halogen.
- Two concurrent 128-token requests completed in 5.616 and 5.417 s; the server
  reported `batched-w2`, physical width 2 and up to two resident requests.
- Per-request decode: 25.82 and 25.90 tokens/s, not end-to-end throughput or a
  quality comparison. Both responses reached the bounded test output limit.
- Loader HIP counter: 23160 MiB; do not add it to RSS or Docker memory on UMA.
- Explicit unload: 60.41 s, preserving alias and Laya container identity.
- Halogen was restored, Laya healthy, Gufo available on demand.

This verifies context allocation, startup and two concurrent short requests,
**not two full 128K prompts**, soak or stability at every input length.
The following trial remains historical 32K/one-slot evidence.

## Initial 32K / one-slot trial

Host observation dated **2026-09-25 UTC**, not a continuing health guarantee.
The official image and both SHA256-verified GGUFs served `gufo-qwen38-27b`
through the existing llama-swap v255 alongside Halogen and Laya.
No additional proxy or authentication policy change was introduced.

- Qwen3.8-27B UD-Q4_K_XL plus DFlash2 Q4_K_M, configured context 32768,
  one session, thinking disabled by default.
- Chat Completions returned HTTP 200 and the correct `42` for `17 + 25`.
- Streaming returned correct content and the SSE `[DONE]` terminator.
- Tools produced the declared `add` call with integer arguments 17 and 25.
  No generated code or actual tool was executed.
- `/ready` confirmed model readiness; `/health` only means process liveness.
- First request including container/model startup: 3.63 s. Loader: 2.876 s.
  This was not a cold host boot or a cleared-filesystem-cache benchmark.
- Three identical programming explanations, 128 output tokens each:
  4.329 / 4.120 / 4.136 s end-to-end; server decode rates
  31.06 / 31.14 / 31.02 tokens/s. The last two reused 29 cached tokens.
  Server TTFT: 196.5 / 3.4 / 3.4 ms, not client-observed latency.
  Responses were truncated by the test budget (`length`).
- `docker stats`: 16.79 GiB; process RSS around 18 GiB and loader HIP counter
  6268 MiB. These are different UMA counters, not additive or a measurement
  of total/peak system memory consumption.
- Laya retained its container identity and CPU health throughout Gufo serving
  and the return to Halogen. Initial gateway restart did unload both services.
- Restoring Halogen via a request took 76.27 s, including Gufo unloading and
  Halogen loading. Switching is not promised to be instantaneous.
- Verified final state: Halogen loaded, Laya healthy; Gufo unloaded but still
  available in the catalog for the next request.

In the initial trial, vision, a full 32K prompt, Gufo concurrency, soak, reboot, AR/DFlash2 parity and
systematic coding quality were not tested. This is a different model and
quantization; these results **do not establish superiority over Halogen**.

## Pinned identities

Official `gufo-org/toolboxes` image:

```text
ghcr.io/gufo-org/toolboxes/gufo-runtime@sha256:989ab52a190244f08511a3ad0fd46546f2144220c37e6c808ad8008a934ebab5
```

The executable reports `gufo version 9cad139`, matching the reviewed source
commit prefix `9cad13974cf6da0cd3674b4e0a88b14b7e4a2908`.
This does not claim a reproducible image rebuild.

| Artifact | Repository and revision | Bytes |
| --- | --- | --- |
| `Qwen3.8-27B-UD-Q4_K_XL.gguf` | `unsloth/Qwen3.8-27B-GGUF` @ `4ca720788d1e01f1bff70c033e0d0028fd02e502` | 17559178144 |
| `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` | `z-lab/Qwen3.8-27B-DFlash2-GGUF` @ `2d9571f8ce46e151f61c6499c99dee6079e1d610` | 1143006816 |

Their respective SHA256 values:

```text
3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e
1a25c56858e1ebe93f2718ac1d49d1151f9323325c1bbfd6209370f4db131ebd
```

## Preparation and operation

From the repository root, without stopping engines during downloads:

```bash
docker pull ghcr.io/gufo-org/toolboxes/gufo-runtime@sha256:989ab52a190244f08511a3ad0fd46546f2144220c37e6c808ad8008a934ebab5
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/gufo.py download
python3 workspaces/inference/gufo.py prepare
```

Download requires `huggingface_hub` in the isolated environment already installed
by `manage.py install`; it does not install global packages. Only target/drafter
are downloaded, with HF resume and verification against hashes pinned in code,
not a blindly trusted local manifest. Everything stays in private ignored
`data/gufo/`. The initial trial used HF from the local Laya CPU image.

`gufo.py install` adapts the existing Halo Control deployment. It requires the
reviewed launcher and a **stopped** gateway, takes operation/settings leases,
validates the candidate with llama-swap, then atomically replaces the actual
configuration with a private backup. It does not start or stop services itself.
Reserve client traffic, check jobs, drain and stop the gateway in the panel
before running it; then start the same gateway. An inflight snapshot does not
prevent a new request from a direct client.

```bash
python3 workspaces/inference/gufo.py install
```

To upgrade an existing 32K deployment, run `prepare` before stopping services,
then run the following with the gateway drained and stopped:

```bash
python3 workspaces/inference/gufo.py upgrade
```

`upgrade` verifies the previous entry's commands/profile before replacing only
Gufo. The old profile is retained; the new one is
`data/gufo/profiles-128k-2slots.json`. It validates the candidate and atomically
updates the gateway profile pointer with a private backup. Start the same gateway
afterward; no parallel proxy is created.

Do not run `manage.py generate` over the existing deployment: entries outside
that profile, such as Laya, would be lost. Other deployments can use the `gufo`
runtime kind with a validated private profile and reviewed routing. The installer
rejects conflicting aliases, backend ports or incompatible routing.

Gufo joins Halogen's exclusive swapping GPU group; Laya stays in its persistent
CPU group. Gufo backend: `127.0.0.1:18102`, read-only models, nonroot user,
dropped capabilities, no host IPC or Docker socket, exact KFD/render devices,
unlimited memlock and cooperative GPU lease inherited by the Docker client.
The process guard also detects `gufo`; this is not isolation against operators
launching unmanaged GPU workloads outside these controls.

Global concurrency is at least the sum of configured limits (7 in this profile),
preserving the current Laya contract. Gufo has two sessions. `output=2048` is a
server default/catalog hint, **not an immutable ceiling** against explicit client
`max_tokens`; use bounded requests. Context 131072 limits each session, including input and output.

Example against the existing running gateway. This request unloads resident
Halogen, so coordinate with other users:

```python
import sys
sys.path.insert(0, 'workspaces/halo-control')
import control
response = control.http('/v1/chat/completions', {
    'model': 'gufo-qwen38-27b',
    'messages': [{'role': 'user', 'content': 'Reply only with the result of 17 + 25.'}],
    'max_tokens': 32, 'temperature': 0,
    'chat_template_kwargs': {'enable_thinking': False},
}, timeout=1200)
print(response['choices'][0]['message']['content'])
```

Use the same client base URL and select `gufo-qwen38-27b`. Chat Completions is
the tested API. Responses supports only a synchronous text subset without
streaming/tools/images/state; this is not a drop-in replacement for every Halogen
Responses client. Halo Control's catalog provides load/unload controls, not a
parameter editor.

## Recovery and verification

A request to `flash-halogen` through the same gateway unloads Gufo and restores
Halogen. To remove the entry: drain and stop the gateway, take the settings lease,
validate and atomically restore the previous private backup, start the same
gateway and reload desired models. Preserve weights and historical backups.
Never stop foreign containers by name without validating ownership.

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -q
python3 -m unittest discover -s workspaces/halo-control/tests -q
git diff --check
```

68 inference and 102 panel tests passed. Catalog browser tests cover buttons,
disabled states and submitted actions without running engines. The synthetic v255 test exercises both
CPU/GPU load orders and Gufo→Halogen swapping without unloading Laya; it is not
a GPU test. Live evidence remains private in `data/gufo/`. The full site retains
its preexisting publication failure for `scripts/engramhalo/.dockerignore`;
the public allowlist was not broadened to suppress it.

Sources: [Gufo](https://github.com/gufo-org/gufo),
[Qwen27B guide](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3.8-27b/README.md),
[API](https://github.com/gufo-org/gufo/blob/main/docs/SERVER.md).
