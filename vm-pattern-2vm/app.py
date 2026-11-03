import os
import json
import time
import threading
import hmac
from collections import deque
from pathlib import PurePosixPath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError

ROLE = os.environ.get("ROLE", "api")
TOKEN = os.environ.get("INTERNAL_TOKEN", "")
LIMIT = int(os.environ.get("REQUEST_LIMIT", "5"))
WINDOW = float(os.environ.get("WINDOW_SECONDS", "10"))
LOCK = threading.Lock()
HITS = {}
EVENTS = deque(maxlen=1000)
ALERTS = deque(maxlen=100)
OPENER = build_opener(ProxyHandler({}))

def check_rate(source, now=None):
    now = time.monotonic() if now is None else now
    with LOCK:
        for key in list(HITS):
            if not HITS[key] or HITS[key][-1] <= now - WINDOW:
                del HITS[key]
        if source not in HITS and len(HITS) >= 10000:
            return False
        queue = HITS.setdefault(source, deque())
        while queue and queue[0] <= now - WINDOW:
            queue.popleft()
        if len(queue) >= LIMIT:
            return False
        queue.append(now)
        return True

def check_file_policy(operation, path):
    if operation != "read":
        return False, "only_read_allowed"
    if not isinstance(path, str) or len(path) > 256:
        return False, "invalid_path"
    if "\\" in path or "\x00" in path:
        return False, "invalid_path"
    if ".." in PurePosixPath(path).parts or path != "/protected/demo.txt":
        return False, "path_not_allowed"
    return True, "allowed"

def get_data(resource):
    if resource == "/data":
        return 200, {"message": "Protected application in Kubernetes on VM2", "role": "data"}
    if resource == "/file":
        try:
            with open("/protected/demo.txt", encoding="utf-8") as stream:
                return 200, {"content": stream.read()}
        except OSError:
            return 503, {"error": "storage_unavailable"}
    return 404, {"error": "not_found"}

def save_event(event):
    record = {"time": time.time(), "service": str(event.get("service", "unknown"))[:64],
              "kind": str(event.get("kind", "unknown"))[:64],
              "source": str(event.get("source", ""))[:128]}
    with LOCK:
        EVENTS.append(record)
        if record["kind"] in {"rate_blocked", "file_blocked", "policy_unavailable"}:
            ALERTS.append(record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record

def call(service, path, payload=None):
    if service not in {"api", "data", "security", "audit"}:
        return 400, {"error": "invalid_service"}
    raw = None if payload is None else json.dumps(payload).encode()
    request = Request("http://" + service + ":8000" + path, data=raw,
                      headers={"Content-Type": "application/json", "X-Internal-Token": TOKEN})
    try:
        with OPENER.open(request, timeout=4) as response:
            return response.status, json.loads(response.read(65536))
    except HTTPError as error:
        return error.code, {"error": "upstream_rejected", "status": error.code}
    except (URLError, TimeoutError, OSError, ValueError):
        return 503, {"error": "upstream_unavailable"}

def audit(kind, source):
    status, _ = call("audit", "/events", {"service": ROLE, "kind": kind, "source": source})
    if status != 201:
        print(json.dumps({"kind": "audit_unavailable", "original_kind": kind}), flush=True)

def proxy_request():
    # The port-forward lab uses a global limit, not an external-IP limit.
    if not check_rate("gateway-ingress"):
        audit("rate_blocked", "gateway-ingress")
        return 429, {"error": "rate_limit_exceeded"}
    audit("request_allowed", "gateway-ingress")
    return call("api", "/api/data")

def handle_file_operation(operation, path):
    status, decision = call("security", "/check", {"operation": operation, "path": path})
    if status != 200:
        audit("policy_unavailable", "file_request")
        return 503, {"error": "policy_unavailable"}
    if not decision.get("allowed", False):
        audit("file_blocked", "file_request")
        return 403, {"error": decision.get("reason", "denied")}
    return call("data", "/file")

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def reply(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        if self.command == "GET" and self.path == "/health":
            return self.reply(200, {"status": "ok", "role": ROLE})
        supplied = self.headers.get("X-Internal-Token", "").encode("utf-8")
        if ROLE != "gateway" and (not TOKEN or not hmac.compare_digest(supplied, TOKEN.encode("utf-8"))):
            return self.reply(403, {"error": "internal_access_only"})
        payload = {}
        if self.command == "POST":
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    return self.reply(413, {"error": "body_size"})
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "invalid_json"})
        if ROLE == "gateway":
            if self.command == "GET" and self.path == "/api/data":
                return self.reply(*proxy_request())
            if self.command == "POST" and self.path == "/file-operation":
                if not check_rate("gateway-ingress"):
                    audit("rate_blocked", "gateway-ingress")
                    return self.reply(429, {"error": "rate_limit_exceeded"})
                return self.reply(*call("api", "/file-operation", payload))
            if self.command == "GET" and self.path == "/":
                return self.reply(200, {"project": "Two-VM Kubernetes lab", "endpoint": "/api/data"})
        if ROLE == "api":
            if self.command == "GET" and self.path == "/api/data":
                return self.reply(*call("data", "/data"))
            if self.command == "POST" and self.path == "/file-operation":
                return self.reply(*handle_file_operation(payload.get("operation"), payload.get("path")))
        if ROLE == "data" and self.command == "GET":
            return self.reply(*get_data(self.path))
        if ROLE == "security" and self.command == "POST" and self.path == "/check":
            allowed, reason = check_file_policy(payload.get("operation"), payload.get("path"))
            return self.reply(200, {"allowed": allowed, "reason": reason})
        if ROLE == "audit":
            if self.command == "POST" and self.path == "/events":
                return self.reply(201, save_event(payload))
            if self.command == "GET" and self.path in {"/events", "/alerts"}:
                with LOCK:
                    items = list(EVENTS if self.path == "/events" else ALERTS)
                return self.reply(200, {"items": items})
        return self.reply(404, {"error": "not_found"})

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    if len(TOKEN) < 32:
        raise SystemExit("INTERNAL_TOKEN must have at least 32 characters")
    if ROLE not in {"gateway", "api", "data", "security", "audit"}:
        raise SystemExit("Unknown ROLE")
    print("Starting " + ROLE, flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
