# Torsionfield Reboot Supervisor

This component is deliberately separate from the ordinary Autogenic resident. Its job is to make a machine reboot a reversible continuation operation for active ChatGPT work rather than a browser-session gamble.

## Invariant

A reboot is blocked until every browser root that contains ChatGPT work is **observed through an executable control path** and every captured execution is quiescent or has produced a handoff.

A Chrome session file, window title, history record or remembered URL is discovery evidence only. It is never sufficient to mark a browser root safe.

## Components

```text
reboot_supervisor.py
    durable state + web management UI + strict reboot gate
          |
          +-- browser_roots.py
          |      process/profile discovery
          |      Chrome session evidence
          |      extension/CDP coverage classification
          |
          +-- browser_bridge.py :17375
          |      localhost command/result relay
          |         |
          |         +-- reboot_bridge.html/js
          |                privileged extension page inside each Chrome profile
          |                chrome.tabs + chrome.scripting + chrome.debugger
          |
          +-- reboot_cdp.mjs
                 fallback for intentionally CDP-enabled browser roots
```

The management UI is served at `http://127.0.0.1:17374/`.

## Browser-native inventory

When a Chrome profile already contains the Torsionfield unpacked extension with `tabs` and `scripting` permission, the supervisor copies only `reboot_bridge.html` and `reboot_bridge.js` into that unpacked extension directory and opens the extension page in that exact profile. It does not modify the normal service-worker core.

The bridge inventories every Chrome window and tab. For each ChatGPT tab it captures, without private ChatGPT HTTP APIs:

- exact URL, title, window/index, pinned/active/discarded state;
- conversation and project IDs;
- exact current composer/draft text;
- streaming state;
- recent user and assistant turns plus hashes;
- latest user/assistant hashes;
- branch-navigation controls and a branch signature;
- scroll position;
- Torsionfield/Autogenic page state;
- pending `TF_ACTION` indication.

The bridge can also stop a streaming response, escrow/restore a draft, request a reboot handoff, submit a state report to a selected ChatGPT tab, freeze/unfreeze a page through `chrome.debugger`, reopen tabs, and rehearse branch restoration in disposable duplicate tabs.

## Control priority

1. **Browser-native extension bridge** — preferred for ordinary user Chrome profiles because current Chromium may deliberately ignore remote-debugging flags on a default user-data directory.
2. **CDP** — accepted for dedicated profiles explicitly launched with a working debugging endpoint.
3. **Chrome session files** — discovery only. Any ChatGPT evidence here without live control makes the root `UNCOVERED` and blocks reboot.

The supervisor must never silently downgrade from 1 or 2 to 3 and retain a `safeForReboot=true` result.

## Preparation gate

`prepare_reboot()` performs:

```text
inventory all browser roots
→ refuse immediately if any ChatGPT root is uncovered
→ stop generation only where required
→ request handoffs for streaming / pending-action / automation-error tabs
→ recapture exact state
→ rehearse restoration through duplicate ChatGPT tabs
→ require every rehearsal and handoff to pass
→ persist immutable pre-reboot snapshot
→ set safeForReboot=true only after all gates pass
```

The physical reboot operation accepts only a recent persisted `prepared` manifest whose `safeForReboot` value is true.

## Restoration

The Scheduled Task `Torsionfield Reboot Supervisor` starts the supervisor at logon with highest privileges. A pending reboot manifest causes it to:

1. recover each saved browser root or launch it with its original executable/profile arguments and `--restore-last-session`;
2. restore the browser-native extension bridge;
3. match existing restored tabs before creating missing ones;
4. restore branch identity by assistant-response hash when branch controls are present;
5. restore exact draft text and scroll position;
6. restore active/pinned ordering;
7. recapture a post-restore inventory;
8. mark restoration failed rather than pretending success if any controlled root or required state cannot be reproduced.

## Rejected production technique: omnibox JavaScript

A Windows keyboard/CUA experiment proved that `javascript:` URLs could inspect a page without CDP. It was rejected for reboot-critical use. During chunked-state experimentation a dropped character caused Chrome to interpret the payload as a search/navigation. The affected ChatGPT tab was immediately restored through its Back history and its original conversation recovered, but the experiment demonstrated the wrong failure mode for a reboot safeguard.

Likewise, recursive raw UI Automation over Chromium's accessibility tree proved too slow/hang-prone on the tested browser build. Neither technique belongs in the production reboot gate.

## Status

Source, static checks and protocol/unit tests live on `chatgpt/autogenic-runtime-v0`. Live Windows acceptance must still prove the extension page can be added to each discovered active Torsionfield Chrome profile, inventory all current ChatGPT tabs, rehearse branch/draft restoration, survive a physical reboot, and produce an equal post-reboot state inventory. Until that evidence exists, the physical reboot gate remains closed.

Local-machine automation must always be announced visibly immediately before Torsionfield or the assistant takes control of browser, process, filesystem or desktop state.
