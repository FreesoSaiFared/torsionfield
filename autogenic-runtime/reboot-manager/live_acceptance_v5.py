#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

import browser_roots_v5 as br

HERE = Path(__file__).resolve().parent
BRIDGE_SOURCE = HERE / "extension_bridge"
CDP_HELPER = HERE / "reboot_cdp.mjs"
STATE_ROOT = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Torsionfield" / "RebootSupervisor"
STATE_ROOT.mkdir(parents=True, exist_ok=True)
OUT = STATE_ROOT / "live-acceptance-v5.json"


def atomic(value: dict) -> None:
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT)


def root_summary(record: dict, elapsed: float) -> dict:
    tabs = record.get("tabs") or []
    return {
        "rootId": record.get("rootId"),
        "pids": record.get("pids"),
        "profilePath": record.get("profilePath"),
        "debugPort": record.get("debugPort"),
        "extension": {
            "id": (record.get("extension") or {}).get("id"),
            "name": (record.get("extension") or {}).get("name"),
            "version": (record.get("extension") or {}).get("version"),
        }
        if record.get("extension")
        else None,
        "coverage": record.get("coverage"),
        "covered": bool(record.get("covered")),
        "errors": record.get("errors") or [],
        "elapsedSeconds": round(elapsed, 3),
        "tabCount": len(tabs),
        "chat": [
            {
                "id": tab.get("id"),
                "windowId": tab.get("windowId"),
                "index": tab.get("index"),
                "frozen": bool(tab.get("frozen")),
                "discarded": bool(tab.get("discarded")),
                "autoDiscardable": tab.get("autoDiscardable"),
                "active": bool(tab.get("active")),
                "status": (tab.get("state") or {}).get("status"),
                "streaming": bool((tab.get("state") or {}).get("streaming")),
                "pendingAction": bool((tab.get("state") or {}).get("pendingAction")),
                "draftLength": len((tab.get("state") or {}).get("composerText") or ""),
                "conversationId": (tab.get("state") or {}).get("conversationId"),
                "projectId": (tab.get("state") or {}).get("projectId"),
                "branchSignature": (tab.get("state") or {}).get("branchSignature"),
                "captureError": tab.get("error"),
            }
            for tab in tabs
        ],
        "activation": (record.get("inventory") or {}).get("activation") or [],
        "restoreErrors": (record.get("inventory") or {}).get("restoreErrors") or [],
    }


def inspect(root: dict) -> dict:
    started = time.time()
    try:
        record = br.root_inventory(root, BRIDGE_SOURCE, CDP_HELPER, auto_bridge=True)
        return root_summary(record, time.time() - started)
    except Exception as exc:
        return {
            "rootId": root.get("rootId"),
            "pids": root.get("pids"),
            "profilePath": root.get("profilePath"),
            "debugPort": root.get("debugPort"),
            "coverage": "exception",
            "covered": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "elapsedSeconds": round(time.time() - started, 3),
            "tabCount": 0,
            "chat": [],
        }


def main() -> int:
    roots = br.discover_roots()
    state = {
        "schema": "TF_LIVE_REBOOT_ACCEPTANCE/5",
        "startedAt": time.time(),
        "complete": False,
        "safeCoverage": False,
        "roots": [],
    }
    atomic(state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(roots))) as pool:
        futures = {pool.submit(inspect, root): root for root in roots}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            state["roots"].append(result)
            atomic(state)
    state["roots"].sort(key=lambda item: item["rootId"])
    state["complete"] = True
    state["completedAt"] = time.time()
    state["elapsedSeconds"] = round(state["completedAt"] - state["startedAt"], 3)
    state["safeCoverage"] = bool(state["roots"] and all(root.get("covered") for root in state["roots"]))
    state["chatTabCount"] = sum(root.get("tabCount", 0) for root in state["roots"])
    state["streamingCount"] = sum(
        1 for root in state["roots"] for tab in root.get("chat", []) if tab.get("streaming")
    )
    state["pendingActionCount"] = sum(
        1 for root in state["roots"] for tab in root.get("chat", []) if tab.get("pendingAction")
    )
    state["draftCount"] = sum(
        1 for root in state["roots"] for tab in root.get("chat", []) if tab.get("draftLength")
    )
    atomic(state)
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0 if state["safeCoverage"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
