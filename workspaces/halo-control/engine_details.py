import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import time
import uuid

import llamafactory
import unsloth
import service_options
import studio_recreate

runtime = unsloth.runtime
ENGINES = {'gateway': 'llama-swap', 'halogen': 'Halogen', 'comfyui': 'ComfyUI', 'unsloth': 'Unsloth Studio', 'llamafactory': 'LLaMA-Factory'}
GATEWAY = runtime.DATA / 'gateway-coder-halogen-noauth.yaml'
LAUNCHER = runtime.DATA / 'start-coder-halogen.py'
SCHEMAS = {
    'gateway': [('healthCheckTimeout', 'Espera de arranque (s)', 30, 1800), ('unloadTimeout', 'Espera de descarga (s)', 10, 300), ('globalConcurrencyLimit', 'Peticiones simultáneas globales', 1, 8)],
    'halogen': [('context', 'Contexto por petición', 1024, 131072), ('output', 'Máximo de salida', 1, 32768), ('slots', 'Slots compartidos', 1, 8), ('kv_pool', 'Posiciones del pool KV', 1024, 524288), ('halogen_max_tok', 'Arena de prefill', 1, 32768)],
    'comfyui': [('reserve_vram', 'Reserva GPU (GiB)', 1, 24), ('cache_none', 'Sin caché de nodos', None, None), ('bf16_vae', 'VAE BF16', None, None), ('disable_smart_memory', 'Desactivar smart memory', None, None), ('hipblaslt', 'Preferir hipBLASLt', None, None), ('aotriton', 'AOTriton experimental', None, None)],
    'llamafactory': [('shm_gib', 'Memoria compartida (GiB)', 1, 32), ('hf_offline', 'Hugging Face sin red', None, None), ('tokenizers_parallelism', 'Paralelismo de tokenizadores', None, None)],
    'unsloth': studio_recreate.SCHEMA,
}


def check_engine(engine):
    if engine not in ENGINES:
        raise ValueError('Motor no permitido')


def mask(value, key=''):
    sensitive = re.search(r'(?i)key|secret|password|token|credential|authorization|environment|properties|cmd|arguments|entrypoint|routing', key)
    if sensitive:
        if isinstance(value, list):
            return [item.split('=', 1)[0] + '=[oculto]' if key == 'environment' and isinstance(item, str) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', item) else '[oculto]' for item in value]
        return '[oculto; mostrar valores privados]'
    if isinstance(value, dict):
        return {name: mask(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [mask(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r'(://)[^/@\s]+:[^/@\s]+@', r'\1[oculto]@', value)
    return value


def document(path):
    return json.loads(runtime.private_file(path).read_text())


def gateway_source(control):
    unit = control.run(['systemctl', '--user', 'show', control.UNITS['gateway'], '--property=ExecStart', '--value']).stdout
    launcher = runtime.private_file(LAUNCHER).read_text()
    if str(LAUNCHER) not in unit or GATEWAY.name not in launcher or "service_options.lease('gateway')" not in launcher:
        raise ValueError('El launcher del gateway no tiene el guard de configuración revisado')
    gateway = document(GATEWAY)
    model = gateway['models'][control.config()['model']]
    command = shlex.split(model['cmd'])
    if len(command) != 8 or command[:3] != ['/usr/bin/python3', str(runtime.ROOT / 'runtime.py'), 'start'] or command[3] != control.config()['model'] or command[4] != '--config' or command[6] != '--port':
        raise ValueError('El comando activo no coincide con el runtime revisado')
    path = Path(command[5])
    if path.parent != runtime.DATA or path.is_symlink():
        raise ValueError('El perfil activo debe ser un archivo privado del workspace')
    profile_document = document(path)
    profile = profile_document['profiles'][command[3]]
    if profile['kind'] != 'halogen':
        raise ValueError('El perfil activo no es Halogen')
    return gateway, path, profile_document, profile


def source(control, engine):
    if engine == 'unsloth':
        snapshot = studio_recreate.snapshot()
        return studio_recreate.values(snapshot), {'container_revision': studio_recreate.revision(snapshot), 'image': snapshot['Image'], 'environment': snapshot['Config']['Env'], 'deployment': {'user': snapshot['Config']['User'], 'ports': snapshot['HostConfig']['PortBindings'], 'mounts': snapshot['Mounts']}, 'note': 'Guardar recrea Studio detenido y conserva el contenedor anterior. No arranca ni valida salud automáticamente.'}, [str(studio_recreate.DATA)]
    if engine in ('gateway', 'halogen'):
        gateway, path, profiles, profile = gateway_source(control)
        values = gateway if engine == 'gateway' else {'halogen_max_tok': 16384, 'slots': 1, 'kv_pool': profile['context'], **profile}
        saved = {'gateway': gateway, 'profiles': profiles}
        return {name: values[name] for name, *_ in SCHEMAS[engine]}, saved, [str(GATEWAY), str(path)]
    if engine in service_options.DEFAULTS:
        values = service_options.read(engine)
        saved = {'options': values}
        if engine == 'llamafactory':
            saved['deployment'] = llamafactory.config()
        else:
            import comfyui
            saved['deployment'] = {'image': comfyui.pinned_image(), 'bind': control.config()['comfyui_bind'], 'port': comfyui.PORT}
        return values, saved, [str(service_options.DATA / (engine + '-options.json'))]
    raise ValueError('Motor sin adaptador de configuración')


def container_id(engine):
    if engine == 'unsloth':
        value = unsloth.inspect()
        return value['id'] if value else None
    if engine == 'llamafactory':
        value = llamafactory.metadata(llamafactory.NAME)
        return value['id'] if value else None
    if engine in ('halogen', 'comfyui'):
        return runtime.inspect_owned('halostrix-' + ('flash-halogen' if engine == 'halogen' else 'comfyui-manual'))
    return None


def observed(control, engine):
    if engine == 'gateway':
        output = control.run(['systemctl', '--user', 'show', control.UNITS['gateway'], '--property=Environment', '--property=ExecStart', '--property=MainPID']).stdout
        value = {'source': 'systemd: propiedades configuradas; entorno del proceso solo si coincide el ejecutable y propietario', 'properties': output}
        match = re.search(r'^MainPID=([1-9][0-9]*)$', output, re.MULTILINE)
        if match:
            process = Path('/proc') / match.group(1)
            try:
                if process.stat().st_uid == os.getuid() and (process / 'exe').resolve() == (runtime.DATA / 'bin/llama-swap').resolve():
                    value['environment'] = (process / 'environ').read_bytes().decode(errors='replace').strip('\x00').split('\x00')
            except (OSError, RuntimeError):
                value['environment'] = ['No disponible: proceso cambiado o acceso denegado']
        return value
    identifier = container_id(engine)
    if not identifier:
        return {'source': 'No hay contenedor actual. Las opciones guardadas se aplicarán en el próximo arranque.'}
    template = '{"image":{{json .Config.Image}},"state":{{json .State.Status}},"environment":{{json .Config.Env}},"entrypoint":{{json .Config.Entrypoint}},"arguments":{{json .Config.Cmd}},"ports":{{json .HostConfig.PortBindings}},"mounts":{{json .Mounts}}}'
    value = json.loads(control.run(['docker', 'inspect', '--format', template, identifier]).stdout)
    return {'source': 'Docker: configuración del contenedor existente (puede estar detenido)', **value}


def stopped(control, engine):
    if engine == 'unsloth':
        studio_recreate.ensure_no_pending()
        unsloth.require_stopped()
    unit = 'gateway' if engine == 'halogen' else engine
    if control.unit_state(unit) not in ('inactive', 'failed'):
        raise ValueError('Detén el servicio antes de editar; para Halogen también debes detener llama-swap')
    if engine in ('gateway', 'halogen'):
        identifier = container_id('halogen')
    else:
        identifier = container_id(engine)
    if identifier:
        state = control.run(['docker', 'inspect', '--format', '{{.State.Status}}', identifier]).stdout.strip()
        if state not in ('exited', 'created', 'dead'):
            raise ValueError('El contenedor sigue activo o su estado no es seguro')
    if engine == 'llamafactory':
        llamafactory.require_stopped()
    with control.database() as connection:
        active = connection.execute("SELECT id FROM jobs WHERE state IN ('queued','running') AND updated>?", (time.time() - 1800,)).fetchone()
    if active:
        raise ValueError('Hay una operación pendiente; espera a que termine')


def revision(saved):
    return hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest()


def detail(control, engine, reveal=False):
    check_engine(engine)
    values, saved, paths = source(control, engine)
    reason = ''
    try:
        stopped(control, engine)
    except (ValueError, RuntimeError, OSError) as error:
        reason = str(error)
    effective = observed(control, engine)
    return {'id': engine, 'title': ENGINES[engine], 'state': control.unit_state('gateway' if engine == 'halogen' else engine), 'editable': not reason, 'reason': reason, 'values': values, 'fields': [{'name': name, 'label': label, 'type': 'boolean' if minimum is None else 'integer', 'min': minimum, 'max': maximum} for name, label, minimum, maximum in SCHEMAS[engine]], 'revision': revision(saved), 'paths': paths, 'saved': saved if reveal else mask(saved), 'effective': effective if reveal else mask(effective), 'revealed': reveal}


def atomic_write(path, content):
    runtime.private_directory(path.parent)
    if path.exists() or path.is_symlink():
        runtime.private_file(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


def replace_with_backup(path, value):
    if path.exists():
        runtime.write_private(path.with_name(path.name + '.backup-' + uuid.uuid4().hex), runtime.private_file(path).read_text())
    atomic_write(path, json.dumps(value, indent=2) + '\n')


def validate(engine, values):
    if not isinstance(values, dict) or set(values) != {field[0] for field in SCHEMAS[engine]}:
        raise ValueError('Campos desconocidos o incompletos')
    for name, _, minimum, maximum in SCHEMAS[engine]:
        value = values[name]
        if minimum is None:
            if type(value) is not bool:
                raise ValueError('Se esperaba un booleano: ' + name)
        elif type(value) is not int or not minimum <= value <= maximum:
            raise ValueError('Valor fuera del rango permitido: ' + name)
    if engine == 'halogen' and (values['output'] >= values['context'] or values['kv_pool'] < values['context'] or values['halogen_max_tok'] > values['context']):
        raise ValueError('Salida, prefill y pool KV incompatibles con el contexto')


def save_gateway(control, engine, values):
    gateway, path, profiles, profile = gateway_source(control)
    candidate = copy.deepcopy(gateway)
    model = candidate['models'][control.config()['model']]
    new_profile = None
    if engine == 'gateway':
        candidate.update(values)
        if values['globalConcurrencyLimit'] < profile.get('slots', 1):
            raise ValueError('El límite global no puede ser menor que los slots de Halogen')
    else:
        profile.update(values)
        runtime.validate_profile(control.config()['model'], profile)
        new_profile = runtime.DATA / ('profiles-panel-' + uuid.uuid4().hex + '.json')
        runtime.write_private(new_profile, json.dumps(profiles, indent=2) + '\n')
        for field in ('cmd', 'cmdStop'):
            command = shlex.split(model[field])
            index = command.index('--config') + 1
            command[index] = str(new_profile)
            model[field] = shlex.join(command)
        model.setdefault('metadata', {}).update(context_length=values['context'], max_output_tokens=values['output'])
        model.setdefault('capabilities', {})['context'] = values['context']
        model['concurrencyLimit'] = values['slots']
        candidate['globalConcurrencyLimit'] = max(candidate.get('globalConcurrencyLimit', 1), values['slots'])
    temporary = GATEWAY.with_name('.gateway-validate-' + uuid.uuid4().hex + '.yaml')
    try:
        runtime.write_private(temporary, json.dumps(candidate))
        result = control.run([str(runtime.DATA / 'bin/llama-swap'), '-config', str(temporary), '-validate'], check=False)
        if result.returncode:
            raise ValueError('llama-swap rechazó la configuración candidata; no se ha activado')
        replace_with_backup(GATEWAY, candidate)
    finally:
        temporary.unlink(missing_ok=True)


def save(control, engine, payload):
    check_engine(engine)
    if not isinstance(payload, dict) or set(payload) != {'revision', 'values'}:
        raise ValueError('Petición de edición inválida')
    validate(engine, payload['values'])
    guard = 'gateway' if engine == 'halogen' else engine
    with control.operation_lock(), service_options.lease(guard):
        stopped(control, engine)
        _, saved, _ = source(control, engine)
        if payload['revision'] != revision(saved):
            raise ValueError('La configuración ha cambiado; recarga la ficha antes de guardar')
        if engine == 'unsloth':
            studio_recreate.recreate(payload['values'], saved['container_revision'])
        elif engine in ('gateway', 'halogen'):
            save_gateway(control, engine, payload['values'])
        else:
            replace_with_backup(service_options.DATA / (engine + '-options.json'), payload['values'])
        with control.database() as connection:
            now = time.time()
            connection.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)', (uuid.uuid4().hex, 'settings-' + engine, 'success', now, now, 'Campos guardados: ' + ', '.join(sorted(payload['values'])), str(os.getuid())))
    return detail(control, engine)


def logs(control, engine):
    check_engine(engine)
    journal = control.logs('gateway' if engine == 'halogen' else engine)
    identifier = container_id(engine)
    legacy = False
    if engine == 'llamafactory' and not identifier:
        metadata = llamafactory.metadata(llamafactory.LEGACY)
        if metadata:
            identifier = metadata['id']
            legacy = True
    text = journal
    if identifier:
        output = control.run(['docker', 'logs', '--tail', '250', '--timestamps', identifier], check=False, timeout=10)
        text += ('\n--- Docker histórico: contenedor legacy (no el launcher del panel) ---\n' if legacy else '\n--- Docker (últimas 250 líneas) ---\n') + output.stdout + output.stderr
    text = re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|password|secret|token)[=: ]+)[^\s]+', r'\1[REDACTED]', text)
    return {'text': text[-80000:], 'source': 'Journal compartido con llama-swap' if engine == 'halogen' else 'Journal del servicio y contenedor actual cuando existe'}
