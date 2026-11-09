#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 0 ]]; then
    printf '%s\n' 'Uso: sudo bash workspaces/halo-control/repair-cockpit.sh' >&2
    exit 1
fi
if [[ "${EUID}" -ne 0 ]]; then
    printf '%s\n' 'Ejecuta este script con sudo en el Halo. No modifica el firewall ni reinicia el equipo.' >&2
    exit 1
fi
for binary in /usr/bin/python3 /usr/bin/systemctl /usr/bin/journalctl; do
    if [[ ! -x "$binary" ]]; then
        printf 'Falta el ejecutable requerido: %s\n' "$binary" >&2
        exit 1
    fi
done

diagnostics() {
    printf '\n%s\n' 'La reparación no se pudo completar. Diagnóstico de Cockpit:' >&2
    /usr/bin/systemctl status cockpit.socket cockpit.service --no-pager --full || true
    /usr/bin/journalctl -b -u cockpit.socket -u cockpit.service -n 40 --no-pager || true
    printf '%s\n' 'No se desactivó el firewall ni se modificaron las direcciones de escucha.' >&2
}
trap diagnostics ERR

if [[ "$(/usr/bin/systemctl show cockpit.socket --property=LoadState --value)" != 'loaded' ]]; then
    printf '%s\n' 'cockpit.socket no está instalado o no puede cargarse.' >&2
    exit 1
fi

/usr/bin/python3 - <<'PY'
import os
from pathlib import Path
import stat
import tempfile

parent = Path('/etc/systemd/system/cockpit.socket.d')
for directory in [*reversed(parent.parents), parent]:
    if not directory.exists() and not directory.is_symlink():
        if directory != parent:
            raise SystemExit('Falta un directorio del sistema; no se modifica nada')
        directory.mkdir(mode=0o755)
    metadata = directory.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise SystemExit('Directorio inseguro o enlace simbólico; revisar manualmente')

path = parent / 'halo-freebind.conf'
content = '[Socket]\nFreeBind=yes\n'
if path.exists() or path.is_symlink():
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise SystemExit('El drop-in existente no es seguro; no se reemplaza')
    if path.read_text() != content:
        raise SystemExit('El drop-in existente tiene otro contenido; se conserva para revisión')
    print('FreeBind ya está configurado; se conserva el archivo existente.')
else:
    descriptor, name = tempfile.mkstemp(prefix='.halo-freebind-', dir=parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    print('Creado el drop-in FreeBind sin cambiar IP, puerto ni otros ajustes.')
PY

/usr/bin/systemctl daemon-reload
if [[ "$(/usr/bin/systemctl show cockpit.socket --property=FreeBind --value)" != 'yes' ]]; then
    printf '%s\n' 'FreeBind no quedó activo; puede existir otro override que lo sustituya.' >&2
    diagnostics
    exit 1
fi
/usr/bin/systemctl enable cockpit.socket
/usr/bin/systemctl restart cockpit.socket
/usr/bin/systemctl is-active --quiet cockpit.socket
printf '\n%s\n' 'Cockpit vuelve a escuchar. Configuración efectiva:'
/usr/bin/systemctl show cockpit.socket --property=ActiveState --property=SubState --property=Listen --property=FreeBind
if command -v ufw >/dev/null 2>&1; then
    printf '\n%s\n' 'Estado del firewall (solo consulta):'
    ufw status verbose || printf '%s\n' 'No se pudo consultar UFW; sus reglas no se han modificado.'
fi
printf '\n%s\n' 'Abre la URL HTTPS habitual de Cockpit. No se han actualizado paquetes ni detenido motores IA.'
printf '%s\n' 'FreeBind resuelve el arranque antes de Wi-Fi; la IP configurada debe seguir asignándose al Halo.'
