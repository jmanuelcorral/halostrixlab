import json
from pathlib import Path
import re
import time
import uuid

import unsloth
import llamafactory


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def pending(control):
    value = control.cached('reboot')
    if not value:
        return None
    record = value['data']
    return record if record.get('boot_id') == boot_id() and record.get('expires', 0) > time.time() else None


def package_idle():
    if Path('/var/lib/pacman/db.lck').exists():
        raise ValueError('Actualización de paquetes activa o bloqueada; no se interrumpe para reiniciar')
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process / 'comm').read_text().strip()
        except FileNotFoundError:
            continue
        if name in ('pacman', 'pamac', 'yay', 'paru'):
            raise ValueError('Gestor de paquetes activo; espera antes de reiniciar')


def verify_stopped(control):
    for kind in ('gateway', 'comfyui', 'unsloth', 'llamafactory'):
        if control.unit_state(kind) not in ('inactive', 'failed'):
            raise ValueError('No se confirmó la parada de ' + kind)
    if control.containers() != []:
        raise ValueError('Quedan contenedores de inferencia activos o no se pueden consultar')
    unsloth.require_stopped()
    llamafactory.require_stopped()
    package_idle()


def prepare(control):
    package_idle()
    control.save_cache('reboot', {'boot_id': boot_id(), 'expires': time.time() + 900, 'phase': 'stopping'})
    try:
        for kind in ('gateway', 'comfyui', 'unsloth', 'llamafactory'):
            control.save_cache('reboot', {'boot_id': boot_id(), 'expires': time.time() + 900, 'phase': 'Deteniendo ' + kind})
            control.unit('stop', kind)
        unsloth.stop()
        llamafactory.stop()
        legacy = llamafactory.metadata(llamafactory.LEGACY)
        if legacy and legacy['state'] not in ('created', 'exited', 'dead'):
            unsloth.runtime.docker(['stop', '--timeout', '60', legacy['id']])
        names = control.containers()
        if names is None:
            raise ValueError('No se pueden verificar los contenedores de inferencia')
        for name in names:
            if not re.fullmatch(r'halostrix-[a-z][a-z0-9-]{0,47}', name):
                raise ValueError('Contenedor gestionado con nombre no reconocido')
            unsloth.runtime.stop(name.removeprefix('halostrix-'))
        verify_stopped(control)
        control.save_cache('reboot', {'boot_id': boot_id(), 'expires': time.time() + 300, 'phase': 'ready', 'token': uuid.uuid4().hex})
    except Exception:
        control.save_cache('reboot', {})
        raise


def verify(control, token):
    with control.operation_lock(allow_reboot=True):
        record = pending(control)
        if not record or record.get('phase') != 'ready' or record.get('token') != token:
            raise ValueError('Preparación de reinicio caducada; confirma de nuevo')
        verify_stopped(control)
    return {'ready': True, 'boot_id': record['boot_id']}


def release(control, token):
    with control.operation_lock(allow_reboot=True):
        record = pending(control)
        if record and record.get('token') == token:
            control.save_cache('reboot', {})
    return {'released': True}
