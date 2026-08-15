#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
import urllib.parse
from pathlib import Path

import browser_roots_v6 as base

VERSION='0.7.0'
CHRONICLE_SUFFIX='-chronicle-v7'
CHRONICLE_FILES=('chronicle_v7.html','chronicle_v7.js','chronicle_v7_focus_patch.js')


def discover_roots():
    roots=base.discover_roots()
    for root in roots:root['chronicleClient']=root['rootId']+CHRONICLE_SUFFIX
    return roots


def ensure_chronicle(root,source_dir,chronicle='http://127.0.0.1:17376',timeout=12):
    client=root.get('chronicleClient') or root['rootId']+CHRONICLE_SUFFIX
    if base.bridge_healthy(client):return{'ok':True,'already':True,'client':client}
    ext=base.extension_record(root)
    if not ext or not ext.get('path'):return{'ok':False,'reason':'torsionfield-extension-not-installed','client':client}
    src=Path(source_dir);dst=Path(ext['path'])
    for name in CHRONICLE_FILES:(dst/name).write_bytes((src/name).read_bytes())
    query=urllib.parse.urlencode({'client':client,'chronicle':chronicle,'rpc':base.bridge_base()})
    url=f"chrome-extension://{ext['id']}/chronicle_v7.html?{query}"
    args=[root['executable']]
    if root.get('explicitUserDataDir'):args.append(f"--user-data-dir={root['userDataDir']}")
    if root.get('profileDirectory'):args.append(f"--profile-directory={root['profileDirectory']}")
    args.append(url);subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    end=time.time()+timeout
    while time.time()<end:
        if base.bridge_healthy(client):return{'ok':True,'opened':True,'client':client,'url':url}
        time.sleep(.2)
    return{'ok':False,'reason':'chronicle-page-did-not-register','client':client,'url':url}


def chronicle_rpc(root,op,payload=None,timeout_ms=30000):
    client=root.get('chronicleClient') or root['rootId']+CHRONICLE_SUFFIX
    return base.bridge_rpc(client,op,payload or{},timeout_ms)

# Preserve the proven v6 live-control surface for operations that actually need it.
bridge_base=base.bridge_base
bridge_healthy=base.bridge_healthy
bridge_rpc=base.bridge_rpc
extension_record=base.extension_record
root_inventory=base.root_inventory
scan_session_urls=base.scan_session_urls
cdp_alive=base.cdp_alive
node_call=base.node_call
ensure_bridge=base.ensure_bridge
