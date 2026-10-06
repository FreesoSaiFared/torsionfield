#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path

SCHEMA="TORSIONFIELD_CHROMIUM_MESH/1"
def j(x): return json.dumps(x,sort_keys=True,separators=(",",":")).encode()
def h(b): return hashlib.sha256(b).hexdigest()
def hf(p): return h(Path(p).read_bytes())

def build_id(source, deps, tool, sysroot, gn, osname="linux", cpu="x64", patch="pristine"):
    return h(j({"source":source,"deps":deps,"tool":tool,"sysroot":sysroot,"gn":gn,"os":osname,"cpu":cpu,"patch":patch}))

def action(build, argv, inputs, outputs, cwd=".", platform="linux-x64"):
    a={"schema":SCHEMA,"build_id":build,"argv":argv,"inputs":inputs,"outputs":outputs,"cwd":cwd,"platform":platform}
    a["action_digest"]=h(j(a)); return a

def verify_action(a):
    d=dict(a); got=d.pop("action_digest",None)
    if d.get("schema")!=SCHEMA or got!=h(j(d)): raise ValueError("ACTION_DIGEST_MISMATCH")

class CAS:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def p(self,d): return self.root/"sha256"/d[:2]/d[2:]
    def put(self,b):
        d=h(b); p=self.p(d); p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists(): p.write_bytes(b)
        if hf(p)!=d: raise ValueError("CAS_CORRUPT")
        return d
    def get(self,d):
        b=self.p(d).read_bytes()
        if h(b)!=d: raise ValueError("CAS_CORRUPT")
        return b

def safe_extract(tf,dst):
    root=Path(dst).resolve()
    for m in tf.getmembers():
        p=(Path(dst)/m.name).resolve()
        if p!=root and root not in p.parents: raise ValueError("UNSAFE_ARCHIVE")
        if m.issym() or m.islnk(): raise ValueError("ARCHIVE_LINK_FORBIDDEN")
    tf.extractall(dst,filter="data")

def make_bundle(a,cas,out):
    verify_action(a)
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); (r/"manifest.json").write_text(json.dumps(a,sort_keys=True))
        for d in sorted(set(a["inputs"].values())):
            p=r/"blobs"/"sha256"/d[:2]/d[2:]; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(cas.get(d))
        with tarfile.open(out,"w:gz") as tf:
            for p in sorted(r.rglob("*")): tf.add(p,arcname=p.relative_to(r))

def import_blobs(root,cas):
    b=Path(root)/"blobs"/"sha256"
    if not b.exists(): return
    for p in b.glob("*/*"):
        want=p.parent.name+p.name
        if cas.put(p.read_bytes())!=want: raise ValueError("BLOB_HASH_MISMATCH")

def run_bundle(bundle,result,worker,expected_build,worker_root):
    worker_root=Path(worker_root); cas=CAS(worker_root/"cas")
    with tempfile.TemporaryDirectory() as td:
        r=Path(td)
        with tarfile.open(bundle,"r:gz") as tf: safe_extract(tf,r)
        import_blobs(r,cas); a=json.loads((r/"manifest.json").read_text()); verify_action(a)
        if a["build_id"]!=expected_build: raise ValueError("BUILD_ID_MISMATCH")
        s=worker_root/"work"/a["action_digest"]; shutil.rmtree(s,ignore_errors=True); s.mkdir(parents=True)
        for rel,d in a["inputs"].items():
            rp=Path(rel)
            if rp.is_absolute() or ".." in rp.parts: raise ValueError("UNSAFE_INPUT")
            p=s/rp; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(cas.get(d))
        cwd=(s/a["cwd"]).resolve(); cwd.mkdir(parents=True,exist_ok=True)
        cp=subprocess.run(a["argv"],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        outputs={}; missing=[]
        if cp.returncode==0:
            for rel in a["outputs"]:
                p=s/rel
                if p.is_file(): outputs[rel]=cas.put(p.read_bytes())
                else: missing.append(rel)
        res={"schema":SCHEMA,"action_digest":a["action_digest"],"build_id":a["build_id"],"worker_id":worker,"ok":cp.returncode==0 and not missing,"returncode":cp.returncode,"stdout_b64":base64.b64encode(cp.stdout).decode(),"stderr_b64":base64.b64encode(cp.stderr).decode(),"outputs":outputs,"missing":missing}
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); (r/"result.json").write_text(json.dumps(res,sort_keys=True))
        for d in sorted(set(outputs.values())):
            p=r/"blobs"/"sha256"/d[:2]/d[2:]; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(cas.get(d))
        with tarfile.open(result,"w:gz") as tf:
            for p in sorted(r.rglob("*")): tf.add(p,arcname=p.relative_to(r))
    return res

def import_result(path,cas,a):
    with tempfile.TemporaryDirectory() as td:
        r=Path(td)
        with tarfile.open(path,"r:gz") as tf: safe_extract(tf,r)
        import_blobs(r,cas); x=json.loads((r/"result.json").read_text())
    if x["action_digest"]!=a["action_digest"] or x["build_id"]!=a["build_id"]: raise ValueError("RESULT_IDENTITY_MISMATCH")
    for d in x["outputs"].values(): cas.get(d)
    return x

def tool_digest(cxx): return h(Path(cxx).read_bytes()+subprocess.check_output([cxx,"--version"]))

def compile_mesh(root,source_revision,units):
    root=Path(root); root.mkdir(parents=True,exist_ok=True); cas=CAS(root/"coord-cas")
    cxx=shutil.which("clang++") or shutil.which("g++"); assert cxx
    deps=h(j({k:h(v) for k,v in units["headers"].items()})); bid=build_id(source_revision,deps,tool_digest(cxx),h(b"host"),h(b"c++20-O0"))
    objs={}; workers=[]
    for n,(name,src,headers,worker) in enumerate(units["compile"],1):
        inputs={name:cas.put(src)}
        for p in headers: inputs[p]=cas.put(units["headers"][p])
        out=name.rsplit(".",1)[0]+".o"; a=action(bid,[cxx,"-std=c++20","-O0","-g","-I.",name,"-c","-o",out],inputs,[out])
        ab=root/f"a{n}.tgz"; rb=root/f"r{n}.tgz"; make_bundle(a,cas,ab); run_bundle(ab,rb,worker,bid,root/worker); x=import_result(rb,cas,a)
        if not x["ok"]: raise RuntimeError(base64.b64decode(x["stderr_b64"]).decode(errors="replace"))
        objs.update(x["outputs"]); workers.append(worker)
    la=action(bid,[cxx,*objs.keys(),"-o","mesh-bin"],objs,["mesh-bin"]); ab=root/"alink.tgz"; rb=root/"rlink.tgz"
    make_bundle(la,cas,ab); run_bundle(ab,rb,"link-worker",bid,root/"link-worker"); lr=import_result(rb,cas,la)
    if not lr["ok"]: raise RuntimeError(base64.b64decode(lr["stderr_b64"]).decode(errors="replace"))
    exe=root/"mesh-bin"; exe.write_bytes(cas.get(lr["outputs"]["mesh-bin"])); exe.chmod(0o755); cp=subprocess.run([exe],capture_output=True,text=True)
    if cp.returncode or cp.stdout.strip()!="42": raise RuntimeError(f"BAD_FINAL {cp.returncode} {cp.stdout!r}")
    return {"schema":SCHEMA,"result":"PASS","build_id":bid,"source_revision":source_revision,"compile_workers":workers,"link_worker":"link-worker","objects":objs,"final_digest":hf(exe),"final_stdout":cp.stdout.strip()}

def demo(root):
    u={"headers":{},"compile":[
      ("a.cc",b'extern "C" int a(){return 17;}\n',[],"worker-a"),
      ("b.cc",b'extern "C" int b(){return 25;}\n',[],"worker-b"),
      ("main.cc",b'#include <cstdio>\nextern "C" int a(); extern "C" int b(); int main(){int v=a()+b(); std::printf("%d",v); return v==42?0:1;}\n',[],"worker-a") ]}
    x=compile_mesh(root,"67505133bc3ef1c64e069cf8de9c853ebf3fb79b",u); x["proof_class"]="MAILBOX_CAS_MIXED_OBJECT"; Path(root,"DEMO_RESULT.json").write_text(json.dumps(x,indent=2)); return x

def chromium_demo(root,source_root,revision):
    sr=Path(source_root); p="base/types/pass_key.h"; q="base/types/cxx26_projected_value_t.h"
    headers={p:(sr/p).read_bytes(),q:(sr/q).read_bytes()}
    u={"headers":headers,"compile":[
      ("pass.cc",b'#include "base/types/pass_key.h"\nstruct G{static int m();}; struct P{explicit P(base::PassKey<G>){} }; int G::m(){P p(base::PassKey<G>());return 17;} extern "C" int a(){return G::m();}\n',[p],"chromium-worker-a"),
      ("projected.cc",b'#include "base/types/cxx26_projected_value_t.h"\n#include <type_traits>\n#include <vector>\nstruct F{int operator()(const int&x)const{return x;}}; using T=base::projected_value_t<std::vector<int>::iterator,F>; static_assert(std::is_same_v<T,int>); extern "C" int b(){return 25;}\n',[q],"chromium-worker-b"),
      ("main.cc",b'#include <cstdio>\nextern "C" int a(); extern "C" int b(); int main(){int v=a()+b(); std::printf("%d",v); return v==42?0:1;}\n',[],"chromium-worker-a") ]}
    x=compile_mesh(root,revision,u); x["proof_class"]="REAL_CHROMIUM_HEADER_CODE_DISTRIBUTED_COMPILE"; x["source_manifest"]={p:h(headers[p]),q:h(headers[q])}; x["boundary"]="Not yet a GN/Siso full-tree action."; Path(root,"CHROMIUM_HEADER_DEMO_RESULT.json").write_text(json.dumps(x,indent=2)); return x

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--root",type=Path,required=True)
    c=sp.add_parser("chromium-header-demo"); c.add_argument("--root",type=Path,required=True); c.add_argument("--source-root",type=Path,required=True); c.add_argument("--source-revision",required=True)
    r=sp.add_parser("run-bundle"); r.add_argument("--bundle",type=Path,required=True); r.add_argument("--result",type=Path,required=True); r.add_argument("--worker-id",required=True); r.add_argument("--build-id",required=True); r.add_argument("--worker-root",type=Path,required=True)
    a=ap.parse_args()
    if a.cmd=="demo": x=demo(a.root)
    elif a.cmd=="chromium-header-demo": x=chromium_demo(a.root,a.source_root,a.source_revision)
    else: x=run_bundle(a.bundle,a.result,a.worker_id,a.build_id,a.worker_root)
    print(json.dumps(x,indent=2,sort_keys=True)); return 0 if x.get("ok",True) else 1
if __name__=="__main__": raise SystemExit(main())
