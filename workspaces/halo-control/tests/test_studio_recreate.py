import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import studio_recreate as studio
import engine_details
import control


class RecreationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = {'Id': 'old-id', 'Image': 'sha256:immutable', 'State': {'Status': 'exited'}, 'Config': {'Image': 'mutable:tag', 'User': '1000:1000', 'Env': ['UNSLOTH_STUDIO_PASSWORD=synthetic-secret', 'HF_HOME=/cache'], 'Entrypoint': ['studio'], 'Cmd': ['serve'], 'Healthcheck': {'Test': ['CMD', 'health']}, 'Labels': {'ownership': 'fixture'}}, 'HostConfig': {'ShmSize': 16 * 2**30, 'NetworkMode': 'fixture-network', 'RestartPolicy': {'Name': 'no'}, 'Devices': [{'PathOnHost': '/dev/kfd', 'PathInContainer': '/dev/kfd', 'CgroupPermissions': 'rwm'}], 'GroupAdd': ['987'], 'SecurityOpt': ['no-new-privileges'], 'PortBindings': {'8888/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8888'}]}}, 'Mounts': [], 'NetworkSettings': {'Networks': {'fixture-network': {'Aliases': ['studio'], 'IPAMConfig': None, 'IPAddress': '172.18.0.2'}}}}
        for index, destination in enumerate(('/workspace/hf-cache', '/workspace/projects', '/workspace/tmp', '/home/unsloth/.unsloth/studio')):
            path = self.root / str(index)
            path.mkdir()
            self.original['Mounts'].append({'Type': 'bind', 'Source': str(path), 'Destination': destination, 'RW': True, 'Mode': 'rw', 'Propagation': 'rprivate'})
        self.options = studio.values(self.original)
        self.requests = []
        self.fail = None
        self.created = None
        self.patcher = patch.object(studio, 'DATA', self.root / 'transactions')
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        if self.fail and self.fail in path:
            raise ValueError('synthetic failure')
        if path.endswith('/changes'):
            return []
        if '/create?' in path:
            self.created = {'Id': 'new-id', 'Image': self.original['Image'], 'State': {'Status': 'created'}, 'Config': {key: value for key, value in payload.items() if key not in ('HostConfig', 'NetworkingConfig')}, 'HostConfig': payload['HostConfig'], 'Mounts': copy.deepcopy(self.original['Mounts']), 'NetworkSettings': {'Networks': payload['NetworkingConfig']['EndpointsConfig']}}
            return {'Id': 'new-id'}
        if path == '/containers/new-id/json':
            return self.created
        return None

    def recreate(self, options=None):
        with patch.object(studio, 'snapshot', return_value=copy.deepcopy(self.original)), patch.object(studio, 'request', side_effect=self.request):
            return studio.recreate(options or self.options, studio.revision(self.original))

    def test_preserves_original_and_creates_stopped_immutable_clone(self):
        self.assertTrue(self.recreate()['recreated'])
        self.assertEqual(self.created['Config']['Env'], self.original['Config']['Env'])
        self.assertEqual(self.created['HostConfig'], self.original['HostConfig'])
        self.assertEqual(self.created['Config']['Image'], 'sha256:immutable')
        self.assertFalse(any('/start' in path or method == 'DELETE' for method, path, _ in self.requests))
        self.assertEqual(len(list(studio.DATA.glob('original-*.json'))), 1)
        self.assertFalse(list(studio.DATA.glob('pending-*.json')))
        for path in studio.DATA.glob('*.json'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('synthetic-secret', next(studio.DATA.glob('completed-*.json')).read_text())

    def test_only_allowlisted_changes_apply(self):
        self.recreate(dict(self.options, shm_gib=8, hf_hub_offline=True))
        self.assertEqual(self.created['HostConfig']['ShmSize'], 8 * 2**30)
        self.assertIn('HF_HUB_OFFLINE=true', self.created['Config']['Env'])
        self.assertIn('UNSLOTH_STUDIO_PASSWORD=synthetic-secret', self.created['Config']['Env'])
        self.assertNotIn('TRANSFORMERS_OFFLINE=false', self.created['Config']['Env'])

    def test_stale_revision_does_not_create(self):
        with patch.object(studio, 'snapshot', return_value=self.original), patch.object(studio, 'request') as request, self.assertRaisesRegex(ValueError, 'cambió'):
            studio.recreate(self.options, 'stale')
        request.assert_not_called()

    def test_pending_transaction_blocks_start_and_edit(self):
        studio.DATA.mkdir(mode=0o700)
        (studio.DATA / 'pending-fixture.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'sin finalizar'):
            self.recreate()

    def test_unknown_writable_change_is_not_discarded(self):
        with patch.object(studio, 'request', return_value=[{'Path': '/home/unsloth/important', 'Kind': 1}]), self.assertRaisesRegex(ValueError, 'capa escribible'):
            studio.validate(self.original, self.options)

    def test_running_mount_changes_and_types_rejected(self):
        for options in (dict(self.options, shm_gib=True), dict(self.options, shm_gib=0), dict(self.options, hf_hub_offline=1), dict(self.options, password='new')):
            with self.subTest(options=options), self.assertRaises(ValueError):
                studio.validate(self.original, options)
        for status in ('running', 'paused', 'restarting', 'dead'):
            value = copy.deepcopy(self.original)
            value['State']['Status'] = status
            with self.assertRaises(ValueError):
                studio.validate(value, self.options)
        value = copy.deepcopy(self.original)
        value['Mounts'].pop()
        with self.assertRaises(ValueError):
            studio.validate(value, self.options)

    def test_rename_failure_restores_original_name(self):
        self.fail = '/containers/new-id/rename?name=' + studio.unsloth.NAME
        with self.assertRaises(ValueError):
            self.recreate()
        calls = [(method, path) for method, path, _ in self.requests]
        self.assertIn(('DELETE', '/containers/new-id'), calls)
        self.assertIn(('POST', '/containers/old-id/rename?name=' + studio.unsloth.NAME), calls)
        self.assertFalse(list(studio.DATA.glob('pending-*.json')))

    def test_validation_failure_removes_only_candidate(self):
        with patch.object(studio, 'verify', side_effect=ValueError('mismatch')), self.assertRaises(ValueError):
            self.recreate()
        calls = [(method, path) for method, path, _ in self.requests]
        self.assertIn(('DELETE', '/containers/new-id'), calls)
        self.assertFalse(any('/old-id/rename' in path for _, path in calls))

    def test_create_unknown_outcome_keeps_recovery_marker(self):
        self.fail = '/containers/create'
        with self.assertRaises(ValueError):
            self.recreate()
        self.assertTrue(list(studio.DATA.glob('pending-*.json')))
        self.assertFalse(any('/old-id/rename' in path for _, path, _ in self.requests))

    def test_mismatched_host_or_mount_fails_verification(self):
        self.recreate()
        payload = studio.candidate(self.original, self.options)
        changed = copy.deepcopy(self.created)
        changed['HostConfig']['GroupAdd'] = []
        with self.assertRaises(ValueError):
            studio.verify(self.original, changed, payload)
        changed = copy.deepcopy(self.created)
        changed['Mounts'][0]['RW'] = False
        with self.assertRaises(ValueError):
            studio.verify(self.original, changed, payload)

    def test_panel_save_invokes_recreation_and_key_only_audit(self):
        with patch.object(control, 'DATA', self.root), patch.object(engine_details.service_options, 'DATA', self.root), patch.object(studio, 'snapshot', return_value=self.original), patch.object(engine_details, 'stopped'), patch.object(engine_details, 'observed', return_value={}), patch.object(control, 'unit_state', return_value='inactive'), patch.object(studio, 'recreate') as recreate:
            detail = engine_details.detail(control, 'unsloth')
            self.assertNotIn('synthetic-secret', json.dumps(detail))
            engine_details.save(control, 'unsloth', {'revision': detail['revision'], 'values': self.options})
            recreate.assert_called_once_with(self.options, studio.revision(self.original))
            with control.database() as connection:
                message = connection.execute('SELECT message FROM jobs').fetchone()[0]
            self.assertNotIn('synthetic-secret', message)


if __name__ == '__main__':
    unittest.main()
