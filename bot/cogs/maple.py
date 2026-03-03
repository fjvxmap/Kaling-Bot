from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Tuple

import discord
from discord.ext import commands
import os
import requests

from bot.services.game.number_baseball import NumberBaseball
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
        self._number_baseball_sessions: Dict[int, Tuple[int, NumberBaseball]] = {}

    @commands.Cog.listener()
    async def on_message(self, message) -> None:
        if message.author.bot:
            return

        content = message.content.strip()
        if await self._handle_number_baseball_try(message, content):
            return
        if await self._handle_number_baseball_stop(message, content):
            return

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

        if parsed.intent == "number_baseball_start":
            await self._start_number_baseball(message)
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

    async def _start_number_baseball(self, message) -> None:
        channel_id = message.channel.id
        current = self._number_baseball_sessions.get(channel_id)
        if current is not None:
            owner_id, _ = current
            if owner_id == message.author.id:
                await message.channel.send("지금 하고 있잖아! 멍청아.")
            else:
                await message.channel.send("지금 하고 있잖아! 멍청아.")
            return

        game = NumberBaseball(digits=4)
        self._number_baseball_sessions[channel_id] = (message.author.id, game)
        await message.channel.send(
            "좋아! 중복 없는 4자리 숫자를 말해.\n"
            f"기회는 총 {game.trials}번이야."
        )

    async def _handle_number_baseball_try(self, message, content: str) -> bool:
        channel_id = message.channel.id
        current = self._number_baseball_sessions.get(channel_id)
        if current is None:
            return False
        if not (len(content) == 4 and content.isdigit()):
            return False
        
        owner_id, game = current
        if owner_id != message.author.id:
            await message.channel.send("다른 메붕이 한 마리가 게임 중이긴 한데, 너도 받아는 줄게.")
            # return True

        if len(set(content)) != 4:
            await message.channel.send("중복 숫자는 안 받아. 4자리 다 다르게 써. 멍청아.")
            return True

        strikes, balls = game.guess(content)
        remain = game.trials - game.attempts

        if strikes == 4:
            self._number_baseball_sessions.pop(channel_id, None)
            await message.channel.send(
                f"{strikes}스트라이크. ...맞췄네. 꽤 건방지네."
            )
            return True

        if remain <= 0:
            answer = game.secret_number
            self._number_baseball_sessions.pop(channel_id, None)
            await message.channel.send(
                f"{strikes}스트라이크 {balls}볼. 끝이야~ 허접. 정답은 {answer}.\n"
                "이 정도도 못 맞추면 가서 지뢰찾기나 하는게 어때?"
            )
            return True

        await message.channel.send(
            f"{strikes}스트라이크 {balls}볼. 남은 기회 {remain}번."
        )
        return True

    async def _handle_number_baseball_stop(self, message, content: str) -> bool:
        channel_id = message.channel.id
        current = self._number_baseball_sessions.get(channel_id)
        if current is None:
            return False
        owner_id, game = current
        if owner_id != message.author.id:
            return False
        if "카링" not in content:
            return False

        try:
            parser = OpenAIIntentParser.from_env()
            parsed = await asyncio.to_thread(parser.parse, content)
        except RuntimeError:
            return False
        except Exception as exc:
            LOGGER.warning("Failed to parse stop intent: %s", exc)
            return False

        if parsed.intent != "number_baseball_stop":
            return False

        self._number_baseball_sessions.pop(channel_id, None)
        await message.channel.send(
            f"그래, 여기서 끝내자. 정답은 {game.secret_number}였어."
        )
        return True

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
