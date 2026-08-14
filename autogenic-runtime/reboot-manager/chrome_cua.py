#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, ctypes, json, os, re, time
from ctypes import wintypes

if os.name != "nt":
    raise SystemExit("chrome_cua.py is Windows-only")

from pywinauto.keyboard import send_keys
import win32clipboard

VERSION = "0.2.0"
CHUNK = 2800
CHAT_RE = re.compile(r"^https://(?:chatgpt\.com|chat\.openai\.com)/", re.I)
user32 = ctypes.windll.user32

STATE_EXPR = r'''(()=>{
const norm=v=>String(v==null?'':v).replace(/\r\n?/g,'\n').trim();
const hash=v=>{let x=2166136261;for(const c of String(v||'')){x^=c.charCodeAt(0);x=Math.imul(x,16777619)}return(x>>>0).toString(16).padStart(8,'0')};
let marker=sessionStorage.getItem('tf.reboot.tab');if(!marker){marker=(crypto.randomUUID?.()||('tf-'+Date.now()+'-'+Math.random()));sessionStorage.setItem('tf.reboot.tab',marker)}
const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
let composer=null;for(const s of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){const a=[...document.querySelectorAll(s)].filter(visible);if(a.length){composer=a.at(-1);break}}
const draft=composer?(typeof composer.value==='string'?composer.value:(composer.innerText||composer.textContent||'')):'';
const nodes=[...document.querySelectorAll('[data-message-author-role]')];
const recent=nodes.slice(-10).map(e=>{const role=e.getAttribute('data-message-author-role')||'';const c=role==='user'?(e.querySelector('[data-testid="collapsible-user-message-content"]')||e):e;const text=norm(c.innerText||c.textContent||'').slice(0,1400);return{role,text,hash:hash(text)}});
const users=recent.filter(x=>x.role==='user'),assistants=recent.filter(x=>x.role==='assistant'),latestUser=users.at(-1)||null,latestAssistant=assistants.at(-1)||null;
const streaming=!!document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]');
const path=location.pathname,conversationId=(path.match(/\/c\/([^/?#]+)/)||[])[1]||'',projectId=(path.match(/\/g\/(g-p-[^/]+)/)||[])[1]||'';
const branchControls=[...document.querySelectorAll('button,[role="button"]')].map(e=>e.getAttribute('aria-label')||'').filter(v=>/branch|previous|next|response/i.test(v)).slice(0,24);
const root=document.documentElement,autogenic={state:root?.dataset?.tfAutogenic||'',version:root?.dataset?.tfAutogenicVersion||'',bridge:root?.dataset?.tfExtensionBridge||'',residentElevated:root?.dataset?.tfResidentElevated||'',lastOp:root?.dataset?.tfAutogenicLastOp||'',lastOpStatus:root?.dataset?.tfAutogenicLastOpStatus||'',loopError:root?.dataset?.tfAutogenicLoopError||''};
return{marker,href:location.href,title:document.title,readyState:document.readyState,visibilityState:document.visibilityState,hidden:document.hidden,scrollY:window.scrollY,scrollHeight:document.documentElement.scrollHeight,conversationId,projectId,draft:norm(draft).slice(0,8000),streaming,status:streaming?'streaming':norm(draft)?'draft':autogenic.loopError?'automation-error':'idle',turnCount:nodes.length,recent,latestUser,latestAssistant,branchControls,branchSignature:[conversationId,latestUser?.hash||'',latestAssistant?.hash||'',branchControls.join('|')].join(':'),autogenic,pendingAction:!!(latestAssistant&&/\[\[TF_ACTION\/1/.test(latestAssistant.text)&&!document.querySelector('[data-tf-autogenic-executed="1"]')),capturedAt:Date.now()}
})()'''


def window_text(hwnd):
    n=user32.GetWindowTextLengthW(hwnd)
    b=ctypes.create_unicode_buffer(n+1)
    user32.GetWindowTextW(hwnd,b,n+1)
    return b.value

def window_pid(hwnd):
    pid=wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid)); return int(pid.value)

def chrome_windows(pids=None):
    wanted=set(int(x) for x in (pids or [])); out=[]
    CB=ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    def cb(hwnd,lparam):
        if not user32.IsWindowVisible(hwnd): return True
        title=window_text(hwnd); pid=window_pid(hwnd)
        if title and (not wanted or pid in wanted) and (title.endswith('Google Chrome') or title.endswith('Chromium') or title.endswith('Microsoft Edge')):
            out.append({'hwnd':int(hwnd),'pid':pid,'title':title})
        return True
    user32.EnumWindows(CB(cb),0)
    return out

def raw_title(hwnd):
    value=window_text(hwnd)
    for suffix in (' - Google Chrome',' - Chromium',' - Microsoft Edge'):
        if value.endswith(suffix): return value[:-len(suffix)]
    return value

def focus(hwnd):
    user32.ShowWindow(hwnd,9); user32.SetForegroundWindow(hwnd); time.sleep(.18)
    if int(user32.GetForegroundWindow())!=int(hwnd):
        send_keys('%'); user32.SetForegroundWindow(hwnd); time.sleep(.18)
    return int(user32.GetForegroundWindow())==int(hwnd)

def clipboard_text():
    try:
        win32clipboard.OpenClipboard()
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) else None
    except Exception: return None
    finally:
        try: win32clipboard.CloseClipboard()
        except Exception: pass

def set_clipboard_text(value):
    for _ in range(30):
        try:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardText(str(value)); win32clipboard.CloseClipboard(); return
        except Exception:
            try: win32clipboard.CloseClipboard()
            except Exception: pass
            time.sleep(.03)
    raise RuntimeError('clipboard unavailable')

def javascript(hwnd, body, wait=.65):
    if not focus(hwnd): raise RuntimeError('could not focus Chrome window')
    send_keys('^l'); send_keys('javascript:',with_spaces=True); set_clipboard_text(body); send_keys('^v{ENTER}'); time.sleep(wait)

def eval_json(hwnd, expression, wait=.75):
    wrapper=("(()=>{try{const value=("+expression+");const encoded=btoa(unescape(encodeURIComponent(JSON.stringify({ok:true,value}))));window.__tfRebootPayload=encoded;document.title='TFJ:'+Math.ceil(encoded.length/"+str(CHUNK)+")+':'+encoded.slice(0,"+str(CHUNK)+");}catch(error){const encoded=btoa(unescape(encodeURIComponent(JSON.stringify({ok:false,error:String(error?.stack||error)}))));window.__tfRebootPayload=encoded;document.title='TFJ:'+Math.ceil(encoded.length/"+str(CHUNK)+")+':'+encoded.slice(0,"+str(CHUNK)+");}void 0})()")
    javascript(hwnd,wrapper,wait)
    first=raw_title(hwnd)
    if not first.startswith('TFJ:'): raise RuntimeError('state-title-not-observed')
    count_text,chunk0=first[4:].split(':',1); count=int(count_text); chunks=[chunk0]
    for index in range(1,count):
        javascript(hwnd,f"document.title='TFC:{index}:'+window.__tfRebootPayload.slice({index*CHUNK},{(index+1)*CHUNK});void 0",.48)
        chunk=raw_title(hwnd); prefix=f'TFC:{index}:'
        if not chunk.startswith(prefix): raise RuntimeError(f'chunk-not-observed:{index}')
        chunks.append(chunk[len(prefix):])
    data=json.loads(base64.b64decode(''.join(chunks)).decode('utf-8'))
    if not data.get('ok'): raise RuntimeError(data.get('error') or 'page evaluation failed')
    return data.get('value')
def restore_page_title(hwnd,title):
    javascript(hwnd,'delete window.__tfRebootPayload;document.title='+json.dumps(str(title))+';void 0',.65)

def capture_current(hwnd):
    original=raw_title(hwnd)
    state=eval_json(hwnd,STATE_EXPR)
    restore_page_title(hwnd,state.get('title') or original)
    state['chatgpt']=bool(CHAT_RE.match(state.get('href') or ''))
    return state

def inventory_window(hwnd,max_tabs=80):
    original_clip=clipboard_text(); first_marker=None; tabs=[]; errors=[]
    try:
        for index in range(max_tabs):
            try: state=capture_current(hwnd)
            except Exception as exc: errors.append({'index':index,'error':repr(exc),'windowTitle':window_text(hwnd)}); break
            marker=state.get('marker')
            if first_marker is None: first_marker=marker
            elif marker==first_marker: break
            state['index']=index; tabs.append(state)
            send_keys('^{TAB}'); time.sleep(.28)
        else: errors.append({'error':f'max-tabs-reached:{max_tabs}'})
    finally:
        if original_clip is not None:
            try: set_clipboard_text(original_clip)
            except Exception: pass
    return {'hwnd':int(hwnd),'pid':window_pid(hwnd),'tabs':tabs,'errors':errors,'windowTitle':window_text(hwnd)}
def inventory(pids=None,max_tabs=80):
    out=[]
    for win in chrome_windows(pids):
        try: out.append(inventory_window(win['hwnd'],max_tabs))
        except Exception as exc: out.append({**win,'tabs':[],'errors':[{'error':repr(exc)}]})
    return {'schema':'TF_CUA_CHROME/2','version':VERSION,'capturedAt':time.time(),'windows':out}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pid',action='append',type=int);ap.add_argument('--hwnd',type=int);ap.add_argument('--max-tabs',type=int,default=80);ap.add_argument('--current',action='store_true');a=ap.parse_args()
    if a.current:
        if not a.hwnd: raise SystemExit('--current requires --hwnd')
        print(json.dumps(capture_current(a.hwnd),ensure_ascii=False,indent=2)); return
    print(json.dumps(inventory(a.pid,a.max_tabs),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
