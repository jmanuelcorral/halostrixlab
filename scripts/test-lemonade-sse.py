"""Synthetic Lemonade SSE acceptance probe (Python 3.9+ stdlib only).

Contract: --base-url is an HTTP(S) ORIGIN, e.g. http://localhost:13305,
not /v1 or /api/v1. Requests go directly to that origin, ignoring proxy
environment variables; redirects and authentication are never followed.
Only GET /api/v1/health and one POST /api/v1/chat/completions are used.
Reasoning is disabled per request with reasoning_effort=none and
chat_template_kwargs.enable_thinking=false; saved model settings are unchanged.

Health must expose status="ok", all_models_loaded with exactly one matching
model_name, backend_alive=true, backend_health="ready", and positive
recipe_options.ctx_size.
Explicit busy/streaming/processing flags or active/pending request counts
are checked globally and for every resident. If no workload telemetry is
present, --allow-unverified-idle requires the operator to independently
verify/reserve an idle server. Known activity is ALWAYS rejected. Health
is a snapshot, not an atomic reservation: prevent concurrent model changes
externally to avoid server-side auto-loading between GET and POST.

build_prompt(records, nonce=None) is importable for external token counting.
The CLI always uses a fresh leading nonce. Records are bounded, but characters
are NOT tokens: independently tokenize with the target tokenizer and include
chat-template/output overhead before a large trial. No tokenizer endpoint is
assumed. Rough sizing: 2,000 records may be 30k-45k tokens, NOT a guarantee.

PASS requires content exactly READY (apart from surrounding whitespace),
finish_reason="stop", [DONE], and first nonempty content/reasoning delta at
least --minimum-first-token-seconds after the POST body was sent. Headers,
role-only deltas and SSE keepalives do not count. Whitespace model deltas DO
count, conservatively, because they may represent actual decoded tokens.
Tool calls are deliberately unsupported. This measures client-observed
latency, not GPU prefill in isolation. A zero threshold is smoke-only.

The overall deadline includes health, connect, upload and streaming. An
independent watchdog cancels the socket even during a stalled read or
slow-drip headers. Stdout contains one redacted JSON report, never the URL,
model identifier, prompt, generated answer, raw server error or local path.
"""

import argparse
import http.client
import json
import math
import queue
import re
import secrets
import socket
import sys
import threading
import time
from urllib.parse import urlsplit


MAX_RECORDS = 10000
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_EVENT_BYTES = 65536
MAX_OUTPUT_CHARS = 32768
MAX_TOKENS = 16
ERRORS = {
    "invalid_arguments": "Invalid arguments; required: --base-url and --model. See --help.",
    "invalid_url": "Base URL must be an HTTP(S) origin without credentials, path, query, fragment or whitespace.",
    "invalid_model": "Model must be an explicit nonempty exact identifier without whitespace.",
    "invalid_limits": "Records or timing limits are outside the documented bounds.",
    "timeout": "Overall deadline expired; the HTTP connection was cancelled.",
    "transport_error": "Direct HTTP transport failed; no retry was attempted.",
    "http_error": "The server returned a non-200 HTTP status; redirects are not followed.",
    "invalid_health": "Health JSON or required health fields are invalid.",
    "not_resident": "The exact target must occur once in all_models_loaded.",
    "backend_not_ready": "The target backend is not explicitly ready.",
    "invalid_context": "Effective recipe_options.ctx_size must be a positive integer.",
    "busy": "Health reports an active, queued, loading or streaming workload.",
    "idle_unverified": "Health lacks workload telemetry; independently reserve an idle server before opting in.",
    "invalid_sse": "The response is not a valid bounded UTF-8 SSE chat stream.",
    "embedded_error": "The SSE stream contains a server error.",
    "missing_done": "The stream ended without a complete [DONE] event.",
    "invalid_completion": "Completion requires nonempty content READY and finish_reason stop.",
    "too_fast": "First model output arrived before the required threshold; slow-prefill coverage was not established.",
    "interrupted": "The operator interrupted the probe; the HTTP connection was cancelled.",
    "unexpected_error": "The probe encountered an unexpected local error.",
}


class ProbeError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(ERRORS[code])


def failure(code, **metadata):
    return {"status": "FAIL", "error_code": code, "message": ERRORS[code], **metadata}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps(failure("invalid_arguments")))
        raise SystemExit(2)


def parse_origin(value):
    try:
        if any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError
        if any(c in value for c in ("\\", "?", "#", "%", "@")):
            raise ValueError
        url = urlsplit(value)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or (url.port is not None and not 1 <= url.port <= 65535)
            or url.netloc.endswith(":")
        ):
            raise ValueError
        host = url.hostname
        if ":" in host:
            socket.inet_pton(socket.AF_INET6, host)
        elif not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise ValueError
        return url
    except (ValueError, OSError):
        raise ProbeError("invalid_url") from None


def build_prompt(records, nonce=None):
    """Return synthetic text only; supply a nonce only for offline token counts."""
    if type(records) is not int or not 1 <= records <= MAX_RECORDS:
        raise ValueError("records must be between 1 and 10000")
    if nonce is None:
        nonce = secrets.token_hex(16)
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("nonce must contain 32 lowercase hexadecimal characters")
    lines = [
        f"Nonce: {nonce}",
        "Read these synthetic records. Do not summarize or reason aloud.",
        "After the final record, reply only with READY.",
    ]
    lines.extend(
        f"Record {i:06d}: blue pebble, green leaf, calm water."
        for i in range(1, records + 1)
    )
    lines.append("End of records. Reply only with READY.")
    return "\n".join(lines)


def strict_json(value):
    def pairs(items):
        result = {}
        for key, val in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = val
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite JSON value")

    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)


def check_health(health, model, allow_unverified_idle):
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise ProbeError("invalid_health")
    models = health.get("all_models_loaded")
    if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
        raise ProbeError("invalid_health")
    matches = [m for m in models if m.get("model_name") == model]
    if len(matches) != 1:
        raise ProbeError("not_resident")
    target = matches[0]
    if target.get("backend_alive") is not True or target.get("backend_health") != "ready":
        raise ProbeError("backend_not_ready")
    options = target.get("recipe_options")
    ctx_size = options.get("ctx_size") if isinstance(options, dict) else None
    if type(ctx_size) is not int or ctx_size <= 0:
        raise ProbeError("invalid_context")

    bool_fields = (
        "busy", "is_busy", "streaming", "is_streaming", "is_processing",
        "processing", "is_loading", "loading",
    )
    count_fields = ("active_requests", "pending_requests", "queued_requests")

    def workload_state(obj):
        observed = False
        for key in bool_fields:
            if key in obj:
                if type(obj[key]) is not bool:
                    raise ProbeError("invalid_health")
                if obj[key]:
                    raise ProbeError("busy")
                # Absence of loading alone does not prove inference is idle.
                observed |= key not in ("is_loading", "loading")
        for key in count_fields:
            if key in obj:
                if type(obj[key]) is not int or obj[key] < 0:
                    raise ProbeError("invalid_health")
                if obj[key] > 0:
                    raise ProbeError("busy")
                observed |= key == "active_requests"
        if obj.get("status") in ("busy", "streaming", "processing", "loading"):
            raise ProbeError("busy")
        return observed

    global_observed = workload_state(health)
    resident_observed = [workload_state(m) for m in models]
    idle_verified = global_observed or all(resident_observed)
    if not idle_verified and not allow_unverified_idle:
        raise ProbeError("idle_unverified")
    version = health.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]{1,32})?", version):
        version = None
    return {
        "server_version": version,
        "effective_context_tokens": ctx_size,
        "idle_telemetry_verified": idle_verified,
    }


class DirectClient:
    """One request at a time; cancellation also wakes blocked HTTP header reads."""

    def __init__(self, origin, deadline):
        self.origin = origin
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.sock = None

    def remaining(self):
        left = self.deadline - time.monotonic()
        if self.cancelled.is_set() or left <= 0:
            raise ProbeError("timeout")
        return left

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.sock is not None:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.sock.close()

    def request(self, method, path, body, consume):
        cls = http.client.HTTPSConnection if self.origin.scheme == "https" else http.client.HTTPConnection
        connection = cls(self.origin.hostname, self.origin.port, timeout=self.remaining())
        response = None
        try:
            connection.connect()
            with self.lock:
                self.remaining()
                self.sock = connection.sock
            headers = {"Accept": "text/event-stream" if method == "POST" else "application/json"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            connection.request(method, path, body=body, headers=headers)
            sent_at = time.monotonic()
            self.remaining()
            response = connection.getresponse()
            if response.status != 200:
                raise ProbeError("http_error")
            return consume(response, sent_at)
        finally:
            if response is not None:
                response.close()
            connection.close()
            with self.lock:
                self.sock = None

    def chunks(self, response):
        size = 0
        while True:
            self.remaining()
            chunk = response.read1(4096)
            self.remaining()
            if not chunk:
                return
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                raise ProbeError("invalid_sse")
            yield chunk


def sse_events(chunks):
    """Parse SSE framing independently of TCP writes, including CR/LF/CRLF."""
    line = bytearray()
    data = []
    event = ""
    event_size = 0
    skip_lf = False
    first_line = True
    for chunk in chunks:
        for byte in chunk:
            if skip_lf and byte == 10:
                skip_lf = False
                continue
            skip_lf = False
            if byte not in (10, 13):
                line.append(byte)
                if len(line) > MAX_EVENT_BYTES:
                    raise ProbeError("invalid_sse")
                continue
            skip_lf = byte == 13
            try:
                text = line.decode("utf-8")
            except UnicodeError:
                raise ProbeError("invalid_sse") from None
            line.clear()
            if first_line:
                text = text.removeprefix("\ufeff")
                first_line = False
            if not text:
                if data or event:
                    yield event, "\n".join(data)
                data = []
                event = ""
                event_size = 0
                continue
            if text.startswith(":"):
                continue
            key, separator, value = text.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if key == "data":
                data.append(value)
                event_size += len(value.encode("utf-8")) + 1
            elif key == "event":
                event = value
            if event_size > MAX_EVENT_BYTES:
                raise ProbeError("invalid_sse")
    # An unterminated last event is NOT a completion signal.
    raise ProbeError("missing_done")


def consume_chat(response, sent_at, client, report):
    if response.getheader("Content-Type", "").split(";")[0].strip().lower() != "text/event-stream":
        raise ProbeError("invalid_sse")
    content = ""
    output_chars = 0
    first_at = None
    finish = None
    for event, data in sse_events(client.chunks(response)):
        client.remaining()
        if event.lower() == "error":
            raise ProbeError("embedded_error")
        if not data.strip():
            continue
        if data.strip() == "[DONE]":
            if event.lower() in ("ping", "keepalive"):
                continue
            report["finish_reason"] = finish
            if first_at is None or content.strip() != "READY" or finish != "stop":
                raise ProbeError("invalid_completion")
            return
        try:
            payload = strict_json(data)
        except (ValueError, UnicodeError):
            if event.lower() in ("ping", "keepalive"):
                continue
            raise ProbeError("invalid_sse") from None
        if isinstance(payload, dict) and (
            payload.get("error") is not None or payload.get("type") == "error"
        ):
            raise ProbeError("embedded_error")
        if event.lower() in ("ping", "keepalive") or (
            isinstance(payload, dict) and payload.get("type") in ("ping", "keepalive")
        ):
            continue
        if not isinstance(payload, dict):
            raise ProbeError("invalid_sse")
        usage = payload.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                raise ProbeError("invalid_sse")
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if key in usage:
                    if type(usage[key]) is not int or usage[key] < 0:
                        raise ProbeError("invalid_sse")
                    report["usage"][key] = usage[key]
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) > 1:
            raise ProbeError("invalid_sse")
        if not choices:
            if usage is None:
                raise ProbeError("invalid_sse")
            continue
        choice = choices[0]
        if not isinstance(choice, dict) or type(choice.get("index")) is not int or choice["index"] != 0:
            raise ProbeError("invalid_sse")
        if choice.get("error") is not None:
            raise ProbeError("embedded_error")
        delta = choice.get("delta")
        if not isinstance(delta, dict) or any(delta.get(k) for k in ("tool_calls", "function_call")):
            raise ProbeError("invalid_sse")
        for key in ("content", "reasoning_content", "reasoning"):
            text = delta.get(key)
            if text is not None and not isinstance(text, str):
                raise ProbeError("invalid_sse")
            if text:
                if finish is not None:
                    raise ProbeError("invalid_sse")
                if first_at is None:
                    first_at = time.monotonic()
                    report["first_token_seconds"] = first_at - sent_at
                    report["first_token_kind"] = key
                output_chars += len(text)
                if output_chars > MAX_OUTPUT_CHARS:
                    raise ProbeError("invalid_sse")
                if key == "content":
                    content += text
        reason = choice.get("finish_reason")
        if reason is not None:
            if reason != "stop" or finish is not None:
                raise ProbeError("invalid_completion")
            finish = reason
            report["finish_reason"] = reason


def run_probe(args, client, report):
    def consume_health(response, sent_at):
        try:
            return strict_json(b"".join(client.chunks(response)).decode("utf-8"))
        except (ValueError, UnicodeError):
            raise ProbeError("invalid_health") from None

    health = client.request("GET", "/api/v1/health", None, consume_health)
    report.update(check_health(health, args.model, args.allow_unverified_idle))
    prompt = build_prompt(args.records)
    report["prompt_characters"] = len(prompt)
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    client.request(
        "POST", "/api/v1/chat/completions",
        json.dumps(payload).encode("utf-8"),
        lambda response, sent_at: consume_chat(response, sent_at, client, report),
    )
    if report["first_token_seconds"] < args.minimum_first_token_seconds:
        raise ProbeError("too_fast")


def main(argv=None):
    parser = JsonArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--base-url", required=True, help="HTTP(S) origin only; no API prefix.")
    parser.add_argument("--model", required=True, help="Exact already-resident model ID.")
    parser.add_argument("--records", type=int, default=2000, help="Synthetic records: 1..10000 (default: 2000).")
    parser.add_argument("--minimum-first-token-seconds", type=float, default=130.0,
                        help="Required first-token delay; 0 is smoke-only (default: 130).")
    parser.add_argument("--timeout-seconds", type=float, default=900.0,
                        help="Overall deadline: >0, <=3600 and > minimum delay (default: 900).")
    parser.add_argument("--allow-unverified-idle", action="store_true",
                        help="Operator has independently reserved idle service; NEVER overrides known activity.")
    args = parser.parse_args(argv)
    started = time.monotonic()
    report = {"status": "FAIL"}
    client = None
    try:
        origin = parse_origin(args.base_url)
        if not args.model or len(args.model) > 256 or any(c.isspace() or ord(c) < 32 for c in args.model):
            raise ProbeError("invalid_model")
        if (
            not 1 <= args.records <= MAX_RECORDS
            or not math.isfinite(args.minimum_first_token_seconds)
            or not math.isfinite(args.timeout_seconds)
            or not 0 <= args.minimum_first_token_seconds < args.timeout_seconds <= 3600
        ):
            raise ProbeError("invalid_limits")
        report.update({
            "records": args.records,
            "minimum_first_token_seconds": args.minimum_first_token_seconds,
            "coverage": "smoke_only" if args.minimum_first_token_seconds == 0 else "first_token_threshold",
            "first_token_seconds": None,
            "finish_reason": None,
            "usage": {},
        })
        client = DirectClient(origin, started + args.timeout_seconds)
        results = queue.Queue(maxsize=1)

        def worker():
            worker_report = {**report, "usage": {}}
            error = None
            try:
                run_probe(args, client, worker_report)
            except ProbeError as exc:
                error = exc.code
            except (TimeoutError, socket.timeout):
                error = "timeout"
            except (OSError, http.client.HTTPException):
                error = "transport_error"
            except Exception:
                error = "unexpected_error"
            results.put((error, worker_report))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            error, report = results.get(timeout=client.remaining())
        except queue.Empty:
            raise ProbeError("timeout") from None
        client.remaining()
        if error is not None:
            raise ProbeError(error)
        report["status"] = "PASS"
    except ProbeError as exc:
        if client is not None:
            client.cancel()
        report.update(failure(exc.code))
    except KeyboardInterrupt:
        report.update(failure("interrupted"))
    except Exception:
        report.update(failure("unexpected_error"))
    finally:
        if client is not None:
            client.cancel()
    report["elapsed_seconds"] = time.monotonic() - started
    print(json.dumps(report, allow_nan=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
