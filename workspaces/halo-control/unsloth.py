import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


INFERENCE = Path(__file__).resolve().parent.parent / 'inference'
sys.path.insert(0, str(INFERENCE))
import runtime
import service_options


NAME = 'halostrix-unsloth-studio-studio-1'
REVISION = 'e18a069c15cde98c7af77ccdb952254db8b0315d'
EXPECTED_LABELS = {'com.docker.compose.project': 'halostrix-unsloth-studio', 'com.docker.compose.service': 'studio', 'com.halostrix.project': 'halostrix-unsloth-studio', 'com.halostrix.service': 'studio', 'org.opencontainers.image.revision': REVISION, 'com.halostrix.commit': REVISION}
FORMAT = '{"id":{{json .Id}},"image":{{json .Image}},"user":{{json .Config.User}},"labels":{{json .Config.Labels}},"state":{{json .State.Status}},"ports":{{json .HostConfig.PortBindings}}}'


def inspect():
    result = runtime.docker(['container', 'ls', '-a', '--filter', f'name=^{NAME}$', '--format', '{{.ID}}'])
    identifier = result.stdout.strip()
    if not identifier:
        return None
    if '\n' in identifier:
        raise ValueError('Ambiguous Studio container')
    metadata = json.loads(runtime.docker(['inspect', '--format', FORMAT, identifier]).stdout)
    if any(metadata['labels'].get(key) != value for key, value in EXPECTED_LABELS.items()):
        raise ValueError('Studio container ownership/revision mismatch')
    if metadata['user'].split(':', 1)[0] != str(os.getuid()) or os.getuid() == 0:
        raise ValueError('Studio must run as the current non-root operator')
    image_labels = json.loads(runtime.docker(['image', 'inspect', metadata['image'], '--format', '{{json .Config.Labels}}']).stdout)
    for key in ('com.halostrix.project', 'com.halostrix.service', 'org.opencontainers.image.revision', 'com.halostrix.commit'):
        if image_labels.get(key) != EXPECTED_LABELS[key]:
            raise ValueError('Studio image ownership/revision mismatch')
    return metadata


def endpoint(metadata):
    bindings = metadata['ports'].get('8888/tcp') or []
    if len(bindings) != 1:
        raise ValueError('Studio requires one explicit port binding')
    address = ipaddress.IPv4Address(bindings[0]['HostIp'])
    if not any(address in ipaddress.IPv4Network(network) for network in ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Studio must bind to loopback or a private LAN address, not all interfaces')
    port = int(bindings[0]['HostPort'])
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid Studio port')
    return f'http://{address}:{port}'


def health(metadata):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(endpoint(metadata) + '/api/health', timeout=3) as response:
        return response.status == 200


def status():
    try:
        metadata = inspect()
        if metadata is None:
            return {'available': False, 'state': 'missing', 'health': False, 'url': None, 'error': 'Existing Studio container not found; prepare the original workspace first'}
        url = endpoint(metadata)
        healthy = False
        if metadata['state'] == 'running':
            try:
                healthy = health(metadata)
            except OSError:
                pass
        return {'available': True, 'state': metadata['state'], 'health': healthy, 'url': url, 'error': ''}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {'available': False, 'state': 'unknown', 'health': False, 'url': None, 'error': str(error)}


def require_stopped():
    metadata = inspect()
    if metadata is not None and metadata['state'] not in ('exited', 'created', 'dead'):
        raise ValueError('Unsloth Studio is active. Finish training and explicitly stop Studio before switching GPU services')


def stop():
    metadata = inspect()
    if metadata is not None and metadata['state'] not in ('exited', 'created', 'dead'):
        runtime.docker(['stop', '--timeout', '60', metadata['id']])


def start():
    runtime.private_directory(runtime.DATA)
    descriptor = os.open(runtime.DATA / 'gpu.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock, service_options.lease('unsloth') as settings_descriptor:
        import studio_recreate
        studio_recreate.ensure_no_pending()
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('GPU reserved by another managed runtime; switch or stop it first') from error
        runtime.require_halo()
        metadata = inspect()
        if metadata is None:
            raise ValueError('Existing Studio container not found; no image/data/credentials will be recreated')
        url = endpoint(metadata)
        require_stopped()
        active = runtime.docker(['container', 'ls', '--filter', f'label={runtime.LABEL}={runtime.ROOT}', '--format', '{{.ID}}'])
        if active.stdout.strip():
            raise ValueError('An inference container is active; Studio was not started')
        cancelled = False
        child = None

        def terminate(signum, frame):
            nonlocal cancelled
            cancelled = True

        previous = {signum: signal.signal(signum, terminate) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            print('Starting existing Unsloth Studio at', url, flush=True)
            print('Studio keeps its own authentication. Training support is not validated.', flush=True)
            child = subprocess.Popen(['docker', 'start', '--attach', metadata['id']], pass_fds=(lock.fileno(), settings_descriptor))
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
                for signum, handler in previous.items():
                    signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description='Adopt the existing Studio container without changing data or credentials')
    parser.add_argument('action', choices=('start', 'stop', 'status'))
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(status()))
        return 0
    return start() if args.action == 'start' else stop()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
