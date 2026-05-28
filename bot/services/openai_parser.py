from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .prompt_loader import load_prompt


@dataclass(frozen=True)
class ParsedIntent:
    intent: str
    character_name: str | None
    reaction: str
    requested_slots: tuple[str, ...]


class OpenAIIntentParser:
    def __init__(self, api_key: str, model: str, instructions: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._instructions = instructions

    @classmethod
    def from_env(cls) -> "OpenAIIntentParser":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        instructions = load_prompt("intent_parser_ko.txt")
        return cls(api_key=api_key, model=model, instructions=instructions)

    def parse(self, message: str) -> ParsedIntent:
        response = self._client.responses.create(
            model=self._model,
            instructions=self._instructions,
            input=message,
        )
        payload = self._safe_json(response.output_text)
        return ParsedIntent(
            intent=str(payload.get("intent", "")),
            character_name=payload.get("character_name"),
            reaction=self._normalize_reaction(payload.get("reaction")),
            requested_slots=self._normalize_slots(payload.get("requested_slots")),
        )

    @staticmethod
    def _safe_json(text: str) -> dict[str, Any]:
        if not text:
            return {
                "intent": "",
                "character_name": None,
                "reaction": "none",
                "requested_slots": [],
            }

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
            return {
                "intent": "",
                "character_name": None,
                "reaction": "none",
                "requested_slots": [],
            }

    @staticmethod
    def _normalize_reaction(value: Any) -> str:
        allowed = {"joy", "love", "scary", "tease", "annoy", "none"}
        reaction = str(value or "none").strip().lower()
        return reaction if reaction in allowed else "none"

    @staticmethod
    def _normalize_slots(value: Any) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        normalized: list[str] = []
        for item in value:
            slot = str(item or "").strip()
            if slot:
                normalized.append(slot)
        return tuple(normalized)
