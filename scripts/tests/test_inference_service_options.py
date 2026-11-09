import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'workspaces/inference'))
import comfyui
import service_options


class OptionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patcher = patch.object(service_options, 'DATA', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_defaults_and_unknown_keys(self):
        self.assertEqual(service_options.read('comfyui'), service_options.DEFAULTS['comfyui'])
        for values in ({}, [], dict(service_options.DEFAULTS['comfyui'], arbitrary=True), dict(service_options.DEFAULTS['comfyui'], reserve_vram=True), dict(service_options.DEFAULTS['comfyui'], cache_none=1)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                service_options.validate('comfyui', values)

    def test_private_file_and_symlink_required(self):
        path = self.root / 'comfyui-options.json'
        path.write_text('{}')
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            service_options.read('comfyui')
        path.unlink()
        path.symlink_to(self.root / 'missing')
        with self.assertRaises((ValueError, FileNotFoundError)):
            service_options.read('comfyui')

    def test_exclusive_settings_lease_and_release(self):
        for service in ('comfyui', 'llamafactory', 'gateway'):
            with service_options.lease(service), self.assertRaises(ValueError):
                with service_options.lease(service):
                    self.fail('Second writer entered')
            with service_options.lease(service):
                pass

    def test_changed_comfy_options_reach_command(self):
        values = dict(service_options.DEFAULTS['comfyui'], reserve_vram=6, cache_none=False, bf16_vae=False, disable_smart_memory=False, aotriton=False, hipblaslt=False)
        path = self.root / 'comfyui-options.json'
        path.write_text(json.dumps(values))
        path.chmod(0o600)
        with patch.object(comfyui.runtime, 'checked_mount', side_effect=lambda value: value):
            command = comfyui.run_command('kyuz0/amd-strix-halo-comfyui@sha256:' + 'a' * 64, [])
        self.assertEqual(command[command.index('--reserve-vram') + 1], '6')
        self.assertIn('TORCH_BLAS_PREFER_HIPBLASLT=0', command)
        self.assertIn('TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=0', command)
        for flag in ('--cache-none', '--bf16-vae', '--disable-smart-memory', '--gpu-only'):
            self.assertNotIn(flag, command)

    def test_settings_lease_prevents_start(self):
        with service_options.lease('comfyui'), patch.object(comfyui, 'pinned_image'), patch.object(comfyui, 'DATA', self.root), patch.object(comfyui.subprocess, 'Popen') as popen, self.assertRaisesRegex(ValueError, 'settings'):
            comfyui.start()
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
