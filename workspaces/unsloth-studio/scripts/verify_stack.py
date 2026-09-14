import importlib.metadata as metadata
import json
import pathlib
import sys

import torch

STACK_FILE = pathlib.Path("/opt/base-torch.json")
CONSTRAINTS_FILE = pathlib.Path("/opt/stack-constraints.txt")
PACKAGES = ("torch", "torchvision", "torchaudio", "triton")


def stack():
    result = {name: metadata.version(name) for name in PACKAGES}
    result.update(version=torch.__version__, hip=torch.version.hip, file=torch.__file__)
    return result


def prohibited_packages():
    names = (dist.metadata["Name"] or "" for dist in metadata.distributions())
    return sorted(name for name in names if "nvidia" in name.lower() or "cuda" in name.lower())


current = stack()
bad = prohibited_packages()
if bad:
    raise SystemExit(f"Paquetes CUDA/NVIDIA detectados: {bad!r}")

if sys.argv[1] == "capture":
    if current["version"].split("+", 1)[0] != "2.11.0" or not str(current["hip"]).startswith("7.14"):
        raise SystemExit(f"La base no contiene PyTorch 2.11 + ROCm 7.14: {current!r}")
    STACK_FILE.write_text(json.dumps(current, sort_keys=True), encoding="utf-8")
    CONSTRAINTS_FILE.write_text(
        "".join(f"{name}=={current[name]}\n" for name in PACKAGES),
        encoding="utf-8",
    )
elif sys.argv[1] == "verify":
    before = json.loads(STACK_FILE.read_text(encoding="utf-8"))
    if current != before:
        raise SystemExit(f"La resolución reemplazó el stack base: {before!r} -> {current!r}")
else:
    raise SystemExit("Uso: verify_stack.py capture|verify")
