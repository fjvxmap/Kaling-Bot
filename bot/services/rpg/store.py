from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import PlayerProfile


class RPGStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[2] / "data" / "rpg_state.json"

    def load_profiles(self) -> dict[int, PlayerProfile]:
        payload = self._load_payload()
        raw_profiles = payload.get("profiles", {})
        if not isinstance(raw_profiles, dict):
            return {}
        profiles: dict[int, PlayerProfile] = {}
        for user_id, data in raw_profiles.items():
            if not isinstance(data, dict):
                continue
            profile = PlayerProfile.from_dict(data)
            profile.user_id = int(user_id)
            profiles[profile.user_id] = profile
        return profiles

    def save_profiles(self, profiles: dict[int, PlayerProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "profiles": {
                str(user_id): profile.to_dict()
                for user_id, profile in sorted(profiles.items())
            },
        }
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "profiles": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "profiles": {}}
        return payload if isinstance(payload, dict) else {"version": 1, "profiles": {}}

