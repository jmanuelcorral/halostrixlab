#!/usr/bin/env python3
"""Weekly maintenance for the Halo: system update, reboot and ntfy notices.

Actions:
  update    wait for idle inference, take a labelled snapper snapshot, run a
            full system upgrade (pacman -Syu), then reboot.
  boot      notify that the machine is up and report unit states.
  shutdown  notify that a shutdown or reboot has started (best effort).

Docker images are never updated here: Halogen and the other engines stay
pinned by digest. The ntfy topic is read from a private file in the inference
data directory (ignored by git), never from the repository.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'inference' / 'data'
TOPIC_FILE = DATA / 'ntfy-topic'
GATEWAY = 'http://127.0.0.1:18080'
IDLE_WAIT_SECONDS = 1800
IDLE_POLL_SECONDS = 60
UNITS = ('llama-swap.service', 'halo-metrics.service')


def log(message):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), message, flush=True)


def topic():
    try:
        value = TOPIC_FILE.read_text(encoding='utf8').strip()
    except OSError:
        return ''
    return value if re.fullmatch(r'[A-Za-z0-9_-]{8,80}', value) else ''


def notify(title, message, priority='default', tags=''):
    name = topic()
    if not name:
        log('ntfy topic missing; notification skipped: ' + title)
        return False
    request = urllib.request.Request(
        'https://ntfy.sh/' + name, data=message.encode('utf8'),
        headers={'Title': title, 'Priority': priority, 'Tags': tags}, method='POST')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20):
                return True
        except (urllib.error.URLError, OSError) as error:
            log(f'ntfy attempt {attempt + 1} failed: {error}')
            time.sleep(10)
    return False


def inflight_count():
    """Return the number of inference requests in flight, or None if unknown."""
    sys.path.insert(0, str(ROOT))
    try:
        import control
        return int(control.inflight())
    except (ImportError, OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return None


def wait_for_idle():
    deadline = time.time() + IDLE_WAIT_SECONDS
    while True:
        count = inflight_count()
        if count == 0:
            return True
        if time.time() >= deadline:
            return False
        log(f'inference busy ({count}); waiting')
        time.sleep(IDLE_POLL_SECONDS)


def sudo(*arguments):
    return subprocess.run(['sudo', '-n', *arguments], capture_output=True, text=True, timeout=7200)


def upgraded_packages(since):
    """Count packages pacman upgraded after the given timestamp."""
    count = 0
    try:
        for line in Path('/var/log/pacman.log').read_text(encoding='utf8', errors='replace').splitlines():
            if line.startswith('[') and '[ALPM] upgraded' in line and line[1:20] >= since:
                count += 1
    except OSError:
        pass
    return count


def update():
    started = time.strftime('%Y-%m-%dT%H:%M:%S')
    notify('Mantenimiento semanal', 'Empieza la actualización del sistema.', tags='gear')
    if not wait_for_idle():
        notify('Mantenimiento omitido', 'Hay peticiones de inferencia en curso desde hace 30 minutos. No se actualiza ni se reinicia esta semana.',
               priority='high', tags='warning')
        return 0
    snapshot = sudo('/usr/bin/snapper', '-c', 'root', 'create', '-d', 'weekly-maintenance')
    if snapshot.returncode != 0:
        notify('Mantenimiento cancelado', 'No se pudo crear el snapshot previo. No se actualiza. ' + snapshot.stderr[-300:],
               priority='urgent', tags='x')
        return 1
    result = sudo('/usr/bin/pacman', '-Syu', '--noconfirm')
    if result.returncode != 0:
        notify('Actualización fallida', 'pacman terminó con error y no se reinicia. Revisa el journal. ' + result.stderr[-300:],
               priority='urgent', tags='x')
        return 1
    count = upgraded_packages(started)
    notify('Actualización completada', f'Paquetes actualizados: {count}. Reinicio en curso.', tags='white_check_mark')
    time.sleep(10)
    reboot = sudo('/usr/bin/systemctl', 'reboot')
    if reboot.returncode != 0:
        notify('Reinicio fallido', 'La actualización terminó, pero el reinicio falló: ' + reboot.stderr[-300:],
               priority='urgent', tags='x')
        return 1
    return 0


def unit_states():
    states = {}
    for unit in UNITS:
        result = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True, timeout=10)
        states[unit] = result.stdout.strip() or 'unknown'
    return states


def boot():
    for _ in range(30):
        try:
            with urllib.request.urlopen(GATEWAY + '/health', timeout=5):
                break
        except OSError:
            time.sleep(10)
    uptime = Path('/proc/uptime').read_text().split()[0]
    lines = [f'Equipo encendido. Tiempo desde el arranque: {float(uptime):.0f} s.']
    lines += [f'{unit}: {state}' for unit, state in unit_states().items()]
    notify('Halo encendido', '\n'.join(lines), tags='rocket')
    return 0


def shutdown():
    notify('Halo apagándose', 'Apagado o reinicio iniciado.', priority='high', tags='power')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=('update', 'boot', 'shutdown', 'test'))
    arguments = parser.parse_args(argv)
    if arguments.action == 'test':
        return 0 if notify('Prueba ntfy', 'Notificaciones del Halo activas.', tags='test_tube') else 1
    return {'update': update, 'boot': boot, 'shutdown': shutdown}[arguments.action]()


if __name__ == '__main__':
    sys.exit(main())
