#!/usr/bin/env python3
"""Evidence-grade check of public Field Notes publication against repository assets."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://torsionfield.de"
PATHS = ["/", "/articles/an-agent-is-not-its-computer/", "/articles/article.css"]
LOCAL = [ROOT / "public/index.html",
         ROOT / "public/articles/an-agent-is-not-its-computer/index.html",
         ROOT / "public/articles/article.css"]

def fetch(path):
    req = Request(BASE + path, headers={"User-Agent": "Torsionfield-Publication-Verify/1"})
    with urlopen(req, timeout=20) as response:
        return response.status, response.read(), response.headers.get("Content-Type", "")

results = {}
for route, local in zip(PATHS, LOCAL):
    status, remote, ctype = fetch(route)
    original = local.read_bytes()
    match = sha256(remote).digest() == sha256(original).digest()
    results[route] = {"http": status, "type": ctype,
                      "sha256_local": sha256(original).hexdigest(),
                      "sha256_live": sha256(remote).hexdigest(),
                      "bytes": len(remote), "exact_match": match}
    assert status == 200, f"unexpected HTTP status for {route}"
    if route != "/":
        assert match, f"article or stylesheet mismatch for {route}"
page = LOCAL[1].read_text(encoding="utf-8")
home = LOCAL[0].read_text(encoding="utf-8")
assert page.count("<h1>") == 1
assert page.count("<h2 id=") == 7
assert "INDEPENDENT BENCHMARK PENDING" in page
assert "https://github.com/feder-cr/invisible_dots" in page
assert "/articles/an-agent-is-not-its-computer/" in home
live_home = fetch("/")[1].decode("utf-8")
assert "/articles/an-agent-is-not-its-computer/" in live_home
assert "An agent is not its computer." in live_home
rev = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
receipt = {"schema": "torsionfield-publication-acceptance/1",
           "timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "site": BASE, "source_commit": rev, "routes": results,
           "source_evidence": {"h1_count": 1, "sections": 7, "benchmark_status": "pending"},
           "homepage_skew": {"present": not results["/"]["exact_match"],
                             "live_has_research_archive_links": "/research/" in live_home,
                             "source_has_research_archive_links": "/research/" in home,
                             "policy": "Preserve unrelated live changes; no redeployment"},
           "visual_desktop": "Brave live article inspected via WinRemote on 2026-10-10"}
target = ROOT / "artifacts/publication-receipts/invisible-dots-20261010.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("PUBLICATION_ACCEPTED", rev[:10], "routes", len(results), "receipt", target)
