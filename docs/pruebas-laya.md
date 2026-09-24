# Cómo probar Laya con Halogen y Halo Control

[English](en/laya-testing.md) | [Consolidación](halo-control-operacion.md) |
[Instalación y arquitectura](../workspaces/inference/LAYA.md)

Guía revisada el **24 de septiembre de 2026**. Distingue tests sintéticos,
peticiones reales y comprobaciones manuales que cambian el estado del servicio.
No instala paquetes, cambia configuración, reinicia el host ni implementa el
flujo Laya → Halogen. Ejecutar desde la raíz del repositorio como el operador
que instaló el workspace; no con sudo.

## 1. Qué está desplegado

Un único `llama-swap.service` sirve Halogen GPU y Laya multilingual CPU.
Laya se consulta en el mismo origen de Halogen mediante
`POST /upstream/laya/v1/systemone`; no mediante chat/completions.
El puerto 18081 y `halo-laya.service` pertenecen al proxy retirado, no se usan.
El backend 18181 es loopback, no un endpoint que deba exponerse a clientes.

El grupo CPU no exclusivo y persistente permite convivir con Halogen; no significa
supervivencia a una parada del gateway. El límite global configurado cubre los
slots GPU más una inferencia CPU. `ttl: 0` conserva Laya cargado hasta descargarlo.
`/v1/models` describe configuración, no modelos necesariamente residentes.

## 2. Tests sin inferencia real

Desde la raíz:

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_laya.py -v
python3 -m unittest discover -s workspaces/halo-control/tests -p test_laya_control.py -v
```

Cada suite tiene **8 tests** en esta revisión. La primera cubre límites, esquema,
comandos Docker, propiedad de contenedores y configuración compartida. Su prueba
opcional usa el binario v255 instalado con backends HTTP sintéticos y puertos
efímeros: comprueba ambos órdenes de carga sin tocar los motores reales. Si falta
el binario, se omite esa prueba; un resultado con skip no demuestra esa convivencia.
La segunda usa mocks para estado sin autocarga, rechazo de gateway parado/ocupado,
arranque exclusivo de Laya, parada y verificación del resultado.

Desde `workspaces/halo-control`, con Node privado y Chromium ya instalados:

```bash
data/node node_modules/typescript/bin/tsc --noEmit
data/node node_modules/vitest/vitest.mjs run frontend
data/node node_modules/vite/bin/vite.js build
PATH="$PWD/data:$PATH" PLAYWRIGHT_BROWSERS_PATH="$PWD/data/browsers" data/node node_modules/@playwright/test/cli.js test tests/browser/engine-cards.spec.ts
```

Los **7 tests de tarjetas** incluyen acciones Laya, gateway obligatorio, logs,
seis imágenes locales, temas, contraste y móvil. Simulan Cockpit; no prueban login
PAM ni arrancan contenedores. Las capturas permanecen en `data/` ignorado.

## 3. Estado previo sin arrancar Laya

```bash
python3 workspaces/inference/laya_runtime.py status
systemctl --user is-active llama-swap.service
docker ps --filter name=halostrix-laya-cpu --format '{{.Names}} {{.Status}}'
```

Esperado: gateway `active`; Laya puede estar `running` o `stopped`. El sondeo de
Halo Control no lo arranca. Si el gateway está parado, estos tests no deben
arrancarlo automáticamente: revisar qué motor GPU está usando el equipo.
No usar `prepare_laya.py` ni `install_laya.py` para comprobar una instalación ya activa.

**Distinción importante:** `/health` comprueba el gateway; `/upstream/laya/health`
carga Laya si está parado y comprueba su backend. La siguiente prueba sí puede
crear el contenedor y reservar hasta 8 GiB, sin descargar Halogen.

## 4. Prueba real: clasificación, puntuación y probabilidad

Esta receta usa el cliente del panel para resolver el origen y la autenticación
activos sin imprimirlos. No presupone loopback ni utiliza la clave del proxy
retirado. La excepción privada LAN sin clave de Halogen, si está configurada,
también afecta a Laya; el login de Cockpit no protege directamente esa API.

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

assert control.unit_state('gateway') == 'active', 'Gateway parado; revisar antes de continuar'
models = control.http('/v1/models')
assert 'laya' in {item['id'] for item in models['data']}, 'Laya no está configurado'
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
print('PASS: health CPU, choice, score, noul y probabilidades válidas')
print('Clasificación observada:', category['choice'])
print('Latencia ms, min/mediana/max:', *(round(value, 1) for value in (min(elapsed), statistics.median(elapsed), max(elapsed))))

for bad in ({}, dict(payload, model='halogen')):
    try:
        control.http('/upstream/laya/v1/systemone', bad, timeout=30)
        raise AssertionError('Se esperaba HTTP 422')
    except urllib.error.HTTPError as error:
        assert error.code == 422, error.code
        error.close()
oversized = copy.deepcopy(payload)
oversized['state'] = 'x' * 65537
try:
    control.http('/upstream/laya/v1/systemone', oversized, timeout=30)
    raise AssertionError('Se esperaba HTTP 413')
except urllib.error.HTTPError as error:
    assert error.code == 413, error.code
    error.close()
print('PASS: rechazos 422 y 413')
PY
```

`choice` devuelve una etiqueta y distribución; `score` es el valor esperado sobre
los índices 0..N-1 de los criterios, puede ser decimal; `noul` devuelve un valor
0..1, no texto generado. El wrapper acepta `choice`, `score`, `noul`, no `bool`.
No exigir una probabilidad exacta ni tratar un acierto de este ejemplo como
validación de calidad. `confidence` no es necesariamente la probabilidad máxima.
`action.act_probability` no tiene señal útil validada según upstream: no usarlo
como autorización de acciones. Estas cinco muestras no establecen percentiles ni SLA.
La llamada previa a health ya calentó/cargó el modelo; no mide el arranque frío.

## 5. Convivencia real con Halogen (opcional)

Solo con Halogen **ya cargado**, sin trabajos sensibles y con permiso para enviar
una petición breve. Una solicitud LLM sigue siendo trabajo GPU real. No realizar
un cambio desde ComfyUI, Studio o LlamaBoard para ejecutar esta prueba.

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
assert before.endswith(' true'), 'Halogen debe estar ya activo'
assert control.unit_state('gateway') == 'active'
payload = {'state': 'Corrige este programa Python.', 'questions': {'kind': {'type': 'choice', 'instructions': 'Clasifica la tarea.', 'criteria': {'code': 'Programar', 'text': 'Redactar'}}}}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    decision = pool.submit(control.http, '/upstream/laya/v1/systemone', payload, timeout=180)
    generation = pool.submit(control.http, '/v1/chat/completions', {'model': control.config()['model'], 'messages': [{'role': 'user', 'content': 'Responde solo: correcto'}], 'max_tokens': 16, 'temperature': 0}, timeout=180)
    assert decision.result()['answers']
    assert generation.result()['choices']
assert identity() == before, 'Halogen cambió durante la prueba; investigar'
print('PASS: ambas respuestas por el mismo gateway; Halogen no reiniciado')
PY
```

Las peticiones son independientes: no se pasa la decisión a Halogen ni se
implementa el pipeline del otro proyecto. Valida una coexistencia puntual,
no saturación simultánea de todos los slots ni estabilidad prolongada.

## 6. Arranque/parada desde el panel (manual y con efectos)

1. Abrir Cockpit → Halo Control → Servicios IA; recargar con Ctrl+F5 si falta Laya.
2. Con el gateway activo, pulsar **Arrancar Laya**. Esperar éxito en Actividad y
   estado verde. No debe arrancar/descargar Halogen ni crear otro proxy.
3. Consultar **Logs compartidos de Laya**: abre los logs del gateway, no un editor
   propio de parámetros de Laya. No publicar logs privados.
4. Reservar clientes externos y esperar peticiones. Registrar privadamente ID y
   `StartedAt` de Halogen si estaba activo. Pulsar **Detener Laya**.
5. Esperar éxito y **Parado**. Permanecer al menos dos sondeos (unos 10 s): el panel
   no debe recargarlo. No llamar a `/upstream/laya/health` durante esa observación.
6. Volver a arrancar Laya si estaba activo al empezar; verificar que Halogen
   conserva ID/fecha de arranque. No detener el gateway para probar solo Laya.

Con gateway parado, controles deshabilitados y aviso de arrancarlo primero.
La parada rechaza peticiones activas de **todo** el gateway, también Halogen.
Puede haber una carrera con clientes externos: reservarlos antes, no es un bloqueo
global. Una nueva petición puede volver a cargar un modelo descargado.

## 7. Resultado de la verificación del 24 de septiembre

Se ejecutaron literalmente los dos ejemplos Python de esta guía con Laya y
Halogen ya activos. Pasaron salud CPU, los tres tipos de respuesta, distribución
de probabilidades, rechazos 422/413 y coexistencia sin reiniciar Halogen.
Las cinco peticiones calientes de **tres preguntas** registraron 133,9 / 136,7 /
179,8 ms (mínimo / mediana / máximo). Clasificación observada: `programming`.
No comparar directamente con los 56-80 ms históricos de una sola pregunta.
No se repitió la parada manual ni un reinicio del host para documentar resultados.

## 8. Diagnóstico y criterios de aceptación

| Resultado | Interpretación / siguiente comprobación |
| --- | --- |
| Conexión rechazada | Revisar origen activo y servicio; no volver al proxy 18081 |
| 401 | Credenciales del gateway existente, no `data/laya/client.key`; en una instalación sin clave no se espera 401 |
| Catálogo sin `laya` | Integración pendiente o configuración distinta; no instalar/reiniciar automáticamente |
| 404 | Ruta incorrecta; usar `/upstream/laya/v1/systemone` |
| 413 / 422 en tests negativos | Esperado; en llamadas normales revisar 64 KiB, 1-8 preguntas y hasta 20 criterios |
| 429 / 503 | Saturación, reducir concurrencia y reintentar de forma acotada |
| 500 o timeout de carga | Consultar journal compartido y contenedor; comprobar imagen, pesos y compatibilidad |
| API responde pero `device` no es CPU | Fallo de aceptación de este despliegue |
| Halogen se descarga al cargar Laya | Revisar grupo CPU persistente/no exclusivo antes de continuar |

Comandos de consulta, sin descargar modelos:

```bash
journalctl --user -u llama-swap.service -n 80 --no-pager
docker stats --no-stream halostrix-laya-cpu
python3 workspaces/inference/laya_runtime.py status
```

**Aceptación funcional:** rutas correctas, HTTP válido, CPU, resultados tipados,
rechazos esperados y sin expulsión mutua. **Calidad pendiente:** corpus etiquetado
representativo en español, matriz de confusión, falsos positivos/negativos,
calibración y abstención con umbral validado. El contexto multilingual por defecto
es 1024 tokens (aprox. 256 reservados a opciones), no 64 KiB de contexto semántico;
textos largos pueden truncarse. No decidir seguridad o acciones irreversibles
basándose únicamente en este smoke test.
