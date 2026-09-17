import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


WORKSPACE = Path(__file__).resolve().parents[2] / "workspaces/inference"
sys.path.insert(0, str(WORKSPACE))
import runtime
import manage


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.models = self.root / "models"
        self.models.mkdir()
        (self.models / "model.gguf").write_bytes(b"fixture")
        self.profile = {
            "enabled": True, "kind": "llamacpp-vulkan",
            "image": "registry.example/runtime@sha256:" + "a" * 64,
            "model_dir": str(self.models), "model": "model.gguf",
            "upstream_model": "coder-local", "context": 32768, "output": 8192,
        }
        self.config = self.root / "profiles.json"
        self.save()

    def save(self):
        self.config.write_text(json.dumps({"profiles": {"coder": self.profile}}))
        self.config.chmod(0o600)

    def test_load_enabled(self):
        self.assertEqual(runtime.load_profiles(self.config)["coder"], self.profile)

    def test_disabled_placeholders_are_not_loaded(self):
        example = json.loads((WORKSPACE / "profiles.example.json").read_text())
        example["profiles"]["coder"] = self.profile
        self.config.write_text(json.dumps(example))
        self.assertEqual(list(runtime.load_profiles(self.config)), ["coder"])

    def test_empty_catalog_fails_closed(self):
        self.profile["enabled"] = False
        self.save()
        with self.assertRaises(ValueError):
            runtime.load_profiles(self.config)

    def test_private_permissions(self):
        self.config.chmod(0o644)
        with self.assertRaises(ValueError):
            runtime.load_profiles(self.config)

    def test_symlink_config_rejected(self):
        link = self.root / "link.json"
        link.symlink_to(self.config)
        with self.assertRaises(ValueError):
            runtime.load_profiles(link)

    def test_bad_profiles(self):
        changes = [
            {"image": "runtime:latest"}, {"image": "runtime@sha256:<DIGEST>"},
            {"context": True}, {"context": 8192}, {"output": 0},
            {"kind": "shell"}, {"model": "../model.gguf"},
            {"model": "/etc/passwd"}, {"upstream_model": "${EVIL}"},
            {"model_dir": "/home"}, {"model_dir": str(Path.home())},
            {"model_dir": str(self.root / ".ssh")}, {"arbitrary": "field"},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                runtime.validate_profile("coder", dict(self.profile, **change))

    def test_model_symlink_escape(self):
        outside = self.root / "outside.gguf"
        outside.write_bytes(b"private")
        (self.models / "escape.gguf").symlink_to(outside)
        with self.assertRaises(ValueError):
            runtime.validate_profile("coder", dict(self.profile, model="escape.gguf"))

    def test_identifier_injection_rejected(self):
        for name in ("../coder", "coder;id", "coder\n", "UPPER", "${PORT}"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                runtime.validate_profile(name, self.profile)

    def command(self, profile=None):
        return runtime.run_command("coder", profile or self.profile, 18100, [Path("/dev/null")])

    def test_docker_bound_loopback_pinned_readonly(self):
        command = self.command()
        self.assertIn("127.0.0.1:18100:8080", command)
        self.assertIn("--pull=never", command)
        self.assertIn("--rm", command)
        self.assertIn("--cap-drop=ALL", command)
        self.assertIn("--security-opt=no-new-privileges", command)
        self.assertIn(self.profile["image"], command)
        self.assertTrue(any("dst=/models,readonly" in item for item in command))
        self.assertNotIn("--privileged", command)
        self.assertNotIn("--ipc=host", command)
        self.assertNotIn("docker.sock", " ".join(command))
        self.assertIn("--jinja", command)

    def test_rocm_has_explicit_ipc(self):
        command = self.command(dict(self.profile, kind="llamacpp-rocm"))
        self.assertIn("--ipc=host", command)
        self.assertIn("memlock=-1:-1", command)

    def test_llamacpp_loading_contract_is_explicit(self):
        self.assertIn("--no-mmap", self.command())
        for kind in ("llamacpp-vulkan", "llamacpp-rocm"):
            profile = dict(self.profile, kind=kind, load_mode="none")
            runtime.validate_profile("coder", profile)
            command = self.command(profile)
            self.assertNotIn("--no-mmap", command)
            self.assertEqual(command[command.index("--load-mode") + 1], "none")
        for mode in (None, True, "mmap", "none;id", ["none"]):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                runtime.validate_profile("coder", dict(self.profile, load_mode=mode))
        for kind in ("halogen", "vllm"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                runtime.validate_profile("coder", dict(self.profile, kind=kind, load_mode="none"))

    def test_halogen_retains_entrypoint_and_no_download(self):
        profile = dict(self.profile, kind="halogen", halogen_checkpoint="model.gguf")
        command = self.command(profile)
        self.assertNotIn("--entrypoint", command)
        self.assertEqual(command[-1], "all")
        for setting in ("HALOGEN_DOWNLOAD=", "HALOGEN_KV_SLOTS=1",
                        "HALOGEN_API_PORT=8080", "HALOGEN_KV_POOL_POSITIONS=32768"):
            self.assertIn(setting, command)

    def test_halogen_explicit_artifacts_and_arena(self):
        (self.models / "overlay.hgn").write_bytes(b"fixture")
        tokenizer = self.models / "tokenizer"
        tokenizer.mkdir()
        (tokenizer / "tokenizer.json").write_text("{}")
        profile = dict(self.profile, kind="halogen", halogen_checkpoint="model.gguf",
                       halogen_overlay="overlay.hgn", halogen_tokenizer="tokenizer",
                       halogen_max_tok=32768)
        runtime.validate_profile("halogen", profile)
        command = self.command(profile)
        for setting in ("HALOGEN_CK_OVERLAY=/models/overlay.hgn",
                        "HALOGEN_TOKENIZER=/models/tokenizer", "HALOGEN_MAX_TOK=32768"):
            self.assertIn(setting, command)
        for key in ("halogen_checkpoint", "halogen_overlay", "halogen_tokenizer"):
            for value in ("../outside", "/absolute", "${SECRET}", "bad\npath", "missing", "", None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    runtime.validate_profile("halogen", dict(profile, **{key: value}))
        for value in (True, 0, -1, 32769, "16384"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.validate_profile("halogen", dict(profile, halogen_max_tok=value))
        outside = self.root / "outside.json"
        outside.write_text("{}")
        (tokenizer / "tokenizer.json").unlink()
        (tokenizer / "tokenizer.json").symlink_to(outside)
        with self.assertRaises(ValueError):
            runtime.validate_profile("halogen", profile)
        for key, value in (("halogen_overlay", "overlay.hgn"),
                           ("halogen_tokenizer", "tokenizer"), ("halogen_max_tok", 16384)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                runtime.validate_profile("coder", dict(self.profile, **{key: value}))

    def test_vllm_cache_and_protected_flags(self):
        cache = self.root / "cache"
        cache.mkdir()
        profile = dict(self.profile, kind="vllm", cache_dir=str(cache),
                       vllm_args=["--enforce-eager"])
        runtime.validate_profile("vllm", profile)
        command = self.command(profile)
        self.assertIn("serve", command)
        self.assertIn("HF_HUB_OFFLINE=1", command)
        self.assertIn("--enforce-eager", command)
        for argument in ("--host=0.0.0.0", "--trust-remote-code", "--api-key", "--port"):
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                runtime.validate_profile("vllm", dict(profile, vllm_args=[argument]))
        with self.assertRaises(ValueError):
            runtime.validate_profile("vllm", dict(profile, cache_dir=str(self.models)))

    def test_stop_uses_owned_id(self):
        responses = [subprocess.CompletedProcess([], 0, "short-id\n", ""),
                     subprocess.CompletedProcess([], 0, json.dumps([{
                         "Id": "full-id", "Config": {"Labels": {runtime.LABEL: str(runtime.ROOT)}}}]), ""),
                     subprocess.CompletedProcess([], 0, "", "")]
        with patch.object(runtime, "docker", side_effect=responses) as mocked:
            runtime.stop("coder")
        self.assertEqual(mocked.call_args.args[0], ["stop", "--time", "60", "full-id"])

    def test_stop_foreign_container_rejected(self):
        responses = [subprocess.CompletedProcess([], 0, "short-id\n", ""),
                     subprocess.CompletedProcess([], 0, json.dumps([{
                         "Id": "full-id", "Config": {"Labels": {}}}]), "")]
        with patch.object(runtime, "docker", side_effect=responses) as mocked:
            with self.assertRaises(ValueError):
                runtime.stop("coder")
        self.assertEqual(mocked.call_count, 2)

    def test_stop_absent_noop(self):
        with patch.object(runtime, "docker", return_value=subprocess.CompletedProcess([], 0, "", "")) as mocked:
            runtime.stop("coder")
        self.assertEqual(mocked.call_count, 1)

    def test_stop_does_not_require_surviving_model_files(self):
        arguments = ["runtime.py", "stop", "coder", "--config", "/missing/profiles.json"]
        with patch.object(sys, "argv", arguments), patch.object(runtime, "stop") as mocked:
            self.assertEqual(runtime.main(), 0)
        mocked.assert_called_once_with("coder")

    def test_render_exclusive_authenticated_no_autoload(self):
        result = manage.render(self.config)
        self.assertEqual(result["globalConcurrencyLimit"], 1)
        self.assertEqual(result["apiKeys"], ["${env.HALOSTRIX_ADMIN_KEY}", "${env.HALOSTRIX_CLIENT_KEY}"])
        self.assertTrue(result["routing"]["router"]["settings"]["groups"]["gpu"]["exclusive"])
        self.assertNotIn("hooks", result)
        self.assertIn("--port 18100", result["models"]["coder"]["cmd"])
        self.assertIn(" stop ", result["models"]["coder"]["cmdStop"])
        self.assertFalse(result["sendLoadingState"])

    def test_render_publishes_effective_profile_limits(self):
        for context, output in ((32768, 8192), (16384, 2048)):
            self.profile.update(context=context, output=output)
            self.save()
            model = manage.render(self.config)["models"]["coder"]
            self.assertEqual(model["capabilities"], {"context": context})
            self.assertEqual(model["metadata"], {"context_length": context,
                                                 "max_output_tokens": output})
            self.assertNotIn("setParams", model)

    def test_generated_config_validated_by_real_binary(self):
        binary = WORKSPACE / "data/bin/llama-swap"
        if not binary.exists():
            self.skipTest("Optional pinned llama-swap binary not installed")
        config = self.root / "swap.yaml"
        config.write_text(json.dumps(manage.render(self.config)))
        environment = dict(os.environ, HALOSTRIX_ADMIN_KEY="a" * 48, HALOSTRIX_CLIENT_KEY="b" * 48)
        result = subprocess.run([str(binary), "-config", str(config), "-validate"],
                                env=environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_start_refuses_busy_lease_before_docker(self):
        import fcntl
        directory = self.root / "lease"
        directory.mkdir(mode=0o700)
        with (directory / "gpu.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(runtime, "DATA", directory), patch.object(runtime, "docker") as mocked:
                with self.assertRaisesRegex(ValueError, "lease"):
                    runtime.start("coder", self.profile, 18100)
                mocked.assert_not_called()

    def test_start_releases_lease_after_preflight_failure(self):
        import fcntl
        directory = self.root / "lease"
        directory.mkdir(mode=0o700)
        with patch.object(runtime, "DATA", directory), patch.object(runtime, "require_halo", side_effect=ValueError("host")):
            with self.assertRaisesRegex(ValueError, "host"):
                runtime.start("coder", self.profile, 18100)
        with (directory / "gpu.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_caddy_edge_has_explicit_allowlist(self):
        text = (WORKSPACE / "Caddyfile").read_text()
        self.assertIn('header Authorization "Bearer {$HALO_CLIENT_KEY}"', text)
        self.assertIn('respond "Forbidden" 403', text)
        self.assertIn("flush_interval -1", text)
        self.assertNotIn("/ui", text)
        self.assertNotIn("/api/", text)
        compose = (WORKSPACE / "compose.yaml").read_text()
        self.assertNotIn("docker.sock", compose)
        self.assertNotIn("/dev/dri", compose)
        self.assertIn("read_only: true", compose)

    def test_cockpit_halogen_uses_host_device_group_ids(self):
        import cockpit_launch
        from types import SimpleNamespace

        arguments = ["--group-add", "video", "--group-add=render", "--ipc=host"]
        with patch.object(cockpit_launch.Path, "stat", side_effect=[
            SimpleNamespace(st_gid=983), SimpleNamespace(st_gid=987)
        ]):
            result = cockpit_launch.halogen_device_groups("docker", arguments)
        self.assertEqual(result, ["--group-add", "983", "--group-add=987", "--ipc=host"])
        self.assertEqual(arguments[1], "video")
        with patch.object(cockpit_launch.Path, "stat") as metadata:
            self.assertEqual(cockpit_launch.halogen_device_groups("podman", arguments), arguments)
            metadata.assert_not_called()
        with patch.object(cockpit_launch.Path, "stat", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                cockpit_launch.halogen_device_groups("docker", arguments)
        self.assertEqual(cockpit_launch.halogen_device_groups("docker", ["--group-add", "123"]),
                         ["--group-add", "123"])

    def test_cockpit_launcher_preserves_private_environment_and_lock(self):
        directory = self.root / "cockpit"
        directory.mkdir(mode=0o700)
        responses = [subprocess.CompletedProcess([], 0, "", ""),
                     subprocess.CompletedProcess([], 0)]
        with patch.object(manage, "DATA", directory), patch.object(manage.subprocess, "run", side_effect=responses) as run:
            self.assertEqual(manage.cockpit(), 0)
        invocation = run.call_args
        self.assertEqual(invocation.args[0], [str(directory / "cockpit-venv/bin/python"),
                                              str(WORKSPACE / "cockpit_launch.py")])
        self.assertEqual(invocation.kwargs["env"]["DBX_CONTAINER_MANAGER"], "docker")
        self.assertEqual(invocation.kwargs["env"]["XDG_CONFIG_HOME"], str(directory / "cockpit-config"))
        self.assertEqual(len(invocation.kwargs["pass_fds"]), 1)

    def test_private_directory_and_exclusive_write(self):
        directory = self.root / "private"
        runtime.private_directory(directory)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        target = directory / "secret"
        runtime.write_private(target, "first")
        with self.assertRaises(FileExistsError):
            runtime.write_private(target, "overwrite")
        self.assertEqual(target.read_text(), "first")


if __name__ == "__main__":
    unittest.main()
