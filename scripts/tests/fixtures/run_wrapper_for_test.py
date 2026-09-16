#!/usr/bin/env python3
"""Test-only subprocess entrypoint for offline EngramHalo wrapper tests.

This driver is NOT part of the production wrapper and ships no bypass in
`scripts/engramhalo/llama-server` itself. It exists only because some
lifecycle tests must exercise the wrapper's real subprocess/signal/argv
code paths (fork+exec, SIGTERM handling, etc.), which cannot be done via an
in-process monkeypatch alone.

It loads the real wrapper module, monkeypatches only the isolated pure
predicate `_gpu_canonical_ok` (the same seam unit tests patch in-process)
so that /dev/null and /dev/zero are accepted as GPU device stand-ins, and
then calls the real, unmodified `main()`. There is no environment variable
or flag read by the production wrapper that does this; the substitution
happens only here, in test-only code, before any docker/engine invocation.
"""

import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

WRAPPER_PATH = Path(__file__).resolve().parents[2] / "engramhalo" / "llama-server"

_loader = SourceFileLoader("engramhalo_wrapper_subprocess", str(WRAPPER_PATH))
wrapper = _loader.load_module()

wrapper._gpu_canonical_ok = lambda real, kind: True

if __name__ == "__main__":
    sys.exit(wrapper.main(sys.argv[1:]))
