import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import copy
import shlex
import signal
import subprocess
import sys
import time

import runtime

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/laya'
NAME = 'halostrix-laya-cpu'
LABEL = 'io.halostrix.laya'
SOURCE_REVISION = 'd120d4ba220711b93c171973118753460310e16b'
MODEL_REVISION = 'b4a904d1a2a54c822b829e24291d4b8f280fe43e'
BACKEND_PORT = 18181


def deployment():
    value = json.loads(runtime.private_file(DATA / 'deployment.json').read_text())
    if set(value) != {'image', 'source_revision', 'model_revision'} or not re.fullmatch(r'sha256:[0-9a-f]{64}', value['image']):
        raise ValueError('Expected an immutable local image ID')
    if value['source_revision'] != SOURCE_REVISION or value['model_revision'] != MODEL_REVISION:
        raise ValueError('Unreviewed Laya revision')
    return value


def run_command(value):
    models = runtime.checked_mount(str(DATA / 'models'))
    cache = runtime.checked_mount(str(DATA / 'cache'))
    return ['docker', 'run', '--rm', '--pull=never', '--init', '--name', NAME,
            '--label', f'{LABEL}={ROOT}', '--user', f'{os.getuid()}:{os.getgid()}',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--read-only',
            '--cpus=4', '--memory=8g', '--memory-swap=8g', '--pids-limit=256',
            '--stop-timeout=60', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
            '--publish', f'127.0.0.1:{BACKEND_PORT}:8000',
            '--mount', f'type=bind,src={models},dst=/models,readonly',
            '--mount', f'type=bind,src={cache},dst=/cache',
            '--env', 'HF_HUB_OFFLINE=1', '--env', 'TRANSFORMERS_OFFLINE=1',
            '--env', 'HF_HUB_DISABLE_TELEMETRY=1', '--env', 'LAYA_DEVICE=cpu',
            '--env', f'LAYA_MODEL_REVISION={MODEL_REVISION}', value['image']]


def owned():
    result = runtime.docker(['container', 'ls', '-a', '--filter', f'name=^{NAME}$', '--format', '{{.ID}}'])
    identifier = result.stdout.strip()
    if not identifier:
        return None
    value = json.loads(runtime.docker(['inspect', identifier]).stdout)[0]
    if value['Config'].get('Labels', {}).get(LABEL) != str(ROOT):
        raise ValueError('Container name belongs to another deployment')
    return value


def stop():
    value = owned()
    if value:
        runtime.docker(['stop', '--time', '60', value['Id']])


def start():
    value = deployment()
    runtime.private_directory(DATA)
    descriptor = os.open(DATA / 'runtime.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if owned():
            raise ValueError('Existing Laya container must be inspected and stopped first')
        runtime.docker(['image', 'inspect', value['image']])
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
    command = ['/usr/bin/python3', str(ROOT / 'laya_runtime.py')]
    return {'cmd': shlex.join([*command, 'start']),
            'cmdStop': shlex.join([*command, 'stop']),
            'proxy': f'http://127.0.0.1:{BACKEND_PORT}',
            'checkEndpoint': '/health', 'ttl': 0, 'unloadTimeout': 90,
            'concurrencyLimit': 1, 'sendLoadingState': False}


def integrate(gateway):
    candidate = copy.deepcopy(gateway)
    router = candidate.get('routing', {}).get('router', {})
    if router.get('use') != 'group':
        raise ValueError('Only reviewed group routing is supported')
    groups = router.get('settings', {}).get('groups', {})
    if not groups or 'gpu' not in groups:
        raise ValueError('Expected the existing GPU group')
    if 'laya' in candidate['models'] and candidate['models']['laya'] != model_config():
        raise ValueError('Existing Laya model differs; refusing replacement')
    cpu = {'swap': False, 'exclusive': False, 'persistent': True, 'members': ['laya']}
    if 'laya-cpu' in groups and groups['laya-cpu'] != cpu:
        raise ValueError('Existing CPU group differs')
    if any('laya' in group.get('members', []) for name, group in groups.items() if name != 'laya-cpu'):
        raise ValueError('Laya already belongs to another group')
    candidate['models']['laya'] = model_config()
    groups['laya-cpu'] = cpu
    slots = sum(model.get('concurrencyLimit', 1) for model in candidate['models'].values())
    candidate['globalConcurrencyLimit'] = max(candidate.get('globalConcurrencyLimit', 1), slots)
    candidate['captureBuffer'] = 0
    return candidate


def configure(image):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Use the immutable Docker image ID')
    runtime.private_directory(DATA)
    for name in ('models', 'cache'):
        runtime.private_directory(DATA / name)
    metadata = json.loads(runtime.docker(['image', 'inspect', image]).stdout)[0]
    if metadata['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != SOURCE_REVISION:
        raise ValueError('Image does not match reviewed Laya source')
    value = {'image': image, 'source_revision': SOURCE_REVISION, 'model_revision': MODEL_REVISION}
    for name, text in [('deployment.json', json.dumps(value, indent=2) + '\n')]:
        path = DATA / name
        if path.exists():
            if runtime.private_file(path).read_text() != text:
                raise ValueError('Existing configuration differs; stop and review before changing it')
        else:
            runtime.write_private(path, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['configure', 'start', 'stop', 'status'])
    parser.add_argument('--image')
    args = parser.parse_args()
    if args.action == 'configure':
        if not args.image:
            parser.error('--image is required')
        configure(args.image)
    elif args.action == 'status':
        value = owned()
        print(json.dumps({'state': value['State']['Status'] if value else 'stopped', 'gateway': 'existing llama-swap', 'device': 'cpu'}))
    else:
        return {'start': start, 'stop': stop}[args.action]()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
