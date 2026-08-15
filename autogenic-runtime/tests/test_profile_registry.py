#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "resident"))

from profile_registry import ProfileRecord, ProfileRegistry


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tf-profile-registry-") as tmp:
        registry = ProfileRegistry(Path(tmp) / "registry.json")
        registry.register_profile(ProfileRecord(
            profile_id="personal-chatgpt",
            label="Personal ChatGPT",
            executable="chrome.exe",
            user_data_dir=str(Path(tmp) / "chrome-user-data"),
            profile_directory="Profile 1",
            identity_label="chatgpt-personal",
            attach_mode="shared-session",
        ))

        a = registry.open_session("personal-chatgpt", owner="agent-A", session_id="A")
        b = registry.open_session("personal-chatgpt", owner="agent-B", session_id="B")
        assert a["profile_id"] == b["profile_id"]

        registry.bind_tab("A", 101, purpose="physics", conversation_id="c-a")
        registry.bind_tab("B", 202, purpose="torsionfield", conversation_id="c-b")
        registry.set_active_tab("A", 101)
        registry.set_active_tab("B", 202)
        assert registry.session("A")["active_tab_id"] == 101
        assert registry.session("B")["active_tab_id"] == 202

        assert registry.next_snapshot_generation("A") == 1
        assert registry.next_snapshot_generation("A") == 2
        assert registry.next_snapshot_generation("B") == 1

        replica = registry.create_replica(
            "personal-chatgpt",
            label="Personal ChatGPT replica",
            user_data_dir=str(Path(tmp) / "replica-user-data"),
        )
        assert replica["attach_mode"] == "replica"
        assert replica["parent_profile_id"] == "personal-chatgpt"

        registry.register_profile(ProfileRecord(
            profile_id="exclusive-admin",
            label="Exclusive admin",
            executable="chrome.exe",
            user_data_dir=str(Path(tmp) / "admin-profile"),
            attach_mode="exclusive",
        ))
        registry.open_session("exclusive-admin", owner="agent-A", session_id="X1")
        try:
            registry.open_session("exclusive-admin", owner="agent-B", session_id="X2")
        except RuntimeError as exc:
            assert "profile-exclusive-in-use" in str(exc)
        else:
            raise AssertionError("exclusive profile accepted a second active session")

        registry.close_session("X1")
        registry.open_session("exclusive-admin", owner="agent-B", session_id="X2")
        assert len(registry.sessions("personal-chatgpt", active_only=True)) == 2

        reloaded = ProfileRegistry(Path(tmp) / "registry.json")
        assert reloaded.session("A")["active_tab_id"] == 101
        assert reloaded.session("B")["active_tab_id"] == 202
        assert reloaded.profile(replica["profile_id"])["parent_profile_id"] == "personal-chatgpt"

    print("PROFILE_REGISTRY_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
