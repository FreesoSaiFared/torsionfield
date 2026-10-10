#!/usr/bin/env python3
"""Generate a source-attributed RSS snapshot. No syndicated article body is copied."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import xml.etree.ElementTree as ET

URL = "https://blog.trailofbits.com/index.xml"
OUT = Path(__file__).resolve().parent.parent / "public" / "research-feed.json"
def main():
    req = Request(URL, headers={"User-Agent": "Torsionfield-ResearchFeed/1.0", "Accept": "application/rss+xml"})
    with urlopen(req, timeout=25) as response:
        xml = response.read(3_000_001)
    if len(xml) > 3_000_000:
        raise ValueError("RSS exceeded three megabytes")
    root = ET.fromstring(xml)
    records = []
    for entry in root.findall("./channel/item"):
        title = (entry.findtext("title") or "").strip()[:300]
        link = (entry.findtext("link") or "").strip()
        host = urlparse(link)
        if not title or host.scheme != "https" or host.hostname != "blog.trailofbits.com":
            continue
        raw = entry.findtext("pubDate") or ""
        try:
            date = parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            date = None
        records.append({"title": title, "url": link, "date": date})
        if len(records) >= 6:
            break
    if not records:
        raise RuntimeError("No usable items; keep the existing snapshot")
    payload = {"source": "Trail of Bits", "sourceUrl": URL, "updatedAt": datetime.now(timezone.utc).isoformat(), "items": records}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(records)} attributed items -> {OUT}")

if __name__ == "__main__":
    main()
