# Browser Runtime Donor Radar — 2026-08-15

This document records the GitHub capability-mining pass performed for Torsionfield/Autogenic browser continuity, profile isolation, semantic browser control, and ChatGPT-state persistence.

The goal is not to choose a framework. External repositories are capability donors. We identify mechanisms that prevent Torsionfield from reinventing work that already exists, then transplant the smallest useful behavior onto the resident + extension + userscript substrate.

## Executive conclusion

A persistent browser profile is necessary but not sufficient for ChatGPT continuity.

There are four different state layers and they must not be conflated:

1. **Browser profile / identity state** — cookies, localStorage, IndexedDB, extensions, browser preferences, account identity, profile directory.
2. **Control-session state** — which AI/controller owns which tabs, active-tab cursor, snapshot namespace, lease/priority, concurrency isolation.
3. **ChatGPT application state** — project, conversation, branch, model/tool selection, composer bytes, streaming/error state, message hashes, pending TF action, context-terminal/handoff state.
4. **Run/continuation state** — objective, action journal/idempotency, last completed action, checkpoint, resume/retry/parent links, artifacts, next executable step.

SuperchargeBrowser is useful for layer 1½: named workspaces, tab groups, and rolling browser-session snapshots. It does **not** by itself preserve layer 3 or 4. `graph-memory/browser-mcp` is a strong donor for layers 1 and 2. Vessel is a strong donor for layer 4. Browser Harness + browser-skills + Unbrowse are strong donors for semantic knowledge that sits across layers 2–4.

## Search method

Search was deliberately graph-shaped rather than keyword-only:

- seed repositories: SuperchargeBrowser, browser-mcp, agent-browser;
- inspect repository topics and implementation vocabulary;
- follow narrow topics exhaustively when small enough (`persistent-browser` was small enough to inspect every result);
- follow broader topics selectively by unique capability, recency, and implementation evidence;
- search concept phrases when GitHub topics did not exist (`semantic-instructions` did not emerge as a useful literal topic);
- deep-read source/docs for mechanisms that would change Torsionfield architecture.

High-signal topic/vocabulary neighborhoods:

`persistent-browser`, `browser-agent`, `agent-browser`, `browser-automation`, `ai-browser-automation`, `browser-profiles`, `accessibility-tree`, `browser-controller`, `agent-skills`, `agentskills`, `browser-skills`, `domain-skills`, `record-and-replay`, `computer-use`, `chrome-extension`, `cdp`, `mcp-server`.

The useful replacement for the phrase **semantic-instructions** is a five-part taxonomy:

- semantic perception — AX/accessibility trees and stable refs;
- semantic recipes — site/domain skills and deterministic interaction recipes;
- semantic compilation — learn a browser workflow once, compile it into a reusable route/API operation;
- semantic state — page schemas, intent, expected content, agent hints, run ledger;
- semantic control — profile manager + independent controller sessions + durable target identity.

## P0 donors — transplant now

### graph-memory/browser-mcp

**Capability:** one browser manager per persistent profile, multiple independent MCP/control sessions over that shared profile.

Important behavior:

- one BrowserManager owns the shared BrowserContext/login state for a profile;
- each BrowserSession has its own active-tab cursor and named snapshot namespace;
- sessions intentionally sharing a profile share authentication without clobbering each other's active tab;
- `/mcp/<profile>` is a clean profile-selection boundary;
- session TTL/tab TTL and manager lifecycle are explicit.

**Torsionfield transplant:** introduce `ProfileRegistry` and `ControlSessionRegistry`. Stop treating browser process, profile, and agent session as the same object.

### browser-use/browser-harness

**Capability:** generic browser interaction mechanics separated from accumulated site-specific domain knowledge.

Important behavior:

- direct real-browser CDP surface;
- editable helper code rather than a fixed closed command set;
- generic `interaction-skills` for mechanics;
- `domain-skills/<site>/...` as a durable learning corpus;
- when domain skills are enabled, the agent reads matching site knowledge before inventing a new approach;
- accessibility-first target identification and postcondition verification;
- actual repository contains a substantial field-tested domain-skill corpus, not merely a proposed architecture.

**Torsionfield transplant:** create a writable `skills/browser/generic/` and `skills/browser/domains/<host>/` store. Successful discoveries should become local executable knowledge immediately.

### bettyguo/browser-skills

**Capability:** a compact executable SKILL.md recipe format for common browser patterns.

Important behavior:

- deterministic selector/semantic path first, scoped vision fallback second;
- explicit `When to invoke`, executable `Recipe`, `Success criteria`, `When NOT to use`, `Known failures`;
- metadata for URL patterns, DOM markers, measured flake rate, exercised sites, cost budget, sensitivity;
- assertions/postconditions are part of the recipe contract;
- skill results include deterministic path, duration, model calls, token cost, trace, warnings;
- versioning semantics for selector tweaks versus recipe-shape changes;
- weekly real-site benchmark and stale-selector issue creation.

**Torsionfield transplant:** use this as the base shape of `TF_BROWSER_SKILL/1`, while allowing richer page-state/AX predicates and direct resident operations.

### unbrowse-ai/unbrowse

**Capability:** browser interaction as a discovery/compiler step, not a permanent tax.

Important behavior:

- observe first-party API/workflow requests during real browsing;
- compile successful workflow edges into reusable indexed routes/contracts;
- resolve + execute cached routes directly on repeat work;
- browser remains available for login, consent, UI-only states, and cache misses;
- `sync` and `close` create checkpoints/index material;
- agent skill explicitly teaches “one capture on a miss, then reuse,” preventing repeated manual browser rediscovery;
- semantic route metadata includes intent, action kind, inputs, examples, and endpoint descriptions.

**Torsionfield transplant:** add a `CapabilityCompiler`: successful browser procedures can graduate into direct extension/resident/network operations when their semantic pre/postconditions are understood. Browser becomes discovery/fallback, not the only execution plane.

### unmodeled-tyler/vessel-browser

**Capability:** durable agent/browser run ledger and semantically annotated browser state.

Important behavior:

- RunRecord with source, goal, status, timestamps, initial/final tab, last completed action, output/error;
- optional conversation/checkpoint/retry/resume/parent/flow identifiers;
- event stream for run/action/checkpoint/navigation/human-steering lifecycle;
- persistent conversation threads and run inbox;
- active runs recovered as `interrupted`, not silently forgotten;
- annotated bookmarks with `intent`, `expectedContent`, `keyFields`, `agentHints`;
- page-schema inference and workflow-flow tracking.

**Torsionfield transplant:** create a durable `RunLedger` below the ChatGPT tab layer. A tab can disappear while a run remains addressable and resumable.

## P1 donors — important supporting mechanisms

### floomhq/openbrowser

**Capability:** identity/profile/lease/browser-slot separation and profile replicas.

Important behavior:

- named persistent identities/profiles;
- browser slots leased to work;
- replicas allow parallel browser processes without making multiple Chrome roots directly mutate the same live profile directory;
- explicit policy for max parallel sessions.

**Transplant:** `ProfileAttachMode = exclusive | shared-session | replica`. Same identity can serve multiple workers without unsafe direct profile-directory sharing.

### leeguooooo/chrome-use

**Capability:** many AI sessions over one already logged-in real Chrome using native messaging and isolated tab groups.

Important behavior:

- extension + native-messaging bridge instead of requiring a debug port;
- each agent session gets a colored, command-isolated Chrome tab group;
- stable session IDs can be derived from runner/thread identity;
- session list/stop/prune/status/handoff/resume are first-class;
- extension survives Chrome restart; worker daemon can be replaced while tabs remain;
- skill instructions are versioned alongside the binary.

**Transplant:** make control-session identity visible inside Chrome and independent of browser identity; support handoff/resume as ordinary session operations.

### vercel-labs/agent-browser

**Capability:** mature session/profile registry, existing-browser/CDP attach, compact accessibility snapshots, profile reuse/import, broad testing surface.

**Transplant:** borrow profile import/copy and session-registry semantics where they are simpler than our current browser-root heuristics. Preserve Torsionfield's privileged extension route as an additional execution plane.

### kunchenguid/chrome-devtools-axi

**Capability:** generation-scoped semantic refs and deliberately agent-ergonomic browser output.

Important behavior:

- AX refs include generation prefixes (`gN:*`);
- a ref from an older snapshot fails loudly as `STALE_REF` rather than silently targeting the wrong element;
- state-changing actions are followed by explicit verification;
- response includes contextual next-step hints;
- persistent local bridge keeps the browser session alive across CLI invocations;
- optional agent SessionStart hook surfaces ambient browser state.

**Transplant:** every Torsionfield semantic target should carry a snapshot generation and target identity. Stale semantic refs must be impossible to execute silently.

### freshtechbro/opendevbrowser

**Capability:** target-aware execution model and broad browser review/diagnostic contract.

Important behavior:

- `snapshot -> refs -> actions` accessibility-first model;
- refs resolve through backend node identity;
- managed, CDP, and extension-backed session modes;
- target-scoped concurrency key `(sessionId,targetId)`: same target FIFO, different targets can run concurrently;
- persistent headed profiles and extension reuse of live tabs;
- review/session-inspector/debug traces as explicit evidence surfaces;
- bundled skills sync into multiple agent hosts.

**Transplant:** scheduling should be target-scoped, not globally serialized. Per-target action queues plus a profile/session lease model give safe concurrency without forbidding concurrency.

### hmmhmmhm/ax-grep

**Capability:** compact semantic evidence and explicit machine-readable handoff/escalation.

Important behavior:

- semantic/accessibility-like tree can be produced before opening a live browser;
- executor decision is one of `return | execute | browser | stop`;
- handoff object contains next command/read/browser target rather than free-form narrative;
- browser HTML can be captured and fed back into the semantic extractor.

**Transplant:** add an `ObservationDisposition` to Torsionfield: `ANSWER_FROM_EVIDENCE | EXECUTE_HELPER | OPEN_BROWSER | STOP`. This avoids launching heavy browser control when static/local semantic evidence is enough.

### ugarchance/record-and-replay-skill

**Capability:** demonstration -> evidence stream -> semantic reusable skill.

Important behavior:

- browser recording produces action events with multiple selector candidates and periodic DOM/trace checkpoints;
- recording is treated as evidence of intent, not a pixel script;
- generated replay uses semantic locators plus verification;
- persistent profile retains login between recordings;
- lightweight event/context stream deliberately preferred over continuous video.

**Transplant:** Torsionfield should be able to observe a successful human or AI repair once and synthesize/update a domain skill from the evidence automatically.

## P2 / situational donors

### SuperchargeBrowser/supercharge-browser

**Useful:** browser workspace/session timeline, named workspaces, tab suspension/discard, session restore UX.

**Not enough for ChatGPT:** browser tabs and workspace metadata are not ChatGPT application semantics. Use its timeline/workspace UX ideas, not as the persistence substrate.

### alibaba/page-agent

**Useful:** a GUI agent can live *inside* the webpage as JavaScript, with text/DOM rather than screenshots; extension only becomes necessary for multi-page reach.

**Transplant:** validates ScriptCat/page-local agent logic as a legitimate fast plane. Torsionfield should execute page-local semantics in-page when privilege is unnecessary, escalating to extension/resident only when needed.

### AVANT-ICONIC/Talox

**Useful:** combined AX/DOM/console/network/visual state; self-healing semantic resolution; per-site `SKILL.md` strategy creation.

**Transplant:** structured multi-channel observation envelope and `skill create` behavior.

### browser-use/desktop

**Useful:** separates daily-driver Chrome from agent browser; ports login cookies into agent Chromium and builds on Browser Harness.

**Caveat:** cookie transfer is identity continuity, not complete application-state transfer. localStorage/IndexedDB/extension/app branch state need separate treatment.

### lightpanda-io/agent-skill

Useful as evidence that browser runtimes are increasingly distributed as agent skills rather than only MCP servers. Lightpanda itself is interesting for cheap non-visual page execution, but it is not the source of truth for authenticated live Chrome state.

### BrowserOperator/browser-operator-core

Large integrated AI-browser platform with multi-agent/MCP ambitions. Useful as ecosystem evidence and occasional donor, but its architecture is too broad and less recently active than the smaller focused donors above. Do not import wholesale.

## Target Torsionfield architecture

```text
ProfileRegistry
  profile_id
  browser_family/channel
  executable
  user_data_dir + profile_directory
  identity/account label
  extension set/hash
  attach_mode: exclusive | shared-session | replica
  restore policy
  profile manager

ProfileManager (one per profile/replica)
  browser process/context
  tab registry
  profile lock/replica lifecycle
  passive event/network/console rings
  run ledger

ControlSession (one per AI/controller)
  session_id
  profile_id
  active_tab cursor
  snapshot namespace/generation
  lease + priority
  visible Chrome tab group / ownership marker

ChatGPTConversationState
  project_id
  conversation_id
  branch_signature
  model + selected tools
  composer bytes/hash
  streaming/error/context-terminal
  message counts/latest hashes
  pending TF action + idempotency state
  domain-skill refs
  latest checkpoint

RunRecord
  run_id
  source + goal + status
  conversation/tab refs
  action event journal
  checkpoint/resume/retry/parent refs
  artifacts + result evidence
  exact next executable step

BrowserSkillRegistry
  generic interaction skills
  domain skills
  observed success/failure evidence
  version + flake metrics
  semantic pre/postconditions
  compiled direct capability, when available
```

## Profile-isolation decision

Profile isolation is now a first-class requirement.

Rules:

1. `Profile` is an identity/storage boundary, never an agent-session identifier.
2. `ControlSession` is a disposable/transferable controller view onto a profile.
3. Multiple sessions may intentionally share one ProfileManager while retaining independent active-tab and snapshot namespaces.
4. Different accounts/identities use different profile directories.
5. Parallel **browser processes** for one identity use replicas/snapshots rather than blindly sharing one mutating Chrome profile directory.
6. A browser restart must reconstruct ProfileManagers first, then ControlSessions, then app/run state.
7. ChatGPT app continuation is restored from `ChatGPTConversationState + RunRecord`, not inferred solely from Chrome's restored URL.

## ChatGPT-specific semantic skill set — immediate target

Create `skills/browser/domains/chatgpt.com/` with at least:

- `conversation-identify`
- `branch-identify-and-restore`
- `composer-read-write-verify`
- `generation-state`
- `message-delivery-state`
- `context-terminal-rollover`
- `model-and-tool-state`
- `project-conversation-routing`
- `pending-tf-action-reconcile`
- `conversation-checkpoint`
- `conversation-handoff`

Each skill should have deterministic semantic probes first, explicit postconditions, known failure modes, versioned selectors/state signatures, and evidence-backed fallbacks.

## Capability-compiler target

For repeated ChatGPT/browser operations:

```text
successful browser operation
-> capture network/DOM/AX/action evidence
-> infer semantic precondition + operation + postcondition
-> determine whether operation can be performed directly
-> if yes: compile extension/resident/network capability
-> attach provenance + version + tests
-> next use tries compiled capability first
-> browser semantic skill remains verification/fallback
```

This is the most important anti-reinvention loop from the research pass.

## Research radar policy

Do not repeat this whole search manually every time.

Maintain a machine-readable donor radar containing:

- repository;
- topics/neighbor terms;
- last activity date;
- unique capability;
- overlap with current Torsionfield;
- transplant priority;
- inspected files/commit;
- next recheck trigger.

Future searches should start from the current high-signal topics plus the topics newly discovered on repositories that have changed since the last scan. Narrow topics should be enumerated completely; huge topics should be sampled by recency + unique mechanism + source evidence.

A repository should be promoted from `interesting` to `donor` only after source/docs demonstrate the claimed mechanism.

## Current transplant queue

### P0

1. `ProfileRegistry + ProfileManager + ControlSession` split from browser-mcp/openbrowser/chrome-use.
2. `RunLedger` based on Vessel's durable run/event model.
3. `TF_BROWSER_SKILL/1` format based on Browser Harness + browser-skills.
4. ChatGPT domain-skill corpus generated from current Torsionfield adapters and live evidence.
5. `CapabilityCompiler` inspired by Unbrowse: learn once, direct/replay thereafter.

### P1

6. Generation-scoped semantic refs and hard stale-ref failure.
7. Target-scoped action queues `(session,target)`.
8. Profile replicas for same-identity parallel browser processes.
9. Record-and-replay -> automatic skill synthesis.
10. Compact ObservationDisposition / machine-readable handoff envelope.

### P2

11. Workspace/time-travel UI inspired by SuperchargeBrowser.
12. Page-schema inference + agent-hint bookmarks inspired by Vessel.
13. Lightweight pre-browser semantic extraction inspired by ax-grep/Lightpanda.

## Do not reinvent

Before implementing any of the following from scratch, re-check the donor listed beside it:

- shared-profile multi-agent isolation -> browser-mcp, chrome-use;
- profile replicas -> openbrowser;
- real-Chrome extension/native-message relay -> chrome-use;
- stale semantic refs -> chrome-devtools-axi;
- deterministic browser recipe format -> browser-skills;
- site-specific learned browser knowledge -> browser-harness;
- browser workflow -> direct API operation -> Unbrowse;
- durable run/checkpoint/event state -> Vessel;
- record demonstration -> skill -> record-and-replay-skill;
- target-aware concurrent command scheduling -> OpenDevBrowser;
- workspace/session history UI -> SuperchargeBrowser;
- compact semantic pre-browser handoff -> ax-grep.
