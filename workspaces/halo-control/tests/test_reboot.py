from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control
import reboot


class RebootTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for patcher in (patch.object(control, 'DATA', self.root), patch.object(reboot, 'package_idle'), patch.object(reboot.unsloth, 'require_stopped'), patch.object(reboot.llamafactory, 'require_stopped')):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_stops_all_managed_services_and_verifies_before_ready(self):
        with patch.object(control, 'unit') as unit, patch.object(control, 'unit_state', return_value='inactive'), patch.object(control, 'containers', side_effect=[['halostrix-flash-halogen'], []]), patch.object(reboot.unsloth, 'stop') as studio, patch.object(reboot.llamafactory, 'stop') as factory, patch.object(reboot.llamafactory, 'metadata', return_value={'state': 'running', 'id': 'legacy-id'}), patch.object(reboot.unsloth.runtime, 'stop') as stop, patch.object(reboot.unsloth.runtime, 'docker') as docker:
            reboot.prepare(control)
            self.assertEqual(reboot.pending(control)['phase'], 'ready')
        self.assertEqual([call.args for call in unit.call_args_list], [('stop', name) for name in ('gateway', 'comfyui', 'unsloth', 'llamafactory')])
        studio.assert_called_once()
        factory.assert_called_once()
        stop.assert_called_once_with('flash-halogen')
        docker.assert_called_once_with(['stop', '--timeout', '60', 'legacy-id'])

    def test_active_packages_never_stop_services(self):
        with patch.object(reboot, 'package_idle', side_effect=ValueError('packages active')), patch.object(control, 'unit') as unit, self.assertRaises(ValueError):
            reboot.prepare(control)
        unit.assert_not_called()

    def test_failed_stop_clears_reservation_and_never_marks_ready(self):
        with patch.object(control, 'unit', side_effect=RuntimeError('stop failed')), self.assertRaises(RuntimeError):
            reboot.prepare(control)
        self.assertIsNone(reboot.pending(control))

    def reserve(self):
        control.save_cache('reboot', {'phase': 'ready', 'boot_id': reboot.boot_id(), 'expires': reboot.time.time() + 300, 'token': 'fixture'})

    def test_reservation_blocks_other_operations(self):
        self.reserve()
        with self.assertRaisesRegex(ValueError, 'Reinicio'):
            with control.operation_lock():
                pass

    def test_verification_requires_token_and_stopped_services(self):
        self.reserve()
        with self.assertRaises(ValueError):
            reboot.verify(control, 'wrong')
        with patch.object(control, 'unit_state', return_value='active'), self.assertRaises(ValueError):
            reboot.verify(control, 'fixture')
        with patch.object(control, 'unit_state', return_value='inactive'), patch.object(control, 'containers', return_value=[]):
            self.assertTrue(reboot.verify(control, 'fixture')['ready'])
        reboot.release(control, 'fixture')
        self.assertIsNone(reboot.pending(control))

    def test_new_boot_or_expiration_invalidates_reservation(self):
        self.reserve()
        with patch.object(reboot, 'boot_id', return_value='new-boot'):
            self.assertIsNone(reboot.pending(control))
        with patch.object(reboot.time, 'time', return_value=999999999999):
            self.assertIsNone(reboot.pending(control))


if __name__ == '__main__':
    unittest.main()
