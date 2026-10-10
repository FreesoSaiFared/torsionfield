#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT/tools/cinematic-matter-engine/Cargo.toml"
cargo build --manifest-path "$MANIFEST" --release --target wasm32-unknown-unknown
SRC="$ROOT/tools/cinematic-matter-engine/target/wasm32-unknown-unknown/release/cinematic_matter_geometry.wasm"
DST="$ROOT/public/cinematic-matter/geometry.wasm"
cp "$SRC" "$DST"
sha256sum "$DST"
wc -c "$DST"
