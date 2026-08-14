#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 17375
VERSION = "0.3.0"
lock = threading.RLock()
condition = threading.Condition(lock)
clients: dict[str, dict] = {}
queues: dict[str, deque] = defaultdict(deque)
pending: dict[str, dict] = {}


def snapshot_clients() -> dict:
    with lock:
        now = time.time()
        return {
            key: {
                **value,
                "ageSeconds": round(now - float(value.get("lastSeen", 0)), 2),
                "queued": len(queues[key]),
            }
            for key, value in clients.items()
        }


def rpc(client: str, message: dict, timeout_ms: int = 30_000):
    with condition:
        info = clients.get(client)
        if not info or time.time() - float(info.get("lastSeen", 0)) > 35:
            raise RuntimeError(f"bridge-client-unavailable:{client}")
        request_id = str(uuid.uuid4())
        event = threading.Event()
        queues[client].append(
            {
                "id": request_id,
                "message": message,
                "timeoutMs": timeout_ms,
                "createdAt": time.time(),
            }
        )
        pending[request_id] = {"event": event, "result": None, "client": client}
        condition.notify_all()

    if not event.wait(timeout_ms / 1000 + 3):
        with lock:
            pending.pop(request_id, None)
        raise TimeoutError(f"bridge-command-timeout:{request_id}")

    with lock:
        record = pending.pop(request_id, None)
    result = (record or {}).get("result") or {"ok": False, "error": "result-missing"}
    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "extension-rpc-failed")
    return result.get("value")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status: int, value) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        return json.loads((self.rfile.read(length) if length else b"{}").decode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self.send_json(200, {"ok": True, "version": VERSION, "clients": snapshot_clients()})
        if parsed.path == "/api/clients":
            return self.send_json(200, {"clients": snapshot_clients()})
        if parsed.path == "/api/next":
            query = parse_qs(parsed.query)
            client = (query.get("client") or [""])[0]
            wait_seconds = min(25.0, max(0.0, float((query.get("wait") or ["20"])[0])))
            deadline = time.time() + wait_seconds
            with condition:
                clients.setdefault(client, {"client": client})["lastSeen"] = time.time()
                while not queues[client] and time.time() < deadline:
                    condition.wait(min(1.0, max(0.0, deadline - time.time())))
                    clients[client]["lastSeen"] = time.time()
                command = queues[client].popleft() if queues[client] else None
            return self.send_json(200, {"command": command})
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self.read_body()
        except Exception as exc:
            return self.send_json(400, {"error": repr(exc)})

        if parsed.path == "/api/hello":
            client = str(body.get("client") or "")
            if not client:
                return self.send_json(400, {"error": "client-required"})
            with lock:
                clients[client] = {**body, "lastSeen": time.time()}
            return self.send_json(200, {"ok": True})

        if parsed.path == "/api/result":
            request_id = str(body.get("id") or "")
            with lock:
                record = pending.get(request_id)
                if record:
                    record["result"] = body.get("result") or {}
                    record["event"].set()
                client = str(body.get("client") or "")
                if client in clients:
                    clients[client]["lastSeen"] = time.time()
            return self.send_json(200, {"ok": bool(record)})

        if parsed.path == "/api/rpc":
            try:
                value = rpc(
                    str(body["client"]),
                    body.get("message") or {},
                    int(body.get("timeoutMs") or 30_000),
                )
                return self.send_json(200, {"ok": True, "value": value})
            except Exception as exc:
                return self.send_json(503, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

        return self.send_json(404, {"error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    print(f"TF Browser Bridge {VERSION} http://{HOST}:{args.port}", flush=True)
    ThreadingHTTPServer((HOST, args.port), Handler).serve_forever(poll_interval=0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
