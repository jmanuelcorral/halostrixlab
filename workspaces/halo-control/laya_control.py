import json
import subprocess
import urllib.request

import engine_details
import laya_runtime


def configured(control):
    gateway, _, _, _ = engine_details.gateway_source(control)
    laya_runtime.deployment()
    if gateway != laya_runtime.integrate(gateway):
        raise ValueError('Laya requiere la configuración de convivencia revisada en llama-swap')


def backend_health():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f'http://127.0.0.1:{laya_runtime.BACKEND_PORT}/health', timeout=2) as response:
        value = json.load(response)
    return value.get('status') == 'ok' and value.get('device') == 'cpu'


def status(control):
    result = {'available': False, 'state': 'unknown', 'health': False, 'error': ''}
    try:
        configured(control)
        result['available'] = True
        container = laya_runtime.owned()
        result['state'] = container['State']['Status'] if container else 'stopped'
        if result['state'] == 'running':
            try:
                result['health'] = backend_health()
            except (OSError, ValueError):
                pass
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError):
        result['error'] = 'No se pudo verificar Laya; revisa su instalación y la configuración del gateway.'
    return result


def execute(control, action):
    configured(control)
    if control.unit_state('gateway') != 'active':
        raise RuntimeError('Arranca primero el gateway compartido. No se iniciará otro proxy ni se detendrán motores GPU.')
    if action == 'laya-start':
        response = control.http('/upstream/laya/health', timeout=180)
        if not isinstance(response, dict) or response.get('status') != 'ok' or response.get('device') != 'cpu':
            raise RuntimeError('Laya no confirmó disponibilidad en CPU')
    elif action == 'laya-stop':
        if control.inflight():
            raise RuntimeError('Gateway ocupado; espera a que terminen las peticiones antes de detener Laya')
        control.http('/api/models/unload/laya', {}, timeout=100)
        if laya_runtime.owned() is not None:
            raise RuntimeError('No se confirmó la parada de Laya; revisa los logs compartidos')
    else:
        raise ValueError('Acción Laya desconocida')
