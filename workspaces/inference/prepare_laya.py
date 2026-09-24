import os
import shutil
import subprocess
import tarfile

import laya_runtime as laya


def prepare():
    os.umask(0o077)
    laya.runtime.private_directory(laya.DATA)
    source = laya.DATA / 'source'
    if (laya.DATA / 'deployment.json').exists():
        laya.deployment()
        print('Existing immutable deployment preserved; no rebuild or download performed')
        return
    if not source.exists():
        archive = laya.DATA / 'source.tar.gz'
        with archive.open('wb') as output:
            subprocess.run(['gh', 'api', 'repos/NandhaKishorM/laya/tarball/' + laya.SOURCE_REVISION], stdout=output, check=True)
        source.mkdir(mode=0o700)
        with tarfile.open(archive) as bundle:
            prefix = bundle.getmembers()[0].name.split('/')[0] + '/'
            for member in bundle.getmembers():
                if not member.name.startswith(prefix):
                    continue
                member.name = member.name[len(prefix):]
                if member.name:
                    bundle.extract(member, source, filter='data')
    for original, destination in [('laya.Dockerfile', 'Dockerfile'), ('laya.dockerignore', '.dockerignore'), ('laya_server.py', 'laya_server.py')]:
        shutil.copyfile(laya.ROOT / original, laya.DATA / destination)
    subprocess.run(['docker', 'build', '--tag', 'halostrix-laya:0.3.9-cpu', str(laya.DATA)], check=True)
    image = laya.runtime.docker(['image', 'inspect', 'halostrix-laya:0.3.9-cpu', '--format', '{{.Id}}']).stdout.strip()
    for name in ('models', 'cache'):
        laya.runtime.private_directory(laya.DATA / name)
    script = ('from huggingface_hub import snapshot_download; '
              'snapshot_download("convaiinnovations/laya-multilingual", revision="' + laya.MODEL_REVISION + '", '
              'local_dir="/models", allow_patterns=["model.safetensors", "rl_agent_config.json", "encoder/*", "tokenizer/*", "README.md"])')
    command = ['docker', 'run', '--rm', '--pull=never', '--user', f'{os.getuid()}:{os.getgid()}',
               '--cap-drop=ALL', '--security-opt=no-new-privileges']
    for name in ('models', 'cache'):
        command.extend(['--mount', f'type=bind,src={laya.DATA / name},dst=/{name}'])
    subprocess.run([*command, '--entrypoint', 'python', image, '-c', script], check=True)
    laya.configure(image)
    with (laya.DATA / 'packages.txt').open('w') as output:
        subprocess.run(['docker', 'run', '--rm', '--pull=never', '--network', 'none', '--entrypoint', 'cat', image, '/opt/packages.txt'], stdout=output, check=True)
    print('Laya CPU prepared; no service started and Halogen unchanged')


if __name__ == '__main__':
    prepare()
