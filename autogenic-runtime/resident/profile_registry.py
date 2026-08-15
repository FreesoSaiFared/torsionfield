#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

AttachMode = Literal["exclusive", "shared-session", "replica"]


def default_registry_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Torsionfield"
    else:
        base = Path.home() / ".torsionfield"
    return Path(os.environ.get("TF_PROFILE_REGISTRY", str(base / "ProfileRegistry" / "state.json")))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


@dataclass
class ProfileRecord:
    profile_id: str
    label: str
    executable: str
    user_data_dir: str
    profile_directory: str = "Default"
    browser_channel: str = "chrome"
    identity_label: str = ""
    attach_mode: AttachMode = "shared-session"
    parent_profile_id: str | None = None
    extension_fingerprint: str = ""
    restore_policy: str = "restore-last-session"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ControlSessionRecord:
    session_id: str
    profile_id: str
    owner: str
    priority: int = 50
    active_tab_id: str | int | None = None
    snapshot_generation: int = 0
    tab_bindings: dict[str, dict[str, Any]] = field(default_factory=dict)
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ProfileRegistry:
    """Persistent identity/profile registry with independent controller sessions."""

    SCHEMA = "TF_PROFILE_REGISTRY/1"

    def __init__(self, path: Path | None = None):
        self.path = path or default_registry_path()
        self._lock = threading.RLock()
        self._state = self._load()

    def _empty(self) -> dict[str, Any]:
        return {"schema": self.SCHEMA, "profiles": {}, "sessions": {}, "updatedAt": time.time()}

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("schema") == self.SCHEMA:
                return value
        except Exception:
            pass
        return self._empty()

    def _save(self) -> None:
        self._state["updatedAt"] = time.time()
        atomic_json(self.path, self._state)

    def register_profile(self, profile: ProfileRecord, *, replace: bool = False) -> dict[str, Any]:
        with self._lock:
            existing = self._state["profiles"].get(profile.profile_id)
            if existing and not replace:
                raise ValueError(f"profile-exists:{profile.profile_id}")
            profile.updated_at = time.time()
            self._state["profiles"][profile.profile_id] = asdict(profile)
            self._save()
            return self.profile(profile.profile_id)

    def profile(self, profile_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._state["profiles"].get(profile_id)
            if not value:
                raise KeyError(f"profile-not-found:{profile_id}")
            return json.loads(json.dumps(value))

    def profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            return [json.loads(json.dumps(v)) for v in self._state["profiles"].values()]

    def create_replica(self, parent_profile_id: str, *, label: str, user_data_dir: str) -> dict[str, Any]:
        parent = self.profile(parent_profile_id)
        replica_id = f"{parent_profile_id}-replica-{uuid.uuid4().hex[:10]}"
        return self.register_profile(ProfileRecord(
            profile_id=replica_id,
            label=label,
            executable=parent["executable"],
            user_data_dir=user_data_dir,
            profile_directory=parent.get("profile_directory", "Default"),
            browser_channel=parent.get("browser_channel", "chrome"),
            identity_label=parent.get("identity_label", ""),
            attach_mode="replica",
            parent_profile_id=parent_profile_id,
            extension_fingerprint=parent.get("extension_fingerprint", ""),
            restore_policy=parent.get("restore_policy", "restore-last-session"),
            metadata={"replicaOf": parent_profile_id},
        ))

    def open_session(self, profile_id: str, *, owner: str, session_id: str | None = None, priority: int = 50) -> dict[str, Any]:
        with self._lock:
            profile = self.profile(profile_id)
            active = [s for s in self._state["sessions"].values() if s["profile_id"] == profile_id and s.get("status") == "active"]
            if profile.get("attach_mode") == "exclusive" and active:
                raise RuntimeError(f"profile-exclusive-in-use:{profile_id}")
            sid = session_id or f"session-{uuid.uuid4().hex}"
            if sid in self._state["sessions"]:
                raise ValueError(f"session-exists:{sid}")
            record = ControlSessionRecord(session_id=sid, profile_id=profile_id, owner=owner, priority=priority)
            self._state["sessions"][sid] = asdict(record)
            self._save()
            return self.session(sid)

    def session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._state["sessions"].get(session_id)
            if not value:
                raise KeyError(f"session-not-found:{session_id}")
            return json.loads(json.dumps(value))

    def sessions(self, profile_id: str | None = None, *, active_only: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            values = self._state["sessions"].values()
            return [json.loads(json.dumps(v)) for v in values if (not profile_id or v["profile_id"] == profile_id) and (not active_only or v.get("status") == "active")]

    def bind_tab(self, session_id: str, tab_id: str | int, *, purpose: str = "", conversation_id: str = "", project_id: str = "") -> dict[str, Any]:
        with self._lock:
            record = self._state["sessions"][session_id]
            key = str(tab_id)
            record["tab_bindings"][key] = {
                "tabId": tab_id,
                "purpose": purpose,
                "conversationId": conversation_id,
                "projectId": project_id,
                "boundAt": time.time(),
            }
            record["updated_at"] = time.time()
            self._save()
            return self.session(session_id)

    def set_active_tab(self, session_id: str, tab_id: str | int | None) -> dict[str, Any]:
        with self._lock:
            record = self._state["sessions"][session_id]
            record["active_tab_id"] = tab_id
            record["updated_at"] = time.time()
            self._save()
            return self.session(session_id)

    def next_snapshot_generation(self, session_id: str) -> int:
        with self._lock:
            record = self._state["sessions"][session_id]
            record["snapshot_generation"] = int(record.get("snapshot_generation", 0)) + 1
            record["updated_at"] = time.time()
            self._save()
            return record["snapshot_generation"]

    def close_session(self, session_id: str, *, status: str = "closed") -> dict[str, Any]:
        with self._lock:
            record = self._state["sessions"][session_id]
            record["status"] = status
            record["updated_at"] = time.time()
            self._save()
            return self.session(session_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))
