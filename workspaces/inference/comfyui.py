import argparse
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import runtime


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STORAGE = DATA / "comfyui"
IMAGE = "docker.io/kyuz0/amd-strix-halo-comfyui:latest"
NAME = "comfyui-manual"
PORT = 8188


def prepare():
    runtime.private_directory(DATA)
    runtime.private_directory(STORAGE)
    for directory in ("models", "input", "output", "user", "cache"):
        runtime.private_directory(STORAGE / directory)
    reference = STORAGE / "image.ref"
    if reference.exists():
        value = pinned_image()
        runtime.docker(["image", "inspect", value])
        print("Existing pinned image preserved:", value)
    else:
        subprocess.run(["docker", "pull", IMAGE], check=True)
        image = runtime.docker(["image", "inspect", IMAGE, "--format", "{{index .RepoDigests 0}}"])
        value = validate_image(image.stdout.strip())
        runtime.write_private(reference, value + "\n")
    seed_workflows(value)
    print("Prepared manual ComfyUI; no model weights downloaded or GPU service started")


def seed_workflows(image):
    script = (
        "from pathlib import Path; "
        "source = Path('/opt/ComfyUI/user/default/workflows'); "
        "target = Path('/persistent/default/workflows'); "
        "target.mkdir(parents=True, exist_ok=True); "
        "[(target / item.name).write_bytes(item.read_bytes()) "
        "for item in source.glob('*.json') if not (target / item.name).exists()]"
    )
    subprocess.run([
        "docker", "run", "--rm", "--network=none", "--pull=never",
        "--user", f"{os.getuid()}:{os.getgid()}", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--mount",
        f"type=bind,src={runtime.checked_mount(str(STORAGE / 'user'))},dst=/persistent",
        "--entrypoint", "/opt/venv/bin/python", image, "-c", script,
    ], check=True)


def validate_image(value):
    if not re.fullmatch(r"(?:docker\.io/)?kyuz0/amd-strix-halo-comfyui@sha256:[0-9a-f]{64}", value):
        raise ValueError("Expected a pinned kyuz0 ComfyUI image digest")
    return value


def pinned_image():
    return validate_image(runtime.private_file(STORAGE / "image.ref").read_text().strip())


def run_command(image, gpu_devices):
    validate_image(image)
    command = [
        "docker", "run", "--rm", "--init", "--pull=never", "--name", "halostrix-" + NAME,
        "--label", f"{runtime.LABEL}={runtime.ROOT}",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--security-opt=seccomp=unconfined", "--shm-size=1g", "--stop-timeout", "60",
        "--publish", f"127.0.0.1:{PORT}:{PORT}",
        "--env", "HOME=/cache", "--env", "XDG_CACHE_HOME=/cache",
        "--env", "HF_HOME=/cache/huggingface", "--env", "HF_HUB_OFFLINE=1",
        "--env", "TRANSFORMERS_OFFLINE=1",
        "--env", "TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1",
        "--env", "TORCH_BLAS_PREFER_HIPBLASLT=1",
    ]
    for device in gpu_devices:
        command.extend(["--device", str(device)])
    for group in sorted({str(device.stat().st_gid) for device in gpu_devices}):
        command.extend(["--group-add", group])
    for directory, target in (
        ("models", "/opt/ComfyUI/models"), ("input", "/opt/ComfyUI/input"),
        ("output", "/outputs"), ("user", "/opt/ComfyUI/user"), ("cache", "/cache"),
    ):
        source = runtime.checked_mount(str(STORAGE / directory))
        readonly = ",readonly" if directory == "models" else ""
        command.extend(["--mount", f"type=bind,src={source},dst={target}{readonly}"])
    command.extend([
        "--entrypoint", "/opt/venv/bin/python", image, "/opt/ComfyUI/main.py",
        "--listen", "0.0.0.0", "--port", str(PORT), "--output-directory", "/outputs",
        "--input-directory", "/opt/ComfyUI/input", "--user-directory", "/opt/ComfyUI/user",
        "--disable-mmap", "--gpu-only", "--disable-smart-memory", "--cache-none", "--bf16-vae",
    ])
    return command


def start():
    image = pinned_image()
    runtime.private_directory(DATA)
    with (DATA / "gpu.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("GPU reserved: unload/stop Halogen or close Cockpit first; nothing was stopped") from error
        runtime.require_halo()
        active = runtime.docker([
            "container", "ls", "--filter", f"label={runtime.LABEL}={runtime.ROOT}",
            "--format", "{{.ID}}",
        ])
        if active.stdout.strip():
            raise ValueError("A managed GPU container is active; nothing was stopped")
        if runtime.inspect_owned("halostrix-" + NAME):
            raise ValueError("An owned ComfyUI container remains; run stop first")
        runtime.docker(["image", "inspect", image])
        command = run_command(image, runtime.devices("comfyui-rocm"))
        cancelled = False
        child = None

        def terminate(signum, frame):
            nonlocal cancelled
            cancelled = True

        previous = {signum: signal.signal(signum, terminate) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            print(f"ComfyUI: http://127.0.0.1:{PORT}, Ctrl+C or the stop command to exit", flush=True)
            child = subprocess.Popen(command, pass_fds=(lock.fileno(),))
            while child.poll() is None:
                if cancelled:
                    runtime.stop(NAME)
                time.sleep(0.1)
            return child.returncode
        finally:
            try:
                runtime.stop(NAME)
                if child and child.poll() is None:
                    child.wait(timeout=70)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)


def status():
    identifier = runtime.inspect_owned("halostrix-" + NAME)
    if not identifier:
        print("ComfyUI stopped; persistent files preserved")
        return
    result = runtime.docker(["inspect", "--format", "{{.State.Status}}", identifier])
    print("ComfyUI:", result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Manual, GPU-exclusive Strix Halo ComfyUI")
    parser.add_argument("action", choices=["prepare", "start", "stop", "status"])
    arguments = parser.parse_args()
    return {"prepare": prepare, "start": start, "stop": lambda: runtime.stop(NAME), "status": status}[arguments.action]()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
