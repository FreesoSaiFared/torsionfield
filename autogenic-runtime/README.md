# Torsionfield Autogenic Runtime

This directory is the executable vertical slice of the permanent privileged-runtime architecture: one persistent elevated resident, one Chrome MV3 privilege bridge, one ScriptCat userscript, and resident-owned browser recovery.

## Runtime shape

```text
ChatGPT conversation
  ↕ ScriptCat userscript / TF_ACTION blocks
page postMessage
  ↕
Torsionfield MV3 content bridge
  ↕ chrome.runtime messaging
Torsionfield MV3 service worker
  ↕ authenticated loopback HTTP
Torsionfield elevated resident (127.0.0.1:17373)
  ↕
processes · filesystem · browser lifecycle · CDP recovery helpers
```

The resident is the continuity anchor. Browser restart must not destroy machine authority. ScriptCat and userscripts are programmable browser-side surfaces, not the privilege boundary.

The resident bearer credential is deliberately absent from userscript source. It is held by the machine-installed MV3 bridge. This protects the bridge credential from ScriptCat installer/source views without reducing resident authority.

## Implemented resident operations

- `exec`
- `process.start`
- `process.kill`
- `process.list`
- `fs.read`
- `fs.write`
- `fs.delete`
- `browser.launch`
- `browser.restart`
- `browser.status`

Browser launch/restart on ChatGPT URLs runs the resident-owned `browser_recover.mjs` helper. It uses raw CDP to restore ScriptCat, its Chrome 138+ `userScriptsAccess` gate, the autogenic userscript, the exact ChatGPT target and the elevated-resident page handshake.

## Chat action protocol

An assistant message can request a machine operation using:

```text
[[TF_ACTION/1
{"id":"probe","op":"exec","args":{"shell":"whoami"}}
[[/TF_ACTION]]
```

The ScriptCat bridge executes it through the elevated resident and automatically submits a `TORSIONFIELD MACHINE RESULT /1` turn back into the same ChatGPT conversation. The assistant can then continue from observed machine state.

The userscript also detects known human-handoff failure language. When the dependency is a reachable machine/browser/software operation, it submits an autonomy-intercept turn rather than asking the human to perform it.

## Windows installation

Run `install/install-windows.ps1` from elevated PowerShell. It creates `Torsionfield Autogenic Resident` as an at-logon Scheduled Task with `RunLevel Highest`, starts it, verifies `/v1/health`, installs the resident browser-recovery helper and generates a browser bootstrap script.

Current designated-machine installation:

```text
C:\ProgramData\Torsionfield\AutogenicRuntime
resident: http://127.0.0.1:17373
Scheduled Task: Torsionfield Autogenic Resident
```

The live acceptance profile is the already-authenticated dedicated profile:

```text
E:\Transductive_MCP_Work\page-agent-chatgpt-profile
Chromium 149.0.7827.55
CDP 127.0.0.1:9448
```

## Linux / Internal VM

Run `sudo install/install-linux.sh`. It installs a root `systemd` resident and the same browser-recovery helper. Browser acceptance should use the ScriptCat/CDP procedures in the Internal VM master guide.

## Reproducible acceptance

Resident smoke test:

```bash
TF_RESIDENT_TOKEN=... python3 tests/smoke.py
```

Live authenticated full-loop acceptance, against an already-running dedicated browser:

```bash
node tests/live_markup_loop.mjs --port 9448 --version 0.2.2
```

That test creates a fresh ChatGPT conversation, asks the model to emit one unique benign `TF_ACTION`, and requires exactly one automatic `TORSIONFIELD MACHINE RESULT /1` turn carrying the same machine stdout marker.

## Proven on the designated Windows machine — 2026-08-14

- Scheduled Task resident running at highest privileges and reporting `elevated=true`.
- authenticated resident command execution as `desktop-01b08bs\admin`.
- authenticated resident filesystem write/read.
- ScriptCat 1.5.0.1100 built locally and loaded unpacked.
- Chrome `userScriptsAccess` enabled and `chrome.userScripts` callable.
- token-free autogenic userscript installed through ScriptCat's real `.user.js` installer/update path.
- userscript → MV3 bridge → elevated resident → Windows command → page-result path proven live.
- resident-owned dedicated-browser restart proven: Chromium closed, CDP disappeared, new Chromium root launched, exact authenticated ChatGPT conversation reacquired, ScriptCat/userscripts restored, page returned to `tfAutogenic=ready` and `tfResidentElevated=true` without RDC repair.
- fresh post-restart machine command returned through the recovered userscript.
- complete assistant `TF_ACTION` → machine execution → automatic result user turn → next assistant turn proven live, with exactly one execution and one result turn.

Two live editor/runtime failures discovered during acceptance were repaired rather than hidden: cold MV3 startup needed a bounded handshake retry, and ChatGPT's hidden fallback textarea had to be excluded so result submission targets the visible ProseMirror editor.

## Current precise boundary

Not yet claimed:

- physical Windows reboot acceptance of at-logon recovery;
- a generic typed CDP/tab/evaluate action family exposed directly as `TF_ACTION` operations. Raw CDP is already resident-owned internally through the recovery helper, and arbitrary local commands are available through `exec`;
- transplantation of every useful donor-environment capability. Those are implementation extensions, not permission limits.
