import fcntl
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llamafactory as factory
import control


class FactoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / 'ai/llama-factory/data'
        self.data.mkdir(parents=True)
        for name in factory.DIRECTORIES:
            (self.data / name).mkdir()
        self.value = {'image':'sha256:' + 'a'*64, 'bind':'192.168.10.20', 'data_root':str(self.data)}
        for patcher in (patch.object(factory, 'validate_image'), patch.object(factory.Path, 'home', return_value=self.root), patch.object(factory.service_options, 'DATA', self.root)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_nonroot_narrow_mounts_private_bind(self):
        command = factory.run_command(self.value, [Path('/dev/null')])
        for argument in ('--rm','--pull=never','--cap-drop=ALL','--security-opt=no-new-privileges',f'{os.getuid()}:{os.getgid()}','192.168.10.20:7860:7860'):
            self.assertIn(argument, command)
        for argument in ('--privileged','--network=host','--restart'):
            self.assertNotIn(argument, command)
        self.assertNotIn('docker.sock',str(command))
        self.assertEqual(command.count('--mount'),9)
        self.assertIn(f'type=bind,src={self.data / "cache"},dst=/workspace/llamaboard_cache', command)
        self.assertIn(f'type=bind,src={self.data / "config"},dst=/workspace/llamaboard_config', command)
        self.assertEqual(command[-1],'webui')

    def test_options_change_real_command(self):
        options = dict(factory.service_options.DEFAULTS['llamafactory'], shm_gib=8, hf_offline=True, tokenizers_parallelism=True)
        with patch.object(factory.service_options, 'read', return_value=options):
            command = factory.run_command(self.value, [])
        self.assertIn('--shm-size=8g', command)
        self.assertIn('HF_HUB_OFFLINE=1', command)
        self.assertIn('TRANSFORMERS_OFFLINE=1', command)
        self.assertIn('TOKENIZERS_PARALLELISM=true', command)

    def test_wildcard_and_public_bind_rejected(self):
        for address in ('0.0.0.0','8.8.8.8','::'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                factory.validate_config(dict(self.value,bind=address))

    def test_other_data_root_rejected(self):
        with self.assertRaises(ValueError):
            factory.validate_config(dict(self.value,data_root=str(self.root)))

    def test_symlink_mount_rejected(self):
        path=self.data/'models'
        path.rmdir()
        path.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):
            factory.validate_config(self.value)

    def test_stop_only_managed_id(self):
        with patch.object(factory,'metadata',return_value={'state':'running','id':'owned-id'}) as inspect,patch.object(factory.runtime,'docker') as docker:
            factory.stop()
        inspect.assert_called_once_with(factory.NAME)
        docker.assert_called_once_with(['stop','--timeout','60','owned-id'])

    def test_legacy_active_blocks_switch(self):
        with patch.object(factory,'metadata',side_effect=[{'state':'running'}]),self.assertRaises(ValueError):
            factory.require_stopped()

    def test_lease_refuses_start(self):
        with (self.root/'gpu.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch.object(factory,'config',return_value=self.value),patch.object(factory.runtime,'DATA',self.root),patch.object(factory.subprocess,'Popen') as popen,self.assertRaisesRegex(ValueError,'GPU reserved'):
                factory.start()
            popen.assert_not_called()

    def test_factory_blocks_other_gpu_start(self):
        for action in ('gateway-start','halogen-load','switch-text','comfyui-start','switch-images','unsloth-start','switch-studio'):
            with self.subTest(action=action),patch.object(control.unsloth,'require_stopped'),patch.object(factory,'require_stopped',side_effect=ValueError('training')),patch.object(control,'unit') as unit,self.assertRaises(ValueError):
                control.execute(action)
            unit.assert_not_called()

    def test_missing_config_does_not_stop_gateway(self):
        with patch.object(control.unsloth,'require_stopped'),patch.object(factory,'require_stopped'),patch.object(factory,'status',return_value={'available':False,'error':'not prepared'}),patch.object(control,'gateway_stop') as stop,self.assertRaises(RuntimeError):
            control.execute('switch-llamafactory')
        stop.assert_not_called()

    def test_failed_studio_stop_never_starts_factory(self):
        with patch.object(factory, 'status', return_value={'available': True}), patch.object(control, 'comfy_stop'), patch.object(control, 'gateway_stop'), patch.object(control, 'unit') as unit, patch.object(control.unsloth, 'stop', side_effect=ValueError('stop failed')), self.assertRaises(ValueError):
            control.execute('switch-llamafactory')
        unit.assert_called_once_with('stop', 'unsloth')

    def test_running_http_failure_retains_url_and_explains_health(self):
        with patch.object(factory, 'metadata', side_effect=[None, {'state': 'running'}]), patch.object(factory, 'config', return_value=self.value), patch.object(factory.urllib.request, 'build_opener', return_value=Mock(open=Mock(side_effect=OSError('offline')))):
            value = factory.status()
        self.assertEqual(value['url'], 'http://192.168.10.20:7860')
        self.assertFalse(value['health'])
        self.assertIn('HTTP', value['error'])

    def test_switch_order(self):
        calls=[]
        with patch.object(control.unsloth,'require_stopped'),patch.object(control.unsloth,'stop',side_effect=lambda:calls.append('studio-stop')),patch.object(factory,'require_stopped'),patch.object(factory,'status',return_value={'available':True,'health':True}),patch.object(control,'comfy_stop',side_effect=lambda:calls.append('comfy')),patch.object(control,'gateway_stop',side_effect=lambda:calls.append('gateway')),patch.object(control,'containers',return_value=[]),patch.object(control,'unit_state',return_value='inactive'),patch.object(control,'unit',side_effect=lambda *args:calls.append(args)):
            control.execute('switch-llamafactory')
        self.assertEqual(calls,['comfy','gateway',('stop','unsloth'),'studio-stop',('start','llamafactory')])


if __name__=='__main__':
    unittest.main()
