#!/usr/bin/env python3
from __future__ import annotations

import argparse, ctypes, hashlib, html, json, os, re, shutil, subprocess, sys, threading, time, urllib.request
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "0.1.0"
HOST = "127.0.0.1"
PORT = 17374
CHAT_RE = re.compile(r"^https://(?:chatgpt\.com|chat\.openai\.com)/", re.I)
CHAT_URL_RE = re.compile(rb"https://(?:chatgpt\.com|chat\.openai\.com)/(?:c/[A-Za-z0-9_-]+|g/[A-Za-z0-9_.-]+(?:/c/[A-Za-z0-9_-]+)?)[^\x00\s\"'<>]*", re.I)
HANDOFF_PROMPT = """TORSIONFIELD REBOOT HANDOFF REQUEST /1
The local machine is preparing for a controlled reboot. Do not start new machine operations.
Return a compact continuation capsule containing: current objective; what has actually completed; any machine/browser operation currently in flight; the exact next executable step; important paths/URLs/IDs; and any state that would not be obvious after this conversation is reopened. End with [[/TF_REBOOT_HANDOFF]]."""


def now_ms(): return int(time.time() * 1000)
def sha(value: str): return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:20]

def state_root() -> Path:
    base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) if os.name == "nt" else Path.home() / ".torsionfield"
    root = Path(os.environ.get("TF_REBOOT_STATE", str(base / "Torsionfield" / "RebootManager")))
    root.mkdir(parents=True, exist_ok=True)
    (root / "snapshots").mkdir(exist_ok=True)
    return root

ROOT = state_root()
PREFERENCES = ROOT / "preferences.json"
PENDING = ROOT / "restore_pending.json"
LOG = ROOT / "reboot-manager.jsonl"


def log(event, **data):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts":time.time(),"event":event,**data}, ensure_ascii=False)+"\n")

def atomic_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def load_json(path: Path, fallback):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return fallback

def find_node():
    for candidate in [os.environ.get("TF_NODE"), shutil.which("node"), r"C:\Program Files\nodejs\node.exe", "/usr/bin/node", "/usr/local/bin/node"]:
        if candidate and Path(candidate).exists(): return str(candidate)
    raise RuntimeError("Node.js not found; reboot CDP helper requires Node 22+")


def windows_split(command_line: str):
    if os.name != "nt": return command_line.split()
    argc = ctypes.c_int()
    shell32 = ctypes.windll.shell32
    shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    argv = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not argv: return []
    try: return [argv[i] for i in range(argc.value)]
    finally: ctypes.windll.kernel32.LocalFree(argv)


def browser_processes():
    if os.name != "nt":
        cp=subprocess.run(["ps","-eo","pid=,args="],text=True,capture_output=True)
        rows=[]
        for line in cp.stdout.splitlines():
            line=line.strip()
            if not line: continue
            pid,_,cmd=line.partition(" ")
            if re.search(r"(?:chrome|chromium|msedge)",cmd,re.I) and "--type=" not in cmd:
                rows.append({"pid":int(pid),"name":"browser","commandLine":cmd,"executable":windows_split(cmd)[0] if cmd else ""})
        return rows
    script = r'''$x=Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('chrome.exe','chromium.exe','msedge.exe') -and $_.CommandLine -and $_.CommandLine -notmatch '--type=' } | Select-Object ProcessId,Name,ExecutablePath,CommandLine; $x | ConvertTo-Json -Compress'''
    cp=subprocess.run(["powershell","-NoProfile","-Command",script],text=True,capture_output=True,timeout=15)
    if cp.returncode!=0: raise RuntimeError(cp.stderr.strip() or "browser process inventory failed")
    if not cp.stdout.strip(): return []
    raw=json.loads(cp.stdout)
    if isinstance(raw,dict): raw=[raw]
    return [{"pid":int(x.get("ProcessId") or 0),"name":x.get("Name") or "","executable":x.get("ExecutablePath") or "","commandLine":x.get("CommandLine") or ""} for x in raw]


def process_instance(row):
    argv=windows_split(row.get("commandLine") or "")
    profile=""; port=None
    for i,arg in enumerate(argv):
        if arg.startswith("--user-data-dir="): profile=arg.split("=",1)[1]
        elif arg=="--user-data-dir" and i+1<len(argv): profile=argv[i+1]
        elif arg.startswith("--remote-debugging-port="):
            try: port=int(arg.split("=",1)[1])
            except ValueError: pass
        elif arg=="--remote-debugging-port" and i+1<len(argv):
            try: port=int(argv[i+1])
            except ValueError: pass
    return {**row,"argv":argv,"profile":profile,"debugPort":port}


def window_titles_by_pid():
    if os.name != "nt": return {}
    out={}
    user32=ctypes.windll.user32
    @ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    def cb(hwnd,lparam):
        if not user32.IsWindowVisible(hwnd): return True
        length=user32.GetWindowTextLengthW(hwnd)
        if length<=0: return True
        buf=ctypes.create_unicode_buffer(length+1); user32.GetWindowTextW(hwnd,buf,length+1)
        pid=wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        title=buf.value.strip()
        if title: out.setdefault(int(pid.value),[]).append(title)
        return True
    user32.EnumWindows(cb,0)
    return out


def resident_browser_spec():
    candidates=[Path(os.environ.get("PROGRAMDATA",r"C:\ProgramData"))/"Torsionfield"/"resident"/"browser.json",
                Path(os.environ.get("PROGRAMDATA",r"C:\ProgramData"))/"Torsionfield"/"AutogenicRuntime"/"state"/"browser.json"]
    for p in candidates:
        if p.exists():
            value=load_json(p,{})
            if value: return value
    return {}


def cdp_alive(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/json/version",timeout=.7) as r:
            return json.loads(r.read().decode())
    except Exception: return None


def node_call(op, port, payload=None, timeout=150):
    helper=Path(__file__).with_name("reboot_cdp.mjs")
    req={"op":op,"port":int(port),"payload":payload or {}}
    cp=subprocess.run([find_node(),str(helper)],input=json.dumps(req),text=True,capture_output=True,timeout=timeout)
    candidates=[x.strip() for x in (cp.stdout+"\n"+cp.stderr).splitlines() if x.strip()]
    parsed=None
    for line in reversed(candidates):
        try:
            obj=json.loads(line)
            if isinstance(obj,dict): parsed=obj; break
        except Exception: pass
    if cp.returncode!=0 or not parsed or not parsed.get("ok"):
        raise RuntimeError((parsed or {}).get("error") or cp.stderr.strip() or cp.stdout.strip() or f"CDP helper failed: {op}")
    return parsed["result"]


def profile_candidates(instances):
    seen={}
    for i in instances:
        if i.get("profile"): seen[str(Path(i["profile"]))]=True
    spec=resident_browser_spec()
    if spec.get("profile"): seen[str(Path(spec["profile"]))]=True
    if os.name=="nt":
        local=Path(os.environ.get("LOCALAPPDATA",Path.home()/"AppData"/"Local"))
        for p in [local/"Google"/"Chrome"/"User Data",local/"Google"/"Chrome SxS"/"User Data",local/"Chromium"/"User Data",Path(r"E:\Transductive_MCP_Work\page-agent-chatgpt-profile")]:
            if p.exists(): seen[str(p)]=True
    return list(seen)


def scan_session_urls(profile: str, max_files=16, max_bytes=12_000_000):
    root=Path(profile)
    if not root.exists(): return []
    files=[]
    for pattern in ["Sessions/*","*/Sessions/*","Current Tabs","Last Tabs","Current Session","Last Session","*/Current Tabs","*/Last Tabs","*/Current Session","*/Last Session"]:
        for p in root.glob(pattern):
            try:
                if p.is_file(): files.append(p)
            except OSError: pass
    files=sorted(set(files),key=lambda p:p.stat().st_mtime if p.exists() else 0,reverse=True)[:max_files]
    found={}
    for p in files:
        try:
            data=p.read_bytes()[-max_bytes:]
        except Exception: continue
        blobs=[data]
        try: blobs.append(data.decode("utf-16le","ignore").encode("utf-8","ignore"))
        except Exception: pass
        for blob in blobs:
            for m in CHAT_URL_RE.finditer(blob):
                url=m.group(0).decode("utf-8","ignore").rstrip("\\/.,;:)")
                found[url]={"url":url,"source":str(p),"mtime":p.stat().st_mtime}
    return list(found.values())


def preferences(): return load_json(PREFERENCES,{"tabs":{}})
def save_preferences(value): atomic_json(PREFERENCES,value)

def tab_key(port, item):
    st=item.get("state") or {}
    stable=st.get("conversationId") or st.get("href") or item.get("url") or item.get("id")
    branch=st.get("branchSignature") or ""
    return sha(f"{port}:{stable}:{branch}")

def project_key(tab):
    st=tab.get("state") or {}
    if st.get("projectId"): return "project:"+st["projectId"]
    if st.get("conversationId"): return "conversation:"+st["conversationId"]
    title=(st.get("title") or tab.get("title") or "untitled").strip().lower()
    return "title:"+re.sub(r"\s+"," ",title)[:100]


def inventory(write_snapshot=False, reason="manual"):
    titles=window_titles_by_pid()
    instances=[process_instance(x) for x in browser_processes()]
    for i in instances: i["windowTitles"]=titles.get(i["pid"],[])
    spec=resident_browser_spec()
    ports={int(i["debugPort"]) for i in instances if i.get("debugPort")}
    if spec.get("debug_port"): ports.add(int(spec["debug_port"]))
    for p in (9448,9222):
        if cdp_alive(p): ports.add(p)
    live=[]; tabs=[]
    pref=preferences().get("tabs",{})
    for port in sorted(ports):
        if not cdp_alive(port): continue
        try: inv=node_call("inventory",port,timeout=40)
        except Exception as exc:
            live.append({"port":port,"error":str(exc)}); continue
        live.append({"port":port,"browser":inv.get("browser"),"pages":len(inv.get("pages") or [])})
        for item in inv.get("pages") or []:
            if not item.get("chatgpt"): continue
            key=tab_key(port,item); st=item.get("state") or {}; p=pref.get(key,{})
            tab={"key":key,"source":"cdp","debugPort":port,"targetId":item.get("id"),"url":st.get("href") or item.get("url"),"title":st.get("title") or item.get("title"),"state":st,
                 "priority":int(p.get("priority",50)),"paused":bool(p.get("paused",False))}
            tab["projectKey"]=project_key(tab)
            tab["needsHandoff"]=bool(st.get("streaming") or st.get("pendingAction") or (st.get("autogenic") or {}).get("loopError") or ((st.get("autogenic") or {}).get("lastOpStatus") not in (None,"","ok")))
            tabs.append(tab)
    live_urls={t.get("url") for t in tabs}
    disk=[]
    for profile in profile_candidates(instances):
        for record in scan_session_urls(profile):
            if record["url"] not in live_urls:
                key=sha("disk:"+profile+":"+record["url"])
                p=pref.get(key,{})
                disk.append({"key":key,"source":"session-file","profile":profile,"url":record["url"],"title":"","priority":int(p.get("priority",25)),"paused":bool(p.get("paused",True)),"sessionFile":record["source"],"projectKey":"disk:"+profile,"needsHandoff":False})
    tabs.extend(disk)
    active_profiles={str(Path(i["profile"])) for i in instances if i.get("profile")}
    unmanaged=[]
    for i in instances:
        if not i.get("debugPort"):
            urls=scan_session_urls(i.get("profile") or "") if i.get("profile") else []
            if urls: unmanaged.append({"pid":i["pid"],"profile":i.get("profile"),"windowTitles":i.get("windowTitles",[]),"chatgptSessionUrls":[x["url"] for x in urls]})
    snapshot={"schema":"TF_REBOOT_SNAPSHOT/1","managerVersion":VERSION,"id":time.strftime("%Y%m%d-%H%M%S"),"capturedAt":time.time(),"reason":reason,
              "residentBrowser":spec,"browserProcesses":instances,"cdpInstances":live,"tabs":tabs,"unmanagedChatgptBrowsers":unmanaged,"activeProfiles":sorted(active_profiles)}
    snapshot["safeForReboot"]=not unmanaged and all(not ((t.get("state") or {}).get("streaming") or (t.get("state") or {}).get("pendingAction")) for t in tabs if t.get("source")=="cdp")
    if write_snapshot:
        path=ROOT/"snapshots"/(snapshot["id"]+".json"); atomic_json(path,snapshot); snapshot["path"]=str(path); log("snapshot",id=snapshot["id"],tabs=len(tabs),safe=snapshot["safeForReboot"])
    return snapshot


def select_tabs(snapshot, keys):
    wanted=set(keys or [])
    return [t for t in snapshot.get("tabs",[]) if not wanted or t.get("key") in wanted]

def save_tab_pref(key, **changes):
    p=preferences(); rec=p.setdefault("tabs",{}).setdefault(key,{})
    rec.update(changes); save_preferences(p); return rec

def perform_tab_op(op, keys, extra=None):
    snap=inventory(False,"operation")
    out=[]
    for tab in select_tabs(snap,keys):
        if tab.get("source")!="cdp": continue
        try:
            payload={"target_id":tab["targetId"],**(extra or {})}
            result=node_call(op,tab["debugPort"],payload,timeout=150)
            out.append({"key":tab["key"],"ok":True,"result":result})
            if op=="freeze": save_tab_pref(tab["key"],paused=True)
            if op=="unfreeze": save_tab_pref(tab["key"],paused=False)
        except Exception as exc: out.append({"key":tab["key"],"ok":False,"error":str(exc)})
    return out


def request_handoffs(snapshot):
    results=[]
    for tab in snapshot.get("tabs",[]):
        if tab.get("source")!="cdp" or not tab.get("needsHandoff"): continue
        try:
            if (tab.get("state") or {}).get("streaming"): node_call("stop",tab["debugPort"],{"target_id":tab["targetId"]},timeout=30)
            result=node_call("handoff",tab["debugPort"],{"target_id":tab["targetId"],"prompt":HANDOFF_PROMPT,"timeout_ms":120000},timeout=140)
            results.append({"key":tab["key"],"url":tab["url"],"ok":True,"handoff":result.get("handoff","")})
        except Exception as exc: results.append({"key":tab["key"],"url":tab["url"],"ok":False,"error":str(exc)})
    return results


def prepare_reboot():
    before=inventory(True,"pre-reboot-before-handoffs")
    handoffs=request_handoffs(before)
    # Stop any remaining generation and capture postconditions.
    for tab in before.get("tabs",[]):
        if tab.get("source")=="cdp" and (tab.get("state") or {}).get("streaming"):
            try: node_call("stop",tab["debugPort"],{"target_id":tab["targetId"]},timeout=30)
            except Exception as exc: log("stop.error",key=tab["key"],error=str(exc))
    after=inventory(True,"pre-reboot-quiescent")
    after["handoffs"]=handoffs
    failed_handoffs=[x for x in handoffs if not x.get("ok")]
    after["safeForReboot"]=bool(after.get("safeForReboot") and not failed_handoffs)
    after["preparedAt"]=time.time()
    atomic_json(PENDING,{"status":"prepared","snapshot":after,"preparedAt":time.time(),"restoreAttempts":0})
    log("reboot.prepared",safe=after["safeForReboot"],tabs=len(after.get("tabs",[])),handoffs=len(handoffs),failed=len(failed_handoffs))
    return after


def launch_instance(instance, first_url=None):
    exe=instance.get("executable") or (instance.get("argv") or [""])[0]
    if not exe or not Path(exe).exists(): return {"ok":False,"error":"browser executable missing","instance":instance}
    argv=list(instance.get("argv") or [])
    filtered=[]
    for arg in argv[1:]:
        if CHAT_RE.match(str(arg)) or str(arg).startswith("http://") or str(arg).startswith("https://"): continue
        if str(arg).startswith("--type="): continue
        filtered.append(str(arg))
    if first_url: filtered.append(first_url)
    flags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS if os.name=="nt" else 0
    proc=subprocess.Popen([exe,*filtered],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags if os.name=="nt" else 0,start_new_session=os.name!="nt")
    return {"ok":True,"pid":proc.pid,"argv":[exe,*filtered]}


def wait_port(port,timeout=30):
    deadline=time.time()+timeout
    while time.time()<deadline:
        if cdp_alive(port): return True
        time.sleep(.25)
    return False


def restore_snapshot(snapshot):
    results=[]
    # Bring back CDP browser roots captured before reboot.
    for instance in snapshot.get("browserProcesses",[]):
        port=instance.get("debugPort")
        if not port: continue
        if not cdp_alive(port):
            first=next((t.get("url") for t in snapshot.get("tabs",[]) if t.get("debugPort")==port and t.get("url")),"https://chatgpt.com/")
            r=launch_instance(instance,first); results.append({"kind":"browser-launch","port":port,**r})
            if r.get("ok"): wait_port(port,40)
    # The resident-managed browser may not have appeared as a process at snapshot time.
    spec=snapshot.get("residentBrowser") or {}
    if spec.get("debug_port") and not cdp_alive(spec["debug_port"]):
        exe=spec.get("chrome_path") or spec.get("chrome")
        if exe and Path(exe).exists():
            args=[exe,f"--user-data-dir={spec.get('profile')}",f"--remote-debugging-address=127.0.0.1",f"--remote-debugging-port={spec.get('debug_port')}",*(spec.get('extra_args') or []),spec.get("url") or "https://chatgpt.com/"]
            flags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS if os.name=="nt" else 0
            p=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags if os.name=="nt" else 0,start_new_session=os.name!="nt")
            results.append({"kind":"resident-browser-launch","pid":p.pid,"port":spec["debug_port"]}); wait_port(spec["debug_port"],40)
    current=inventory(False,"restore-current")
    by_port_url={(t.get("debugPort"),t.get("url")):t for t in current.get("tabs",[]) if t.get("source")=="cdp"}
    for saved in sorted(snapshot.get("tabs",[]),key=lambda t:-int(t.get("priority",50))):
        if saved.get("source")!="cdp": continue
        port=saved.get("debugPort"); url=saved.get("url")
        if not port or not url or not cdp_alive(port):
            results.append({"kind":"tab","key":saved.get("key"),"ok":False,"error":"CDP instance unavailable"}); continue
        live=by_port_url.get((port,url))
        if not live:
            try:
                opened=node_call("open",port,{"url":url,"background":int(saved.get("priority",50))<75},timeout=20)
                tid=opened.get("targetId"); time.sleep(.7)
                live={"targetId":tid,"debugPort":port,"url":url}
                results.append({"kind":"tab-open","key":saved.get("key"),"ok":True,"targetId":tid})
            except Exception as exc:
                results.append({"kind":"tab-open","key":saved.get("key"),"ok":False,"error":str(exc)}); continue
        tid=live.get("targetId")
        st=saved.get("state") or {}
        draft=st.get("composerText") or ""
        if draft:
            try: results.append({"kind":"draft","key":saved.get("key"),"ok":True,"result":node_call("restore_draft",port,{"target_id":tid,"text":draft,"scroll_y":st.get("scrollY")},timeout=20)})
            except Exception as exc: results.append({"kind":"draft","key":saved.get("key"),"ok":False,"error":str(exc)})
        if saved.get("paused") or int(saved.get("priority",50))<25:
            try: node_call("freeze",port,{"target_id":tid},timeout=15); results.append({"kind":"freeze","key":saved.get("key"),"ok":True})
            except Exception as exc: results.append({"kind":"freeze","key":saved.get("key"),"ok":False,"error":str(exc)})
    final=inventory(True,"post-restore")
    return {"ok":True,"results":results,"final":final}


def restore_pending():
    pending=load_json(PENDING,{})
    if pending.get("status") not in ("prepared","rebooting","restoring"): return None
    pending["status"]="restoring"; pending["restoreAttempts"]=int(pending.get("restoreAttempts",0))+1; atomic_json(PENDING,pending)
    try:
        result=restore_snapshot(pending["snapshot"])
        pending["status"]="restored"; pending["restoredAt"]=time.time(); pending["resultSummary"]={"finalTabs":len(result["final"].get("tabs",[]))}; atomic_json(PENDING,pending)
        log("restore.complete",tabs=len(result["final"].get("tabs",[])))
        return result
    except Exception as exc:
        pending["status"]="restore-failed"; pending["error"]=repr(exc); atomic_json(PENDING,pending); log("restore.failed",error=repr(exc)); raise


def schedule_reboot(delay=12):
    pending=load_json(PENDING,{})
    snap=pending.get("snapshot") or {}
    if pending.get("status")!="prepared" or not snap.get("safeForReboot"): raise RuntimeError("no safe prepared reboot manifest")
    if time.time()-float(pending.get("preparedAt") or 0)>900: raise RuntimeError("prepared reboot manifest is stale")
    pending["status"]="rebooting"; pending["rebootScheduledAt"]=time.time(); atomic_json(PENDING,pending)
    if os.name=="nt": subprocess.Popen(["shutdown","/r","/t",str(int(delay)),"/d","p:0:0","/c","Torsionfield controlled reboot"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else: subprocess.Popen(["shutdown","-r",f"+{max(1,int(delay)//60)}","Torsionfield controlled reboot"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    log("reboot.scheduled",delay=delay)
    return {"scheduled":True,"delaySeconds":delay,"snapshotId":snap.get("id")}


def install_startup_task():
    if os.name!="nt": return {"installed":False,"reason":"Windows installer only in v0.1"}
    python=str(Path(sys.executable).resolve()); script=str(Path(__file__).resolve())
    task="Torsionfield Reboot Manager"
    command=f'"{python}" "{script}" --serve'
    cp=subprocess.run(["schtasks","/Create","/TN",task,"/TR",command,"/SC","ONLOGON","/RL","HIGHEST","/F"],text=True,capture_output=True)
    if cp.returncode!=0: raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return {"installed":True,"task":task,"command":command,"stdout":cp.stdout.strip()}


UI = r'''<!doctype html><meta charset="utf-8"><title>Torsionfield Reboot Manager</title>
<style>body{font:14px system-ui;margin:0;background:#111;color:#eee}header{position:sticky;top:0;background:#171717;padding:14px 18px;border-bottom:1px solid #444;z-index:4}button{margin:3px;padding:7px 10px}main{padding:14px 18px}.group{border:1px solid #3b3b3b;margin:12px 0}.gh{background:#202020;padding:8px;font-weight:700}.tab{display:grid;grid-template-columns:28px 64px 90px 1fr 100px;gap:8px;padding:8px;border-top:1px solid #292929;align-items:start}.bad{color:#ff9c9c}.ok{color:#9cffb0}.muted{color:#aaa}pre{white-space:pre-wrap;max-height:240px;overflow:auto}.draft{color:#ffd37a}</style>
<header><b>TF REBOOT MANAGER</b> <span id="summary"></span><br><button onclick="refresh()">Refresh</button><button onclick="snapshot()">Snapshot</button><button onclick="bulk('freeze')">Pause selected</button><button onclick="bulk('unfreeze')">Resume selected</button><button onclick="bulk('stop')">Stop selected execution</button><button onclick="prepare()">Prepare reboot</button><button onclick="reboot()">REBOOT IF SAFE</button></header><main id="main">Loading…</main>
<script>let state=null;const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}function chosen(){return [...document.querySelectorAll('.pick:checked')].map(x=>x.value)}async function refresh(){state=await api('/api/inventory');render()}async function snapshot(){state=await api('/api/snapshot',{});render()}async function bulk(op){await api('/api/tab/'+op,{keys:chosen()});await refresh()}async function prepare(){state=await api('/api/prepare-reboot',{});render();alert('Prepared. safeForReboot='+state.safeForReboot)}async function reboot(){if(!confirm('Execute the prepared controlled reboot?'))return;alert(JSON.stringify(await api('/api/reboot',{delay:12})))}async function priority(k,v){await api('/api/priority',{key:k,priority:Number(v)});await refresh()}function render(){let tabs=state.tabs||[], groups={};for(let t of tabs)(groups[t.projectKey]??=[]).push(t);document.getElementById('summary').innerHTML=`— ${tabs.length} ChatGPT tabs — <b class="${state.safeForReboot?'ok':'bad'}">${state.safeForReboot?'SAFE':'NOT QUIESCENT'}</b>`;let h='';if((state.unmanagedChatgptBrowsers||[]).length)h+=`<p class=bad>Unmanaged Chrome instances with ChatGPT session evidence: ${state.unmanagedChatgptBrowsers.length}. Reboot is blocked.</p>`;for(let [g,ts] of Object.entries(groups)){h+=`<section class=group><div class=gh>${esc(g)} — ${ts.length} tab(s)</div>`;for(let t of ts.sort((a,b)=>b.priority-a.priority)){let s=t.state||{};h+=`<div class=tab><input class=pick type=checkbox value="${t.key}"><b>${t.priority}</b><span class="${s.streaming||s.pendingAction?'bad':'ok'}">${esc(s.status||t.source)}</span><div><a style="color:#9cc8ff" href="${esc(t.url)}" target=_blank>${esc(t.title||t.url)}</a><br><span class=muted>${esc(t.url)}</span>${s.composerText?`<div class=draft>DRAFT: ${esc(s.composerText.slice(0,300))}</div>`:''}${t.needsHandoff?'<div class=bad>HANDOFF REQUIRED</div>':''}${s.latestAssistant?`<details><summary>latest assistant / branch</summary><pre>${esc(s.latestAssistant.text)}\n\nbranch: ${esc(s.branchSignature)}</pre></details>`:''}</div><select onchange="priority('${t.key}',this.value)">${[100,75,50,25,10,0].map(x=>`<option ${x==t.priority?'selected':''}>${x}</option>`).join('')}</select></div>`}h+='</section>'}document.getElementById('main').innerHTML=h||'<p>No ChatGPT tabs found.</p>'}refresh()</script>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt,*args): log("http",message=fmt%args)
    def send_json(self,status,obj):
        body=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def body(self):
        n=int(self.headers.get("Content-Length","0") or 0); return json.loads((self.rfile.read(n) if n else b"{}").decode())
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":
            body=UI.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body);return
        if path=="/api/health": return self.send_json(200,{"ok":True,"version":VERSION,"pid":os.getpid(),"root":str(ROOT)})
        if path=="/api/inventory": return self.send_json(200,inventory(False,"ui"))
        if path=="/api/pending": return self.send_json(200,load_json(PENDING,{}))
        return self.send_json(404,{"error":"not found"})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            body=self.body()
            if path=="/api/snapshot": return self.send_json(200,inventory(True,"ui-snapshot"))
            if path=="/api/priority":
                rec=save_tab_pref(str(body["key"]),priority=int(body.get("priority",50))); return self.send_json(200,{"ok":True,"preference":rec})
            if path=="/api/tab/freeze": return self.send_json(200,{"results":perform_tab_op("freeze",body.get("keys"))})
            if path=="/api/tab/unfreeze": return self.send_json(200,{"results":perform_tab_op("unfreeze",body.get("keys"))})
            if path=="/api/tab/stop": return self.send_json(200,{"results":perform_tab_op("stop",body.get("keys"))})
            if path=="/api/prepare-reboot": return self.send_json(200,prepare_reboot())
            if path=="/api/restore": return self.send_json(200,restore_snapshot(body.get("snapshot") or load_json(PENDING,{}).get("snapshot") or {}))
            if path=="/api/reboot": return self.send_json(200,schedule_reboot(int(body.get("delay",12))))
            return self.send_json(404,{"error":"not found"})
        except Exception as exc:
            log("api.error",path=path,error=repr(exc)); return self.send_json(500,{"error":f"{type(exc).__name__}: {exc}"})


def serve():
    httpd=ThreadingHTTPServer((HOST,PORT),Handler); log("manager.start",pid=os.getpid(),version=VERSION,port=PORT)
    def boot_restore():
        time.sleep(8)
        try: restore_pending()
        except Exception as exc: log("boot.restore.error",error=repr(exc))
    threading.Thread(target=boot_restore,daemon=True).start()
    print(f"Torsionfield Reboot Manager {VERSION} http://{HOST}:{PORT}",flush=True)
    httpd.serve_forever(poll_interval=.25)


def self_test():
    assert windows_split('chrome.exe --remote-debugging-port=9448 --user-data-dir="C:\\TF Profile" https://chatgpt.com/c/abc')[-1].startswith('https://')
    sample={"debugPort":9448,"targetId":"x","url":"https://chatgpt.com/c/abc","title":"T","state":{"conversationId":"abc","branchSignature":"abc:u:a:"}}
    assert tab_key(9448,sample)==tab_key(9448,sample)
    assert project_key(sample)=="conversation:abc"
    return {"PASS":True,"version":VERSION,"root":str(ROOT)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--serve",action="store_true");ap.add_argument("--self-test",action="store_true");ap.add_argument("--snapshot-once",action="store_true");ap.add_argument("--prepare-reboot",action="store_true");ap.add_argument("--reboot-if-safe",action="store_true");ap.add_argument("--restore-pending",action="store_true");ap.add_argument("--install-task",action="store_true")
    a=ap.parse_args()
    if a.self_test: print(json.dumps(self_test(),indent=2)); return 0
    if a.snapshot_once: print(json.dumps(inventory(True,"cli"),indent=2)); return 0
    if a.prepare_reboot: print(json.dumps(prepare_reboot(),indent=2)); return 0
    if a.restore_pending: print(json.dumps(restore_pending(),indent=2)); return 0
    if a.install_task: print(json.dumps(install_startup_task(),indent=2)); return 0
    if a.reboot_if_safe: print(json.dumps(schedule_reboot(),indent=2)); return 0
    serve(); return 0

if __name__=="__main__": raise SystemExit(main())
