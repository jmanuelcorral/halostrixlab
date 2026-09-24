import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from control import DATA, DEFAULT, INFERENCE, ROOT, config, private_dir


def unit_quote(value):
    if any(character in value for character in ('\n', '\r', '\x00')):
        raise ValueError('Invalid unit path')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def write_unit(directory, name, content):
    target = directory / name
    if target.is_symlink():
        raise ValueError('Refusing to replace a unit symlink: ' + name)
    if target.exists() and target.read_text() != content:
        raise ValueError('Unit already exists with different content; review manually: ' + name)
    target.write_text(content)


def main():
    parser = argparse.ArgumentParser(description='Install user Cockpit package and manual Halo units; no root changes')
    parser.add_argument('--start-metrics', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    private_dir()
    if not (ROOT / 'dist/index.html').exists():
        raise ValueError('Build frontend first with npm ci && npm run build')
    config_path = DATA / 'config.json'
    if not config_path.exists():
        with config_path.open('x') as stream:
            json.dump(DEFAULT, stream, indent=2)
        config_path.chmod(0o600)
    settings = config()
    package = Path.home() / '.local/share/cockpit/halo_control'
    package.parent.mkdir(parents=True, exist_ok=True)
    if package.is_symlink():
        raise ValueError('Refusing package symlink')
    if package.exists() and not (package / 'halo-owned').exists():
        raise ValueError('Package path is not owned by this installer')
    package.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'dist', package, dirs_exist_ok=True)
    (package / 'halo-owned').touch()
    (package / 'runtime.json').write_text(json.dumps({'workspace': str(ROOT)}))
    manifest = {'version':'0.1.0', 'requires': {'cockpit':'300'}, 'tools': {'index': {'label':'Halo Control','path':'index.html','order':1}}, 'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'"}
    (package / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    units = Path.home() / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    common = 'NoNewPrivileges=yes\nUMask=0077\nStandardOutput=journal\nStandardError=journal\n'
    write_unit(units, 'halo-metrics.service', '[Unit]\nDescription=Halo read-only hardware telemetry\n\n[Service]\nExecStart=/usr/bin/python3 ' + unit_quote(str(ROOT / 'metrics.py')) + '\n' + common + 'Restart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=default.target\n')
    write_unit(units, 'halo-comfyui.service', '[Unit]\nDescription=Manual ComfyUI with exclusive Halo GPU lease\n\n[Service]\nExecStart=/usr/bin/python3 ' + unit_quote(str(INFERENCE / 'comfyui.py')) + ' start --bind ' + settings['comfyui_bind'] + '\nExecStop=/usr/bin/python3 ' + unit_quote(str(INFERENCE / 'comfyui.py')) + ' stop\nTimeoutStopSec=100\nKillMode=mixed\nRestart=no\n' + common)
    write_unit(units, 'halo-unsloth.service', '[Unit]\nDescription=Existing Unsloth Studio with exclusive Halo GPU lease\n\n[Service]\nExecStart=/usr/bin/python3 ' + unit_quote(str(ROOT / 'unsloth.py')) + ' start\nExecStop=/usr/bin/python3 ' + unit_quote(str(ROOT / 'unsloth.py')) + ' stop\nTimeoutStopSec=100\nKillMode=mixed\nRestart=no\n' + common)
    write_unit(units, 'halo-llamafactory.service', '[Unit]\nDescription=Manual LlamaBoard with exclusive Halo GPU lease\n\n[Service]\nExecStart=/usr/bin/python3 ' + unit_quote(str(ROOT / 'llamafactory.py')) + ' start\nExecStop=/usr/bin/python3 ' + unit_quote(str(ROOT / 'llamafactory.py')) + ' stop\nTimeoutStopSec=100\nKillMode=mixed\nRestart=no\n' + common)
    subprocess.run(['busctl','--user','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','Reload'],check=True)
    if args.start_metrics:
        subprocess.run(['busctl','--user','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','StartUnit','ss','halo-metrics.service','replace'],check=True)
    print('Installed Cockpit user package:', package)
    print('Created manual ComfyUI and metrics units. Existing inference untouched.')
    print('Cockpit available:', bool(shutil.which('cockpit-bridge')))
    print('Metrics endpoint: http://127.0.0.1:19100/metrics')
    print('Edit private data/config.json for the actual gateway origin and optional SSH aliases.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
