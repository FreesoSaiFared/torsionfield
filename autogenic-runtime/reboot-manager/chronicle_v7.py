#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "0.7.0"
HOST = "127.0.0.1"
PORT = 17376
MAX_JOURNAL_BYTES = 8 * 1024 * 1024
lock = threading.RLock()


def state_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Torsionfield" / "RebootSupervisor"
    else:
        base = Path.home() / ".torsionfield" / "RebootSupervisor"
    root = base / "chronicle"
    root.mkdir(parents=True, exist_ok=True)
    return root


ROOT = state_root()
LATEST = ROOT / "latest.json"
EVENTS = ROOT / "events.jsonl"
GHOSTS = ROOT / "ghosts.json"


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def atomic_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def rotate_events() -> None:
    if EVENTS.exists() and EVENTS.stat().st_size > MAX_JOURNAL_BYTES:
        previous = EVENTS.with_suffix(".jsonl.1")
        previous.unlink(missing_ok=True)
        EVENTS.replace(previous)


def append_event(event: dict) -> None:
    with lock:
        rotate_events()
        with EVENTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def checkpoint_key(value: dict) -> str:
    state = value.get("state") or {}
    return str(
        value.get("key")
        or state.get("conversationId")
        or value.get("conversationId")
        or value.get("url")
        or f"{value.get('client','?')}:{value.get('tabId','?')}"
    )


def ingest(kind: str, body: dict) -> dict:
    now = time.time()
    event = {**body, "kind": kind, "serverTs": now}
    append_event(event)
    if kind == "checkpoint":
        with lock:
            latest = load_json(LATEST, {})
            key = checkpoint_key(body)
            latest[key] = {**body, "key": key, "serverTs": now}
            atomic_json(LATEST, latest)
        return {"ok": True, "key": key, "serverTs": now}
    if kind == "ghost":
        with lock:
            ghosts = load_json(GHOSTS, {})
            ghost_id = str(body.get("ghostId") or checkpoint_key(body))
            ghosts[ghost_id] = {**body, "ghostId": ghost_id, "serverTs": now}
            atomic_json(GHOSTS, ghosts)
        return {"ok": True, "ghostId": ghost_id, "serverTs": now}
    return {"ok": True, "serverTs": now}


def tail_events(limit: int) -> list[dict]:
    if not EVENTS.exists():
        return []
    lines = EVENTS.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 500)):]
    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except Exception:
            pass
    return result


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
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        length = int(self.headers.get("content-length", "0") or 0)
        return json.loads((self.rfile.read(length) if length else b"{}").decode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            latest = load_json(LATEST, {})
            return self.send_json(200, {"ok": True, "version": VERSION, "checkpoints": len(latest)})
        if parsed.path == "/latest":
            return self.send_json(200, {"latest": load_json(LATEST, {})})
        if parsed.path == "/ghosts":
            return self.send_json(200, {"ghosts": load_json(GHOSTS, {})})
        if parsed.path == "/events":
            query = parse_qs(parsed.query)
            limit = int((query.get("limit") or ["100"])[0])
            return self.send_json(200, {"events": tail_events(limit)})
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self.body()
        except Exception as exc:
            return self.send_json(400, {"error": repr(exc)})
        if parsed.path == "/event":
            return self.send_json(200, ingest("event", body))
        if parsed.path == "/checkpoint":
            return self.send_json(200, ingest("checkpoint", body))
        if parsed.path == "/ghost":
            return self.send_json(200, ingest("ghost", body))
        return self.send_json(404, {"error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        probe = ingest("checkpoint", {"client": "self-test", "tabId": 1, "url": "https://chatgpt.com/c/test", "state": {"conversationId": "test", "streaming": False}})
        assert probe["ok"] and load_json(LATEST, {}).get("test")
        print(json.dumps({"PASS": True, "version": VERSION, "root": str(ROOT)}, indent=2))
        return 0
    print(f"TF Reboot Chronicle {VERSION} http://{HOST}:{args.port}", flush=True)
    ThreadingHTTPServer((HOST, args.port), Handler).serve_forever(poll_interval=0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
