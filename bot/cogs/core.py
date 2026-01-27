from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class Core(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Bot response test")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!")

    @commands.command(name="ping")
    async def message_ping(self, ctx: commands.Context) -> None:
        await ctx.send("Pong!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Core(bot))
