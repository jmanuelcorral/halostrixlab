import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'workspaces/inference'))
import laya_runtime
import laya_server


class LayaTests(unittest.TestCase):
    def test_cpu_isolated_command(self):
        with patch.object(laya_runtime.runtime, 'checked_mount', side_effect=lambda value: value):
            command = laya_runtime.run_command({'image': 'sha256:' + 'a' * 64})
        for flag in ('--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=8g', '--cpus=4', '--pull=never'):
            self.assertIn(flag, command)
        self.assertIn('127.0.0.1:18181:8000', command)
        self.assertIn('HF_HUB_OFFLINE=1', command)
        self.assertNotIn('--device', command)
        self.assertNotIn('--privileged', command)
        self.assertNotIn('--ipc=host', command)
        self.assertNotIn(laya_runtime.runtime.LABEL, ' '.join(command))

    def test_single_gateway_preserves_gpu_and_authentication(self):
        original = {'models': {'halogen': {'cmd': 'existing', 'concurrencyLimit': 4}}, 'apiKeys': ['private-key-placeholder'], 'globalConcurrencyLimit': 4,
                    'routing': {'router': {'use': 'group', 'settings': {'groups': {'gpu': {'swap': True, 'exclusive': True, 'members': ['halogen']}}}}}}
        config = laya_runtime.integrate(original)
        self.assertEqual(list(config['models']), ['halogen', 'laya'])
        self.assertEqual(config['apiKeys'], original['apiKeys'])
        self.assertEqual(config['models']['halogen'], original['models']['halogen'])
        self.assertNotIn('laya', original['models'])
        self.assertEqual(config['captureBuffer'], 0)
        self.assertEqual(config['globalConcurrencyLimit'], 5)
        self.assertEqual(config['models']['laya']['ttl'], 0)
        groups = config['routing']['router']['settings']['groups']
        self.assertEqual(groups['gpu'], original['routing']['router']['settings']['groups']['gpu'])
        self.assertEqual(groups['laya-cpu'], {'swap': False, 'exclusive': False, 'persistent': True, 'members': ['laya']})
        self.assertEqual(laya_runtime.integrate(config), config)

    def test_unreviewed_routing_rejected(self):
        for config in ({'models': {}}, {'models': {}, 'routing': {'router': {'use': 'matrix'}}}):
            with self.assertRaises(ValueError):
                laya_runtime.integrate(config)

    def test_real_gateway_keeps_cpu_and_gpu_loaded_in_both_orders(self):
        import http.server
        import socket
        import subprocess
        import tempfile
        import threading
        import time
        import urllib.request
        binary = laya_runtime.runtime.DATA / 'bin/llama-swap'
        if not binary.exists():
            self.skipTest('Optional llama-swap binary absent')
        class Backend(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Backend)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            port = reserved.getsockname()[1]
        model = {'cmd': '/bin/sleep 120', 'proxy': f'http://127.0.0.1:{server.server_port}', 'checkEndpoint': '/health'}
        config = laya_runtime.integrate({'models': {'halogen': model}, 'routing': {'router': {'use': 'group', 'settings': {'groups': {'gpu': {'swap': True, 'exclusive': True, 'members': ['halogen']}}}}}})
        config['models']['laya'] = dict(model)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'gateway.yaml'
            path.write_text(json.dumps(config))
            child = subprocess.Popen([str(binary), '-config', str(path), '-listen', f'127.0.0.1:{port}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                def request(route, body=None):
                    req = urllib.request.Request(f'http://127.0.0.1:{port}' + route, data=body)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        return json.load(response)
                for attempt in range(100):
                    try:
                        request('/running')
                        break
                    except OSError:
                        time.sleep(0.05)
                for order in [('halogen', 'laya'), ('laya', 'halogen')]:
                    for name in order:
                        request('/upstream/' + name + '/health')
                    running = json.dumps(request('/running'))
                    self.assertIn('halogen', running)
                    self.assertIn('laya', running)
                    request('/api/models/unload', b'{}')
            finally:
                child.terminate()
                child.wait(timeout=20)

    def test_foreign_container_is_never_stopped(self):
        from subprocess import CompletedProcess
        with patch.object(laya_runtime.runtime, 'docker', side_effect=[CompletedProcess([], 0, 'abc'), CompletedProcess([], 0, json.dumps([{'Config': {'Labels': {}}}]))]) as docker:
            with self.assertRaises(ValueError):
                laya_runtime.stop()
            self.assertEqual(docker.call_count, 2)

    def test_valid_request_and_no_model_routing(self):
        body = {'state': 'texto', 'questions': {'category': {'type': 'choice', 'criteria': {'code': 'programar', 'text': 'redactar'}}}}
        self.assertEqual(laya_server.validate_request(body), (body['state'], body['questions']))
        for model in ('halogen', '../other', 'typed-decisions'):
            with self.assertRaises(ValueError):
                laya_server.validate_request(dict(body, model=model))

    def test_request_limits_and_schema(self):
        invalid = [[], {}, {'state': None, 'questions': {}}, {'state': '', 'questions': {}},
                   {'state': '', 'questions': {'q': {'type': 'execute'}}},
                   {'state': '', 'questions': {'q': {'type': 'choice', 'criteria': dict.fromkeys(map(str, range(21)), 'value')}}},
                   {'state': '', 'questions': dict.fromkeys(map(str, range(9)), {'type': 'noul'})}]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValueError):
                laya_server.validate_request(body)

    def test_revision_and_image_validation(self):
        for value in ({'image': 'latest'}, {'image': 'sha256:' + 'a' * 64, 'source_revision': 'wrong', 'model_revision': laya_runtime.MODEL_REVISION}):
            with patch.object(laya_runtime.runtime, 'private_file') as private:
                private.return_value.read_text.return_value = json.dumps(value)
                with self.assertRaises(ValueError):
                    laya_runtime.deployment()


if __name__ == '__main__':
    unittest.main()
