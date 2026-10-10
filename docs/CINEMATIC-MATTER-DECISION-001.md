# Cinematic Matter / Implementation decision 001

Status: **EXPERIMENTAL / NOT LAUNCHED**. Managerial decision, 2026-10-10.

## Product hypothesis
A reader can examine and change an explicitly modeled assumption while a document performs its argument, and thereby understand the claim, its limitations and evidence better than from an ordinary interactive article.

This is **not** a proposal to replace HTML with video. HTML remains the authoritative, accessible and indexable document. Graphics are computed projections from stable semantic objects. Provenance and lineage survive visual topology changes. See prototype under `public/cinematic-matter/`.

## Three cooperating contracts
1. **Director** controls timing, emphasis, narration cues, expressive motion and scene constraints.
2. **Simulation** maps narrative time, assumption values, layout and seeded interaction state to deterministic geometries and computable model outputs.
3. **Semantic contract** types a relation as `defines`, `derives`, `cites`, `disputes`, `hypothesizes`, or `illustrates`. It prohibits drawing an artistic association as if it were evidential support.

Expressive matter may be aesthetically free; referential matter always points to a versioned document object. A merge may have many ancestors, and a split may have many descendants. Unknown source reattachment after revision must be flagged, never silently assumed.

## First bounded vertical slice
- One original HTML article about a **fictional** exponential-decay toy model; no fictional results are claimed as science.
- Three claims and two source fixtures; one extrapolation disputed on a second revision.
- Three stable curve actors that originate from DOM Range/element geometry, transition into a human-like figure, and then represent an inspectable argument field before returning to text.
- Interventions: narrative seek, editable model damping λ, revision selection, provenance inspection and original-text reveal.
- Voice: optional browser `speechSynthesis` following a user gesture; ElevenLabs or AI Studio are separately evaluated future adapters, **not assumed** in the pilot.

## Invariants
- `Scene = F(t, v, θ, I, L)`. Rendering at the same inputs must produce the same result within tolerance; seeking reconstructs rather than reverse-integrates physics.
- An assumption may change only modeled quantities. It cannot automatically manufacture empirical facts or sources.
- Read mode must preserve selection, links, accessible order and search indexing without JS, animation or audio.
- Watch mode must never autoplay audible speech; Investigate mode must pause and reveal a stable passage anchor.
- An expressionist transformation does not confer source authority. Labels and dotted/solid relations preserve uncertainty.

## Release gates
1. Syntax and static render; no browser errors. Read mode works on mobile and with reduced motion.
2. Browser tests: deterministic seeking; λ changes calculated output and actor geometry; revision changes dispute status; filament selection reveals the original claim and source; reconstruction restores HTML.
3. Keyboard, screen-reader semantics, selection and responsive layout remain usable.
4. Do not modify the production homepage until the pilot is mechanically accepted and editorially reviewed.
5. Real articles require versioned passage hashes and explicit uncertainty when an anchor cannot be reattached.

## Test against a normal article
Give matched readers identical research claims through (A) an ordinary interactive document and (B) Cinematic Matter. Measure accuracy identifying disputed relationships, source-finding time, what assumptions establish, cognitive load and mistaken causal inference. Expand only if comprehension improves; do not optimize for spectacle.

## Build stages
P0: static experimental route, provenance inspection and model intervention.
P1: interactive browser acceptance; real text-range contours and accessibility.
P2: one-to-many geometry lineage, repeatable interaction replay and versioned anchors.
P3: authored cinematic grammar, synchronized narration and compositional polish.
P4: reuse the engine for a second article. Defer WASM/WebGPU until measured profiling justifies them.

## Verified state / unresolved
2026-10-10: Files written under `public/cinematic-matter/`. Node syntax validation passed and headless Chromium rendered the static reading surface, retained in `artifacts/cinematic-matter/read-mode.png`. The first browser-test run exposed a test-harness failure during simulated filament selection. An attempted rerun was blocked before execution. The interaction acceptance suite is **not passed** and no production deployment has been performed.

## Visual grammar
Deliberately depart from OpenAI ChatGPT website defaults: architectural editorial grid; ivory, near-black and one restrained signal red; compact controls; precise hierarchy; geometry subordinate to the document. Maintain accessibility and responsiveness.

## Stop condition
If readers do not gain a measurable understanding or evidence-navigation advantage over normal interactive articles, keep this as an optional experimental treatment rather than shipping a universal engine.

## CM-002: Rust / WebAssembly transformation engine — 2026-10-10
A more ambitious engine replaces the three decorative SVG strokes as the main cinematic geometry. `tools/cinematic-matter-engine/src/lib.rs` compiles to `public/cinematic-matter/geometry.wasm` with `build.sh`. The browser samples pixels from actual highlighted HTML glyphs using per-character DOM Ranges, sends normalized source coordinates and claim identity into the module, then renders its deterministic curve field on Canvas. In the desktop test: 696 strands × 26 vertices = **18,096 vertices/frame**; WASM binary **30,976 bytes**. Each source actor maintains its associated claim and provenance. Staged motion forms a dancing human silhouette, then orbital claim structures, and reconstructs the originating text geometry.

The mathematical fields include animated Bézier skeletons, seeded curl-like turbulence, staged splines, evidence-graph morphing, λ-sensitive deformation and direct pointer forces. These are actual Rust/WebAssembly computations, not a JavaScript-only imitation or a prerendered video. For unsupported WASM environments the earlier semantic SVG can remain visible.

**Browser verification:** `tests/cinematic-matter-wasm.mjs` passed nine checks in headless Chromium, including WASM loading under a narrowly scoped `wasm-unsafe-eval` CSP, glyph seeding, five distinct phases, deterministic seeking, equation-and-geometry counterfactuals, versioned disputed links, direct pointer interaction and HTML reconstruction. Receipt: `artifacts/cinematic-matter/wasm-test-receipt.json`; screenshots: `wasm-4s.png`, `wasm-8s.png`, `wasm-13s.png` in the same artifacts directory.

**Limitations:** This is a bounded live experiment, not a validated scientific publishing platform. Its observations are intentionally fictional, the glyphs are raster-sampled rather than exact vector font outlines, and the dancer and graph are authored mathematical attractors rather than a generally capable semantic scene composer. Accessibility, mobile performance and comprehension testing require further independent acceptance before making it the homepage presentation.

## Live experimental deployment verification
CM-002 has been deployed **only** at `https://torsionfield.de/cinematic-matter/`; it does not replace the blog homepage. Cloudflare version `322a67d6-7a4c-4020-9319-9400b7acc743`. Public HTTP checks returned 200 for the unchanged homepage, runtime, new experiment, JavaScript and its 30,976-byte `application/wasm` binary. CSP retains the standard policy everywhere else and enables `wasm-unsafe-eval` solely for the experimental path. The D1 registration binding remains attached.

Using the public URL, headless Chromium loaded the WASM module and repeated all nine behavior checks successfully, including direct animated-geometry hit-testing. The `CM_URL` environment variable in the test harness selects the production route for independent regression testing. Do not equate this with completed mobile, visual, accessibility or scientific comprehension acceptance.

## CM-002 editorial legibility revision — 2026-10-10
The mathematical example now includes a plain-language ringing-bell explanation and a persistent three-color legend. The Canvas filament rendering defaults to **1.7×** its original stroke width, with a live **0.7×–3.2×** thickness control; the underlying Rust/WASM trajectory calculation and semantic identities are unchanged. This is a presentation adjustment, not evidence of improved comprehension. Validate with the browser acceptance suite before release.
