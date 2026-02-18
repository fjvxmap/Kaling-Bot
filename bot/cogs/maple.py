from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

import discord
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
        self._schedule_tease_style = self._load_prompt(
            "schedule_tease_ko.txt",
            "Tone: playful tease, short Korean sentence. End with a cute flourish like ♡.",
        )
        self._small_talk_style = self._load_prompt(
            "small_talk_ko.txt",
            "Tone: friendly and witty Korean Discord bot, 1-2 short lines.",
        )
        self._scary_reject_style = self._load_prompt(
            "scary_reject_ko.txt",
            "Tone: short firm rejection in Korean, no emoji.",
        )
        self._character_reference = self._load_prompt("reference.txt", "")
        self._img_root = Path(__file__).resolve().parents[2] / "img"
        self._image_send_prob = float(os.getenv("KALING_IMAGE_SEND_PROB", "0.35"))

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
        LOGGER.info(
            "Parsed intent=%s character_name=%s reaction=%s",
            parsed.intent,
            parsed.character_name,
            parsed.reaction,
        )

        if parsed.intent == "small_talk":
            await self._send_small_talk(message, text, parsed.reaction)
            return

        if parsed.intent == "schedule_query":
            if not await asyncio.to_thread(self._django_is_up):
                await self._send_tease(message, text, parsed.reaction)
            else:
                url = self._schedule_url()
                await message.channel.send(f"여기서 일정 남겨줘: {url}")
                await self._send_reaction_image(message, parsed.reaction, default="joy")
            return

        if parsed.intent != "maple_combat_power":
            if parsed.reaction == "scary":
                await self._send_scary_reject(message, text)
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
        await self._send_reaction_image(message, parsed.reaction, default="joy")

    def _django_is_up(self) -> bool:
        base_url = (os.getenv("DJANGO_BASE_URL", "http://127.0.0.1:8000/")).strip()
        try:
            response = requests.get(base_url, timeout=2)
            return response.status_code < 500
        except requests.RequestException:
            return False

    def _schedule_url(self) -> str:
        return os.getenv("DJANGO_BASE_URL", "http://127.0.0.1:8000/").strip()

    async def _send_tease(self, message, user_text: str, reaction: str) -> None:
        try:
            responder = OpenAIResponder.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        tease = await asyncio.to_thread(
            responder.generate_tease,
            self._schedule_tease_style,
            user_text,
            self._character_reference,
        )
        await message.channel.send(tease)
        await self._send_reaction_image(message, reaction, default="tease")

    async def _send_small_talk(self, message, user_text: str, reaction: str) -> None:
        try:
            responder = OpenAIResponder.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        reply = await asyncio.to_thread(
            responder.generate_small_talk,
            self._small_talk_style,
            user_text,
            self._character_reference,
        )
        await message.channel.send(reply)
        await self._send_reaction_image(message, reaction, default="joy")

    async def _send_scary_reject(self, message, user_text: str) -> None:
        try:
            responder = OpenAIResponder.from_env()
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        reply = await asyncio.to_thread(
            responder.generate_scary_reject,
            self._scary_reject_style,
            user_text,
            self._character_reference,
        )
        await message.channel.send(reply)
        await self._maybe_send_image(message, "scary", force=True)

    async def _send_reaction_image(self, message, reaction: str, default: str) -> None:
        image_category = reaction if reaction in {"joy", "love", "scary", "tease"} else default
        await self._maybe_send_image(message, image_category)

    async def _maybe_send_image(
        self, message, category: str, force: bool = False
    ) -> None:
        if not force and random.random() > self._image_send_prob:
            return
        image_path = self._pick_random_image(category)
        if not image_path:
            return
        try:
            await message.channel.send(file=discord.File(str(image_path)))
        except Exception as exc:
            LOGGER.warning("Failed to send image (%s): %s", image_path, exc)

    def _pick_random_image(self, category: str) -> Path | None:
        folder = self._img_root / category
        if not folder.exists():
            return None
        candidates = [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        ]
        if not candidates:
            return None
        return random.choice(candidates)

    @staticmethod
    def _load_prompt(filename: str, fallback: str) -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / filename
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return fallback


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MapleCombatPower(bot))
