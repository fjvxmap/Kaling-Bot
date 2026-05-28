from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path

import discord
import requests
from discord.ext import commands

from bot.services.game.number_baseball_manager import NumberBaseballManager
from bot.services.maple.equipment_formatter import summarize_equipment
from bot.services.nexon_client import NexonAPIClient
from bot.services.openai_parser import OpenAIIntentParser, ParsedIntent
from bot.services.openai_responder import OpenAIResponder
from bot.services.prompt_loader import load_prompt

LOGGER = logging.getLogger("kaling.cog")


class KalingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._schedule_tease_style = load_prompt("schedule_tease_ko.txt")
        self._small_talk_style = load_prompt("small_talk_ko.txt")
        self._annoy_reject_style = load_prompt("annoy_reject_ko.txt")
        self._character_reference = load_prompt("reference.txt")
        self._img_root = Path(__file__).resolve().parents[2] / "img"
        self._image_send_prob = float(os.getenv("KALING_IMAGE_SEND_PROB", "0.35"))
        self._number_baseball = NumberBaseballManager()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        content = message.content.strip()
        if await self._handle_number_baseball_guess(message, content):
            return
        if await self._handle_number_baseball_stop(message, content):
            return
        if "카링" in content:
            await self._handle_request(message, content)

    async def _handle_request(self, message: discord.Message, text: str) -> None:
        try:
            parsed = await asyncio.to_thread(OpenAIIntentParser.from_env().parse, text)
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        LOGGER.info(
            "Parsed intent=%s character_name=%s reaction=%s requested_slots=%s",
            parsed.intent,
            parsed.character_name,
            parsed.reaction,
            parsed.requested_slots,
        )

        if parsed.intent == "small_talk":
            await self._send_small_talk(message, text, parsed.reaction)
            return

        if parsed.intent == "number_baseball_start":
            await self._start_number_baseball(message)
            return

        if parsed.intent == "schedule_query":
            await self._handle_schedule_query(message, text, parsed.reaction)
            return

        if parsed.intent == "maple_combat_power":
            await self._handle_combat_power(message, parsed)
            return

        if parsed.intent == "maple_equipment":
            await self._handle_equipment(message, parsed)
            return

        if parsed.reaction == "annoy":
            await self._send_annoy_reject(message, text)

    async def _handle_schedule_query(
        self, message: discord.Message, text: str, reaction: str
    ) -> None:
        if not await asyncio.to_thread(self._django_is_up):
            await self._send_tease(message, text, reaction)
            return
        await message.channel.send(f"여기서 일정 남겨줘: {self._schedule_url()}")
        await self._send_reaction_image(message, reaction, default="joy")

    async def _handle_combat_power(
        self, message: discord.Message, parsed: ParsedIntent
    ) -> None:
        if not parsed.character_name:
            await message.channel.send("캐릭터 이름을 알려줘.")
            return

        try:
            client = NexonAPIClient.from_env()
            power = await asyncio.to_thread(client.get_combat_power, parsed.character_name)
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return
        except Exception as exc:
            await message.channel.send(f"API 호출 실패: {exc}")
            return

        if power is None:
            LOGGER.warning("Combat power not found for '%s'", parsed.character_name)
            await message.channel.send("전투력을 찾지 못했어. 닉네임이나 설정을 확인해줘.")
            return

        await message.channel.send(
            f"{parsed.character_name} 전투력: {self._format_combat_power(power)}"
        )
        await self._send_reaction_image(message, parsed.reaction, default="joy")

    async def _handle_equipment(
        self, message: discord.Message, parsed: ParsedIntent
    ) -> None:
        if not parsed.character_name:
            await message.channel.send("캐릭터 이름을 알려줘.")
            return

        try:
            client = NexonAPIClient.from_env()
            equip = await asyncio.to_thread(client.get_equipment, parsed.character_name)
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return
        except Exception as exc:
            await message.channel.send(f"API 호출 실패: {exc}")
            return

        if equip is None:
            LOGGER.warning("Equipment not found for '%s'", parsed.character_name)
            await message.channel.send("장비 정보를 찾지 못했어. 닉네임이나 설정을 확인해줘.")
            return

        lines = summarize_equipment(equip, parsed.character_name, parsed.requested_slots)
        if not lines:
            if parsed.requested_slots:
                requested = ", ".join(parsed.requested_slots)
                await message.channel.send(f"{requested} 부위 장비를 찾지 못했어.")
            else:
                await message.channel.send("장비 정보는 가져왔는데 정리할 장비 목록이 없었어.")
            return

        await message.channel.send("\n".join(lines[:40]))
        await self._send_reaction_image(message, parsed.reaction, default="joy")

    async def _send_tease(
        self, message: discord.Message, user_text: str, reaction: str
    ) -> None:
        try:
            responder = OpenAIResponder.from_env()
            tease = await asyncio.to_thread(
                responder.generate_tease,
                self._schedule_tease_style,
                user_text,
                self._character_reference,
            )
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        await message.channel.send(tease)
        await self._send_reaction_image(message, reaction, default="tease")

    async def _send_small_talk(
        self, message: discord.Message, user_text: str, reaction: str
    ) -> None:
        try:
            responder = OpenAIResponder.from_env()
            reply = await asyncio.to_thread(
                responder.generate_small_talk,
                self._small_talk_style,
                user_text,
                self._character_reference,
            )
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        await message.channel.send(reply)
        await self._send_reaction_image(message, reaction, default="joy")

    async def _send_annoy_reject(self, message: discord.Message, user_text: str) -> None:
        try:
            responder = OpenAIResponder.from_env()
            reply = await asyncio.to_thread(
                responder.generate_annoy_reject,
                self._annoy_reject_style,
                user_text,
                self._character_reference,
            )
        except RuntimeError as exc:
            await message.channel.send(str(exc))
            return

        await message.channel.send(reply)
        await self._maybe_send_image(message, "annoy", force=True)

    async def _start_number_baseball(self, message: discord.Message) -> None:
        status, game = self._number_baseball.start(message.channel.id, message.author.id)
        if status == "already_running_self":
            await message.channel.send("지금 하고 있잖아! 멍청아.")
            return
        if status == "already_running_other":
            await message.channel.send("이 채널은 이미 다른 사람이 숫자야구 중이야.")
            return
        await message.channel.send(
            "좋아! 중복 없는 4자리 숫자를 말해.\n"
            f"기회는 총 {game.trials}번이야."
        )

    async def _handle_number_baseball_guess(
        self, message: discord.Message, content: str
    ) -> bool:
        result = self._number_baseball.guess(message.channel.id, message.author.id, content)
        if result is None:
            return False
        result_type = str(result["type"])
        if result_type == "duplicate":
            await message.channel.send("중복 숫자는 안 받아. 4자리 다 다르게 써. 멍청아.")
            return True
        if result_type == "win":
            await message.channel.send(f"{result['strikes']}스트라이크. ...맞췄네. 꽤 건방지네.")
            return True
        if result_type == "lose":
            await message.channel.send(
                f"{result['strikes']}스트라이크 {result['balls']}볼. 끝이야~ 허접. 정답은 {result['answer']}.\n"
                "이 정도도 못 맞추면 가서 지뢰찾기나 하는게 어때?"
            )
            return True
        await message.channel.send(
            f"{result['strikes']}스트라이크 {result['balls']}볼. 남은 기회 {result['remain']}번."
        )
        return True

    async def _handle_number_baseball_stop(
        self, message: discord.Message, content: str
    ) -> bool:
        if "카링" not in content:
            return False
        try:
            parsed = await asyncio.to_thread(OpenAIIntentParser.from_env().parse, content)
        except RuntimeError:
            return False
        except Exception as exc:
            LOGGER.warning("Failed to parse stop intent: %s", exc)
            return False

        if parsed.intent != "number_baseball_stop":
            return False

        answer = self._number_baseball.stop(message.channel.id, message.author.id)
        if answer is None:
            return False
        await message.channel.send(f"그래, 여기서 끝내자. 정답은 {answer}였어.")
        return True

    def _django_is_up(self) -> bool:
        base_url = self._schedule_url()
        try:
            response = requests.get(base_url, timeout=2)
            return response.status_code < 500
        except requests.RequestException:
            return False

    @staticmethod
    def _schedule_url() -> str:
        return os.getenv("DJANGO_BASE_URL", "http://127.0.0.1:8000/").strip()

    @staticmethod
    def _format_combat_power(power: int | str) -> str:
        power_int = int(str(power).replace(",", ""))
        if power_int >= 100_000_000:
            return f"{power_int // 100_000_000}억 {(power_int % 100_000_000) // 10_000}만"
        if power_int >= 10_000:
            return f"{power_int // 10_000}만"
        return str(power_int)

    async def _send_reaction_image(
        self, message: discord.Message, reaction: str, default: str
    ) -> None:
        image_category = reaction if reaction in {"joy", "love", "scary", "tease", "annoy"} else default
        await self._maybe_send_image(message, image_category)

    async def _maybe_send_image(
        self, message: discord.Message, category: str, force: bool = False
    ) -> None:
        if not force and random.random() > self._image_send_prob:
            return
        image_path = self._pick_random_image(category)
        if image_path is None:
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
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        ]
        if not candidates:
            return None
        return random.choice(candidates)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(KalingCog(bot))
