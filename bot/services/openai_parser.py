from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class ParsedIntent:
    intent: str
    character_name: str | None


class OpenAIIntentParser:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @classmethod
    def from_env(cls) -> "OpenAIIntentParser":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        return cls(api_key=api_key, model=model)

    def parse(self, message: str) -> ParsedIntent:
        instructions = (
            "You are a strict JSON parser for a Discord bot. "
            "Extract intent and character_name from Korean requests. "
            "If the request is about MapleStory combat power, set intent "
            "to 'maple_combat_power' and include the character name. "
            "If the request is about schedules, availability, or calendar, "
            "set intent to 'schedule_query'. "
            "If you cannot determine the character name, set it to null. "
            "'카링' is the bot's name. Do not query for other intents. "
            "Respond with JSON only, no extra text."
        )
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=message,
        )
        payload = self._safe_json(response.output_text)
        return ParsedIntent(
            intent=str(payload.get("intent", "")),
            character_name=payload.get("character_name"),
        )

    @staticmethod
    def _safe_json(text: str) -> dict[str, Any]:
        if not text:
            return {"intent": "", "character_name": None}

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return {"intent": "", "character_name": None}
