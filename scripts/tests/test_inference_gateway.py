import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request


BINARY = Path(__file__).resolve().parents[2] / "workspaces/inference/data/bin/llama-swap"


class Backend(http.server.BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *arguments):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls.append((self.path, body))
        streaming = body.get("stream", False)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
        self.end_headers()
        if streaming:
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"READY"}}]}\n\ndata: [DONE]\n\n')
        else:
            self.wfile.write(json.dumps({"id": "fixture", "model": body["model"],
                                        "choices": [{"message": {"role": "assistant", "content": "READY"}}]}).encode())


@unittest.skipUnless(BINARY.exists(), "Install optional pinned llama-swap binary for integration tests")
class GatewayTests(unittest.TestCase):
    def test_real_gateway_auth_ui_routing_and_streaming(self):
        Backend.calls = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            config = directory / "config.yaml"
            config.write_text(json.dumps({
                "apiKeys": ["${env.FIXTURE_KEY}"], "healthCheckTimeout": 15,
                "models": {"fixture": {"cmd": "/bin/sleep 120", "useModelName": "upstream-fixture",
                                       "proxy": f"http://127.0.0.1:{server.server_port}", "checkEndpoint": "/health",
                                       "capabilities": {"context": 32768},
                                       "metadata": {"context_length": 32768, "max_output_tokens": 8192}}}
            }))
            environment = dict(os.environ, FIXTURE_KEY="fixture-not-a-real-key")
            with (directory / "gateway.log").open("w") as log:
                child = subprocess.Popen([str(BINARY), "-config", str(config), "-listen", f"127.0.0.1:{port}"],
                                         cwd=directory, env=environment, stdout=log, stderr=log)
                try:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    def request(path, body=None, auth=True):
                        headers = {"Content-Type": "application/json"}
                        if auth:
                            headers["Authorization"] = "Bearer fixture-not-a-real-key"
                        target = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                                        data=None if body is None else json.dumps(body).encode(),
                                                        headers=headers)
                        return opener.open(target, timeout=10)
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            with request("/v1/models") as response:
                                models = json.load(response)
                            break
                        except (urllib.error.URLError, ConnectionError):
                            if time.monotonic() >= deadline:
                                self.fail("Gateway failed to become ready")
                            time.sleep(0.1)
                    self.assertEqual(models["data"][0]["id"], "fixture")
                    self.assertEqual(models["data"][0]["context_length"], 32768)
                    self.assertEqual(models["data"][0]["context_window"], 32768)
                    self.assertEqual(models["data"][0]["meta"]["n_ctx"], 32768)
                    self.assertEqual(models["data"][0]["meta"]["llamaswap"]["max_output_tokens"], 8192)
                    self.assertFalse(Backend.calls)
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        request("/v1/models", auth=False)
                    self.assertEqual(rejected.exception.code, 401)
                    rejected.exception.close()
                    with request("/ui/") as response:
                        self.assertIn(b"<html", response.read().lower())
                    for path in ("/v1/chat/completions", "/v1/responses"):
                        for streaming in (False, True):
                            body = {"model": "fixture", "stream": streaming,
                                    "messages": [{"role": "user", "content": "fixture"}],
                                    "input": "fixture", "tools": [{"type": "function", "function": {"name": "read"}}]}
                            with request(path, body) as response:
                                result = response.read()
                            self.assertIn(b"READY", result)
                            if streaming:
                                self.assertIn(b"[DONE]", result)
                            self.assertEqual(Backend.calls[-1][0], path)
                            self.assertEqual(Backend.calls[-1][1]["model"], "upstream-fixture")
                            self.assertEqual(Backend.calls[-1][1]["tools"], body["tools"])
                finally:
                    child.terminate()
                    try:
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
