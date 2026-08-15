#!/usr/bin/env python3
"""Disposable mailbox worker for Torsionfield Chromium Mesh.

A worker is configured for exactly one admitted build identity. It atomically
claims action bundles from spool/incoming, executes them through mesh.run_bundle,
and publishes result bundles under spool/results. No complete Chromium checkout
is required on the worker: each action bundle carries its declared input closure.
"""

import argparse
import json
import os
import time
import traceback
from pathlib import Path

import mesh


def ensure_dirs(spool: Path):
    for name in ("incoming", "claimed", "results", "done", "failed"):
        (spool / name).mkdir(parents=True, exist_ok=True)


def claim_one(spool: Path, worker_id: str):
    ensure_dirs(spool)
    for src in sorted((spool / "incoming").glob("*.tgz")):
        dst = spool / "claimed" / f"{worker_id}--{src.name}"
        try:
            os.replace(src, dst)
            return dst, src.name
        except FileNotFoundError:
            continue
    return None


def process_one(spool: Path, worker_id: str, build_id: str, worker_root: Path):
    claimed = claim_one(spool, worker_id)
    if claimed is None:
        return None
    bundle, original_name = claimed
    stem = original_name[:-4] if original_name.endswith(".tgz") else original_name
    result_tmp = spool / "claimed" / f"{worker_id}--{stem}.result.tmp.tgz"
    result_final = spool / "results" / f"{stem}.result.tgz"
    receipt = {
        "schema": "TORSIONFIELD_CHROMIUM_MESH_WORKER/1",
        "worker_id": worker_id,
        "build_id": build_id,
        "action_bundle": original_name,
    }
    try:
        result = mesh.run_bundle(bundle, result_tmp, worker_id, build_id, worker_root)
        receipt["result"] = result
        if not result.get("ok"):
            raise RuntimeError(f"action returned non-success: {result}")
        os.replace(result_tmp, result_final)
        receipt["result_bundle"] = result_final.name
        receipt["status"] = "DONE"
        done = spool / "done" / f"{worker_id}--{original_name}"
        os.replace(bundle, done)
        (spool / "done" / f"{worker_id}--{stem}.receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True)
        )
        return receipt
    except Exception as exc:
        receipt["status"] = "FAILED"
        receipt["error"] = str(exc)
        receipt["traceback"] = traceback.format_exc()
        try:
            result_tmp.unlink(missing_ok=True)
        except Exception:
            pass
        failed = spool / "failed" / f"{worker_id}--{original_name}"
        if bundle.exists():
            os.replace(bundle, failed)
        (spool / "failed" / f"{worker_id}--{stem}.error.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True)
        )
        return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spool", type=Path, required=True)
    ap.add_argument("--worker-root", type=Path, required=True)
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--build-id", required=True)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-seconds", type=float, default=1.0)
    args = ap.parse_args()

    ensure_dirs(args.spool)
    processed = 0
    while True:
        receipt = process_one(
            args.spool, args.worker_id, args.build_id, args.worker_root
        )
        if receipt is not None:
            processed += 1
            print(json.dumps(receipt, sort_keys=True), flush=True)
        if args.once:
            return 0 if receipt is None or receipt.get("status") == "DONE" else 1
        if receipt is None:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
