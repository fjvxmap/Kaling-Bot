from __future__ import annotations

import logging

import discord
from discord.ext import commands

from .config import load_config
from .logging import setup_logging

LOGGER = logging.getLogger("kaling.bot")


class KalingBot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("bot.cogs.core")
        await self.load_extension("bot.cogs.maple")
        await self.load_extension("bot.cogs.rpg")
        await self.tree.sync()
        LOGGER.info("App commands synced.")


def build_bot() -> KalingBot:
    intents = discord.Intents.default()
    intents.message_content = True
    return KalingBot(command_prefix="!", intents=intents)


def run_bot() -> None:
    setup_logging()
    config = load_config()
    bot = build_bot()
    bot.run(config.token)
