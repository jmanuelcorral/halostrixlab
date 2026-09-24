import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control
import engine_details as details
import service_options


class DetailTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.options = self.root / 'options'
        self.options.mkdir(mode=0o700)
        self.value = dict(service_options.DEFAULTS['comfyui'])
        for patcher in (patch.object(control, 'DATA', self.root), patch.object(service_options, 'DATA', self.options), patch.object(control, 'unit_state', return_value='inactive'), patch.object(details, 'container_id', return_value=None), patch.object(details, 'observed', return_value={'environment': ['API_KEY=synthetic-secret', 'HOME=/tmp']}), patch.object(details, 'source', side_effect=lambda *_: (service_options.read('comfyui'), {'options': service_options.read('comfyui'), 'apiKeys': ['synthetic-secret']}, []))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def payload(self):
        return {'revision': details.detail(control, 'comfyui')['revision'], 'values': self.value}

    def test_redaction_does_not_leak_secret_prefixes(self):
        value = {'apiKeys': ['synthetic-secret=padding'], 'arguments': ['synthetic-secret=value'], 'environment': ['SAFE_NAME=synthetic-secret', 'not a variable synthetic-secret=value']}
        result = json.dumps(details.mask(value))
        self.assertNotIn('synthetic-secret', result)
        self.assertIn('SAFE_NAME=[oculto]', result)

    def test_gateway_discovers_active_profile_and_requires_guard(self):
        launcher = self.options / 'launcher.py'
        gateway = self.options / 'gateway.yaml'
        profile = self.options / 'actual.json'
        launcher.write_text("service_options.lease('gateway')\n'gateway.yaml'")
        gateway.write_text(json.dumps({'models': {'flash-halogen': {'cmd': '/usr/bin/python3 ' + str(details.runtime.ROOT / 'runtime.py') + ' start flash-halogen --config ' + str(profile) + ' --port 18100'}}}))
        profile.write_text(json.dumps({'profiles': {'flash-halogen': {'kind': 'halogen', 'context': 8192}}}))
        for path in (launcher, gateway, profile):
            path.chmod(0o600)
        with patch.object(details, 'LAUNCHER', launcher), patch.object(details, 'GATEWAY', gateway), patch.object(details.runtime, 'DATA', self.options), patch.object(control, 'config', return_value={'model': 'flash-halogen'}), patch.object(control, 'run', return_value=Mock(stdout=str(launcher))):
            _, found, _, selected = details.gateway_source(control)
            self.assertEqual(found, profile)
            self.assertEqual(selected['context'], 8192)
            launcher.write_text("'gateway.yaml'")
            with self.assertRaisesRegex(ValueError, 'guard'):
                details.gateway_source(control)

    def test_redacted_default_and_explicit_reveal(self):
        public = json.dumps(details.detail(control, 'comfyui'))
        private = json.dumps(details.detail(control, 'comfyui', True))
        self.assertNotIn('synthetic-secret', public)
        self.assertIn('synthetic-secret', private)

    def test_save_persists_private_options_and_key_only_audit(self):
        payload = self.payload()
        payload['values']['reserve_vram'] = 6
        result = details.save(control, 'comfyui', payload)
        self.assertEqual(result['values']['reserve_vram'], 6)
        path = self.options / 'comfyui-options.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with control.database() as connection:
            row = connection.execute('SELECT message FROM jobs').fetchone()
        self.assertIn('reserve_vram', row['message'])
        self.assertNotIn('synthetic-secret', row['message'])
        details.save(control, 'comfyui', {'revision': result['revision'], 'values': self.value})
        self.assertEqual(len(list(self.options.glob('*.backup-*'))), 1)

    def test_running_unknown_starting_and_container_states_reject(self):
        payload = self.payload()
        for state in ('active', 'activating', 'deactivating', 'unknown'):
            with self.subTest(state=state), patch.object(control, 'unit_state', return_value=state), self.assertRaises(ValueError):
                details.save(control, 'comfyui', payload)
        with patch.object(details, 'container_id', return_value='owned'), patch.object(control, 'run', return_value=Mock(stdout='running')), self.assertRaises(ValueError):
            details.save(control, 'comfyui', payload)
        self.assertFalse((self.options / 'comfyui-options.json').exists())

    def test_stale_revision_rejected(self):
        payload = self.payload()
        payload['revision'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'ha cambiado'):
            details.save(control, 'comfyui', payload)

    def test_queued_operation_rejected(self):
        payload = self.payload()
        with control.database() as connection:
            connection.execute("INSERT INTO jobs VALUES ('job','start','queued',0,9999999999,'','fixture')")
        with self.assertRaisesRegex(ValueError, 'pendiente'):
            details.save(control, 'comfyui', payload)

    def test_settings_and_operation_locks_reject(self):
        payload = self.payload()
        with service_options.lease('comfyui'), self.assertRaises(ValueError):
            details.save(control, 'comfyui', payload)
        with control.operation_lock(), self.assertRaises(ValueError):
            details.save(control, 'comfyui', payload)

    def test_strict_schema_and_limits(self):
        for value in (dict(self.value, reserve_vram=True), dict(self.value, reserve_vram=0), dict(self.value, reserve_vram=25), dict(self.value, cache_none=1), dict(self.value, command='arbitrary')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                details.validate('comfyui', value)
        with self.assertRaises(ValueError):
            details.validate('halogen', {'context': 1024, 'output': 1024, 'kv_pool': 1024, 'slots': 1, 'halogen_max_tok': 1024})

    def test_unknown_service_and_studio_edit_rejected(self):
        for service in ('../../tmp', 'unsloth'):
            with self.assertRaises(ValueError):
                details.save(control, service, {})

    def test_symlink_target_rejected(self):
        target = self.root / 'target'
        target.write_text('unchanged')
        path = self.options / 'comfyui-options.json'
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            details.atomic_write(path, 'changed')
        self.assertEqual(target.read_text(), 'unchanged')

    def test_logs_owned_container_and_redaction(self):
        with patch.object(details, 'container_id', return_value='owned'), patch.object(control, 'logs', return_value='journal'), patch.object(control, 'run', return_value=Mock(stdout='password=synthetic-secret', stderr='')) as run:
            result = details.logs(control, 'halogen')
        self.assertNotIn('synthetic-secret', result['text'])
        self.assertEqual(run.call_args.args[0][-1], 'owned')

    def test_halogen_update_uses_atomic_gateway_pointer(self):
        gateway = {'models': {'flash-halogen': {'cmd': '/usr/bin/python3 /runtime.py start flash-halogen --config /old.json --port 18100', 'cmdStop': '/usr/bin/python3 /runtime.py stop flash-halogen --config /old.json', 'metadata': {}, 'capabilities': {}}}, 'apiKeys': ['synthetic-secret']}
        profile = {'context': 131072, 'output': 8192, 'slots': 4, 'kv_pool': 524288, 'halogen_max_tok': 16384}
        profiles = {'profiles': {'flash-halogen': profile}}
        path = self.options / 'gateway.yaml'
        path.write_text(json.dumps(gateway))
        path.chmod(0o600)
        values = dict(profile, slots=2)
        with patch.object(details, 'gateway_source', return_value=(copy.deepcopy(gateway), self.options / 'old.json', profiles, profile)), patch.object(details, 'GATEWAY', path), patch.object(details.runtime, 'DATA', self.options), patch.object(details.runtime, 'validate_profile'), patch.object(control, 'config', return_value={'model': 'flash-halogen'}), patch.object(control, 'run', return_value=Mock(returncode=0)):
            details.save_gateway(control, 'halogen', values)
        saved = json.loads(path.read_text())
        self.assertEqual(saved['apiKeys'], ['synthetic-secret'])
        model = saved['models']['flash-halogen']
        self.assertIn('profiles-panel-', model['cmd'])
        self.assertIn('profiles-panel-', model['cmdStop'])
        self.assertEqual(model['concurrencyLimit'], 2)
        self.assertEqual(model['metadata']['context_length'], 131072)
        self.assertEqual(json.loads(next(self.options.glob('profiles-panel-*.json')).read_text())['profiles']['flash-halogen']['slots'], 2)

    def test_invalid_gateway_candidate_does_not_replace_source(self):
        gateway = {'models': {'flash-halogen': {}}}
        with patch.object(details, 'gateway_source', return_value=(gateway, self.options / 'profile', {}, {'slots': 1})), patch.object(details, 'GATEWAY', self.options / 'gateway'), patch.object(control, 'config', return_value={'model': 'flash-halogen'}), patch.object(control, 'run', return_value=Mock(returncode=1)), patch.object(details, 'replace_with_backup') as replace:
            with self.assertRaisesRegex(ValueError, 'rechazó'):
                details.save_gateway(control, 'gateway', {'globalConcurrencyLimit': 2})
        replace.assert_not_called()


if __name__ == '__main__':
    unittest.main()
