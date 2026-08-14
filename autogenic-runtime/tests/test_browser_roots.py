#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent / "reboot-manager" / "browser_roots.py"
spec = importlib.util.spec_from_file_location("browser_roots", MODULE)
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)

with tempfile.TemporaryDirectory(prefix="tf-browser-root-") as temp:
    profile = Path(temp) / "Profile 1"
    sessions = profile / "Sessions"
    sessions.mkdir(parents=True)
    url = "https://chatgpt.com/c/6a7ef8a3-aa70-83ec-9105-0ace064c98e8"
    (sessions / "Tabs_test").write_bytes(b"prefix\x00" + url.encode() + b"\x00suffix")

    evidence = br.scan_session_urls(str(profile))
    assert [item["url"] for item in evidence] == [url]

    secure = {
        "extensions": {
            "settings": {
                "abcdefghijklmnopabcdefghijklmnop": {
                    "path": str(Path(temp) / "Torsionfield" / "extension"),
                    "manifest": {"name": "Torsionfield Session Loop", "version": "2.2.1"},
                    "active_permissions": {
                        "api": ["tabs", "scripting", "debugger"],
                        "scriptable_host": ["https://chatgpt.com/*"],
                    },
                }
            }
        }
    }
    (profile / "Secure Preferences").write_text(json.dumps(secure), encoding="utf-8")
    root = {
        "rootId": "test-root",
        "client": "test-root",
        "profilePath": str(profile),
        "debugPort": None,
    }
    extension = br.extension_record(root)
    assert extension is not None
    assert extension["name"] == "Torsionfield Session Loop"

    # Installed capability is not live coverage. With no bridge heartbeat and no
    # CDP listener, the root must remain uncovered even though session evidence exists.
    record = br.root_inventory(
        root,
        bridge_source=HERE.parent / "reboot-manager" / "extension_bridge",
        cdp_helper=HERE.parent / "reboot-manager" / "reboot_cdp.mjs",
        auto_bridge=False,
    )
    assert record["discoveredChatGPT"] is True
    assert record["coverage"] == "none"
    assert record["covered"] is False

print(json.dumps({"PASS": True, "evidence": url, "coverageGate": "uncovered-without-live-control"}, indent=2))
