#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import browser_roots as br

VERSION = "0.2.1"
HOST = "127.0.0.1"
PORT = 17374
HANDOFF_PROMPT = """TORSIONFIELD REBOOT HANDOFF REQUEST /1
The local machine is preparing for a controlled reboot. Do not start new machine operations.
Return a compact continuation capsule containing: current objective; what has actually completed; any machine/browser operation currently in flight; the exact next executable step; important paths/URLs/IDs; and any state that would not be obvious after this conversation is reopened. End with [[/TF_REBOOT_HANDOFF]]."""


def state_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Torsionfield"
    else:
        base = Path.home() / ".torsionfield"
    root = Path(os.environ.get("TF_REBOOT_STATE", str(base / "RebootSupervisor")))
    root.mkdir(parents=True, exist_ok=True)
    (root / "snapshots").mkdir(exist_ok=True)
    return root


ROOT = state_root()
PENDING = ROOT / "restore_pending.json"
PREFERENCES = ROOT / "preferences.json"
LOG = ROOT / "supervisor.jsonl"
BRIDGE_SOURCE = Path(__file__).parent / "extension_bridge"
CDP_HELPER = Path(__file__).parent / "reboot_cdp.mjs"


def log(event: str, **data) -> None:
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": time.time(), "event": event, **data}, ensure_ascii=False) + "\n")


def atomic_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def short_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()[:20]


def preferences() -> dict:
    return load_json(PREFERENCES, {"tabs": {}})


def set_preference(key: str, **changes) -> dict:
    prefs = preferences()
    record = prefs.setdefault("tabs", {}).setdefault(key, {})
    record.update(changes)
    atomic_json(PREFERENCES, prefs)
    return record


def tab_key(root_id: str, tab: dict) -> str:
    state = tab.get("state") or {}
    stable = state.get("conversationId") or tab.get("url") or tab.get("id")
    branch = state.get("branchSignature") or ""
    return short_hash(f"{root_id}|{stable}|{branch}")


def project_key(tab: dict) -> str:
    state = tab.get("state") or {}
    if state.get("projectId"):
        return "project:" + state["projectId"]
    if state.get("conversationId"):
        return "conversation:" + state["conversationId"]
    return "title:" + str(tab.get("title") or "untitled").strip().lower()[:100]


def decorate_tab(root: dict, tab: dict, prefs: dict) -> dict:
    record = dict(tab)
    record["rootId"] = root["rootId"]
    record["client"] = root["client"]
    record["coverage"] = root["coverage"]
    record["key"] = tab_key(root["rootId"], record)
    record["projectKey"] = project_key(record)
    preference = prefs.get(record["key"], {})
    record["priority"] = int(preference.get("priority", 50))
    record["paused"] = bool(preference.get("paused", False))
    state = record.get("state") or {}
    autogenic = state.get("autogenic") or {}
    record["needsHandoff"] = bool(
        state.get("streaming")
        or state.get("pendingAction")
        or autogenic.get("loopError")
        or autogenic.get("lastOpStatus") not in (None, "", "ok")
    )
    return record


def inventory(auto_bridge: bool = True) -> dict:
    prefs = preferences().get("tabs", {})
    roots = []
    tabs = []
    for root in br.discover_roots():
        record = br.root_inventory(root, BRIDGE_SOURCE, CDP_HELPER, auto_bridge=auto_bridge)
        record_tabs = [decorate_tab(record, tab, prefs) for tab in record.get("tabs", [])]
        record["tabs"] = record_tabs
        roots.append(record)
        tabs.extend(record_tabs)

    uncovered = [root for root in roots if root.get("discoveredChatGPT") and not root.get("covered")]
    unsafe_tabs = [
        tab
        for tab in tabs
        if (tab.get("state") or {}).get("streaming")
        or (tab.get("state") or {}).get("pendingAction")
    ]
    return {
        "schema": "TF_REBOOT_INVENTORY/2",
        "version": VERSION,
        "capturedAt": time.time(),
        "roots": roots,
        "tabs": tabs,
        "uncoveredRoots": [root["rootId"] for root in uncovered],
        "unsafeTabKeys": [tab["key"] for tab in unsafe_tabs],
        "safeForReboot": not uncovered and not unsafe_tabs,
    }


def snapshot(reason: str) -> dict:
    value = inventory(auto_bridge=True)
    value["id"] = time.strftime("%Y%m%d-%H%M%S")
    value["reason"] = reason
    path = ROOT / "snapshots" / f"{value['id']}.json"
    atomic_json(path, value)
    value["path"] = str(path)
    log(
        "snapshot",
        id=value["id"],
        tabs=len(value["tabs"]),
        uncovered=value["uncoveredRoots"],
        safe=value["safeForReboot"],
    )
    return value


def root_for_tab(inv: dict, tab: dict) -> dict:
    return next(root for root in inv["roots"] if root["rootId"] == tab["rootId"])


def tab_action(inv: dict, tab: dict, op: str, payload: dict | None = None, timeout_ms: int = 120_000):
    root = root_for_tab(inv, tab)
    if tab.get("coverage") == "extension":
        return br.bridge_rpc(
            root["client"],
            op,
            {"tabId": tab["id"], **(payload or {})},
            timeout_ms,
        )
    if tab.get("coverage") == "cdp":
        mapping = {
            "stop": "stop",
            "freeze": "freeze",
            "unfreeze": "unfreeze",
            "restore_draft": "restore_draft",
            "handoff": "handoff",
        }
        if op not in mapping:
            raise RuntimeError(f"CDP operation not implemented for reboot supervisor: {op}")
        cdp_payload = {"target_id": tab["id"], **(payload or {})}
        return br.node_call(
            CDP_HELPER,
            mapping[op],
            root["debugPort"],
            cdp_payload,
            timeout=max(30, timeout_ms / 1000 + 5),
        )
    raise RuntimeError("tab is not covered by an executable browser control path")


def request_handoffs(inv: dict) -> list[dict]:
    results = []
    for tab in inv.get("tabs", []):
        if not tab.get("needsHandoff"):
            continue
        try:
            if (tab.get("state") or {}).get("streaming"):
                tab_action(inv, tab, "stop", timeout_ms=30_000)
            response = tab_action(
                inv,
                tab,
                "handoff",
                {"prompt": HANDOFF_PROMPT},
                timeout_ms=140_000,
            )
            results.append(
                {
                    "key": tab["key"],
                    "url": tab.get("url"),
                    "ok": True,
                    "response": response.get("response") if isinstance(response, dict) else None,
                }
            )
        except Exception as exc:
            results.append({"key": tab["key"], "url": tab.get("url"), "ok": False, "error": repr(exc)})
    return results


def rehearse_restore(inv: dict) -> list[dict]:
    results = []
    for root in inv.get("roots", []):
        if root.get("coverage") != "extension" or not root.get("tabs"):
            continue
        try:
            result = br.bridge_rpc(
                root["client"],
                "rehearse_restore",
                {"snapshot": root.get("inventory") or {}},
                300_000,
            )
            results.append({"rootId": root["rootId"], "ok": bool(result.get("ok")), "result": result})
        except Exception as exc:
            results.append({"rootId": root["rootId"], "ok": False, "error": repr(exc)})
    return results


def prepare_reboot() -> dict:
    before = snapshot("prepare-before")
    if before["uncoveredRoots"]:
        blocked = {
            **before,
            "handoffs": [],
            "rehearsal": [],
            "safeForReboot": False,
            "prepareError": "uncovered-browser-roots",
        }
        atomic_json(PENDING, {"status": "blocked", "preparedAt": time.time(), "snapshot": blocked})
        return blocked

    handoffs = request_handoffs(before)
    after = snapshot("prepare-after-handoffs")
    rehearsal = rehearse_restore(after)
    failures = [item for item in handoffs if not item.get("ok")] + [
        item for item in rehearsal if not item.get("ok")
    ]
    safe = bool(after["safeForReboot"] and not failures)
    prepared = {
        **after,
        "handoffs": handoffs,
        "rehearsal": rehearsal,
        "safeForReboot": safe,
        "preparedAt": time.time(),
    }
    atomic_json(
        PENDING,
        {
            "status": "prepared" if safe else "blocked",
            "preparedAt": time.time(),
            "snapshot": prepared,
            "restoreAttempts": 0,
        },
    )
    log("prepare", safe=safe, handoffs=len(handoffs), rehearsals=len(rehearsal), failures=len(failures))
    return prepared


def schedule_reboot(delay_seconds: int = 20) -> dict:
    pending = load_json(PENDING, {})
    snap = pending.get("snapshot") or {}
    if pending.get("status") != "prepared" or not snap.get("safeForReboot"):
        raise RuntimeError("no-safe-prepared-manifest")
    if time.time() - float(pending.get("preparedAt") or 0) > 900:
        raise RuntimeError("prepared-manifest-stale")
    pending["status"] = "rebooting"
    pending["scheduledAt"] = time.time()
    atomic_json(PENDING, pending)
    if os.name != "nt":
        raise RuntimeError("physical reboot acceptance is Windows-only in v0.2")
    subprocess.Popen(
        [
            "shutdown",
            "/r",
            "/t",
            str(int(delay_seconds)),
            "/d",
            "p:0:0",
            "/c",
            "Torsionfield controlled reboot",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log("reboot.scheduled", delay=delay_seconds, snapshot=snap.get("id"))
    return {"scheduled": True, "delaySeconds": delay_seconds, "snapshotId": snap.get("id")}


def ensure_bridge_server() -> bool:
    try:
        with urllib.request.urlopen(br.bridge_base() + "/api/health", timeout=1):
            return True
    except Exception:
        pass
    script = Path(__file__).with_name("browser_bridge.py")
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(
            [sys.executable, str(script), "--port", str(br.BRIDGE_PORT)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    else:
        subprocess.Popen(
            [sys.executable, str(script), "--port", str(br.BRIDGE_PORT)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(br.bridge_base() + "/api/health", timeout=0.5):
                return True
        except Exception:
            time.sleep(0.1)
    return False


def launch_saved_root(saved_root: dict) -> None:
    executable = saved_root.get("executable")
    argv = list(saved_root.get("argv") or [])
    if not executable or not Path(executable).exists():
        raise RuntimeError("saved-browser-executable-missing")
    args = [executable]
    for arg in argv[1:]:
        if str(arg).startswith(("http://", "https://", "chrome-extension://")):
            continue
        if str(arg).startswith("--type="):
            continue
        args.append(str(arg))
    if "--restore-last-session" not in args:
        args.append("--restore-last-session")
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restore_pending() -> dict:
    pending = load_json(PENDING, {})
    if pending.get("status") not in ("rebooting", "restoring"):
        return {"skipped": True, "status": pending.get("status")}

    pending["status"] = "restoring"
    pending["restoreAttempts"] = int(pending.get("restoreAttempts", 0)) + 1
    atomic_json(PENDING, pending)
    snapshot_value = pending["snapshot"]
    results = []

    for saved_root in snapshot_value.get("roots", []):
        if not saved_root.get("discoveredChatGPT"):
            continue
        current = next(
            (root for root in br.discover_roots() if root["rootId"] == saved_root["rootId"]),
            None,
        )
        if current is None:
            try:
                launch_saved_root(saved_root)
                time.sleep(2)
                current = next(
                    (root for root in br.discover_roots() if root["rootId"] == saved_root["rootId"]),
                    None,
                )
            except Exception as exc:
                results.append({"rootId": saved_root["rootId"], "ok": False, "error": repr(exc)})
                continue
        if current is None:
            results.append({"rootId": saved_root["rootId"], "ok": False, "error": "browser-root-not-restored"})
            continue

        bridge = br.ensure_bridge(current, BRIDGE_SOURCE, timeout=25)
        if not bridge.get("ok"):
            results.append(
                {"rootId": current["rootId"], "ok": False, "error": "bridge-not-restored", "bridge": bridge}
            )
            continue
        try:
            result = br.bridge_rpc(
                current["client"],
                "restore_manifest",
                {"snapshot": saved_root.get("inventory") or {}},
                300_000,
            )
            results.append({"rootId": current["rootId"], "ok": bool(result.get("ok")), "result": result})
        except Exception as exc:
            results.append({"rootId": current["rootId"], "ok": False, "error": repr(exc)})

    final = snapshot("post-reboot-restore")
    ok = all(item.get("ok") for item in results) and not final["uncoveredRoots"] and not final["unsafeTabKeys"]
    pending["status"] = "restored" if ok else "restore-failed"
    pending["restoredAt"] = time.time()
    pending["results"] = results
    pending["finalSnapshot"] = final
    atomic_json(PENDING, pending)
    log("restore", ok=ok, results=len(results))
    return {"ok": ok, "results": results, "final": final}


def install_task() -> dict:
    if os.name != "nt":
        return {"installed": False, "reason": "Windows-only"}
    task = "Torsionfield Reboot Supervisor"
    command = f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --serve'
    completed = subprocess.run(
        ["schtasks", "/Create", "/TN", task, "/TR", command, "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return {"installed": True, "task": task, "command": command}


UI = r'''<!doctype html><meta charset="utf-8"><title>TF Reboot Supervisor</title>
<style>body{font:13px system-ui;background:#111;color:#eee;margin:0}header{position:sticky;top:0;background:#181818;padding:12px;border-bottom:1px solid #444;z-index:4}main{padding:12px}.root{border:1px solid #444;margin:10px 0}.rh{padding:8px;background:#222}.tab{padding:8px;border-top:1px solid #333;display:grid;grid-template-columns:55px 85px 1fr;gap:8px}.ok{color:#8aff9e}.bad{color:#ff9696}.draft{color:#ffd67a}button{margin:2px;padding:6px 9px}select{background:#222;color:#eee}</style>
<header><b>TF REBOOT SUPERVISOR</b> <span id="summary"></span><br><button onclick="refreshState()">Refresh</button><button onclick="makeSnapshot()">Snapshot</button><button onclick="prepareReboot()">Prepare + rehearse</button><button onclick="doReboot()">REBOOT IF SAFE</button></header><main id="main">Loading…</main>
<script>let state=null;const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:{'content-type':'application/json'},body:body?JSON.stringify(body):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}async function refreshState(){state=await api('/api/inventory');render()}async function makeSnapshot(){state=await api('/api/snapshot',{});render()}async function prepareReboot(){state=await api('/api/prepare',{});render();alert('safeForReboot='+state.safeForReboot)}async function doReboot(){if(!confirm('Execute the strictly prepared controlled reboot?'))return;alert(JSON.stringify(await api('/api/reboot',{delay:20})))}async function priority(key,value){await api('/api/priority',{key,priority:+value});await refreshState()}function render(){document.getElementById('summary').innerHTML=`— ${state.tabs.length} ChatGPT tabs — <b class="${state.safeForReboot?'ok':'bad'}">${state.safeForReboot?'QUIESCENT':'BLOCKED'}</b>`;let html='';for(const root of state.roots){html+=`<section class="root"><div class="rh"><b>${esc(root.rootId)}</b> · ${esc(root.coverage)} · <span class="${root.covered?'ok':'bad'}">${root.covered?'covered':'UNCOVERED'}</span><br>${esc(root.executable)} · ${esc(root.profilePath)}</div>`;for(const tab of root.tabs||[]){const s=tab.state||{};html+=`<div class="tab"><select onchange="priority('${tab.key}',this.value)">${[100,75,50,25,10,0].map(x=>`<option ${x==tab.priority?'selected':''}>${x}</option>`).join('')}</select><span class="${s.streaming||s.pendingAction?'bad':'ok'}">${esc(s.status||'unknown')}</span><div><b>${esc(tab.title)}</b><br>${esc(tab.url)}${s.composerText?`<div class="draft">DRAFT: ${esc(s.composerText.slice(0,400))}</div>`:''}${tab.needsHandoff?'<div class="bad">HANDOFF REQUIRED</div>':''}</div></div>`}html+='</section>'}document.getElementById('main').innerHTML=html||'No browser roots.'}refreshState()</script>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

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

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = UI.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/health":
            return self.send_json(200, {"ok": True, "version": VERSION, "root": str(ROOT)})
        if path == "/api/inventory":
            return self.send_json(200, inventory(auto_bridge=True))
        if path == "/api/pending":
            return self.send_json(200, load_json(PENDING, {}))
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_body()
            if path == "/api/snapshot":
                return self.send_json(200, snapshot("ui"))
            if path == "/api/prepare":
                return self.send_json(200, prepare_reboot())
            if path == "/api/reboot":
                return self.send_json(200, schedule_reboot(int(body.get("delay", 20))))
            if path == "/api/restore":
                return self.send_json(200, restore_pending())
            if path == "/api/priority":
                return self.send_json(
                    200,
                    {"ok": True, "preference": set_preference(str(body["key"]), priority=int(body.get("priority", 50)))},
                )
            return self.send_json(404, {"error": "not found"})
        except Exception as exc:
            log("api.error", path=path, error=repr(exc))
            return self.send_json(500, {"error": f"{type(exc).__name__}: {exc}"})


def serve() -> None:
    ensure_bridge_server()
    log("serve.start", pid=os.getpid(), version=VERSION)

    def recovery():
        time.sleep(8)
        try:
            restore_pending()
        except Exception as exc:
            log("boot.restore.error", error=repr(exc))

    threading.Thread(target=recovery, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever(poll_interval=0.25)


def self_test() -> dict:
    assert br.CHAT_URL_RE.search(b"https://chatgpt.com/c/6a7ef8a3-aa70-83ec-9105-0ace064c98e8")
    assert not br.CHAT_URL_RE.search(b"https://example.com/c/6a7ef8a3-aa70-83ec-9105-0ace064c98e8")
    sample = {"state": {"conversationId": "abc", "branchSignature": "abc:u:a"}, "url": "https://chatgpt.com/c/abc"}
    assert tab_key("root", sample) == tab_key("root", sample)
    return {"PASS": True, "version": VERSION, "root": str(ROOT)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--reboot-if-safe", action="store_true")
    parser.add_argument("--restore-pending", action="store_true")
    parser.add_argument("--install-task", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    ensure_bridge_server()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return 0
    if args.inventory:
        print(json.dumps(inventory(auto_bridge=True), indent=2))
        return 0
    if args.snapshot:
        print(json.dumps(snapshot("cli"), indent=2))
        return 0
    if args.prepare:
        print(json.dumps(prepare_reboot(), indent=2))
        return 0
    if args.reboot_if_safe:
        print(json.dumps(schedule_reboot(), indent=2))
        return 0
    if args.restore_pending:
        print(json.dumps(restore_pending(), indent=2))
        return 0
    if args.install_task:
        print(json.dumps(install_task(), indent=2))
        return 0
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
