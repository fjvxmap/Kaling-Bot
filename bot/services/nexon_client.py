from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class NexonAPIConfig:
    base_url: str
    api_key: str
    ocid_path: str
    character_stat_path: str
    combat_power_path: str


class NexonAPIClient:
    def __init__(self, config: NexonAPIConfig) -> None:
        self._config = config
        self._logger = logging.getLogger("kaling.nexon")

    @classmethod
    def from_env(cls) -> "NexonAPIClient":
        base_url = os.getenv("NEXON_API_BASE_URL", "").strip()
        api_key = os.getenv("NEXON_API_KEY", "").strip()
        ocid_path = os.getenv("NEXON_MAPLE_OCID_PATH", "").strip()
        stat_path = os.getenv("NEXON_MAPLE_CHARACTER_STAT_PATH", "").strip()
        combat_path = os.getenv("NEXON_MAPLE_COMBAT_POWER_JSON_PATH", "final_stat.전투력").strip()
        if not base_url or not api_key or not ocid_path or not stat_path:
            raise RuntimeError(
                "NEXON_API_BASE_URL, NEXON_API_KEY, "
                "NEXON_MAPLE_OCID_PATH, and NEXON_MAPLE_CHARACTER_STAT_PATH must be set."
            )
        return cls(
            NexonAPIConfig(
                base_url=base_url,
                api_key=api_key,
                ocid_path=ocid_path,
                character_stat_path=stat_path,
                combat_power_path=combat_path,
            )
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"x-nxopen-api-key": self._config.api_key}
        self._logger.debug("Nexon GET %s params=%s", url, params)
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        self._logger.debug("Nexon response keys=%s", list(payload.keys()))
        return payload

    def get_combat_power(self, character_name: str) -> int | str | None:
        self._logger.info("Fetching combat power for '%s'", character_name)
        ocid_payload = self.get(self._config.ocid_path, {"character_name": character_name})
        self._logger.debug("OCID payload=%s", ocid_payload)
        ocid = ocid_payload.get("ocid")
        if not ocid:
            self._logger.warning("OCID not found in response for '%s'", character_name)
            return None

        stat_payload = self.get(self._config.character_stat_path, {"ocid": ocid})
        self._logger.debug("Stat payload keys=%s", list(stat_payload.keys()))
        return self._extract_path(stat_payload, self._config.combat_power_path)

    @staticmethod
    def _extract_path(payload: dict[str, Any], path: str) -> Any:
        current: Any = payload
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
                continue

            if isinstance(current, list):
                match = None
                for item in current:
                    if isinstance(item, dict) and item.get("stat_name") == key:
                        match = item
                        break
                if match is not None:
                    if "stat_value" in match:
                        return match["stat_value"]
                    current = match
                    continue

            return None
        return current
