#!/usr/bin/env python3
from __future__ import annotations

import json, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SERVER=ROOT/'reboot-manager'/'browser_bridge.py'
PORT=18375
BASE=f'http://127.0.0.1:{PORT}'
CLIENT='test-profile'

def post(path,obj,timeout=10):
    req=urllib.request.Request(BASE+path,data=json.dumps(obj).encode(),headers={'content-type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
def get(path,timeout=10):
    with urllib.request.urlopen(BASE+path,timeout=timeout) as r:return json.loads(r.read().decode())

def wait_health():
    end=time.time()+10
    while time.time()<end:
        try:
            if get('/api/health',1).get('ok'):return
        except Exception:time.sleep(.1)
    raise RuntimeError('bridge server did not become healthy')

def fake_browser(stop):
    post('/api/hello',{'client':CLIENT,'extensionPage':True,'runtimeId':'test-extension','bridgeVersion':'test'})
    while not stop.is_set():
        try: item=get('/api/next?client='+urllib.parse.quote(CLIENT)+'&wait=1',3)
        except Exception: continue
        cmd=item.get('command')
        if not cmd:continue
        message=cmd.get('message') or {}
        result={'ok':True,'value':{'echo':message,'browserClient':CLIENT}}
        post('/api/result',{'client':CLIENT,'id':cmd['id'],'result':result})

proc=subprocess.Popen([sys.executable,str(SERVER),'--port',str(PORT)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
stop=threading.Event()
try:
    wait_health()
    thread=threading.Thread(target=fake_browser,args=(stop,),daemon=True);thread.start()
    end=time.time()+5
    while time.time()<end:
        clients=get('/api/clients').get('clients',{})
        if CLIENT in clients:break
        time.sleep(.1)
    else:raise RuntimeError('fake browser not registered')
    result=post('/api/rpc',{'client':CLIENT,'message':{'op':'inventory','payload':{'probe':1}},'timeoutMs':5000},10)
    assert result['ok'] is True
    assert result['value']['echo']['op']=='inventory'
    assert result['value']['echo']['payload']['probe']==1
    print(json.dumps({'PASS':True,'client':CLIENT,'result':result['value']},indent=2))
finally:
    stop.set();proc.terminate()
    try:proc.wait(5)
    except subprocess.TimeoutExpired:proc.kill()
