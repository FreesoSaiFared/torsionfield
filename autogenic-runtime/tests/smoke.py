#!/usr/bin/env python3
import json, os, tempfile, urllib.request
BASE=os.environ.get('TF_RESIDENT_URL','http://127.0.0.1:17373')
TOKEN=os.environ['TF_RESIDENT_TOKEN']

def request(path,payload=None,auth=True):
    data=None if payload is None else json.dumps(payload).encode()
    headers={}
    if auth: headers['Authorization']='Bearer '+TOKEN
    if data: headers['Content-Type']='application/json'
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req,timeout=10) as r: return json.loads(r.read())

health=request('/v1/health',auth=False)
assert health['ok']
probe=request('/v1/exec',{'argv':['python3','-c','print(40+2)']})
assert probe['result']['returncode']==0 and probe['result']['stdout'].strip()=='42'
path=os.path.join(tempfile.gettempdir(),'tf-resident-smoke.txt')
request('/v1/fs/write',{'path':path,'text':'machine-control-ok'})
read=request('/v1/fs/read',{'path':path})
assert read['result']['text']=='machine-control-ok'
print(json.dumps({'PASS':True,'health':health,'exec':probe['result'],'file':read['result']},indent=2))
