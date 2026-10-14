#!/usr/bin/env python3
"""Install persistent WatchThese source-observation timer on i9ES."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
UNIT=Path.home()/'.config/systemd/user'
UNIT.mkdir(parents=True,exist_ok=True)
SERVICE='tf-watchthese-monitor.service'
TIMER='tf-watchthese-monitor.timer'
s='[Unit]\nDescription=WatchThese daily source drift sensor\n[Service]\nType=oneshot\nWorkingDirectory='+str(ROOT)+'\nExecStart=/usr/bin/python3 '+str(ROOT/'tools/watchthese_monitor.py')+'\n'
t='[Unit]\nDescription=WatchThese daily source observation\n[Timer]\nOnCalendar=daily\nPersistent=true\nUnit='+SERVICE+'\n[Install]\nWantedBy=timers.target\n'
(UNIT/SERVICE).write_text(s,encoding='utf-8')
(UNIT/TIMER).write_text(t,encoding='utf-8')
for args in (['daemon-reload'],['enable','--now',TIMER]):
 subprocess.run(['systemctl','--user',*args],check=True,timeout=20)
print('DAILY_TIMER_INSTALLED',TIMER)
