import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.request

import unsloth

runtime = unsloth.runtime
import service_options

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
NAME = 'halostrix-llamaboard-panel'
LEGACY = 'halostrix-llamafactory-llamaboard-1'
REVISION = '7af909522a951e3ad9f022ea6f88b6755257eaa5'
SOURCE = 'https://github.com/hiyouga/LlamaFactory'
DIRECTORIES = {'hf-cache': '/workspace/hf-cache', 'models': '/workspace/models', 'datasets': '/workspace/data', 'outputs': '/workspace/saves', 'cache': '/workspace/cache', 'config': '/workspace/config', 'logs': '/workspace/logs'}
LABEL = 'io.halostrix.llamaboard'


def metadata(name):
    result = runtime.docker(['container', 'ls', '-a', '--filter', f'name=^{name}$', '--format', '{{.ID}}'])
    identifier = result.stdout.strip()
    if not identifier:
        return None
    if '\n' in identifier:
        raise ValueError('Ambiguous LlamaBoard container')
    template = '{"id":{{json .Id}},"image":{{json .Image}},"labels":{{json .Config.Labels}},"state":{{json .State.Status}},"mounts":{{json .Mounts}}}'
    value = json.loads(runtime.docker(['inspect', '--format', template, identifier]).stdout)
    if name == LEGACY:
        expected = {'com.docker.compose.project':'halostrix-llamafactory', 'com.docker.compose.service':'llamaboard', 'org.opencontainers.image.revision':REVISION}
    else:
        expected = {LABEL: str(ROOT), 'org.opencontainers.image.revision':REVISION}
    if any(value['labels'].get(key) != expected_value for key, expected_value in expected.items()):
        raise ValueError('LlamaBoard container ownership mismatch')
    validate_image(value['image'])
    return value


def validate_image(image):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('LlamaBoard image must be a full local immutable ID')
    labels = json.loads(runtime.docker(['image', 'inspect', image, '--format', '{{json .Config.Labels}}']).stdout)
    if labels.get('org.opencontainers.image.revision') != REVISION or labels.get('org.opencontainers.image.source') != SOURCE:
        raise ValueError('LLaMA-Factory image source/revision mismatch')


def validate_config(value):
    if set(value) != {'image', 'bind', 'data_root'}:
        raise ValueError('Invalid LlamaBoard configuration fields')
    address = ipaddress.IPv4Address(value['bind'])
    if not any(address in ipaddress.IPv4Network(network) for network in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('Use a private LAN or loopback address, not wildcard')
    validate_image(value['image'])
    root = Path(value['data_root'])
    if not root.is_absolute() or root.is_symlink() or root.resolve() not in {(Path.home() / 'ai/llama-factory/data').resolve(), (ROOT.parent / 'llama-factory/data').resolve()}:
        raise ValueError('Data must belong to the reviewed LLaMA-Factory workspace')
    for directory in DIRECTORIES:
        path = root / directory
        runtime.checked_mount(str(path))
        if path.is_symlink() or path.stat().st_uid != os.getuid() or not os.access(path, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError('Existing data must be writable by the operator without ownership changes')
    return value


def config():
    return validate_config(json.loads(runtime.private_file(DATA / 'llamaboard.json').read_text()))


def prepare(bind):
    runtime.private_directory(DATA)
    path = DATA / 'llamaboard.json'
    if path.exists():
        config()
        print('Existing LlamaBoard configuration preserved')
        return
    legacy = metadata(LEGACY)
    if not legacy:
        raise ValueError('Legacy LlamaBoard container missing; nothing created')
    if legacy['state'] not in ('exited','created','dead'):
        raise ValueError('Stop legacy LlamaBoard before adoption')
    mounts = {entry['Destination']: entry for entry in legacy['mounts']}
    roots = set()
    for directory, destination in DIRECTORIES.items():
        mount = mounts.get(destination)
        if not mount or mount['Type'] != 'bind' or Path(mount['Source']).name != directory:
            raise ValueError('Legacy mounts do not match the reviewed layout')
        roots.add(str(Path(mount['Source']).parent))
    if len(roots) != 1:
        raise ValueError('Legacy data roots are inconsistent')
    value = validate_config({'image':legacy['image'], 'bind':bind, 'data_root':roots.pop()})
    runtime.write_private(path, json.dumps(value, indent=2) + '\n')
    print('LlamaBoard prepared; original container, data and image preserved. No GPU started.')


def endpoint(value):
    return 'http://' + value['bind'] + ':7860'


def status():
    try:
        legacy = metadata(LEGACY)
        current = metadata(NAME)
        value = config()
        state = current['state'] if current else 'stopped'
        if legacy and legacy['state'] not in ('exited','created','dead'):
            return {'available':False,'state':'legacy-active','health':False,'url':None,'error':'Legacy LlamaBoard active; stop it explicitly first'}
        healthy = False
        if state == 'running':
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(endpoint(value) + '/', timeout=3) as response:
                    healthy = response.status == 200
            except OSError:
                pass
        return {'available':True,'state':state,'health':healthy,'url':endpoint(value),'error':'Contenedor activo; la interfaz HTTP todavía no responde. Revisa los logs.' if state == 'running' and not healthy else ''}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {'available':False,'state':'unconfigured','health':False,'url':None,'error':str(error)}


def require_stopped():
    for name in (LEGACY, NAME):
        value = metadata(name)
        if value and value['state'] not in ('exited','created','dead'):
            raise ValueError('LlamaBoard is active. Finish training and explicitly stop it before switching GPU services')


def stop():
    value = metadata(NAME)
    if value and value['state'] not in ('exited','created','dead'):
        runtime.docker(['stop','--timeout','60',value['id']])


def run_command(value, devices):
    value = validate_config(value)
    options = service_options.read('llamafactory')
    command = ['docker','run','--rm','--init','--pull=never','--name',NAME,'--label',LABEL+'='+str(ROOT),'--label','org.opencontainers.image.revision='+REVISION,'--user',f'{os.getuid()}:{os.getgid()}','--cap-drop=ALL','--security-opt=no-new-privileges',f"--shm-size={options['shm_gib']}g",'--stop-timeout','60','--publish',value['bind']+':7860:7860']
    for device in devices:
        command.extend(['--device',str(device)])
    for group in sorted({str(device.stat().st_gid) for device in devices}):
        command.extend(['--group-add',group])
    for directory,destination in DIRECTORIES.items():
        command.extend(['--mount',f'type=bind,src={runtime.checked_mount(str(Path(value["data_root"]) / directory))},dst={destination}'])
    for directory, destination in (('cache', '/workspace/llamaboard_cache'), ('config', '/workspace/llamaboard_config')):
        command.extend(['--mount', f'type=bind,src={runtime.checked_mount(str(Path(value["data_root"]) / directory))},dst={destination}'])
    for variable in ('HOME=/workspace/cache','GRADIO_SERVER_NAME=0.0.0.0','GRADIO_SERVER_PORT=7860','GRADIO_SHARE=false','HF_HOME=/workspace/hf-cache','HF_HUB_CACHE=/workspace/hf-cache/hub','TRANSFORMERS_CACHE=/workspace/hf-cache/transformers','TORCH_EXTENSIONS_DIR=/workspace/cache/torch-extensions','TRITON_CACHE_DIR=/workspace/cache/triton','PYTORCH_KERNEL_CACHE_PATH=/workspace/cache/torch-kernels'):
        command.extend(['--env',variable])
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
        command.extend(['--env', name + '=' + str(int(options['hf_offline']))])
    command.extend(['--env', 'TOKENIZERS_PARALLELISM=' + str(options['tokenizers_parallelism']).lower()])
    command.extend(['--entrypoint','llamafactory-cli',value['image'],'webui'])
    return command


def start():
    value = config()
    runtime.private_directory(runtime.DATA)
    descriptor = os.open(runtime.DATA / 'gpu.lock',os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'a') as lock, service_options.lease('llamafactory') as settings_descriptor:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('GPU reserved by another managed runtime') from error
        runtime.require_halo()
        unsloth.require_stopped()
        require_stopped()
        active = runtime.docker(['container','ls','--filter',f'label={runtime.LABEL}={runtime.ROOT}','--format','{{.ID}}'])
        if active.stdout.strip():
            raise ValueError('Managed inference container is still active')
        command = run_command(value,runtime.devices('llamafactory-rocm'))
        cancelled = False
        child = None

        def terminate(signum,frame):
            nonlocal cancelled
            cancelled = True

        previous = {signum:signal.signal(signum,terminate) for signum in (signal.SIGINT,signal.SIGTERM)}
        try:
            print('LlamaBoard:',endpoint(value),'(trusted LAN only; no built-in authentication)',flush=True)
            child = subprocess.Popen(command,pass_fds=(lock.fileno(),settings_descriptor))
            while child.poll() is None:
                if cancelled:
                    stop()
                time.sleep(0.2)
            return child.returncode
        finally:
            try:
                stop()
                if child and child.poll() is None:
                    child.wait(timeout=75)
            finally:
                for signum,handler in previous.items():
                    signal.signal(signum,handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','start','stop','status'))
    parser.add_argument('--bind',default='127.0.0.1')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.bind)
    elif args.action == 'status':
        print(json.dumps(status()))
    else:
        return start() if args.action == 'start' else stop()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
