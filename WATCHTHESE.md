# WatchThese — emerging project radar

Canonical source: `public/watchthese/` in `FreesoSaiFared/torsionfield`.

Requested hostname: `https://watchthese.torsionfield.de/` (Cloudflare Worker; not live until authorized deployment). Verified preview: `https://watchthese.transductive.art/` on i9ES, port 8441 via named tunnel `torsionfield-watchthese-20261014`.

## Add a project

1. Add a dated `projects[]` record to `public/watchthese/projects.json`. Stable `id`, name, URL, editorial stage, source-linked claims, milestones, and watch reasons are required.
2. Attribute company claims; distinguish company-listed milestones from independently reproduced tests, and projected targets from observed releases.
3. Add the corresponding source URL and stable anchors to `public/watchthese/sources.json`.
4. Run `python3 tools/watchthese_monitor.py`. Review `public/watchthese/observations.json`, which signals source changes and missing anchors; it does NOT auto-promote facts or change project descriptions.
5. Test JS, run `wrangler deploy --dry-run`, publish through valid Cloudflare credentials, and independently test public pages.
