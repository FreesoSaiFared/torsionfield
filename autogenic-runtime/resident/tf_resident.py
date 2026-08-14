#!/usr/bin/env python3
from __future__ import annotations

import base64, json, os, platform, secrets, signal, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

VERSION = "0.4.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17373


def is_elevated() -> bool:
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return bool(hasattr(os, "geteuid") and os.geteuid() == 0)


def default_state_dir() -> Path:
    override = os.environ.get("TF_RESIDENT_STATE")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Torsionfield" / "resident"
    return Path("/var/lib/torsionfield") if hasattr(os, "geteuid") and os.geteuid() == 0 else Path.home() / ".torsionfield"


class ResidentState:
    def __init__(self):
        self.state_dir = default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.state_dir / "token"
        self.browser_path = self.state_dir / "browser.json"
        self.log_path = self.state_dir / "resident.jsonl"
        self.token = self._load_or_create_token()
        self.lock = threading.RLock()

    def _load_or_create_token(self):
        if self.token_path.exists():
            return self.token_path.read_text(encoding="utf-8").strip()
        token = secrets.token_urlsafe(48)
        self.token_path.write_text(token + "\n", encoding="utf-8")
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass
        return token

    def log(self, event, **data):
        with self.lock:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "event": event, **data}, ensure_ascii=False) + "\n")

    def save_browser(self, spec):
        with self.lock:
            self.browser_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    def load_browser(self):
        try:
            return json.loads(self.browser_path.read_text(encoding="utf-8"))
        except Exception:
            return {}


STATE = ResidentState()


def merged_env(extra):
    env = os.environ.copy()
    if isinstance(extra, dict):
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def shell_command(command):
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command] if os.name == "nt" else ["/bin/sh", "-lc", command]


def command_from_payload(payload):
    if isinstance(payload.get("argv"), list) and payload["argv"]:
        return [str(x) for x in payload["argv"]]
    if isinstance(payload.get("shell"), str) and payload["shell"].strip():
        return shell_command(payload["shell"])
    raise ValueError("expected non-empty argv[] or shell string")


def process_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def kill_pid(pid, tree=True, force=True):
    pid = int(pid)
    if pid <= 0:
        raise ValueError("pid must be positive")
    if os.name == "nt":
        args = ["taskkill", "/PID", str(pid)] + (["/T"] if tree else []) + (["/F"] if force else [])
        cp = subprocess.run(args, text=True, capture_output=True)
        return {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(os.getpgid(pid), sig) if tree else os.kill(pid, sig)
        return {"returncode": 0, "stdout": "", "stderr": ""}
    except ProcessLookupError:
        return {"returncode": 0, "stdout": "already stopped", "stderr": ""}


def find_chrome(explicit=None):
    candidates = [explicit] if explicit else []
    if os.name == "nt":
        for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(name)
            if root:
                candidates += [
                    str(Path(root) / "Google/Chrome/Application/chrome.exe"),
                    str(Path(root) / "Google/Chrome SxS/Application/chrome.exe"),
                    str(Path(root) / "Chromium/Application/chrome.exe"),
                    str(Path(root) / "Microsoft/Edge/Application/msedge.exe"),
                ]
    else:
        candidates += ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]
    from shutil import which
    for candidate in filter(None, candidates):
        p = Path(candidate)
        if p.is_absolute() and p.exists():
            return str(p)
        resolved = which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("Chrome/Chromium executable not found")


def debug_endpoint(port: int, timeout: float = 0.5):
    try:
        with urlopen(f"http://127.0.0.1:{int(port)}/json/version", timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body if isinstance(body, dict) else None
    except Exception:
        return None


def windows_listener_pid(port: int):
    if os.name != "nt":
        return None
    cp = subprocess.run(["netstat", "-ano", "-p", "tcp"], text=True, capture_output=True)
    for line in cp.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            local_port = int(parts[1].rsplit(":", 1)[1])
            owner = int(parts[4])
        except (ValueError, IndexError):
            continue
        if local_port == int(port):
            return owner
    return None


def windows_direct_child(parent_pid: int, exe_name: str):
    if os.name != "nt":
        return None
    safe_name = exe_name.replace("'", "''")
    command = (
        f"Get-CimInstance Win32_Process -Filter \"ParentProcessId={int(parent_pid)}\" | "
        f"Where-Object {{$_.Name -eq '{safe_name}'}} | Select-Object -First 1 -ExpandProperty ProcessId"
    )
    cp = subprocess.run(["powershell", "-NoProfile", "-Command", command], text=True, capture_output=True)
    for token in cp.stdout.split():
        if token.isdigit():
            return int(token)
    return None


def find_node():
    from shutil import which
    candidates = [os.environ.get("TF_NODE"), which("node")]
    if os.name == "nt":
        for root_name in ("PROGRAMFILES", "LOCALAPPDATA"):
            root = os.environ.get(root_name)
            if root:
                candidates.extend([str(Path(root) / "nodejs/node.exe"), str(Path(root) / "Programs/nodejs/node.exe")])
    else:
        candidates.extend(["/usr/bin/node", "/usr/local/bin/node"])
    for candidate in filter(None, candidates):
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def browser_control(operation, payload):
    node = find_node()
    helper = Path(__file__).resolve().with_name("browser_control.mjs")
    if not node:
        raise RuntimeError("node-not-found")
    if not helper.exists():
        raise RuntimeError(f"browser-control-helper-missing: {helper}")
    spec = browser_status()
    if not spec.get("cdp_ready"):
        raise RuntimeError("managed browser CDP is not ready")
    body = dict(payload or {})
    if operation not in {"targets", "open"} and not any(body.get(key) for key in ("target_id", "target_url", "url_contains", "title_contains")):
        if spec.get("url"):
            body["target_url"] = spec["url"]
    request = {"op": operation, "port": int(spec.get("debug_port") or 9222), "payload": body}
    timeout = max(5.0, float(body.get("timeout") or body.get("timeout_seconds") or 60.0))
    cp = subprocess.run([node, str(helper)], input=json.dumps(request), text=True, capture_output=True, timeout=timeout)
    parsed = None
    for stream in (cp.stdout, cp.stderr):
        for line in reversed([line.strip() for line in stream.splitlines() if line.strip()]):
            try:
                candidate = json.loads(line)
                if isinstance(candidate, dict):
                    parsed = candidate
                    break
            except Exception:
                continue
        if parsed is not None:
            break
    if cp.returncode != 0 or not isinstance(parsed, dict) or not parsed.get("ok"):
        detail = parsed.get("error") if isinstance(parsed, dict) else (cp.stderr.strip() or cp.stdout.strip())
        raise RuntimeError(f"browser-control {operation} failed: {detail}")
    return parsed.get("result")


def autogenic_recover(spec):
    node = find_node()
    helper = Path(__file__).resolve().with_name("browser_recover.mjs")
    if not node:
        return {"ok": False, "error": "node-not-found"}
    if not helper.exists():
        return {"ok": False, "error": "browser-recover-helper-missing", "path": str(helper)}
    resident_port = int(os.environ.get("TF_RESIDENT_PORT", DEFAULT_PORT))
    command = [
        node, str(helper),
        "--port", str(int(spec.get("debug_port") or 9222)),
        "--chat-url", str(spec.get("url") or "https://chatgpt.com/"),
        "--userscript-url", f"http://127.0.0.1:{resident_port}/userscripts/torsionfield-autogenic.user.js",
    ]
    try:
        cp = subprocess.run(command, text=True, capture_output=True, timeout=90)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
    parsed = None
    for line in reversed([line.strip() for line in cp.stdout.splitlines() if line.strip()]):
        try:
            candidate = json.loads(line)
            if isinstance(candidate, dict):
                parsed = candidate
                break
        except Exception:
            continue
    if parsed is None:
        for line in reversed([line.strip() for line in cp.stderr.splitlines() if line.strip()]):
            try:
                candidate = json.loads(line)
                if isinstance(candidate, dict):
                    parsed = candidate
                    break
            except Exception:
                continue
    result = {"ok": bool(cp.returncode == 0 and isinstance(parsed, dict) and parsed.get("ok")), "returncode": cp.returncode}
    if parsed is not None:
        result["helper"] = parsed
    elif cp.stderr.strip():
        result["error"] = cp.stderr.strip()[-2000:]
    return result


def browser_launch(payload):
    chrome = find_chrome(payload.get("chrome_path"))
    url = str(payload.get("url") or "https://chatgpt.com/")
    profile = str(payload.get("profile") or (STATE.state_dir / "chrome-profile"))
    Path(profile).mkdir(parents=True, exist_ok=True)
    port = int(payload.get("debug_port") or 9222)
    extra_args = [str(x) for x in payload.get("args") or []]
    ready_timeout = max(0.0, float(payload.get("ready_timeout") or 5.0))
    require_cdp = bool(payload.get("require_cdp", False))
    default_recovery = url.startswith("https://chatgpt.com/") or url.startswith("https://chat.openai.com/")
    recover_autogenic = bool(payload.get("recover_autogenic", default_recovery))
    require_recovery = bool(payload.get("require_recovery", recover_autogenic))
    args = [
        chrome,
        f"--user-data-dir={profile}",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        *extra_args,
        url,
    ]
    kwargs = {
        "cwd": payload.get("cwd") or None,
        "env": merged_env(payload.get("env")),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(args, **kwargs)
    launcher_pid = proc.pid
    runtime_pid = launcher_pid
    cdp = None
    deadline = time.time() + ready_timeout
    while time.time() <= deadline:
        cdp = debug_endpoint(port)
        if cdp:
            runtime_pid = windows_listener_pid(port) or runtime_pid
            break
        if os.name == "nt" and proc.poll() is not None:
            runtime_pid = windows_direct_child(launcher_pid, Path(chrome).name) or runtime_pid
        if ready_timeout <= 0:
            break
        time.sleep(0.1)
    if require_cdp and not cdp:
        raise RuntimeError(f"browser launched but CDP did not become ready on 127.0.0.1:{port}")
    spec = {
        "pid": runtime_pid,
        "launcher_pid": launcher_pid,
        "chrome_path": chrome,
        "profile": profile,
        "debug_port": port,
        "url": url,
        "extra_args": extra_args,
        "ready_timeout": ready_timeout,
        "require_cdp": require_cdp,
        "recover_autogenic": recover_autogenic,
        "require_recovery": require_recovery,
        "cdp_ready": bool(cdp),
        "browser_version": cdp.get("Browser") if cdp else None,
        "launched_at": time.time(),
    }
    STATE.save_browser(spec)
    if recover_autogenic:
        recovery = autogenic_recover(spec)
        spec["autogenic_recovery"] = recovery
        STATE.save_browser(spec)
        if require_recovery and not recovery.get("ok"):
            STATE.log("browser.recovery", ok=False, recovery=recovery)
            raise RuntimeError(f"browser launched but autogenic recovery failed: {recovery.get('error') or recovery.get('helper') or recovery}")
    STATE.log("browser.launch", **spec)
    return spec


def browser_status():
    spec = STATE.load_browser()
    pid = int(spec.get("pid") or 0)
    port = int(spec.get("debug_port") or 0)
    cdp = debug_endpoint(port) if port else None
    if cdp and os.name == "nt":
        listener_pid = windows_listener_pid(port)
        if listener_pid:
            pid = listener_pid
    elif pid and not process_alive(pid) and os.name == "nt":
        launcher_pid = int(spec.get("launcher_pid") or 0)
        chrome_path = spec.get("chrome_path") or spec.get("chrome") or "chrome.exe"
        if launcher_pid:
            pid = windows_direct_child(launcher_pid, Path(chrome_path).name) or pid
    alive = bool(cdp) or (pid > 0 and process_alive(pid))
    migrated = False
    if not spec.get("chrome_path") and spec.get("chrome"):
        spec["chrome_path"] = spec.get("chrome")
        migrated = True
    if "extra_args" not in spec and isinstance(spec.get("args"), list):
        spec["extra_args"] = legacy_extra_args(spec)
        migrated = True
    changed = migrated or pid != int(spec.get("pid") or 0) or bool(cdp) != bool(spec.get("cdp_ready"))
    spec.update({
        "pid": pid,
        "alive": alive,
        "cdp_ready": bool(cdp),
        "browser_version": cdp.get("Browser") if cdp else spec.get("browser_version"),
    })
    if changed:
        STATE.save_browser({k: v for k, v in spec.items() if k != "alive"})
    return spec


def legacy_extra_args(spec):
    current = spec.get("extra_args")
    if isinstance(current, list):
        return [str(x) for x in current]
    old = spec.get("args")
    if not isinstance(old, list):
        return []
    url = str(spec.get("url") or "")
    output = []
    for index, item in enumerate(old):
        value = str(item)
        if index == 0 or value == url:
            continue
        if value.startswith("--user-data-dir=") or value.startswith("--remote-debugging-address=") or value.startswith("--remote-debugging-port="):
            continue
        output.append(value)
    return output


def browser_restart(payload):
    previous = STATE.load_browser()
    status = browser_status()
    scope = str(payload.get("scope") or "managed")
    stopped = None
    pid = int(status.get("pid") or 0)
    if pid and status.get("alive"):
        stopped = kill_pid(pid, True, True)
        time.sleep(float(payload.get("settle_seconds") or 0.5))
    elif scope == "all":
        if os.name == "nt":
            stopped = []
            for image in ("chrome.exe", "chromium.exe", "msedge.exe"):
                cp = subprocess.run(["taskkill", "/IM", image, "/T", "/F"], text=True, capture_output=True)
                stopped.append({"image": image, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr})
        else:
            cp = subprocess.run(["pkill", "-KILL", "-f", "chrom(e|ium)"], text=True, capture_output=True)
            stopped = {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
    merged = {
        "chrome_path": previous.get("chrome_path") or previous.get("chrome"),
        "profile": previous.get("profile"),
        "debug_port": previous.get("debug_port"),
        "url": previous.get("url"),
        "args": legacy_extra_args(previous),
        "ready_timeout": previous.get("ready_timeout", 5),
        "require_cdp": previous.get("require_cdp", False),
        "recover_autogenic": previous.get("recover_autogenic", True),
        "require_recovery": previous.get("require_recovery", True),
    }
    merged.update({k: v for k, v in payload.items() if k not in {"scope", "settle_seconds"}})
    return {"stopped": stopped, "launched": browser_launch(merged)}


class Handler(BaseHTTPRequestHandler):
    server_version = f"TorsionfieldResident/{VERSION}"

    def log_message(self, fmt, *args):
        STATE.log("http", client=self.client_address[0], message=fmt % args)

    def _cors(self):
        origin = self.headers.get("Origin", "")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Torsionfield-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def _send(self, status, obj, content_type="application/json; charset=utf-8"):
        body = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        auth = self.headers.get("Authorization", "")
        token = self.headers.get("X-Torsionfield-Token", "")
        supplied = auth[7:] if auth.startswith("Bearer ") else token
        return bool(supplied) and secrets.compare_digest(supplied, STATE.token)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        obj = json.loads((self.rfile.read(n) if n else b"{}").decode())
        if not isinstance(obj, dict):
            raise ValueError("JSON object required")
        return obj

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/v1/health":
            return self._send(200, {"ok": True, "name": "torsionfield-resident", "version": VERSION, "pid": os.getpid(), "platform": platform.platform(), "elevated": is_elevated()})
        if path == "/v1/state":
            if not self._authorized():
                return self._send(401, {"ok": False, "error": "unauthorized"})
            return self._send(200, {"ok": True, "browser": STATE.load_browser(), "state_dir": str(STATE.state_dir)})
        if path == "/userscripts/torsionfield-autogenic.user.js":
            template = Path(__file__).resolve().parent.parent / "userscript" / "torsionfield-autogenic.user.js"
            if not template.exists():
                return self._send(404, {"ok": False, "error": "userscript template missing"})
            return self._send(200, template.read_bytes(), "application/javascript; charset=utf-8")
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self._authorized():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        try:
            payload = self._read_json()
            path = urlparse(self.path).path
            result = self._dispatch(path, payload)
            STATE.log("action", path=path, ok=True)
            return self._send(200, {"ok": True, "result": result})
        except subprocess.TimeoutExpired as exc:
            return self._send(504, {"ok": False, "error": "timeout", "detail": str(exc)})
        except Exception as exc:
            STATE.log("action", path=self.path, ok=False, error=repr(exc))
            return self._send(500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)})

    def _dispatch(self, path, payload):
        if path == "/v1/exec":
            argv = command_from_payload(payload)
            cp = subprocess.run(argv, cwd=payload.get("cwd") or None, env=merged_env(payload.get("env")), input=payload.get("stdin"), text=True, capture_output=True, timeout=float(payload.get("timeout") or 300))
            return {"argv": argv, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
        if path == "/v1/process/start":
            argv = command_from_payload(payload)
            kwargs = {"cwd": payload.get("cwd") or None, "env": merged_env(payload.get("env")), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen(argv, **kwargs)
            return {"pid": proc.pid, "argv": argv}
        if path == "/v1/process/kill":
            return kill_pid(payload["pid"], bool(payload.get("tree", True)), bool(payload.get("force", True)))
        if path == "/v1/process/list":
            cmd = ["tasklist", "/FO", "CSV"] if os.name == "nt" else ["ps", "-eo", "pid,ppid,user,args"]
            cp = subprocess.run(cmd, text=True, capture_output=True)
            return {"returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
        if path == "/v1/fs/read":
            p = Path(str(payload["path"])).expanduser()
            raw = p.read_bytes()
            return {"path": str(p), "base64": base64.b64encode(raw).decode(), "bytes": len(raw)} if payload.get("encoding") == "base64" else {"path": str(p), "text": raw.decode(payload.get("charset") or "utf-8"), "bytes": len(raw)}
        if path == "/v1/fs/write":
            p = Path(str(payload["path"])).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            raw = base64.b64decode(payload["base64"]) if "base64" in payload else str(payload.get("text", "")).encode(payload.get("charset") or "utf-8")
            with p.open("ab" if payload.get("append") else "wb") as fh:
                fh.write(raw)
            if payload.get("mode") is not None and os.name != "nt":
                os.chmod(p, int(str(payload["mode"]), 8) if isinstance(payload["mode"], str) else int(payload["mode"]))
            return {"path": str(p), "bytes": len(raw), "append": bool(payload.get("append"))}
        if path == "/v1/fs/delete":
            p = Path(str(payload["path"])).expanduser()
            if p.is_dir() and not p.is_symlink():
                import shutil
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
            return {"path": str(p), "deleted": True}
        if path == "/v1/browser/launch":
            return browser_launch(payload)
        if path == "/v1/browser/restart":
            return browser_restart(payload)
        if path == "/v1/browser/status":
            return browser_status()
        if path == "/v1/browser/targets":
            return browser_control("targets", payload)
        if path == "/v1/browser/open":
            return browser_control("open", payload)
        if path == "/v1/browser/close":
            return browser_control("close", payload)
        if path == "/v1/browser/activate":
            return browser_control("activate", payload)
        if path == "/v1/browser/navigate":
            return browser_control("navigate", payload)
        if path == "/v1/browser/reload":
            return browser_control("reload", payload)
        if path == "/v1/browser/evaluate":
            return browser_control("evaluate", payload)
        if path == "/v1/browser/screenshot":
            return browser_control("screenshot", payload)
        if path == "/v1/userscript/refresh":
            spec = browser_status()
            recovery = autogenic_recover(spec)
            state = STATE.load_browser()
            state["autogenic_recovery"] = recovery
            STATE.save_browser(state)
            if not recovery.get("ok"):
                raise RuntimeError(f"userscript refresh failed: {recovery}")
            return recovery
        raise ValueError(f"unknown operation: {path}")


def main():
    host = os.environ.get("TF_RESIDENT_HOST", DEFAULT_HOST)
    port = int(os.environ.get("TF_RESIDENT_PORT", DEFAULT_PORT))
    httpd = ThreadingHTTPServer((host, port), Handler)
    STATE.log("resident.start", pid=os.getpid(), host=host, port=port, version=VERSION)
    print(f"Torsionfield resident {VERSION} listening on http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        STATE.log("resident.stop", pid=os.getpid())
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
