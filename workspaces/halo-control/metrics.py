import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time

from control import DATA, private_dir


LATEST = {}
LATEST_LOCK = threading.Lock()


def number(path, scale=1):
    try:
        return float(Path(path).read_text().strip()) / scale
    except (OSError, ValueError):
        return None


def cpu_snapshot():
    result = {}
    for line in Path('/proc/stat').read_text().splitlines():
        parts = line.split()
        if not parts or not parts[0].startswith('cpu'):
            continue
        values = [int(value) for value in parts[1:9]]
        result[parts[0]] = (sum(values), values[3] + values[4])
    return result


def cpu_percent(previous, current):
    result = {}
    for key, (total, idle) in current.items():
        old_total, old_idle = previous.get(key, (total, idle))
        delta = total - old_total
        result[key] = round(100 * (1 - (idle - old_idle) / delta), 2) if delta > 0 else None
    return result


def counters():
    network = {}
    for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
        name, values = line.split(':', 1)
        fields = values.split()
        network[name.strip()] = {'rx': int(fields[0]), 'tx': int(fields[8]), 'errors': int(fields[2]) + int(fields[10])}
    disk = {}
    for line in Path('/proc/diskstats').read_text().splitlines():
        fields = line.split()
        if fields[2].startswith(('loop', 'ram')) or not (Path('/sys/block') / fields[2]).exists():
            continue
        disk[fields[2]] = {'read': int(fields[5]) * 512, 'write': int(fields[9]) * 512, 'busy_ms': int(fields[12])}
    return network, disk


def rate(previous, current, elapsed):
    output = {}
    for name, values in current.items():
        output[name] = {key: max(0, value - previous[name].get(key, value)) / elapsed if name in previous and elapsed > 0 else None for key, value in values.items()}
    return output


def sample(previous_cpu, previous_counters, elapsed):
    cpu = cpu_snapshot()
    network, disk = counters()
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        parts = line.split()
        memory[parts[0].rstrip(':')] = int(parts[1]) * 1024
    temperatures = []
    disk_temperatures = []
    for device in Path('/sys/class/hwmon').glob('hwmon*'):
        try:
            name = (device / 'name').read_text().strip()
        except OSError:
            continue
        for path in device.glob('temp*_input'):
            label_path = path.with_name(path.name.replace('_input', '_label'))
            label = label_path.read_text().strip() if label_path.exists() else path.stem
            temperatures.append({'sensor': name + ':' + label, 'celsius': number(path, 1000), 'critical': number(path.with_name(path.name.replace('_input', '_crit')), 1000)})
            if name in ('nvme', 'drivetemp'):
                disk_temperatures.append({'sensor': name + ':' + (device / 'device').resolve().name + ':' + label, 'celsius': number(path, 1000)})
    gpu = []
    for device in Path('/sys/class/drm').glob('card*/device'):
        if not (device / 'gpu_busy_percent').exists():
            continue
        info = {'device': device.parent.name, 'busy': number(device / 'gpu_busy_percent')}
        for name in ('gtt_total', 'gtt_used', 'vram_total', 'vram_used'):
            info[name] = number(device / ('mem_info_' + name))
        power = next(iter(device.glob('hwmon/hwmon*/power1_average')), None)
        info['watts'] = number(power, 1_000_000) if power else None
        gpu.append(info)
    pressure = {}
    for kind in ('cpu', 'memory', 'io'):
        try:
            lines = (Path('/proc/pressure') / kind).read_text().splitlines()
            pressure[kind] = {line.split()[0]: {key: float(value) for key, value in (part.split('=') for part in line.split()[1:])} for line in lines}
        except OSError:
            pressure[kind] = None
    usage = shutil.disk_usage(DATA)
    result = {'cpu': cpu_percent(previous_cpu, cpu), 'load': list(os.getloadavg()), 'memory': {'total': memory['MemTotal'], 'available': memory['MemAvailable'], 'used': memory['MemTotal'] - memory['MemAvailable'], 'cached': memory.get('Cached'), 'swap_used': memory['SwapTotal'] - memory['SwapFree'], 'swap_total': memory['SwapTotal']}, 'gpu': gpu, 'temperatures': temperatures, 'disk': {'total': usage.total, 'used': usage.used, 'free': usage.free}, 'network': rate(previous_counters[0], network, elapsed), 'io': rate(previous_counters[1], disk, elapsed), 'pressure': pressure, 'uptime': number('/proc/uptime')}
    result['disk_temperatures'] = disk_temperatures
    result['uptime'] = float(Path('/proc/uptime').read_text().split()[0])
    return result, cpu, (network, disk)


def prometheus_text(snapshot):
    if not snapshot:
        return '# No sample available\n'
    lines = [f'halo_sample_timestamp_seconds {snapshot["time"]}']
    for core, value in snapshot['cpu'].items():
        if value is not None:
            lines.append(f'halo_cpu_usage_percent{{core={json.dumps(core)}}} {value}')
    for key, value in snapshot['memory'].items():
        if value is not None:
            lines.append(f'halo_memory_{key}_bytes {value}')
    for device in snapshot['gpu']:
        for key, value in device.items():
            if key != 'device' and value is not None:
                suffix = 'percent' if key == 'busy' else ('watts' if key == 'watts' else 'bytes')
                lines.append(f'halo_gpu_{key}_{suffix}{{device={json.dumps(device["device"])}}} {value}')
    for sensor in snapshot['temperatures']:
        if sensor['celsius'] is not None:
            lines.append(f'halo_temperature_celsius{{sensor={json.dumps(sensor["sensor"])}}} {sensor["celsius"]}')
    return '\n'.join(lines) + '\n'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/metrics', '/health'):
            self.send_error(404)
            return
        with LATEST_LOCK:
            snapshot = dict(LATEST)
        body = (prometheus_text(snapshot) if self.path == '/metrics' else 'OK').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def collect(stop):
    private_dir()
    with contextlib.closing(sqlite3.connect(DATA / 'metrics.sqlite', timeout=10)) as connection, connection:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE IF NOT EXISTS samples (timestamp REAL PRIMARY KEY, payload TEXT)')
    previous_cpu = cpu_snapshot()
    previous_counters = counters()
    previous_time = time.monotonic()
    iteration = 0
    while not stop.wait(5):
        try:
            now = time.monotonic()
            payload, previous_cpu, previous_counters = sample(previous_cpu, previous_counters, now - previous_time)
            previous_time = now
            timestamp = time.time()
            with contextlib.closing(sqlite3.connect(DATA / 'metrics.sqlite', timeout=10)) as connection, connection:
                connection.execute('INSERT INTO samples VALUES (?,?)', (timestamp, json.dumps(payload)))
                if iteration % 120 == 0:
                    connection.execute('DELETE FROM samples WHERE timestamp<?', (timestamp - 15 * 86400,))
                    connection.execute('DELETE FROM samples WHERE timestamp < (SELECT timestamp FROM samples ORDER BY timestamp DESC LIMIT 1 OFFSET 259199)')
            with LATEST_LOCK:
                LATEST.clear()
                LATEST.update({'time': timestamp, **payload})
            iteration += 1
        except (OSError, ValueError, sqlite3.Error) as error:
            print('Metrics error:', error, flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    private_dir()
    if args.once:
        print(json.dumps(sample({}, ({}, {}), 1)[0]))
        return
    stop = threading.Event()
    thread = threading.Thread(target=collect, args=(stop,), daemon=True)
    thread.start()
    server = ThreadingHTTPServer(('127.0.0.1', 19100), Handler)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=10)


if __name__ == '__main__':
    main()
