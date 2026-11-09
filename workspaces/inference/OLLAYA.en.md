# Winnow-12B on Ollaya CPU behind the existing llama-swap

[Español](OLLAYA.md) | [Workspace](README.en.md) |
[Earlier research](../../docs/en/winnow-ollaya-research.md)

## Deployment evidence, September 28, 2026

**Ollaya 0.7.5 CPU with Winnow-12B Q8_0**, not E4B, was deployed. The existing
llama-swap owns the container lifecycle; no second gateway or host Ollaya daemon
was installed. The trial ended with **Halogen, Laya and Winnow resident**.
This is dated evidence, not a permanent health guarantee.

The derived image adds Python's standard-library restricted HTTP adapter to the
pinned Ollaya image. No model weights or llama.cpp libraries were changed, no GPU
is used and no additional Python packages are installed. The Docker build sends
only `ollaya.Dockerfile` and `ollaya_server.py`, never private workspace data.

- Model: `EldanRing/Winnow-12B`, revision
  `b6ac22b0d51b69b18200acacb3fbdd98073fffe8`.
- Q8: 12,669,646,592 bytes; SHA-256
  `b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea`.
- Ollaya release 0.7.5: `32acb6d2ea13f616b1e11d9dfb8260b305106847`.
- Pinned model manifest SHA-256:
  `8d72fee0e5f92a625cdb85ae4f6abdc024c9e6f124a0ca67e64522c3f24c47ce`.
- Tested local image:
  `sha256:a0de95d83b48204809102cb6ee581a79f0d0dfccf98f20a1695b262ebfa25383`.
  Docker reports 299,258,921 bytes excluding weights. Rebuilt IDs can differ;
  private deployment metadata pins the immutable image and adapter hash.
- Weights, manifests, licenses, cache and evidence stay in ignored `data/winnow/`.
  Staging and the final GGUF blob are hard links, not two physical weight copies.

## Contract and limits

| Property | Value |
| --- | --- |
| Gateway alias | `winnow-12b-cpu` |
| Backend model | `winnow:12b` |
| Decisions | `POST /upstream/winnow-12b-cpu/v1/systemone` |
| Readiness | `GET /upstream/winnow-12b-cpu/ready` |
| Host backend | Adapter only, `127.0.0.1:18182` |
| Ollaya listener | Container-internal `127.0.0.1:11435`, not published |
| CPU / memory | 8-CPU quota, 32 GiB RAM limit, no additional swap |
| Context | 8192 total tokens, state budget 6144 |
| Requests | One active; concurrent excess can receive 429, no guaranteed queue |
| Body / questions | 64 KiB, 1-8 questions, up to 64 alternatives |
| Types | `noul`, `choice`, `score`; no chat or images |
| Output | Typed answers, `output_tokens=0` |
| Group | Separate persistent, non-exclusive CPU group |
| Global concurrency | 8 after preserving existing model limits |

The adapter accepts an omitted model, `winnow:12b`, or the gateway alias and
always forwards the fixed backend identity. Other models, administrative fields,
vision extensions and routes such as `/api/pull` are denied. Confidence follows
Ollaya semantics, not universal calibrated correctness.

Readiness requires a completed synthetic decision and exactly one CPU runner.
Backend failure or timeout fails closed and exits the container, requiring reload
rather than another device/model fallback. A disconnected client does not guarantee
immediate cancellation of an active CPU evaluation: the adapter holds its lock
until the bounded 300-second call finishes or fails. Drain before unloading.
Stopping the gateway also unloads its other resident models.

## Isolation

Non-root container, read-only weights/root, dropped capabilities,
`no-new-privileges`, no Docker socket, no GPU devices, no host IPC. Bounded tmpfs,
256-process limit, rotated Docker logs, no request/response logging. Ollaya's
native management API is neither published nor forwarded.

The owned Docker bridge disables outbound masquerading; an external HTTPS probe
timed out. **This is not a universal firewall policy:** host routing changes may
alter reachability. Docker `--internal` prevented port publication on this host,
so that unsuccessful variant was replaced. Pull prevention also relies on fixed
model identity, denied administrative routes and the read-only store.

Existing gateway access policy was preserved. Public Caddy still allows text
routes only, not this endpoint. Use the existing authorized origin or an approved
tunnel, never blanket external `/upstream/*` access.

## Operation

From the repository root:

```bash
python3 workspaces/inference/ollaya_runtime.py status
python3 workspaces/inference/ollaya_runtime.py load
python3 workspaces/inference/ollaya_runtime.py unload
```

Unloading retains weights and alias; later requests may load it again. Lifecycle
commands acquire the operation lock and refuse a busy gateway. CLI and the native
llama-swap UI provide control; **no Winnow card/editor was added to Halo Control**.
Its existing catalog remains available.

Example body for the authorized gateway's decision endpoint:

```json
{
  "model": "winnow:12b",
  "state": {"paid": true, "priority": "high"},
  "questions": {
    "paid": {"type": "noul", "instructions": "Has the customer paid?"},
    "route": {
      "type": "choice",
      "instructions": "Which priority is recorded?",
      "criteria": {"low": null, "high": null}
    },
    "urgency": {
      "type": "score",
      "instructions": "Rate the recorded priority's urgency.",
      "criteria": ["low", "medium", "high"]
    }
  }
}
```

### Reproducible preparation, not an instruction to repeat maintenance

```bash
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/ollaya_runtime.py download
python3 workspaces/inference/ollaya_runtime.py build
python3 workspaces/inference/ollaya_runtime.py configure
python3 workspaces/inference/ollaya_runtime.py verify
```

Download uses the existing huggingface_hub environment. Full hashes of every blob
and manifest are checked; configure refuses a differing saved image. Startup
checks identity and sizes, not 12.67 GB of checksums for each request. Do not edit
weights or manifests beneath a running service.

To integrate during authorized maintenance:

```bash
python3 workspaces/inference/ollaya_runtime.py install --restart
```

The installer verifies the active launcher/config, validates its candidate,
refuses inflight requests, stops the gateway, acquires the settings lease, backs
up and atomically replaces config. It restarts and restores previous residents.
This is **temporary downtime**, not hot reload or an admission reservation against
new direct clients: coordinate a client pause. Without `--restart` the gateway
must be stopped. Identical already-installed configuration does not restart it.
The actual cutover restored Halogen and Laya before loading Winnow.

On failure inspect private evidence and live state before retrying. Removal or
rollback requires drained/stopped maintenance, restoring the validated backup
under the settings lease and starting the previous gateway. Do not delete weights,
staging or historical configuration as part of rollback.

## Validation and limits

- 82 inference Python tests, including 8 dedicated adapter/runtime cases, and
  108 Halo Control Python tests. Fixtures do not prove GPU inference or Cockpit login.
- Actual `/api/ps`: Winnow-12B Q8_0, context 8192, `device=cpu`, `size_vram=0`.
- Three Spanish questions correctly identified paid=true, high priority and
  score near 2. First direct sample: 7.602 s. Three warm gateway runs:
  **5.283 / 5.262 / 5.271 s**. Small samples, not p95 or a quality benchmark.
- One question concurrent with Laya: Winnow **1.683 s**, Laya **0.061 s**.
  Same synthetic task, not representative comparative quality evidence.
- Admin routes 404, foreign model 400, oversized body 413; simultaneous requests
  returned 200 and 429. Recovery after client disconnect passed.
- Selective unload/reload preserved Halogen and Laya without another gateway.
- Short-run observed cgroup peak around 2.85 GiB is **not total model memory**:
  shared mmap/page-cache pages can be charged outside that cgroup. Do not size
  a fresh installation from that number.
- Still pending: held-out Spanish quality, context boundaries, representative
  p50/p95, soak, reboot and AMD GPU. No quality superiority over Laya claimed.

Private evidence: `direct-smoke.json`, `gateway-smoke.json`, `lifecycle-smoke.json`.

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_ollaya.py -v
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -q
python3 -m unittest discover -s workspaces/halo-control/tests -q
```
