#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import browser_roots_v7 as br
import reboot_supervisor as legacy

VERSION='0.7.0'
CHRONICLE='http://127.0.0.1:17376'
ROOT=legacy.ROOT
PENDING=legacy.PENDING
BRIDGE_SOURCE=legacy.BRIDGE_SOURCE
CDP_HELPER=legacy.CDP_HELPER


def http_json(url,timeout=3):
    with urllib.request.urlopen(url,timeout=timeout) as response:return json.loads(response.read().decode())

def ensure_chronicle_server():
    try:return bool(http_json(CHRONICLE+'/health',1).get('ok'))
    except Exception:pass
    script=Path(__file__).with_name('chronicle_v7.py')
    flags=(subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS) if os.name=='nt' else 0
    subprocess.Popen([sys.executable,str(script)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,start_new_session=(os.name!='nt'))
    end=time.time()+5
    while time.time()<end:
        try:
            if http_json(CHRONICLE+'/health',.5).get('ok'):return True
        except Exception:time.sleep(.1)
    return False

def latest():return http_json(CHRONICLE+'/latest',3).get('latest',{}) if ensure_chronicle_server() else {}

def roots_with_chronicle():
    result=[]
    for root in br.discover_roots():
        record=dict(root)
        if br.extension_record(root):
            try:record['chronicle']=br.ensure_chronicle(root,BRIDGE_SOURCE,CHRONICLE,12)
            except Exception as exc:record['chronicle']={'ok':False,'reason':repr(exc)}
        else:record['chronicle']={'ok':False,'reason':'extension-not-installed'}
        result.append(record)
    return result

def flush_active(roots):
    results=[]
    for root in roots:
        if not (root.get('chronicle') or{}).get('ok'):continue
        try:results.append({'rootId':root['rootId'],'ok':True,'result':br.chronicle_rpc(root,'flush_active',{},20000)})
        except Exception as exc:results.append({'rootId':root['rootId'],'ok':False,'error':repr(exc)})
    return results

def checkpoint_rows(values=None):
    now=time.time();values=values or latest();rows=[]
    for key,value in values.items():
        row=dict(value);row['key']=key;row['ageSeconds']=round(now-float(value.get('serverTs') or value.get('ts',0)/1000 or now),1);rows.append(row)
    return rows

def active_work(rows):
    return [row for row in rows if bool((row.get('state') or{}).get('streaming') or (row.get('state') or{}).get('pendingAction'))]

def inventory(auto_bridge=True):
    roots=roots_with_chronicle() if auto_bridge else br.discover_roots();flush=flush_active(roots) if auto_bridge else[]
    if flush:time.sleep(.4)
    rows=checkpoint_rows();work=active_work(rows)
    return{
        'schema':'TF_REBOOT_INVENTORY/7','version':VERSION,'capturedAt':time.time(),
        'roots':roots,'tabs':rows,'chronicleFlush':flush,
        'activeWorkKeys':[row['key'] for row in work],
        'deferredKeys':[row['key'] for row in rows if row not in work],
        'restoreModel':'persistent-browser-profile + rolling-checkpoint + post-boot reconciliation',
        'safeForReboot':not work
    }

def request_active_handoffs(inv):
    wanted=set(inv.get('activeWorkKeys') or[]);results=[]
    if not wanted:return results
    # v6 is used only for the small active delta, never as a prerequisite for historical tabs.
    try:live=legacy.inventory(auto_bridge=True)
    except Exception as exc:return[{'ok':False,'error':'active-live-inventory:'+repr(exc)}]
    live['tabs']=[tab for tab in live.get('tabs',[]) if tab.get('key') in wanted]
    return legacy.request_handoffs(live)

def prepare_reboot():
    before=inventory(True);handoffs=request_active_handoffs(before)
    time.sleep(.5);after=inventory(True)
    unresolved=active_work(after.get('tabs') or[])
    failed=[item for item in handoffs if not item.get('ok')]
    safe=not unresolved and not failed
    manifest={**after,'id':time.strftime('%Y%m%d-%H%M%S'),'reason':'v7-rolling-prepare','handoffs':handoffs,'unresolvedActiveKeys':[r['key'] for r in unresolved],'safeForReboot':safe,'preparedAt':time.time()}
    legacy.atomic_json(ROOT/'snapshots'/f"{manifest['id']}-v7.json",manifest)
    legacy.atomic_json(PENDING,{'status':'prepared' if safe else'blocked','preparedAt':time.time(),'snapshot':manifest,'restoreAttempts':0,'policy':'v7-rolling'})
    legacy.log('prepare.v7',safe=safe,checkpoints=len(manifest['tabs']),active=len(unresolved),handoffFailures=len(failed))
    return manifest

def ghost_low_priority(threshold=40,mode='discard'):
    roots=roots_with_chronicle();by_client={r.get('chronicleClient'):r for r in roots};prefs=legacy.preferences().get('tabs',{});results=[]
    for row in checkpoint_rows():
        priority=int((prefs.get(row['key']) or{}).get('priority',50));state=row.get('state') or{}
        if priority>=threshold or state.get('streaming') or state.get('pendingAction'):continue
        root=by_client.get(row.get('client'))
        if not root:continue
        try:results.append({'key':row['key'],'priority':priority,'result':br.chronicle_rpc(root,'ghost',{'tabId':row['tabId'],'mode':mode},20000)})
        except Exception as exc:results.append({'key':row['key'],'priority':priority,'error':repr(exc)})
    return{'threshold':threshold,'mode':mode,'results':results}

def restore_pending():
    pending=legacy.load_json(PENDING,{})
    if pending.get('status') not in ('rebooting','restoring'):return{'skipped':True,'status':pending.get('status')}
    pending['status']='restoring';pending['restoreAttempts']=int(pending.get('restoreAttempts',0))+1;legacy.atomic_json(PENDING,pending)
    saved=pending.get('snapshot') or{};current={r['rootId']:r for r in br.discover_roots()};results=[]
    for root in saved.get('roots') or[]:
        if root['rootId'] not in current:
            try:legacy.launch_saved_root(root);results.append({'rootId':root['rootId'],'launched':True})
            except Exception as exc:results.append({'rootId':root['rootId'],'launched':False,'error':repr(exc)})
    time.sleep(4);roots=roots_with_chronicle();flush=flush_active(roots)
    # Chrome restores tab/session/profile state; chronicle now reconciles what actually came back.
    legacy.atomic_json(PENDING,{**pending,'status':'restored','restoredAt':time.time(),'postBootFlush':flush})
    legacy.log('restore.v7',roots=len(roots),flush=len(flush))
    return{'restored':True,'roots':len(roots),'flush':flush,'launches':results}
