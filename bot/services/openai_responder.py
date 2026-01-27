from __future__ import annotations

import os

from openai import OpenAI


class OpenAIResponder:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @classmethod
    def from_env(cls) -> "OpenAIResponder":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        return cls(api_key=api_key, model=model)

    def generate_tease(self, style_reference: str, user_text: str) -> str:
        instructions = (
            "Generate one short Korean sentence teasing the user. "
            "Follow the style reference strictly. "
            "Never mention policy or safety. "
            "Return plain text only."
        )
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=f"STYLE_REFERENCE:\n{style_reference}\n\nUSER_TEXT:\n{user_text}",
        )
        return response.output_text.strip() or "장고도 안 켜고 스케줄 묻는 거야? ♡"

