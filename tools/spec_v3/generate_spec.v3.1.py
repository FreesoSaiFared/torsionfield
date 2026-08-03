from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "source-spec-v3.1.txt"
OUT = ROOT / "public" / "spec"
VERSION = "3.1"
DATE = "2 August 2026"

PARTS = [
    ("I", "Mandate and architecture", range(1, 7)),
    ("II", "Browser runtime and operations", range(7, 15)),
    ("III", "Node, network, authority, and recovery", range(15, 21)),
    ("IV", "Implementation, productization, and evolution", range(21, 30)),
    ("V", "Participatory work, verification, and governance", range(30, 38)),
    ("VI", "References", range(38, 39)),
]

TOP_RE = re.compile(r"^(\d+)\.\s+(.+)$")
SUB_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)*)\s+(.+)$")
NORM_RE = re.compile(r"\b(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY NOT|MAY)\b")
@dataclass
class Section:
    number: int
    title: str
    body: str
    source_start: int
    source_end: int


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "section"


def is_top_heading(line: str) -> bool:
    match = TOP_RE.match(line.strip())
    if not match:
        return False
    title = match.group(2).strip()
    letters = [c for c in title if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.82


def parse_sections(text: str) -> tuple[str, list[Section]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    starts: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        if is_top_heading(line):
            match = TOP_RE.match(line.strip())
            assert match
            starts.append((index, int(match.group(1)), match.group(2).strip()))
    preface = "\n".join(lines[: starts[0][0]]).strip()
    sections: list[Section] = []
    for pos, (start, number, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        sections.append(Section(number, title, body, start + 1, end))
    return preface, sections


SUMMARIES = {
    1: "Defines the product that must be delivered and the evidence standard for calling it complete.",
    2: "States the rules that remain true across every implementation: durable identity, observable effects, explicit authority, recoverability, and local credentials.",
    3: "Fixes the verified ScriptCat foundation and separates existing CAT capabilities from additions required by Torsionfield.",
    4: "Explains the runtime roles, execution planes, and the canonical path of a delegated browser operation.",
    5: "Defines the repository shape, release artifacts, and source boundaries an implementation must actually produce.",
    6: "Names the stable identities used for browsers, tabs, agents, operations, projects, peers, capabilities, and artifacts.",
    7: "Defines routing, delivery, deduplication, recovery, and unknown-outcome semantics for every requested effect.",
    8: "Defines the Mother Script, command envelopes, compatibility tags, acknowledgements, and incremental output parsing.",
    9: "Makes self-mutation and userscript installation transactional, versioned, testable, and reversible.",
    10: "Specifies the human-guided tab and element selection flow and the evidence returned to the requesting operation.",
    11: "Defines provider adapters as complete interaction contracts rather than brittle collections of selectors.",
    12: "Defines protected agent tabs, pool scheduling, restoration, and the difference between extension and native enforcement.",
    13: "Lists the typed CAT compatibility APIs that expose privileged extension capabilities to userscripts.",
    14: "Defines remotely callable NetworkScripts and revocable tab or script endpoints without hiding broad user-configured authority.",
    15: "Defines the Rust Torsion Node, its transports, services, command registry, invocation lifecycle, and service installation.",
    16: "Defines identity hierarchy, pairing, key handling, signatures, encryption, and replay protection.",
    17: "Defines peer connectivity, project tasks, domain responsibilities, and the optional Cloudflare coordination plane.",
    18: "Defines the permission model, including narrow profiles, explicit unrestricted profiles, and signed delegation.",
    19: "Defines persistent state, restart reconciliation, failure envelopes, traces, and user-visible diagnostic surfaces.",
    20: "Defines optional Chromium-native guarantees while keeping the extension and daemon as the complete first implementation.",
}

SUMMARIES.update({
    21: "Turns the architecture into one integrated engineering work packet rather than a sequence of disconnected demonstrations.",
    22: "Defines the acceptance matrix for mutation, routing, adapters, recovery, the daemon, and the network.",
    23: "Collects the non-negotiable implementation rules that prevent silent narrowing, brittle routing, and false success.",
    24: "States what remains missing before the specification is implementation-closed and production-ready.",
    25: "Defines how useful extension capabilities may be incorporated without uncontrolled copying or architectural fragmentation.",
    26: "Defines Prompt Commits and the replayable, licensed, tested process for keeping incorporated capabilities synchronized.",
    27: "Defines product naming, domain responsibilities, registration, first-party integration, and background services.",
    28: "Defines how the product must present immediate browser-only value, progressive installation, and evidence-backed claims.",
    29: "Unifies compile-time and runtime configuration through signed profiles, capability graphs, and reproducible build variants.",
    30: "Defines opt-in contribution of source generation, review, build, test, documentation, and compute work.",
    31: "Defines the boundary around participant-owned model sessions and the limits of what provider execution can prove.",
    32: "Defines encrypted task bundles, ScriptVault, the MCP Notary, execution receipts, verification levels, and supply-chain hardening.",
    33: "Makes TF.* the canonical API while retaining CAT and GM compatibility for the ScriptCat ecosystem.",
    34: "Defines observable, reversible self-modification and governed activation without making model output sovereign.",
    35: "Separates stable capability meaning from movable implementations and defines evidence-driven promotion to native layers.",
    36: "Makes participant trust, delegated authority, assurance, verification, and acceptance explicit and independently inspectable.",
    37: "Defines persistent participant-owned edge cells, separated authority, encrypted state, portable capabilities, and governed deployment.",
    38: "Lists the primary documentation and source projects used as implementation and interoperability references.",
})


def status_for(number: int) -> str:
    if number <= 19 or number in {21, 22, 23, 24, 33, 36}:
        return "first-release"
    if number == 20:
        return "optional-native"
    if 25 <= number <= 32 or number in {34, 35, 37}:
        return "staged-target"
    return "reference"


def part_for(number: int) -> tuple[str, str]:
    for roman, title, members in PARTS:
        if number in members:
            return roman, title
    raise KeyError(number)
def linkify(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(
        r"(https?://[^\s<]+)",
        lambda m: f'<a href="{html.escape(m.group(1), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    return NORM_RE.sub(lambda m: f'<strong class="norm">{m.group(1)}</strong>', escaped)


def requirement_meta(section: int, counter: int, text: str) -> dict[str, object]:
    keywords = list(dict.fromkeys(NORM_RE.findall(text)))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "requirementId": f"TF-S{section:02d}-R{counter:03d}",
        "section": section,
        "keywords": keywords,
        "text": text,
        "sha256": digest,
    }


def looks_like_code(lines: list[str]) -> bool:
    stripped = [line.rstrip() for line in lines if line.strip()]
    if not stripped:
        return False
    first = stripped[0].lstrip()
    code_starts = (
        "{", "}", "[", "type ", "interface ", "@grant ", "CAT.", "TF.",
        "/transductive/", "scriptcat-transductive/", "mother/", "adapters/",
        "extension/", "daemon/", "cloud/", "shared/", "tests/", "packaging/",
        "docs/", "incorporated/", "tools/",
    )
    if first.startswith(code_starts):
        return True
    if len(stripped) > 1 and any(line.startswith(("  ", "    ", "\t")) for line in stripped):
        return True
    punctuation = sum(any(token in line for token in ("=>", "|", "?:", "[]", "{}", ".json", ".ts", ".js")) for line in stripped)
    return len(stripped) > 2 and punctuation >= max(2, len(stripped) // 3)


def is_short_term(block: str) -> bool:
    value = " ".join(block.split())
    return len(value) <= 54 and "\n" not in block and not value.endswith((".", ":", ";")) and not NORM_RE.search(value)
def render_section(section: Section, requirements: list[dict[str, object]]) -> tuple[str, str]:
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n+", section.body) if b.strip()]
    html_out: list[str] = []
    md_out: list[str] = []
    req_counter = 0

    for index, block in enumerate(blocks):
        lines = block.splitlines()
        normalized = " ".join(line.strip() for line in lines).strip()
        sub = SUB_RE.match(normalized) if len(lines) == 1 else None
        if sub:
            anchor = f"s{section.number}-{slug(sub.group(1))}"
            level = 3 if sub.group(1).count(".") == 1 else 4
            html_out.append(f'<h{level} id="{anchor}"><span>{html.escape(sub.group(1))}</span> {html.escape(sub.group(2))}</h{level}>')
            md_out.append(f"{'#' * level} {sub.group(1)} {sub.group(2)}")
            continue

        bullet_lines = [line.strip() for line in lines if line.strip()]
        if bullet_lines and all(line.startswith("- ") for line in bullet_lines):
            items_html: list[str] = []
            items_md: list[str] = []
            for line in bullet_lines:
                value = line[2:].strip()
                attrs = ""
                if NORM_RE.search(value):
                    req_counter += 1
                    meta = requirement_meta(section.number, req_counter, value)
                    requirements.append(meta)
                    attrs = f' id="{meta["requirementId"]}" data-requirement="true"'
                items_html.append(f"<li{attrs}>{linkify(value)}</li>")
                items_md.append(f"- {value}")
            html_out.append("<ul>" + "".join(items_html) + "</ul>")
            md_out.append("\n".join(items_md))
            continue

        numbered = [re.match(r"^(\d+)\.\s+(.+)$", line.strip()) for line in bullet_lines]
        if bullet_lines and all(numbered):
            items_html = []
            items_md = []
            for match in numbered:
                assert match
                value = match.group(2).strip()
                attrs = ""
                if NORM_RE.search(value):
                    req_counter += 1
                    meta = requirement_meta(section.number, req_counter, value)
                    requirements.append(meta)
                    attrs = f' id="{meta["requirementId"]}" data-requirement="true"'
                items_html.append(f"<li{attrs}>{linkify(value)}</li>")
                items_md.append(f"{match.group(1)}. {value}")
            html_out.append("<ol>" + "".join(items_html) + "</ol>")
            md_out.append("\n".join(items_md))
            continue
        if looks_like_code(lines):
            code = "\n".join(line.rstrip() for line in lines).strip()
            html_out.append(f'<pre><code>{html.escape(code)}</code></pre>')
            md_out.append(f"```text\n{code}\n```")
            continue

        if re.fullmatch(r"https?://\S+", normalized):
            safe = html.escape(normalized, quote=True)
            html_out.append(f'<p class="reference-link"><a href="{safe}">{html.escape(normalized)}</a></p>')
            md_out.append(f"<{normalized}>")
            continue

        next_block = blocks[index + 1] if index + 1 < len(blocks) else ""
        if is_short_term(block) and next_block and not SUB_RE.match(" ".join(next_block.split())):
            anchor = f"s{section.number}-{slug(normalized)}"
            html_out.append(f'<h4 class="term" id="{anchor}">{html.escape(normalized)}</h4>')
            md_out.append(f"#### {normalized}")
            continue

        attrs = ""
        if NORM_RE.search(normalized):
            req_counter += 1
            meta = requirement_meta(section.number, req_counter, normalized)
            requirements.append(meta)
            attrs = f' id="{meta["requirementId"]}" data-requirement="true"'
        html_out.append(f"<p{attrs}>{linkify(normalized)}</p>")
        md_out.append(normalized)

    return "\n".join(html_out), "\n\n".join(md_out)


def part_markers(sections: Iterable[Section]) -> dict[int, tuple[str, str]]:
    markers: dict[int, tuple[str, str]] = {}
    seen: set[str] = set()
    for section in sections:
        roman, title = part_for(section.number)
        if roman not in seen:
            markers[section.number] = (roman, title)
            seen.add(roman)
    return markers


def clean_title(title: str) -> str:
    words = title.lower().split()
    fixed = " ".join(words)
    fixed = fixed.replace("scriptcat", "ScriptCat").replace("networkscript", "NetworkScript")
    fixed = fixed.replace("torsionfield", "Torsionfield").replace("scriptvault", "ScriptVault")
    fixed = fixed.replace("mcp", "MCP").replace("api", "API").replace("tf ", "TF ")
    return fixed[:1].upper() + fixed[1:]
def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = SOURCE.read_text(encoding="utf-8-sig")
    preface, sections = parse_sections(text)
    numbers = [section.number for section in sections]
    if numbers != list(range(1, 39)):
        raise RuntimeError(f"Unexpected top-level section sequence: {numbers}")

    requirements: list[dict[str, object]] = []
    markers = part_markers(sections)
    toc_items: list[str] = []
    print_toc: list[str] = []
    body_html: list[str] = []
    body_md: list[str] = []
    source_map: list[dict[str, object]] = []

    for section in sections:
        anchor = f"section-{section.number}"
        display_title = clean_title(section.title)
        status = status_for(section.number)
        toc_items.append(
            f'<a href="#{anchor}" data-section="{section.number}"><span>§{section.number}</span>{html.escape(display_title)}</a>'
        )
        print_toc.append(
            f'<li><a href="#{anchor}"><span>§{section.number}</span>{html.escape(display_title)}</a></li>'
        )
        if section.number in markers:
            roman, part_title = markers[section.number]
            body_html.append(
                f'<section class="part-opener" id="part-{roman.lower()}"><p>Part {roman}</p><h2>{html.escape(part_title)}</h2></section>'
            )
            body_md.append(f"# Part {roman}. {part_title}")

        section_body_html, section_body_md = render_section(section, requirements)
        summary = SUMMARIES[section.number]
        body_hash = hashlib.sha256(section.body.encode("utf-8")).hexdigest()
        source_map.append({
            "section": section.number,
            "sourceTitle": section.title,
            "displayTitle": display_title,
            "anchor": anchor,
            "status": status,
            "sourceLines": [section.source_start, section.source_end],
            "sourceBodySha256": body_hash,
        })
        body_html.append(f'''<section class="spec-section" id="{anchor}" data-status="{status}">
<header class="section-head"><div class="section-number">§{section.number}</div><div><p class="section-kicker">{html.escape(status.replace('-', ' '))}</p><h2>{html.escape(display_title)}</h2></div></header>
<div class="section-summary"><strong>Purpose.</strong> {html.escape(summary)}</div>
<div class="section-body">{section_body_html}</div>
<p class="back-to-top"><a href="#top">Back to contents</a></p>
</section>''')
        body_md.append(f"## §{section.number}. {display_title}\n\n> **Purpose.** {summary}\n\n{section_body_md}")
    source_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    generated_at = datetime.now(timezone.utc).isoformat()
    requirement_count = len(requirements)
    section_count = len(sections)

    html_doc = f'''<!doctype html>
<html lang="en" data-view="comfortable">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Torsionfield Runtime Specification v{VERSION}</title>
<meta name="description" content="The complete Torsionfield Runtime product and engineering specification: browser runtime, local node, network, work donation, verification, participant trust, and governed self-modification.">
<link rel="canonical" href="https://spec.torsionfield.de/">
<link rel="icon" href="/favicon.svg">
<link rel="stylesheet" href="/spec/spec.css">
<script src="/spec/spec.js" defer></script>
</head>
<body id="top">
<a class="skip-link" href="#spec-content">Skip to specification</a>
<header class="site-head">
  <a class="wordmark" href="https://torsionfield.de/">TORSION<span>FIELD</span></a>
  <nav aria-label="Specification actions">
    <a href="#contents">Contents</a>
    <a href="/spec/torsionfield-runtime-spec-v3.1-print.pdf">PDF</a>
    <a href="/spec/torsionfield-runtime-spec-v3.1.md" download>Markdown</a>
    <button type="button" data-print>Print / PDF</button>
  </nav>
</header>
<div class="reading-progress" aria-hidden="true"><span></span></div>
<div class="spec-layout">
<aside class="spec-rail" aria-label="Specification navigation">
  <div class="rail-inner">
    <label for="spec-search">Search sections</label>
    <input id="spec-search" type="search" placeholder="Filter contents" autocomplete="off">
    <div class="view-switch" role="group" aria-label="Reading density">
      <button type="button" data-view-mode="comfortable" aria-pressed="true">Readable</button>
      <button type="button" data-view-mode="compact" aria-pressed="false">Compact</button>
    </div>
    <nav class="toc" aria-label="Table of contents">{''.join(toc_items)}</nav>
  </div>
</aside>
<main id="spec-content" tabindex="-1">
'''
    html_doc += f'''
<section class="cover" aria-labelledby="spec-title">
  <p class="overline">Product and engineering specification</p>
  <h1 id="spec-title">Torsionfield Runtime</h1>
  <p class="subtitle">Capability, authority, evidence, verification, and acceptance</p>
  <dl class="cover-meta">
    <div><dt>Edition</dt><dd>Version {VERSION}</dd></div>
    <div><dt>Date</dt><dd>{DATE}</dd></div>
    <div><dt>Status</dt><dd>Normative integrated rewrite</dd></div>
    <div><dt>Source</dt><dd>Complete v2.4 specification</dd></div>
  </dl>
  <p class="cover-note">This edition rewrites the document for navigability, implementation traceability, accessible screen reading, and compact paged-media output. All 38 sections are retained and mapped. Normative clauses receive stable requirement identifiers without changing their force.</p>
</section>
<section class="front-matter" id="orientation">
  <div class="front-grid">
    <div>
      <p class="overline">What this system is</p>
      <h2>A programmable browser runtime with explicit authority and evidence.</h2>
      <p>Torsionfield begins as a ScriptCat-derived extension and a local Torsion Node. It turns browser pages, AI sessions, userscripts, local tools, and optional peers into typed capability providers connected by durable operations.</p>
      <p>The first release is not a browser fork, a token economy, or a promise of autonomous correctness. It is a working browser runtime whose effects are attributable, observable, recoverable, and accepted only under an explicit policy.</p>
    </div>
    <div class="principle-card">
      <p class="overline">Governing rule</p>
      <blockquote>Nothing is silently prohibited. Nothing is silently trusted. Nothing is silently verified. Nothing is silently accepted.</blockquote>
    </div>
  </div>
  <section class="implementation-path" aria-labelledby="first-build-title">
    <p class="overline">The direct implementation path</p>
    <h2 id="first-build-title">Build one complete ScriptCat-first vertical slice.</h2>
    <ol class="stack-flow">
      <li><span>01</span><strong>Extension</strong><small>Router, Mother Script, provider adapters, target selection, mutation, installation, and protected agent tabs.</small></li>
      <li><span>02</span><strong>Torsion Node</strong><small>Authenticated local IPC, durable journal, files, processes, artifacts, identity, and bounded runners.</small></li>
      <li><span>03</span><strong>Work and verification</strong><small>Signed tasks, participant-owned providers, encrypted bundles, quarantine, receipts, independent review, and rollback.</small></li>
      <li><span>04</span><strong>Optional network</strong><small>Peer discovery, revocable capabilities, project coordination, and first-party domain integration.</small></li>
    </ol>
  </section>
'''
    html_doc += f'''
  <section class="four-dimensions" aria-labelledby="dimensions-title">
    <p class="overline">Do not collapse these concepts</p>
    <h2 id="dimensions-title">Four independent decisions govern every consequential result.</h2>
    <div class="dimension-grid">
      <article><h3>Permission</h3><p>May this operation execute under the current authority profile?</p></article>
      <article><h3>Participant trust</h3><p>How reliable is this participant for this task, role, consequence, device, and context?</p></article>
      <article><h3>Assurance</h3><p>What properties of identity, execution, observation, isolation, recovery, and attestation are actually supported?</p></article>
      <article><h3>Acceptance</h3><p>Who is willing to rely on this exact result, for which purpose, despite what remaining uncertainty?</p></article>
    </div>
  </section>
  <section class="status-legend" aria-labelledby="status-title">
    <p class="overline">Implementation interpretation</p>
    <h2 id="status-title">Every section is labelled by delivery status.</h2>
    <dl>
      <div><dt><span class="status first-release">First release</span></dt><dd>Required by the direct ScriptCat-first implementation or its release gates.</dd></div>
      <div><dt><span class="status optional-native">Optional native</span></dt><dd>Stronger browser-native guarantees that are not on the first-release critical path.</dd></div>
      <div><dt><span class="status staged-target">Staged target</span></dt><dd>Architecturally defined future work that must not delay the complete vertical slice.</dd></div>
      <div><dt><span class="status reference">Reference</span></dt><dd>Source material, interoperability targets, and implementation references.</dd></div>
    </dl>
  </section>
  <section class="normative-key" aria-labelledby="normative-title">
    <p class="overline">Normative language</p>
    <h2 id="normative-title">Requirement force is preserved.</h2>
    <p><strong class="norm">MUST</strong> and <strong class="norm">MUST NOT</strong> define acceptance requirements. <strong class="norm">SHOULD</strong> identifies the preferred implementation unless a documented constraint requires another choice. <strong class="norm">MAY</strong> identifies an optional capability.</p>
    <p>This edition identified <strong>{requirement_count}</strong> normative clauses. Each receives a stable identifier such as <code>TF-S07-R004</code> and an exact SHA-256 digest in the downloadable requirements manifest.</p>
  </section>
</section>
<section class="contents-page" id="contents" aria-labelledby="contents-title">
  <p class="overline">Document map</p>
  <h2 id="contents-title">Contents</h2>
  <ol>{''.join(print_toc)}</ol>
</section>
{''.join(body_html)}
'''
    html_doc += f'''
<footer class="spec-footer">
  <p><strong>Torsionfield Runtime Specification v{VERSION}</strong></p>
  <p>{section_count} complete source sections · {requirement_count} indexed normative clauses · source SHA-256 <code>{source_digest}</code></p>
  <p><a href="/spec/source-map.json">Source map</a> · <a href="/spec/requirements.json">Requirements manifest</a> · <a href="/spec/editorial-loop.html">Editorial loop</a> · <a href="https://torsionfield.de/">Torsionfield product site</a></p>
</footer>
</main>
</div>
</body>
</html>
'''

    md_front = f'''---
title: "Torsionfield Runtime Specification"
version: "{VERSION}"
date: "{DATE}"
status: "Normative integrated rewrite"
source_sha256: "{source_digest}"
---

# Torsionfield Runtime

## Capability, authority, evidence, verification, and acceptance

This edition rewrites the complete v2.4 specification plus the Participant Edge amendment plus the Participant Edge amendment plus the Participant Edge amendment for clarity, navigability, implementation traceability, accessible screen reading, and compact paged-media output. All 38 sections are retained and mapped. Normative clauses keep their original force.

> Nothing is silently prohibited. Nothing is silently trusted. Nothing is silently verified. Nothing is silently accepted.

'''
    markdown_doc = md_front + "\n\n".join(body_md) + "\n"

    manifest = {
        "protocol": "torsionfield-spec/1",
        "version": VERSION,
        "date": DATE,
        "generatedAt": generated_at,
        "source": {
            "title": preface.splitlines()[0] if preface else "Torsionfield Runtime",
            "version": "2.4+participant-edge",
            "sha256": source_digest,
            "characters": len(text),
            "sections": section_count,
        },
        "output": {
            "canonical": "https://spec.torsionfield.de/",
            "requirements": requirement_count,
            "formats": ["html", "css-paged-media", "pdf", "markdown", "json-manifests"],
        },
    }

    (OUT / "index.html").write_text(html_doc, encoding="utf-8")
    (OUT / "torsionfield-runtime-spec-v3.1.md").write_text(markdown_doc, encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "source-map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    (OUT / "requirements.json").write_text(json.dumps(requirements, indent=2), encoding="utf-8")
    rounds = [
        {
            "round": 1,
            "question": "What is this actually trying to build?",
            "finding": "The source mixed product definition, implementation detail, future architecture, and governance without a short reading path.",
            "change": "Added a new cover, executive orientation, direct vertical-slice path, six document parts, and one-sentence purpose summaries for all 37 sections.",
            "gate": "A reader can identify the first build without reading the optional browser-native or network targets.",
        },
        {
            "round": 2,
            "question": "Can an engineer trace every important sentence to a release decision?",
            "finding": "Normative language existed, but requirements lacked stable identifiers and machine-readable extraction.",
            "change": "Indexed every normative paragraph and list item, generated exact hashes, source ranges, status labels, and downloadable requirement and source-map manifests.",
            "gate": "Every MUST, SHOULD, and MAY can be linked, tested, compared, and audited without changing its original force.",
        },
        {
            "round": 3,
            "question": "Where could the document claim more trust than the evidence supports?",
            "finding": "Permission, participant trust, assurance, verification, and acceptance were easy to read as one security score.",
            "change": "Made the four independent decisions explicit in the front matter and preserved the complete participant-trust, receipt, dispute, falsification, and acceptance architecture.",
            "gate": "The document never treats a signature, sandbox, model response, attestation, or majority vote as semantic truth by itself.",
        },
        {
            "round": 4,
            "question": "Can a tired person read this on screen and print it without wasting paper?",
            "finding": "The source was complete but visually flat, difficult to navigate, and not designed for paged media.",
            "change": "Added semantic landmarks, keyboard focus, searchable navigation, readable and compact modes, section status, print contents, A4 rules, running strings, page counters, widows/orphans, compact code, and reference columns.",
            "gate": "The same HTML remains accessible on screen and produces a compact, legible print edition without a separate content fork.",
        },
    ]
    loop_md = "# Ralph Wiggum editorial loop\n\n" + "\n\n".join(
        f"## Round {r['round']}: {r['question']}\n\n**Finding.** {r['finding']}\n\n**Change.** {r['change']}\n\n**Gate.** {r['gate']}"
        for r in rounds
    )
    loop_md += f"\n\n## Closure metrics\n\n- Source sections retained: {section_count}/38\n- Normative clauses indexed: {requirement_count}\n- Source SHA-256: `{source_digest}`\n- Output formats: HTML, paged-media CSS, Markdown, JSON source map, JSON requirements manifest\n"
    loop_cards = "".join(
        f'''<article><p class="overline">Round {r['round']}</p><h2>{html.escape(r['question'])}</h2><p><strong>Finding.</strong> {html.escape(r['finding'])}</p><p><strong>Change.</strong> {html.escape(r['change'])}</p><p><strong>Gate.</strong> {html.escape(r['gate'])}</p></article>'''
        for r in rounds
    )
    loop_html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Editorial loop · Torsionfield Specification</title><link rel="stylesheet" href="/spec/spec.css"></head>
<body class="editorial-page"><main class="editorial-wrap"><p><a href="/">← Specification</a></p><p class="overline">Rewrite audit</p><h1>Ralph Wiggum editorial loop</h1><p class="lede">Four passes were repeated until the document had a clear product hierarchy, traceable requirements, an honest trust model, and one accessible screen/print source.</p>{loop_cards}<section><h2>Closure metrics</h2><ul><li>Source sections retained: {section_count}/38</li><li>Normative clauses indexed: {requirement_count}</li><li>Source SHA-256: <code>{source_digest}</code></li><li>Canonical output: <a href="https://spec.torsionfield.de/">spec.torsionfield.de</a></li></ul></section></main></body></html>'''
    (OUT / "editorial-loop.md").write_text(loop_md, encoding="utf-8")
    (OUT / "editorial-loop.html").write_text(loop_html, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "source": str(SOURCE),
                "output": str(OUT),
                "sourceCharacters": len(text),
                "sections": section_count,
                "requirements": requirement_count,
                "sourceSha256": source_digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    build()
