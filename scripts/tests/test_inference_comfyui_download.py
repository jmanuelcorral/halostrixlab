import fcntl
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


WORKSPACE = Path(__file__).resolve().parents[2] / "workspaces/inference"
sys.path.insert(0, str(WORKSPACE))
import download_comfyui_models as downloader


class ComfyDownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        self.storage = self.data / "comfyui"
        self.storage.mkdir(mode=0o700)
        for name in ("cache", "models"):
            (self.storage / name).mkdir(mode=0o700)
        self.image = "kyuz0/amd-strix-halo-comfyui@sha256:" + "a" * 64
        for name, value in (("DATA", self.data), ("STORAGE", self.storage)):
            patcher = patch.object(downloader.comfyui, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_download_is_pinned_without_gpu_or_service_access(self):
        command = downloader.download_command(self.image)
        for value in (self.image, "--pull=never", "--rm", "--init", "--cap-drop=ALL",
                      "--security-opt=no-new-privileges", "HOME=/download"):
            self.assertIn(value, command)
        for value in ("--device", "--privileged", "--publish", "--restart"):
            self.assertNotIn(value, command)
        self.assertNotIn("docker.sock", " ".join(command))
        self.assertNotIn("gpu.lock", " ".join(command))
        self.assertEqual(command[-1], "set -e; /opt/get_qwen_image.sh 1 bf16; /opt/get_qwen_image.sh 3")

    def test_invalid_image_rejected(self):
        with self.assertRaises(ValueError):
            downloader.download_command("untrusted:latest")

    def test_existing_download_is_refused_before_docker(self):
        with (self.storage / "download.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(downloader.comfyui, "pinned_image", return_value=self.image), patch.object(
                downloader.runtime, "docker"
            ) as docker, self.assertRaisesRegex(ValueError, "already running"):
                downloader.main()
            docker.assert_not_called()

    def test_failure_is_propagated_and_lock_released(self):
        with patch.object(downloader.comfyui, "pinned_image", return_value=self.image), patch.object(
            downloader.runtime, "docker"
        ), patch.object(downloader.subprocess, "run", return_value=Mock(returncode=7)) as run:
            self.assertEqual(downloader.main(), 7)
        self.assertIn("pass_fds", run.call_args.kwargs)
        with (self.storage / "download.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


if __name__ == "__main__":
    unittest.main()
