import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import uuid

import manage
import runtime
import service_options


NAME = 'gufo-qwen38-27b'
PORT = 18102
DATA = runtime.DATA / 'gufo'
IMAGE = 'ghcr.io/gufo-org/toolboxes/gufo-runtime@sha256:989ab52a190244f08511a3ad0fd46546f2144220c37e6c808ad8008a934ebab5'
TARGET = 'Qwen3.8-27B-UD-Q4_K_XL.gguf'
DRAFT = 'Qwen3.8-27B-DFlash2-Q4_K_M.gguf'
PROFILE = DATA / 'profiles-128k-2slots.json'
ARTIFACTS = [
    {'repo': 'unsloth/Qwen3.8-27B-GGUF', 'revision': '4ca720788d1e01f1bff70c033e0d0028fd02e502',
     'file': TARGET, 'size': 17559178144, 'sha256': '3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e'},
    {'repo': 'z-lab/Qwen3.8-27B-DFlash2-GGUF', 'revision': '2d9571f8ce46e151f61c6499c99dee6079e1d610',
     'file': DRAFT, 'size': 1143006816, 'sha256': '1a25c56858e1ebe93f2718ac1d49d1151f9323325c1bbfd6209370f4db131ebd'},
]


def verify_artifacts():
    for entry in ARTIFACTS:
        path = runtime.private_file(DATA / 'models' / entry['file'])
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != entry['sha256'] or path.stat().st_size != entry['size']:
            raise ValueError('GGUF integrity check failed')


def download():
    os.umask(0o077)
    runtime.private_directory(DATA)
    runtime.private_directory(DATA / 'models')
    os.environ['HF_HOME'] = str(DATA / 'cache')
    from huggingface_hub import hf_hub_download
    descriptor = os.open(DATA / 'download.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for entry in ARTIFACTS:
            hf_hub_download(entry['repo'], entry['file'], revision=entry['revision'], local_dir=DATA / 'models')
        verify_artifacts()
        manifest = DATA / 'artifacts.json'
        if manifest.exists():
            if json.loads(runtime.private_file(manifest).read_text()) != ARTIFACTS:
                raise ValueError('Existing artifact manifest differs')
        else:
            runtime.write_private(manifest, json.dumps(ARTIFACTS, indent=2) + '\n')
    print('Pinned target and drafter verified; no services changed')


def profile():
    return {'enabled': True, 'kind': 'gufo', 'image': IMAGE,
            'model_dir': str(DATA / 'models'), 'model': TARGET,
            'dflash_model': DRAFT, 'upstream_model': NAME,
            'context': 131072, 'output': 2048, 'slots': 2}


def integrate(gateway, config=PROFILE):
    profiles = runtime.load_profiles(config)
    if set(profiles) != {NAME} or profiles[NAME]['kind'] != 'gufo':
        raise ValueError('Expected the reviewed Gufo-only profile')
    candidate = copy.deepcopy(gateway)
    router = candidate.get('routing', {}).get('router', {})
    groups = router.get('settings', {}).get('groups', {})
    gpu = groups.get('gpu', {})
    if router.get('use') != 'group' or gpu.get('swap') is not True or gpu.get('exclusive') is not True or gpu.get('persistent', False):
        raise ValueError('Expected the existing exclusive swapping GPU group')
    members = gpu.get('members')
    if not isinstance(members, list) or not members or any(member not in candidate['models'] for member in members):
        raise ValueError('GPU membership is invalid')
    model = manage.render(config)['models'][NAME]
    for field in ('cmd', 'cmdStop'):
        command = shlex.split(model[field])
        command[0] = '/usr/bin/python3'
        if field == 'cmd':
            command[-1] = str(PORT)
        model[field] = shlex.join(command)
    model['proxy'] = f'http://127.0.0.1:{PORT}'
    for name, existing in candidate['models'].items():
        if name == NAME and existing != model:
            raise ValueError('Existing Gufo entry differs; refusing replacement')
        if name != NAME and existing.get('proxy') == model['proxy']:
            raise ValueError('Gufo backend port already configured')
    if any(NAME in group.get('members', []) for name, group in groups.items() if name != 'gpu'):
        raise ValueError('Gufo belongs to another group')
    candidate['models'][NAME] = model
    if NAME not in members:
        members.append(NAME)
    slots = sum(item.get('concurrencyLimit', 1) for item in candidate['models'].values())
    candidate['globalConcurrencyLimit'] = max(candidate.get('globalConcurrencyLimit', 1), slots)
    candidate['captureBuffer'] = 0
    return candidate


def upgrade_candidate(gateway):
    existing = gateway.get('models', {}).get(NAME)
    if existing is None:
        return integrate(gateway)
    command = shlex.split(existing.get('cmd', ''))
    if len(command) != 8 or command[:5] != ['/usr/bin/python3', str(runtime.ROOT / 'runtime.py'), 'start', NAME, '--config'] or command[6:] != ['--port', str(PORT)]:
        raise ValueError('Existing Gufo command is not the reviewed launcher')
    previous = Path(command[5])
    if previous.parent != DATA or previous.is_symlink():
        raise ValueError('Existing Gufo profile must stay in the private Gufo directory')
    integrate(gateway, previous)
    candidate = copy.deepcopy(gateway)
    del candidate['models'][NAME]
    members = candidate['routing']['router']['settings']['groups']['gpu']['members']
    members.remove(NAME)
    return integrate(candidate)


def install(control, details, upgrade=False):
    with control.operation_lock(), service_options.lease('gateway'):
        if control.unit_state('gateway') not in ('inactive', 'failed'):
            raise ValueError('Drain and stop the existing gateway before installing Gufo')
        gateway, _, _, _ = details.gateway_source(control)
        candidate = upgrade_candidate(gateway) if upgrade else integrate(gateway)
        temporary = DATA / ('.validate-' + uuid.uuid4().hex + '.yaml')
        try:
            runtime.write_private(temporary, json.dumps(candidate))
            result = control.run([str(runtime.DATA / 'bin/llama-swap'), '-config', str(temporary), '-validate'], check=False)
            if result.returncode:
                raise ValueError('llama-swap rejected the candidate')
            if details.gateway_source(control)[0] != gateway:
                raise ValueError('Active configuration changed during validation')
            if candidate != gateway:
                details.replace_with_backup(details.GATEWAY, candidate)
        finally:
            temporary.unlink(missing_ok=True)


def activate(control, details, action, locked=False):
    import contextlib
    if action not in ('load', 'unload'):
        raise ValueError('Unsupported Gufo lifecycle action')
    with contextlib.nullcontext() if locked else control.operation_lock():
        if control.unit_state('gateway') != 'active':
            raise ValueError('Start the existing gateway first')
        gateway, _, _, _ = details.gateway_source(control)
        if integrate(gateway) != gateway:
            raise ValueError('Gufo catalog configuration is not current')
        if control.inflight():
            raise ValueError('Gateway busy; wait before changing GPU residency')
        if action == 'load':
            control.unsloth.require_stopped()
            control.llamafactory.require_stopped()
            containers = control.containers()
            if containers is None or set(containers) - {'halostrix-' + NAME, 'halostrix-' + control.config()['model']}:
                raise ValueError('Another GPU engine is active or unknown')
            result = control.http('/upstream/' + NAME + '/ready', timeout=1200)
            if not isinstance(result, dict) or result.get('status') != 'ready' or result.get('model') != NAME:
                raise ValueError('Gufo did not confirm model readiness')
        else:
            control.http('/api/models/unload/' + NAME, {}, timeout=150)
            if runtime.inspect_owned('halostrix-' + NAME) is not None:
                raise ValueError('Gufo container did not stop')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['download', 'prepare', 'install', 'upgrade', 'load', 'unload'])
    args = parser.parse_args()
    if args.action == 'download':
        download()
    elif args.action == 'prepare':
        runtime.private_directory(DATA)
        value = profile()
        runtime.validate_profile(NAME, value)
        verify_artifacts()
        runtime.docker(['image', 'inspect', IMAGE])
        text = json.dumps({'profiles': {NAME: value}}, indent=2) + '\n'
        if PROFILE.exists():
            if runtime.private_file(PROFILE).read_text() != text:
                raise ValueError('Existing profile differs; refusing replacement')
        else:
            runtime.write_private(PROFILE, text)
        print('Gufo profile prepared; no services changed')
    else:
        sys.path.insert(0, str(runtime.ROOT.parent / 'halo-control'))
        import control
        import engine_details
        if args.action in ('load', 'unload'):
            activate(control, engine_details, args.action)
            print('Gufo ' + ('loaded' if args.action == 'load' else 'unloaded') + '; catalog entry preserved')
        else:
            install(control, engine_details, upgrade=args.action == 'upgrade')
            print('Gufo configured in the existing gateway; start that gateway to apply')


if __name__ == '__main__':
    main()
