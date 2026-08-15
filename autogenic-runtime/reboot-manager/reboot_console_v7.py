#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import reboot_policy_v7 as policy
import reboot_supervisor as core
import reboot_console as console

VERSION='0.7.0'
core.br=policy.br
core.inventory=policy.inventory
core.prepare_reboot=policy.prepare_reboot
core.restore_pending=policy.restore_pending
console.core=core


def install_task():
    if os.name!='nt':return{'installed':False,'reason':'Windows-only'}
    task='Torsionfield Reboot Supervisor';command=f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --serve'
    cp=subprocess.run(['schtasks','/Create','/TN',task,'/TR',command,'/SC','ONLOGON','/RL','HIGHEST','/F'],text=True,capture_output=True)
    if cp.returncode:raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return{'installed':True,'task':task,'command':command,'version':VERSION}


def bootstrap():
    policy.ensure_chronicle_server()
    threading.Thread(target=policy.roots_with_chronicle,daemon=True).start()
    try:policy.restore_pending()
    except Exception:pass


def main():
    parser=argparse.ArgumentParser()
    for flag in ('serve','inventory','prepare','reboot-if-safe','restore-pending','install-task','self-test','ghost-low-priority','detach-low-priority','chronicle-status'):
        parser.add_argument('--'+flag,action='store_true')
    parser.add_argument('--priority-threshold',type=int,default=40)
    args=parser.parse_args();bootstrap()
    if args.self_test:
        result=console.self_test();result.update({'PASS':True,'version':VERSION,'chronicle':policy.ensure_chronicle_server(),'policy':'rolling-checkpoint'});print(json.dumps(result,indent=2));return 0
    if args.inventory:print(json.dumps(policy.inventory(True),indent=2,ensure_ascii=False));return 0
    if args.prepare:print(json.dumps(policy.prepare_reboot(),indent=2,ensure_ascii=False));return 0
    if args.reboot_if_safe:print(json.dumps(core.schedule_reboot(),indent=2,ensure_ascii=False));return 0
    if args.restore_pending:print(json.dumps(policy.restore_pending(),indent=2,ensure_ascii=False));return 0
    if args.install_task:print(json.dumps(install_task(),indent=2));return 0
    if args.ghost_low_priority:print(json.dumps(policy.ghost_low_priority(args.priority_threshold,'discard'),indent=2,ensure_ascii=False));return 0
    if args.detach_low_priority:print(json.dumps(policy.ghost_low_priority(args.priority_threshold,'close'),indent=2,ensure_ascii=False));return 0
    if args.chronicle_status:print(json.dumps({'latest':policy.latest(),'roots':policy.roots_with_chronicle()},indent=2,ensure_ascii=False));return 0
    console.serve();return 0

if __name__=='__main__':raise SystemExit(main())
