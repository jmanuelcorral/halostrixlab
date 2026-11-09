import copy
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'workspaces/inference'))
import ollaya_runtime
import ollaya_server


class OllayaTests(unittest.TestCase):
    def test_isolated_cpu_command(self):
        with patch.object(ollaya_runtime.runtime, 'checked_mount', side_effect=lambda value: value):
            command = ollaya_runtime.run_command({'image': 'sha256:' + 'a' * 64})
        for flag in ('--read-only', '--cpus=8', '--memory=32g', '--memory-swap=32g', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pull=never'):
            self.assertIn(flag, command)
        self.assertIn('127.0.0.1:18182:8000', command)
        self.assertIn(ollaya_runtime.NETWORK, command)
        self.assertNotIn('--device', command)
        self.assertNotIn('--privileged', command)
        self.assertNotIn('io.halostrix.inference=', ' '.join(command))
        self.assertTrue(any(value.endswith('dst=/models,readonly') for value in command))

    def gateway(self):
        return {'models': {'gpu-model': {'concurrencyLimit': 4}, 'laya': {'concurrencyLimit': 1}, 'gufo': {'concurrencyLimit': 2}},
                'apiKeys': ['placeholder'], 'globalConcurrencyLimit': 7,
                'routing': {'router': {'use': 'group', 'settings': {'groups': {
                    'gpu': {'swap': True, 'exclusive': True, 'members': ['gpu-model', 'gufo']},
                    'laya-cpu': {'swap': False, 'exclusive': False, 'persistent': True, 'members': ['laya']}}}}}}

    def test_gateway_preserves_existing_models_groups_and_auth(self):
        original = self.gateway()
        candidate = ollaya_runtime.integrate(original)
        self.assertEqual(candidate['apiKeys'], original['apiKeys'])
        self.assertEqual(candidate['globalConcurrencyLimit'], 8)
        self.assertEqual(candidate['captureBuffer'], 0)
        for name, model in original['models'].items():
            self.assertEqual(candidate['models'][name], model)
        self.assertNotIn(ollaya_runtime.ALIAS, original['models'])
        groups = candidate['routing']['router']['settings']['groups']
        for name, group in original['routing']['router']['settings']['groups'].items():
            self.assertEqual(groups[name], group)
        self.assertEqual(groups['winnow-cpu'], {'swap': False, 'exclusive': False, 'persistent': True, 'members': [ollaya_runtime.ALIAS]})
        self.assertEqual(ollaya_runtime.integrate(candidate), candidate)

    def test_gateway_rejects_collisions_and_changed_configuration(self):
        for field in ('proxy', 'group', 'model', 'router'):
            value = self.gateway()
            groups = value['routing']['router']['settings']['groups']
            if field == 'proxy':
                value['models']['laya']['proxy'] = ollaya_runtime.model_config()['proxy']
            elif field == 'group':
                groups['gpu']['members'].append(ollaya_runtime.ALIAS)
            elif field == 'model':
                value['models'][ollaya_runtime.ALIAS] = {'cmd': 'unreviewed'}
            else:
                value['routing']['router']['use'] = 'matrix'
            with self.subTest(field=field), self.assertRaises(ValueError):
                ollaya_runtime.integrate(value)

    def test_schema_and_fixed_identity(self):
        body = copy.deepcopy(ollaya_server.SMOKE)
        body['model'] = ollaya_runtime.ALIAS
        self.assertEqual(ollaya_server.validate_request(body)['model'], 'winnow:12b')
        for invalid in ({**body, 'model': 'laya'}, {**body, 'keep_alive': 0}, {**body, 'questions': {}},
                        {**body, 'state': None}, {**body, 'winnow': {'images': []}},
                        {**body, 'questions': {'bad': {'type': 'choice', 'criteria': {'a': None}}}},
                        {**body, 'questions': {'bad': {'type': 'score', 'criteria': {'a': None, 'b': None}}}}):
            with self.assertRaises(ValueError):
                ollaya_server.validate_request(invalid)

    def test_readiness_requires_cpu_inference(self):
        state = ollaya_server.State()
        with patch.object(ollaya_server, 'backend', side_effect=[(200, {'answers': {'paid': True}}), (200, {'models': [{'device': 'cpu'}]})]):
            state.warmup()
        self.assertTrue(state.healthy())
        state = ollaya_server.State()
        with patch.object(ollaya_server, 'backend', side_effect=[(200, {'answers': {'paid': True}}), (200, {'models': [{'device': 'cuda:0'}]})]):
            with self.assertRaises(ValueError):
                state.warmup()
        self.assertFalse(state.healthy())

    def server(self):
        state = ollaya_server.State()
        state.ready = True
        server = ollaya_server.Server(('127.0.0.1', 0), state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def request(self, server, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_http_routes_body_limits_and_backend_sanitization(self):
        server = self.server()
        headers = {'Content-Type': 'application/json'}
        for path in ('/api/pull', '/api/delete', '/v1/chat/completions', '/v1/systemone?model=laya', '/%61pi/pull'):
            self.assertEqual(self.request(server, 'POST', path, b'{}', headers)[0], 404)
        self.assertEqual(self.request(server, 'POST', '/v1/systemone', b'x' * 65537, headers)[0], 413)
        self.assertEqual(self.request(server, 'POST', '/v1/systemone', b'{"state":NaN}', headers)[0], 400)
        body = json.dumps(ollaya_server.SMOKE).encode()
        with patch.object(ollaya_server, 'backend', return_value=(422, {'private': 'secret'})):
            status, raw = self.request(server, 'POST', '/v1/systemone', body, headers)
        self.assertEqual(status, 422)
        self.assertNotIn(b'secret', raw)
        with patch.object(ollaya_server, 'backend', return_value=(200, {'answers': {'paid': 0.99}})):
            self.assertEqual(self.request(server, 'POST', '/v1/systemone', body, headers)[0], 200)

    def test_busy_and_backend_failure_fail_closed(self):
        server = self.server()
        body = json.dumps(ollaya_server.SMOKE).encode()
        headers = {'Content-Type': 'application/json'}
        server.state.gate.acquire()
        try:
            self.assertEqual(self.request(server, 'POST', '/v1/systemone', body, headers)[0], 429)
        finally:
            server.state.gate.release()
        with patch.object(ollaya_server, 'backend', side_effect=TimeoutError):
            self.assertEqual(self.request(server, 'POST', '/v1/systemone', body, headers)[0], 503)
        self.assertTrue(server.state.failed)
        self.assertEqual(self.request(server, 'GET', '/ready')[0], 503)

    def test_source_pins_and_minimal_build(self):
        dockerfile = (ollaya_runtime.ROOT / 'ollaya.Dockerfile').read_text()
        self.assertIn(ollaya_runtime.BASE_IMAGE, dockerfile)
        self.assertIn(ollaya_runtime.PYTHON_IMAGE, dockerfile)
        self.assertNotIn('COPY .', dockerfile)
        self.assertIn('OLLAYA_DEVICE=cpu', dockerfile)
        self.assertIn('OLLAYA_MAX_LOADED_MODELS=1', dockerfile)


if __name__ == '__main__':
    unittest.main()
