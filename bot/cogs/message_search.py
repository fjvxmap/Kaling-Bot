from __future__ import annotations

import asyncio
import logging
import os
import unicodedata
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Awaitable, Callable, Sequence

import discord
from discord import app_commands
from discord.ext import commands


LOGGER = logging.getLogger("kaling.message_search")

MESSAGE_SEARCH_PERIODS = [
    app_commands.Choice(name="최근 24시간", value=1),
    app_commands.Choice(name="최근 7일", value=7),
    app_commands.Choice(name="최근 30일", value=30),
    app_commands.Choice(name="최근 90일", value=90),
    app_commands.Choice(name="최근 1년", value=365),
    app_commands.Choice(name="전체 기간", value=0),
]
NO_VISIBLE_RESULTS_MESSAGE = (
    "검색 후 채널 권한이 변경되었거나 확인할 수 없어 "
    "표시할 결과가 없습니다."
)


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
    """Concurrency for complete on-demand history scans.

    Discord does not expose its client-side guild search through discord.py, so
    the bot has to inspect channel histories itself. A small concurrency bound
    avoids flooding the API while still allowing every channel to finish.
    """

    concurrency: int = 5

    @classmethod
    def from_env(cls) -> MessageSearchConfig:
        return cls(
            concurrency=_bounded_env_int(
                "KALING_MESSAGE_SEARCH_CONCURRENCY",
                5,
                minimum=1,
                maximum=10,
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
    failed_channels: int = 0
    total_channels: int = 0
    content_messages: int = 0
    scope_label: str = "전체 기간"


@dataclass(frozen=True)
class _ChannelSearchResult:
    messages: tuple[MessageSearchResult, ...]
    scanned_messages: int
    content_messages: int
    failed: bool = False


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


class MessageSearchEngine:
    def __init__(self, config: MessageSearchConfig) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency)

    async def search(
        self,
        channels: Sequence[Any],
        keyword: str,
        *,
        discovery_failures: int = 0,
        after: datetime | None = None,
        scope_label: str = "전체 기간",
    ) -> MessageSearchReport:
        normalized_keyword = _normalized(keyword)

        async def run(channel: Any) -> _ChannelSearchResult:
            async with self._semaphore:
                return await self._search_channel(
                    channel,
                    normalized_keyword,
                    after=after,
                )

        tasks = [asyncio.create_task(run(channel)) for channel in channels]
        if not tasks:
            return MessageSearchReport(
                results=(),
                searched_channels=0,
                scanned_messages=0,
                failed_channels=discovery_failures,
                total_channels=0,
                scope_label=scope_label,
            )

        channel_reports: list[_ChannelSearchResult] = []
        unexpected_failures = 0
        for outcome in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(outcome, BaseException):
                if isinstance(outcome, asyncio.CancelledError):
                    raise outcome
                # A broken or newly unsupported channel should not discard
                # results already collected from every other channel.
                LOGGER.error(
                    "Unexpected error while scanning a message channel: %s",
                    type(outcome).__name__,
                )
                unexpected_failures += 1
                continue
            channel_reports.append(outcome)

        failed_channels = discovery_failures + unexpected_failures + sum(
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
        return MessageSearchReport(
            results=tuple(all_results),
            searched_channels=searched_channels,
            scanned_messages=sum(
                report.scanned_messages
                for report in channel_reports
                if not report.failed
            ),
            failed_channels=failed_channels,
            total_channels=len(channels),
            content_messages=sum(
                report.content_messages
                for report in channel_reports
                if not report.failed
            ),
            scope_label=scope_label,
        )

    async def _search_channel(
        self,
        channel: Any,
        normalized_keyword: str,
        *,
        after: datetime | None,
    ) -> _ChannelSearchResult:
        messages: list[MessageSearchResult] = []
        scanned = 0
        content_messages = 0
        history_options: dict[str, Any] = {
            "limit": None,
            "oldest_first": after is not None,
        }
        if after is not None:
            history_options["after"] = after
        try:
            async for message in channel.history(**history_options):
                scanned += 1
                if message.content:
                    content_messages += 1
                if normalized_keyword not in _normalized(message.content):
                    continue
                messages.append(MessageSearchResult.from_message(message))
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            LOGGER.info(
                "Could not scan channel id=%s: %s",
                getattr(channel, "id", "unknown"),
                type(exc).__name__,
            )
            return _ChannelSearchResult(
                (),
                scanned,
                content_messages,
                failed=True,
            )
        return _ChannelSearchResult(
            tuple(messages),
            scanned,
            content_messages,
        )


class MessageSearchView(discord.ui.View):
    def __init__(
        self,
        requester_id: int,
        keyword: str,
        report: MessageSearchReport,
        *,
        permission_filter: (
            Callable[[MessageSearchReport], Awaitable[MessageSearchReport]] | None
        ) = None,
    ) -> None:
        super().__init__(timeout=300)
        if not report.results:
            raise ValueError("A search result view needs at least one result.")
        self.requester_id = requester_id
        self.keyword = keyword
        self.report = report
        self.permission_filter = permission_filter
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
        self.message: discord.Message | None = None
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
        await interaction.response.defer()
        if not await self._refresh_permissions():
            await interaction.edit_original_response(
                content=NO_VISIBLE_RESULTS_MESSAGE,
                embed=None,
                view=None,
            )
            return
        self.index = max(0, self.index - 1)
        self._sync_buttons()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="▶️")
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[MessageSearchView],
    ) -> None:
        del button
        await interaction.response.defer()
        if not await self._refresh_permissions():
            await interaction.edit_original_response(
                content=NO_VISIBLE_RESULTS_MESSAGE,
                embed=None,
                view=None,
            )
            return
        self.index = min(len(self.report.results) - 1, self.index + 1)
        self._sync_buttons()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    async def _refresh_permissions(self) -> bool:
        if self.permission_filter is None:
            return True
        self.report = await self.permission_filter(self.report)
        if self.report.results:
            self.index = min(self.index, len(self.report.results) - 1)
            return True

        self.stop()
        return False

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
        notes = [
            f"결과 {self.index + 1}/{result_count}",
            self.report.scope_label,
            f"확인한 기록 {self.report.scanned_messages:,}개",
            f"완료 채널 {self.report.searched_channels}개",
        ]
        if self.report.failed_channels:
            notes.append(
                f"일부 기록 조회 실패 {self.report.failed_channels}곳"
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
        description="볼 수 있는 서버 채널의 메시지 기록을 기간별로 비공개 검색합니다.",
    )
    @app_commands.guild_only()
    @app_commands.rename(keyword="키워드", channel="채널", period="기간")
    @app_commands.describe(
        keyword="메시지 본문에서 찾을 키워드",
        channel="한 채널만 검색하려면 선택하세요. 비우면 접근 가능한 서버 기록 전체를 검색합니다.",
        period="검색할 기간입니다. 비우면 전체 기간을 검색합니다.",
    )
    @app_commands.choices(period=MESSAGE_SEARCH_PERIODS)
    async def search(
        self,
        interaction: discord.Interaction,
        keyword: app_commands.Range[str, 2, 100],
        channel: discord.TextChannel | None = None,
        period: app_commands.Choice[int] | None = None,
    ) -> None:
        requester_id = interaction.user.id
        if requester_id in self._active_requesters:
            await interaction.response.send_message(
                "이미 진행 중인 메시지 검색이 있습니다.",
                ephemeral=True,
            )
            return

        keyword = keyword.strip()
        if len(keyword) < 2:
            await interaction.response.send_message(
                "검색어는 두 글자 이상 입력해 주세요.",
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
            scope_label = period.name if period is not None else "전체 기간"
            after = None
            if period is not None and period.value > 0:
                after = datetime.now(UTC) - timedelta(days=period.value)
            channels, discovery_failures = await self._candidate_channels(
                guild,
                requester,
                bot_member,
                selected_channel=channel,
                current_channel=interaction.channel,
            )
            if not channels:
                message = (
                    "요청자와 봇이 모두 메시지 기록을 읽을 수 있는 "
                    "채널이 없습니다."
                )
                if discovery_failures:
                    message += (
                        f"\n다만 {discovery_failures}곳은 Discord API 오류로 "
                        "접근 여부를 확인하지 못했습니다."
                    )
                await self._deliver_text(interaction, requester, message)
                return

            report = await self.engine.search(
                channels,
                keyword,
                discovery_failures=discovery_failures,
                after=after,
                scope_label=scope_label,
            )
            report = await self._filter_report_current_permissions(
                report,
                channels,
                guild,
                requester_id,
                bot_member.id,
            )
            if not report.results:
                await self._deliver_text(
                    interaction,
                    requester,
                    self._empty_result_message(report),
                )
                return

            async def permission_filter(
                current_report: MessageSearchReport,
            ) -> MessageSearchReport:
                return await self._filter_report_current_permissions(
                    current_report,
                    channels,
                    guild,
                    requester_id,
                    bot_member.id,
                )

            view = MessageSearchView(
                requester_id,
                keyword,
                report,
                permission_filter=permission_filter,
            )
            await self._deliver_results(interaction, requester, view)
        except Exception:
            LOGGER.exception(
                "Message search failed for guild id=%s and requester id=%s.",
                guild.id,
                requester_id,
            )
            await self._deliver_error(interaction, requester)
        finally:
            self._active_requesters.discard(requester_id)

    async def _candidate_channels(
        self,
        guild: discord.Guild,
        requester: discord.Member,
        bot_member: discord.Member,
        *,
        selected_channel: discord.TextChannel | None,
        current_channel: Any,
    ) -> tuple[list[Any], int]:
        if selected_channel is not None:
            if selected_channel.guild.id != guild.id:
                return [], 0
            try:
                searchable = await self._channel_is_searchable(
                    selected_channel,
                    requester,
                    bot_member,
                )
            except (discord.Forbidden, discord.HTTPException):
                return [], 1
            if searchable:
                return [selected_channel], 0
            return [], 0

        message_channel_types = (
            discord.TextChannel,
            discord.VoiceChannel,
            discord.StageChannel,
        )
        candidates: list[Any] = [
            candidate
            for candidate in guild.channels
            if isinstance(candidate, message_channel_types)
        ]
        discovery_failures = 0
        try:
            candidates.extend(await guild.active_threads())
        except (discord.Forbidden, discord.HTTPException):
            candidates.extend(guild.threads)
            discovery_failures += 1

        archive_parents = [
            candidate
            for candidate in guild.channels
            if isinstance(candidate, (discord.TextChannel, discord.ForumChannel))
            and self._base_channel_is_searchable(
                candidate,
                requester,
                bot_member,
            )
        ]
        for parent in archive_parents:
            try:
                async for thread in parent.archived_threads(limit=None):
                    candidates.append(thread)
            except (discord.Forbidden, discord.HTTPException):
                discovery_failures += 1
            if not isinstance(parent, discord.TextChannel):
                continue
            try:
                async for thread in parent.archived_threads(
                    private=True,
                    joined=True,
                    limit=None,
                ):
                    candidates.append(thread)
            except (discord.Forbidden, discord.HTTPException):
                discovery_failures += 1

        # Keep the invoking channel first. IDs remove threads returned by both
        # the active and archived endpoints.
        current_id = getattr(current_channel, "id", None)
        unique = {candidate.id: candidate for candidate in candidates}
        ordered = list(unique.values())
        ordered.sort(key=lambda candidate: candidate.id != current_id)
        searchable: list[Any] = []
        for candidate in ordered:
            try:
                can_search = await self._channel_is_searchable(
                    candidate,
                    requester,
                    bot_member,
                )
            except (discord.Forbidden, discord.HTTPException):
                discovery_failures += 1
                continue
            if can_search:
                searchable.append(candidate)
        return searchable, discovery_failures

    @staticmethod
    def _base_channel_is_searchable(
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

        return True

    @classmethod
    async def _channel_is_searchable(
        cls,
        channel: Any,
        requester: discord.Member,
        bot_member: discord.Member,
    ) -> bool:
        if not cls._base_channel_is_searchable(channel, requester, bot_member):
            return False
        if not isinstance(channel, discord.Thread) or not channel.is_private():
            return True

        requester_permissions = channel.permissions_for(requester)
        if requester_permissions.manage_threads:
            return True
        try:
            await channel.fetch_member(requester.id)
        except discord.NotFound:
            return False
        return True

    @classmethod
    async def _filter_report_permissions(
        cls,
        report: MessageSearchReport,
        channels: Sequence[Any],
        requester: discord.Member,
        bot_member: discord.Member,
    ) -> MessageSearchReport:
        result_channel_ids = {result.channel_id for result in report.results}
        if not result_channel_ids:
            return report

        allowed_ids: set[int] = set()
        revoked_channels = 0
        for channel in channels:
            if channel.id not in result_channel_ids:
                continue
            try:
                searchable = await cls._channel_is_searchable(
                    channel,
                    requester,
                    bot_member,
                )
            except (discord.Forbidden, discord.HTTPException):
                searchable = False
            if searchable:
                allowed_ids.add(channel.id)
            else:
                revoked_channels += 1

        if not revoked_channels:
            return report
        return replace(
            report,
            results=tuple(
                result
                for result in report.results
                if result.channel_id in allowed_ids
            ),
            searched_channels=max(0, report.searched_channels - revoked_channels),
            failed_channels=report.failed_channels + revoked_channels,
        )

    @classmethod
    async def _filter_report_current_permissions(
        cls,
        report: MessageSearchReport,
        channels: Sequence[Any],
        guild: discord.Guild,
        requester_id: int,
        bot_member_id: int,
    ) -> MessageSearchReport:
        if not report.results:
            return report
        try:
            requester = await guild.fetch_member(requester_id)
            bot_member = await guild.fetch_member(bot_member_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            affected_channels = len(
                {result.channel_id for result in report.results}
            )
            return replace(
                report,
                results=(),
                searched_channels=max(
                    0,
                    report.searched_channels - affected_channels,
                ),
                failed_channels=report.failed_channels + affected_channels,
            )
        return await cls._filter_report_permissions(
            report,
            channels,
            requester,
            bot_member,
        )

    @staticmethod
    async def _deliver_results(
        interaction: discord.Interaction,
        requester: discord.Member,
        view: MessageSearchView,
    ) -> None:
        send_options = {
            "embed": view.embed(),
            "view": view,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        try:
            view.message = await interaction.followup.send(
                **send_options,
                ephemeral=True,
                wait=True,
            )
            return
        except (discord.NotFound, discord.HTTPException) as exc:
            LOGGER.info(
                "Private interaction response expired or failed; using DM: %s",
                type(exc).__name__,
            )

        try:
            view.message = await requester.send(
                "검색이 오래 걸려 비공개 응답이 만료되어 DM으로 결과를 보냅니다.",
                **send_options,
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            LOGGER.warning(
                "Could not deliver completed message search to requester id=%s: %s",
                requester.id,
                type(exc).__name__,
            )

    @staticmethod
    async def _deliver_error(
        interaction: discord.Interaction,
        requester: discord.Member,
    ) -> None:
        message = "검색 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        await MessageSearchCog._deliver_text(interaction, requester, message)

    @staticmethod
    async def _deliver_text(
        interaction: discord.Interaction,
        requester: discord.Member,
        message: str,
    ) -> None:
        try:
            await interaction.followup.send(message, ephemeral=True)
            return
        except (discord.NotFound, discord.HTTPException):
            pass
        try:
            await requester.send(
                "비공개 응답이 만료되어 DM으로 검색 상태를 보냅니다.\n\n"
                f"{message}"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    @staticmethod
    def _empty_result_message(report: MessageSearchReport) -> str:
        details = [
            f"검색 범위: {report.scope_label}",
            "읽기에 성공한 "
            f"{report.searched_channels}개 채널에서 "
            f"메시지 {report.scanned_messages:,}개를 끝까지 확인했지만 "
            "결과가 없습니다.",
        ]
        if report.failed_channels:
            details.append(
                f"다만 {report.failed_channels}곳은 권한 변경 또는 Discord API 오류로 "
                "기록을 읽지 못했습니다."
            )
        if report.scanned_messages >= 10 and report.content_messages == 0:
            details.append(
                "메시지 본문을 하나도 받지 못했습니다. Discord Developer Portal에서 Message Content Intent를 확인해 주세요."
            )
        return "\n".join(details)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageSearchCog(bot))
