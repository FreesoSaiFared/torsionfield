from pathlib import Path

ROOT = Path(r"E:\Transductive_MCP_Work\torsionfield-site")
DOCS = ROOT / "public" / "docs"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:90]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_exact(
    DOCS / "node-network.html",
    '<h2>Torsion Node</h2><p>The production daemon is a signed Rust service with native messaging, loopback WebSocket and platform socket transports. It owns identity, capability policy, process/filesystem runners, local models, MCP clients, artifacts, operation journal, updater and libp2p.</p>',
    '<h2>Torsion Node</h2><p>Torsion Node is the machine-local capability host. Its stable contract is identity, capability policy, typed invocation, evidence, recovery and optional peer transport. Its implementation language is deliberately not architectural: Node.js, Go, Rust or a composed set of services may satisfy the contract when they pass the same acceptance tests.</p><h2>First live capability actor</h2><p><b>Local Repomix</b> is live as a self-describing Repository Context actor. ChatGPT reaches it through OAuth, a Cloudflare gateway and a named tunnel; the runtime remains local, restarts at logon and returns only bounded tool results. It proves the local capability pattern, but peer leases and two-machine invocation are still pending.</p>',
)
replace_exact(
    DOCS / "architecture.html",
    '<h2>One operation, one identity</h2>',
    '<h2>Capability actors</h2><p>Torsionfield is a field of self-describing actors rather than one monolithic daemon. A browser tab, repository-context service, local model, workflow runner or peer machine can expose a typed capability while remaining separately owned. Identity, capability description, transport and actuation are independent and replaceable.</p><p>The first live non-tab actor is <b>Local Repomix</b>: an OAuth-protected MCP service backed by a persistent local runtime and evidence-bearing restart path.</p><h2>One operation, one identity</h2>',
)

replace_exact(
    DOCS / "product-completeness.html",
    '<h2>Architecturally complete</h2><p>The specification now names the full product: extension, daemon, adapters, visual workflow compiler, source incorporation system, P2P network, websites, first-party bridges, permission model, packaging and acceptance matrix.</p>',
    '<h2>Coherent core contracts</h2><p>The stable core is now clear: durable operation identity, self-describing capability actors, observable postconditions, replaceable adapters, local ownership, bounded delegation, evidence and recovery. The architecture no longer depends on one daemon language, one browser actuator or one provider.</p><h2>Verified executable today</h2><p>Local Repomix is deployed and live as the first Repository Context capability actor. It has passed authenticated ChatGPT discovery, real tool invocation, concurrent initialization, OAuth replay handling, Scheduled Task restart and tunnel recovery. This is a real subsystem, not proof-by-documentation.</p>',
)

replace_exact(
    DOCS / "getting-started.html",
    '<h2>Three-minute path</h2>',
    '<h2>Executable today</h2><p>Install the <b>Local Repomix</b> ChatGPT app and invoke one bounded repository or directory operation. The machine-local service owns execution; ChatGPT receives the declared result and evidence. Peer sharing is not yet enabled.</p><h2>Target three-minute path — not yet released</h2>',
)
replace_exact(
    DOCS / "implementation.html",
    '<h2>ScriptCat patch dossier</h2><p>The next controlling artifact must pin the upstream commit and list every changed file, symbol, API, grant, manifest permission, migration, test and rebase risk. It prevents “modify ScriptCat” from remaining an abstract instruction.</p>',
    '<h2>Current single goal</h2><p>Turn Local Repomix from a live machine-local capability into the first lease-bound Torsionfield peer capability. One authorized remote machine must invoke one bounded Repository Context operation, receive the artifact and evidence, then lose access immediately when the owner revokes the lease. Network loss, replay and process restart must not duplicate the effect or widen scope.</p><h2>Later ScriptCat patch dossier</h2><p>A later controlling artifact must pin the upstream commit and list every changed file, symbol, API, grant, manifest permission, migration, test and rebase risk. It prevents “modify ScriptCat” from remaining an abstract instruction, but it is not the current blocking goal.</p>',
)

replace_exact(
    DOCS / "implementation.html",
    '<h2>Definition of done</h2><p>Completion means a fresh machine can install signed artifacts, import existing scripts, create and repair an automation, use at least three provider adapters, pair a local node, expose and invoke a NetworkScript, survive browser/daemon restarts and reproduce every accepted effect from its evidence trail.</p>',
    '<h2>Next milestone done</h2><p>Two separately owned machines can discover one Repository Context actor, grant a narrow expiring lease, invoke it once, verify the result, revoke it, survive restart and network loss, and prove that no credentials or unrelated filesystem state crossed the boundary.</p><h2>Full product done</h2><p>A fresh machine can install signed artifacts, import existing scripts, create and repair an automation, use provider adapters, pair local capability actors, expose and invoke bounded peer capabilities, survive browser/node restarts and reproduce every accepted effect from its evidence trail.</p>',
)

print("Updated Torsionfield documentation for Local Repomix and capability-actor goals.")
