#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import reboot_supervisor as core

VERSION = "0.3.0"
HOST = core.HOST
PORT = core.PORT


def find_tab(inv: dict, key: str) -> dict:
    for tab in inv.get("tabs", []):
        if tab.get("key") == key:
            return tab
    raise KeyError(f"tab-not-found:{key}")


def tab_operation(key: str, op: str) -> dict:
    inv = core.inventory(auto_bridge=True)
    tab = find_tab(inv, key)
    if op not in {"freeze", "unfreeze", "stop"}:
        raise ValueError(f"unsupported-tab-operation:{op}")
    result = core.tab_action(inv, tab, op, timeout_ms=30_000)
    if op == "freeze":
        core.set_preference(key, paused=True)
    elif op == "unfreeze":
        core.set_preference(key, paused=False)
    return {"ok": True, "key": key, "op": op, "result": result}


def project_operation(project_key: str, op: str) -> dict:
    inv = core.inventory(auto_bridge=True)
    selected = [tab for tab in inv.get("tabs", []) if tab.get("projectKey") == project_key]
    results = []
    for tab in selected:
        try:
            result = core.tab_action(inv, tab, op, timeout_ms=30_000)
            if op == "freeze":
                core.set_preference(tab["key"], paused=True)
            elif op == "unfreeze":
                core.set_preference(tab["key"], paused=False)
            results.append({"key": tab["key"], "ok": True, "result": result})
        except Exception as exc:
            results.append({"key": tab["key"], "ok": False, "error": repr(exc)})
    return {"ok": all(item["ok"] for item in results), "projectKey": project_key, "op": op, "results": results}


def compact_turn(turn: dict | None) -> dict | None:
    if not turn:
        return None
    text = str(turn.get("text") or "")
    return {
        "role": turn.get("role"),
        "hash": turn.get("hash"),
        "text": text[:5000],
        "truncated": len(text) > 5000,
    }


def state_report(inv: dict, selected_keys: list[str] | None = None) -> str:
    selected = set(selected_keys or [])
    tabs = [tab for tab in inv.get("tabs", []) if not selected or tab.get("key") in selected]
    roots = []
    for root in inv.get("roots", []):
        root_tabs = [tab for tab in tabs if tab.get("rootId") == root.get("rootId")]
        if not root_tabs:
            continue
        roots.append(
            {
                "rootId": root.get("rootId"),
                "coverage": root.get("coverage"),
                "profilePath": root.get("profilePath"),
                "browser": root.get("executable"),
                "tabs": [tab.get("key") for tab in root_tabs],
            }
        )

    reports = []
    for tab in tabs:
        state = tab.get("state") or {}
        reports.append(
            {
                "key": tab.get("key"),
                "projectKey": tab.get("projectKey"),
                "rootId": tab.get("rootId"),
                "coverage": tab.get("coverage"),
                "priority": tab.get("priority"),
                "paused": tab.get("paused"),
                "title": tab.get("title"),
                "url": tab.get("url"),
                "windowId": tab.get("windowId"),
                "index": tab.get("index"),
                "active": tab.get("active"),
                "pinned": tab.get("pinned"),
                "conversationId": state.get("conversationId"),
                "projectId": state.get("projectId"),
                "status": state.get("status"),
                "streaming": state.get("streaming"),
                "pendingAction": state.get("pendingAction"),
                "turnCount": state.get("turnCount"),
                "branchSignature": state.get("branchSignature"),
                "branchButtons": state.get("branchButtons"),
                "draft": state.get("composerText") or "",
                "scrollY": state.get("scrollY"),
                "latestUser": compact_turn(state.get("latestUser")),
                "latestAssistant": compact_turn(state.get("latestAssistant")),
                "autogenic": state.get("autogenic"),
                "needsHandoff": tab.get("needsHandoff"),
            }
        )

    payload = {
        "schema": "TORSIONFIELD_REBOOT_STATE/2",
        "capturedAt": inv.get("capturedAt"),
        "safeForReboot": inv.get("safeForReboot"),
        "uncoveredRoots": inv.get("uncoveredRoots"),
        "unsafeTabKeys": inv.get("unsafeTabKeys"),
        "roots": roots,
        "tabs": reports,
    }
    return "TORSIONFIELD REBOOT STATE /2\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n[[/TORSIONFIELD_REBOOT_STATE]]"


def report_to_chat(target_key: str, selected_keys: list[str] | None = None) -> dict:
    inv = core.inventory(auto_bridge=True)
    target = find_tab(inv, target_key)
    if target.get("coverage") != "extension":
        raise RuntimeError("state-report-target-requires-browser-native-extension-coverage")
    state = target.get("state") or {}
    if state.get("streaming"):
        raise RuntimeError("state-report-target-is-streaming")
    if str(state.get("composerText") or "").strip():
        raise RuntimeError("state-report-target-has-draft")
    report = state_report(inv, selected_keys)
    root = core.root_for_tab(inv, target)
    result = core.br.bridge_rpc(
        root["client"],
        "submit",
        {"tabId": target["id"], "text": report, "timeoutMs": 120_000},
        140_000,
    )
    return {
        "ok": True,
        "targetKey": target_key,
        "reportedKeys": selected_keys or [tab["key"] for tab in inv.get("tabs", [])],
        "characters": len(report),
        "result": result,
    }


def set_project_priority(project_key: str, priority: int) -> dict:
    inv = core.inventory(auto_bridge=True)
    selected = [tab for tab in inv.get("tabs", []) if tab.get("projectKey") == project_key]
    for tab in selected:
        core.set_preference(tab["key"], priority=int(priority))
    return {"ok": True, "projectKey": project_key, "priority": int(priority), "keys": [tab["key"] for tab in selected]}


UI = r'''<!doctype html><meta charset="utf-8"><title>TF Reboot Console</title>
<style>
body{font:13px system-ui;background:#101010;color:#eee;margin:0}header{position:sticky;top:0;background:#171717;padding:12px;border-bottom:1px solid #444;z-index:5}main{padding:12px}.root{border:1px solid #444;margin:12px 0}.root-head{padding:9px;background:#222}.project{margin:9px;border:1px solid #353535}.project-head{padding:7px;background:#1b1b1b}.tab{display:grid;grid-template-columns:28px 62px 92px 1fr auto;gap:7px;padding:8px;border-top:1px solid #2b2b2b;align-items:start}.ok{color:#82ff9c}.bad{color:#ff9696}.draft{color:#ffd67a}.muted{color:#aaa}button,select{background:#292929;color:#eee;border:1px solid #555;padding:5px 7px;margin:2px}a{color:#9cc9ff}pre{white-space:pre-wrap;max-height:280px;overflow:auto}.toolbar{display:inline-flex;gap:2px;flex-wrap:wrap}
</style>
<header><b>TF REBOOT CONSOLE</b> <span id="summary"></span><br><span class="toolbar"><button onclick="refreshState()">Refresh</button><button onclick="makeSnapshot()">Snapshot</button><button onclick="prepareReboot()">Prepare + rehearse</button><button onclick="sendReport()">Send selected state → selected ChatGPT</button><button onclick="doReboot()">REBOOT IF SAFE</button></span></header><main id="main">Loading…</main>
<script>
let state=null;const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));async function api(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:{'content-type':'application/json'},body:body?JSON.stringify(body):undefined});const value=await response.json();if(!response.ok)throw Error(value.error||response.status);return value}function chosen(){return[...document.querySelectorAll('.pick:checked')].map(x=>x.value)}function reportTarget(){return document.querySelector('input[name=report-target]:checked')?.value||''}async function refreshState(){state=await api('/api/inventory');render()}async function makeSnapshot(){state=await api('/api/snapshot',{});render()}async function prepareReboot(){state=await api('/api/prepare',{});render();alert('safeForReboot='+state.safeForReboot)}async function doReboot(){if(!confirm('Execute the strictly prepared controlled reboot?'))return;alert(JSON.stringify(await api('/api/reboot',{delay:20})))}async function tabOp(key,op){await api('/api/tab-op',{key,op});await refreshState()}async function projectOp(projectKey,op){await api('/api/project-op',{projectKey,op});await refreshState()}async function priority(key,value){await api('/api/priority',{key,priority:+value});await refreshState()}async function projectPriority(projectKey,value){await api('/api/project-priority',{projectKey,priority:+value});await refreshState()}async function sendReport(){const target=reportTarget();if(!target){alert('Select a report target with the circle control.');return}const selected=chosen();const result=await api('/api/report',{targetKey:target,selectedKeys:selected});alert('State report returned to ChatGPT: '+result.characters+' characters')}function render(){document.getElementById('summary').innerHTML=`— ${state.tabs.length} ChatGPT tabs — <b class="${state.safeForReboot?'ok':'bad'}">${state.safeForReboot?'QUIESCENT':'BLOCKED'}</b>`;let html='';for(const root of state.roots){html+=`<section class="root"><div class="root-head"><b>${esc(root.rootId)}</b> · ${esc(root.coverage)} · <span class="${root.covered?'ok':'bad'}">${root.covered?'covered':'UNCOVERED'}</span><br><span class="muted">${esc(root.executable)} · ${esc(root.profilePath)}</span></div>`;const groups={};for(const tab of root.tabs||[])(groups[tab.projectKey]??=[]).push(tab);for(const [projectKey,tabs] of Object.entries(groups)){html+=`<section class="project"><div class="project-head"><b>${esc(projectKey)}</b> · ${tabs.length} tab(s) <button onclick='projectOp(${JSON.stringify(projectKey)},"freeze")'>Pause project</button><button onclick='projectOp(${JSON.stringify(projectKey)},"unfreeze")'>Resume project</button><select onchange='projectPriority(${JSON.stringify(projectKey)},this.value)'><option value="">priority…</option>${[100,75,50,25,10,0].map(x=>`<option>${x}</option>`).join('')}</select></div>`;for(const tab of tabs.sort((a,b)=>b.priority-a.priority)){const s=tab.state||{};html+=`<div class="tab"><input class="pick" type="checkbox" value="${esc(tab.key)}"><select onchange='priority(${JSON.stringify(tab.key)},this.value)'>${[100,75,50,25,10,0].map(x=>`<option ${x==tab.priority?'selected':''}>${x}</option>`).join('')}</select><span class="${s.streaming||s.pendingAction?'bad':'ok'}">${esc(s.status||tab.coverage)}</span><div><b>${esc(tab.title)}</b><br><a href="${esc(tab.url)}" target="_blank">${esc(tab.url)}</a>${s.composerText?`<div class="draft">DRAFT: ${esc(s.composerText.slice(0,500))}</div>`:''}${tab.needsHandoff?'<div class="bad">HANDOFF REQUIRED</div>':''}<details><summary>branch / latest state</summary><pre>${esc(JSON.stringify({branchSignature:s.branchSignature,branchButtons:s.branchButtons,latestUser:s.latestUser,latestAssistant:s.latestAssistant,autogenic:s.autogenic},null,2))}</pre></details></div><div><input type="radio" name="report-target" value="${esc(tab.key)}" title="Return state report into this ChatGPT tab"><button onclick='tabOp(${JSON.stringify(tab.key)},"freeze")'>Pause</button><button onclick='tabOp(${JSON.stringify(tab.key)},"unfreeze")'>Resume</button>${s.streaming?`<button onclick='tabOp(${JSON.stringify(tab.key)},"stop")'>Stop</button>`:''}</div></div>`}html+='</section>'}html+='</section>'}document.getElementById('main').innerHTML=html||'No browser roots.'}refreshState()
</script>'''


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
            return self.send_json(200, {"ok": True, "version": VERSION, "root": str(core.ROOT)})
        if path == "/api/inventory":
            return self.send_json(200, core.inventory(auto_bridge=True))
        if path == "/api/pending":
            return self.send_json(200, core.load_json(core.PENDING, {}))
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_body()
            if path == "/api/snapshot":
                return self.send_json(200, core.snapshot("console"))
            if path == "/api/prepare":
                return self.send_json(200, core.prepare_reboot())
            if path == "/api/reboot":
                return self.send_json(200, core.schedule_reboot(int(body.get("delay", 20))))
            if path == "/api/restore":
                return self.send_json(200, core.restore_pending())
            if path == "/api/priority":
                return self.send_json(200, {"ok": True, "preference": core.set_preference(str(body["key"]), priority=int(body.get("priority", 50)))})
            if path == "/api/project-priority":
                return self.send_json(200, set_project_priority(str(body["projectKey"]), int(body.get("priority", 50))))
            if path == "/api/tab-op":
                return self.send_json(200, tab_operation(str(body["key"]), str(body["op"])))
            if path == "/api/project-op":
                return self.send_json(200, project_operation(str(body["projectKey"]), str(body["op"])))
            if path == "/api/report":
                return self.send_json(200, report_to_chat(str(body["targetKey"]), list(body.get("selectedKeys") or [])))
            return self.send_json(404, {"error": "not found"})
        except Exception as exc:
            core.log("console.api.error", path=path, error=repr(exc))
            return self.send_json(500, {"error": f"{type(exc).__name__}: {exc}"})


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


def serve() -> None:
    core.ensure_bridge_server()
    core.log("console.start", pid=os.getpid(), version=VERSION)

    def recovery():
        time.sleep(8)
        try:
            core.restore_pending()
        except Exception as exc:
            core.log("console.boot.restore.error", error=repr(exc))

    threading.Thread(target=recovery, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever(poll_interval=0.25)


def self_test() -> dict:
    sample_inv = {
        "capturedAt": 1,
        "safeForReboot": False,
        "uncoveredRoots": ["r2"],
        "unsafeTabKeys": ["t1"],
        "roots": [{"rootId": "r1", "coverage": "extension", "profilePath": "P", "executable": "chrome"}],
        "tabs": [
            {
                "key": "t1",
                "projectKey": "conversation:c1",
                "rootId": "r1",
                "coverage": "extension",
                "priority": 75,
                "paused": False,
                "title": "A",
                "url": "https://chatgpt.com/c/c1",
                "state": {"conversationId": "c1", "status": "idle", "branchSignature": "c1:u:a"},
            }
        ],
    }
    report = state_report(sample_inv)
    assert "TORSIONFIELD REBOOT STATE /2" in report
    assert '"conversationId": "c1"' in report
    return {"PASS": True, "version": VERSION, "reportCharacters": len(report)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--install-task", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return 0
    if args.install_task:
        print(json.dumps(install_task(), indent=2))
        return 0
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
