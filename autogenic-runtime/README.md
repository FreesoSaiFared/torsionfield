# Torsionfield Autogenic Runtime v0

This directory is the first executable vertical slice of the permanent privileged-runtime architecture. It is deliberately small: one always-running resident, one Chrome bridge, one ScriptCat userscript, and installers for Windows and Linux.

## Runtime shape

```text
ChatGPT conversation
  ↕ ScriptCat userscript / TF_ACTION blocks
Chrome MV3 bridge
  ↕ authenticated loopback HTTP
Torsionfield privileged resident (127.0.0.1:17373)
  ↕
processes · filesystem · browser lifecycle · generated helpers
```

The resident is the continuity anchor. Restarting Chrome must not destroy machine control. ScriptCat and the extension are programmable browser-side surfaces, not the privilege boundary.

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

## Chat action protocol

An assistant message can request a machine operation using:

```text
[[TF_ACTION/1
{"id":"probe","op":"exec","args":{"shell":"whoami"}}
[[/TF_ACTION]]
```

The ScriptCat bridge executes it through the resident and submits a `TORSIONFIELD MACHINE RESULT /1` turn back into the same ChatGPT conversation. The assistant can then continue from observed state.

The userscript also watches for known human-handoff failure language. When it sees one, it submits an autonomy-intercept turn that explains the executable action protocol rather than asking the human to perform the machine step.

## Windows

Run `install/install-windows.ps1` from elevated PowerShell. The installer intentionally has no reduced-privilege fallback. It creates `Torsionfield Autogenic Resident` as an at-logon Scheduled Task with `RunLevel Highest`, starts it, verifies `/v1/health`, and generates `bootstrap-browser.ps1` for a managed Chrome profile with the unpacked bridge loaded.

## Linux / internal VM

Run `sudo install/install-linux.sh`. It installs a root `systemd` service and verifies resident health. The resident can then launch a managed Chromium profile; VM/browser acceptance should use the already-proven ScriptCat/CDP procedure from the Internal VM master guide.

## Current proof boundary

The resident and its `exec` + filesystem write/read path are locally smoke-tested in the ChatGPT Debian execution environment. JavaScript syntax checks pass for the userscript and extension. Windows Scheduled Task installation, actual local Chrome restart/reacquisition, ScriptCat installation of the generated userscript, and the full ChatGPT → TF_ACTION → resident → result-return loop still require acceptance on the designated Windows machine.
