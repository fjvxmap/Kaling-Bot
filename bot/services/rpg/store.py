from __future__ import annotations

import json
import os
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import fcntl

from .models import PlayerProfile


_MISSING = object()
_UNION_LIST_FIELDS = {"cleared_boss_ids", "solo_cleared_boss_ids"}


class RPGStore:
    def __init__(self, path: Path | None = None) -> None:
        configured_path = os.getenv("KALING_RPG_STATE_PATH", "").strip()
        self.path = path or (
            Path(configured_path).expanduser()
            if configured_path
            else Path(__file__).resolve().parents[2] / "data" / "rpg_state.json"
        )
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._baseline: dict[str, dict[str, Any]] = {}

    def load_profiles(self) -> dict[int, PlayerProfile]:
        with self._file_lock(exclusive=False):
            payload = self._load_payload_unlocked()
        raw_profiles = self._raw_profiles(payload)
        self._baseline = deepcopy(raw_profiles)
        return self._deserialize_profiles(raw_profiles)

    def load_profile(self, user_id: int) -> PlayerProfile | None:
        user_key = str(int(user_id))
        with self._file_lock(exclusive=False):
            payload = self._load_payload_unlocked()
        raw = self._raw_profiles(payload).get(user_key)
        if not isinstance(raw, dict):
            self._baseline.pop(user_key, None)
            return None
        self._baseline[user_key] = deepcopy(raw)
        profile = PlayerProfile.from_dict(raw)
        profile.user_id = int(user_id)
        return profile

    def profile_is_dirty(self, profile: PlayerProfile) -> bool:
        baseline = self._baseline.get(str(int(profile.user_id)), _MISSING)
        return baseline is _MISSING or profile.to_dict() != baseline

    def save_profiles(self, profiles: dict[int, PlayerProfile]) -> dict[int, PlayerProfile]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_lock(exclusive=True):
            payload = self._load_payload_unlocked()
            latest = deepcopy(self._raw_profiles(payload))
            for user_id, profile in profiles.items():
                user_key = str(int(user_id))
                current = profile.to_dict()
                baseline = self._baseline.get(user_key, _MISSING)
                disk_value = latest.get(user_key, _MISSING)
                merged = self._three_way_merge(
                    baseline,
                    current,
                    disk_value,
                    path=("profiles", user_key),
                )
                if merged is not _MISSING:
                    latest[user_key] = merged

            next_payload = dict(payload)
            next_payload["version"] = max(1, int(payload.get("version", 1) or 1))
            next_payload["profiles"] = {
                user_id: latest[user_id]
                for user_id in sorted(
                    latest,
                    key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
                )
            }
            self._write_payload_unlocked(next_payload)
            self._baseline = deepcopy(latest)
        return self._deserialize_profiles(latest)

    def _three_way_merge(
        self,
        baseline: Any,
        current: Any,
        latest: Any,
        *,
        path: tuple[str, ...],
    ) -> Any:
        if current is _MISSING and latest is _MISSING:
            return _MISSING
        if baseline is _MISSING:
            if latest is _MISSING:
                return self._clone(current)
            if current == latest:
                return self._clone(current)
        if current == baseline:
            return self._clone(latest)
        if latest == baseline or latest is _MISSING:
            return self._clone(current)
        if current == latest:
            return self._clone(current)

        if isinstance(current, dict) and isinstance(latest, dict):
            base_dict = baseline if isinstance(baseline, dict) else {}
            keys = set(base_dict) | set(current) | set(latest)
            merged: dict[str, Any] = {}
            for key in keys:
                value = self._three_way_merge(
                    base_dict.get(key, _MISSING),
                    current.get(key, _MISSING),
                    latest.get(key, _MISSING),
                    path=(*path, str(key)),
                )
                if value is not _MISSING:
                    merged[key] = value
            return merged

        field = path[-1] if path else ""
        if isinstance(current, list) and isinstance(latest, list):
            base_list = baseline if isinstance(baseline, list) else []
            if field == "inventory":
                return self._merge_inventory(base_list, current, latest, path=path)
            if field in _UNION_LIST_FIELDS:
                return list(dict.fromkeys([*latest, *current]))
            return self._clone(current)

        if (
            isinstance(baseline, (int, float))
            and not isinstance(baseline, bool)
            and isinstance(current, (int, float))
            and not isinstance(current, bool)
            and isinstance(latest, (int, float))
            and not isinstance(latest, bool)
        ):
            return latest + (current - baseline)

        return self._clone(current)

    @staticmethod
    def _clone(value: Any) -> Any:
        return _MISSING if value is _MISSING else deepcopy(value)

    def _merge_inventory(
        self,
        baseline: list[Any],
        current: list[Any],
        latest: list[Any],
        *,
        path: tuple[str, ...],
    ) -> list[Any]:
        def by_uid(rows: list[Any]) -> dict[int, dict[str, Any]]:
            return {
                int(row["uid"]): row
                for row in rows
                if isinstance(row, dict) and str(row.get("uid", "")).isdigit()
            }

        base_by_uid = by_uid(baseline)
        current_by_uid = by_uid(current)
        latest_by_uid = by_uid(latest)
        merged: list[dict[str, Any]] = []
        for uid in sorted(set(base_by_uid) | set(current_by_uid) | set(latest_by_uid)):
            value = self._three_way_merge(
                base_by_uid.get(uid, _MISSING),
                current_by_uid.get(uid, _MISSING),
                latest_by_uid.get(uid, _MISSING),
                path=(*path, str(uid)),
            )
            if value is not _MISSING:
                merged.append(value)
        return merged

    def _write_payload_unlocked(self, payload: dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def _load_payload(self) -> dict[str, Any]:
        with self._file_lock(exclusive=False):
            return self._load_payload_unlocked()

    def _load_payload_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "profiles": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "profiles": {}}
        return payload if isinstance(payload, dict) else {"version": 1, "profiles": {}}

    @staticmethod
    def _raw_profiles(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw_profiles = payload.get("profiles", {})
        if not isinstance(raw_profiles, dict):
            return {}
        return {
            str(user_id): data
            for user_id, data in raw_profiles.items()
            if isinstance(data, dict)
        }

    @staticmethod
    def _deserialize_profiles(raw_profiles: dict[str, dict[str, Any]]) -> dict[int, PlayerProfile]:
        profiles: dict[int, PlayerProfile] = {}
        for user_id, data in raw_profiles.items():
            profile = PlayerProfile.from_dict(data)
            profile.user_id = int(user_id)
            profiles[profile.user_id] = profile
        return profiles

    @contextmanager
    def _file_lock(self, *, exclusive: bool) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
