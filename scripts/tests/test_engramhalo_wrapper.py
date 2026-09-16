"""Offline unit tests for the EngramHalo Docker wrapper.

No real Docker, GPU, or network access. Uses a fake 'docker' engine
(scripts/tests/fixtures/fake_engine.py) and, for the port-collision case,
a monkeypatched socket. Only creates/removes files inside temporary
directories owned by the test process.
"""

import importlib.util
import json
import os
import signal
import stat as stat_mod
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
from importlib.machinery import SourceFileLoader
from pathlib import Path

WRAPPER_PATH = Path(__file__).resolve().parents[1] / "engramhalo" / "llama-server"
FAKE_ENGINE = Path(__file__).resolve().parent / "fixtures" / "fake_engine.py"
# Test-only subprocess entrypoint (loads the real wrapper unmodified, only
# patching the isolated `_gpu_canonical_ok` predicate before main() runs).
# See scripts/tests/fixtures/run_wrapper_for_test.py for the full rationale.
TEST_DRIVER = Path(__file__).resolve().parent / "fixtures" / "run_wrapper_for_test.py"

# The wrapper has no .py suffix (it is an executable). Load it as a module
# for in-process unit tests of the pure functions (validation/parsing).
_loader = SourceFileLoader("engramhalo_wrapper", str(WRAPPER_PATH))
_spec = importlib.util.spec_from_loader("engramhalo_wrapper", _loader)
wrapper = importlib.util.module_from_spec(_spec)
_loader.exec_module(wrapper)

# /dev/null and /dev/zero are real character devices always present in any
# sandbox, used as stand-ins for the canonical GPU device nodes in offline
# tests. There is no environment variable or runtime flag in the production
# wrapper that relaxes the canonical-path check; tests that need the
# canonical-path check to accept these stand-ins monkeypatch the isolated
# pure function `wrapper._gpu_canonical_ok` directly (see
# `_patch_gpu_canonical_ok` below), never a flag reachable from real argv or
# environment.
DEVICE_A = "/dev/null"
DEVICE_B = "/dev/zero"


def _patch_gpu_canonical_ok():
    """Context manager: monkeypatch the isolated canonical-path predicate so
    /dev/null and /dev/zero are accepted as GPU device stand-ins in offline
    tests, without touching any production bypass (there is none)."""
    return mock.patch.object(wrapper, "_gpu_canonical_ok", return_value=True)


# Most tests in this module use /dev/null and /dev/zero as GPU device
# stand-ins and expect the canonical-path check to accept them. Rather than
# wrapping dozens of individual call sites, patch the isolated pure
# predicate for the whole test process; this only rebinds an attribute on
# the already-imported test module object (`wrapper`), it is not an
# environment variable or flag reachable from the production entrypoint.
# Tests that specifically need the real (unpatched) canonical-path
# rejection behavior save/restore it locally (see DeviceValidationTests).
_module_gpu_patch = _patch_gpu_canonical_ok()
_module_gpu_patch.start()


def make_state_dir(tmp):
    d = os.path.join(tmp, "state")
    os.mkdir(d, mode=0o700)
    os.chmod(d, 0o700)
    return d


def make_config(tmp, *, image=None, extra_model=None):
    models_root = os.path.join(tmp, "models")
    os.mkdir(models_root)
    model_path = os.path.join(models_root, "example.gguf")
    with open(model_path, "w", encoding="utf-8") as fh:
        fh.write("fake-gguf")

    allowed_models = [{"model": model_path, "mmproj": None}]
    if extra_model:
        allowed_models.append(extra_model)

    cfg = {
        "image": image or ("sha256:" + "0" * 64),
        "engine": str(FAKE_ENGINE),
        "engine_server": "/opt/llama.cpp/llama-server",
        "allowed_model_roots": [models_root],
        "allowed_models": allowed_models,
        "runtime_state_dir": make_state_dir(tmp),
        "gpu_render_device": DEVICE_A,
        "gpu_kfd_device": DEVICE_B,
        "uid": os.getuid(),
        "gid": os.getgid(),
    }
    return cfg, model_path


def write_config(tmp, cfg):
    path = os.path.join(tmp, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def test_missing_env_fails_before_docker(self):
        os.environ.pop("ENGRAMHALO_CONFIG", None)
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_relative_config_path_rejected(self):
        os.environ["ENGRAMHALO_CONFIG"] = "relative/config.json"
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_valid_config_loads(self):
        cfg, _ = make_config(self.tmp)
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        loaded = wrapper.load_config()
        self.assertTrue(loaded["image"].startswith("sha256:"))

    def test_mutable_tag_image_rejected(self):
        cfg, _ = make_config(self.tmp, image="myrepo/engramhalo:latest")
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_short_digest_rejected(self):
        cfg, _ = make_config(self.tmp, image="myrepo/engramhalo@sha256:abcd")
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_root_model_root_rejected(self):
        cfg, _ = make_config(self.tmp)
        cfg["allowed_model_roots"] = ["/"]
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_home_model_root_rejected(self):
        cfg, _ = make_config(self.tmp)
        cfg["allowed_model_roots"] = [os.path.expanduser("~")]
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_ssh_dir_in_root_rejected(self):
        cfg, _ = make_config(self.tmp)
        bad = os.path.join(self.tmp, ".ssh", "models")
        cfg["allowed_model_roots"] = [bad]
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_symlink_escape_rejected(self):
        cfg, model_path = make_config(self.tmp)
        outside = os.path.join(self.tmp, "outside.gguf")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("outside")
        escape_link = os.path.join(os.path.dirname(model_path), "escape.gguf")
        os.symlink(outside, escape_link)
        cfg["allowed_models"].append({"model": escape_link, "mmproj": None})
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_state_dir_wrong_mode_rejected(self):
        cfg, _ = make_config(self.tmp)
        os.chmod(cfg["runtime_state_dir"], 0o755)
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_state_dir_symlink_rejected(self):
        cfg, _ = make_config(self.tmp)
        real_dir = cfg["runtime_state_dir"]
        link_dir = real_dir + "-link"
        os.symlink(real_dir, link_dir)
        cfg["runtime_state_dir"] = link_dir
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_root_uid_rejected(self):
        cfg, _ = make_config(self.tmp)
        cfg["uid"] = 0
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_nonexistent_engine_rejected(self):
        cfg, _ = make_config(self.tmp)
        cfg["engine"] = "/no/such/docker-binary"
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_forbidden_path_characters_rejected(self):
        cfg, _ = make_config(self.tmp)
        cfg["allowed_model_roots"] = [cfg["allowed_model_roots"][0] + ",evil"]
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()


class ArgParsingTests(unittest.TestCase):
    def test_missing_required_fields_fail(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args(["--port", "8000"])

    def test_unknown_flag_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--not-a-real-flag", "1",
            ])

    def test_hf_download_flag_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "-hf", "someorg/somerepo",
            ])

    def test_lora_flag_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--lora", "/x/adapter.gguf",
            ])

    def test_duplicate_flag_rejected_even_if_identical(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--port", "8000",
                "--ctx-size", "4096", "--parallel", "1",
            ])

    def test_parallel_gt_one_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "2",
            ])

    def test_host_other_than_loopback_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--host", "0.0.0.0",
            ])

    def test_host_defaults_to_loopback(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1",
        ])
        self.assertEqual(parsed["host"], "127.0.0.1")

    def test_port_out_of_range_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "70000", "--ctx-size", "4096",
                "--parallel", "1",
            ])

    def test_equals_syntax_supported(self):
        parsed = wrapper.parse_forward_args([
            "--model=/x/model.gguf", "--port=8000", "--ctx-size=4096",
            "--parallel=1", "--jinja",
        ])
        self.assertEqual(parsed["model"], "/x/model.gguf")
        self.assertEqual(parsed["port"], 8000)
        self.assertTrue(parsed["jinja"])

    def test_bool_flag_rejects_inline_value(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--jinja=true",
            ])

    def test_relative_model_path_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1",
            ])

    def test_load_mode_mmap_is_supported_by_engram_contract(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--load-mode", "mmap",
        ])
        self.assertEqual(parsed["load_mode"], "mmap")

    def test_load_mode_other_than_mmap_rejected(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--load-mode", "vram",
            ])

    def test_no_mmap_still_denied(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--no-mmap",
            ])

    def test_mmap_flag_is_not_forbidden_when_intended_by_profile(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--mmap",
        ])
        self.assertTrue(parsed["mmap"])

    def test_flash_attn_requires_enum_value(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--flash-attn",
            ])

    def test_flash_attn_rejects_unknown_value(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--flash-attn", "maybe",
            ])

    def test_flash_attn_accepts_on_off_auto(self):
        for mode in ("on", "off", "auto"):
            parsed = wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--flash-attn", mode,
            ])
            self.assertEqual(parsed["flash_attn"], mode)

    def test_cache_type_k_v_only_typed_values(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--cache-type-k", "q8_0", "--cache-type-v", "f16",
        ])
        self.assertEqual(parsed["cache_type_k"], "q8_0")
        self.assertEqual(parsed["cache_type_v"], "f16")

    def test_cache_type_rejects_unknown_value(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--cache-type-k", "fp32",
            ])

    def test_spec_type_only_none(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--spec-type", "none",
        ])
        self.assertEqual(parsed["spec_type"], "none")
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--spec-type", "draft",
            ])

    def test_cpu_moe_and_n_cpu_moe_mutually_exclusive(self):
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--cpu-moe", "--n-cpu-moe", "4",
            ])

    def test_n_cpu_moe_alone_ok(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--n-cpu-moe", "4",
        ])
        self.assertEqual(parsed["n_cpu_moe"], 4)

    def test_override_tensor_only_exact_known_profile(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "--override-tensor",
            "^per_layer_token_embd[.]weight$=CPU",
        ])
        self.assertEqual(
            parsed["override_tensor"], "^per_layer_token_embd[.]weight$=CPU")
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--override-tensor", "^.*$=CPU",
            ])

    def test_ngl_short_alias_forwarded(self):
        parsed = wrapper.parse_forward_args([
            "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1", "-ngl", "10",
        ])
        self.assertEqual(parsed["n_gpu_layers"], 10)

    def test_ngl_invented_alias_rejected(self):
        # '--ngl' is not a real upstream llama.cpp flag (only '-ngl' and
        # '--n-gpu-layers' are); the wrapper must not accept an invented
        # long alias.
        with self.assertRaises(wrapper.WrapperError):
            wrapper.parse_forward_args([
                "-m", "/x/model.gguf", "--port", "8000", "--ctx-size", "4096",
                "--parallel", "1", "--ngl", "10",
            ])


class ModelResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")
        self.cfg, self.model_path = make_config(self.tmp)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def test_model_not_in_allowlist_rejected(self):
        parsed = {"model": "/some/other/model.gguf", "mmproj": None,
                   "port": 8000, "ctx_size": 4096, "parallel": 1,
                   "host": "127.0.0.1"}
        with self.assertRaises(wrapper.WrapperError):
            wrapper.resolve_model(self.cfg, parsed)

    def test_model_in_allowlist_resolves(self):
        parsed = {"model": self.model_path, "mmproj": None,
                  "port": 8000, "ctx_size": 4096, "parallel": 1,
                  "host": "127.0.0.1"}
        entry = wrapper.resolve_model(self.cfg, parsed)
        self.assertEqual(entry["model"], os.path.realpath(self.model_path))


class DockerArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")
        self.cfg, self.model_path = make_config(self.tmp)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def test_build_run_argv_has_no_interactive_or_detach_flags(self):
        parsed = wrapper.parse_forward_args([
            "-m", self.model_path, "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1",
        ])
        entry = wrapper.resolve_model(self.cfg, parsed)
        argv = wrapper.build_run_argv(
            self.cfg, parsed, entry, "/tmp/x.cid", "engramhalo-test", "run-1",
        )
        self.assertNotIn("-it", argv)
        self.assertNotIn("-d", argv)
        self.assertIn("--rm", argv)
        self.assertIn("--pull=never", argv)
        self.assertIn("--cap-drop=ALL", argv)
        self.assertIn("--security-opt=no-new-privileges", argv)
        self.assertNotIn("--privileged", argv)

    def test_build_run_argv_forwards_spaces_and_equals_safely(self):
        model_with_space = os.path.join(
            os.path.dirname(self.model_path), "a model.gguf")
        with open(model_with_space, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.cfg["allowed_models"].append(
            {"model": os.path.realpath(model_with_space), "mmproj": None})
        parsed = wrapper.parse_forward_args([
            "--model=" + model_with_space, "--port=8000", "--ctx-size=4096",
            "--parallel=1",
        ])
        entry = wrapper.resolve_model(self.cfg, parsed)
        argv = wrapper.build_run_argv(
            self.cfg, parsed, entry, "/tmp/x.cid", "engramhalo-test", "run-1",
        )
        # argv is a list (no shell), so the literal path with a space
        # survives as a single element, unsplit.
        self.assertIn(os.path.realpath(model_with_space), argv)

    def test_build_run_argv_always_includes_explicit_mmap(self):
        parsed = wrapper.parse_forward_args([
            "-m", self.model_path, "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1",
        ])
        entry = wrapper.resolve_model(self.cfg, parsed)
        argv = wrapper.build_run_argv(
            self.cfg, parsed, entry, "/tmp/x.cid", "engramhalo-test", "run-1",
        )
        self.assertIn("--mmap", argv)

    def test_build_run_argv_does_not_auto_add_configured_mmproj(self):
        mmproj_path = os.path.join(os.path.dirname(self.model_path), "proj.mmproj")
        with open(mmproj_path, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.cfg["allowed_models"][0]["mmproj"] = os.path.realpath(mmproj_path)
        parsed = wrapper.parse_forward_args([
            "-m", self.model_path, "--port", "8000", "--ctx-size", "4096",
            "--parallel", "1",
        ])
        entry = wrapper.resolve_model(self.cfg, parsed)
        argv = wrapper.build_run_argv(
            self.cfg, parsed, entry, "/tmp/x.cid", "engramhalo-test", "run-1",
        )
        self.assertNotIn("--mmproj", argv)
        self.assertNotIn(os.path.realpath(mmproj_path), argv)


class HelpVersionFastpathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")
        self.cfg, _ = make_config(self.tmp)
        self.path = write_config(self.tmp, self.cfg)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def _run(self, arg):
        env = dict(os.environ)
        env["ENGRAMHALO_CONFIG"] = self.path
        return subprocess.run(
            [sys.executable, str(TEST_DRIVER), arg],
            env=env, capture_output=True, text=True, timeout=15,
        )

    def test_help_fastpath_no_devices_or_mounts(self):
        result = self._run("--help")
        self.assertEqual(result.returncode, 0)

    def test_version_fastpath(self):
        result = self._run("--version")
        self.assertEqual(result.returncode, 0)

    def test_help_with_extra_args_is_not_fastpath_and_fails_closed(self):
        env = dict(os.environ)
        env["ENGRAMHALO_CONFIG"] = self.path
        result = subprocess.run(
            [sys.executable, str(TEST_DRIVER), "--help", "--port", "8000"],
            env=env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)


class PortCollisionTests(unittest.TestCase):
    def test_check_port_free_raises_on_bound_port(self):
        import socket as real_socket

        blocker = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        try:
            with self.assertRaises(wrapper.WrapperError):
                wrapper.check_port_free("127.0.0.1", port)
        finally:
            blocker.close()

    def test_check_port_free_ok_when_available(self):
        class FakeSocket:
            def __init__(self, *a, **kw):
                pass

            def setsockopt(self, *a, **kw):
                pass

            def bind(self, addr):
                return None

            def close(self):
                pass

        import unittest.mock as mock
        with mock.patch.object(wrapper.socket, "socket", FakeSocket):
            wrapper.check_port_free("127.0.0.1", 65000)


class LifecycleTests(unittest.TestCase):
    """End-to-end wrapper invocation against the fake engine only."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")
        self.cfg, self.model_path = make_config(self.tmp)
        self.path = write_config(self.tmp, self.cfg)
        self.fake_state_dir = os.path.join(self.tmp, "fake-engine-state")
        os.mkdir(self.fake_state_dir)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def _spawn(self, port):
        env = dict(os.environ)
        env["ENGRAMHALO_CONFIG"] = self.path
        env["FAKE_ENGINE_STATE_DIR"] = self.fake_state_dir
        env["FAKE_ENGINE_IDLE_SECONDS"] = "5"
        argv = [
            sys.executable, str(TEST_DRIVER),
            "-m", self.model_path, "--port", str(port),
            "--ctx-size", "4096", "--parallel", "1",
        ]
        return subprocess.Popen(argv, env=env)

    def _wait_for_cid(self, timeout=10):
        cids_dir = os.path.join(self.cfg["runtime_state_dir"], "cids")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.isdir(cids_dir):
                entries = os.listdir(cids_dir)
                if entries:
                    return os.path.join(cids_dir, entries[0])
            time.sleep(0.05)
        return None

    def _run_with_env(self, port, env_overrides=None):
        env = dict(os.environ)
        env["ENGRAMHALO_CONFIG"] = self.path
        env["FAKE_ENGINE_STATE_DIR"] = self.fake_state_dir
        env["FAKE_ENGINE_IDLE_SECONDS"] = "1"
        if env_overrides:
            env.update(env_overrides)
        argv = [
            sys.executable, str(TEST_DRIVER),
            "-m", self.model_path, "--port", str(port),
            "--ctx-size", "4096", "--parallel", "1",
        ]
        return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=25)

    def test_sigterm_triggers_owned_cleanup_and_exit_code(self):
        proc = self._spawn(18712)
        try:
            cidfile = self._wait_for_cid()
            self.assertIsNotNone(cidfile, "wrapper never created a cidfile")
            deadline = time.time() + 5
            cid = ""
            while time.time() < deadline and not cid:
                if os.path.isfile(cidfile):
                    with open(cidfile, "r", encoding="utf-8") as fh:
                        cid = fh.read().strip()
                time.sleep(0.05)
            self.assertTrue(cid, "cid was never written")

            proc.send_signal(signal.SIGTERM)
            rc = proc.wait(timeout=15)
            self.assertEqual(rc, 128 + signal.SIGTERM)

            state_file = os.path.join(self.fake_state_dir, "state.json")
            with open(state_file, "r", encoding="utf-8") as fh:
                st = json.load(fh)
            self.assertIn(cid, st)
            self.assertFalse(st[cid]["running"])
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def test_port_lock_blocks_second_concurrent_instance(self):
        proc1 = self._spawn(18713)
        try:
            cidfile = self._wait_for_cid()
            self.assertIsNotNone(cidfile)

            result = self._run_with_env(18713)
            self.assertNotEqual(result.returncode, 0)
        finally:
            proc1.send_signal(signal.SIGTERM)
            try:
                proc1.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc1.kill()
                proc1.wait(timeout=5)

    def test_wrapper_handles_fake_engine_normal_exit_without_cid(self):
        result = self._run_with_env(18714, {"FAKE_ENGINE_MODE": "no-cid"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cid", result.stderr.lower())

    def test_wrapper_reuses_lock_per_port_only_and_detects_concurrent_distinct_port(self):
        result1 = self._run_with_env(18716)
        self.assertEqual(result1.returncode, 0)
        result2 = self._run_with_env(18717)
        self.assertEqual(result2.returncode, 0)

    def test_delayed_cid_with_early_term_still_resolves_or_blocks(self):
        # The child writes its cidfile late; a SIGTERM sent before the cid
        # exists must not be silently treated as success. Either the
        # backend genuinely stops (rc reflects the signal) or the run is
        # reported as failed/blocked -- never a false PASS.
        proc = self._spawn_with_mode(18718, "delay-cid")
        try:
            time.sleep(0.05)  # before the fake engine writes its cid
            proc.send_signal(signal.SIGTERM)
            rc = proc.wait(timeout=15)
            self.assertNotEqual(rc, 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def test_normal_client_exit_cleans_up_container(self):
        # A clean run (no signal at all) must still verify the container is
        # gone before reporting success; the fake engine's fallback timeout
        # models a client that exits normally once its container stops.
        result = self._run_with_env(
            18719, {"FAKE_ENGINE_IDLE_SECONDS": "1"})
        self.assertEqual(result.returncode, 0)
        cids_dir = os.path.join(self.cfg["runtime_state_dir"], "cids")
        # cidfile should have been cleaned up on a fully successful run.
        if os.path.isdir(cids_dir):
            self.assertEqual(os.listdir(cids_dir), [])
        active = os.path.join(self.cfg["runtime_state_dir"], "active.json")
        self.assertFalse(os.path.isfile(active))

    def test_inspect_wrong_label_never_stops_and_reports_failure(self):
        result = self._run_with_env(18720, {"FAKE_ENGINE_MODE": "inspect-wrong-label"})
        self.assertNotEqual(result.returncode, 0)
        active = os.path.join(self.cfg["runtime_state_dir"], "active.json")
        self.assertTrue(os.path.isfile(active))

    def test_stop_and_rm_failure_retains_active_marker_nonzero(self):
        result = self._run_with_env(18721, {"FAKE_ENGINE_MODE": "stop-fails"})
        self.assertNotEqual(result.returncode, 0)
        active = os.path.join(self.cfg["runtime_state_dir"], "active.json")
        self.assertTrue(os.path.isfile(active))

    def test_stale_active_marker_blocks_even_other_port(self):
        state_dir = self.cfg["runtime_state_dir"]
        stale = os.path.join(state_dir, "active.json")
        with open(stale, "w", encoding="utf-8") as fh:
            json.dump({"run_uuid": "stale", "name": "n", "cidfile": "x",
                       "engine": "e", "image": "i", "port": 1, "pid": 1,
                       "started_at": 0}, fh)
        try:
            result = self._run_with_env(18722)
            self.assertNotEqual(result.returncode, 0)
        finally:
            os.remove(stale)

    def test_global_lock_blocks_concurrent_run_on_different_ports(self):
        proc1 = self._spawn(18723)
        try:
            cidfile = self._wait_for_cid()
            self.assertIsNotNone(cidfile)
            result = self._run_with_env(18724)
            self.assertNotEqual(result.returncode, 0)
        finally:
            proc1.send_signal(signal.SIGTERM)
            try:
                proc1.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc1.kill()
                proc1.wait(timeout=5)

    def _spawn_with_mode(self, port, mode):
        env = dict(os.environ)
        env["ENGRAMHALO_CONFIG"] = self.path
        env["FAKE_ENGINE_STATE_DIR"] = self.fake_state_dir
        env["FAKE_ENGINE_MODE"] = mode
        env["FAKE_ENGINE_IDLE_SECONDS"] = "5"
        argv = [
            sys.executable, str(TEST_DRIVER),
            "-m", self.model_path, "--port", str(port),
            "--ctx-size", "4096", "--parallel", "1",
        ]
        return subprocess.Popen(argv, env=env)


class DeviceValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="engramhalo-test-")

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp], check=False)

    def test_non_device_file_rejected(self):
        cfg, _ = make_config(self.tmp)
        not_a_device = os.path.join(self.tmp, "not-a-device")
        with open(not_a_device, "w", encoding="utf-8") as fh:
            fh.write("x")
        cfg["gpu_render_device"] = not_a_device
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        with self.assertRaises(wrapper.WrapperError):
            wrapper.load_config()

    def test_real_char_devices_accepted(self):
        cfg, _ = make_config(self.tmp)
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        loaded = wrapper.load_config()
        self.assertEqual(loaded["gpu_render_device"], DEVICE_A)

    def test_arbitrary_chardev_rejected_without_test_override(self):
        # Without the test-only monkeypatch of `_gpu_canonical_ok`, a real
        # character device that is not the canonical /dev/kfd or
        # /dev/dri/renderD<N> path must be rejected. This proves the
        # canonical-path restriction is real production behavior, not just
        # bypassed by the test harness's module-wide patch.
        cfg, _ = make_config(self.tmp)
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        _module_gpu_patch.stop()
        try:
            with self.assertRaises(wrapper.WrapperError):
                wrapper.load_config()
        finally:
            _module_gpu_patch.start()

    def test_removed_fake_gpu_env_var_has_no_effect(self):
        # Regression guard: ENGRAMHALO_FAKE_GPU_DEVICES used to be a
        # production bypass read directly by the wrapper; it has been
        # removed. Setting it must have zero effect on validation, proving
        # there is no residual flag in the shipped code path.
        cfg, _ = make_config(self.tmp)
        path = write_config(self.tmp, cfg)
        os.environ["ENGRAMHALO_CONFIG"] = path
        os.environ["ENGRAMHALO_FAKE_GPU_DEVICES"] = "1"
        _module_gpu_patch.stop()
        try:
            with self.assertRaises(wrapper.WrapperError):
                wrapper.load_config()
        finally:
            _module_gpu_patch.start()
            os.environ.pop("ENGRAMHALO_FAKE_GPU_DEVICES", None)

    def test_block_device_rejected_even_with_test_override(self):
        # A block device must never be accepted, even under the test-only
        # canonical-path patch, and even if its path happened to look
        # canonical.
        cfg, _ = make_config(self.tmp)
        st_mock = os.stat_result(
            (stat_mod.S_IFBLK | 0o600, 0, 0, 1, os.getuid(), os.getgid(), 0, 0, 0, 0))
        with mock.patch.object(wrapper.os, "stat", return_value=st_mock):
            path = write_config(self.tmp, cfg)
            os.environ["ENGRAMHALO_CONFIG"] = path
            with self.assertRaises(wrapper.WrapperError):
                wrapper.load_config()


if __name__ == "__main__":
    unittest.main()
