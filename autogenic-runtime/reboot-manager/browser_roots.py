#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 17375
CHAT_URL_RE = re.compile(
    rb"https://(?:chatgpt\.com|chat\.openai\.com)/(?:c/[0-9A-Za-z-]{20,}|g/[0-9A-Za-z_.-]+(?:/c/[0-9A-Za-z-]{20,})?)",
    re.I,
)


def short_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def split_cmdline(command_line: str) -> list[str]:
    if os.name != "nt":
        return str(command_line).split()
    argc = ctypes.c_int()
    fn = ctypes.windll.shell32.CommandLineToArgvW
    fn.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    fn.restype = ctypes.POINTER(wintypes.LPWSTR)
    ptr = fn(str(command_line), ctypes.byref(argc))
    if not ptr:
        return []
    try:
        return [ptr[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(ptr)


def arg_value(argv: list[str], name: str) -> str:
    prefix = name + "="
    for index, arg in enumerate(argv):
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
        if arg == name and index + 1 < len(argv):
            return argv[index + 1]
    return ""


def browser_processes() -> list[dict]:
    if os.name != "nt":
        return []
    script = r'''$x=Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('chrome.exe','chromium.exe','msedge.exe') -and $_.CommandLine -and $_.CommandLine -notmatch '--type=' } | Select-Object ProcessId,Name,ExecutablePath,CommandLine; $x | ConvertTo-Json -Compress'''
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        timeout=20,
    )
    if completed.returncode or not completed.stdout.strip():
        return []
    raw = json.loads(completed.stdout)
    if isinstance(raw, dict):
        raw = [raw]
    return [
        {
            "pid": int(item.get("ProcessId") or 0),
            "name": item.get("Name") or "",
            "executable": item.get("ExecutablePath") or "",
            "commandLine": item.get("CommandLine") or "",
        }
        for item in raw
    ]


def default_user_data(executable: str) -> Path | None:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    lower = str(executable).lower()
    if "chrome sxs" in lower:
        return local / "Google" / "Chrome SxS" / "User Data"
    if "\\google\\chrome\\" in lower:
        return local / "Google" / "Chrome" / "User Data"
    if "msedge" in lower:
        return local / "Microsoft" / "Edge" / "User Data"
    return None


def profile_path(user_data: str, profile_directory: str) -> Path:
    root = Path(user_data)
    if profile_directory:
        return root / profile_directory
    if (root / "Default" / "Preferences").exists() or (root / "Default" / "Secure Preferences").exists():
        return root / "Default"
    return root


def parse_root(row: dict) -> dict:
    argv = split_cmdline(row.get("commandLine") or "")
    executable = row.get("executable") or (argv[0] if argv else "")
    explicit_user_data = arg_value(argv, "--user-data-dir")
    user_data = explicit_user_data
    if not user_data:
        default = default_user_data(executable)
        user_data = str(default) if default else ""
    profile_directory = arg_value(argv, "--profile-directory")
    debug_text = arg_value(argv, "--remote-debugging-port")
    try:
        debug_port = int(debug_text) if debug_text else None
    except ValueError:
        debug_port = None
    profile = profile_path(user_data, profile_directory) if user_data else None
    root_id = "browser-" + short_hash(
        f"{str(executable).lower()}|{str(user_data).lower()}|{profile_directory.lower()}"
    )
    return {
        **row,
        "argv": argv,
        "userDataDir": user_data,
        "explicitUserDataDir": bool(explicit_user_data),
        "profileDirectory": profile_directory,
        "profilePath": str(profile) if profile else "",
        "debugPort": debug_port,
        "rootId": root_id,
        "client": root_id,
    }


def discover_roots() -> list[dict]:
    merged: dict[str, dict] = {}
    for row in browser_processes():
        root = parse_root(row)
        key = root["rootId"]
        if key not in merged:
            merged[key] = {**root, "pids": [root["pid"]]}
        else:
            merged[key]["pids"].append(root["pid"])
    return list(merged.values())


def scan_session_urls(profile: str, max_files: int = 20, max_bytes: int = 16_000_000) -> list[dict]:
    root = Path(profile)
    if not root.exists():
        return []
    files: list[Path] = []
    for pattern in ("Sessions/*", "Current Tabs", "Last Tabs", "Current Session", "Last Session"):
        files.extend(path for path in root.glob(pattern) if path.is_file())
    files = sorted(set(files), key=lambda path: path.stat().st_mtime, reverse=True)[:max_files]
    found: dict[str, dict] = {}
    for file in files:
        try:
            data = file.read_bytes()[-max_bytes:]
        except Exception:
            continue
        for match in CHAT_URL_RE.finditer(data):
            url = match.group(0).decode("ascii", "ignore")
            found[url] = {"url": url, "sessionFile": str(file), "mtime": file.stat().st_mtime}
    return list(found.values())


def extension_record(root: dict) -> dict | None:
    secure = Path(root.get("profilePath") or "") / "Secure Preferences"
    if not secure.exists():
        return None
    try:
        settings = json.loads(secure.read_text(encoding="utf-8")).get("extensions", {}).get("settings", {})
    except Exception:
        return None
    candidates: list[tuple[int, dict]] = []
    for extension_id, value in settings.items():
        manifest = value.get("manifest") or {}
        path = str(value.get("path") or "")
        name = str(manifest.get("name") or "")
        active = value.get("active_permissions") or {}
        permissions = active.get("api") or []
        hosts = active.get("scriptable_host") or []
        score = (
            (4 if "torsionfield" in name.lower() else 0)
            + (3 if "torsionfield" in path.lower() else 0)
            + (2 if "tabs" in permissions else 0)
            + (2 if "scripting" in permissions else 0)
            + (1 if any("chatgpt.com" in host for host in hosts) else 0)
        )
        if score >= 6:
            candidates.append(
                (
                    score,
                    {
                        "id": extension_id,
                        "path": path,
                        "name": name,
                        "version": manifest.get("version"),
                        "permissions": permissions,
                        "hosts": hosts,
                    },
                )
            )
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def bridge_base() -> str:
    return f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"


def http_json(path: str, method: str = "GET", body: dict | None = None, timeout: float = 10) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"content-type": "application/json"} if data else {}
    request = urllib.request.Request(bridge_base() + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def bridge_clients() -> dict:
    try:
        return http_json("/api/clients", timeout=3).get("clients", {})
    except Exception:
        return {}


def bridge_healthy(client: str) -> bool:
    info = bridge_clients().get(client)
    return bool(info and float(info.get("ageSeconds", 999)) < 35 and not info.get("error"))


def bridge_rpc(client: str, op: str, payload: dict | None = None, timeout_ms: int = 120_000):
    value = http_json(
        "/api/rpc",
        "POST",
        {
            "client": client,
            "message": {"op": op, "payload": payload or {}},
            "timeoutMs": timeout_ms,
        },
        timeout=timeout_ms / 1000 + 10,
    )
    if not value.get("ok"):
        raise RuntimeError(value.get("error") or "bridge-rpc-failed")
    return value.get("value")


def ensure_bridge_files(extension: dict, source_dir: str | Path) -> bool:
    if not extension or not extension.get("path"):
        return False
    source = Path(source_dir)
    destination = Path(extension["path"])
    if not source.exists() or not destination.exists():
        return False
    for name in ("reboot_bridge.html", "reboot_bridge.js"):
        shutil.copy2(source / name, destination / name)
    return True


def open_bridge(root: dict, extension: dict | None, source_dir: str | Path) -> dict:
    if not extension:
        return {"ok": False, "reason": "torsionfield-extension-not-installed"}
    if not ensure_bridge_files(extension, source_dir):
        return {"ok": False, "reason": "bridge-files-not-installed"}
    query = urllib.parse.urlencode({"client": root["client"], "server": bridge_base()})
    url = f"chrome-extension://{extension['id']}/reboot_bridge.html?{query}"
    args = [root["executable"]]
    if root.get("explicitUserDataDir"):
        args.append(f"--user-data-dir={root['userDataDir']}")
    if root.get("profileDirectory"):
        args.append(f"--profile-directory={root['profileDirectory']}")
    args.append(url)
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "url": url, "extension": extension}


def ensure_bridge(root: dict, source_dir: str | Path, timeout: float = 12) -> dict:
    if bridge_healthy(root["client"]):
        return {"ok": True, "already": True}
    extension = extension_record(root)
    opened = open_bridge(root, extension, source_dir)
    if not opened.get("ok"):
        return opened
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bridge_healthy(root["client"]):
            return {"ok": True, "opened": True, "extension": extension, "url": opened["url"]}
        time.sleep(0.25)
    return {
        "ok": False,
        "reason": "bridge-page-did-not-register",
        "extension": extension,
        "url": opened.get("url"),
    }


def cdp_alive(port: int | None) -> bool:
    if not port:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/json/version", timeout=0.8):
            return True
    except Exception:
        return False


def node_call(helper: str | Path, op: str, port: int, payload: dict | None = None, timeout: float = 60):
    node = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
    completed = subprocess.run(
        [node, str(helper)],
        input=json.dumps({"op": op, "port": port, "payload": payload or {}}),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    for line in reversed([line.strip() for line in completed.stdout.splitlines() if line.strip()]):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("ok"):
            return value.get("result")
        if value.get("error"):
            raise RuntimeError(value["error"])
    raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "CDP-helper-failed")


def root_inventory(
    root: dict,
    bridge_source: str | Path,
    cdp_helper: str | Path,
    auto_bridge: bool = True,
) -> dict:
    evidence = scan_session_urls(root.get("profilePath") or "")
    extension = extension_record(root)
    coverage = "none"
    inventory = None
    errors: list[str] = []
    bridge = None

    if auto_bridge and evidence and not bridge_healthy(root["client"]):
        try:
            bridge = ensure_bridge(root, bridge_source)
        except Exception as exc:
            bridge = {"ok": False, "reason": repr(exc)}

    if bridge_healthy(root["client"]):
        try:
            inventory = bridge_rpc(root["client"], "inventory", {}, 90_000)
            coverage = "extension"
        except Exception as exc:
            errors.append("bridge:" + repr(exc))

    if inventory is None and cdp_alive(root.get("debugPort")):
        try:
            inventory = node_call(cdp_helper, "inventory", root["debugPort"], {}, 60)
            coverage = "cdp"
        except Exception as exc:
            errors.append("cdp:" + repr(exc))

    tabs: list[dict] = []
    if inventory:
        source_tabs = inventory.get("tabs") if coverage == "extension" else inventory.get("pages")
        for tab in source_tabs or []:
            if tab.get("chatgpt"):
                tabs.append(tab)

    discovered = bool(evidence or tabs)
    covered = bool(
        (not discovered)
        or (inventory is not None and coverage in ("extension", "cdp") and not errors)
    )
    return {
        **root,
        "extension": extension,
        "sessionEvidence": evidence,
        "discoveredChatGPT": discovered,
        "coverage": coverage,
        "covered": covered,
        "bridgeEnsure": bridge,
        "errors": errors,
        "inventory": inventory,
        "tabs": tabs,
    }
