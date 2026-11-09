import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import signal
import subprocess
import threading
import time


MODEL = 'winnow:12b'
ALIAS = 'winnow-12b-cpu'
MAX_BODY = 65536
MAX_RESPONSE = 1048576
BACKEND_PORT = 11435
TIMEOUT = 300
SMOKE = {'model': MODEL, 'state': {'paid': True}, 'questions': {
    'paid': {'type': 'noul', 'instructions': 'Is paid true in the supplied state?'}}}


def validate_request(body):
    if not isinstance(body, dict) or set(body) - {'model', 'state', 'questions'}:
        raise ValueError('Unsupported fields')
    if body.get('model', MODEL) not in (MODEL, ALIAS):
        raise ValueError('Unsupported model')
    if not isinstance(body.get('state'), (str, dict, list)):
        raise ValueError('Invalid state')
    questions = body.get('questions')
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 8:
        raise ValueError('Expected 1-8 questions')
    for name, question in questions.items():
        if not name or not isinstance(question, dict) or set(question) - {'type', 'instructions', 'criteria'}:
            raise ValueError('Invalid question')
        if question.get('instructions') is not None and not isinstance(question['instructions'], (str, dict, list)):
            raise ValueError('Invalid instructions')
        kind = question.get('type')
        criteria = question.get('criteria')
        if kind == 'noul':
            if criteria is not None and (not isinstance(criteria, dict) or set(criteria) - {'false', 'true'}):
                raise ValueError('Invalid noul criteria')
        elif kind == 'choice':
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 64 or any(not key for key in criteria):
                raise ValueError('Invalid choice criteria')
        elif kind == 'score':
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 64:
                raise ValueError('Invalid score criteria')
        else:
            raise ValueError('Invalid question type')
        values = criteria.values() if isinstance(criteria, dict) else criteria or []
        if any(value is not None and not isinstance(value, (str, dict, list)) for value in values):
            raise ValueError('Invalid criterion description')
    return {**body, 'model': MODEL}


def reject_constant(value):
    raise ValueError('Non-finite JSON number')


def backend(path, payload=None, timeout=TIMEOUT):
    connection = http.client.HTTPConnection('127.0.0.1', BACKEND_PORT, timeout=timeout)
    try:
        content = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        connection.request('GET' if payload is None else 'POST', path, body=content,
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Backend response too large')
        if response.status != 200:
            return response.status, None
        return 200, json.loads(raw, parse_constant=reject_constant)
    finally:
        connection.close()


class State:
    def __init__(self, child=None):
        self.child = child
        self.ready = False
        self.failed = False
        self.gate = threading.Lock()

    def healthy(self):
        return self.ready and not self.failed and (self.child is None or self.child.poll() is None)

    def warmup(self):
        status, result = backend('/v1/systemone', SMOKE)
        if status != 200 or not isinstance(result, dict) or not result.get('answers'):
            raise ValueError('Model did not complete readiness inference')
        status, result = backend('/api/ps')
        models = result.get('models', []) if status == 200 and isinstance(result, dict) else []
        if len(models) != 1 or models[0].get('device') != 'cpu':
            raise ValueError('Expected exactly one CPU runner')
        self.ready = True


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, state):
        self.state = state
        self.workers = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.workers.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.workers.release()

    def handle_error(self, request, client_address):
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = 'HaloDecision'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def respond(self, status, body):
        raw = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_GET(self):
        if self.path not in ('/', '/ready'):
            self.respond(404, {'error': 'Route not available'})
        elif self.server.state.healthy():
            self.respond(200, {'status': 'ready', 'model': MODEL, 'alias': ALIAS, 'device': 'cpu'})
        else:
            self.respond(503, {'error': 'Model not ready'})

    def do_POST(self):
        if self.path != '/v1/systemone':
            self.respond(404, {'error': 'Route not available'})
            return
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
            self.respond(400, {'error': 'A single Content-Length is required'})
            return
        size = int(lengths[0])
        if not 0 < size <= MAX_BODY:
            self.respond(413, {'error': 'Body must fit 64 KiB'})
            return
        if self.headers.get_content_type() != 'application/json':
            self.respond(415, {'error': 'Expected application/json'})
            return
        state = self.server.state
        if not state.healthy():
            self.respond(503, {'error': 'Model not ready'})
            return
        if not state.gate.acquire(blocking=False):
            self.respond(429, {'error': 'Decision worker busy'})
            return
        try:
            try:
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('Incomplete body')
                body = validate_request(json.loads(raw, parse_constant=reject_constant))
            except (ValueError, TypeError, RecursionError, TimeoutError):
                self.respond(400, {'error': 'Invalid typed decision request'})
                return
            try:
                status, result = backend('/v1/systemone', body)
            except (OSError, ValueError, http.client.HTTPException):
                state.failed = True
                self.respond(503, {'error': 'Backend unavailable; reload model'})
                return
            if status == 200:
                if not isinstance(result, dict) or not result.get('answers'):
                    state.failed = True
                    self.respond(503, {'error': 'Invalid backend response'})
                else:
                    self.respond(200, result)
            elif status in (400, 413, 422):
                self.respond(status, {'error': 'Backend rejected schema or context budget'})
            else:
                state.failed = True
                self.respond(503, {'error': 'Backend unavailable; reload model'})
        finally:
            state.gate.release()


def main():
    child = subprocess.Popen(['/usr/bin/ollaya', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state = State(child)
    server = Server(('0.0.0.0', 8000), state)
    stopping = threading.Event()
    def terminate(signum, frame):
        stopping.set()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, terminate)
    def prepare():
        deadline = time.monotonic() + 60
        while not stopping.is_set() and time.monotonic() < deadline:
            try:
                backend('/api/version', timeout=2)
                state.warmup()
                return
            except (OSError, ValueError, http.client.HTTPException):
                if child.poll() is not None:
                    break
                time.sleep(1)
        state.failed = True
    threading.Thread(target=prepare, daemon=True).start()
    server.timeout = 0.5
    try:
        while not stopping.is_set() and child.poll() is None and not state.failed:
            server.handle_request()
    finally:
        state.ready = False
        server.server_close()
        child.terminate()
        try:
            child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    return 1 if state.failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
