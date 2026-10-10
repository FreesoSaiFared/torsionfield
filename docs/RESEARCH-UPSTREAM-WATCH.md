# Torsionfield upstream research watch

Source: https://github.com/steveash/hitchhikers-guide-to-ai-native-engineering

The existing public Torsionfield repository watches this independent, AI-maintained
engineering corpus. Do not equate source-note synthesis with primary evidence.

## Ingestion mechanism
- GitHub Actions: .github/workflows/watch-ai-native-upstream.yml
- Schedule: every 30 minutes, at minutes 08 and 38, and manual dispatch.
- Scanner: tools/watch_hitchhikers.py; latest SHA check; no write if unchanged.
- Incremental compare detects relevant guide, source-note and agent changes.
- A truncated or non-forward diff fails closed without advancing the cursor.
- Output: public/research/hitchhikers-upstream.json (metadata only).
- High-priority changes open a GitHub issue for independent source review.
- Live homepage reads /api/research/hitchhikers, backed by a Cloudflare
  Worker fetching the published metadata from GitHub with 180-second caching.
- No external source content is ever run as an instruction or silently adopted.

## Quality gate
The watcher records candidates; it does not certify claims.
Only verified primary-source evidence and reviewed Torsionfield experiments
may become recommendations. The source note about GPT-5.5-Cyber has two
standing review leads:
1. The note labels AISI's ±1-standard-error figures as 95% confidence intervals.
2. The note treats an IT-stage failure on Cooling Tower as an OT-specific
   model limitation, contradicting AISI's express limitation.
Primary source:
https://www.aisi.gov.uk/blog/our-evaluation-of-openais-gpt-5-5-cyber-capabilities

These findings must be rechecked when the upstream note changes.
Use python3 -m unittest discover -s tests -p test_watch_hitchhikers.py -v
to verify idempotence, provenance, relevance and incomplete-diff safety.

The schedule is best-effort, not an immediate push webhook. Standard runners
for public GitHub repositories are free; no new hosting repo is necessary.

## Second gate: primary-source evidence (2026-10-10)
- `tools/verify_research_claims.py` reads the pinned upstream GPT-5.5-Cyber
  source note and the directly linked AISI and Simon Willison publications.
- The verifier is a **bounded, deterministic evidence checker**, not an LLM
  asked to decide whether a conclusion is true. It detects eight claim headings,
  checks whether attributed quotations occur in source text, validates four
  literal numerical anchors and checks two previously identified interpretive
  conflicts against AISI's express caveats.
- Each report is SHA-bound to the upstream note and SHA-256-bound to the
  downloaded original sources. An unchanged note is rechecked against the
  primary sources at most once every 24 hours. A relevant new note revision
  triggers rechecking sooner. Other changed notes remain review candidates.
- Unknown linked domains are never fetched automatically; no source content
  becomes executable instructions. Missing primary evidence or a reduced
  extraction causes the checker to preserve the last report and fail the check.
- Outcomes: `literal-match-only`, `primary-text-located`,
  `linked-commentary-located`, `quote-not-located`, `potential-conflict`,
  and `pending-independent-judgment`. None equals semantic verification.
- The public audit is `public/research/evidence-audit.json`, served by
  `/api/research/evidence`; the JSON is metadata, not full article text.
- The 30-minute GitHub Action now updates both research files. The verifier
  step uses `continue-on-error`: upstream discovery stays operational during
  primary-source outages, while older evidence retains its dated timestamp.
- Exact-match checking does NOT prove that the author's inference is sound.
  A human or separately evaluated reviewer must independently consider
  alternative explanations before approving publication or code changes.
- Offline acceptance: `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
- This pilot is narrowly scoped to the AISI note. Other incoming research
  sources are queued by discovery and have not silently been verified.

## Second gate: primary-source evidence (2026-10-10)
- `tools/verify_research_claims.py` reads the pinned upstream GPT-5.5-Cyber
  source note and the directly linked AISI and Simon Willison publications.
- The verifier is a **bounded, deterministic evidence checker**, not an LLM
  asked to decide whether a conclusion is true. It detects eight claim headings,
  checks whether attributed quotations occur in source text, validates four
  literal numerical anchors and checks two previously identified interpretive
  conflicts against AISI's express caveats.
- Each report is SHA-bound to the upstream note and SHA-256-bound to the
  downloaded original sources. An unchanged note is rechecked against the
  primary sources at most once every 24 hours. A relevant new note revision
  triggers rechecking sooner. Other changed notes remain review candidates.
- Unknown linked domains are never fetched automatically; no source content
  becomes executable instructions. Missing primary evidence or a reduced
  extraction causes the checker to preserve the last report and fail the check.
- Outcomes: `literal-match-only`, `primary-text-located`,
  `linked-commentary-located`, `quote-not-located`, `potential-conflict`,
  and `pending-independent-judgment`. None equals semantic verification.
- The public audit is `public/research/evidence-audit.json`, served by
  `/api/research/evidence`; the JSON is metadata, not full article text.
- The 30-minute GitHub Action now updates both research files. The verifier
  step uses `continue-on-error`: upstream discovery stays operational during
  primary-source outages, while older evidence retains its dated timestamp.
- Exact-match checking does NOT prove that the author's inference is sound.
  A human or separately evaluated reviewer must independently consider
  alternative explanations before approving publication or code changes.
- Offline acceptance: `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
- This pilot is narrowly scoped to the AISI note. Other incoming research
  sources are queued by discovery and have not silently been verified.
