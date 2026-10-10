#!/usr/bin/env python3
"""Inspect the upstream research corpus by revision; publish only metadata."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "steveash/hitchhikers-guide-to-ai-native-engineering"
API = "https://api.github.com/repos/" + REPO
WEB = "https://github.com/" + REPO
NOTE = "source-notes/blog-simonwillison-aisi-gpt55-cyber.md"
OUT = Path(__file__).resolve().parent.parent / "public/research/hitchhikers-upstream.json"
WATCH = {NOTE:100, "guide/06-security-threat-model.md":95,
         "guide/03-verification.md":92, "agents/README.md":90,
         "agents/ASSAYER.md":90, "agents/MINER.md":88,
         "agents/SMITH.md":88, "agents/GARDENER.md":84,
         "CONTRADICTIONS.md":94, "EDITORIAL-CONSTITUTION.md":94,
         "registry/trusted-feeds.json":80}
KEYWORDS = re.compile(r"security|cyber|agent|harness|browser|prompt|verification|context|evaluation|mcp|source|ai-native|orchestrat|workflow|failure|vulnerab|compaction|codex|claude|openai|simonwillison|trust", re.I)
FINDINGS = [
 {"id":"uncertainty-unit","finding":"The source note labels one standard error as a 95% confidence interval.","status":"review-required"},
 {"id":"industrial-control","finding":"AISI says Cooling Tower stalled on IT steps; its results cannot establish OT-specific model ability.","status":"review-required"},
]
PRIMARY = "https://www.aisi.gov.uk/blog/our-evaluation-of-openais-gpt-5-5-cyber-capabilities"

def fetch_json(url):
    h = {"User-Agent":"Torsionfield-SourceWatch/1.0",
         "Accept":"application/vnd.github+json",
         "X-GitHub-Api-Version":"2022-11-28"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token: h["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=h), timeout=20) as response:
        data = response.read(4_000_001)
    if len(data) > 4_000_000: raise ValueError("Oversized upstream API response")
    return json.loads(data)

def priority(path):
    if path in WATCH: return WATCH[path]
    if path.startswith("source-notes/") and path.endswith(".md"):
        return 70 if KEYWORDS.search(Path(path).name) else 0
    if path.startswith("agents/") and path.endswith(".md"): return 78
    if path.startswith(".github/workflows/") and KEYWORDS.search(path): return 73
    if path.startswith("scripts/") and KEYWORDS.search(path): return 66
    if path.startswith("registry/") and KEYWORDS.search(path): return 60
    return 0

def analyze_compare(data, sha):
    if data.get("status") != "ahead": raise ValueError("Non-forward upstream history; manual reconciliation required")
    files = data.get("files")
    if not isinstance(files, list) or len(files) >= 300 or data.get("total_commits",0) > 250:
        raise ValueError("Upstream diff incomplete; refusing to advance cursor")
    changed = []
    for f in files:
        p = f.get("filename","")
        weight = priority(p)
        if not weight or p.startswith("/") or ".." in Path(p).parts: continue
        changed.append({"path":p,"change":f.get("status","modified"),"priority":weight,
                        "url":WEB+"/blob/"+sha+"/"+quote(p)})
    return sorted(changed,key=lambda x:(-x["priority"],x["path"]))

def run(path=OUT, api=fetch_json, now=None):
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    latest = api(API+"/commits/main")
    sha = latest["sha"]
    if not re.fullmatch("[a-f0-9]{40}",sha): raise ValueError("Invalid upstream commit ID")
    previous = existing.get("upstreamSha")
    if previous == sha:
        print("UNCHANGED",sha,"— no write")
        return {"status":"unchanged","sha":sha,"relevantCount":0,"reviewNeeded":False}
    if previous:
        diff = api(API+"/compare/"+previous+"..."+sha)
        changes = analyze_compare(diff,sha)
    else:
        changes = [{"path":NOTE,"change":"initial tracking","priority":100,
                    "url":WEB+"/blob/"+sha+"/"+NOTE}]
    events = [{"atSha":sha,"path":x["path"],"change":x["change"],
               "priority":x["priority"],"url":x["url"],"detectedAt":now} for x in changes]
    record = {
        "schema":"torsionfield-source-watch/1","source":"Hitchhiker's Guide to AI-Native Engineering",
        "upstreamRepo":REPO,"upstreamUrl":WEB,"upstreamSha":sha,
        "previousSha":previous,"checkedAt":now,
        "sourceCommitAt":latest.get("commit",{}).get("committer",{}).get("date"),
        "comparisonUrl":WEB+"/compare/"+(previous or sha)+"..."+sha,
        "trackedNote":{"path":NOTE,"url":WEB+"/blob/"+sha+"/"+NOTE,
                       "primarySource":PRIMARY,"status":"secondary synthesis — verify primary evidence"},
        "auditFindings":[dict(x,primarySource=PRIMARY) for x in FINDINGS],
        "changed":events[:30],"events":(events+existing.get("events",[]))[:80],
        "relevantCount":len(changes),
        "reviewNeeded":any(x["priority"]>=90 for x in changes),
        "publicationPolicy":"Metadata and review leads only. No automatic claim acceptance.",
    }
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    status = "bootstrapped" if not previous else "updated"
    print(status.upper(),sha,"relevant",len(changes),"review",record["reviewNeeded"])
    return {"status":status,"sha":sha,"relevantCount":len(changes),
            "reviewNeeded":record["reviewNeeded"]}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    receipt=run(path=args.output)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
