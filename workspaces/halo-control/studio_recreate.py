import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import uuid

import unsloth

DATA = Path(__file__).resolve().parent / 'data/studio-recreation'
ENV_FIELDS = {'hf_hub_offline': 'HF_HUB_OFFLINE', 'transformers_offline': 'TRANSFORMERS_OFFLINE', 'tokenizers_parallelism': 'TOKENIZERS_PARALLELISM'}
SCHEMA = [('shm_gib', 'Memoria compartida (GiB)', 1, 32), ('hf_hub_offline', 'Hugging Face sin red', None, None), ('transformers_offline', 'Transformers sin red', None, None), ('tokenizers_parallelism', 'Paralelismo de tokenizadores', None, None)]


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


def request(method, path, payload=None):
    connection = DockerConnection('localhost', timeout=60)
    try:
        body = None if payload is None else json.dumps(payload).encode()
        connection.request(method, path, body=body, headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(8_000_001)
        if response.status >= 300 or len(raw) > 8_000_000:
            raise ValueError('Docker rechazó la operación de Studio (HTTP ' + str(response.status) + '); detalles privados no publicados')
        return json.loads(raw) if raw else None
    except (OSError, http.client.HTTPException) as error:
        raise ValueError('No se pudo completar la operación Docker de Studio; revisa su estado antes de reintentar') from error
    finally:
        connection.close()


def snapshot():
    metadata = unsloth.inspect()
    if not metadata:
        raise ValueError('Falta el contenedor original de Studio')
    unsloth.endpoint(metadata)
    value = request('GET', '/containers/' + metadata['id'] + '/json')
    if value['Id'] != metadata['id'] or value['Image'] != metadata['image']:
        raise ValueError('Studio cambió durante la consulta')
    return value


def values(snapshot):
    environment = dict(item.split('=', 1) for item in snapshot['Config']['Env'])
    result = {'shm_gib': snapshot['HostConfig']['ShmSize'] // 2**30}
    if snapshot['HostConfig']['ShmSize'] % 2**30:
        raise ValueError('La memoria compartida actual no es un número entero de GiB')
    for name, variable in ENV_FIELDS.items():
        current = environment.get(variable, 'false').lower()
        if current not in ('0', '1', 'false', 'true'):
            raise ValueError('Variable existente fuera del formato permitido: ' + variable)
        result[name] = current in ('1', 'true')
    return result


def revision(snapshot):
    value = {key: snapshot[key] for key in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')}
    value['networks'] = network_config(snapshot)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def network_config(snapshot):
    return {name: {key: copy.deepcopy(endpoint.get(key)) for key in ('IPAMConfig', 'Links', 'Aliases', 'DriverOpts', 'GwPriority') if endpoint.get(key) is not None} for name, endpoint in snapshot['NetworkSettings']['Networks'].items()}


def validate(snapshot, options):
    if snapshot['State']['Status'] not in ('exited', 'created'):
        raise ValueError('Studio debe estar detenido antes de recrearlo')
    if set(options) != {'shm_gib', *ENV_FIELDS} or type(options['shm_gib']) is not int or not 1 <= options['shm_gib'] <= 32 or any(type(options[name]) is not bool for name in ENV_FIELDS):
        raise ValueError('Opciones de Studio inválidas')
    host = snapshot['HostConfig']
    if host.get('AutoRemove') or host.get('RestartPolicy', {}).get('Name') not in ('no', '') or host.get('NetworkMode', '').startswith(('container:', 'host')):
        raise ValueError('Recreación no compatible con borrado automático, restart o red compartida')
    mounts = snapshot['Mounts']
    expected = {'/workspace/hf-cache', '/workspace/projects', '/workspace/tmp', '/home/unsloth/.unsloth/studio'}
    if {mount['Destination'] for mount in mounts} != expected or any(mount['Type'] != 'bind' for mount in mounts):
        raise ValueError('Montajes distintos del despliegue revisado; no se recrea')
    for mount in mounts:
        path = Path(mount['Source'])
        if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
            raise ValueError('Los datos deben seguir disponibles y pertenecer al operador')
    changes = request('GET', '/containers/' + snapshot['Id'] + '/changes') or []
    for change in changes:
        path = change['Path']
        if path not in ('/usr', '/usr/sbin', '/usr/sbin/docker-init', '/tmp') and not re.fullmatch(r'/tmp/rocmsmi_boot_(compute|memory)_partition_[A-Za-z0-9_.-]+', path):
            raise ValueError('Hay cambios no revisados en la capa escribible; se conserva Studio sin recrear')


def candidate(snapshot, options):
    config = copy.deepcopy(snapshot['Config'])
    config['Image'] = snapshot['Image']
    host = copy.deepcopy(snapshot['HostConfig'])
    host['ShmSize'] = options['shm_gib'] * 2**30
    before = values(snapshot)
    for name, variable in ENV_FIELDS.items():
        if options[name] != before[name]:
            config['Env'] = [item for item in config['Env'] if item.split('=', 1)[0] != variable]
            config['Env'].append(variable + '=' + ('true' if options[name] else 'false'))
    return {**config, 'HostConfig': host, 'NetworkingConfig': {'EndpointsConfig': network_config(snapshot)}}


def verify(original, created, payload):
    if created['Image'] != original['Image'] or created['State']['Status'] != 'created':
        raise ValueError('La imagen o el estado del reemplazo no coinciden')
    for key, value in payload.items():
        if key not in ('HostConfig', 'NetworkingConfig') and created['Config'].get(key) != value:
            raise ValueError('Configuración no preservada: ' + key)
    for key, value in payload['HostConfig'].items():
        actual = created['HostConfig'].get(key)
        if key == 'OomKillDisable' and value in (None, False) and actual in (None, False):
            continue
        if actual != value:
            raise ValueError('Configuración Docker no preservada: ' + key)
    fields = ('Type', 'Source', 'Destination', 'Mode', 'RW', 'Propagation')
    mounts = lambda snapshot: sorted(tuple(mount.get(key) for key in fields) for mount in snapshot['Mounts'])
    if mounts(original) != mounts(created) or network_config(original) != network_config(created):
        raise ValueError('Montajes o configuración de red no preservados')


def ensure_no_pending():
    if DATA.exists() and list(DATA.glob('pending-*.json')):
        raise ValueError('Recreación de Studio sin finalizar; revisar el registro privado antes de arrancar o editar')


def recreate(options, expected_revision):
    ensure_no_pending()
    original = snapshot()
    if revision(original) != expected_revision:
        raise ValueError('Studio cambió; recarga la ficha')
    validate(original, options)
    payload = candidate(original, options)
    unsloth.runtime.private_directory(DATA)
    identifier = uuid.uuid4().hex
    backup_name = unsloth.NAME + '-backup-' + identifier
    temporary_name = unsloth.NAME + '-candidate-' + identifier
    pending = DATA / ('pending-' + identifier + '.json')
    unsloth.runtime.write_private(DATA / ('original-' + identifier + '.json'), json.dumps(original))
    unsloth.runtime.write_private(pending, json.dumps({'original': original['Id'], 'backup_name': backup_name, 'candidate_name': temporary_name, 'health': 'not-tested', 'shared_data': 'same bind mounts, not a data snapshot'}))
    new_id = None
    renamed = False
    try:
        result = request('POST', '/containers/create?name=' + temporary_name, payload)
        new_id = result['Id']
        created = request('GET', '/containers/' + new_id + '/json')
        verify(original, created, payload)
        current = snapshot()
        if revision(current) != expected_revision or current['State']['Status'] not in ('exited', 'created'):
            raise ValueError('Studio cambió durante la recreación')
        request('POST', '/containers/' + original['Id'] + '/rename?name=' + backup_name)
        renamed = True
        request('POST', '/containers/' + new_id + '/rename?name=' + unsloth.NAME)
        unsloth.runtime.write_private(DATA / ('completed-' + identifier + '.json'), json.dumps({'original': original['Id'], 'replacement': new_id, 'backup_name': backup_name, 'health': 'not-tested', 'state': 'stopped', 'changed_fields': sorted(name for name in options if options[name] != values(original)[name])}))
        pending.unlink()
    except Exception:
        if new_id:
            try:
                request('DELETE', '/containers/' + new_id)
                if renamed:
                    request('POST', '/containers/' + original['Id'] + '/rename?name=' + unsloth.NAME)
                pending.unlink()
            except Exception:
                raise ValueError('Recreación incompleta; original conservado. Revisar el registro privado antes de continuar') from None
        raise ValueError('No se recreó Studio; el original se conserva. Revisa el registro privado si existe') from None
    return {'recreated': True, 'health': 'not-tested', 'state': 'stopped'}
