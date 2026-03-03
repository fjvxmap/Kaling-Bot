from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class ParsedIntent:
    intent: str
    character_name: str | None
    reaction: str


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
        instructions = cls._load_instructions()
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
        )

    @staticmethod
    def _load_instructions() -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / "intent_parser_ko.txt"
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return (
                "You are a strict JSON parser for a Discord bot. Your name is Kaling(카링)."
                "Valid intents are maple_combat_power, schedule_query, number_baseball_start, number_baseball_stop, small_talk, ignore. "
                "Valid reactions are joy, love, scary, tease, none. "
                "If the request is about MapleStory combat power, use maple_combat_power and include character_name. "
                "If the request is about schedules, use schedule_query. "
                "If the request is to start number baseball game, use number_baseball_start. "
                "If the request is to stop/quit number baseball game, use number_baseball_stop. "
                "If the user is casually talking to the bot, use small_talk. "
                "If none apply, use ignore. character_name should be null when unknown. "
                "Include reaction for image mood. "
                "Respond with JSON only."
            )

    @staticmethod
    def _safe_json(text: str) -> dict[str, Any]:
        if not text:
            return {"intent": "", "character_name": None, "reaction": "none"}

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
            return {"intent": "", "character_name": None, "reaction": "none"}

    @staticmethod
    def _normalize_reaction(value: Any) -> str:
        allowed = {"joy", "love", "scary", "tease", "none"}
        reaction = str(value or "none").strip().lower()
        return reaction if reaction in allowed else "none"
