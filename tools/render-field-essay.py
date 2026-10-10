#!/usr/bin/env python3
"""Compile a source-backed Torsionfield field essay; Markdown is authoritative."""
from html import escape
from pathlib import Path
import re
from markdown_it import MarkdownIt

root = Path(__file__).resolve().parents[1]
source = root / "docs/articles/an-agent-is-not-its-computer.md"
template = root / "tools/field-essay-template.html"
output = root / "public/articles/an-agent-is-not-its-computer/index.html"
md = source.read_text(encoding="utf-8")
assert md.startswith("# An Agent Is Not Its Computer\n")
assert "Evidence and status — 10 October 2026." in md
body = MarkdownIt("commonmark", {"html": False}).render(md)
sections = []
def anchor(match):
    name = re.sub(r"<[^>]+>", "", match.group(1))
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    sections.append((slug, name))
    return f'<h2 id="{escape(slug)}">{match.group(1)}</h2>'
body = re.sub(r"<h2>(.*?)</h2>", anchor, body, flags=re.DOTALL)
toc = "\n".join(f'<li><a href="#{escape(slug)}">{escape(name)}</a></li>' for slug, name in sections)
page = template.read_text(encoding="utf-8").replace("__TF_BODY__", body).replace("__TF_TOC__", toc)
assert len(sections) >= 6 and page.count("<h1>") == 1
assert "__TF_BODY__" not in page and "__TF_TOC__" not in page
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(page, encoding="utf-8")
print(f"RENDER_OK sections={len(sections)} bytes={output.stat().st_size} output={output}")
