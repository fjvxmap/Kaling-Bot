from __future__ import annotations

import asyncio
import logging
import os
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import discord
from discord import app_commands
from discord.ext import commands


LOGGER = logging.getLogger("kaling.message_search")


def _bounded_env_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        LOGGER.warning("Ignoring invalid integer value for %s.", name)
        return default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class MessageSearchConfig:
    """Resource limits for history scans.

    Discord does not expose its client-side guild search through discord.py, so
    the bot has to inspect channel histories.  These limits keep that operation
    predictable even in a large guild.
    """

    history_per_channel: int = 1_000
    max_results: int = 100
    max_channels: int = 100
    concurrency: int = 3
    timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> MessageSearchConfig:
        return cls(
            history_per_channel=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_HISTORY_PER_CHANNEL",
                1_000,
                minimum=50,
                maximum=10_000,
            ),
            max_results=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_MAX_RESULTS",
                100,
                minimum=10,
                maximum=500,
            ),
            max_channels=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_MAX_CHANNELS",
                100,
                minimum=1,
                maximum=500,
            ),
            concurrency=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_CONCURRENCY",
                3,
                minimum=1,
                maximum=10,
            ),
            timeout_seconds=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_TIMEOUT_SECONDS",
                20,
                minimum=5,
                maximum=60,
            ),
        )


@dataclass(frozen=True)
class MessageSearchResult:
    message_id: int
    channel_id: int
    channel_name: str
    author_name: str
    content: str
    created_at: datetime
    jump_url: str
    attachment_count: int = 0

    @classmethod
    def from_message(cls, message: discord.Message) -> MessageSearchResult:
        channel = message.channel
        author = message.author
        return cls(
            message_id=message.id,
            channel_id=channel.id,
            channel_name=getattr(channel, "name", str(channel)),
            author_name=getattr(author, "display_name", str(author)),
            content=message.content,
            created_at=message.created_at,
            jump_url=message.jump_url,
            attachment_count=len(message.attachments),
        )


@dataclass(frozen=True)
class MessageSearchReport:
    results: tuple[MessageSearchResult, ...]
    searched_channels: int
    scanned_messages: int
    history_per_channel: int
    failed_channels: int = 0
    omitted_channels: int = 0
    timed_out_channels: int = 0
    timed_out: bool = False
    results_truncated: bool = False


@dataclass(frozen=True)
class _ChannelSearchResult:
    messages: tuple[MessageSearchResult, ...]
    scanned_messages: int
    failed: bool = False
    truncated: bool = False


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


class MessageSearchEngine:
    def __init__(self, config: MessageSearchConfig) -> None:
        self.config = config

    async def search(
        self,
        channels: Sequence[Any],
        keyword: str,
        *,
        omitted_channels: int = 0,
    ) -> MessageSearchReport:
        normalized_keyword = _normalized(keyword)
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def run(channel: Any) -> _ChannelSearchResult:
            async with semaphore:
                return await self._search_channel(channel, normalized_keyword)

        tasks = [asyncio.create_task(run(channel)) for channel in channels]
        if not tasks:
            return MessageSearchReport(
                results=(),
                searched_channels=0,
                scanned_messages=0,
                history_per_channel=self.config.history_per_channel,
                omitted_channels=omitted_channels,
            )

        done, pending = await asyncio.wait(
            tasks,
            timeout=self.config.timeout_seconds,
        )
        timed_out = bool(pending)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        channel_reports: list[_ChannelSearchResult] = []
        unexpected_failures = 0
        for task in done:
            try:
                channel_report = task.result()
            except Exception:
                # A broken or newly unsupported channel should not discard
                # results already collected from every other channel.
                LOGGER.exception("Unexpected error while scanning a message channel.")
                unexpected_failures += 1
                continue
            channel_reports.append(channel_report)

        failed_channels = unexpected_failures + sum(
            int(report.failed) for report in channel_reports
        )
        searched_channels = sum(
            int(not report.failed) for report in channel_reports
        )

        all_results = [
            result
            for channel_report in channel_reports
            for result in channel_report.messages
        ]
        all_results.sort(
            key=lambda result: (result.created_at, result.message_id),
            reverse=True,
        )
        results_truncated = (
            len(all_results) > self.config.max_results
            or any(report.truncated for report in channel_reports)
        )
        results = tuple(all_results[: self.config.max_results])
        return MessageSearchReport(
            results=results,
            searched_channels=searched_channels,
            scanned_messages=sum(report.scanned_messages for report in channel_reports),
            history_per_channel=self.config.history_per_channel,
            failed_channels=failed_channels,
            omitted_channels=omitted_channels,
            timed_out_channels=len(pending),
            timed_out=timed_out,
            results_truncated=results_truncated,
        )

    async def _search_channel(
        self,
        channel: Any,
        normalized_keyword: str,
    ) -> _ChannelSearchResult:
        messages: list[MessageSearchResult] = []
        scanned = 0
        try:
            async for message in channel.history(
                limit=self.config.history_per_channel,
                oldest_first=False,
            ):
                scanned += 1
                if normalized_keyword not in _normalized(message.content):
                    continue
                messages.append(MessageSearchResult.from_message(message))
                if len(messages) > self.config.max_results:
                    break
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            LOGGER.info(
                "Could not scan channel id=%s: %s",
                getattr(channel, "id", "unknown"),
                type(exc).__name__,
            )
            return _ChannelSearchResult(
                tuple(messages[: self.config.max_results]),
                scanned,
                failed=True,
                truncated=len(messages) > self.config.max_results,
            )
        return _ChannelSearchResult(
            tuple(messages[: self.config.max_results]),
            scanned,
            truncated=len(messages) > self.config.max_results,
        )


class MessageSearchView(discord.ui.View):
    def __init__(
        self,
        requester_id: int,
        keyword: str,
        report: MessageSearchReport,
    ) -> None:
        super().__init__(timeout=300)
        if not report.results:
            raise ValueError("A search result view needs at least one result.")
        self.requester_id = requester_id
        self.keyword = keyword
        self.report = report
        self.index = 0
        self.jump_button = discord.ui.Button(
            label="메시지로 이동",
            style=discord.ButtonStyle.link,
            url=report.results[0].jump_url,
            emoji="↗️",
        )
        self.remove_item(self.next)
        self.add_item(self.jump_button)
        self.add_item(self.next)
        self.message: discord.WebhookMessage | None = None
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "이 검색 결과는 명령을 실행한 사람만 조작할 수 있습니다.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        self.previous.disabled = True
        self.next.disabled = True
        if self.message is None:
            return
        try:
            await self.message.edit(view=self)
        except (discord.NotFound, discord.HTTPException):
            pass

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def previous(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[MessageSearchView],
    ) -> None:
        del button
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[MessageSearchView],
    ) -> None:
        del button
        self.index = min(len(self.report.results) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    def _sync_buttons(self) -> None:
        self.previous.disabled = self.index == 0
        self.next.disabled = self.index == len(self.report.results) - 1
        self.jump_button.url = self.report.results[self.index].jump_url

    def embed(self) -> discord.Embed:
        result = self.report.results[self.index]
        content = result.content.strip()
        if content:
            content = discord.utils.escape_markdown(
                discord.utils.escape_mentions(content)
            )
            if len(content) > 3_500:
                content = f"{content[:3_499]}…"
        else:
            content = "*텍스트가 없는 메시지입니다.*"
        if result.attachment_count:
            content += f"\n\n📎 첨부 파일 {result.attachment_count}개"

        display_keyword = discord.utils.escape_markdown(
            self.keyword.replace("\n", " ").replace("\r", " ")
        )
        embed = discord.Embed(
            title=f"‘{display_keyword}’ 검색 결과",
            description=content,
            color=0x5865F2,
            timestamp=result.created_at,
        )
        embed.add_field(name="채널", value=f"<#{result.channel_id}>", inline=True)
        author_name = discord.utils.escape_markdown(result.author_name)
        if len(author_name) > 1_024:
            author_name = f"{author_name[:1_023]}…"
        embed.add_field(name="작성자", value=author_name, inline=True)

        result_count = len(self.report.results)
        count_label = f"{result_count}+" if self.report.results_truncated else str(result_count)
        notes = [
            f"결과 {self.index + 1}/{count_label}",
            f"{self.report.searched_channels}개 채널 · {self.report.scanned_messages:,}개 메시지 확인",
            f"채널당 최근 {self.report.history_per_channel:,}개 기준(이전 기록 미검색 가능)",
        ]
        if self.report.omitted_channels:
            notes.append(f"채널 제한으로 {self.report.omitted_channels}개 미검색")
        if self.report.failed_channels:
            notes.append(f"읽기 실패 {self.report.failed_channels}개")
        if self.report.timed_out:
            notes.append(
                f"시간 제한으로 {self.report.timed_out_channels}개 채널 미완료"
            )
        embed.set_footer(text=" · ".join(notes))
        return embed


class MessageSearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = MessageSearchConfig.from_env()
        self.engine = MessageSearchEngine(self.config)
        self._active_requesters: set[int] = set()

    @app_commands.command(
        name="메시지검색",
        description="볼 수 있는 일반 채널의 메시지를 비공개로 검색합니다.",
    )
    @app_commands.guild_only()
    @app_commands.rename(keyword="키워드", channel="채널")
    @app_commands.describe(
        keyword="메시지 본문에서 찾을 키워드",
        channel="한 채널만 검색하려면 선택하세요. 비우면 일반 채널과 활성 공개 스레드를 검색합니다.",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        keyword: app_commands.Range[str, 1, 100],
        channel: discord.TextChannel | None = None,
    ) -> None:
        requester_id = interaction.user.id
        if requester_id in self._active_requesters:
            await interaction.response.send_message(
                "이미 진행 중인 메시지 검색이 있습니다.",
                ephemeral=True,
            )
            return

        keyword = keyword.strip()
        if not keyword:
            await interaction.response.send_message(
                "공백이 아닌 검색어를 입력해 주세요.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "메시지 검색은 서버 안에서만 사용할 수 있습니다.",
                ephemeral=True,
            )
            return

        bot_member = guild.me
        if bot_member is None and self.bot.user is not None:
            bot_member = guild.get_member(self.bot.user.id)
        requester = interaction.user
        if not isinstance(requester, discord.Member):
            requester = guild.get_member(requester_id)
        if requester is None or bot_member is None:
            await interaction.response.send_message(
                "서버 권한 정보를 확인할 수 없어 검색하지 않았습니다.",
                ephemeral=True,
            )
            return

        self._active_requesters.add(requester_id)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            channels, omitted_channels = self._candidate_channels(
                guild,
                requester,
                bot_member,
                selected_channel=channel,
                current_channel=interaction.channel,
            )
            if not channels:
                await interaction.followup.send(
                    "요청자와 봇이 모두 메시지 기록을 읽을 수 있는 채널이 없습니다.",
                    ephemeral=True,
                )
                return

            report = await self.engine.search(
                channels,
                keyword,
                omitted_channels=omitted_channels,
            )
            if not report.results:
                await interaction.followup.send(
                    self._empty_result_message(report),
                    ephemeral=True,
                )
                return

            view = MessageSearchView(requester_id, keyword, report)
            view.message = await interaction.followup.send(
                embed=view.embed(),
                view=view,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
                wait=True,
            )
        except Exception:
            LOGGER.exception(
                "Message search failed for guild id=%s and requester id=%s.",
                guild.id,
                requester_id,
            )
            await interaction.followup.send(
                "검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )
        finally:
            self._active_requesters.discard(requester_id)

    def _candidate_channels(
        self,
        guild: discord.Guild,
        requester: discord.Member,
        bot_member: discord.Member,
        *,
        selected_channel: discord.TextChannel | None,
        current_channel: Any,
    ) -> tuple[list[Any], int]:
        if selected_channel is not None:
            if (
                selected_channel.guild.id == guild.id
                and self._channel_is_searchable(selected_channel, requester, bot_member)
            ):
                return [selected_channel], 0
            return [], 0

        candidates: list[Any] = [
            candidate
            for candidate in guild.channels
            if isinstance(candidate, discord.TextChannel)
        ]
        candidates.extend(guild.threads)

        # Keep the invoking channel first so a channel cap never makes a local
        # search less useful.  IDs also remove a thread duplicated by cache data.
        current_id = getattr(current_channel, "id", None)
        unique = {candidate.id: candidate for candidate in candidates}
        ordered = list(unique.values())
        ordered.sort(key=lambda candidate: candidate.id != current_id)
        searchable = [
            candidate
            for candidate in ordered
            if self._channel_is_searchable(candidate, requester, bot_member)
        ]
        omitted = max(0, len(searchable) - self.config.max_channels)
        return searchable[: self.config.max_channels], omitted

    @staticmethod
    def _channel_is_searchable(
        channel: Any,
        requester: discord.Member,
        bot_member: discord.Member,
    ) -> bool:
        try:
            requester_permissions = channel.permissions_for(requester)
            bot_permissions = channel.permissions_for(bot_member)
        except (AttributeError, discord.ClientException):
            return False

        requester_can_read = (
            requester_permissions.view_channel
            and requester_permissions.read_message_history
        )
        bot_can_read = (
            bot_permissions.view_channel and bot_permissions.read_message_history
        )
        if not requester_can_read or not bot_can_read:
            return False

        # Private thread membership cannot be verified reliably without the
        # privileged members intent and extra API calls. Excluding them avoids
        # exposing a cached thread after a requester has left it.
        if isinstance(channel, discord.Thread) and channel.is_private():
            return False
        return True

    @staticmethod
    def _empty_result_message(report: MessageSearchReport) -> str:
        details = [
            f"{report.searched_channels}개 채널에서 메시지 {report.scanned_messages:,}개를 확인했지만 결과가 없습니다.",
            f"채널당 최근 {report.history_per_channel:,}개 메시지만 검색하므로 이전 기록은 남아 있을 수 있습니다.",
        ]
        if report.omitted_channels:
            details.append(f"채널 제한으로 {report.omitted_channels}개 채널은 검색하지 않았습니다.")
        if report.failed_channels:
            details.append(f"{report.failed_channels}개 채널은 읽는 중 오류가 발생했습니다.")
        if report.timed_out:
            details.append(
                f"시간 제한에 도달해 {report.timed_out_channels}개 채널을 완료하지 못했습니다."
            )
        return "\n".join(details)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageSearchCog(bot))
