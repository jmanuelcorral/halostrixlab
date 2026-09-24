import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

import laya_runtime
import manage
import service_options


def install(config):
    laya_runtime.deployment()
    config = laya_runtime.runtime.private_file(config)
    candidate = laya_runtime.integrate(json.loads(config.read_text()))
    temporary = config.with_name('.laya-validate-' + uuid.uuid4().hex + '.yaml')
    try:
        laya_runtime.runtime.write_private(temporary, json.dumps(candidate, indent=2) + '\n')
        subprocess.run([str(laya_runtime.runtime.DATA / 'bin/llama-swap'), '-config', str(temporary), '-validate'], env=manage.key_environment(), check=True)
        with service_options.lease('gateway'):
            result = subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'GetUnit', 's', 'llama-swap.service'], capture_output=True, text=True, check=True)
            unit_path = result.stdout.strip().split('"')[1]
            state = subprocess.run(['busctl', '--user', 'get-property', 'org.freedesktop.systemd1', unit_path, 'org.freedesktop.systemd1.Unit', 'ActiveState'], capture_output=True, text=True, check=True).stdout.strip()
            if state not in ('s "inactive"', 's "failed"'):
                raise ValueError('Stop the existing gateway before installing Laya')
            current = laya_runtime.runtime.private_file(config).read_text()
            if laya_runtime.integrate(json.loads(current)) != candidate:
                raise ValueError('Gateway configuration changed during validation')
            if json.loads(current) != candidate:
                laya_runtime.runtime.write_private(config.with_name(config.name + '.before-laya-' + uuid.uuid4().hex), current)
                temporary.replace(config)
    finally:
        temporary.unlink(missing_ok=True)
    print('Laya added to the existing gateway; no additional proxy or unit installed. Start the original gateway to apply.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True, help='Actual existing gateway configuration, not a historical profile')
    install(parser.parse_args().config)
