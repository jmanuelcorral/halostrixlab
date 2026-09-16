#!/usr/bin/env python3
"""Fake 'docker' engine for offline EngramHalo wrapper tests.

Never touches real containers, GPUs, or the network. Understands just
enough of the docker CLI surface (`run`, `inspect`, `stop`, `rm`) to
exercise the wrapper's argv construction and lifecycle logic. State is
kept in a JSON file under the directory given by FAKE_ENGINE_STATE_DIR.

FAKE_ENGINE_MODE selects scripted behaviors used by the lifecycle tests:
  default               - normal run/inspect/stop/rm.
  no-cid                - `run` exits 0 immediately without writing a cidfile.
  delay-cid             - `run` writes the cidfile after a short delay.
  inspect-wrong-label   - `inspect` always reports a foreign name/label.
  inspect-daemon-error  - `inspect` fails with a daemon-style error (not a
                          "not found" condition).
  stop-fails            - `stop` fails (simulates a daemon that won't stop
                          the container); `rm` also fails to keep it retained.
"""
import json
import os
import signal
import sys
import time
import uuid


def state_path():
    d = os.environ["FAKE_ENGINE_STATE_DIR"]
    return os.path.join(d, "state.json")


def load_state():
    p = state_path()
    if not os.path.isfile(p):
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state(st):
    with open(state_path(), "w", encoding="utf-8") as fh:
        json.dump(st, fh)


def cmd_run(args):
    # Extract --cidfile, --name, and the run label from a
    # "--label engramhalo.run=<uuid>" argument, plus record full argv.
    cidfile = None
    name = None
    label = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--cidfile":
            cidfile = args[i + 1]
            i += 2
            continue
        if a == "--name":
            name = args[i + 1]
            i += 2
            continue
        if a == "--label" and args[i + 1].startswith("engramhalo.run="):
            label = args[i + 1].split("=", 1)[1]
            i += 2
            continue
        i += 1

    mode = os.environ.get("FAKE_ENGINE_MODE", "default")
    if mode == "no-cid":
        return 0

    cid = uuid.uuid4().hex
    if cidfile and mode != "delay-cid":
        with open(cidfile, "w", encoding="utf-8") as fh:
            fh.write(cid)
    elif cidfile and mode == "delay-cid":
        time.sleep(0.25)
        with open(cidfile, "w", encoding="utf-8") as fh:
            fh.write(cid)

    st = load_state()
    st[cid] = {"name": name, "label": label, "argv": args, "running": True}
    save_state(st)

    stop_requested = {"flag": False}

    def _term(_signum, _frame):
        stop_requested["flag"] = True

    signal.signal(signal.SIGTERM, _term)

    # Behave like a foreground server: run until asked to stop (either by
    # a direct signal, or because a separate "docker stop" invocation
    # flipped our shared state's "running" flag), or a bounded fallback
    # timeout in case a test forgets to signal us.
    deadline = time.time() + float(os.environ.get("FAKE_ENGINE_IDLE_SECONDS", "20"))
    while not stop_requested["flag"] and time.time() < deadline:
        cur = load_state().get(cid, {})
        if not cur.get("running", True):
            break
        time.sleep(0.05)

    st = load_state()
    if cid in st:
        if mode != "stop-fails":
            st[cid]["running"] = False
        save_state(st)
    return 0 if stop_requested["flag"] else 0


def cmd_inspect(args):
    fmt = None
    cid = None
    i = 0
    while i < len(args):
        if args[i] == "--format":
            fmt = args[i + 1]
            i += 2
            continue
        cid = args[i]
        i += 1
    mode = os.environ.get("FAKE_ENGINE_MODE", "default")
    if mode == "inspect-wrong-label":
        if fmt and "Labels" in fmt:
            sys.stdout.write("true|/engramhalo-wrong|wrong-label\n")
        return 0
    if mode == "inspect-daemon-error":
        sys.stderr.write("Error response from daemon: fake internal failure\n")
        return 1
    st = load_state()
    entry = st.get(cid)
    if entry is None:
        sys.stderr.write(f"Error: No such object: {cid}\n")
        return 1
    if fmt and "Labels" in fmt:
        running = "true" if entry.get("running") else "false"
        sys.stdout.write(f"{running}|/{entry['name']}|{entry['label']}\n")
    return 0


def cmd_stop(args):
    cid = args[-1]
    mode = os.environ.get("FAKE_ENGINE_MODE", "default")
    if mode == "stop-fails":
        sys.stderr.write("Error response from daemon: fake stop failure\n")
        return 1
    st = load_state()
    if cid in st:
        st[cid]["running"] = False
        save_state(st)
        return 0
    return 1


def cmd_rm(args):
    cid = args[-1]
    mode = os.environ.get("FAKE_ENGINE_MODE", "default")
    if mode == "stop-fails":
        sys.stderr.write("Error response from daemon: fake rm failure\n")
        return 1
    st = load_state()
    if cid in st:
        st[cid]["removed"] = True
        save_state(st)
        return 0
    return 1


def main(argv):
    if not argv:
        return 1
    sub = argv[0]
    rest = argv[1:]
    if sub == "run":
        # --help / --version fastpath: no --cidfile present.
        if "--cidfile" not in rest:
            sys.stdout.write("fake-engine-server help/version output\n")
            return 0
        return cmd_run(rest)
    if sub == "inspect":
        return cmd_inspect(rest)
    if sub == "stop":
        return cmd_stop(rest)
    if sub == "rm":
        return cmd_rm(rest)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
