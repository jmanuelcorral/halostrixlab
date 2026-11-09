#!/usr/bin/python3
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path('/run/halo-control')
SOCKET = ROOT / 'maintenance.sock'
HELPER = '/usr/local/libexec/halo-maintenance'


def require_root():
    if os.geteuid() != 0:
        raise PermissionError('Administrator authorization is required')
    installed = Path(HELPER)
    if installed.is_symlink() or installed.stat().st_uid != 0 or installed.stat().st_mode & 0o022:
        raise PermissionError('Maintenance helper must be root-owned and not group/world writable')
    if ROOT.is_symlink():
        raise PermissionError('Unsafe maintenance directory')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    if ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o077:
        raise PermissionError('Unsafe maintenance permissions')


def idle():
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process / 'comm').read_text().strip()
            command = (process / 'cmdline').read_bytes()
        except (OSError, PermissionError):
            continue
        if name in {'llama-swap', 'flash_serve', 'llama-server', 'vllm'} or b'/opt/ComfyUI/main.py' in command:
            raise RuntimeError('Stop and drain AI services before maintenance')
    if Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Package database is locked; never remove the lock automatically')
    if shutil.disk_usage('/').free < 10 * 1024**3:
        raise RuntimeError('At least 10 GiB free is required before maintenance')


def tmux(*arguments, check=True):
    return subprocess.run(['/usr/bin/tmux', '-S', str(SOCKET), *arguments], check=check)


def update_worker():
    with (ROOT / 'operation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        idle()
        record = {'started': time.time(), 'state': 'running', 'actor': os.environ.get('PKEXEC_UID', 'root')}
        Path('/var/log/halo-control').mkdir(mode=0o700, exist_ok=True)
        report = Path('/var/log/halo-control/last-update.json')
        report.write_text(json.dumps(record))
        print('Full CachyOS update. Review pacman prompts; no automatic conflict acceptance.', flush=True)
        result = subprocess.run(['/usr/bin/pacman', '-Syu'])
        record.update(state='success' if result.returncode == 0 else 'failed', exit_code=result.returncode, ended=time.time())
        report.write_text(json.dumps(record))
        print('Update finished with exit code', result.returncode, flush=True)
        print('Review kernel/firmware changes before reboot. Press Enter to close.', flush=True)
        input()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('update', 'update-worker', 'reboot', 'report'))
    args = parser.parse_args()
    require_root()
    if args.action == 'report':
        path = Path('/var/log/halo-control/last-update.json')
        print(path.read_text() if path.exists() else '{}')
        return
    if args.action == 'update-worker':
        update_worker()
        return
    if args.action == 'reboot':
        idle()
        if tmux('has-session', '-t', 'update', check=False).returncode == 0:
            raise RuntimeError('Close the update session before rebooting')
        with (ROOT / 'operation.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            subprocess.run(['/usr/bin/systemctl', 'reboot'], check=True)
        return
    if not Path('/usr/bin/tmux').is_file():
        raise RuntimeError('Install tmux to provide a reconnectable maintenance terminal')
    with (ROOT / 'launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if tmux('has-session', '-t', 'update', check=False).returncode:
            idle()
            tmux('new-session', '-d', '-s', 'update', HELPER + ' update-worker')
    os.execv('/usr/bin/tmux', ['/usr/bin/tmux', '-S', str(SOCKET), 'attach-session', '-t', 'update'])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
