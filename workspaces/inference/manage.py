import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shlex
import subprocess
import sys
import tarfile

from runtime import DATA, ROOT, docker, load_profiles, private_directory, private_file, write_private


SWAP_VERSION = "v255"
SWAP_ARCHIVE = "llama-swap_255_linux_amd64.tar.gz"
SWAP_SHA256 = "84aa0df0cf3e302a8591e39de347f64c0c7dce1c3a948df68723a82e1fb4f1d4"
COCKPIT_REVISION = "6959d068c020f3f33bfb8ef743e7ba44a6390dda"


def install():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Pinned installer currently supports Linux x86_64 only")
    private_directory(DATA)
    binaries = private_directory(DATA / "bin")
    target = binaries / "llama-swap"
    if not target.exists():
        downloads = private_directory(DATA / "downloads")
        archive = downloads / SWAP_ARCHIVE
        if not archive.exists():
            subprocess.run(["gh", "release", "download", SWAP_VERSION, "--repo",
                            "mostlygeek/llama-swap", "--pattern", SWAP_ARCHIVE,
                            "--dir", str(downloads)], check=True)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SWAP_SHA256:
            raise ValueError("llama-swap release checksum mismatch; archive retained for inspection")
        with tarfile.open(archive) as bundle:
            members = [member for member in bundle.getmembers()
                       if Path(member.name).name == "llama-swap" and member.isfile()]
            if len(members) != 1:
                raise ValueError("Expected exactly one release binary")
            stream = bundle.extractfile(members[0])
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
            with os.fdopen(descriptor, "wb") as output:
                output.write(stream.read())
    subprocess.run([str(target), "-version"], check=True)
    environment = DATA / "cockpit-venv"
    python = environment / "bin/python"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    source = DATA / "cockpit-source"
    if not source.exists():
        subprocess.run(["gh", "repo", "clone", "kyuz0/ai-toolbox-cockpit", str(source),
                        "--", "--no-checkout"], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", COCKPIT_REVISION], check=True)
    subprocess.run([str(python), "-m", "pip", "install", str(source)], check=True)
    subprocess.run([str(python), "-c", "from ai_toolbox_cockpit.main import cli_main; print('Cockpit import OK')"], check=True)
    with (DATA / "cockpit-packages.txt").open("w") as manifest:
        subprocess.run([str(python), "-m", "pip", "freeze", "--all"], check=True, stdout=manifest)
    print("Installed isolated tools; no service, image or model started")


def initialize():
    private_directory(DATA)
    config = DATA / "profiles.json"
    if not config.exists():
        write_private(config, (ROOT / "profiles.example.json").read_text())
    for name in ("admin.key", "client.key"):
        path = DATA / name
        if not path.exists():
            write_private(path, secrets.token_urlsafe(48) + "\n")
        private_file(path)
    print("Private profiles and separate keys ready; no credentials printed")


def key_environment():
    environment = os.environ.copy()
    for name, variable in (("admin.key", "HALOSTRIX_ADMIN_KEY"), ("client.key", "HALOSTRIX_CLIENT_KEY")):
        value = private_file(DATA / name).read_text().strip()
        if len(value) < 32:
            raise ValueError("API keys must be at least 32 characters")
        environment[variable] = value
    return environment


def render(config):
    profiles = load_profiles(config)
    models = {}
    for index, (name, profile) in enumerate(profiles.items()):
        port = 18100 + index
        command = [sys.executable, str(ROOT / "runtime.py")]
        common = [name, "--config", str(config.resolve())]
        models[name] = {
            "cmd": shlex.join([*command, "start", *common, "--port", str(port)]),
            "cmdStop": shlex.join([*command, "stop", *common]),
            "proxy": f"http://127.0.0.1:{port}",
            "checkEndpoint": "/health", "useModelName": profile["upstream_model"],
            "ttl": 0, "unloadTimeout": 90, "concurrencyLimit": 1,
            "sendLoadingState": False,
            "capabilities": {"context": profile["context"]},
            "metadata": {"context_length": profile["context"],
                         "max_output_tokens": profile["output"]},
        }
    return {
        "healthCheckTimeout": 1200, "unloadTimeout": 90,
        "globalConcurrencyLimit": 1, "sendLoadingState": False,
        "apiKeys": ["${env.HALOSTRIX_ADMIN_KEY}", "${env.HALOSTRIX_CLIENT_KEY}"],
        "models": models,
        "routing": {"router": {"use": "group", "settings": {"groups": {
            "gpu": {"swap": True, "exclusive": True, "members": list(models)}
        }}}},
    }


def generate(config):
    result = render(config)
    private_directory(DATA)
    destination = DATA / "llama-swap.yaml"
    content = json.dumps(result, indent=2) + "\n"
    if destination.exists():
        private_file(destination)
        destination.write_text(content)
    else:
        write_private(destination, content)
    subprocess.run([str(DATA / "bin/llama-swap"), "-config", str(destination), "-validate"],
                   env=key_environment(), check=True)
    print("Gateway configuration validated; no models started")


def gateway():
    config = DATA / "llama-swap.yaml"
    private_file(config)
    os.chdir(DATA)
    os.execve(DATA / "bin/llama-swap", [str(DATA / "bin/llama-swap"), "-config", str(config),
                                      "-listen", "127.0.0.1:18080"], key_environment())


def status():
    print(docker(["container", "ls", "-a", "--filter", f"label=io.halostrix.inference={ROOT}",
                  "--format", "{{.Names}} {{.Status}}"]).stdout, end="")


def unload():
    import urllib.request
    key = key_environment()["HALOSTRIX_ADMIN_KEY"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request("http://127.0.0.1:18080/api/models/unload", data=b"",
                                     headers={"Authorization": "Bearer " + key}, method="POST")
    with opener.open(request, timeout=120) as response:
        print("Unload request:", response.status)


def cockpit():
    import fcntl
    private_directory(DATA)
    with (DATA / "gpu.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Unload the managed model before entering Cockpit") from error
        active = docker(["container", "ls", "--filter", f"label=io.halostrix.inference={ROOT}",
                         "--format", "{{.ID}}"])
        if active.stdout.strip():
            raise ValueError("Managed runtime is still active")
        environment = os.environ.copy()
        environment["DBX_CONTAINER_MANAGER"] = "docker"
        environment["XDG_CONFIG_HOME"] = str(private_directory(DATA / "cockpit-config"))
        return subprocess.run([str(DATA / "cockpit-venv/bin/python"), str(ROOT / "cockpit_launch.py")],
                              env=environment, pass_fds=(lock.fileno(),)).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["install", "init", "generate", "gateway", "cockpit", "status", "unload"])
    parser.add_argument("--config", type=Path, default=DATA / "profiles.json")
    arguments = parser.parse_args()
    if arguments.action == "generate":
        return generate(arguments.config)
    return {"install": install, "init": initialize, "gateway": gateway,
            "cockpit": cockpit, "status": status, "unload": unload}[arguments.action]()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
