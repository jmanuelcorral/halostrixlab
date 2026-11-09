import argparse
import contextlib
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
import uuid

import runtime
import service_options


ROOT = runtime.ROOT
DATA = runtime.DATA / 'winnow'
NAME = 'halostrix-winnow-cpu'
ALIAS = 'winnow-12b-cpu'
MODEL = 'winnow:12b'
LABEL = 'io.halostrix.ollaya'
NETWORK = 'halostrix-winnow-cpu'
PORT = 18182
SOURCE = '32acb6d2ea13f616b1e11d9dfb8260b305106847'
BASE_IMAGE = 'ghcr.io/ollaya-dev/ollaya@sha256:3fb6a50039bd97147e131844c21401f2b01aa648cd3749d4c8d8773f5f200fb5'
PYTHON_IMAGE = 'python@sha256:37134a49d21d2120e4c4d73bb76f8a4ab9aef31f096f7ec2ead48c2feead4332'
MANIFEST_SHA = '8d72fee0e5f92a625cdb85ae4f6abdc024c9e6f124a0ca67e64522c3f24c47ce'
WEIGHT_SHA = 'b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea'
REVISION = 'b6ac22b0d51b69b18200acacb3fbdd98073fffe8'
WEIGHT_SIZE = 12669646592
MANIFEST_PATH = Path('manifests/ollaya.dev/library/winnow/12b')


def digest(path):
    with runtime.private_file(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest():
    path = DATA / 'models' / MANIFEST_PATH
    if digest(path) != MANIFEST_SHA:
        raise ValueError('Unreviewed model manifest')
    return json.loads(path.read_text())


def verify(full=True):
    value = manifest()
    for entry in [value['config'], *value['layers']]:
        checksum = entry['digest'].removeprefix('sha256:')
        if not re.fullmatch('[0-9a-f]{64}', checksum):
            raise ValueError('Invalid artifact digest')
        path = runtime.private_file(DATA / 'models/blobs' / ('sha256-' + checksum))
        if path.stat().st_size != entry['size'] or (full and digest(path) != checksum):
            raise ValueError('Model artifact failed integrity verification')


def download():
    os.umask(0o077)
    runtime.private_directory(DATA)
    with lock('download'):
        store = runtime.private_directory(DATA / 'models')
        blobs = runtime.private_directory(store / 'blobs')
        target = store / MANIFEST_PATH
        raw = subprocess.run(['gh', 'api', f'repos/ollaya-dev/ollaya/contents/registry/v2/library/winnow/manifests/12b?ref={SOURCE}', '--jq', '.content'], check=True, capture_output=True).stdout
        import base64
        raw = base64.b64decode(raw)
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
            raise ValueError('Registry manifest changed')
        value = json.loads(raw)
        for entry in [value['config'], *value['layers']]:
            checksum = entry['digest'].removeprefix('sha256:')
            path = blobs / ('sha256-' + checksum)
            if path.exists():
                if path.stat().st_size != entry['size'] or digest(path) != checksum:
                    raise ValueError('Existing blob differs; refusing replacement')
                continue
            if checksum == WEIGHT_SHA:
                os.environ['HF_HOME'] = str(DATA / 'cache')
                os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
                from huggingface_hub import hf_hub_download
                source = Path(hf_hub_download('EldanRing/Winnow-12B', 'gguf/Winnow-12B-Q8_0.gguf', revision=REVISION, local_dir=DATA / 'stage', token=False))
                if source.stat().st_size != WEIGHT_SIZE or digest(source) != WEIGHT_SHA:
                    raise ValueError('Weight verification failed')
                os.link(source, path)
            else:
                url = entry['urls'][0]
                if url != 'https://ollaya.dev/blobs/sha256-' + checksum:
                    raise ValueError('Unexpected metadata source')
                request = urllib.request.Request(url, headers={'User-Agent': 'ollaya/0.7.5'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read(entry['size'] + 1)
                if len(content) != entry['size'] or hashlib.sha256(content).hexdigest() != checksum:
                    raise ValueError('Metadata verification failed')
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(content)
        if target.exists():
            if runtime.private_file(target).read_bytes() != raw:
                raise ValueError('Existing manifest differs')
        else:
            runtime.write_private(target, raw.decode())
        verify()
    print('Winnow-12B Q8 weights and metadata verified')


@contextlib.contextmanager
def lock(name):
    runtime.private_directory(DATA)
    descriptor = os.open(DATA / (name + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def build():
    for image in (BASE_IMAGE, PYTHON_IMAGE):
        subprocess.run(['docker', 'pull', image], check=True)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz', format=tarfile.USTAR_FORMAT) as archive:
        archive.add(ROOT / 'ollaya.Dockerfile', arcname='Dockerfile')
        archive.add(ROOT / 'ollaya_server.py', arcname='ollaya_server.py')
    subprocess.run(['docker', 'build', '--network=none', '-t', 'halostrix-ollaya:0.7.5-cpu', '-'], input=stream.getvalue(), check=True)


def ensure_network():
    result = runtime.docker(['network', 'inspect', NETWORK], check=False)
    if result.returncode:
        runtime.docker(['network', 'create', '--opt', 'com.docker.network.bridge.enable_ip_masquerade=false', '--label', f'{LABEL}={ROOT}', NETWORK])
        result = runtime.docker(['network', 'inspect', NETWORK])
    value = json.loads(result.stdout)[0]
    if value.get('Internal') or value.get('Options', {}).get('com.docker.network.bridge.enable_ip_masquerade') != 'false' or value.get('Labels', {}).get(LABEL) != str(ROOT):
        raise ValueError('Network must be owned with outbound masquerading disabled')


def configure():
    verify()
    metadata = json.loads(runtime.docker(['image', 'inspect', 'halostrix-ollaya:0.7.5-cpu']).stdout)[0]
    if metadata['Config'].get('Labels', {}).get('io.halostrix.ollaya.source') != SOURCE:
        raise ValueError('Unexpected image provenance')
    value = {'image': metadata['Id'], 'source': SOURCE, 'manifest': MANIFEST_SHA,
             'adapter_sha256': hashlib.sha256((ROOT / 'ollaya_server.py').read_bytes()).hexdigest()}
    path = DATA / 'deployment.json'
    if path.exists():
        if json.loads(runtime.private_file(path).read_text()) != value:
            raise ValueError('Existing deployment differs; stop and review before replacing')
    else:
        runtime.write_private(path, json.dumps(value, indent=2) + '\n')
    ensure_network()


def deployment():
    value = json.loads(runtime.private_file(DATA / 'deployment.json').read_text())
    if set(value) != {'image', 'source', 'manifest', 'adapter_sha256'} or not re.fullmatch(r'sha256:[0-9a-f]{64}', value['image']):
        raise ValueError('Expected immutable reviewed deployment')
    if value['source'] != SOURCE or value['manifest'] != MANIFEST_SHA or value['adapter_sha256'] != hashlib.sha256((ROOT / 'ollaya_server.py').read_bytes()).hexdigest():
        raise ValueError('Deployment source differs')
    return value


def run_command(value):
    models = runtime.checked_mount(str(DATA / 'models'))
    return ['docker', 'run', '--rm', '--pull=never', '--init', '--name', NAME,
            '--label', f'{LABEL}={ROOT}', '--user', f'{os.getuid()}:{os.getgid()}',
            '--network', NETWORK, '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--read-only', '--cpus=8', '--memory=32g', '--memory-swap=32g',
            '--pids-limit=256', '--stop-timeout=60', '--log-opt', 'max-size=5m',
            '--log-opt', 'max-file=2', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
            '--tmpfs', '/home/ollaya/.ollaya:rw,nosuid,nodev,size=1m',
            '--publish', f'127.0.0.1:{PORT}:8000',
            '--mount', f'type=bind,src={models},dst=/models,readonly', value['image']]


def owned():
    result = runtime.docker(['container', 'ls', '-a', '--filter', f'name=^{NAME}$', '--format', '{{.ID}}'])
    if not result.stdout.strip():
        return None
    value = json.loads(runtime.docker(['inspect', result.stdout.strip()]).stdout)[0]
    if value['Config'].get('Labels', {}).get(LABEL) != str(ROOT):
        raise ValueError('Container belongs to another deployment')
    return value


def stop():
    value = owned()
    if value:
        runtime.docker(['stop', '--time', '60', value['Id']])


def start():
    with lock('runtime'):
        value = deployment()
        verify(full=False)
        ensure_network()
        if owned():
            raise ValueError('Existing Winnow container must be stopped first')
        cancelled = False
        def terminate(signum, frame):
            nonlocal cancelled
            cancelled = True
        previous = {signum: signal.signal(signum, terminate) for signum in (signal.SIGTERM, signal.SIGINT)}
        child = None
        try:
            child = subprocess.Popen(run_command(value))
            while child.poll() is None:
                if cancelled:
                    stop()
                time.sleep(0.2)
            return child.returncode
        finally:
            try:
                stop()
                if child and child.poll() is None:
                    child.wait(timeout=70)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)


def model_config():
    command = ['/usr/bin/python3', str(ROOT / 'ollaya_runtime.py')]
    return {'cmd': shlex.join([*command, 'start']), 'cmdStop': shlex.join([*command, 'stop']),
            'proxy': f'http://127.0.0.1:{PORT}', 'checkEndpoint': '/ready', 'ttl': 0,
            'unloadTimeout': 90, 'concurrencyLimit': 1, 'sendLoadingState': False}


def integrate(gateway):
    candidate = copy.deepcopy(gateway)
    router = candidate.get('routing', {}).get('router', {})
    groups = router.get('settings', {}).get('groups', {})
    if router.get('use') != 'group' or 'gpu' not in groups:
        raise ValueError('Expected reviewed existing group routing')
    group = {'swap': False, 'exclusive': False, 'persistent': True, 'members': [ALIAS]}
    if 'winnow-cpu' in groups and groups['winnow-cpu'] != group:
        raise ValueError('Existing CPU group differs')
    if any(ALIAS in item.get('members', []) for name, item in groups.items() if name != 'winnow-cpu'):
        raise ValueError('Model already belongs to another group')
    model = model_config()
    for name, existing in candidate['models'].items():
        if name == ALIAS and existing != model:
            raise ValueError('Existing model differs')
        if name != ALIAS and existing.get('proxy') == model['proxy']:
            raise ValueError('Backend port already configured')
    candidate['models'][ALIAS] = model
    groups['winnow-cpu'] = group
    candidate['globalConcurrencyLimit'] = max(candidate.get('globalConcurrencyLimit', 1), sum(item.get('concurrencyLimit', 1) for item in candidate['models'].values()))
    candidate['captureBuffer'] = 0
    return candidate


def unit_path():
    result = subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'LoadUnit', 's', 'llama-swap.service'], capture_output=True, text=True, check=True)
    return shlex.split(result.stdout)[1]


def unit_state():
    result = subprocess.run(['busctl', '--user', 'get-property', 'org.freedesktop.systemd1', unit_path(), 'org.freedesktop.systemd1.Unit', 'ActiveState'], capture_output=True, text=True, check=True)
    return shlex.split(result.stdout)[1]


def unit_action(action):
    if action not in ('StartUnit', 'StopUnit'):
        raise ValueError('Unsupported unit operation')
    subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', action, 'ss', 'llama-swap.service', 'replace'], capture_output=True, check=True)
    expected = 'active' if action == 'StartUnit' else 'inactive'
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if unit_state() == expected:
            return
        time.sleep(0.5)
    raise ValueError('Gateway state transition timed out')


def gateway_source(control, details):
    unit = subprocess.run(['busctl', '--user', 'get-property', 'org.freedesktop.systemd1', unit_path(), 'org.freedesktop.systemd1.Service', 'ExecStart'], capture_output=True, text=True, check=True).stdout
    launcher = runtime.private_file(details.LAUNCHER).read_text()
    if str(details.LAUNCHER) not in unit or details.GATEWAY.name not in launcher or "service_options.lease('gateway')" not in launcher:
        raise ValueError('Unreviewed active gateway launcher')
    gateway = details.document(details.GATEWAY)
    command = shlex.split(gateway['models'][control.config()['model']]['cmd'])
    if len(command) != 8 or command[:5] != ['/usr/bin/python3', str(ROOT / 'runtime.py'), 'start', control.config()['model'], '--config'] or command[6] != '--port':
        raise ValueError('Unreviewed active GPU command')
    path = Path(command[5])
    if path.parent != runtime.DATA or path.is_symlink():
        raise ValueError('Unreviewed active GPU profile')
    runtime.load_profiles(path)
    return gateway


def install(restart=False):
    sys.path.insert(0, str(ROOT.parent / 'halo-control'))
    import control
    import engine_details as details
    deployment()
    with control.operation_lock():
        gateway = gateway_source(control, details)
        candidate = integrate(gateway)
        if gateway == candidate:
            return
        temporary = DATA / ('.validate-' + uuid.uuid4().hex + '.yaml')
        was_active = unit_state() == 'active'
        if was_active and not restart:
            raise ValueError('Gateway active; explicit --restart required for drained maintenance')
        resident = []
        try:
            runtime.write_private(temporary, json.dumps(candidate))
            result = subprocess.run([str(runtime.DATA / 'bin/llama-swap'), '-config', str(temporary), '-validate'], capture_output=True)
            if result.returncode:
                raise ValueError('Gateway rejected candidate configuration')
            if was_active:
                if control.inflight():
                    raise ValueError('Gateway busy; nothing changed')
                for name in gateway['models']:
                    if name == 'laya':
                        import laya_runtime
                        if laya_runtime.owned():
                            resident.append(name)
                    elif runtime.inspect_owned('halostrix-' + name):
                        resident.append(name)
                unit_action('StopUnit')
            try:
                with service_options.lease('gateway'):
                    if unit_state() not in ('inactive', 'failed') or gateway_source(control, details) != gateway:
                        raise ValueError('Gateway is active or configuration changed')
                    details.replace_with_backup(details.GATEWAY, candidate)
            finally:
                if was_active and unit_state() in ('inactive', 'failed'):
                    unit_action('StartUnit')
                    control.ready()
                    for name in resident:
                        control.http('/upstream/' + name + gateway['models'][name].get('checkEndpoint', '/health'), timeout=1200)
        finally:
            temporary.unlink(missing_ok=True)
    print('Added Winnow CPU to the existing gateway; previous resident models restored')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['download', 'build', 'configure', 'verify', 'start', 'stop', 'install', 'load', 'unload', 'status'])
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    if args.action == 'install':
        install(args.restart)
    elif args.action in ('load', 'unload'):
        sys.path.insert(0, str(ROOT.parent / 'halo-control'))
        import control
        with control.operation_lock():
            if unit_state() != 'active':
                raise ValueError('Start the existing gateway first')
            if control.inflight():
                raise ValueError('Gateway busy')
            if args.action == 'load':
                result = control.http('/upstream/' + ALIAS + '/ready', timeout=600)
                if result.get('status') != 'ready' or result.get('device') != 'cpu':
                    raise ValueError('CPU inference readiness failed')
            else:
                control.http('/api/models/unload/' + ALIAS, {}, timeout=150)
                if owned():
                    raise ValueError('Container did not stop')
        print('Winnow CPU ' + args.action + ' complete')
    elif args.action == 'status':
        value = owned()
        print(json.dumps({'state': value['State']['Status'] if value else 'stopped', 'alias': ALIAS, 'device': 'cpu'}))
    else:
        return globals()[args.action]()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError):
        print('Ollaya operation failed; inspect private evidence before retrying', file=sys.stderr)
        sys.exit(1)
