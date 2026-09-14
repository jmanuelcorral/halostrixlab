"""Offline regression tests for the actual PowerShell entrypoint (stdlib only)."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SCRIPT = Path(__file__).resolve().parents[1] / "test-lemonade.ps1"
MODEL = "fixture-model"
SHELL = None
SHELL_ENV = os.environ.copy()
# Let each PowerShell edition build its own module path.
SHELL_ENV.pop("PSModulePath", None)


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.server.requests.append(("GET", self.path, None))
        self.respond(self.server.models_status, self.server.models)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(("POST", self.path, body))
        self.respond(self.server.chat_status, self.server.chat)

    def respond(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class LemonadeEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.server.requests = []
        self.server.models_status = 200
        self.server.chat_status = 200
        self.server.models = {"data": [{"id": MODEL}]}
        self.server.chat = {"choices": [{"message": {"content": " LAN_OK "}}]}

    def invoke(self, arguments=None):
        if arguments is None:
            arguments = ["-BaseUrl", self.base, "-Model", MODEL]
        return subprocess.run(
            [SHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT)]
            + arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
            env=SHELL_ENV,
        )

    def assert_failure(self, result, message=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("UnauthorizedAccess", result.stderr)
        if message:
            output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
            output = re.sub(r"\n\s*\|\s*", " ", output)
            self.assertIn(message, " ".join(output.split()))

    def test_powershell_parser(self):
        escaped = str(SCRIPT).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            f"[void][System.Management.Automation.Language.Parser]::ParseFile('{escaped}',"
            "[ref]$tokens,[ref]$errors); "
            "Write-Output ('Parse errors: ' + $errors.Count); "
            "if ($errors.Count) { exit 1 }"
        )
        result = subprocess.run(
            [SHELL, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=20, check=False,
            env=SHELL_ENV,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Parse errors: 0", result.stdout)

    def test_both_parameters_required(self):
        self.assert_failure(self.invoke([]))
        self.assertEqual(self.server.requests, [])

    def test_base_url_required(self):
        self.assert_failure(self.invoke(["-Model", MODEL]))
        self.assertEqual(self.server.requests, [])

    def test_model_required(self):
        self.assert_failure(self.invoke(["-BaseUrl", self.base]))
        self.assertEqual(self.server.requests, [])

    def test_invalid_urls_make_no_requests(self):
        invalid = [
            "relative/v1", "ftp://localhost/v1", "http://:13305/v1",
            "http://localhost:invalid/v1", "http://user@localhost/v1",
            self.base + "?query=value", self.base + "#fragment",
            self.base + " path",
        ]
        for base in invalid:
            with self.subTest(base=base):
                result = self.invoke(["-BaseUrl", base, "-Model", MODEL])
                self.assert_failure(result, "BaseUrl must be an absolute HTTP(S) URL")
                self.assertEqual(self.server.requests, [])

    def test_content_success_and_payload(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Lemonade LAN test: PASS", result.stdout)
        self.assertIn(f"Endpoint: {self.base}", result.stdout)
        self.assertIn(f"Model: {MODEL}", result.stdout)
        self.assertIn("Response: LAN_OK", result.stdout)
        self.assertEqual(
            [(method, path) for method, path, _ in self.server.requests],
            [("GET", "/v1/models"), ("POST", "/v1/chat/completions")],
        )
        self.assertEqual(self.server.requests[1][2], {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply only with LAN_OK."}],
            "temperature": 0, "max_tokens": 16, "stream": False,
        })

    def test_trailing_slashes(self):
        result = self.invoke(["-BaseUrl", self.base + "///", "-Model", MODEL])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server.requests[0][1], "/v1/models")
        self.assertEqual(self.server.requests[1][1], "/v1/chat/completions")

    def test_reasoning_fallback(self):
        self.server.chat = {"choices": [{"message": {
            "content": None, "reasoning_content": " fallback answer ",
        }}]}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Response: fallback answer", result.stdout)

    def test_whitespace_content_fallback(self):
        self.server.chat = {"choices": [{"message": {
            "content": " \n", "reasoning_content": "fallback",
        }}]}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Response: fallback", result.stdout)

    def test_non_literal_answer_is_accepted(self):
        self.server.chat = {"choices": [{"message": {"content": "another answer"}}]}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Response: another answer", result.stdout)

    def test_missing_model_stops_before_chat(self):
        self.server.models = {"data": []}
        self.assert_failure(self.invoke(), "must appear exactly once")
        self.assertEqual(len(self.server.requests), 1)

    def test_duplicate_model_stops_before_chat(self):
        self.server.models["data"].append({"id": MODEL})
        self.assert_failure(self.invoke(), "must appear exactly once")
        self.assertEqual(len(self.server.requests), 1)

    def test_null_model_data(self):
        self.server.models = {"data": None}
        self.assert_failure(self.invoke(), "does not contain 'data'")
        self.assertEqual(len(self.server.requests), 1)

    def test_models_http_error(self):
        self.server.models_status = 503
        self.assert_failure(self.invoke(), "HTTP 503")
        self.assertEqual(len(self.server.requests), 1)

    def test_chat_http_error(self):
        self.server.chat_status = 503
        self.assert_failure(self.invoke(), "HTTP 503")
        self.assertEqual(len(self.server.requests), 2)

    def test_no_chat_choices(self):
        self.server.chat = {"choices": []}
        self.assert_failure(self.invoke(), "does not contain a valid chat choice")

    def test_null_chat_message(self):
        self.server.chat = {"choices": [{"message": None}]}
        self.assert_failure(self.invoke(), "does not contain a valid chat choice")

    def test_no_answer(self):
        self.server.chat = {"choices": [{"message": {
            "content": "", "reasoning_content": "",
        }}]}
        self.assert_failure(self.invoke(), "contains neither content nor reasoning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", default="pwsh", help="pwsh or powershell executable")
    args, remaining = parser.parse_known_args()
    SHELL = shutil.which(args.shell)
    if SHELL is None:
        parser.error("PowerShell executable not found; specify --shell with its path.")
    probe = subprocess.run(
        [SHELL, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT)],
        capture_output=True, text=True, timeout=20, check=False, env=SHELL_ENV,
    )
    if "UnauthorizedAccess" in probe.stderr or "PSSecurityException" in probe.stderr:
        parser.error("This shell blocks script execution; use an approved shell without bypassing policy.")
    unittest.main(argv=[__file__] + remaining)
