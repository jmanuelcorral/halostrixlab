# Laya CPU alongside Halogen

[Español](LAYA.md) | [Inference](README.en.md)

## Architecture

Laya 0.3.9 multilingual runs in Docker behind the same llama-swap v255 as Halogen.
There is no parallel proxy. The CPU group is non-exclusive and persistent, so
loading either model does not evict the other. Global concurrency accommodates
GPU slots plus one CPU request. No decision-to-Halogen pipeline, automatic engine
selection or cross-service forwarding is implemented.
Halo Control includes a Laya card in Overview and AI Services with official
artwork, status, start/stop controls and shared logs. The existing gateway must
be active; these actions never create a proxy or stop GPU engines. Stops refuse
in-flight gateway requests. Status checks the backend only when its container
exists, without automatically loading a stopped model.

- Gateway: the existing Halogen origin on port 18080, with its existing access policy.
- Decisions: `POST /upstream/laya/v1/systemone`.
- Model health: `GET /upstream/laya/health`, loads the model if stopped.
- Gateway `/health` does not prove inference readiness.
- Backend: `127.0.0.1:18181`, local-only, without separate authentication.
- Shared user unit: `llama-swap.service`. The old `halo-laya.service` is retired;
  port 18081 is closed.
- Container: `halostrix-laya-cpu`, non-root, no GPU devices or Docker socket,
  dropped capabilities, read-only root, 4 CPU quota, 8 GiB memory with no extra
  swap allowance, 256 PID/thread limit. CPU quota does not reserve physical cores.
- On-demand loading, `ttl: 0` keeps the loaded model until explicitly unloaded.

No GPU lease or GPU container label is used. Stopping the shared gateway,
including panel switches to other GPU engines, also stops Laya. Unloading only
Halogen leaves Laya running. Startup follows the existing gateway service.

## Preparation

From repository root, with Docker, gh, Python supporting safe tar extraction and
the installed llama-swap v255 binary:

```bash
python3 workspaces/inference/prepare_laya.py
python3 workspaces/inference/install_laya.py --config /private/path/active-gateway.yaml
systemctl --user start llama-swap.service
```

Before installation, reserve clients, wait for requests and stop the existing
gateway. The installer requires a stopped gateway and settings lease, validates
the candidate, saves a private backup and atomically replaces the configuration.
Use the active launcher's config, not a historical profile. Halogen commands,
profiles and credentials are preserved. Shared request capture is disabled
with `captureBuffer: 0`.

Preparation downloads pinned official source, builds a CPU image and downloads
only multilingual. Repeated preparation preserves an existing deployment rather
than replacing an image in use. Updates require explicit review.

- Source revision: `d120d4ba220711b93c171973118753460310e16b` in
  `NandhaKishorM/laya`.
- Model revision: `b4a904d1a2a54c822b829e24291d4b8f280fe43e` in
  `convaiinnovations/laya-multilingual`.
- Python base image pinned by digest, PyTorch 2.8.0 CPU, Transformers 4.57.6.
  No TileLang or compilation. Main dependencies are pinned; transitive versions
  are recorded in private `data/laya/packages.txt`, not fully locked on rebuild.
  Runtime selects the immutable local image ID.
- Original weights are read-only. Configuration/tokenizer copies on tmpfs allow
  Laya's compatibility repair without changing the original files.
- Inference uses `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. These prevent
  model downloads, not all network egress; Docker bridge is not an air gap.

Private source, weights, cache, keys and evidence stay under ignored `data/laya/`.
Do not publish these files or print keys. Source and model license: Apache-2.0;
retain upstream notices.

## Local client

```python
import json
from pathlib import Path
from urllib.request import Request, urlopen

key = Path('workspaces/inference/data/client.key').read_text().strip()
payload = {
    'state': 'Necesito corregir un error en un programa Python.',
    'questions': {
        'category': {
            'type': 'choice',
            'instructions': 'Clasifica la tarea solicitada.',
            'criteria': {
                'programming': 'Escribir o corregir código informático',
                'writing': 'Redactar o resumir texto',
                'images': 'Crear o editar imágenes',
            },
        },
    },
}
request = Request(
    'http://127.0.0.1:18080/upstream/laya/v1/systemone',
    data=json.dumps(payload).encode(),
    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
)
with urlopen(request, timeout=180) as response:
    print(json.load(response))
```

The example uses public loopback/Bearer defaults. Adapt the origin and credentials
to the existing gateway. Its previously authorized private LAN HTTP/no-key
exception is preserved and now also covers Laya; the retired proxy key is unused.
Do not publish private origins or expose the backend. Use an approved tunnel or
existing gateway protection for remote access. This is a decision API, not
OpenAI chat. Only multilingual is served: omit `model` or use `multilingual`,
`laya`, or the full checkpoint ID. Other model selections are rejected.
Requests are limited to 64 KiB, 1-8 questions and 20 criteria per question.
One inference runs at a time; saturation may return 429/503. Request bodies are
not logged or captured by this gateway.

## Observed September 23, 2026

Real offline CPU inference returned HTTP 200. A synthetic Spanish request chose
`programming` with probability 0.9778. Cold startup took 4.3-5.4 seconds; observed
warm calls took 56 ms and 80 ms while Halogen generated concurrently. These are
individual samples, not percentiles or an SLA. Container memory was about
1.62 GiB. These samples describe the initial, temporary separate-proxy deployment.
The later migration to the original gateway checked for idle requests, restarted
the gateway and reloaded Halogen. Both models subsequently answered concurrently
through the shared gateway and appear in `/v1/models`. Tests with v255 verify
coexistence in both loading orders. Invalid schema/model returns 422 and oversized
body 413; authentication now follows the existing gateway policy.

This does not establish production accuracy, routing quality or calibration.
Do not automate using `action.act_probability`, which upstream acknowledges is
not yet useful. Evaluate thresholds and probabilities on your own data before
building the separate decision workflow.

## Tests and lifecycle

[Reproducible test guide](../../docs/en/laya-testing.md): model-free tests, live
`choice`/`score`/`noul`, probability validation, 422/413 rejection, latency samples,
optional coexistence and Halo Control start/stop. Its client resolves the active
origin and credentials without printing them. September 24 verification: 8 runtime
and 8 panel-adapter tests; full suites contain 57 inference and 101 panel Python
tests. Frontend passed 50 unit and 40 Playwright tests. Fixtures are not real inference.

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_laya.py -v
python3 workspaces/inference/laya_runtime.py status
systemctl --user status llama-swap.service
```

Unload only Laya with `POST /api/models/unload/laya` using the existing gateway's
authentication. Stopping `llama-swap.service` unloads both; weights/cache persist.
The retired proxy files and archived unit remain under `data/laya/` as evidence,
not active configuration.

Sources: [Laya](https://github.com/NandhaKishorM/laya),
[weights](https://huggingface.co/convaiinnovations/laya-multilingual).
