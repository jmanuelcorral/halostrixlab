#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIND="${1:-127.0.0.1}"
if [[ "$#" -gt 1 ]]; then
    printf '%s\n' 'Usage: install-system.sh [PRIVATE_LAN_IPV4]' >&2
    exit 1
fi
/usr/bin/python3 - "$BIND" <<'PY'
import ipaddress
import sys
address = ipaddress.IPv4Address(sys.argv[1])
allowed = ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
if not any(address in ipaddress.IPv4Network(network) for network in allowed):
    raise SystemExit('Bind must be a loopback or private LAN IPv4 address')
PY
if [[ "${EUID}" -ne 0 ]]; then
    printf '%s\n' 'Run this reviewed installer as root from a local administrative terminal.' >&2
    exit 1
fi
for binary in cockpit-bridge cockpit-ws tmux; do
    if ! command -v "$binary" >/dev/null 2>&1 && [[ ! -x "/usr/lib/cockpit/${binary}" ]]; then
        printf 'Missing %s. Install cockpit and tmux using a full CachyOS update first.\n' "$binary" >&2
        exit 1
    fi
done
if [[ ! -f /etc/pam.d/cockpit ]]; then
    printf '%s\n' 'Missing Cockpit PAM policy. Repair the distribution package; do not create an ad-hoc password checker.' >&2
    exit 1
fi
if [[ -e /etc/systemd/system/cockpit.socket.d/halo-control.conf || -L /etc/systemd/system/cockpit.socket.d/halo-control.conf ]]; then
    printf '%s\n' 'Cockpit socket override already exists; preserve and review it manually.' >&2
    exit 1
fi
install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 "${ROOT}/maintenance.py" /usr/local/libexec/halo-maintenance
install -d -o root -g root -m 0755 /etc/systemd/system/cockpit.socket.d
printf '[Socket]\nListenStream=\nListenStream=%s:9090\nFreeBind=yes\n' "$BIND" > /etc/systemd/system/cockpit.socket.d/halo-control.conf
systemctl daemon-reload
systemctl enable --now cockpit.socket
printf 'Cockpit: https://%s:9090. Login uses the local Linux account through PAM.\n' "$BIND"
printf '%s\n' 'Verify the TLS certificate before entering a password. Root login is not required.'
printf '%s\n' 'Firewall unchanged: authorize TCP/9090 only from the trusted LAN if needed.'
printf '%s\n' 'Open Tools -> Halo Control after authenticating as the inference operator.'
