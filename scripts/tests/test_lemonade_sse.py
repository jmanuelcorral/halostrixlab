"""Offline subprocess acceptance tests; no remote services or dependencies."""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "test-lemonade-sse.py"
MODEL = "fixture-model"


def delta(content=None, **extra):
    value = {} if content is None else {"content": content}
    value.update(extra)
    return {"choices": [{"index": 0, "delta": value, "finish_reason": None}]}


def event(payload, kind=None):
    prefix = f"event: {kind}\n" if kind else ""
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return (prefix + "data: " + data + "\n\n").encode("utf-8")


STOP = event({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
DONE = event("[DONE]")
READY = event(delta("READY"))
HEALTH = {
    "status": "ok",
    "version": "11.9.0",
    "busy": False,
    "streaming": False,
    "all_models_loaded": [{
        "model_name": MODEL,
        "backend_alive": True,
        "backend_health": "ready",
        "recipe_options": {"ctx_size": 32768},
        "max_context_window": 262144,
    }],
}


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.server.requests.append(("GET", self.path, None))
        if self.path != "/api/v1/health":
            self.send_error(404)
            return
        if self.server.stopping.wait(self.server.health_delay):
            return
        body = self.server.health
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(self.server.health_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Location", "/must-not-follow")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(("POST", self.path, body))
        if self.server.header_drip:
            try:
                self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Delay: ")
                self.wfile.flush()
                while not self.server.stopping.wait(0.03):
                    self.wfile.write(b"x")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.server.chat_disconnected.set()
            return
        self.send_response(self.server.chat_status)
        self.send_header("Content-Type", self.server.content_type)
        self.send_header("Location", "/must-not-follow")
        self.end_headers()
        try:
            for delay, data in self.server.fragments:
                if self.server.stopping.wait(delay):
                    return
                self.wfile.write(data)
                self.wfile.flush()
            while self.server.keep_open and not self.server.stopping.wait(0.03):
                if select.select([self.connection], [], [], 0)[0]:
                    if self.connection.recv(1) == b"":
                        self.server.chat_disconnected.set()
                        return
                if self.server.drip:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.server.chat_disconnected.set()
        finally:
            self.server.chat_finished.set()


class LemonadeSSEEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.server.daemon_threads = False
        self.server.requests = []
        self.server.health = copy.deepcopy(HEALTH)
        self.server.health_status = 200
        self.server.health_delay = 0
        self.server.chat_status = 200
        self.server.content_type = "text/event-stream; charset=utf-8"
        self.server.fragments = [(0, READY + STOP + DONE)]
        self.server.keep_open = False
        self.server.header_drip = False
        self.server.drip = False
        self.server.stopping = threading.Event()
        self.server.chat_finished = threading.Event()
        self.server.chat_disconnected = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.stopping.set()
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())

    def invoke(self, extra=None, arguments=None, env=None):
        if arguments is None:
            arguments = [
                "--base-url", self.base, "--model", MODEL, "--records", "3",
                "--minimum-first-token-seconds", "0", "--timeout-seconds", "5",
            ]
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT)] + arguments + (extra or []),
            capture_output=True, text=True, encoding="utf-8",
            timeout=10, check=False, env=env,
        )

    def report(self, result, error=None):
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        report = json.loads(result.stdout)
        self.assertNotIn(self.base, result.stdout)
        self.assertNotIn(MODEL, result.stdout)
        self.assertNotIn(str(SCRIPT), result.stdout)
        self.assertGreaterEqual(report.get("elapsed_seconds", 0), 0)
        if error is None:
            self.assertEqual(result.returncode, 0, report)
            self.assertEqual(report["status"], "PASS")
        else:
            self.assertNotEqual(result.returncode, 0, report)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["error_code"], error, report)
        return report

    def assert_no_post(self):
        self.assertTrue(all(method == "GET" for method, _, _ in self.server.requests))

    def test_required_arguments(self):
        for arguments in ([], ["--model", MODEL], ["--base-url", self.base]):
            with self.subTest(arguments=arguments):
                self.report(self.invoke(arguments=arguments), "invalid_arguments")
        self.assertEqual(self.server.requests, [])

    def test_unsafe_urls_make_zero_requests(self):
        for base in (
            "relative", "ftp://localhost", "http://:13305", "http://localhost:bad",
            "http://user:private-secret@localhost", self.base + "?secret=x",
            self.base + "?", self.base + "#", self.base + "#fragment",
            self.base + " path", "\n" + self.base, self.base + "/api/v1",
            self.base + "/v1", "http://localhost\\evil", "http://%6cocalhost",
            "http://localhost:0", "http://localhost:65536", "http://localhost:",
        ):
            with self.subTest(base=base):
                result = self.invoke(arguments=["--base-url", base, "--model", MODEL])
                self.report(result, "invalid_url")
                self.assertNotIn("private-secret", result.stdout + result.stderr)
        self.assertEqual(self.server.requests, [])

    def test_invalid_limits_and_model_make_zero_requests(self):
        for extra, code in (
            (["--records", "0"], "invalid_limits"),
            (["--records", "10001"], "invalid_limits"),
            (["--records", "private-secret"], "invalid_arguments"),
            (["--timeout-seconds", "0"], "invalid_limits"),
            (["--timeout-seconds", "3601"], "invalid_limits"),
            (["--minimum-first-token-seconds", "-1"], "invalid_limits"),
            (["--minimum-first-token-seconds", "nan"], "invalid_limits"),
            (["--minimum-first-token-seconds", "nan", "--base-url", "invalid"], "invalid_url"),
            (["--timeout-seconds", "inf"], "invalid_limits"),
            (["--minimum-first-token-seconds", "6"], "invalid_limits"),
            (["--model", ""], "invalid_model"),
            (["--model", "has space"], "invalid_model"),
            (["--unknown-private-secret"], "invalid_arguments"),
        ):
            with self.subTest(extra=extra):
                result = self.invoke(extra)
                self.report(result, code)
                self.assertNotIn("private-secret", result.stdout + result.stderr)
        self.assertEqual(self.server.requests, [])

    def test_help_is_offline_and_documents_defaults(self):
        result = self.invoke(arguments=["--help"])
        self.assertEqual(result.returncode, 0)
        normalized = " ".join(result.stdout.split())
        self.assertIn("default: 130", normalized)
        self.assertIn("default: 900", normalized)
        self.assertIn("ORIGIN", result.stdout)
        self.assertIn("token", result.stdout)
        self.assertEqual(self.server.requests, [])

    def test_health_failures_never_post(self):
        cases = [
            (None, "invalid_health"),
            ({"status": "loading"}, "invalid_health"),
            ({**HEALTH, "all_models_loaded": None}, "invalid_health"),
            ({**HEALTH, "all_models_loaded": []}, "not_resident"),
            ({**HEALTH, "all_models_loaded": HEALTH["all_models_loaded"] * 2}, "not_resident"),
            ({**HEALTH, "all_models_loaded": [{"model_name": MODEL.upper()}]}, "not_resident"),
        ]
        for backend_alive in (False, None, "true", 1):
            health = copy.deepcopy(HEALTH)
            health["all_models_loaded"][0]["backend_alive"] = backend_alive
            cases.append((health, "backend_not_ready"))
        for backend_health in (None, "loading", "error", True):
            health = copy.deepcopy(HEALTH)
            health["all_models_loaded"][0]["backend_health"] = backend_health
            cases.append((health, "backend_not_ready"))
        for ctx in (None, 0, -1, "32768", True):
            health = copy.deepcopy(HEALTH)
            health["all_models_loaded"][0]["recipe_options"]["ctx_size"] = ctx
            cases.append((health, "invalid_context"))
        for health, code in cases:
            with self.subTest(health=health):
                self.server.health = health
                self.report(self.invoke(), code)
                self.assert_no_post()

    def test_actual_lemonade_health_fields_without_synthetic_ready_flag(self):
        self.server.health = {
                "status": "ok",
                "version": "11.9.0",
                "max_models": {"llm": 2},
                "all_models_loaded": [
                    {
                        "model_name": MODEL,
                        "backend_alive": True,
                        "backend_health": "ready",
                        "status": "ready",
                        "is_busy": False,
                        "is_streaming": False,
                        "pinned": True,
                        "watchdog_reset": False,
                        "max_context_window": 262144,
                        "recipe_options": {"ctx_size": 65536},
                    },
                    {
                        "model_name": "other-model",
                        "backend_alive": True,
                        "backend_health": "ready",
                        "status": "ready",
                        "is_busy": False,
                        "is_streaming": False,
                        "pinned": True,
                        "recipe_options": {"ctx_size": 196608},
                    },
                ],
        }
        report = self.report(self.invoke())
        self.assertEqual(report["effective_context_tokens"], 65536)
        self.assertTrue(report["idle_telemetry_verified"])
        self.assertEqual([method for method, _, _ in self.server.requests], ["GET", "POST"])

    def test_busy_any_resident_or_global_never_posts_even_with_override(self):
        for key, value in (
            ("busy", True), ("is_busy", True), ("streaming", True),
            ("is_streaming", True), ("is_processing", True), ("is_loading", True),
            ("active_requests", 1), ("pending_requests", 1), ("queued_requests", 1),
        ):
            for global_flag in (True, False):
                with self.subTest(key=key, global_flag=global_flag):
                    self.server.health = copy.deepcopy(HEALTH)
                    target = self.server.health
                    if not global_flag:
                        target = {"model_name": "other-model", "backend_alive": True, "backend_health": "ready"}
                        self.server.health["all_models_loaded"].append(target)
                    target[key] = value
                    self.report(self.invoke(["--allow-unverified-idle"]), "busy")
                    self.assert_no_post()

    def test_missing_or_invalid_workload_telemetry(self):
        self.server.health.pop("busy")
        self.server.health.pop("streaming")
        self.report(self.invoke(), "idle_unverified")
        self.assert_no_post()
        report = self.report(self.invoke(["--allow-unverified-idle"]))
        self.assertFalse(report["idle_telemetry_verified"])
        self.server.health["busy"] = "false"
        self.report(self.invoke(["--allow-unverified-idle"]), "invalid_health")
        self.assertEqual(sum(m == "POST" for m, _, _ in self.server.requests), 1)

    def test_success_payload_context_usage_nonce_and_no_mutations(self):
        usage = event({"choices": [], "usage": {
            "prompt_tokens": 97, "completion_tokens": 2, "total_tokens": 99,
            "private_path": "must-not-leak",
        }})
        self.server.fragments = [(0, READY + STOP + usage + DONE)]
        first = self.report(self.invoke())
        second = self.report(self.invoke(["--base-url", self.base + "/"]))
        for report in (first, second):
            self.assertEqual(report["effective_context_tokens"], 32768)
            self.assertEqual(report["server_version"], "11.9.0")
            self.assertEqual(report["finish_reason"], "stop")
            self.assertEqual(report["coverage"], "smoke_only")
            self.assertTrue(report["idle_telemetry_verified"])
            self.assertEqual(report["usage"], {"prompt_tokens": 97, "completion_tokens": 2, "total_tokens": 99})
        self.assertEqual(
            [(m, p) for m, p, _ in self.server.requests],
            [("GET", "/api/v1/health"), ("POST", "/api/v1/chat/completions")] * 2,
        )
        payload = self.server.requests[1][2]
        prompt = payload["messages"][0]["content"]
        self.assertEqual(set(payload), {
            "model", "messages", "temperature", "max_tokens", "reasoning_effort",
            "chat_template_kwargs", "stream", "stream_options",
        })
        self.assertEqual(payload["model"], MODEL)
        self.assertIs(payload["stream"], True)
        self.assertEqual(payload["max_tokens"], 16)
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["stream_options"], {"include_usage": True})
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertRegex(prompt, r"^Nonce: [0-9a-f]{32}\n")
        self.assertEqual(
            prompt.splitlines()[3:-1],
            [f"Record {i:06d}: blue pebble, green leaf, calm water." for i in range(1, 4)],
        )
        self.assertEqual(prompt.splitlines()[-1], "End of records. Reply only with READY.")
        self.assertNotEqual(prompt.splitlines()[0], self.server.requests[3][2]["messages"][0]["content"].splitlines()[0])

    def test_delayed_meaningful_output_ignores_keepalives_and_role(self):
        self.server.fragments = [
            (0, b": connected\n\n\n" + event("ping", "ping")
             + event({"type": "ping"}) + event(delta(role="assistant"))),
            (0.35, event(delta("RE"))),
            (0, event(delta("ADY")) + STOP + DONE),
        ]
        report = self.report(self.invoke(["--minimum-first-token-seconds", "0.2"]))
        self.assertGreaterEqual(report["first_token_seconds"], 0.30)
        self.assertEqual(report["first_token_kind"], "content")

    def test_health_latency_does_not_count_toward_first_token_gate(self):
        self.server.health_delay = 0.35
        report = self.report(self.invoke(["--minimum-first-token-seconds", "0.2"]), "too_fast")
        self.assertGreaterEqual(report["elapsed_seconds"], 0.35)
        self.assertLess(report["first_token_seconds"], 0.2)

    def test_default_threshold_rejects_short_success(self):
        self.report(self.invoke(arguments=[
            "--base-url", self.base, "--model", MODEL, "--records", "1",
        ]), "too_fast")

    def test_reasoning_counts_before_later_content(self):
        self.server.fragments = [
            (0, event(delta(reasoning_content="Check."))),
            (0.35, READY + STOP + DONE),
        ]
        report = self.report(self.invoke(["--minimum-first-token-seconds", "0.2"]), "too_fast")
        self.assertEqual(report["first_token_kind"], "reasoning_content")
        self.assertLess(report["first_token_seconds"], 0.2)

    def test_whitespace_is_conservatively_a_model_token(self):
        self.server.fragments = [(0, event(delta(" "))), (0.35, READY + STOP + DONE)]
        report = self.report(self.invoke(["--minimum-first-token-seconds", "0.2"]), "too_fast")
        self.assertLess(report["first_token_seconds"], 0.2)

    def test_fragmented_multiline_data_utf8_and_sse_line_endings(self):
        stream = (
            b"\xef\xbb\xbf: start\r\n\r\n"
            + event(delta(reasoning="caf\u00e9"))
            + b'id: 1\rretry: 1000\rdata: {"choices": [\r'
            + b'data: {"index":0,"delta":{"content":"READY"},"finish_reason":null}]}\r\r'
            + STOP.replace(b"\n", b"\r\n") + DONE
        )
        self.server.fragments = [(0, stream[i:i + 1]) for i in range(len(stream))]
        self.report(self.invoke())

    def test_embedded_errors_under_http_200_are_redacted(self):
        for data in (
            event({"error": {"message": "private-secret /private/path"}}),
            event({"type": "error", "message": "private-secret"}),
            event("private-secret", "error"),
            event({"error": "private-secret"}, "ping"),
            event({"choices": [{"index": 0, "delta": {}, "error": "private-secret"}]}),
            READY + event({"error": {"message": "private-secret"}}) + STOP + DONE,
        ):
            with self.subTest(data=data):
                self.server.fragments = [(0, data)]
                result = self.invoke()
                self.report(result, "embedded_error")
                self.assertNotIn("private-secret", result.stdout + result.stderr)

    def test_missing_done_and_unterminated_done_fail(self):
        for data in (
            READY + STOP, READY + STOP + b"data: [DONE]\n",
            READY + STOP + event("[DONE]", "ping"), b": ping\n\n", b"",
        ):
            with self.subTest(data=data):
                self.server.fragments = [(0, data)]
                self.report(self.invoke(), "missing_done")

    def test_bad_json_and_malformed_chat_fail(self):
        for data in (
            b"data: {broken}\n\n", event([]), event({"choices": None}),
            event({"choices": []}), event({"choices": [{"index": 0, "delta": None}]}),
            event({"choices": [{"index": 1, "delta": {"content": "READY"}}]}),
            event({"choices": [{"index": False, "delta": {"content": "READY"}}]}),
            event(delta(123)), event(delta(tool_calls=[{"index": 0}])),
            b'data: {"choices":[],"choices":[]}\n\n',
            b'data: {"choices":[],"usage":{"prompt_tokens":NaN}}\n\n',
            b"data: \xff\n\n",
            READY + STOP + READY + DONE,
        ):
            with self.subTest(data=data):
                self.server.fragments = [(0, data)]
                self.report(self.invoke(), "invalid_sse")

    def test_empty_wrong_or_incomplete_output_fail(self):
        for data in (
            DONE, STOP + DONE, event(delta(role="assistant")) + STOP + DONE,
            event(delta(reasoning_content="READY")) + STOP + DONE,
            event(delta(" \n")) + STOP + DONE,
            event(delta("NOT_READY")) + STOP + DONE,
            READY + DONE,
            READY + event({"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]}) + DONE,
        ):
            with self.subTest(data=data):
                self.server.fragments = [(0, data)]
                self.report(self.invoke(), "invalid_completion")

    def test_http_errors_and_redirects_not_followed(self):
        for stage in ("health", "chat"):
            for status in (302, 307, 500, 503):
                with self.subTest(stage=stage, status=status):
                    self.server.requests.clear()
                    self.server.health_status = status if stage == "health" else 200
                    self.server.chat_status = status if stage == "chat" else 200
                    self.report(self.invoke(), "http_error")
                    self.assertEqual(len(self.server.requests), 1 if stage == "health" else 2)
                    self.assertTrue(all(p in ("/api/v1/health", "/api/v1/chat/completions")
                                        for _, p, _ in self.server.requests))

    def test_health_bad_json_and_wrong_content_type(self):
        self.server.health = b"{broken}"
        self.report(self.invoke(), "invalid_health")
        self.assert_no_post()
        self.server.health = copy.deepcopy(HEALTH)
        self.server.content_type = "application/json"
        self.report(self.invoke(), "invalid_sse")

    def test_deadline_with_silent_or_keepalive_stream_cancels_connection(self):
        self.server.keep_open = True
        for drip in (False, True):
            with self.subTest(drip=drip):
                self.server.chat_disconnected.clear()
                self.server.drip = drip
                self.server.fragments = [(0, event(delta(role="assistant")))]
                report = self.report(self.invoke(["--timeout-seconds", "0.25"]), "timeout")
                self.assertIsNone(report["first_token_seconds"])
                self.assertLess(report["elapsed_seconds"], 2)
                self.assertTrue(self.server.chat_disconnected.wait(2), "Client did not close the HTTP socket")

    def test_health_deadline_prevents_chat(self):
        self.server.health_delay = 0.5
        self.report(self.invoke(["--timeout-seconds", "0.25"]), "timeout")
        self.assert_no_post()

    def test_deadline_also_bounds_slow_drip_headers(self):
        self.server.header_drip = True
        report = self.report(self.invoke(["--timeout-seconds", "0.25"]), "timeout")
        self.assertLess(report["elapsed_seconds"], 2)
        self.assertTrue(self.server.chat_disconnected.wait(2))

    def test_oversized_event_is_rejected(self):
        self.server.fragments = [(0, b"data: " + b"x" * 65537 + b"\n\n")]
        self.report(self.invoke(), "invalid_sse")

    def test_proxy_environment_is_ignored(self):
        env = os.environ.copy()
        for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            env[key] = "http://127.0.0.1:1"
        env["NO_PROXY"] = ""
        env["no_proxy"] = ""
        self.report(self.invoke(env=env))

    def test_server_version_and_usage_do_not_leak_arbitrary_metadata(self):
        self.server.health["version"] = "private-host/private-path"
        self.server.fragments = [(0, READY + STOP + event({
            "choices": [], "usage": {"prompt_tokens": 1, "secret": "private-secret"},
        }) + DONE)]
        result = self.invoke()
        report = self.report(result)
        self.assertIsNone(report["server_version"])
        self.assertNotIn("private-", result.stdout)


if __name__ == "__main__":
    unittest.main()
