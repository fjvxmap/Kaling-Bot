from __future__ import annotations

import os

from openai import OpenAI

from .prompt_loader import load_prompt


class OpenAIResponder:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._tease_instructions = load_prompt("respond_tease_instructions_ko.txt")
        self._small_talk_instructions = load_prompt("respond_small_talk_instructions_ko.txt")
        self._annoy_reject_instructions = load_prompt("respond_annoy_reject_instructions_ko.txt")

    @classmethod
    def from_env(cls) -> "OpenAIResponder":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        return cls(api_key=api_key, model=model)

    def generate_tease(
        self, style_reference: str, user_text: str, character_reference: str = ""
    ) -> str:
        reference_block = ""
        if character_reference:
            reference_block = f"\n\nCHARACTER_REFERENCE:\n{character_reference}"
        response = self._client.responses.create(
            model=self._model,
            instructions=self._tease_instructions,
            input=(
                f"STYLE_REFERENCE:\n{style_reference}"
                f"{reference_block}\n\nUSER_TEXT:\n{user_text}"
            ),
        )
        return response.output_text.strip() or "장고도 안 켜고 스케줄 묻는 거야?"

    def generate_small_talk(
        self, style_reference: str, user_text: str, character_reference: str = ""
    ) -> str:
        reference_block = ""
        if character_reference:
            reference_block = f"\n\nCHARACTER_REFERENCE:\n{character_reference}"
        response = self._client.responses.create(
            model=self._model,
            instructions=self._small_talk_instructions,
            input=(
                f"STYLE_REFERENCE:\n{style_reference}"
                f"{reference_block}\n\nUSER_TEXT:\n{user_text}"
            ),
        )
        return response.output_text.strip() or "응, 카링 여기 있어. 무슨 얘기할래?"

    def generate_annoy_reject(
        self, style_reference: str, user_text: str, character_reference: str = ""
    ) -> str:
        reference_block = ""
        if character_reference:
            reference_block = f"\n\nCHARACTER_REFERENCE:\n{character_reference}"
        response = self._client.responses.create(
            model=self._model,
            instructions=self._annoy_reject_instructions,
            input=(
                f"STYLE_REFERENCE:\n{style_reference}"
                f"{reference_block}\n\nUSER_TEXT:\n{user_text}"
            ),
        )
        return response.output_text.strip() or "그런 말은 받지 않아. 선 지켜."
