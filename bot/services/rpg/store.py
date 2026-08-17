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
_REPLACE_NUMERIC_FIELDS = {
    "genesis_item_uid",
    "genesis_liberation_stage",
}
_MONOTONIC_NUMERIC_FIELDS = {"liberation_reset_revision"}


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
        if current == latest:
            return self._clone(current)

        # Material quantities are additive counters. Treat an absent key as
        # zero so a concurrent final-item consumption (key removal) and reward
        # gain preserve both deltas regardless of save order.
        if len(path) >= 2 and path[-2] == "materials":
            values = (baseline, current, latest)
            if all(
                value is _MISSING
                or (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                )
                for value in values
            ):
                baseline_amount = 0 if baseline is _MISSING else baseline
                current_amount = 0 if current is _MISSING else current
                latest_amount = 0 if latest is _MISSING else latest
                merged_amount = max(
                    0,
                    int(latest_amount) + int(current_amount) - int(baseline_amount),
                )
                return merged_amount if merged_amount > 0 else _MISSING

        if baseline is _MISSING:
            if latest is _MISSING:
                return self._clone(current)
            if current == latest:
                return self._clone(current)

        # Service startup applies profile migrations before it can accept user
        # actions. If another process has already persisted the same (or a newer)
        # migration revision, this process is holding a stale pre-migration
        # snapshot. Keep the complete latest profile so a late bot/web startup
        # cannot roll back liberation progress made after the first startup.
        if (
            len(path) == 2
            and path[0] == "profiles"
            and isinstance(baseline, dict)
            and isinstance(current, dict)
            and isinstance(latest, dict)
        ):
            baseline_revision = int(baseline.get("liberation_reset_revision", 0) or 0)
            current_revision = int(current.get("liberation_reset_revision", 0) or 0)
            latest_revision = int(latest.get("liberation_reset_revision", 0) or 0)
            if latest_revision >= current_revision > baseline_revision:
                return self._clone(latest)

            # Liberation stages, their weapon stars/potential, and consumed
            # trace materials form one progress snapshot. When two processes
            # advance from the same stage but one is already further ahead,
            # field-by-field numeric merging can roll the stage back and add
            # the star deltas together. Keep the complete higher-stage snapshot
            # instead; the lower-stage advance is fully subsumed by it.
            if current_revision == latest_revision == baseline_revision:
                baseline_stage = int(baseline.get("genesis_liberation_stage", -1) or 0)
                current_stage = int(current.get("genesis_liberation_stage", -1) or 0)
                latest_stage = int(latest.get("genesis_liberation_stage", -1) or 0)
                if (
                    current_stage > baseline_stage
                    and latest_stage > baseline_stage
                    and current_stage != latest_stage
                ):
                    higher_stage = current if current_stage > latest_stage else latest
                    # Only liberation-owned state is subsumed by the higher
                    # stage. Normalize that snapshot on both sides, then let
                    # the ordinary three-way merge retain unrelated concurrent
                    # changes such as gold, EXP, equipment, and new drops.
                    normalized_current = self._with_liberation_snapshot(
                        current,
                        higher_stage,
                        baseline,
                        latest,
                    )
                    normalized_latest = self._with_liberation_snapshot(
                        latest,
                        higher_stage,
                        baseline,
                        current,
                    )
                    merged = self._three_way_merge(
                        baseline,
                        normalized_current,
                        normalized_latest,
                        path=path,
                    )
                    return self._with_liberation_material_snapshot(
                        merged,
                        higher_stage,
                        baseline,
                        current,
                        latest,
                    )

        if current == baseline:
            return self._clone(latest)
        if latest == baseline or latest is _MISSING:
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
            if field in _MONOTONIC_NUMERIC_FIELDS:
                return max(current, latest)
            if field in _REPLACE_NUMERIC_FIELDS:
                return self._clone(current)
            return latest + (current - baseline)

        return self._clone(current)

    @staticmethod
    def _clone(value: Any) -> Any:
        return _MISSING if value is _MISSING else deepcopy(value)

    @classmethod
    def _with_liberation_snapshot(
        cls,
        target: dict[str, Any],
        source: dict[str, Any],
        *related: dict[str, Any],
    ) -> dict[str, Any]:
        """Overlay the atomic liberation fields without replacing the profile."""
        def item_uid(value: Any) -> int:
            try:
                return max(0, int(value or 0))
            except (TypeError, ValueError):
                return 0

        normalized = deepcopy(target)
        for field in (
            "genesis_item_uid",
            "genesis_liberation_stage",
            "liberation_reset_revision",
        ):
            if field in source:
                normalized[field] = deepcopy(source[field])
            else:
                normalized.pop(field, None)

        tracked_uids = {
            item_uid(profile.get("genesis_item_uid", 0))
            for profile in (source, target, *related)
            if isinstance(profile, dict)
        }
        tracked_uids.discard(0)
        source_uid = item_uid(source.get("genesis_item_uid", 0))
        source_inventory = source.get("inventory", [])
        source_genesis = next(
            (
                deepcopy(row)
                for row in source_inventory
                if isinstance(row, dict) and item_uid(row.get("uid", 0)) == source_uid
            ),
            None,
        ) if isinstance(source_inventory, list) else None
        target_inventory = normalized.get("inventory", [])
        if isinstance(target_inventory, list):
            normalized_inventory = [
                deepcopy(row)
                for row in target_inventory
                if not (
                    isinstance(row, dict)
                    and item_uid(row.get("uid", 0)) in tracked_uids
                )
            ]
            if source_genesis is not None:
                normalized_inventory.append(source_genesis)
            normalized["inventory"] = normalized_inventory
        return normalized

    @staticmethod
    def _with_liberation_material_snapshot(
        target: dict[str, Any],
        source: dict[str, Any],
        *related: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep trace consumption aligned with the selected liberation stage."""
        normalized = deepcopy(target)
        material_maps = [
            profile.get("materials", {})
            for profile in (source, target, *related)
            if isinstance(profile, dict)
            and isinstance(profile.get("materials", {}), dict)
        ]
        trace_ids = {
            str(material_id)
            for materials in material_maps
            for material_id in materials
            if str(material_id).endswith("_liberation_trace")
        }
        source_materials = source.get("materials", {})
        normalized_materials = normalized.get("materials", {})
        if not isinstance(normalized_materials, dict):
            normalized_materials = {}
        else:
            normalized_materials = deepcopy(normalized_materials)
        for material_id in trace_ids:
            if isinstance(source_materials, dict) and material_id in source_materials:
                normalized_materials[material_id] = deepcopy(source_materials[material_id])
            else:
                normalized_materials.pop(material_id, None)
        normalized["materials"] = normalized_materials
        return normalized

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
