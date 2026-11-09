import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


WORKSPACE = Path(__file__).resolve().parents[2] / "workspaces/inference"
sys.path.insert(0, str(WORKSPACE))
import comfyui


class ComfyUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.storage = self.data / "comfyui"
        self.storage.mkdir(mode=0o700)
        for name in ("models", "input", "output", "user", "cache"):
            (self.storage / name).mkdir(mode=0o700)
        self.image = "kyuz0/amd-strix-halo-comfyui@sha256:" + "a" * 64
        reference = self.storage / "image.ref"
        reference.write_text(self.image + "\n")
        reference.chmod(0o600)
        options = patch.object(comfyui.service_options, 'DATA', self.data)
        options.start()
        self.addCleanup(options.stop)
        for name, value in (("DATA", self.data), ("STORAGE", self.storage)):
            patcher = patch.object(comfyui, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_command_is_manual_local_pinned_and_isolated(self):
        command = comfyui.run_command(self.image, [Path("/dev/null")])
        for argument in (self.image, "--pull=never", "--rm", "--init", "--cap-drop=ALL",
                         "--security-opt=no-new-privileges", "127.0.0.1:8188:8188",
                         "--disable-mmap", "--bf16-vae", "--cache-none", "--reserve-vram",
                         "--disable-smart-memory", "HF_HUB_OFFLINE=1"):
            self.assertIn(argument, command)
        self.assertEqual(command[command.index("--reserve-vram") + 1], "4")
        for forbidden in ("--privileged", "--restart", "--detach", "--ipc=host", "--gpu-only", "--highvram"):
            self.assertNotIn(forbidden, command)
        self.assertNotIn("docker.sock", " ".join(command))
        self.assertIn(f"{os.getuid()}:{os.getgid()}", command)
        self.assertIn("TORCH_BLAS_PREFER_HIPBLASLT=1", command)
        self.assertTrue(any("dst=/opt/ComfyUI/models,readonly" in item for item in command))

    def test_private_lan_bind_is_explicit(self):
        command = comfyui.run_command(self.image, [], "192.168.10.20")
        self.assertIn("192.168.10.20:8188:8188", command)
        self.assertNotIn("127.0.0.1:8188:8188", command)

    def test_public_wildcard_and_invalid_bind_rejected(self):
        for address in ("0.0.0.0", "8.8.8.8", "::", "localhost", "192.168.1.2;id", "169.254.1.1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                comfyui.run_command(self.image, [], address)

    def test_reference_rejects_tag_and_foreign_image(self):
        for image in (comfyui.IMAGE, "foreign/comfyui@sha256:" + "a" * 64, "$(id)"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                comfyui.run_command(image, [])

    def test_private_reference(self):
        self.assertEqual(comfyui.pinned_image(), self.image)
        (self.storage / "image.ref").chmod(0o644)
        with self.assertRaises(ValueError):
            comfyui.pinned_image()

    def test_prepare_preserves_existing_pin_without_pull(self):
        with patch.object(comfyui.runtime, "docker") as docker, patch.object(comfyui.subprocess, "run") as run:
            comfyui.prepare()
        docker.assert_called_once_with(["image", "inspect", self.image])
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["docker", "run"])
        self.assertIn("--network=none", command)
        self.assertNotIn("--device", command)
        self.assertIn("if not (target / item.name).exists()", command[-1])

    def test_busy_gpu_refused_before_docker(self):
        with (self.data / "gpu.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(comfyui.runtime, "docker") as docker, self.assertRaisesRegex(ValueError, "GPU reserved"):
                comfyui.start()
            docker.assert_not_called()

    def test_active_container_refused_without_stopping(self):
        with patch.object(comfyui.runtime, "require_halo"), patch.object(
            comfyui.runtime, "docker", return_value=Mock(stdout="owned-id\n")
        ), patch.object(comfyui.runtime, "stop") as stop, self.assertRaisesRegex(ValueError, "active"):
            comfyui.start()
        stop.assert_not_called()
        with (self.data / "gpu.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_process_exit_stops_owned_container_and_releases_lock(self):
        child = Mock(returncode=0)
        child.poll.return_value = 0
        with patch.object(comfyui.runtime, "require_halo"), patch.object(
            comfyui.runtime, "docker", return_value=Mock(stdout="")
        ), patch.object(comfyui.runtime, "inspect_owned", return_value=None), patch.object(
            comfyui.runtime, "devices", return_value=[Path("/dev/null")]
        ), patch.object(comfyui.subprocess, "Popen", return_value=child) as popen, patch.object(
            comfyui.runtime, "stop"
        ) as stop:
            self.assertEqual(comfyui.start(), 0)
        self.assertIn("pass_fds", popen.call_args.kwargs)
        stop.assert_called_once_with(comfyui.NAME)
        with (self.data / "gpu.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_failed_launch_cleans_up(self):
        with patch.object(comfyui.runtime, "require_halo"), patch.object(
            comfyui.runtime, "docker", return_value=Mock(stdout="")
        ), patch.object(comfyui.runtime, "inspect_owned", return_value=None), patch.object(
            comfyui.runtime, "devices", return_value=[]
        ), patch.object(comfyui.subprocess, "Popen", side_effect=OSError("launch failed")), patch.object(
            comfyui.runtime, "stop"
        ) as stop, self.assertRaises(OSError):
            comfyui.start()
        stop.assert_called_once_with(comfyui.NAME)

    def test_status_stopped_does_not_create_container(self):
        with patch.object(comfyui.runtime, "inspect_owned", return_value=None), patch.object(comfyui.runtime, "docker") as docker:
            comfyui.status()
        docker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
