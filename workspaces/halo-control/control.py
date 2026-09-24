import argparse
import contextlib
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import unsloth
import llamafactory


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
INFERENCE = ROOT.parent / "inference"
UNITS = {"gateway": "llama-swap.service", "comfyui": "halo-comfyui.service", "metrics": "halo-metrics.service", "unsloth": "halo-unsloth.service", "llamafactory": "halo-llamafactory.service"}
ACTIONS = {"laya-start", "laya-stop", "gateway-start", "gateway-stop", "gateway-restart", "halogen-load", "halogen-unload", "comfyui-start", "comfyui-stop", "switch-text", "switch-images", "check-updates", "check-images", "unsloth-start", "unsloth-stop", "switch-studio", "llamafactory-start", "llamafactory-stop", "switch-llamafactory", "analyze-storage", "prepare-reboot"}
DEFAULT = {"gateway_url": "http://127.0.0.1:18080", "comfyui_bind": "127.0.0.1", "model": "flash-halogen", "admin_key_file": "", "drain_timeout": 120, "ssh_hosts": []}


def private_dir():
    if DATA.is_symlink():
        raise ValueError("Private data cannot be a symlink")
    DATA.mkdir(mode=0o700, exist_ok=True)
    metadata = DATA.stat()
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError("Private data must belong to this user with mode 0700")


def config():
    private_dir()
    path = DATA / "config.json"
    if not path.exists():
        return dict(DEFAULT)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError("Configuration requires current owner, regular file and mode 0600")
    value = json.loads(path.read_text())
    if set(value) - set(DEFAULT):
        raise ValueError("Unknown configuration field")
    result = dict(DEFAULT, **value)
    address = ipaddress.IPv4Address(result["comfyui_bind"])
    if not (address.is_loopback or any(address in ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))):
        raise ValueError("ComfyUI bind must be loopback or private IPv4")
    url = urllib.parse.urlsplit(result["gateway_url"])
    if url.scheme not in ("http", "https") or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError("Invalid gateway origin")
    host = ipaddress.ip_address(url.hostname)
    if not host.is_loopback and not host.is_private:
        raise ValueError("Gateway must be local/private")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,64}", result["model"]):
        raise ValueError("Invalid model ID")
    if type(result["drain_timeout"]) is not int or not 10 <= result["drain_timeout"] <= 600:
        raise ValueError("Drain timeout must be 10..600 seconds")
    for target in result["ssh_hosts"]:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", target):
            raise ValueError("Only configured SSH aliases are allowed")
    return result


def run(arguments, timeout=20, check=True):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Command failed")[-2000:])
    return result


@contextlib.contextmanager
def database():
    private_dir()
    connection = sqlite3.connect(DATA / "control.sqlite", timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, action TEXT, state TEXT, created REAL, updated REAL, message TEXT, actor TEXT)")
    connection.execute("CREATE TABLE IF NOT EXISTS cache (name TEXT PRIMARY KEY, updated REAL, payload TEXT)")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def save_cache(name, payload):
    with database() as connection:
        connection.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (name, time.time(), json.dumps(payload)))


def cached(name):
    with database() as connection:
        row = connection.execute("SELECT * FROM cache WHERE name=?", (name,)).fetchone()
    return {"updated": row["updated"], "data": json.loads(row["payload"])} if row else None


def unit_state(kind):
    result = run(["systemctl", "--user", "show", UNITS[kind], "--property=ActiveState", "--value"], check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def unit(action, kind):
    if kind not in UNITS or action not in ("start", "stop", "restart"):
        raise ValueError("Unsupported unit operation")
    run(["systemctl", "--user", action, UNITS[kind]], timeout=150)


def http(path, payload=None, comfy=False, timeout=10):
    settings = config()
    base = "http://" + settings["comfyui_bind"] + ":8188" if comfy else settings["gateway_url"]
    headers = {}
    if settings["admin_key_file"] and not comfy:
        key_path = Path(settings["admin_key_file"])
        if key_path.is_symlink() or key_path.stat().st_uid != os.getuid() or key_path.stat().st_mode & 0o077:
            raise ValueError("Unsafe API key file")
        headers["Authorization"] = "Bearer " + key_path.read_text().strip()
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        body = response.read(2_000_000)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body.decode()


def inflight():
    settings = config()
    headers = {"Accept": "text/event-stream"}
    if settings["admin_key_file"]:
        path = Path(settings["admin_key_file"])
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            raise ValueError("Unsafe API key file")
        headers["Authorization"] = "Bearer " + path.read_text().strip()
    request = urllib.request.Request(settings["gateway_url"] + "/api/events", headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 10
    with opener.open(request, timeout=10) as response:
        for count in range(300):
            if time.monotonic() > deadline:
                break
            line = response.readline(1_000_000).decode()
            if not line:
                break
            if not line.startswith("data:"):
                continue
            envelope = json.loads(line[5:])
            if envelope.get("type") == "inflight":
                event = envelope["data"]
                if isinstance(event, str):
                    event = json.loads(event)
                if event.get("operation") == "snapshot":
                    return len(event.get("requests") or [])
    raise RuntimeError("Unable to verify gateway active requests; refusing to stop")


def containers():
    result = run(["docker", "ps", "--filter", f"label=io.halostrix.inference={INFERENCE}", "--format", "{{.Names}}"], check=False)
    return result.stdout.splitlines() if result.returncode == 0 else None


def status():
    settings = config()
    names = containers()
    services = {kind: unit_state(kind) for kind in UNITS}
    state = {"services": services, "containers": names, "halogen": "unknown" if names is None else ("loaded" if "halostrix-flash-halogen" in names else "unloaded"), "comfyui_url": "http://" + settings["comfyui_bind"] + ":8188", "ssh_hosts": settings["ssh_hosts"], "gateway_health": False, "comfyui_health": False, "errors": []}
    state["gateway_ui_url"] = settings["gateway_url"] + "/ui/"
    state["unsloth"] = unsloth.status()
    state["llamafactory"] = llamafactory.status()
    import laya_control
    state['laya'] = laya_control.status(sys.modules[__name__])
    if services["gateway"] == "active":
        try:
            http("/health", timeout=3)
            state["gateway_health"] = True
        except Exception:
            state["errors"].append("Gateway active but health check failed")
    if services["comfyui"] == "active":
        try:
            state["queue"] = http("/queue", comfy=True, timeout=3)
            state["comfyui_health"] = True
        except Exception:
            state["errors"].append("ComfyUI active but health check failed")
    with database() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 30").fetchall()
    state["jobs"] = [dict(row) for row in rows]
    for job in state["jobs"]:
        if job["state"] in ("queued", "running") and time.time() - job["updated"] > 1800:
            job["state"] = "unknown"
            job["message"] = "Operation stale; inspect journal before retrying"
    state["updates"] = cached("updates")
    state["images"] = cached("images")
    state["storage"] = cached("storage")
    import reboot
    state['reboot'] = reboot.pending(sys.modules[__name__])
    state["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    state["maintenance_available"] = Path("/usr/local/libexec/halo-maintenance").is_file()
    return state


@contextlib.contextmanager
def operation_lock(allow_reboot=False):
    private_dir()
    descriptor = os.open(DATA / "operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another operation is active") from error
        if not allow_reboot:
            import reboot
            if reboot.pending(sys.modules[__name__]):
                raise ValueError('Reinicio en preparación; operaciones bloqueadas temporalmente')
        yield


def comfy_stop():
    names = containers()
    if names is None:
        raise RuntimeError("Cannot verify containers")
    if "halostrix-comfyui-manual" not in names:
        unit("stop", "comfyui")
        return
    queue = http("/queue", comfy=True)
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise RuntimeError("ComfyUI has active/pending jobs; wait before switching")
    unit("stop", "comfyui")
    run([sys.executable, str(INFERENCE / "comfyui.py"), "stop"], timeout=90)
    remaining = containers()
    if remaining is None or "halostrix-comfyui-manual" in remaining:
        raise RuntimeError("Cannot confirm ComfyUI stopped")


def gateway_stop():
    if unit_state("gateway") in ("inactive", "failed"):
        return
    deadline = time.monotonic() + config()["drain_timeout"]
    while inflight():
        if time.monotonic() >= deadline:
            raise RuntimeError("Gateway still busy; nothing was stopped")
        time.sleep(2)
    unit("stop", "gateway")
    if unit_state("gateway") not in ("inactive", "failed"):
        raise RuntimeError("Gateway did not stop")


def ready(comfy=False):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            http("/queue" if comfy else "/health", comfy=comfy, timeout=3)
            return
        except (OSError, ValueError):
            time.sleep(2)
    raise RuntimeError("Readiness timeout; inspect logs")


def execute(action):
    if action not in ACTIONS:
        raise ValueError("Action is not allowed")
    if action == 'prepare-reboot':
        import reboot
        reboot.prepare(sys.modules[__name__])
        return
    if action == 'analyze-storage':
        import storage
        save_cache('storage', storage.analyze(DATA))
        return
    if action == "check-updates":
        result = run(["checkupdates", "--nocolor"], timeout=300, check=False)
        payload = {"ok": result.returncode in (0, 2), "packages": [], "error": ""}
        if payload["ok"]:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[2] == "->":
                    payload["packages"].append({"name": parts[0], "from": parts[1], "to": parts[3]})
        else:
            payload["error"] = result.stderr[-2000:] or "checkupdates failed"
        save_cache("updates", payload)
        if not payload["ok"]:
            raise RuntimeError(payload["error"])
        return
    if action == "check-images":
        images = {}
        for tag in ("kyuz0/amd-strix-halo-comfyui:latest", "ghcr.io/peonist-ai/halogen-flash-server:latest"):
            local = run(["docker", "image", "inspect", tag, "--format", "{{json .RepoDigests}}"], check=False)
            remote = run(["docker", "manifest", "inspect", "--verbose", tag], timeout=90, check=False)
            images[tag] = {"local": json.loads(local.stdout) if local.returncode == 0 else [], "remote": json.loads(remote.stdout) if remote.returncode == 0 else None, "error": remote.stderr[-1000:] if remote.returncode else "", "note": "Manifest inspection only; no pull or activation"}
        save_cache("images", images)
        return
    if action in ('laya-start', 'laya-stop'):
        import laya_control
        laya_control.execute(sys.modules[__name__], action)
        return
    training_services = {"unsloth": unsloth, "llamafactory": llamafactory}
    for name, service in training_services.items():
        if action == name + "-stop":
            unit("stop", name)
            service.stop()
            service.require_stopped()
            return
    if action in ("gateway-start", "gateway-restart", "halogen-load", "comfyui-start", "switch-text", "switch-images", "unsloth-start", "switch-studio", "llamafactory-start"):
        unsloth.require_stopped()
        llamafactory.require_stopped()
    target = "unsloth" if action in ("unsloth-start", "switch-studio") else "llamafactory" if action in ("llamafactory-start", "switch-llamafactory") else None
    if target:
        service = training_services[target]
        studio = service.status()
        if not studio["available"]:
            raise RuntimeError(studio["error"])
        if action in ("switch-studio", "switch-llamafactory"):
            comfy_stop()
            gateway_stop()
        if action == 'switch-llamafactory':
            unit('stop', 'unsloth')
            unsloth.stop()
            unsloth.require_stopped()
            if unit_state('unsloth') not in ('inactive', 'failed'):
                raise RuntimeError('No se confirmó la parada de Studio')
            if studio.get('state') == 'running':
                if studio['health']:
                    return
                raise RuntimeError('LlamaBoard ya está activo pero su interfaz no responde; revisa los logs')
            llamafactory.require_stopped()
        if unit_state("gateway") not in ("inactive", "failed"):
            raise RuntimeError("Gateway active; use the explicit switch action")
        names = containers()
        if names is None or names:
            raise RuntimeError("GPU container active or status unknown")
        unit("start", target)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if service.status()["health"]:
                return
            if unit_state(target) in ("failed", "inactive"):
                raise RuntimeError("Training UI exited during startup; inspect logs")
            time.sleep(3)
        raise RuntimeError("Training UI readiness timeout; inspect logs")
    if action in ("comfyui-stop", "switch-text"):
        comfy_stop()
    if action in ("gateway-stop", "gateway-restart", "switch-images"):
        gateway_stop()
    if action in ("gateway-start", "gateway-restart", "switch-text", "halogen-load"):
        names = containers()
        if names is None:
            raise RuntimeError("Cannot verify GPU container ownership")
        if "halostrix-comfyui-manual" in names:
            raise RuntimeError("ComfyUI owns the GPU; use switch-text")
        unit("start", "gateway")
        ready()
    if action in ("halogen-load", "switch-text"):
        result = http("/v1/chat/completions", {"model": config()["model"], "messages": [{"role": "user", "content": "Reply OK."}], "max_tokens": 8, "stream": False}, timeout=1200)
        if not isinstance(result, dict) or not result.get("choices"):
            raise RuntimeError("Halogen inference probe failed")
    if action == "halogen-unload":
        if inflight():
            raise RuntimeError("Gateway busy; refusing unload")
        http("/api/models/unload/" + urllib.parse.quote(config()["model"], safe=""), {})
    if action in ("comfyui-start", "switch-images"):
        if unit_state("gateway") not in ("inactive", "failed"):
            raise RuntimeError("Stop gateway or use switch-images first")
        unit("start", "comfyui")
        ready(comfy=True)


def update_job(identifier, state, message):
    with database() as connection:
        connection.execute("UPDATE jobs SET state=?,updated=?,message=? WHERE id=?", (state, time.time(), message[:2000], identifier))


def submit(action):
    if action not in ACTIONS:
        raise ValueError("Unsupported action")
    identifier = uuid.uuid4().hex
    with operation_lock(), database() as connection:
        active = connection.execute("SELECT id FROM jobs WHERE state IN ('queued','running') AND updated>?", (time.time() - 1800,)).fetchone()
        if active:
            raise ValueError("An operation is already pending")
        connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (identifier, action, "queued", time.time(), time.time(), "", str(os.getuid())))
    try:
        run(["systemd-run", "--user", "--collect", "--unit=halo-job-" + identifier, "--property=RuntimeMaxSec=1500", sys.executable, str(ROOT / "control.py"), "worker", identifier], timeout=15)
    except Exception as error:
        update_job(identifier, "failed", str(error))
        raise
    return {"job": identifier}


def worker(identifier):
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("Invalid job")
    with database() as connection:
        row = connection.execute("SELECT action FROM jobs WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ValueError("Unknown job")
    try:
        with operation_lock():
            update_job(identifier, "running", "Operation started")
            execute(row["action"])
            update_job(identifier, "success", "Completed")
    except Exception as error:
        update_job(identifier, "failed", str(error))
        raise


def history(seconds):
    if seconds not in (900, 3600, 86400, 604800):
        raise ValueError("Unsupported range")
    path = DATA / "metrics.sqlite"
    if not path.exists():
        return []
    with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        bucket = max(5, seconds // 850)
        rows = connection.execute("SELECT timestamp,payload FROM samples WHERE timestamp IN (SELECT MAX(timestamp) FROM samples WHERE timestamp>? GROUP BY CAST(timestamp / ? AS INTEGER)) ORDER BY timestamp", (time.time() - seconds, bucket)).fetchall()
    return [{"time": stamp, **json.loads(payload)} for stamp, payload in rows]


def logs(kind):
    if kind not in UNITS and kind != "jobs":
        raise ValueError("Unknown log source")
    target = "halo-job-*" if kind == "jobs" else UNITS[kind]
    output = run(["journalctl", "--user", "-u", target, "-n", "250", "--no-pager", "-o", "short-iso"], timeout=10).stdout
    return re.sub(r"(?i)(bearer\s+|api[_-]?key[=: ]+)[^\s]+", r"\1[REDACTED]", output)[-80000:]


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "submit", "worker", "history", "logs", "engine-detail", "engine-reveal", "engine-save", "engine-logs", "reboot-verify", "reboot-release"))
    parser.add_argument("argument", nargs="?")
    args = parser.parse_args()
    if args.command in ('reboot-verify', 'reboot-release'):
        import reboot
        handler = reboot.verify if args.command == 'reboot-verify' else reboot.release
        output = handler(sys.modules[__name__], args.argument)
    elif args.command.startswith('engine-'):
        import engine_details
        module = sys.modules[__name__]
        if args.command == 'engine-save':
            text = sys.stdin.read(16385)
            if len(text) > 16384:
                raise ValueError('Settings payload too large')
            output = engine_details.save(module, args.argument, json.loads(text))
        elif args.command == 'engine-logs':
            output = engine_details.logs(module, args.argument)
        else:
            output = engine_details.detail(module, args.argument, reveal=args.command == 'engine-reveal')
    elif args.command == "status":
        output = status()
    elif args.command == "submit":
        output = submit(args.argument)
    elif args.command == "worker":
        worker(args.argument)
        output = {"ok": True}
    elif args.command == "history":
        output = history(int(args.argument or 900))
    else:
        output = {"text": logs(args.argument)}
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
