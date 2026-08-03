# Torsionfield implementation evidence - 2 August 2026

Status: executable semantic prototype verified on the Windows host; Debian 13 executor NEEDS_REPAIR.

## Provenance
- Upstream: scriptscat/scriptcat
- Commit: 413bee9593259179e9db72be61d98f060fcf5738
- Archive SHA-256: 0f7b10780a7ab9c71b6697c7510b0e1ae56f2d8851af029ddfe84beadbd9bcea
- License: GPL-3.0

## Verified host evidence
- Node.js one-shot build completed.
- Three modules syntax-checked and copied to dist.
- Seven of seven tests passed.
- Bearer-authenticated loopback health and system.describe smoke test passed.
- A broken Volta/npm launcher was encountered, captured and bypassed by invoking process.execPath directly.

## Implemented semantic calls
system.describe; calls.list; userscripts.list/get/install/update/enable/disable/remove/restore; browser.tabs.list/create/remove; providers.bind/insert/submit/capture; extension.eval.

## Exact boundary
The harness uses virtual tabs and providers. It is not the production ScriptCat fork, a live browser adapter, or the Rust Torsion Node. Podman is installed but its Linux VM/socket is unavailable; the Debian image build exits 125 and is classified NEEDS_REPAIR.

## Next implementation packet
Wire userscripts.install and userscripts.update into ScriptCat's canonical registry and hot-reload path, preserve stable identity through ten updates, prove rollback, then rerun the same acceptance campaign inside a functioning Debian 13 executor.
