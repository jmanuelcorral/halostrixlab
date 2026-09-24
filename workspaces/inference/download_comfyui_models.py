import fcntl
import os
import subprocess
import sys

import comfyui
import runtime


def download_command(image):
    comfyui.validate_image(image)
    cache = runtime.checked_mount(str(comfyui.STORAGE / "cache"))
    models = runtime.checked_mount(str(comfyui.STORAGE / "models"))
    return [
        "docker", "run", "--rm", "--init", "--pull=never",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--env", "HOME=/download", "--env", "HF_HOME=/download/huggingface",
        "--mount", f"type=bind,src={cache},dst=/download",
        "--mount", f"type=bind,src={models},dst=/download/comfy-models",
        "--entrypoint", "/bin/bash", image, "-c",
        "set -e; /opt/get_qwen_image.sh 1 bf16; /opt/get_qwen_image.sh 3",
    ]


def main():
    image = comfyui.pinned_image()
    for directory in (comfyui.DATA, comfyui.STORAGE,
                      comfyui.STORAGE / "cache", comfyui.STORAGE / "models"):
        runtime.private_directory(directory)
    lock_path = comfyui.STORAGE / "download.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another ComfyUI model download is already running") from error
        runtime.docker(["image", "inspect", image])
        print("Downloading Qwen Image 2512 BF16, encoder, VAE and Lightning 4-step LoRA.", flush=True)
        print("No GPU access or service changes. Allow tens of GB and keep this terminal open.", flush=True)
        print("Ctrl+C interrupts; rerun this script to resume. Existing files are skipped by upstream.", flush=True)
        result = subprocess.run(download_command(image), pass_fds=(lock.fileno(),))
        if result.returncode:
            return result.returncode
        print("Download helper completed. Weights:", comfyui.STORAGE / "models")
        print("Use the Qwen-Image-2512-Lightning LoRA, not the Edit-2511 LoRA, in the workflow.")
        print("No GPU generation or independent checksum verification has been performed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDownload interrupted; rerun to resume.", file=sys.stderr)
        sys.exit(130)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("Prepare the image first with: python3 workspaces/inference/comfyui.py prepare", file=sys.stderr)
        sys.exit(1)
