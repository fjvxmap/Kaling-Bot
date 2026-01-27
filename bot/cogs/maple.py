from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from discord.ext import commands
import os
import requests

from bot.services.nexon_client import NexonAPIClient
from bot.services.openai_parser import OpenAIIntentParser
from bot.services.openai_responder import OpenAIResponder

LOGGER = logging.getLogger("kaling.maple")


class MapleCombatPower(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._style_text = self._load_style_reference()

    @commands.Cog.listener()
    async def on_message(self, message) -> None:
        if message.author.bot:
            return

        content = message.content.strip()
        if "카링" in content:
            await self._handle_request(message)

    async def _handle_request(self, message) -> None:
        text = message.content.strip()
        try:
            parser = OpenAIIntentParser.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        parsed = await asyncio.to_thread(parser.parse, text)
        LOGGER.info("Parsed intent=%s character_name=%s", parsed.intent, parsed.character_name)
        if parsed.intent == "schedule_query":
            if not await asyncio.to_thread(self._django_is_up):
                await self._send_tease(message, text)
            return

        if parsed.intent != "maple_combat_power":
            return

        if not parsed.character_name:
            await message.channel.send("캐릭터 이름을 알려줘.")
            return

        try:
            client = NexonAPIClient.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        try:
            power = await asyncio.to_thread(client.get_combat_power, parsed.character_name)
        except Exception as exc:
            await message.channel.send(f"API 호출 실패: {exc}")
            return

        if power is None:
            LOGGER.warning("Combat power not found for '%s'", parsed.character_name)
            await message.channel.send("전투력을 찾지 못했어. 닉네임이나 설정을 확인해줘.")
            return
        
        power_str = str(power)
        if len(power_str) > 8:
            power = f"{int(power) // 100000000}억 { (int(power) % 100000000) // 10000 }만"
        elif len(power_str) > 4:
            power = f"{int(power) // 10000}만"

        await message.channel.send(f"{parsed.character_name} 전투력: {power}")

    def _django_is_up(self) -> bool:
        base_url = (os.getenv("DJANGO_BASE_URL", "http://127.0.0.1:8000/")).strip()
        try:
            response = requests.get(base_url, timeout=2)
            return response.status_code < 500
        except requests.RequestException:
            return False

    async def _send_tease(self, message, user_text: str) -> None:
        try:
            responder = OpenAIResponder.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        tease = await asyncio.to_thread(
            responder.generate_tease, self._style_text, user_text
        )
        await message.channel.send(tease)

    @staticmethod
    def _load_style_reference() -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / "schedule_tease_ko.txt"
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return "Tone: playful tease, short Korean sentence. End with a cute flourish like ♡."


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MapleCombatPower(bot))
