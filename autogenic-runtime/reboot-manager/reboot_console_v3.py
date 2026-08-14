#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import browser_roots_v3 as roots_v3
import reboot_supervisor as core

# Deliberately replace the supervisor's browser-root implementation before the
# web console is imported. Every supervisor function resolves core.br at call
# time, so preparation and post-boot restore use the same bounded v3 coverage.
core.br = roots_v3

import reboot_console as console
console.core = core

VERSION = "0.3.1"


def install_task() -> dict:
    if os.name != "nt":
        return {"installed": False, "reason": "Windows-only"}
    task = "Torsionfield Reboot Supervisor"
    command = f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve()}" --serve'
    completed = subprocess.run(
        ["schtasks", "/Create", "/TN", task, "/TR", command, "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return {"installed": True, "task": task, "command": command}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--reboot-if-safe", action="store_true")
    parser.add_argument("--restore-pending", action="store_true")
    parser.add_argument("--install-task", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    core.ensure_bridge_server()
    if args.self_test:
        result = console.self_test()
        result["v3Binding"] = True
        result["version"] = VERSION
        print(json.dumps(result, indent=2))
        return 0
    if args.inventory:
        print(json.dumps(core.inventory(auto_bridge=True), indent=2, ensure_ascii=False))
        return 0
    if args.snapshot:
        print(json.dumps(core.snapshot("v3-cli"), indent=2, ensure_ascii=False))
        return 0
    if args.prepare:
        print(json.dumps(core.prepare_reboot(), indent=2, ensure_ascii=False))
        return 0
    if args.reboot_if_safe:
        print(json.dumps(core.schedule_reboot(), indent=2, ensure_ascii=False))
        return 0
    if args.restore_pending:
        print(json.dumps(core.restore_pending(), indent=2, ensure_ascii=False))
        return 0
    if args.install_task:
        print(json.dumps(install_task(), indent=2))
        return 0
    console.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
