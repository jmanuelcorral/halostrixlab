import fcntl
import hashlib
import os
from pathlib import Path

import comfyui
import runtime


ARTIFACTS = [
    {'repo': 'Comfy-Org/Qwen-Image-Edit_ComfyUI', 'revision': 'f68ace85e60b4a02a323e394253731947657b7d2',
     'file': 'split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors',
     'directory': 'diffusion_models', 'size': 40861031560,
     'sha256': 'ae42d927b5fac4f278b9a894554c727e619727a63622976f2d95625be4bce08c'},
    {'repo': 'lightx2v/Qwen-Image-Edit-2511-Lightning', 'revision': 'd74eba145674fd7e31b949324e148e21e7118abd',
     'file': 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors',
     'directory': 'loras', 'size': 849608296,
     'sha256': '22226e8d05d354bb356627d428809f5afd7819399b077238a2b70a82883a904f'},
]


def verify(path, artifact):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != artifact['size']:
        raise ValueError('Model file is unsafe or has the wrong size')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != artifact['sha256']:
            raise ValueError('Model SHA256 mismatch')


def download():
    os.umask(0o077)
    runtime.private_directory(comfyui.STORAGE)
    models = runtime.private_directory(comfyui.STORAGE / 'models')
    os.environ['HF_HOME'] = str(comfyui.STORAGE / 'cache' / 'huggingface')
    from huggingface_hub import hf_hub_download
    descriptor = os.open(comfyui.STORAGE / 'download.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for artifact in ARTIFACTS:
            directory = models / artifact['directory']
            if directory.is_symlink() or not directory.is_dir() or directory.stat().st_uid != os.getuid():
                raise ValueError('Prepare an operator-owned model directory first')
            destination = directory / Path(artifact['file']).name
            if destination.exists() or destination.is_symlink():
                verify(destination, artifact)
                continue
            source = Path(hf_hub_download(artifact['repo'], artifact['file'], revision=artifact['revision'],
                                         local_dir=models / '.portrait-stage'))
            verify(source, artifact)
            os.link(source, destination)
            print('Verified: ' + destination.name, flush=True)
    print('Portrait Edit models ready; existing Image models and services unchanged')


if __name__ == '__main__':
    download()
