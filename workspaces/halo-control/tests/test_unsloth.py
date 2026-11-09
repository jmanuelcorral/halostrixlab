import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unsloth
import control


class UnslothTests(unittest.TestCase):
    def setUp(self):
        factory = patch.object(control.llamafactory, 'require_stopped')
        factory.start()
        self.addCleanup(factory.stop)

    def metadata(self):
        return {'id': 'owned-id', 'image': 'sha256:fixture', 'user': f'{os.getuid()}:1000', 'labels': dict(unsloth.EXPECTED_LABELS), 'state': 'exited', 'ports': {'8888/tcp': [{'HostIp': '192.168.10.20', 'HostPort': '8888'}]}}

    def test_inspection_does_not_request_credentials(self):
        metadata = self.metadata()
        with patch.object(unsloth.runtime, 'docker', side_effect=[Mock(stdout='owned-id'), Mock(stdout=json.dumps(metadata)), Mock(stdout=json.dumps(metadata['labels']))]) as docker:
            self.assertEqual(unsloth.inspect()['id'], 'owned-id')
        commands = str(docker.call_args_list)
        self.assertNotIn('.Config.Env', commands)
        self.assertNotIn('password', commands.lower())

    def test_foreign_container_rejected(self):
        metadata = self.metadata()
        metadata['labels']['com.halostrix.project'] = 'foreign'
        with patch.object(unsloth.runtime, 'docker', side_effect=[Mock(stdout='foreign'), Mock(stdout=json.dumps(metadata))]), self.assertRaises(ValueError):
            unsloth.inspect()

    def test_missing_container_is_unavailable(self):
        with patch.object(unsloth, 'inspect', return_value=None):
            self.assertFalse(unsloth.status()['available'])

    def test_lan_link_comes_from_existing_binding(self):
        self.assertEqual(unsloth.endpoint(self.metadata()), 'http://192.168.10.20:8888')

    def test_wildcard_binding_refused(self):
        metadata = self.metadata()
        metadata['ports']['8888/tcp'][0]['HostIp'] = '0.0.0.0'
        with self.assertRaises(ValueError):
            unsloth.endpoint(metadata)

    def test_running_studio_blocks_switch(self):
        metadata = self.metadata()
        metadata['state'] = 'running'
        with patch.object(unsloth, 'inspect', return_value=metadata), self.assertRaises(ValueError):
            unsloth.require_stopped()

    def test_stop_preserves_container_and_data(self):
        metadata = self.metadata()
        metadata['state'] = 'running'
        with patch.object(unsloth, 'inspect', return_value=metadata), patch.object(unsloth.runtime, 'docker') as docker:
            unsloth.stop()
        docker.assert_called_once_with(['stop', '--timeout', '60', 'owned-id'])

    def test_busy_gpu_does_not_start_container(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            with (root / 'gpu.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(unsloth.runtime, 'DATA', root), patch.object(unsloth.runtime, 'docker') as docker, self.assertRaisesRegex(ValueError, 'GPU reserved'):
                    unsloth.start()
                docker.assert_not_called()

    def test_start_without_container_never_recreates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            with patch.object(unsloth.runtime, 'DATA', root), patch.object(unsloth.runtime, 'require_halo'), patch.object(unsloth, 'inspect', return_value=None), patch.object(unsloth.subprocess, 'Popen') as popen, self.assertRaises(ValueError):
                unsloth.start()
            popen.assert_not_called()

    def test_active_studio_blocks_all_gpu_start_actions(self):
        for action in ('gateway-start', 'gateway-restart', 'halogen-load', 'comfyui-start', 'switch-text', 'switch-images'):
            with self.subTest(action=action), patch.object(control.unsloth, 'require_stopped', side_effect=ValueError('Training may be active')), patch.object(control, 'unit') as unit, self.assertRaises(ValueError):
                control.execute(action)
            unit.assert_not_called()

    def test_missing_studio_does_not_stop_existing_services(self):
        with patch.object(control.unsloth, 'require_stopped'), patch.object(control.unsloth, 'status', return_value={'available': False, 'error': 'missing'}), patch.object(control, 'gateway_stop') as stop, self.assertRaises(RuntimeError):
            control.execute('switch-studio')
        stop.assert_not_called()

    def test_switch_studio_orders_stops_before_start(self):
        calls = []
        with patch.object(control.unsloth, 'require_stopped'), patch.object(control.unsloth, 'status', return_value={'available': True, 'health': True}), patch.object(control, 'comfy_stop', side_effect=lambda: calls.append('comfy-stop')), patch.object(control, 'gateway_stop', side_effect=lambda: calls.append('gateway-stop')), patch.object(control, 'unit_state', return_value='inactive'), patch.object(control, 'containers', return_value=[]), patch.object(control, 'unit', side_effect=lambda *args: calls.append(args)):
            control.execute('switch-studio')
        self.assertEqual(calls, ['comfy-stop', 'gateway-stop', ('start', 'unsloth')])


if __name__ == '__main__':
    unittest.main()
