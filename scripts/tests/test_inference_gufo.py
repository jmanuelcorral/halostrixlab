import copy
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'workspaces/inference'))
import gufo
import laya_runtime
import runtime


class GufoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = dict(gufo.profile(), model_dir=str(self.root))
        for name in (gufo.TARGET, gufo.DRAFT):
            (self.root / name).write_bytes(b'fixture')
        self.config = self.root / 'profiles.json'
        runtime.write_private(self.config, json.dumps({'profiles': {gufo.NAME: self.profile}}))
        self.gateway = laya_runtime.integrate({'models': {'halogen': {'cmd': 'preserved', 'concurrencyLimit': 4}},
            'apiKeys': ['fixture-key'], 'healthCheckTimeout': 1200,
            'routing': {'router': {'use': 'group', 'settings': {'groups': {'gpu': {
                'swap': True, 'exclusive': True, 'members': ['halogen']}}}}}})

    def test_artifacts_and_settings_are_validated(self):
        self.assertEqual(runtime.validate_profile(gufo.NAME, self.profile), self.profile)
        for key in ('model', 'dflash_model'):
            for value in ('../escape', '/absolute', '', None, '$SECRET', 'missing', 'bad\npath'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    runtime.validate_profile(gufo.NAME, dict(self.profile, **{key: value}))
        outside = self.root.parent / (self.root.name + '-outside')
        outside.write_bytes(b'fixture')
        self.addCleanup(outside.unlink)
        (self.root / 'escape').symlink_to(outside)
        with self.assertRaises(ValueError):
            runtime.validate_profile(gufo.NAME, dict(self.profile, dflash_model='escape'))
        for slots in (1, 2):
            runtime.validate_profile(gufo.NAME, dict(self.profile, slots=slots, context=131072))
        for changes in ({'slots': 3}, {'slots': 0}, {'slots': True}, {'slots': '2'},
                        {'slots': 1.5}, {'context': 131073}, {'image': 'gufo:latest'}, {'kind': 'llamacpp-rocm'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                runtime.validate_profile(gufo.NAME, dict(self.profile, **changes))

    def test_nonroot_fixed_command_without_host_ipc(self):
        command = runtime.run_command(gufo.NAME, self.profile, gufo.PORT, [Path('/dev/null')])
        for value in ('--cap-drop=ALL', '--read-only', '--security-opt=no-new-privileges',
                      '--pull=never', 'memlock=-1:-1', '127.0.0.1:18102:8080', gufo.IMAGE):
            self.assertIn(value, command)
        self.assertNotIn('--ipc=host', command)
        self.assertNotIn('--privileged', command)
        self.assertEqual(command[command.index('--entrypoint') + 1], 'gufo')
        self.assertEqual(command[command.index('--user') + 1], f'{os.getuid()}:{os.getgid()}')
        self.assertEqual(command[command.index('--sessions') + 1], '2')
        self.assertEqual(command[command.index('--context') + 1], '131072')
        self.assertEqual(command[command.index('--speculative') + 1], 'dflash2')
        self.assertIn('/models/' + gufo.DRAFT, command)
        self.assertTrue(any('dst=/models,readonly' in value for value in command))
        ar = dict(self.profile)
        del ar['dflash_model']
        runtime.validate_profile(gufo.NAME, ar)
        self.assertNotIn('--speculative', runtime.run_command(gufo.NAME, ar, gufo.PORT, []))

    def test_preserves_existing_gateway_and_cpu_contract(self):
        original = copy.deepcopy(self.gateway)
        candidate = gufo.integrate(self.gateway, self.config)
        self.assertEqual(original, self.gateway)
        self.assertEqual(candidate['models']['halogen'], original['models']['halogen'])
        self.assertEqual(candidate['apiKeys'], original['apiKeys'])
        self.assertEqual(candidate['models'][gufo.NAME]['checkEndpoint'], '/ready')
        self.assertEqual(candidate['globalConcurrencyLimit'], 7)
        self.assertEqual(candidate['models'][gufo.NAME]['concurrencyLimit'], 2)
        self.assertEqual(candidate['models'][gufo.NAME]['capabilities']['context'], 131072)
        self.assertEqual(candidate['models'][gufo.NAME]['metadata']['context_length'], 131072)
        self.assertEqual(candidate, laya_runtime.integrate(candidate))
        self.assertEqual(candidate, gufo.integrate(candidate, self.config))
        groups = candidate['routing']['router']['settings']['groups']
        self.assertEqual(groups['gpu']['members'], ['halogen', gufo.NAME])
        self.assertEqual(groups['laya-cpu'], original['routing']['router']['settings']['groups']['laya-cpu'])

    def test_conflicts_fail_closed(self):
        for field, value in [('swap', False), ('exclusive', False), ('persistent', True)]:
            gateway = copy.deepcopy(self.gateway)
            gateway['routing']['router']['settings']['groups']['gpu'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                gufo.integrate(gateway, self.config)
        for model in (gufo.NAME, 'collision'):
            gateway = copy.deepcopy(self.gateway)
            gateway['models'][model] = {'proxy': f'http://127.0.0.1:{gufo.PORT}'}
            with self.subTest(model=model), self.assertRaises(ValueError):
                gufo.integrate(gateway, self.config)

    def test_gpu_lease_passed_to_child_and_released(self):
        child = MagicMock()
        child.poll.return_value = 0
        child.returncode = 0
        def spawn(command, pass_fds):
            self.assertEqual(len(pass_fds), 1)
            with (self.root / 'gpu.lock').open('r') as competing:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.fstat(pass_fds[0])
            return child
        with patch.object(runtime, 'DATA', self.root), patch.object(runtime, 'require_halo'), \
             patch.object(runtime, 'inspect_owned', return_value=None), patch.object(runtime, 'docker'), \
             patch.object(runtime, 'devices', return_value=[]), patch.object(runtime, 'stop') as stop, \
             patch.object(runtime.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(runtime.start(gufo.NAME, self.profile, gufo.PORT), 0)
            stop.assert_called_once_with(gufo.NAME)
        with (self.root / 'gpu.lock').open('r') as released:
            fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_integrity_uses_pinned_hash_not_local_manifest(self):
        import hashlib
        artifact = {'file': gufo.TARGET, 'size': 7, 'sha256': hashlib.sha256(b'fixture').hexdigest()}
        with patch.object(gufo, 'DATA', self.root.parent), patch.object(runtime, 'private_file', return_value=self.root / gufo.TARGET), patch.object(gufo, 'ARTIFACTS', [artifact]):
            gufo.verify_artifacts()
            (self.root / gufo.TARGET).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                gufo.verify_artifacts()

    def test_install_validates_before_atomic_replacement(self):
        control = MagicMock()
        control.unit_state.return_value = 'inactive'
        control.run.return_value.returncode = 1
        details = MagicMock()
        details.gateway_source.return_value = (self.gateway, None, None, None)
        candidate = gufo.integrate(self.gateway, self.config)
        with patch.object(gufo.service_options, 'lease'), patch.object(gufo, 'DATA', self.root), patch.object(gufo, 'integrate', return_value=candidate):
            with self.assertRaises(ValueError):
                gufo.install(control, details)
            details.replace_with_backup.assert_not_called()
            control.run.return_value.returncode = 0
            gufo.install(control, details)
            details.replace_with_backup.assert_called_once_with(details.GATEWAY, candidate)
        self.assertFalse(list(self.root.glob('.validate-*')))
        control.unit.assert_not_called()

    def test_upgrade_only_replaces_verified_gufo_entry(self):
        old = dict(self.profile, context=32768)
        del old['slots']
        previous = self.root / 'old.json'
        runtime.write_private(previous, json.dumps({'profiles': {gufo.NAME: old}}))
        original = gufo.integrate(self.gateway, previous)
        target = gufo.integrate(self.gateway, self.config)
        real_integrate = gufo.integrate
        def integrate(gateway, config=None):
            return real_integrate(gateway, config or self.config)
        with patch.object(gufo, 'DATA', self.root), patch.object(gufo, 'integrate', side_effect=integrate):
            candidate = gufo.upgrade_candidate(original)
            self.assertEqual(candidate, target)
            self.assertEqual(gufo.upgrade_candidate(candidate), candidate)
            invalid = copy.deepcopy(original)
            invalid['models'][gufo.NAME]['cmdStop'] = '/bin/true'
            with self.assertRaises(ValueError):
                gufo.upgrade_candidate(invalid)
        self.assertEqual(original['models'][gufo.NAME]['concurrencyLimit'], 1)

    def test_lifecycle_uses_existing_gateway_and_single_model_unload(self):
        control = MagicMock()
        control.unit_state.return_value = 'active'
        control.inflight.return_value = 0
        control.config.return_value = {'model': 'halogen'}
        control.containers.return_value = ['halostrix-halogen']
        control.http.return_value = {'status': 'ready', 'model': gufo.NAME}
        details = MagicMock()
        details.gateway_source.return_value = (self.gateway, None, None, None)
        with patch.object(gufo, 'integrate', return_value=self.gateway), patch.object(runtime, 'inspect_owned', return_value=None):
            gufo.activate(control, details, 'load')
            control.http.assert_called_once_with('/upstream/' + gufo.NAME + '/ready', timeout=1200)
            control.unsloth.require_stopped.assert_called_once()
            control.llamafactory.require_stopped.assert_called_once()
            control.http.reset_mock()
            gufo.activate(control, details, 'unload')
            control.http.assert_called_once_with('/api/models/unload/' + gufo.NAME, {}, timeout=150)
        control.unit.assert_not_called()

    def test_lifecycle_fails_closed_for_busy_or_other_gpu(self):
        control = MagicMock()
        control.unit_state.return_value = 'active'
        control.inflight.return_value = 1
        details = MagicMock()
        details.gateway_source.return_value = (self.gateway, None, None, None)
        with patch.object(gufo, 'integrate', return_value=self.gateway):
            for action in ('load', 'unload'):
                with self.assertRaises(ValueError):
                    gufo.activate(control, details, action)
            control.inflight.return_value = 0
            for containers in (None, ['halostrix-comfyui-manual']):
                control.containers.return_value = containers
                with self.assertRaises(ValueError):
                    gufo.activate(control, details, 'load')
            control.unit_state.return_value = 'inactive'
            with self.assertRaises(ValueError):
                gufo.activate(control, details, 'load')
        control.http.assert_not_called()

    def test_install_refuses_running_gateway(self):
        control = MagicMock()
        control.unit_state.return_value = 'active'
        details = MagicMock()
        with patch.object(gufo.service_options, 'lease'), self.assertRaises(ValueError):
            gufo.install(control, details)
        details.gateway_source.assert_not_called()


if __name__ == '__main__':
    unittest.main()
