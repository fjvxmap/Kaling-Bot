from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class NexonAPIConfig:
    base_url: str
    api_key: str


class NexonAPIClient:
    def __init__(self, config: NexonAPIConfig) -> None:
        self._config = config

    @classmethod
    def from_env(cls) -> "NexonAPIClient":
        base_url = os.getenv("NEXON_API_BASE_URL", "").strip()
        api_key = os.getenv("NEXON_API_KEY", "").strip()
        if not base_url or not api_key:
            raise RuntimeError("NEXON_API_BASE_URL or NEXON_API_KEY is not set.")
        return cls(NexonAPIConfig(base_url=base_url, api_key=api_key))

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"x-nxopen-api-key": self._config.api_key}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

