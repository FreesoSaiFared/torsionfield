# Torsionfield Runtime website

Cloudflare Worker + static assets serving `torsionfield.de` and `docs.torsionfield.de`. The Worker provides security headers, site manifest/status APIs and D1-backed alpha-interest registration.

Torsionfield is now described as a **field of separately owned capability actors**, not as one predetermined daemon. Browser tabs, repository-context services, local models, workflow runners and peer machines can expose typed, revocable capabilities while retaining local identity and credentials.

## Executable state today

The website and documentation are deployed. The first live machine-local capability actor is Local Repomix:

- authenticated ChatGPT MCP app;
- persistent Windows runtime and Scheduled Task;
- named Cloudflare Tunnel;
- eight bounded repository/file context tools;
- evidence-bearing restart and recovery;
- no peer lease or two-machine invocation yet.

This proves the local capability pattern. It does not yet prove the distributed Torsionfield network.

## Current single goal

Grant one remote Torsionfield peer a narrow, expiring lease to invoke one bounded Local Repomix Repository Context operation. Verify result, evidence, revocation, replay safety, restart/rebind and no credential or unrelated-filesystem transfer.

## Superfluid rule

Keep identity, capability contract, authority, evidence and recovery stable. Let languages, processes, transports, browser lanes and provider implementations change when a better verified path exists.

Documentation must distinguish:

- **live** — proved by executable evidence;
- **partial** — one layer works, distributed closure pending;
- **target** — intended user journey, not yet available.

## Commands

- `npm run check`
- `npm run db:migrate`
- `npm run deploy`

The registration endpoint is an alpha-interest list, not production P2P credential enrollment.
