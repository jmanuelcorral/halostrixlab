import hashlib
import os
from pathlib import Path
import subprocess
import tarfile

from control import DATA, private_dir
from install import unit_quote, write_unit


RELEASES = [('node-release', 'node_exporter-1.12.1.linux-amd64', ['node_exporter']), ('prometheus-release', 'prometheus-3.14.0.linux-amd64', ['prometheus', 'promtool'])]


def main():
    os.umask(0o077)
    private_dir()
    binaries = DATA / 'bin'
    binaries.mkdir(mode=0o700, exist_ok=True)
    for directory, release, names in RELEASES:
        source = DATA / directory
        archive = source / (release + '.tar.gz')
        expected = dict((parts[1].lstrip('*'), parts[0]) for line in (source / 'sha256sums.txt').read_text().splitlines() if len(parts := line.split()) == 2)
        with archive.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if expected.get(archive.name) != actual:
            raise ValueError('Checksum mismatch: ' + archive.name)
        with tarfile.open(archive) as bundle:
            for name in names:
                member = bundle.getmember(release + '/' + name)
                if not member.isfile():
                    raise ValueError('Binary is not a regular archive member')
                target = binaries / name
                if target.is_symlink():
                    raise ValueError('Refusing binary symlink')
                with bundle.extractfile(member) as stream:
                    target.write_bytes(stream.read())
                target.chmod(0o700)
    metrics = DATA / 'prometheus'
    metrics.mkdir(mode=0o700, exist_ok=True)
    configuration = DATA / 'prometheus.yml'
    configuration.write_text('global:\n  scrape_interval: 5s\nscrape_configs:\n  - job_name: halo\n    static_configs:\n      - targets: ["127.0.0.1:19100"]\n  - job_name: node\n    static_configs:\n      - targets: ["127.0.0.1:19101"]\n')
    subprocess.run([str(binaries / 'promtool'), 'check', 'config', str(configuration)], check=True)
    units = Path.home() / '.config/systemd/user'
    units.mkdir(parents=True, exist_ok=True)
    common = '\nRestart=on-failure\nRestartSec=10\nNoNewPrivileges=yes\nUMask=0077\n\n[Install]\nWantedBy=default.target\n'
    write_unit(units, 'halo-node-exporter.service', '[Unit]\nDescription=Read-only host metrics\n[Service]\nExecStart=' + unit_quote(str(binaries / 'node_exporter')) + ' --web.listen-address=127.0.0.1:19101 --collector.disable-defaults --collector.cpu --collector.meminfo --collector.hwmon --collector.loadavg --collector.diskstats --collector.filesystem --collector.netdev --collector.pressure --collector.time --collector.uname' + common)
    write_unit(units, 'halo-prometheus.service', '[Unit]\nDescription=Private Halo metric history\n[Service]\nExecStart=' + unit_quote(str(binaries / 'prometheus')) + ' --web.listen-address=127.0.0.1:19090 --config.file=' + unit_quote(str(configuration)) + ' --storage.tsdb.path=' + unit_quote(str(metrics)) + ' --storage.tsdb.retention.time=15d --storage.tsdb.retention.size=2GB' + common)
    subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'Reload'], check=True)
    for name in ('halo-node-exporter.service', 'halo-prometheus.service'):
        subprocess.run(['busctl', '--user', 'call', 'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', 'StartUnit', 'ss', name, 'replace'], check=True)
    print('Verified binaries installed; Prometheus and node_exporter started on loopback only')


if __name__ == '__main__':
    main()
