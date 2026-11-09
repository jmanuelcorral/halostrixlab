import json
from pathlib import Path
import subprocess

import engine_details
import runtime


SELECTIONS = {
    'catalog-halogen': ('halogen',),
}


def artifact_bytes(profile, fields):
    root = Path(profile['model_dir']).resolve()
    paths = {(root / profile[field]).resolve() for field in fields if field in profile}
    if any(not path.is_relative_to(root) or not path.is_file() for path in paths):
        raise ValueError('Model artifacts unavailable')
    return sum(path.stat().st_size for path in paths)


def snapshot(control):
    result = {'available': False, 'models': [], 'reason': 'No se pudo verificar el catálogo activo', 'global_slots': None}
    try:
        gateway, _, _, halogen = engine_details.gateway_source(control)
        runtime.validate_profile(control.config()['model'], halogen)
        result['models'] = [
            {'id': 'halogen', 'alias': control.config()['model'], 'name': 'Qwen3.8-Flash-Next', 'engine': 'Halogen',
             'device': 'GPU', 'context': halogen['context'], 'slots': halogen.get('slots', 1), 'output': halogen['output'],
             'weights_bytes': artifact_bytes(halogen, ('halogen_checkpoint', 'halogen_overlay')), 'parameters_b': None,
             'quantization': 'HGN', 'note': 'Pool KV compartido.', 'kv_pool': halogen.get('kv_pool', halogen['context'])},
        ]
        for peer_id, peer in gateway.get('peers', {}).items():
            for model_id in peer.get('models', []):
                result['models'].append({'id': model_id, 'alias': peer_id + '/' + model_id, 'name': model_id,
                    'engine': 'Halogen NPU', 'device': 'NPU', 'context': None, 'slots': None, 'output': None,
                    'weights_bytes': None, 'parameters_b': None, 'quantization': None,
                    'note': 'Peer de llama-swap hacia el backend de Halogen; depende de que Halogen esté cargado.', 'kv_pool': None})
        result.update(available=True, reason='', global_slots=gateway.get('globalConcurrencyLimit'))
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.SubprocessError):
        pass
    return result


def preflight(control, selected, catalog):
    if not selected or len(set(selected)) != len(selected) or set(selected) - {'halogen'}:
        raise ValueError('Selección de modelos inválida')
    if not catalog['available']:
        raise ValueError('Catálogo no verificado; revisa perfiles y routing')
    if control.unit_state('gateway') != 'active':
        raise ValueError('Arranca primero el servicio llama-swap')
    if control.inflight():
        raise ValueError('Gateway ocupado; espera a que terminen las peticiones')
    control.unsloth.require_stopped()
    control.llamafactory.require_stopped()
    names = control.containers()
    allowed = {'halostrix-' + control.config()['model']}
    if names is None or set(names) - allowed:
        raise ValueError('Otro servicio ocupa la GPU o su estado es desconocido; deténlo explícitamente')
    if any(control.unit_state(kind) not in ('inactive', 'failed') for kind in ('comfyui', 'unsloth', 'llamafactory')):
        raise ValueError('Otro stack IA está activo o en transición')


def launch(control, action):
    if action not in SELECTIONS:
        raise ValueError('Combinación no permitida')
    selected = SELECTIONS[action]
    catalog = snapshot(control)
    preflight(control, selected, catalog)
    try:
        if 'halogen' in selected:
            response = control.http('/v1/chat/completions', {'model': control.config()['model'],
                'messages': [{'role': 'user', 'content': 'Reply OK.'}], 'max_tokens': 8}, timeout=1200)
            if not isinstance(response, dict) or not response.get('choices'):
                raise ValueError('Halogen no confirmó inferencia')
    except Exception as error:
        raise RuntimeError('Carga incompleta; puede quedar un modelo cargado. Revisa estado y logs antes de reintentar.') from error
