# Testing Laya with Halogen and Halo Control

[Español](../pruebas-laya.md) | [Consolidation](halo-control-operations.md) |
[Installation and architecture](../../workspaces/inference/LAYA.en.md)

Reviewed **September 24, 2026**. Synthetic tests, live requests and manual
lifecycle checks have different side effects. Run from repository root as the
workspace operator, not with sudo. This guide does not install packages, change
configuration, reboot the host or implement a Laya-to-Halogen pipeline.

## 1. Deployment under test

One `llama-swap.service` serves Halogen on GPU and multilingual Laya on CPU.
Use the existing Halogen origin with `POST /upstream/laya/v1/systemone`, not
chat/completions. Port 18081 and `halo-laya.service` belong to the retired proxy.
The backend on loopback 18181 must not be exposed as a client service.

The persistent, non-exclusive CPU group permits coexistence, not survival across
a gateway stop. Global concurrency covers GPU slots plus one CPU inference.
`ttl: 0` retains the loaded model until unloaded. `/v1/models` lists configured
models, not necessarily resident models.

## 2. Tests without real inference

From repository root:

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_laya.py -v
python3 -m unittest discover -s workspaces/halo-control/tests -p test_laya_control.py -v
```

Each suite has **8 tests** at this revision. Runtime tests cover limits, schemas,
Docker restrictions, container ownership and shared configuration. The optional
v255 binary test uses synthetic HTTP backends and ephemeral ports, checking both
loading orders without touching real engines. If the binary is absent, that test
is skipped: a skipped test does not establish coexistence. Controller tests mock
non-loading status checks, stopped/busy gateway rejection, isolated Laya start,
stop and confirmation.

From `workspaces/halo-control`, with private Node and Chromium already installed:

```bash
data/node node_modules/typescript/bin/tsc --noEmit
data/node node_modules/vitest/vitest.mjs run frontend
data/node node_modules/vite/bin/vite.js build
PATH="$PWD/data:$PATH" PLAYWRIGHT_BROWSERS_PATH="$PWD/data/browsers" data/node node_modules/@playwright/test/cli.js test tests/browser/engine-cards.spec.ts
```

The **7 card tests** include Laya actions, gateway prerequisite, shared logs,
six local images, themes, contrast and mobile layout. They simulate Cockpit;
they neither validate PAM login nor start containers. Screenshots stay in ignored
`data/`.

## 3. Preflight without starting Laya

```bash
python3 workspaces/inference/laya_runtime.py status
systemctl --user is-active llama-swap.service
docker ps --filter name=halostrix-laya-cpu --format '{{.Names}} {{.Status}}'
```

Expected: gateway `active`; Laya may be `running` or `stopped`. Panel polling does
not start it. If the gateway is stopped, review the current GPU engine instead
of automatically starting it. Do not run preparation/installation to test an
already active deployment.

Gateway `/health` checks only the proxy. `/upstream/laya/health` loads Laya if
stopped and checks its backend. The next test can create its container and allow
up to 8 GiB memory, without unloading Halogen.

## 4. Live classification, scoring and probability test

This recipe uses the panel client to resolve the active origin and authentication
without printing them. It neither assumes a loopback binding nor uses the retired
proxy key. Any existing private LAN/no-key exception also applies to Laya; Cockpit
login does not authenticate direct requests to that API.

```bash
python3 - <<'PY'
import copy
import math
import statistics
import sys
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path('workspaces/halo-control').resolve()))
import control

assert control.unit_state('gateway') == 'active', 'Gateway stopped; review before continuing'
models = control.http('/v1/models')
assert 'laya' in {item['id'] for item in models['data']}, 'Laya is not configured'
health = control.http('/upstream/laya/health', timeout=180)
assert health['status'] == 'ok' and health['device'] == 'cpu'
payload = {
    'model': 'multilingual',
    'state': 'Mi programa Python falla al leer un CSV. Necesito corregirlo hoy.',
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
        'urgency': {
            'type': 'score',
            'instructions': 'Estima la urgencia de la solicitud.',
            'criteria': ['Sin plazo', 'Necesario pronto', 'Bloqueo crítico inmediato'],
        },
        'mentions_python': {
            'type': 'noul',
            'instructions': '¿La solicitud menciona explícitamente Python?',
        },
    },
}
elapsed = []
for iteration in range(5):
    started = time.perf_counter()
    result = control.http('/upstream/laya/v1/systemone', payload, timeout=180)
    elapsed.append((time.perf_counter() - started) * 1000)
    assert result['model'] == 'convaiinnovations/laya-multilingual'
    answers = result['answers']
    category = answers['category']
    probabilities = category['probabilities']
    assert set(probabilities) == set(payload['questions']['category']['criteria'])
    assert category['choice'] in probabilities
    assert all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values())
    assert abs(sum(probabilities.values()) - 1) < 0.002
    assert 0 <= category['confidence'] <= 1
    assert 0 <= answers['urgency']['score'] <= 2
    assert 0 <= answers['mentions_python']['noul'] <= 1
    assert result['usage']['output_tokens'] == 0
print('PASS: CPU health, choice, score, noul and valid probabilities')
print('Observed classification:', category['choice'])
print('Latency ms, min/median/max:', *(round(value, 1) for value in (min(elapsed), statistics.median(elapsed), max(elapsed))))

for bad in ({}, dict(payload, model='halogen')):
    try:
        control.http('/upstream/laya/v1/systemone', bad, timeout=30)
        raise AssertionError('Expected HTTP 422')
    except urllib.error.HTTPError as error:
        assert error.code == 422, error.code
        error.close()
oversized = copy.deepcopy(payload)
oversized['state'] = 'x' * 65537
try:
    control.http('/upstream/laya/v1/systemone', oversized, timeout=30)
    raise AssertionError('Expected HTTP 413')
except urllib.error.HTTPError as error:
    assert error.code == 413, error.code
    error.close()
print('PASS: 422 and 413 rejection')
PY
```

`choice` returns a label and distribution. `score` is the expected value over
criterion indices 0..N-1 and may be fractional. `noul` returns a number in 0..1,
not generated text. The wrapper accepts these three types, not `bool`.
Do not require exact probabilities or treat one correct example as quality
validation. `confidence` is not necessarily the maximum probability.
Upstream acknowledges `action.act_probability` is not a useful validated signal;
do not use it to authorize actions. Five samples do not establish percentiles or
an SLA. The health call already loaded/warmed the model, so this is not cold-start timing.

## 5. Optional live coexistence check

Only when Halogen is **already loaded**, no sensitive jobs are running and a
short GPU inference request is acceptable. Do not switch away from ComfyUI,
Studio or LlamaBoard just to run this check.

```bash
python3 - <<'PY'
import concurrent.futures
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path('workspaces/halo-control').resolve()))
import control

def identity():
    return subprocess.check_output(['docker', 'inspect', 'halostrix-flash-halogen', '--format', '{{.Id}} {{.State.StartedAt}} {{.State.Running}}'], text=True).strip()

before = identity()
assert before.endswith(' true'), 'Halogen must already be running'
assert control.unit_state('gateway') == 'active'
payload = {'state': 'Corrige este programa Python.', 'questions': {'kind': {'type': 'choice', 'instructions': 'Clasifica la tarea.', 'criteria': {'code': 'Programar', 'text': 'Redactar'}}}}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    decision = pool.submit(control.http, '/upstream/laya/v1/systemone', payload, timeout=180)
    generation = pool.submit(control.http, '/v1/chat/completions', {'model': control.config()['model'], 'messages': [{'role': 'user', 'content': 'Responde solo: correcto'}], 'max_tokens': 16, 'temperature': 0}, timeout=180)
    assert decision.result()['answers']
    assert generation.result()['choices']
assert identity() == before, 'Halogen changed during this test; investigate'
print('PASS: both responses through one gateway; Halogen not restarted')
PY
```

These are independent requests, not a decision forwarded to Halogen. The check
establishes one coexistence observation, not all-slot saturation or a soak test.

## 6. Manual panel lifecycle test (changes service state)

1. Open Cockpit → Halo Control → Servicios IA; Ctrl+F5 if the Laya card is missing.
2. With gateway active, press **Arrancar Laya**. Wait for Activity success and a
   green state. This must not start/unload Halogen or create a separate proxy.
3. **Logs compartidos de Laya** opens shared gateway logs, not a Laya settings
   editor. Keep those logs private.
4. Reserve external clients and wait for requests. Privately record Halogen ID
   and `StartedAt` if running. Press **Detener Laya**.
5. Wait for success and **Parado**. Observe at least two polls (about 10 seconds):
   the panel must not reload it. Do not call `/upstream/laya/health` while checking.
6. Start Laya again if it was running before, and verify unchanged Halogen
   identity/start time. Do not stop the entire gateway to test only Laya.

A stopped gateway disables controls and shows a start-gateway-first message.
Stopping Laya rejects active requests anywhere on the gateway, including Halogen.
External clients can race with this check: reserve them first; this is not global
admission control. New requests may reload a stopped model.

## 7. September 24 verification results

Both Python examples in the Spanish companion guide were executed verbatim with
Laya and Halogen already running. CPU health, all three answer types, probability
distributions, 422/413 rejection and coexistence without restarting Halogen passed.
Five warm requests with **three questions** measured 133.9 / 136.7 / 179.8 ms
(minimum / median / maximum). Observed classification: `programming`.
Do not directly compare these with historical 56-80 ms single-question requests.
Manual stop/start and host reboot were not repeated to document these results.

## 8. Troubleshooting and acceptance

| Result | Meaning / next check |
| --- | --- |
| Connection refused | Check active origin/service, do not return to retired port 18081 |
| 401 | Existing gateway credentials, not `data/laya/client.key`; no-key deployments do not promise 401 |
| No `laya` in catalog | Integration absent or wrong config; do not automatically install/restart |
| 404 | Check `/upstream/laya/v1/systemone` |
| 413 / 422 in negative tests | Expected; for normal requests check 64 KiB, 1-8 questions and up to 20 criteria |
| 429 / 503 | Saturation; reduce concurrency, use bounded retries |
| 500 or startup timeout | Inspect shared journal/container, image, weights and compatibility |
| Health device not CPU | This deployment fails acceptance |
| Halogen unloaded when Laya loads | Review persistent, non-exclusive CPU group before continuing |

Read-only diagnostics:

```bash
journalctl --user -u llama-swap.service -n 80 --no-pager
docker stats --no-stream halostrix-laya-cpu
python3 workspaces/inference/laya_runtime.py status
```

**Functional acceptance:** correct routes, valid HTTP, CPU, typed answers, expected
rejections and no mutual eviction. **Quality still requires:** representative
labelled Spanish data, confusion matrix, false positives/negatives, calibration
and validated abstention thresholds. Default multilingual context is 1024 tokens
(roughly 256 allocated to options), not 64 KiB of semantic context; long inputs
may be truncated. Do not base security or irreversible actions on this smoke test.
