import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control
import laya_control


class LayaControlTests(unittest.TestCase):
    def test_stopped_status_never_loads_model(self):
        with patch.object(laya_control, 'configured'), patch.object(laya_control.laya_runtime, 'owned', return_value=None), patch.object(laya_control, 'backend_health') as health:
            value = laya_control.status(control)
        self.assertEqual(value['state'], 'stopped')
        self.assertTrue(value['available'])
        health.assert_not_called()

    def test_running_status_checks_backend_not_autoload_route(self):
        with patch.object(laya_control, 'configured'), patch.object(laya_control.laya_runtime, 'owned', return_value={'State': {'Status': 'running'}}), patch.object(laya_control, 'backend_health', return_value=True), patch.object(control, 'http') as http:
            self.assertTrue(laya_control.status(control)['health'])
            http.assert_not_called()

    def test_unknown_installation_is_unavailable(self):
        with patch.object(laya_control, 'configured', side_effect=ValueError('private details')):
            value = laya_control.status(control)
        self.assertFalse(value['available'])
        self.assertNotIn('private details', value['error'])

    def test_start_only_loads_laya_in_existing_gateway(self):
        with patch.object(laya_control, 'configured'), patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'http', return_value={'status': 'ok', 'device': 'cpu'}) as http, patch.object(control, 'unit') as unit, patch.object(control.unsloth, 'require_stopped') as gpu:
            control.execute('laya-start')
            http.assert_called_once_with('/upstream/laya/health', timeout=180)
            unit.assert_not_called()
            gpu.assert_not_called()

    def test_inactive_gateway_does_not_start_or_stop_any_service(self):
        with patch.object(laya_control, 'configured'), patch.object(control, 'unit_state', return_value='inactive'), patch.object(control, 'http') as http, self.assertRaises(RuntimeError):
            control.execute('laya-start')
        http.assert_not_called()

    def test_busy_refuses_stop(self):
        with patch.object(laya_control, 'configured'), patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'inflight', return_value=1), patch.object(control, 'http') as http, self.assertRaises(RuntimeError):
            control.execute('laya-stop')
        http.assert_not_called()

    def test_stop_targets_only_laya(self):
        with patch.object(laya_control, 'configured'), patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'inflight', return_value=0), patch.object(control, 'http') as http, patch.object(laya_control.laya_runtime, 'owned', return_value=None):
            control.execute('laya-stop')
        http.assert_called_once_with('/api/models/unload/laya', {}, timeout=100)

    def test_stop_checks_result(self):
        with patch.object(laya_control, 'configured'), patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'inflight', return_value=0), patch.object(control, 'http'), patch.object(laya_control.laya_runtime, 'owned', return_value={'State': {'Status': 'running'}}), self.assertRaises(RuntimeError):
            control.execute('laya-stop')


if __name__ == '__main__':
    unittest.main()
