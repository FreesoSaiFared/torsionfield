# WatchThese — emerging project radar

Canonical source: `public/watchthese/` in `FreesoSaiFared/torsionfield`.

LIVE canonical hostname: `https://watchthese.torsionfield.de/` (verified HTTPS 200 and ABP-i9ES page content on 2026-10-14). Alternative hostname: `https://watchthese.transductive.art/`. Both serve the dedicated Caddy origin on i9ES port 8441 via named tunnel `torsionfield-watchthese-20261014` (ID `27d34d00-4a2b-42f0-9896-5c1268547eaf`). DNS for canonical host is a proxied CNAME to the same tunnel in Cloudflare's torsionfield.de zone. The main Torsionfield Worker is not the host of this subdomain.

## Add a project

1. Add a dated `projects[]` record to `public/watchthese/projects.json`. Stable `id`, name, URL, editorial stage, source-linked claims, milestones, and watch reasons are required.
2. Attribute company claims; distinguish company-listed milestones from independently reproduced tests, and projected targets from observed releases.
3. Add the corresponding source URL and stable anchors to `public/watchthese/sources.json`.
4. Run `python3 tools/watchthese_monitor.py`. Review `public/watchthese/observations.json`, which signals source changes and missing anchors; it does NOT auto-promote facts or change project descriptions.
5. Test JS and public pages through the persistent i9ES Caddy origin and named Cloudflare Tunnel. The canonical hostname lives on the tunnel, not the main Worker. When changing the main Torsionfield journal navigation, run `wrangler deploy --dry-run`, deploy with the i9ES OAuth login (exclude obsolete `CF_API_TOKEN`), and independently verify the live apex. Do not re-add a Worker custom-domain route for this subdomain.
