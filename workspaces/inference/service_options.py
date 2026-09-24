import contextlib
import fcntl
import json
import os
from pathlib import Path

import runtime


DATA = Path(__file__).resolve().parent / 'data'
DEFAULTS = {
    'comfyui': {'reserve_vram': 4, 'cache_none': True, 'bf16_vae': True, 'disable_smart_memory': True, 'hipblaslt': True, 'aotriton': True},
    'llamafactory': {'shm_gib': 16, 'hf_offline': False, 'tokenizers_parallelism': False},
}


def validate(service, values):
    if service not in DEFAULTS or not isinstance(values, dict) or set(values) != set(DEFAULTS[service]):
        raise ValueError('Unknown or missing runtime setting')
    for name, default in DEFAULTS[service].items():
        value = values[name]
        if type(default) is bool:
            if type(value) is not bool:
                raise ValueError('Expected boolean: ' + name)
        elif type(value) is not int or not 1 <= value <= (24 if name == 'reserve_vram' else 32):
            raise ValueError('Runtime memory setting outside allowed range: ' + name)
    return values


def read(service):
    if service not in DEFAULTS:
        raise ValueError('Unknown service options')
    path = DATA / (service + '-options.json')
    values = dict(DEFAULTS[service])
    if path.exists() or path.is_symlink():
        stored = json.loads(runtime.private_file(path).read_text())
        if not isinstance(stored, dict):
            raise ValueError('Expected a settings object')
        values.update(stored)
    return validate(service, values)


@contextlib.contextmanager
def lease(service):
    if service not in {*DEFAULTS, 'gateway', 'unsloth'}:
        raise ValueError('Unknown service options')
    runtime.private_directory(DATA)
    descriptor = os.open(DATA / (service + '-settings.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Service settings are in use; stop the service before saving') from error
        yield stream.fileno()
