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
