import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import control
import metrics
import maintenance
import install


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data = Path(self.temporary.name)
        self.data.chmod(0o700)
        patcher = patch.object(control, 'DATA', self.data)
        patcher.start()
        self.addCleanup(patcher.stop)
        studio = patch.object(control.unsloth, 'require_stopped')
        studio.start()
        self.addCleanup(studio.stop)
        factory = patch.object(control.llamafactory, 'require_stopped')
        factory.start()
        self.addCleanup(factory.stop)

    def configure(self, **values):
        path = self.data / 'config.json'
        path.write_text(json.dumps(dict(control.DEFAULT, **values)))
        path.chmod(0o600)

    def test_default_is_loopback(self):
        self.assertEqual(control.config()['gateway_url'], 'http://127.0.0.1:18080')
        self.assertEqual(control.config()['comfyui_bind'], '127.0.0.1')

    def test_invalid_origins_and_keys_rejected(self):
        for value in ('http://8.8.8.8:80', 'http://user:secret@127.0.0.1', 'file:///etc/passwd', 'http://127.0.0.1/path'):
            self.configure(gateway_url=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                control.config()

    def test_unsafe_bind_rejected(self):
        for value in ('0.0.0.0', '8.8.8.8', '::', '192.168.1.2;id'):
            self.configure(comfyui_bind=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                control.config()

    def test_unsafe_permissions_rejected(self):
        self.configure()
        (self.data / 'config.json').chmod(0o644)
        with self.assertRaises(ValueError):
            control.config()

    def test_ssh_alias_cannot_be_command_or_option(self):
        for name in ('-oProxyCommand=id', 'user@host', 'host;id', '/etc/passwd'):
            self.configure(ssh_hosts=[name])
            with self.subTest(name=name), self.assertRaises(ValueError):
                control.config()

    def test_lock_rejects_second_operation(self):
        with control.operation_lock():
            with self.assertRaises(ValueError):
                with control.operation_lock():
                    pass

    def test_action_allowlist(self):
        with self.assertRaises(ValueError):
            control.submit('shell;id')
        with self.assertRaises(ValueError):
            control.execute('delete-everything')

    def test_unit_allowlist(self):
        with self.assertRaises(ValueError):
            control.unit('start', 'sshd')

    def test_comfy_busy_refuses_stop(self):
        with patch.object(control, 'containers', return_value=['halostrix-comfyui-manual']), patch.object(control, 'http', return_value={'queue_running': [1], 'queue_pending': []}), patch.object(control, 'unit') as unit:
            with self.assertRaises(RuntimeError):
                control.comfy_stop()
            unit.assert_not_called()

    def test_unload_busy_refuses(self):
        with patch.object(control, 'inflight', return_value=1), patch.object(control, 'http') as http:
            with self.assertRaises(RuntimeError):
                control.execute('halogen-unload')
            http.assert_not_called()

    def test_start_images_does_not_stop_gateway_implicitly(self):
        with patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'unit') as unit:
            with self.assertRaises(RuntimeError):
                control.execute('comfyui-start')
            unit.assert_not_called()

    def test_start_text_refuses_existing_comfy(self):
        with patch.object(control, 'containers', return_value=['halostrix-comfyui-manual']), patch.object(control, 'unit') as unit:
            with self.assertRaises(RuntimeError):
                control.execute('gateway-start')
            unit.assert_not_called()

    def test_switch_order(self):
        order = []
        with patch.object(control, 'gateway_stop', side_effect=lambda: order.append('stop')), patch.object(control, 'unit_state', return_value='inactive'), patch.object(control, 'unit', side_effect=lambda *args: order.append(args)), patch.object(control, 'ready', side_effect=lambda **args: order.append('ready')):
            control.execute('switch-images')
        self.assertEqual(order, ['stop', ('start', 'comfyui'), 'ready'])

    def test_checkupdates_no_updates_is_not_error(self):
        with patch.object(control, 'run', return_value=Mock(returncode=2, stdout='', stderr='')):
            control.execute('check-updates')
        self.assertTrue(control.cached('updates')['data']['ok'])
        self.assertEqual(control.cached('updates')['data']['packages'], [])

    def test_checkupdates_failure_is_visible(self):
        with patch.object(control, 'run', return_value=Mock(returncode=1, stdout='', stderr='network unavailable')):
            with self.assertRaises(RuntimeError):
                control.execute('check-updates')
        self.assertFalse(control.cached('updates')['data']['ok'])

    def test_submit_is_persistent_and_duplicate_rejected(self):
        with patch.object(control, 'run') as run:
            job = control.submit('check-updates')
            self.assertIn('halo-job-' + job['job'], ' '.join(run.call_args.args[0]))
            with self.assertRaises(ValueError):
                control.submit('check-updates')

    def test_worker_failure_recorded(self):
        with patch.object(control, 'run'):
            job = control.submit('check-updates')['job']
        with patch.object(control, 'execute', side_effect=RuntimeError('fixture error')):
            with self.assertRaises(RuntimeError):
                control.worker(job)
        with control.database() as database:
            row = database.execute('SELECT state,message FROM jobs WHERE id=?', (job,)).fetchone()
        self.assertEqual(row['state'], 'failed')
        self.assertIn('fixture error', row['message'])

    def test_log_allowlist_and_redaction(self):
        with self.assertRaises(ValueError):
            control.logs('/etc/shadow')
        with patch.object(control, 'run', return_value=Mock(stdout='Authorization: Bearer topsecret\napi_key=anothersecret')):
            result = control.logs('gateway')
        self.assertNotIn('topsecret', result)
        self.assertNotIn('anothersecret', result)

    def test_metrics_history_range_allowlist(self):
        with self.assertRaises(ValueError):
            control.history(99999999)
        self.assertEqual(control.history(900), [])

    def test_cpu_first_sample_is_unknown(self):
        self.assertIsNone(metrics.cpu_percent({}, {'cpu': (100, 80)})['cpu'])
        self.assertEqual(metrics.cpu_percent({'cpu': (100, 80)}, {'cpu': (200, 130)})['cpu'], 50)

    def test_missing_sensor_is_unknown(self):
        self.assertIsNone(metrics.number(self.data / 'absent'))

    def test_counter_reset_not_negative(self):
        self.assertEqual(metrics.rate({'eth': {'rx': 100}}, {'eth': {'rx': 20}}, 5)['eth']['rx'], 0)

    def test_prometheus_does_not_export_null(self):
        result = metrics.prometheus_text({'time': 1, 'cpu': {'cpu': None}, 'memory': {'used': 2}, 'gpu': [], 'temperatures': []})
        self.assertNotIn('None', result)
        self.assertIn('halo_memory_used_bytes 2', result)

    def test_gateway_snapshot_reads_only_inflight(self):
        envelope = {'type': 'inflight', 'data': json.dumps({'operation': 'snapshot', 'requests': [{'id': 'fixture'}]})}
        stream = io.BytesIO(('data: ' + json.dumps(envelope) + '\n\n').encode())
        with patch.object(control.urllib.request, 'build_opener', return_value=Mock(open=Mock(return_value=stream))):
            self.assertEqual(control.inflight(), 1)

    def test_unknown_snapshot_fails_closed(self):
        stream = io.BytesIO(b'data: {"type":"other"}\n\n')
        with patch.object(control.urllib.request, 'build_opener', return_value=Mock(open=Mock(return_value=stream))):
            with self.assertRaises(RuntimeError):
                control.inflight()

    def test_docker_failure_prevents_start(self):
        with patch.object(control, 'containers', return_value=None), patch.object(control, 'unit') as unit:
            with self.assertRaises(RuntimeError):
                control.execute('gateway-start')
            unit.assert_not_called()

    def test_missing_inflight_prevents_stop(self):
        with patch.object(control, 'unit_state', return_value='active'), patch.object(control, 'inflight', side_effect=RuntimeError('unknown')), patch.object(control, 'unit') as unit:
            with self.assertRaises(RuntimeError):
                control.gateway_stop()
            unit.assert_not_called()

    def test_history_is_bounded_and_contains_latest(self):
        import time
        import contextlib
        now = time.time()
        with contextlib.closing(sqlite3.connect(self.data / 'metrics.sqlite')) as connection, connection:
            connection.execute('CREATE TABLE samples (timestamp REAL PRIMARY KEY,payload TEXT)')
            connection.executemany('INSERT INTO samples VALUES (?,?)', [(now - index * 5, '{}') for index in range(10000)])
        result = control.history(86400)
        self.assertLess(len(result), 900)
        self.assertEqual(result[-1]['time'], now)

    def test_maintenance_requires_root(self):
        with patch.object(maintenance.os, 'geteuid', return_value=1000), self.assertRaises(PermissionError):
            maintenance.require_root()

    def test_units_cannot_inject_specifiers(self):
        self.assertEqual(install.unit_quote('/tmp/a%b'), '"/tmp/a%%b"')
        with self.assertRaises(ValueError):
            install.unit_quote('/tmp/a\nExecStart=evil')

    def test_installer_preserves_foreign_units(self):
        path = self.data / 'fixture.service'
        path.write_text('foreign')
        with self.assertRaises(ValueError):
            install.write_unit(self.data, 'fixture.service', 'new')
        self.assertEqual(path.read_text(), 'foreign')


if __name__ == '__main__':
    unittest.main()
