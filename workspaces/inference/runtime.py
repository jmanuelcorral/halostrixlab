import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LABEL = "io.halostrix.inference"
KINDS = {"llamacpp-vulkan", "llamacpp-rocm", "vllm", "halogen"}


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Private directory must not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError("Private directory requires current owner and mode 0700")
    return path


def private_file(path):
    path = Path(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise ValueError("Configuration must be a regular file owned by the operator")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("Configuration requires mode 0600")
    return path


def write_private(path, content):
    private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)


def checked_mount(value, must_exist=True):
    path = Path(value)
    if not path.is_absolute() or any(character in value for character in ",\n\r"):
        raise ValueError("Mounts require absolute paths without commas or newlines")
    resolved = path.resolve()
    if resolved in {Path("/"), Path("/home"), Path("/root"), Path.home()}:
        raise ValueError("Mounting a HOME or filesystem root is forbidden")
    if any(part in {".ssh", ".config", ".opencode", ".git"} for part in resolved.parts):
        raise ValueError("Private configuration directories cannot be mounted")
    if must_exist and not resolved.is_dir():
        raise ValueError("Model/cache directory does not exist")
    return str(resolved)


def validate_profile(name, profile, must_exist=True):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", name):
        raise ValueError("Invalid profile identifier")
    allowed = {"enabled", "kind", "image", "model_dir", "model", "upstream_model",
               "context", "output", "cache_dir", "halogen_checkpoint", "vllm_args", "load_mode",
               "halogen_overlay", "halogen_tokenizer", "halogen_max_tok", "slots", "kv_pool"}
    if set(profile) - allowed:
        raise ValueError("Unknown profile fields")
    if profile.get("kind") not in KINDS:
        raise ValueError("Unsupported runtime kind")
    if not re.fullmatch(r"[^\s$<>]+@sha256:[0-9a-f]{64}", profile.get("image", "")):
        raise ValueError("Image must be pinned by registry digest")
    checked_mount(profile["model_dir"], must_exist)
    if "load_mode" in profile and (
        not profile["kind"].startswith("llamacpp") or profile["load_mode"] != "none"
    ):
        raise ValueError("Only llama.cpp load_mode none is supported")
    for key in ("context", "output"):
        if type(profile.get(key)) is not int or profile[key] < 1:
            raise ValueError("Context/output must be positive integers")
    if profile["output"] >= profile["context"] or profile["context"] > 262144:
        raise ValueError("Output must fit within native context, capped at 262144")
    if not isinstance(profile.get("upstream_model"), str) or not profile["upstream_model"]:
        raise ValueError("An exact upstream model ID is required")
    if any(character in profile["upstream_model"] for character in "\n\r$"):
        raise ValueError("Invalid upstream model ID")
    halogen_fields = {"halogen_overlay", "halogen_tokenizer", "halogen_max_tok", "slots", "kv_pool"}
    if profile["kind"] != "halogen" and halogen_fields.intersection(profile):
        raise ValueError("Halogen settings require a Halogen profile")
    if profile["kind"] == "halogen":
        slots = profile.get("slots", 1)
        pool = profile.get("kv_pool", profile["context"])
        if type(slots) is not int or not 1 <= slots <= 8:
            raise ValueError("Halogen slots must be an integer between 1 and 8")
        if type(pool) is not int or not profile["context"] <= pool <= 1048576:
            raise ValueError("Halogen KV pool must cover one context and be capped at 1048576")
    if "halogen_max_tok" in profile:
        maximum = profile["halogen_max_tok"]
        if type(maximum) is not int or not 1 <= maximum <= min(profile["context"], 32768):
            raise ValueError("Halogen prefill arena must fit within context and 32768 tokens")
    if profile["kind"].startswith("llamacpp") or profile["kind"] == "halogen":
        keys = ["halogen_checkpoint"] if profile["kind"] == "halogen" else ["model"]
        keys.extend(key for key in ("halogen_overlay", "halogen_tokenizer") if key in profile)
        root = Path(profile["model_dir"]).resolve()
        for key in keys:
            value = profile[key]
            if not isinstance(value, str) or not value or any(character in value for character in "$\n\r"):
                raise ValueError("Artifact must be a nonempty relative path")
            artifact = Path(value)
            if artifact.is_absolute() or ".." in artifact.parts:
                raise ValueError("Artifact must be relative to its model directory")
            target = (root / artifact).resolve()
            if key == "halogen_tokenizer":
                target = (target / "tokenizer.json").resolve()
            if not target.is_relative_to(root) or (must_exist and not target.is_file()):
                raise ValueError("Artifact is absent or escapes model directory")
    if profile["kind"] == "vllm":
        checked_mount(profile["cache_dir"], must_exist)
        if Path(profile["cache_dir"]).resolve() == Path(profile["model_dir"]).resolve():
            raise ValueError("Writable cache must be separate from read-only models")
        arguments = profile.get("vllm_args", [])
        if not isinstance(arguments, list) or any(not isinstance(item, str) for item in arguments):
            raise ValueError("vllm_args must be a string list")
        blocked = {"--host", "--port", "--model", "--served-model-name", "--api-key",
                   "--trust-remote-code", "--allowed-local-media-path"}
        if any(item.split("=", 1)[0] in blocked for item in arguments):
            raise ValueError("vllm_args cannot override network, identity or trust settings")
    return profile


def load_profiles(config):
    document = json.loads(private_file(config).read_text())
    if set(document) != {"profiles"} or not isinstance(document["profiles"], dict):
        raise ValueError("Expected a profiles object")
    profiles = {}
    for name, profile in document["profiles"].items():
        if not isinstance(profile, dict) or type(profile.get("enabled")) is not bool:
            raise ValueError("Every profile needs an explicit enabled boolean")
        if profile["enabled"]:
            profiles[name] = validate_profile(name, profile)
    if not profiles:
        raise ValueError("Enable at least one fully configured profile")
    return profiles


def devices(kind):
    render_nodes = sorted(Path("/dev/dri").glob("renderD*"))
    if len(render_nodes) != 1:
        raise ValueError("Exactly one render device is required for this initial single-GPU setup")
    paths = render_nodes + ([] if kind == "llamacpp-vulkan" else [Path("/dev/kfd")])
    for path in paths:
        if not stat.S_ISCHR(path.stat().st_mode) or not os.access(path, os.R_OK | os.W_OK):
            raise ValueError("GPU devices must be readable/writable by the operator")
    return paths


def require_halo():
    cpu = Path("/proc/cpuinfo").read_text()
    if not re.search(r"Ryzen AI MAX", cpu, re.IGNORECASE):
        raise ValueError("Runtime launch is restricted to the Halo; this CPU is not Ryzen AI Max")
    active = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process / "comm").read_text().strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if name in {"llama-server", "flash_serve", "vllm", "lemond"}:
            active.append(name)
    if active:
        raise ValueError("Existing inference service detected; drain and stop it explicitly before activation")


def docker(arguments, check=True):
    return subprocess.run(["docker", *arguments], check=check, capture_output=True, text=True)


def inspect_owned(name):
    result = docker(["container", "ls", "-a", "--filter", f"name=^{name}$", "--format", "{{.ID}}"])
    identifier = result.stdout.strip()
    if not identifier:
        return None
    data = json.loads(docker(["container", "inspect", identifier]).stdout)[0]
    if data["Config"].get("Labels", {}).get(LABEL) != str(ROOT):
        raise ValueError("Container name belongs to another owner; refusing to stop it")
    return data["Id"]


def stop(name):
    identifier = inspect_owned("halostrix-" + name)
    if identifier:
        docker(["stop", "--time", "60", identifier])


def run_command(name, profile, port, gpu_devices):
    command = ["docker", "run", "--rm", "--pull=never", "--name", "halostrix-" + name,
               "--label", f"{LABEL}={ROOT}", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", "--stop-timeout", "60",
               "--publish", f"127.0.0.1:{port}:8080",
               "--mount", f"type=bind,src={checked_mount(profile['model_dir'])},dst=/models,readonly",
               "--env", "HF_HUB_OFFLINE=1", "--env", "TRANSFORMERS_OFFLINE=1"]
    for path in gpu_devices:
        command.extend(["--device", str(path)])
    for group in sorted({str(path.stat().st_gid) for path in gpu_devices}):
        command.extend(["--group-add", group])
    kind = profile["kind"]
    if kind != "llamacpp-vulkan":
        command.extend(["--ipc=host", "--ulimit", "memlock=-1:-1"])
    if kind.startswith("llamacpp"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}", "--entrypoint", "llama-server",
                        profile["image"], "--host", "0.0.0.0", "--port", "8080",
                        "--model", "/models/" + profile["model"], "--alias", profile["upstream_model"],
                        "--ctx-size", str(profile["context"]), "--parallel", "1", "--jinja",
                        "--flash-attn", "on", "--n-gpu-layers", "999"])
        command.extend(["--load-mode", "none"] if profile.get("load_mode") == "none" else ["--no-mmap"])
    elif kind == "halogen":
        settings = {"HALOGEN_API_PORT": "8080", "HALOGEN_DOWNLOAD": "",
                    "HALOGEN_CHECKPOINT": "/models/" + profile["halogen_checkpoint"],
                    "HALOGEN_MODEL_ID": profile["upstream_model"],
                    "HALOGEN_CTX": str(profile["context"]),
                    "HALOGEN_KV_POOL_POSITIONS": str(profile.get("kv_pool", profile["context"])),
                    "HALOGEN_KV_SLOTS": str(profile.get("slots", 1)),
                    "HALOGEN_MAX_TOK": str(profile.get("halogen_max_tok", 16384)),
                    "HALOGEN_MAX_TOKENS_CAP": str(profile["output"]),
                    "HALOGEN_MAX_TOKENS_DEFAULT": str(min(8192, profile["output"]))}
        for key, variable in (("halogen_overlay", "HALOGEN_CK_OVERLAY"),
                              ("halogen_tokenizer", "HALOGEN_TOKENIZER")):
            if key in profile:
                settings[variable] = "/models/" + profile[key]
        for key, value in settings.items():
            command.extend(["--env", f"{key}={value}"])
        command.extend([profile["image"], "all"])
    else:
        command.extend(["--mount", f"type=bind,src={checked_mount(profile['cache_dir'])},dst=/cache",
                        "--env", "HOME=/cache", "--env", "HF_HOME=/cache/huggingface",
                        "--env", "VLLM_CACHE_ROOT=/cache/vllm", "--env", "TRITON_CACHE_DIR=/cache/triton",
                        "--entrypoint", "vllm", profile["image"], "serve", "/models",
                        "--host", "0.0.0.0", "--port", "8080", "--served-model-name",
                        profile["upstream_model"], "--max-model-len", str(profile["context"]),
                        "--max-num-seqs", "1", *profile.get("vllm_args", [])])
    return command


def start(name, profile, port):
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid unprivileged backend port")
    private_directory(DATA)
    with (DATA / "gpu.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another managed GPU profile holds the lease") from error
        require_halo()
        if inspect_owned("halostrix-" + name):
            raise ValueError("A stale owned container exists; inspect and stop it first")
        docker(["image", "inspect", profile["image"]])
        command = run_command(name, profile, port, devices(profile["kind"]))
        child = None
        cancelled = False

        def terminate(signum, frame):
            nonlocal cancelled
            cancelled = True

        previous = {signum: signal.signal(signum, terminate) for signum in (signal.SIGINT, signal.SIGTERM)}
        try:
            child = subprocess.Popen(command)
            while child.poll() is None:
                if cancelled:
                    stop(name)
                time.sleep(0.1)
            return child.returncode
        finally:
            try:
                stop(name)
                if child and child.poll() is None:
                    child.wait(timeout=70)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("name")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    arguments = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", arguments.name):
        raise ValueError("Invalid profile identifier")
    if arguments.action == "stop":
        stop(arguments.name)
        return 0
    profiles = load_profiles(arguments.config)
    if arguments.name not in profiles:
        raise ValueError("Profile is not enabled")
    return start(arguments.name, profiles[arguments.name], arguments.port)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
