#!/usr/bin/env python3
"""Idempotent, separately owned WatchThese preview: Caddy + named Cloudflare Tunnel."""
from pathlib import Path
import subprocess, json, os, time, hashlib
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/"public"/"watchthese"
OPS=ROOT/"ops"/"watchthese"
HOME=Path.home()
HOST="watchthese.transductive.art"
NAME="torsionfield-watchthese-20261014"
PORT=8441
OPS.mkdir(parents=True,exist_ok=True)
def run(args,check=True):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=55)
 if check and p.returncode: raise RuntimeError(args[0]+" failed: "+(p.stderr or p.stdout)[-900:])
 return p
def save(path,content,mode=0o644):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(content,encoding="utf-8");path.chmod(mode)
def status(url):
 return run(["curl","-L","-sS","-o","/dev/null","-w","%{http_code}","--max-time","9",url],False).stdout.strip()
def main():
 for p in ("index.html","watchthese.css","watchthese.js","projects.json"):
  assert (SITE/p).is_file(),p
 config=f"""{{\n admin off\n auto_https off\n}}\n:{PORT} {{\n bind 127.0.0.1\n root * {SITE}\n encode zstd gzip\n header X-Content-Type-Options nosniff\n file_server\n}}\n"""
 save(OPS/"Caddyfile",config)
 caddy=str(HOME/".local/bin/caddy")
 run([caddy,"validate","--config",str(OPS/"Caddyfile"),"--adapter","caddyfile"])
 unitdir=HOME/".config/systemd/user"
 origin="tf-watchthese-origin.service"
 origin_text=f"""[Unit]\nDescription=WatchThese preview local Caddy origin\nAfter=network-online.target\n[Service]\nExecStart={caddy} run --config {OPS}/Caddyfile --adapter caddyfile\nRestart=always\nRestartSec=4\n[Install]\nWantedBy=default.target\n"""
 save(unitdir/origin,origin_text)
 run(["systemctl","--user","daemon-reload"])
 run(["systemctl","--user","enable","--now",origin])
 run(["systemctl","--user","restart",origin])
 time.sleep(.8)
 local=status(f"http://127.0.0.1:{PORT}/")
 assert local=="200",("local",local)
 cloudflared="/usr/local/bin/cloudflared"
 listing=json.loads(run([cloudflared,"tunnel","list","--output","json"]).stdout)
 matching=[t for t in listing if t.get("name")==NAME and not str(t.get("deleted_at") or "").startswith("202")]
 if len(matching)>1:raise RuntimeError("Multiple tunnels with same name")
 if not matching:
  run([cloudflared,"tunnel","create",NAME])
  listing=json.loads(run([cloudflared,"tunnel","list","--output","json"]).stdout)
  matching=[t for t in listing if t.get("name")==NAME and not str(t.get("deleted_at") or "").startswith("202")]
 assert len(matching)==1
 tid=matching[0]["id"]
 creds=HOME/".cloudflared"/(tid+".json")
 assert creds.is_file(),"Missing named tunnel credential"
 tunnel_cfg=f"tunnel: {tid}\ncredentials-file: {creds}\ningress:\n  - hostname: {HOST}\n    service: http://127.0.0.1:{PORT}\n  - hostname: watchthese.torsionfield.de\n    service: http://127.0.0.1:{PORT}\n  - service: http_status:404\n"
 save(OPS/"tunnel.yml",tunnel_cfg,0o600)
 route=run([cloudflared,"tunnel","route","dns",tid,HOST],False)
 detail=(route.stdout+route.stderr)
 if route.returncode and "already" not in detail.lower():
  raise RuntimeError("DNS route: "+detail[-800:])
 tunnel_unit="tf-watchthese-tunnel.service"
 tunnel_text=f"""[Unit]\nDescription=WatchThese named tunnel\nAfter=network-online.target tf-watchthese-origin.service\nWants=tf-watchthese-origin.service\n[Service]\nExecStart={cloudflared} --no-autoupdate --config {OPS}/tunnel.yml tunnel run {tid}\nRestart=always\nRestartSec=5\n[Install]\nWantedBy=default.target\n"""
 save(unitdir/tunnel_unit,tunnel_text)
 run(["systemctl","--user","daemon-reload"])
 run(["systemctl","--user","enable","--now",tunnel_unit])
 run(["systemctl","--user","restart",tunnel_unit])
 public="not_yet_200"
 for attempt in range(8):
  time.sleep(2)
  public=status("https://"+HOST+"/")
  if public=="200":break
 receipt={"host":HOST,"origin":local,"public":public,"tunnel_id":tid,"name":NAME,"services":{"origin":run(["systemctl","--user","is-active",origin],False).stdout.strip(),"tunnel":run(["systemctl","--user","is-active",tunnel_unit],False).stdout.strip()},"source_commit":run(["git","-C",str(ROOT),"rev-parse","HEAD"]).stdout.strip()}
 save(OPS/"deployment-receipt.json",json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(receipt,indent=2))
 if public!="200":raise RuntimeError("Public preview not yet reachable")
if __name__=="__main__": main()
