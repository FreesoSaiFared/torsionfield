#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
import urllib.parse
from pathlib import Path

import browser_roots as base

BRIDGE_CLIENT_SUFFIX = "-reboot-v3"
BRIDGE_FILES = ("reboot_bridge_v3.html", "reboot_bridge_v3.js")

# Re-export stable primitives used by the supervisor.
CHAT_URL_RE = base.CHAT_URL_RE
BRIDGE_HOST = base.BRIDGE_HOST
BRIDGE_PORT = base.BRIDGE_PORT
bridge_base = base.bridge_base
bridge_clients = base.bridge_clients
bridge_rpc = base.bridge_rpc
bridge_healthy = base.bridge_healthy
extension_record = base.extension_record
scan_session_urls = base.scan_session_urls
cdp_alive = base.cdp_alive
node_call = base.node_call


def parse_root(row: dict) -> dict:
    root = base.parse_root(row)
    root["client"] = root["rootId"] + BRIDGE_CLIENT_SUFFIX
    return root


def discover_roots() -> list[dict]:
    merged: dict[str, dict] = {}
    for row in base.browser_processes():
        root = parse_root(row)
        key = root["rootId"]
        if key not in merged:
            merged[key] = {**root, "pids": [root["pid"]]}
        else:
            merged[key]["pids"].append(root["pid"])
    return list(merged.values())


def ensure_bridge_files(extension: dict, source_dir: str | Path) -> bool:
    if not extension or not extension.get("path"):
        return False
    source = Path(source_dir)
    destination = Path(extension["path"])
    if not source.exists() or not destination.exists():
        return False
    for name in BRIDGE_FILES:
        (destination / name).write_bytes((source / name).read_bytes())
    return True


def open_bridge(root: dict, extension: dict | None, source_dir: str | Path) -> dict:
    if not extension:
        return {"ok": False, "reason": "torsionfield-extension-not-installed"}
    if not ensure_bridge_files(extension, source_dir):
        return {"ok": False, "reason": "bridge-v3-files-not-installed"}
    query = urllib.parse.urlencode({"client": root["client"], "server": bridge_base()})
    url = f"chrome-extension://{extension['id']}/reboot_bridge_v3.html?{query}"
    args = [root["executable"]]
    if root.get("explicitUserDataDir"):
        args.append(f"--user-data-dir={root['userDataDir']}")
    if root.get("profileDirectory"):
        args.append(f"--profile-directory={root['profileDirectory']}")
    args.append(url)
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "url": url, "extension": extension}


def ensure_bridge(root: dict, source_dir: str | Path, timeout: float = 10) -> dict:
    if bridge_healthy(root["client"]):
        return {"ok": True, "already": True}
    extension = extension_record(root)
    opened = open_bridge(root, extension, source_dir)
    if not opened.get("ok"):
        return opened
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bridge_healthy(root["client"]):
            return {
                "ok": True,
                "opened": True,
                "extension": extension,
                "url": opened["url"],
            }
        time.sleep(0.2)
    return {
        "ok": False,
        "reason": "bridge-v3-page-did-not-register",
        "extension": extension,
        "url": opened.get("url"),
    }


def root_inventory(
    root: dict,
    bridge_source: str | Path,
    cdp_helper: str | Path,
    auto_bridge: bool = True,
) -> dict:
    evidence = scan_session_urls(root.get("profilePath") or "")
    extension = extension_record(root)
    coverage = "none"
    inventory = None
    errors: list[str] = []
    bridge = None

    if auto_bridge and evidence and not bridge_healthy(root["client"]):
        try:
            bridge = ensure_bridge(root, bridge_source)
        except Exception as exc:
            bridge = {"ok": False, "reason": repr(exc)}

    if bridge_healthy(root["client"]):
        try:
            # The v3 page bounds every individual tab capture. A root-level timeout
            # remains as a second independent guard against a wedged extension page.
            inventory = bridge_rpc(root["client"], "inventory", {}, 25_000)
            coverage = "extension"
        except Exception as exc:
            errors.append("bridge:" + repr(exc))

    if inventory is None and cdp_alive(root.get("debugPort")):
        try:
            inventory = node_call(cdp_helper, "inventory", root["debugPort"], {}, 35)
            coverage = "cdp"
        except Exception as exc:
            errors.append("cdp:" + repr(exc))

    tabs: list[dict] = []
    if inventory:
        source_tabs = inventory.get("tabs") if coverage == "extension" else inventory.get("pages")
        for tab in source_tabs or []:
            if not tab.get("chatgpt"):
                continue
            tabs.append(tab)
            # A tab that is known to be ChatGPT but whose page state was not read is
            # not safe. Never let a partial inventory silently certify the root.
            if tab.get("error") or not tab.get("state"):
                errors.append(f"chatgpt-tab-unobserved:{tab.get('id')}:{tab.get('error') or 'missing-state'}")

    discovered = bool(evidence or tabs)
    covered = bool(
        (not discovered)
        or (inventory is not None and coverage in ("extension", "cdp") and not errors)
    )
    return {
        **root,
        "extension": extension,
        "sessionEvidence": evidence,
        "discoveredChatGPT": discovered,
        "coverage": coverage,
        "covered": covered,
        "bridgeEnsure": bridge,
        "errors": errors,
        "inventory": inventory,
        "tabs": tabs,
    }
