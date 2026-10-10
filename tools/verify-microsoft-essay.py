#!/usr/bin/env python3
"""Verify the public Microsoft essay against its exact local release bytes."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SLUG = "the-empire-that-mistook-distribution-for-intelligence"
BASE = "https://torsionfield.de"
targets = {
    "/": ROOT / "public/index.html",
    f"/articles/{SLUG}/": ROOT / "public/articles" / SLUG / "index.html",
    "/articles/article.css": ROOT / "public/articles/article.css",
    "/sitemap.xml": ROOT / "public/sitemap.xml",
}
beacon = rb'<script type="module" src="https://static\.cloudflareinsights\.com/beacon\.min\.js/[^"]+"[^>]*></script>\s*'
results = {}
for route, file in targets.items():
    req = Request(BASE + route, headers={"User-Agent": "Torsionfield-Release-Verification/1"})
    with urlopen(req, timeout=25) as response:
        assert response.status == 200, f"HTTP {response.status}: {route}"
        remote = response.read()
        content_type = response.headers.get("Content-Type", "")
    normalized = re.sub(beacon, b"", remote)
    local = file.read_bytes()
    assert normalized == local, f"LIVE_SOURCE_MISMATCH: {route}"
    results[route] = {
        "http": 200, "content_type": content_type,
        "bytes_live": len(remote), "bytes_source": len(local),
        "sha256_live": sha256(remote).hexdigest(),
        "sha256_source": sha256(local).hexdigest(),
        "cloudflare_beacon_bytes": len(remote) - len(normalized),
        "normalized_exact_match": True,
    }
article = targets[f"/articles/{SLUG}/"].read_text(encoding="utf-8")
home = targets["/"].read_text(encoding="utf-8")
sitemap = targets["/sitemap.xml"].read_text(encoding="utf-8")
assert article.count("<h1>") == 1 and article.count("<h2 id=") == 8
assert "Status: draft" not in article
assert 'href="https://commandline.microsoft.com/new-rules-for-builders-agentic-ai-development-jay-parikh-build-2026/"' in article
assert f'href="/articles/{SLUG}/"' in home
assert f"https://torsionfield.de/articles/{SLUG}/" in sitemap
assert article.count("<a href=") >= 20
revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
receipt = {
    "schema": "torsionfield-microsoft-publication/1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "site": BASE, "source_commit_at_verification": revision,
    "article": f"{BASE}/articles/{SLUG}/",
    "checks": {"h1": 1, "sections": 8, "source_links": article.count("<a href="),
               "visual_brave_desktop": "observed locally 2026-10-10",
               "visual_brave_mobile_400px": "observed locally 2026-10-10"},
    "routes": results,
}
path = ROOT / "artifacts/publication-receipts/microsoft-copilot-20261010.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("PUBLICATION_ACCEPTED", receipt["article"], "routes", len(results), "receipt", path)
