#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, ctypes, json, os, re, time
from ctypes import wintypes

if os.name != "nt":
    raise SystemExit("cua_windows.py is Windows-only")

from pywinauto.keyboard import send_keys
import win32clipboard

VERSION = "0.1.0"
CHAT_RE = re.compile(r"^https://(?:chatgpt\.com|chat\.openai\.com)/", re.I)
user32 = ctypes.windll.user32

STATE_JS = r'''(()=>{
const n=v=>String(v==null?'':v).replace(/\r\n?/g,'\n').trim();
const h=v=>{let x=2166136261;for(const c of String(v||'')){x^=c.charCodeAt(0);x=Math.imul(x,16777619)}return (x>>>0).toString(16).padStart(8,'0')};
let marker=sessionStorage.getItem('tf.reboot.tab');if(!marker){marker=(crypto.randomUUID?.()||('tf-'+Date.now()+'-'+Math.random()));sessionStorage.setItem('tf.reboot.tab',marker)}
const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
let composer=null;for(const s of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){const a=[...document.querySelectorAll(s)].filter(visible);if(a.length){composer=a.at(-1);break}}
const draft=composer?(typeof composer.value==='string'?composer.value:(composer.innerText||composer.textContent||'')):'';
const turns=[...document.querySelectorAll('[data-message-author-role]')].slice(-8).map(e=>{const r=e.getAttribute('data-message-author-role')||'';const c=r==='user'?(e.querySelector('[data-testid="collapsible-user-message-content"]')||e):e;const t=n(c.innerText||c.textContent||'').slice(0,1800);return{r,t,h:h(t)}});
const users=turns.filter(x=>x.r==='user'), assistants=turns.filter(x=>x.r==='assistant'), lu=users.at(-1)||null, la=assistants.at(-1)||null;
const streaming=!!document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]');
const path=location.pathname, conv=(path.match(/\/c\/([^/?#]+)/)||[])[1]||'', project=(path.match(/\/g\/(g-p-[^/]+)/)||[])[1]||'';
const branch=[...document.querySelectorAll('button,[role="button"]')].map(e=>e.getAttribute('aria-label')||'').filter(v=>/branch|previous|next|response/i.test(v)).slice(0,24);
const root=document.documentElement, autogenic={state:root?.dataset?.tfAutogenic||'',version:root?.dataset?.tfAutogenicVersion||'',bridge:root?.dataset?.tfExtensionBridge||'',elevated:root?.dataset?.tfResidentElevated||'',lastOp:root?.dataset?.tfAutogenicLastOp||'',lastOpStatus:root?.dataset?.tfAutogenicLastOpStatus||'',loopError:root?.dataset?.tfAutogenicLoopError||''};
const state={marker,href:location.href,title:document.title,conversationId:conv,projectId:project,draft:n(draft).slice(0,8000),streaming,turnCount:document.querySelectorAll('[data-message-author-role]').length,turns,latestUser:lu,latestAssistant:la,branchControls:branch,branchSignature:[conv,lu?.h||'',la?.h||'',branch.join('|')].join(':'),autogenic,pendingAction:!!(la&&/\[\[TF_ACTION\/1/.test(la.t)&&!document.querySelector('[data-tf-autogenic-executed="1"]')),scrollY:window.scrollY,visibility:document.visibilityState,hidden:document.hidden,capturedAt:Date.now()};
document.title='TFSTATE:'+btoa(unescape(encodeURIComponent(JSON.stringify(state))));void 0})()'''


def window_text(hwnd):
    n=user32.GetWindowTextLengthW(hwnd); b=ctypes.create_unicode_buffer(n+1); user32.GetWindowTextW(hwnd,b,n+1); return b.value

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
    user32.EnumWindows(CB(cb),0); return out

def focus(hwnd):
    user32.ShowWindow(hwnd,9); user32.SetForegroundWindow(hwnd); time.sleep(.18)
    if int(user32.GetForegroundWindow())!=int(hwnd):
        send_keys('%'); user32.SetForegroundWindow(hwnd); time.sleep(.18)
    return int(user32.GetForegroundWindow())==int(hwnd)

def clipboard_text():
    try:
        win32clipboard.OpenClipboard(); return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) else None
    except Exception: return None
    finally:
        try: win32clipboard.CloseClipboard()
        except Exception: pass

def set_clipboard_text(value):
    for _ in range(20):
        try:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardText(str(value)); win32clipboard.CloseClipboard(); return
        except Exception:
            try: win32clipboard.CloseClipboard()
            except Exception: pass
            time.sleep(.03)
    raise RuntimeError('clipboard unavailable')

def js_url(hwnd, body, wait=.28):
    if not focus(hwnd): raise RuntimeError('could not focus Chrome window')
    send_keys('^l'); send_keys('javascript:',with_spaces=True); set_clipboard_text(body); send_keys('^v{ENTER}'); time.sleep(wait)

def parse_state_title(title):
    raw=title
    for suffix in (' - Google Chrome',' - Chromium',' - Microsoft Edge'):
        if raw.endswith(suffix): raw=raw[:-len(suffix)]
    if not raw.startswith('TFSTATE:'): return None
    try:
        data=base64.b64decode(raw[len('TFSTATE:'):]); return json.loads(data.decode('utf-8'))
    except Exception as exc: return {'decodeError':repr(exc),'rawLength':len(raw)}
def restore_title(hwnd, title):
    js_url(hwnd, 'document.title='+json.dumps(str(title))+';void 0', .12)

def inventory_window(hwnd, max_tabs=80):
    original_clip=clipboard_text(); first_marker=None; tabs=[]; errors=[]
    try:
        for index in range(max_tabs):
            before=window_text(hwnd)
            try: js_url(hwnd, STATE_JS, .32)
            except Exception as exc: errors.append({'index':index,'phase':'execute','error':repr(exc),'windowTitle':before}); break
            state=parse_state_title(window_text(hwnd))
            if not state or state.get('decodeError'):
                errors.append({'index':index,'phase':'read','error':'state-title-not-observed','windowTitle':window_text(hwnd)}); break
            marker=state.get('marker')
            if first_marker is None: first_marker=marker
            elif marker==first_marker:
                try: restore_title(hwnd,state.get('title') or before.rsplit(' - ',1)[0])
                except Exception: pass
                break
            state['index']=index; state['chatgpt']=bool(CHAT_RE.match(state.get('href') or '')); tabs.append(state)
            try: restore_title(hwnd,state.get('title') or before.rsplit(' - ',1)[0])
            except Exception as exc: errors.append({'index':index,'phase':'restore-title','error':repr(exc)})
            send_keys('^{TAB}'); time.sleep(.22)
        else: errors.append({'phase':'cycle','error':f'max-tabs-reached:{max_tabs}'})
    finally:
        if original_clip is not None:
            try: set_clipboard_text(original_clip)
            except Exception: pass
    return {'hwnd':int(hwnd),'pid':window_pid(hwnd),'windowTitle':window_text(hwnd),'tabs':tabs,'errors':errors}
def inventory(pids=None,max_tabs=80):
    windows=chrome_windows(pids); results=[]
    for w in windows:
        try: results.append(inventory_window(w['hwnd'],max_tabs))
        except Exception as exc: results.append({**w,'tabs':[],'errors':[{'error':repr(exc)}]})
    return {'schema':'TF_CUA_CHROME/1','version':VERSION,'capturedAt':time.time(),'windows':results}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pid',action='append',type=int); ap.add_argument('--max-tabs',type=int,default=80); a=ap.parse_args(); print(json.dumps(inventory(a.pid,a.max_tabs),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
