#!/usr/bin/env python3
import importlib.util, json, os, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
MANAGER=HERE.parent/'reboot-manager'/'tf_reboot_manager.py'
os.environ['TF_REBOOT_STATE']=tempfile.mkdtemp(prefix='tf-reboot-test-')
spec=importlib.util.spec_from_file_location('tf_reboot_manager',MANAGER)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

assert mod.self_test()['PASS']
assert mod.project_key({'state':{'projectId':'g-p-test'}})=='project:g-p-test'
assert mod.project_key({'state':{'conversationId':'c-test'}})=='conversation:c-test'
assert mod.CHAT_RE.match('https://chatgpt.com/c/abc')
assert not mod.CHAT_RE.match('https://example.com/')

sample={'id':'x','url':'https://chatgpt.com/c/abc','state':{'conversationId':'abc','branchSignature':'abc:u:a:','title':'Project'}}
key1=mod.tab_key(9448,sample); key2=mod.tab_key(9448,sample)
assert key1==key2 and len(key1)==20

prefs={'tabs':{key1:{'priority':75,'paused':True}}}; mod.save_preferences(prefs)
assert mod.preferences()==prefs

print(json.dumps({'PASS':True,'manager':mod.VERSION,'tabKey':key1,'root':str(mod.ROOT)},indent=2))
