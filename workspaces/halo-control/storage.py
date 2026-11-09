import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import json


def roots():
    candidates = [('Archivos del usuario', Path.home()), ('Workspaces IA del usuario (incluidos arriba)', Path.home() / 'ai'), ('Inferencia y modelos (incluidos en el workspace)', Path(__file__).resolve().parent.parent / 'inference/data'), ('Caché del usuario (incluida arriba)', Path.home() / '.cache'), ('Sistema y aplicaciones', Path('/usr')), ('Datos y cachés del sistema', Path('/var')), ('Aplicaciones adicionales', Path('/opt'))]
    return [(label, path) for label, path in candidates if path.exists()]


def category(path):
    parts = {part.lower() for part in Path(path).parts}
    if parts & {'models', 'hf-cache', 'huggingface', 'checkpoints', 'diffusion_models', 'text_encoders'}:
        return 'Modelos y caché de Hugging Face'
    if parts & {'docker', 'containerd', 'containers'}:
        return 'Contenedores e imágenes'
    if parts & {'outputs', 'output', 'saves', 'datasets'}:
        return 'Resultados, checkpoints o datasets'
    if parts & {'node_modules', '.venv', '.venv-site', 'venv', 'site-packages'}:
        return 'Dependencias y entornos de desarrollo'
    if parts & {'.cache', 'cache', 'pkg'}:
        return 'Cachés y paquetes descargados'
    if parts & {'downloads', 'descargas'}:
        return 'Descargas'
    if parts & {'gitrepos', 'projects', 'workspaces', 'ai'}:
        return 'Proyectos y herramientas de IA'
    if parts & {'log', 'logs', 'journal'}:
        return 'Registros'
    if str(path).startswith('/usr/'):
        return 'Sistema y aplicaciones instaladas'
    return 'Otros archivos (clasificación por ruta)'


def parse_usage(text, root):
    rows = []
    for record in text.split('\0'):
        if not record:
            continue
        size, separator, name = record.partition('\t')
        if not separator or not size.isdecimal():
            continue
        path = Path(name)
        if not path.is_absolute() or not path.is_relative_to(root):
            continue
        rows.append({'path': str(path), 'bytes': int(size), 'depth': len(path.relative_to(root).parts), 'category': category(path)})
    return rows


def scan_root(label, root, data, timeout=120):
    if root.is_symlink() or not root.is_dir():
        return {'label': label, 'path': str(root), 'partial': True, 'reason': 'Ruta no disponible o enlace simbólico; no se sigue', 'bytes': None, 'directories': []}
    command = ['du', '-x', '-B1', '--null', '--max-depth=3', '--', str(root)]
    if shutil.which('ionice'):
        command = ['ionice', '-c', '3', *command]
    if shutil.which('nice'):
        command = ['nice', '-n', '15', *command]
    reason = ''
    with tempfile.TemporaryFile(dir=data) as output:
        try:
            result = subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            if result.returncode:
                reason = 'Lectura parcial: permisos, archivos cambiantes o error de du'
        except subprocess.TimeoutExpired:
            reason = 'Tiempo límite alcanzado; resultado parcial'
        except OSError:
            reason = 'No se pudo ejecutar du; resultado no disponible'
        output.seek(0)
        raw = output.read(4_000_001)
    if len(raw) > 4_000_000:
        raw = raw[:4_000_000].rsplit(b'\0', 1)[0]
        reason = 'Salida limitada; resultado parcial'
    rows = parse_usage(raw.decode(errors='replace'), root)
    total = next((row['bytes'] for row in rows if row['depth'] == 0), None)
    directories = sorted((row for row in rows if row['depth'] > 0), key=lambda row: row['bytes'], reverse=True)[:30]
    return {'label': label, 'path': str(root), 'bytes': total, 'partial': bool(reason) or total is None, 'reason': reason or ('Sin total disponible' if total is None else ''), 'directories': directories}


def docker_usage():
    try:
        result = subprocess.run(['docker', 'system', 'df', '--format', '{{json .}}'], capture_output=True, text=True, timeout=45, check=False)
        if result.returncode:
            raise ValueError('Docker unavailable')
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        allowed = ('Type', 'TotalCount', 'Active', 'Size', 'Reclaimable')
        return {'available': True, 'rows': [{key: row.get(key) for key in allowed} for row in rows]}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'available': False, 'rows': []}


def analyze(data):
    started = time.time()
    filesystem = shutil.disk_usage(data)
    root_usage = [scan_root(label, path, data) for label, path in roots()]
    docker = docker_usage()
    return {'started': started, 'finished': time.time(), 'filesystem': {'path': str(data), 'total': filesystem.total, 'used': filesystem.used, 'free': filesystem.free}, 'roots': root_usage, 'docker': docker, 'method': 'du: bloques asignados, sin seguir enlaces ni cruzar otros sistemas de archivos; profundidad 3. Las carpetas incluyen sus descendientes: no sumar filas. Reflinks, snapshots, metadatos y archivos borrados pero abiertos pueden diferir de la ocupación real. Docker es un inventario separado con capas compartidas, no sumarlo a du. No se leen contenidos ni se borra nada.'}
