# Torsionfield Chromium Mesh v0

This directory is the first executable mailbox/CAS substrate for distributing one Chromium build graph over disposable VMs.

It does **not** claim a distributed Chromium build yet. It proves the transport and admission primitive that such a build needs:

- immutable build identity;
- content-addressed inputs and outputs;
- self-contained action bundles for network-isolated VMs;
- per-worker execution sandboxes;
- hash-verified result import;
- mixed-worker object linking;
- hard rejection of an object/action from another build identity.

## Why action sharding, not repository sharding

A Chromium compile action may consume a `.cc` file under `chrome/`, headers under `base/`, generated Mojom outputs and files under `third_party/`. The distributable unit is therefore a hermetic build action plus its input closure, not a top-level source directory.

`mesh.py` implements a minimal mailbox form of REAPI semantics. A future live transport can map the same action/result model to Siso/REAPI without changing the identity or evidence rules.

## Smoke proof

```bash
python3 tools/chromium-mesh/mesh.py demo --root /tmp/chromium-mesh-demo
cat /tmp/chromium-mesh-demo/DEMO_RESULT.json
```

The demo compiles three translation units across two worker roots, imports their objects into the coordinator CAS, links a binary from objects produced by both workers, executes it (`42`), and verifies that a deliberately wrong build ID is rejected.

## Build identity

Every admitted action is bound to a digest over:

- Chromium source revision;
- DEPS digest;
- toolchain digest;
- sysroot digest;
- GN args digest;
- target OS/CPU;
- local patch-set digest.

This is deliberately stronger than checking filenames or object timestamps. Objects from two builds cannot be silently mixed.

## Mailbox flow

```text
coordinator CAS
   ↓ create action bundle
TF-CHROMIUM-ACTION-*.tar.gz
   ↓ transfer by any available channel
worker local CAS + sandbox
   ↓ compile
TF-CHROMIUM-RESULT-*.tar.gz
   ↓ transfer back
coordinator verifies action digest, build identity and every output hash
```

The bundle is self-contained for the declared action, so a worker does not need a complete Chromium checkout.

## Full-Chromium integration boundary

The next executable layer is a GN/Siso action extractor/adapter:

1. generate one pristine Chromium build graph for the pinned source revision;
2. export compile/codegen actions with exact command lines and file input closures;
3. convert eligible actions to this mesh action format (or directly to REAPI when live connectivity exists);
4. return `.o`, `.dwo`, generated headers/resources and other declared outputs into the coordinator CAS;
5. preserve local-only actions for operations that are not yet hermetic;
6. link the complete `chrome` target from admitted outputs;
7. launch the resulting browser and run the existing CDP acceptance;
8. repeat for Linux ARM64 cross-build and the debug configuration.

The Anything Analyzer Chromium patch gate remains closed until that pristine complete-browser path passes.

## Real Chromium-source probe

When a Chromium source root is available, the mesh can prove that actual Chromium code survives the mailbox boundary without requiring a full checkout on either worker. The current probe uses two self-contained `base/types` headers:

```bash
python3 tools/chromium-mesh/mesh.py chromium-header-demo \
  --root /tmp/chromium-header-mesh \
  --source-root /path/to/chromium/src \
  --source-revision <exact-commit>
```

It compiles code instantiating `base::PassKey` on one worker and `base::projected_value_t` on another, then links their objects through a third action. This is **real Chromium source input**, but it is intentionally not described as a real GN/Siso action or a Chromium product build.
