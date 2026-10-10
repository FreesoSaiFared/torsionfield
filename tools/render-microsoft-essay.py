#!/usr/bin/env python3
"""Reproducible, idempotent Torsionfield Field Notes publication renderer."""
from pathlib import Path
from html import escape
import re
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
SLUG = "the-empire-that-mistook-distribution-for-intelligence"
TITLE = "The Empire That Mistook Distribution for Intelligence"
source = ROOT / "docs/articles" / f"{SLUG}.md"
output = ROOT / "public/articles" / SLUG / "index.html"
md = source.read_text(encoding="utf-8")
assert md.startswith(f"# {TITLE}\n")
assert "Status: draft" not in md
sections = []
body = MarkdownIt("commonmark", {"html": False}).render(md)

def anchor(match):
    name = re.sub(r"<[^>]+>", "", match.group(1))
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    sections.append((slug, name))
    return f'<h2 id="{escape(slug)}">{match.group(1)}</h2>'

body = re.sub(r"<h2>(.*?)</h2>", anchor, body, flags=re.DOTALL)
toc = "\n".join(f'<li><a href="#{escape(s)}">{escape(n)}</a></li>' for s,n in sections)
page = (ROOT / "tools/field-essay-template.html").read_text(encoding="utf-8")
replacements = [
    ("An Agent Is Not Its Computer", TITLE),
    ("an-agent-is-not-its-computer", SLUG),
    ("A source-backed critical examination of invisible_dots: durable agents, virtual machines, verified effects, browser identity, and portable capabilities.",
     "Why Microsoft can distribute Copilot everywhere yet struggle to deliver independently verifiable AI agency."),
    ("TF / CRITICAL ESSAY 001", "TF / CRITICAL ESSAY 002"),
    ("https://github.com/feder-cr/invisible_dots",
     "https://commandline.microsoft.com/new-rules-for-builders-agentic-ai-development-jay-parikh-build-2026/"),
    ("feder-cr / invisible_dots ↗", "Microsoft / Agent-first rules ↗"),
    ("SOURCE ANALYSIS / INDEPENDENT BENCHMARK PENDING",
     "SOURCED CRITIQUE / COMPARATIVE TEST PROPOSED"),
    ("← FIELD NOTES / CRITICAL ARCHITECTURE", "← FIELD NOTES / PLATFORM ANALYSIS"),
    ("Questions generate work. Capabilities perform it. Evidence changes the graph. Authority remains revocable.",
     "Distribution is not intelligence. Evidence is not optional. Authority must remain portable."),
]
for old, new in replacements:
    assert old in page, f"TEMPLATE_DRIFT: {old[:40]}"
    page = page.replace(old, new)
page = page.replace("__TF_BODY__", body).replace("__TF_TOC__", toc)
assert len(sections) >= 8 and page.count("<h1>") == 1
assert "__TF_BODY__" not in page and "Status: draft" not in page
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(page, encoding="utf-8", newline="\n")
home = ROOT / "public/index.html"
html = home.read_text(encoding="utf-8")
anchor_tag = '<a class="journal-feature" href="/articles/an-agent-is-not-its-computer/"'
feature = (
    f'<a class="journal-feature" href="/articles/{SLUG}/" aria-label="Read {TITLE}">'
    '<p class="meta">06 / INDUSTRY CRITIQUE / 10 OCT 2026</p><div>'
    f'<h3>{TITLE}.</h3><p>Copilot, proprietary control, and the difference between selling AI access and completing verifiable work.</p>'
    '</div><span class="feature-action">READ CRITIQUE →</span></a>'
)
if f'href="/articles/{SLUG}/"' not in html:
    assert anchor_tag in html, "HOMEPAGE_ANCHOR_MISSING"
    html = html.replace(anchor_tag, feature + anchor_tag, 1)
    home.write_text(html, encoding="utf-8", newline="\n")
else:
    assert feature in html, "HOMEPAGE_ENTRY_DRIFT"
site = ROOT / "public/sitemap.xml"
sm = site.read_text(encoding="utf-8")
url = f'<url><loc>https://torsionfield.de/articles/{SLUG}/</loc></url>'
if url not in sm:
    original = '<url><loc>https://torsionfield.de/</loc></url>'
    assert original in sm, "SITEMAP_ANCHOR_MISSING"
    sm = sm.replace(original, original + "\n  " + url, 1)
    site.write_text(sm, encoding="utf-8", newline="\n")
print("RENDER_OK", "sections", len(sections), "bytes", output.stat().st_size, output)
