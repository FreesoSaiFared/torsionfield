#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,subprocess,sys
from pathlib import Path
import browser_roots_v6 as roots_v6
import reboot_supervisor as core
core.br=roots_v6
import reboot_console as console
console.core=core
VERSION='0.6.0'

def install_task():
    if os.name!='nt':return{'installed':False,'reason':'Windows-only'}
    task='Torsionfield Reboot Supervisor';command=f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --serve'
    cp=subprocess.run(['schtasks','/Create','/TN',task,'/TR',command,'/SC','ONLOGON','/RL','HIGHEST','/F'],text=True,capture_output=True)
    if cp.returncode:raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return{'installed':True,'task':task,'command':command}
def main():
    p=argparse.ArgumentParser();
    for flag in ('serve','inventory','snapshot','prepare','reboot-if-safe','restore-pending','install-task','self-test'):p.add_argument('--'+flag,action='store_true')
    a=p.parse_args();core.ensure_bridge_server()
    if a.self_test:
        r=console.self_test();r.update({'v6Binding':True,'version':VERSION});print(json.dumps(r,indent=2));return 0
    if a.inventory:print(json.dumps(core.inventory(True),indent=2,ensure_ascii=False));return 0
    if a.snapshot:print(json.dumps(core.snapshot('v6-cli'),indent=2,ensure_ascii=False));return 0
    if a.prepare:print(json.dumps(core.prepare_reboot(),indent=2,ensure_ascii=False));return 0
    if a.reboot_if_safe:print(json.dumps(core.schedule_reboot(),indent=2,ensure_ascii=False));return 0
    if a.restore_pending:print(json.dumps(core.restore_pending(),indent=2,ensure_ascii=False));return 0
    if a.install_task:print(json.dumps(install_task(),indent=2));return 0
    console.serve();return 0
if __name__=='__main__':raise SystemExit(main())
