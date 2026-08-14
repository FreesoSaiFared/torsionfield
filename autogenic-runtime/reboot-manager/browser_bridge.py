#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, threading, time, uuid
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST='127.0.0.1'; PORT=17375; VERSION='0.1.0'
lock=threading.RLock(); cv=threading.Condition(lock)
clients={}; queues=defaultdict(deque); pending={}

PAGE=r'''<!doctype html><meta charset="utf-8"><title>TF Browser Bridge</title>
<style>body{font:13px system-ui;background:#111;color:#eee;margin:20px}code,pre{font:12px ui-monospace,monospace}b.ok{color:#7fff9a}b.bad{color:#ff8a8a}</style>
<h2>Torsionfield Browser Bridge</h2><p id=s>starting…</p><pre id=d></pre>
<script>
const q=new URLSearchParams(location.search), client=q.get('client')||('browser-'+crypto.randomUUID());
let seq=0;
function rpc(message,timeout=30000){return new Promise((resolve,reject)=>{const id='b'+(++seq)+'-'+crypto.randomUUID();const timer=setTimeout(()=>{document.removeEventListener('tf-fixture-result',on);reject(Error('extension-rpc-timeout'))},timeout);function on(ev){let x;try{x=JSON.parse(ev.detail)}catch{return}if(x.id!==id)return;clearTimeout(timer);document.removeEventListener('tf-fixture-result',on);if(x.result?.ok===false)reject(Error(x.result.error||'extension-error'));else resolve(x.result?.value??x.result)}document.addEventListener('tf-fixture-result',on);window.postMessage({type:'tf-fixture',id,message},'*')})}
async function post(path,obj){const r=await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(obj)});return r.json()}
async function hello(){try{const state=await rpc({type:'tf.getState'},8000);await post('/api/hello',{client,href:location.href,userAgent:navigator.userAgent,state});document.querySelector('#s').innerHTML='<b class=ok>extension bridge live</b> · '+client;document.querySelector('#d').textContent=JSON.stringify({paused:state.paused,boundUrl:state.boundUrl,boundTabId:state.boundTabId,extensionVersion:state.extensionVersion},null,2);return true}catch(e){await post('/api/hello',{client,href:location.href,userAgent:navigator.userAgent,error:String(e)});document.querySelector('#s').innerHTML='<b class=bad>extension bridge unavailable</b> · '+String(e);return false}}
async function loop(){await hello();for(;;){try{const r=await fetch('/api/next?client='+encodeURIComponent(client)+'&wait=20');const j=await r.json();if(j.command){let result;try{result={ok:true,value:await rpc(j.command.message,Number(j.command.timeoutMs||30000))}}catch(e){result={ok:false,error:String(e)}}await post('/api/result',{client,id:j.command.id,result});}}catch(e){}await new Promise(r=>setTimeout(r,250))}}
loop();
</script>'''

def jread(h):
    n=int(h.headers.get('content-length','0') or 0); return json.loads((h.rfile.read(n) if n else b'{}').decode())
def jsend(h,status,obj):
    data=json.dumps(obj,ensure_ascii=False).encode();h.send_response(status);h.send_header('content-type','application/json; charset=utf-8');h.send_header('content-length',str(len(data)));h.end_headers();h.wfile.write(data)
def snapshot_clients():
    with lock:return {k:{**v,'ageSeconds':round(time.time()-v.get('lastSeen',0),2),'queued':len(queues[k])} for k,v in clients.items()}
def enqueue(client,message,timeout_ms=30000):
    rid=str(uuid.uuid4()); command={'id':rid,'message':message,'timeoutMs':timeout_ms,'createdAt':time.time()}
    with cv: queues[client].append(command); pending[rid]={'event':threading.Event(),'result':None,'client':client};cv.notify_all()
    return rid,pending[rid]['event']
def rpc(client,message,timeout_ms=30000):
    with lock:
        info=clients.get(client)
        if not info or time.time()-info.get('lastSeen',0)>35: raise RuntimeError(f'bridge-client-unavailable:{client}')
    rid,event=enqueue(client,message,timeout_ms)
    if not event.wait(timeout_ms/1000+5):
        with lock: pending.pop(rid,None)
        raise TimeoutError(f'bridge-command-timeout:{rid}')
    with lock: rec=pending.pop(rid,None)
    result=(rec or {}).get('result') or {'ok':False,'error':'result-missing'}
    if not result.get('ok'): raise RuntimeError(result.get('error') or 'extension-rpc-failed')
    return result.get('value')

class H(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        u=urlparse(self.path); p=u.path; q=parse_qs(u.query)
        if p=='/':
            body=PAGE.encode();self.send_response(200);self.send_header('content-type','text/html; charset=utf-8');self.send_header('content-length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if p=='/api/health': return jsend(self,200,{'ok':True,'version':VERSION,'clients':snapshot_clients()})
        if p=='/api/clients': return jsend(self,200,{'clients':snapshot_clients()})
        if p=='/api/next':
            client=(q.get('client') or [''])[0]; wait=min(25,max(0,float((q.get('wait') or ['20'])[0]))); deadline=time.time()+wait
            with cv:
                clients.setdefault(client,{'client':client})['lastSeen']=time.time()
                while not queues[client] and time.time()<deadline: cv.wait(min(1,deadline-time.time()));clients[client]['lastSeen']=time.time()
                cmd=queues[client].popleft() if queues[client] else None
            return jsend(self,200,{'command':cmd})
        return jsend(self,404,{'error':'not found'})
    def do_POST(self):
        p=urlparse(self.path).path
        try: body=jread(self)
        except Exception as e:return jsend(self,400,{'error':str(e)})
        if p=='/api/hello':
            client=str(body.get('client') or '')
            with lock: clients[client]={**body,'lastSeen':time.time()}
            return jsend(self,200,{'ok':True})
        if p=='/api/result':
            rid=str(body.get('id') or '')
            with lock:
                rec=pending.get(rid)
                if rec: rec['result']=body.get('result') or {};rec['event'].set()
                if body.get('client') in clients: clients[body['client']]['lastSeen']=time.time()
            return jsend(self,200,{'ok':bool(rec)})
        if p=='/api/rpc':
            try:
                value=rpc(str(body['client']),body.get('message') or {},int(body.get('timeoutMs') or 30000));return jsend(self,200,{'ok':True,'value':value})
            except Exception as e:return jsend(self,503,{'ok':False,'error':f'{type(e).__name__}: {e}'})
        return jsend(self,404,{'error':'not found'})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=PORT);a=ap.parse_args();print(f'TF Browser Bridge {VERSION} http://{HOST}:{a.port}/?tf-fixture=1&client=profile',flush=True);ThreadingHTTPServer((HOST,a.port),H).serve_forever(.25)
if __name__=='__main__':main()
