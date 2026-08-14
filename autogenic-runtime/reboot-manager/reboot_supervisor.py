#!/usr/bin/env python3
from __future__ import annotations

import argparse, ctypes, hashlib, json, os, re, shutil, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION='0.2.0'
HOST='127.0.0.1'; PORT=17374; BRIDGE_PORT=17375
CHAT_URL_RE=re.compile(rb'https://(?:chatgpt\.com|chat\.openai\.com)/(?:c/[0-9A-Za-z-]{20,}|g/[0-9A-Za-z_.-]+(?:/c/[0-9A-Za-z-]{20,})?)',re.I)
HANDOFF_PROMPT='''TORSIONFIELD REBOOT HANDOFF REQUEST /1
The local machine is preparing for a controlled reboot. Do not start new machine operations.
Return a compact continuation capsule containing: current objective; what has actually completed; any machine/browser operation currently in flight; the exact next executable step; important paths/URLs/IDs; and any state that would not be obvious after this conversation is reopened. End with [[/TF_REBOOT_HANDOFF]].'''


def root_dir():
    base=Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData')) if os.name=='nt' else Path.home()/'.torsionfield'
    p=Path(os.environ.get('TF_REBOOT_STATE',str(base/'Torsionfield'/'RebootSupervisor')));p.mkdir(parents=True,exist_ok=True);(p/'snapshots').mkdir(exist_ok=True);return p
ROOT=root_dir(); PENDING=ROOT/'restore_pending.json'; PREFS=ROOT/'preferences.json'; LOG=ROOT/'supervisor.jsonl'

def log(event,**data):
    with LOG.open('a',encoding='utf-8') as f:f.write(json.dumps({'ts':time.time(),'event':event,**data},ensure_ascii=False)+'\n')
def atomic(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
def load(path,fallback):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return fallback
def short_hash(text):return hashlib.sha256(str(text).encode()).hexdigest()[:16]

def split_cmdline(command_line):
    if os.name!='nt':return str(command_line).split()
    argc=ctypes.c_int(); fn=ctypes.windll.shell32.CommandLineToArgvW;fn.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)];fn.restype=ctypes.POINTER(wintypes.LPWSTR)
    ptr=fn(str(command_line),ctypes.byref(argc));
    if not ptr:return[]
    try:return[ptr[i] for i in range(argc.value)]
    finally:ctypes.windll.kernel32.LocalFree(ptr)

def browser_processes():
    if os.name!='nt':return[]
    ps=r'''$x=Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('chrome.exe','chromium.exe','msedge.exe') -and $_.CommandLine -and $_.CommandLine -notmatch '--type=' } | Select-Object ProcessId,Name,ExecutablePath,CommandLine; $x | ConvertTo-Json -Compress'''
    cp=subprocess.run(['powershell','-NoProfile','-Command',ps],text=True,capture_output=True,timeout=20)
    if cp.returncode:return[]
    if not cp.stdout.strip():return[]
    raw=json.loads(cp.stdout);raw=[raw] if isinstance(raw,dict) else raw
    return[{'pid':int(x.get('ProcessId') or 0),'name':x.get('Name') or'','executable':x.get('ExecutablePath') or'','commandLine':x.get('CommandLine') or''} for x in raw]

def arg_value(argv,name):
    prefix=name+'='
    for i,arg in enumerate(argv):
        if arg.startswith(prefix):return arg.split('=',1)[1]
        if arg==name and i+1<len(argv):return argv[i+1]
    return''
def default_user_data(exe):
    local=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'));low=str(exe).lower()
    if 'chrome sxs' in low:return local/'Google'/'Chrome SxS'/'User Data'
    if '\\google\\chrome\\' in low:return local/'Google'/'Chrome'/'User Data'
    if 'msedge' in low:return local/'Microsoft'/'Edge'/'User Data'
    return Path()
def profile_path(user_data,profile_dir):
    root=Path(user_data)
    if profile_dir:return root/profile_dir
    if (root/'Default'/'Preferences').exists() or (root/'Default'/'Secure Preferences').exists():return root/'Default'
    return root

def parse_root(row):
    argv=split_cmdline(row.get('commandLine') or'');exe=row.get('executable') or (argv[0] if argv else'')
    user_data=arg_value(argv,'--user-data-dir'); profile_dir=arg_value(argv,'--profile-directory')
    if not user_data:
        d=default_user_data(exe);user_data=str(d) if str(d) not in ('','.') else''
    debug=arg_value(argv,'--remote-debugging-port');
    try:debug=int(debug) if debug else None
    except ValueError:debug=None
    pp=profile_path(user_data,profile_dir) if user_data else Path()
    key=short_hash(f'{str(exe).lower()}|{str(user_data).lower()}|{profile_dir.lower()}')
    return{**row,'argv':argv,'userDataDir':user_data,'profileDirectory':profile_dir,'profilePath':str(pp) if str(pp)!='.' else'','debugPort':debug,'rootId':'browser-'+key,'client':'browser-'+key}

def discover_roots():
    merged={}
    for row in browser_processes():
        r=parse_root(row);key=r['rootId']
        if key not in merged:merged[key]={**r,'pids':[r['pid']]}
        else:merged[key]['pids'].append(r['pid'])
    return list(merged.values())

def scan_session_urls(profile,max_files=20,max_bytes=16_000_000):
    p=Path(profile)
    if not p.exists():return[]
    files=[]
    for pattern in ('Sessions/*','Current Tabs','Last Tabs','Current Session','Last Session'):
        files.extend([x for x in p.glob(pattern) if x.is_file()])
    files=sorted(set(files),key=lambda x:x.stat().st_mtime,reverse=True)[:max_files];found={}
    for file in files:
        try:data=file.read_bytes()[-max_bytes:]
        except Exception:continue
        for match in CHAT_URL_RE.finditer(data):
            url=match.group(0).decode('ascii','ignore');found[url]={'url':url,'sessionFile':str(file),'mtime':file.stat().st_mtime}
    return list(found.values())

def extension_record(root):
    profile=Path(root.get('profilePath') or'');secure=profile/'Secure Preferences'
    if not secure.exists():return None
    try:settings=json.loads(secure.read_text(encoding='utf-8')).get('extensions',{}).get('settings',{})
    except Exception:return None
    candidates=[]
    for ext_id,value in settings.items():
        path=str(value.get('path') or'');manifest=value.get('manifest') or{};name=str(manifest.get('name') or'')
        perms=(value.get('active_permissions') or{}).get('api') or[];hosts=(value.get('active_permissions') or{}).get('scriptable_host') or[]
        score=(4 if 'torsionfield' in name.lower() else 0)+(3 if 'torsionfield' in path.lower() else 0)+(2 if 'tabs' in perms else 0)+(2 if 'scripting' in perms else 0)+(1 if any('chatgpt.com' in h for h in hosts) else 0)
        if score>=6:candidates.append((score,{'id':ext_id,'path':path,'name':name,'version':manifest.get('version'),'permissions':perms,'hosts':hosts}))
    return max(candidates,key=lambda x:x[0])[1] if candidates else None

def ensure_bridge_files(ext):
    if not ext or not ext.get('path'):return False
    src=Path(__file__).parent/'extension_bridge';dst=Path(ext['path'])
    if not src.exists() or not dst.exists():return False
    for name in ('reboot_bridge.html','reboot_bridge.js'):shutil.copy2(src/name,dst/name)
    return True

def bridge_base():return f'http://{HOST}:{BRIDGE_PORT}'
def http_json(path,method='GET',body=None,timeout=10):
    data=None if body is None else json.dumps(body).encode();headers={'content-type':'application/json'} if data else{}
    request=urllib.request.Request(bridge_base()+path,data=data,headers=headers,method=method)
    with urllib.request.urlopen(request,timeout=timeout) as response:return json.loads(response.read().decode())
def bridge_clients():
    try:return http_json('/api/clients',timeout=3).get('clients',{})
    except Exception:return{}
def bridge_rpc(client,op,payload=None,timeout_ms=120000):
    value=http_json('/api/rpc','POST',{'client':client,'message':{'op':op,'payload':payload or{}},'timeoutMs':timeout_ms},timeout=timeout_ms/1000+10)
    if not value.get('ok'):raise RuntimeError(value.get('error') or'bridge rpc failed')
    return value.get('value')
def bridge_healthy(client):
    info=bridge_clients().get(client);return bool(info and float(info.get('ageSeconds',999))<35 and not info.get('error'))

def cdp_alive(port):
    if not port:return False
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{int(port)}/json/version',timeout=.8):return True
    except Exception:return False

def node_call(op,port,payload=None,timeout=60):
    helper=Path(__file__).with_name('reboot_cdp.mjs');node=shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
    cp=subprocess.run([node,str(helper)],input=json.dumps({'op':op,'port':port,'payload':payload or{}}),text=True,capture_output=True,timeout=timeout)
    for line in reversed([x for x in cp.stdout.splitlines() if x.strip()]):
        try:
            j=json.loads(line)
            if j.get('ok'):return j.get('result')
            if 'error' in j:raise RuntimeError(j['error'])
        except json.JSONDecodeError:pass
    raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or'CDP helper failed')

def open_bridge(root,ext):
    if not ext:return{'ok':False,'reason':'torsionfield-extension-not-installed'}
    ensure_bridge_files(ext)
    url=f"chrome-extension://{ext['id']}/reboot_bridge.html?client={urllib.parse.quote(root['client'])}&server={urllib.parse.quote(bridge_base(),safe=':/')}"
    args=[root['executable']]
    if root.get('userDataDir') and arg_value(root.get('argv') or[],'--user-data-dir'):args.append(f"--user-data-dir={root['userDataDir']}")
    if root.get('profileDirectory'):args.append(f"--profile-directory={root['profileDirectory']}")
    args.append(url)
    subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return{'ok':True,'url':url,'extension':ext}
def ensure_bridge(root,timeout=12):
    if bridge_healthy(root['client']):return{'ok':True,'already':True}
    ext=extension_record(root);opened=open_bridge(root,ext)
    if not opened.get('ok'):return opened
    end=time.time()+timeout
    while time.time()<end:
        if bridge_healthy(root['client']):return{'ok':True,'opened':True,'extension':ext}
        time.sleep(.25)
    return{'ok':False,'reason':'bridge-page-did-not-register','extension':ext,'url':opened.get('url')}

def tab_key(root_id,tab):
    state=tab.get('state') or{};stable=state.get('conversationId') or tab.get('url') or tab.get('id');branch=state.get('branchSignature') or''
    return short_hash(f'{root_id}|{stable}|{branch}')
def project_key(tab):
    st=tab.get('state') or{}
    if st.get('projectId'):return'project:'+st['projectId']
    if st.get('conversationId'):return'conversation:'+st['conversationId']
    return'title:'+re.sub(r'\s+',' ',str(tab.get('title') or'untitled').lower())[:100]
def preferences():return load(PREFS,{'tabs':{}})
def set_pref(key,**changes):
    p=preferences();r=p.setdefault('tabs',{}).setdefault(key,{});r.update(changes);atomic(PREFS,p);return r

def inventory(auto_bridge=True):
    roots=discover_roots();clients=bridge_clients();prefs=preferences().get('tabs',{});all_tabs=[];root_records=[]
    for root in roots:
        evidence=scan_session_urls(root.get('profilePath') or'');ext=extension_record(root);coverage='none';inv=None;errors=[];bridge_result=None
        if auto_bridge and evidence and not bridge_healthy(root['client']):
            try:bridge_result=ensure_bridge(root)
            except Exception as exc:bridge_result={'ok':False,'reason':repr(exc)}
        if bridge_healthy(root['client']):
            try:inv=bridge_rpc(root['client'],'inventory',{},90000);coverage='extension'
            except Exception as exc:errors.append('bridge:'+repr(exc))
        if inv is None and cdp_alive(root.get('debugPort')):
            try:inv=node_call('inventory',root['debugPort'],{},60);coverage='cdp'
            except Exception as exc:errors.append('cdp:'+repr(exc))
        tabs=[]
        if inv:
            source_tabs=inv.get('tabs') if coverage=='extension' else inv.get('pages')
            for tab in source_tabs or[]:
                is_chat=bool(tab.get('chatgpt')) if coverage=='extension' else bool(tab.get('chatgpt'))
                if not is_chat:continue
                t=dict(tab);t['rootId']=root['rootId'];t['client']=root['client'];t['coverage']=coverage;t['key']=tab_key(root['rootId'],t);t['projectKey']=project_key(t)
                pref=prefs.get(t['key'],{});t['priority']=int(pref.get('priority',50));t['paused']=bool(pref.get('paused',False))
                st=t.get('state') or{};aut=st.get('autogenic') or{}
                t['needsHandoff']=bool(st.get('streaming') or st.get('pendingAction') or aut.get('loopError') or (aut.get('lastOpStatus') not in (None,'','ok')))
                tabs.append(t);all_tabs.append(t)
        discovered_chat=bool(evidence or tabs)
        covered=bool((not discovered_chat) or (coverage in ('extension','cdp') and inv is not None and not errors))
        root_records.append({**root,'extension':ext,'sessionEvidence':evidence,'discoveredChatGPT':discovered_chat,'coverage':coverage,'covered':covered,'bridgeEnsure':bridge_result,'errors':errors,'inventory':inv,'tabs':tabs})
    unsafe_tabs=[t for t in all_tabs if (t.get('state') or{}).get('streaming') or (t.get('state') or{}).get('pendingAction')]
    uncovered=[r for r in root_records if r['discoveredChatGPT'] and not r['covered']]
    return{'schema':'TF_REBOOT_INVENTORY/2','version':VERSION,'capturedAt':time.time(),'roots':root_records,'tabs':all_tabs,'uncoveredRoots':[r['rootId'] for r in uncovered],'unsafeTabKeys':[t['key'] for t in unsafe_tabs],'safeForReboot':not uncovered and not unsafe_tabs}

def snapshot(reason):
    value=inventory(True);value['id']=time.strftime('%Y%m%d-%H%M%S');value['reason']=reason;path=ROOT/'snapshots'/f"{value['id']}.json";atomic(path,value);value['path']=str(path);log('snapshot',id=value['id'],safe=value['safeForReboot'],tabs=len(value['tabs']),uncovered=value['uncoveredRoots']);return value

def action(tab,op,payload=None,timeout=120000):
    if tab.get('coverage')=='extension':return bridge_rpc(tab['client'],op,{'tabId':tab['id'],**(payload or{})},timeout)
    if tab.get('coverage')=='cdp':
        root=next(r for r in discover_roots() if r['rootId']==tab['rootId']);return node_call(op,root['debugPort'],{'target_id':tab['id'],**(payload or{})},timeout/1000+5)
    raise RuntimeError('tab-uncovered')

def request_handoffs(inv):
    results=[]
    for tab in inv.get('tabs',[]):
        if not tab.get('needsHandoff'):continue
        try:
            if (tab.get('state') or{}).get('streaming'):action(tab,'stop',{},30000)
            result=action(tab,'handoff',{'prompt':HANDOFF_PROMPT},140000)
            results.append({'key':tab['key'],'ok':True,'url':tab.get('url'),'response':result.get('response') if isinstance(result,dict) else None})
        except Exception as exc:results.append({'key':tab['key'],'ok':False,'url':tab.get('url'),'error':repr(exc)})
    return results

def rehearse(inv):
    results=[]
    for root in inv.get('roots',[]):
        if root.get('coverage')!='extension' or not root.get('tabs'):continue
        try:
            result=bridge_rpc(root['client'],'rehearse_restore',{'snapshot':root['inventory']},300000);results.append({'rootId':root['rootId'],'ok':bool(result.get('ok')),'result':result})
        except Exception as exc:results.append({'rootId':root['rootId'],'ok':False,'error':repr(exc)})
    return results

def prepare():
    before=snapshot('prepare-before')
    if before.get('uncoveredRoots'):
        prepared={**before,'handoffs':[],'rehearsal':[],'safeForReboot':False,'prepareError':'uncovered-browser-roots'};atomic(PENDING,{'status':'blocked','preparedAt':time.time(),'snapshot':prepared});return prepared
    handoffs=request_handoffs(before)
    after=snapshot('prepare-after-handoffs')
    rehearsal=rehearse(after)
    failures=[x for x in handoffs if not x.get('ok')]+[x for x in rehearsal if not x.get('ok')]
    safe=bool(after.get('safeForReboot') and not failures)
    prepared={**after,'handoffs':handoffs,'rehearsal':rehearsal,'safeForReboot':safe,'preparedAt':time.time()}
    atomic(PENDING,{'status':'prepared' if safe else'blocked','preparedAt':time.time(),'snapshot':prepared,'restoreAttempts':0});log('prepare',safe=safe,handoffs=len(handoffs),rehearsals=len(rehearsal),failures=len(failures));return prepared

def schedule_reboot(delay=20):
    pending=load(PENDING,{});snap=pending.get('snapshot') or{}
    if pending.get('status')!='prepared' or not snap.get('safeForReboot'):raise RuntimeError('no-safe-prepared-manifest')
    if time.time()-float(pending.get('preparedAt') or0)>900:raise RuntimeError('prepared-manifest-stale')
    pending['status']='rebooting';pending['scheduledAt']=time.time();atomic(PENDING,pending)
    if os.name=='nt':subprocess.Popen(['shutdown','/r','/t',str(int(delay)),'/d','p:0:0','/c','Torsionfield controlled reboot'])
    else:raise RuntimeError('physical reboot v0.2 acceptance is Windows-only')
    log('reboot.scheduled',delay=delay,id=snap.get('id'));return{'scheduled':True,'delaySeconds':delay,'snapshotId':snap.get('id')}

def restore_pending():
    pending=load(PENDING,{});
    if pending.get('status') not in ('rebooting','restoring'):return{'skipped':True,'status':pending.get('status')}
    pending['status']='restoring';pending['restoreAttempts']=int(pending.get('restoreAttempts',0))+1;atomic(PENDING,pending);snap=pending['snapshot'];results=[]
    for saved_root in snap.get('roots',[]):
        if not saved_root.get('discoveredChatGPT'):continue
        current=next((r for r in discover_roots() if r['rootId']==saved_root['rootId']),None)
        if not current:
            argv=saved_root.get('argv') or[];exe=saved_root.get('executable')
            if exe and Path(exe).exists():
                args=[exe]+[a for a in argv[1:] if not str(a).startswith(('http://','https://','chrome-extension://'))]
                if '--restore-last-session' not in args:args.append('--restore-last-session')
                subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(2);current=next((r for r in discover_roots() if r['rootId']==saved_root['rootId']),None)
        if not current:results.append({'rootId':saved_root['rootId'],'ok':False,'error':'browser-root-not-restored'});continue
        bridge=ensure_bridge(current,25)
        if not bridge.get('ok'):results.append({'rootId':current['rootId'],'ok':False,'error':'bridge-not-restored','bridge':bridge});continue
        try:
            value=bridge_rpc(current['client'],'restore_manifest',{'snapshot':saved_root.get('inventory') or{}},300000);results.append({'rootId':current['rootId'],'ok':bool(value.get('ok')),'result':value})
        except Exception as exc:results.append({'rootId':current['rootId'],'ok':False,'error':repr(exc)})
    final=snapshot('post-reboot-restore');ok=all(x.get('ok') for x in results) and not final.get('uncoveredRoots') and not final.get('unsafeTabKeys')
    pending['status']='restored' if ok else'restore-failed';pending['restoredAt']=time.time();pending['results']=results;pending['finalSnapshot']=final;atomic(PENDING,pending);log('restore',ok=ok,results=len(results));return{'ok':ok,'results':results,'final':final}

def ensure_bridge_server():
    try:
        with urllib.request.urlopen(bridge_base()+'/api/health',timeout=1):return True
    except Exception:pass
    script=Path(__file__).with_name('browser_bridge.py');flags=(subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS) if os.name=='nt' else0
    subprocess.Popen([sys.executable,str(script),'--port',str(BRIDGE_PORT)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags if os.name=='nt' else0,start_new_session=os.name!='nt')
    end=time.time()+5
    while time.time()<end:
        try:
            with urllib.request.urlopen(bridge_base()+'/api/health',timeout=.5):return True
        except Exception:time.sleep(.1)
    return False

def install_task():
    if os.name!='nt':return{'installed':False}
    cmd=f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --serve';task='Torsionfield Reboot Supervisor'
    cp=subprocess.run(['schtasks','/Create','/TN',task,'/TR',cmd,'/SC','ONLOGON','/RL','HIGHEST','/F'],text=True,capture_output=True)
    if cp.returncode:raise RuntimeError(cp.stderr or cp.stdout)
    return{'installed':True,'task':task,'command':cmd}

UI='''<!doctype html><meta charset=utf-8><title>TF Reboot Supervisor</title><style>body{font:13px system-ui;background:#111;color:#eee;margin:0}header{position:sticky;top:0;background:#181818;padding:12px;border-bottom:1px solid #444}main{padding:12px}.root{border:1px solid #444;margin:10px 0}.rh{padding:8px;background:#222}.tab{padding:8px;border-top:1px solid #333;display:grid;grid-template-columns:55px 85px 1fr;gap:8px}.ok{color:#8aff9e}.bad{color:#ff9696}.draft{color:#ffd67a}button{margin:2px;padding:6px 9px}select{background:#222;color:#eee}</style><header><b>TF REBOOT SUPERVISOR</b> <span id=s></span><br><button onclick="refresh()">Refresh</button><button onclick="snapshot()">Snapshot</button><button onclick="prepare()">Prepare + rehearse</button><button onclick="reboot()">REBOOT IF SAFE</button></header><main id=m>Loading…</main><script>let data;async function api(p,b){let r=await fetch(p,{method:b?'POST':'GET',headers:{'content-type':'application/json'},body:b?JSON.stringify(b):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}const e=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));async function refresh(){data=await api('/api/inventory');render()}async function snapshot(){data=await api('/api/snapshot',{});render()}async function prepare(){data=await api('/api/prepare',{});render();alert('safeForReboot='+data.safeForReboot)}async function reboot(){if(!confirm('Execute the strictly prepared controlled reboot?'))return;alert(JSON.stringify(await api('/api/reboot',{delay:20})))}async function priority(k,v){await api('/api/priority',{key:k,priority:+v});refresh()}function render(){s.innerHTML=`— ${data.tabs.length} ChatGPT tabs — <b class=${data.safeForReboot?'ok':'bad'}>${data.safeForReboot?'QUIESCENT':'BLOCKED'}</b>`;let h='';for(const r of data.roots){h+=`<section class=root><div class=rh><b>${e(r.rootId)}</b> · ${e(r.coverage)} · <span class=${r.covered?'ok':'bad'}>${r.covered?'covered':'UNCOVERED'}</span><br>${e(r.executable)} · ${e(r.profilePath)}</div>`;for(const t of r.tabs||[]){let st=t.state||{};h+=`<div class=tab><select onchange="priority('${t.key}',this.value)">${[100,75,50,25,10,0].map(x=>`<option ${x==t.priority?'selected':''}>${x}</option>`).join('')}</select><span class=${st.streaming||st.pendingAction?'bad':'ok'}>${e(st.status||'unknown')}</span><div><b>${e(t.title)}</b><br>${e(t.url)}${st.composerText?`<div class=draft>DRAFT ${e(st.composerText.slice(0,400))}</div>`:''}${t.needsHandoff?'<div class=bad>HANDOFF REQUIRED</div>':''}</div></div>`}h+='</section>'}m.innerHTML=h||'No browser roots.'}refresh()</script>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def sendj(self,status,obj):
        b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('content-type','application/json; charset=utf-8');self.send_header('content-length',str(len(b)));self.end_headers();self.wfile.write(b)
    def body(self):
        n=int(self.headers.get('content-length','0') or0);return json.loads((self.rfile.read(n) if n else b'{}').decode())
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/':b=UI.encode();self.send_response(200);self.send_header('content-type','text/html; charset=utf-8');self.send_header('content-length',str(len(b)));self.end_headers();self.wfile.write(b);return
        if p=='/api/health':return self.sendj(200,{'ok':True,'version':VERSION,'root':str(ROOT)})
        if p=='/api/inventory':return self.sendj(200,inventory(True))
        if p=='/api/pending':return self.sendj(200,load(PENDING,{}))
        self.sendj(404,{'error':'not found'})
    def do_POST(self):
        p=urlparse(self.path).path
        try:
            body=self.body()
            if p=='/api/snapshot':return self.sendj(200,snapshot('ui'))
            if p=='/api/prepare':return self.sendj(200,prepare())
            if p=='/api/reboot':return self.sendj(200,schedule_reboot(int(body.get('delay',20))))
            if p=='/api/restore':return self.sendj(200,restore_pending())
            if p=='/api/priority':return self.sendj(200,{'ok':True,'pref':set_pref(str(body['key']),priority=int(body.get('priority',50)))})
            self.sendj(404,{'error':'not found'})
        except Exception as exc:log('api.error',path=p,error=repr(exc));self.sendj(500,{'error':f'{type(exc).__name__}: {exc}'})

def serve():
    ensure_bridge_server();log('serve.start',pid=os.getpid(),version=VERSION)
    def recovery():time.sleep(8);restore_pending()
    threading.Thread(target=recovery,daemon=True).start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever(.25)
def self_test():
    assert CHAT_URL_RE.search(b'https://chatgpt.com/c/6a7ef8a3-aa70-83ec-9105-0ace064c98e8')
    assert not CHAT_URL_RE.search(b'https://example.com/c/6a7ef8a3-aa70-83ec-9105-0ace064c98e8')
    return{'PASS':True,'version':VERSION,'root':str(ROOT)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--serve',action='store_true');ap.add_argument('--inventory',action='store_true');ap.add_argument('--snapshot',action='store_true');ap.add_argument('--prepare',action='store_true');ap.add_argument('--reboot-if-safe',action='store_true');ap.add_argument('--restore-pending',action='store_true');ap.add_argument('--install-task',action='store_true');ap.add_argument('--self-test',action='store_true');a=ap.parse_args();ensure_bridge_server()
    if a.self_test:print(json.dumps(self_test(),indent=2));return0
    if a.inventory:print(json.dumps(inventory(True),indent=2));return0
    if a.snapshot:print(json.dumps(snapshot('cli'),indent=2));return0
    if a.prepare:print(json.dumps(prepare(),indent=2));return0
    if a.reboot_if_safe:print(json.dumps(schedule_reboot(),indent=2));return0
    if a.restore_pending:print(json.dumps(restore_pending(),indent=2));return0
    if a.install_task:print(json.dumps(install_task(),indent=2));return0
    serve();return0
if __name__=='__main__':raise SystemExit(main())
