from __future__ import annotations

import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from bot.cogs.message_search import (
    MessageSearchCog,
    MessageSearchConfig,
    MessageSearchEngine,
    MessageSearchReport,
    MessageSearchResult,
    MessageSearchView,
)


class FakeMessage:
    def __init__(
        self,
        message_id: int,
        channel: FakeChannel,
        content: str,
        created_at: datetime,
    ) -> None:
        self.id = message_id
        self.channel = channel
        self.content = content
        self.created_at = created_at
        self.jump_url = f"https://discord.com/channels/1/{channel.id}/{message_id}"
        self.author = SimpleNamespace(display_name=f"author-{message_id}")
        self.attachments: list[object] = []


class FakeChannel:
    def __init__(self, channel_id: int, name: str = "channel") -> None:
        self.id = channel_id
        self.name = name
        self.messages: list[FakeMessage] = []
        self.history_limits: list[int | None] = []
        self.history_afters: list[datetime | None] = []
        self.history_oldest_first: list[bool] = []

    async def history(
        self,
        *,
        limit: int | None,
        oldest_first: bool,
        after: datetime | None = None,
    ):
        self.history_limits.append(limit)
        self.history_afters.append(after)
        self.history_oldest_first.append(oldest_first)
        for message in self.messages[:limit]:
            if after is not None and message.created_at <= after:
                continue
            yield message


class MessageSearchConfigTests(unittest.TestCase):
    def test_environment_values_are_bounded_and_invalid_values_fall_back(self) -> None:
        with patch.dict(
            os.environ,
            {"KALING_MESSAGE_SEARCH_CONCURRENCY": "0"},
            clear=False,
        ):
            config = MessageSearchConfig.from_env()

        self.assertEqual(config.concurrency, 1)
        self.assertFalse(hasattr(config, "history_per_channel"))
        self.assertFalse(hasattr(config, "max_results"))
        self.assertFalse(hasattr(config, "max_channels"))
        self.assertFalse(hasattr(config, "timeout_seconds"))


class MessageSearchEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_search_reaches_messages_beyond_first_thousand(self) -> None:
        now = datetime.now(UTC)
        channel = FakeChannel(10)
        channel.messages = [
            FakeMessage(
                index,
                channel,
                "10시" if index == 1_001 else "unrelated",
                now - timedelta(seconds=index),
            )
            for index in range(1, 1_002)
        ]
        engine = MessageSearchEngine(MessageSearchConfig())

        report = await engine.search([channel], "10시")

        self.assertEqual([result.message_id for result in report.results], [1_001])
        self.assertEqual(report.scanned_messages, 1_001)
        self.assertEqual(channel.history_limits, [None])
        self.assertEqual(channel.history_afters, [None])
        self.assertEqual(channel.history_oldest_first, [False])

    async def test_optional_period_limits_history_without_changing_full_default(self) -> None:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=7)
        channel = FakeChannel(10)
        channel.messages = [
            FakeMessage(1, channel, "needle recent", now - timedelta(days=1)),
            FakeMessage(2, channel, "needle old", now - timedelta(days=30)),
        ]
        engine = MessageSearchEngine(MessageSearchConfig())

        report = await engine.search(
            [channel],
            "needle",
            after=cutoff,
            scope_label="최근 7일",
        )

        self.assertEqual([result.message_id for result in report.results], [1])
        self.assertEqual(channel.history_limits, [None])
        self.assertEqual(channel.history_afters, [cutoff])
        self.assertEqual(channel.history_oldest_first, [True])
        self.assertEqual(report.scope_label, "최근 7일")

    async def test_searches_across_channels_case_insensitively_and_sorts_newest(self) -> None:
        now = datetime.now(UTC)
        first = FakeChannel(10, "first")
        second = FakeChannel(20, "second")
        first.messages = [
            FakeMessage(1, first, "Needle from yesterday", now - timedelta(days=1)),
            FakeMessage(2, first, "unrelated", now - timedelta(days=2)),
        ]
        second.messages = [
            FakeMessage(3, second, "ＮＥＥＤＬＥ from today", now),
        ]
        engine = MessageSearchEngine(
            MessageSearchConfig(concurrency=2)
        )

        report = await engine.search([first, second], "needle")

        self.assertEqual([result.message_id for result in report.results], [3, 1])
        self.assertEqual(report.searched_channels, 2)
        self.assertEqual(report.scanned_messages, 3)
        self.assertEqual(report.content_messages, 3)

    async def test_waits_for_slow_channels_instead_of_timing_out(self) -> None:
        class SlowChannel(FakeChannel):
            async def history(self, *, limit: int, oldest_first: bool):
                del limit, oldest_first
                await asyncio.sleep(0.01)
                yield self.messages[0]

        now = datetime.now(UTC)
        fast = FakeChannel(10)
        fast.messages = [FakeMessage(1, fast, "needle", now)]
        slow = SlowChannel(20)
        slow.messages = [FakeMessage(2, slow, "needle", now - timedelta(seconds=1))]
        engine = MessageSearchEngine(MessageSearchConfig(concurrency=2))

        report = await engine.search([fast, slow], "needle")

        self.assertEqual([result.message_id for result in report.results], [1, 2])
        self.assertEqual(report.searched_channels, 2)
        self.assertEqual(report.scanned_messages, 2)

    async def test_returns_every_matching_result_without_a_result_cap(self) -> None:
        now = datetime.now(UTC)
        channel = FakeChannel(10)
        channel.messages = [
            FakeMessage(index, channel, "needle", now - timedelta(seconds=index))
            for index in range(1, 502)
        ]
        engine = MessageSearchEngine(MessageSearchConfig(concurrency=1))

        report = await engine.search([channel], "needle")

        self.assertEqual(len(report.results), 501)
        self.assertEqual(report.results[-1].message_id, 501)

    async def test_failed_channel_does_not_discard_other_results(self) -> None:
        class ForbiddenChannel(FakeChannel):
            async def history(self, *, limit: int, oldest_first: bool):
                del limit, oldest_first
                response = SimpleNamespace(status=403, reason="Forbidden")
                raise discord.Forbidden(response, "denied")
                if False:
                    yield None

        now = datetime.now(UTC)
        readable = FakeChannel(10)
        readable.messages = [FakeMessage(1, readable, "needle", now)]
        engine = MessageSearchEngine(MessageSearchConfig(concurrency=2))

        report = await engine.search(
            [ForbiddenChannel(20), readable],
            "needle",
        )

        self.assertEqual([result.message_id for result in report.results], [1])
        self.assertEqual(report.searched_channels, 1)
        self.assertEqual(report.failed_channels, 1)

    async def test_partial_results_from_a_failed_channel_are_discarded(self) -> None:
        class PartiallyForbiddenChannel(FakeChannel):
            async def history(self, *, limit: int | None, oldest_first: bool):
                self.history_limits.append(limit)
                self.assert_oldest_first = oldest_first
                yield self.messages[0]
                response = SimpleNamespace(status=403, reason="Forbidden")
                raise discord.Forbidden(response, "denied")

        now = datetime.now(UTC)
        partial = PartiallyForbiddenChannel(20)
        partial.messages = [FakeMessage(2, partial, "needle", now)]
        readable = FakeChannel(10)
        readable.messages = [
            FakeMessage(1, readable, "needle", now - timedelta(seconds=1))
        ]
        engine = MessageSearchEngine(MessageSearchConfig(concurrency=2))

        report = await engine.search([partial, readable], "needle")

        self.assertEqual([result.message_id for result in report.results], [1])
        self.assertEqual(report.scanned_messages, 1)
        self.assertEqual(report.content_messages, 1)
        self.assertEqual(report.failed_channels, 1)
        self.assertEqual(partial.history_limits, [None])
        self.assertFalse(partial.assert_oldest_first)

    async def test_concurrent_searches_share_the_engine_concurrency_limit(self) -> None:
        active = 0
        peak = 0

        class TrackedChannel(FakeChannel):
            async def history(self, *, limit: int | None, oldest_first: bool):
                nonlocal active, peak
                self.history_limits.append(limit)
                self.assert_oldest_first = oldest_first
                active += 1
                peak = max(peak, active)
                try:
                    await asyncio.sleep(0.01)
                    yield self.messages[0]
                finally:
                    active -= 1

        now = datetime.now(UTC)
        channels = [TrackedChannel(channel_id) for channel_id in range(1, 7)]
        for channel in channels:
            channel.messages = [FakeMessage(channel.id, channel, "needle", now)]
        engine = MessageSearchEngine(MessageSearchConfig(concurrency=2))

        first, second = await asyncio.gather(
            engine.search(channels[:3], "needle"),
            engine.search(channels[3:], "needle"),
        )

        self.assertEqual(peak, 2)
        self.assertEqual(len(first.results), 3)
        self.assertEqual(len(second.results), 3)
        self.assertTrue(all(channel.history_limits == [None] for channel in channels))


class MessageSearchPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.requester = SimpleNamespace(id=1)
        self.bot_member = SimpleNamespace(id=2)

    def channel(self, requester_permissions, bot_permissions):
        channel = MagicMock()
        channel.permissions_for.side_effect = lambda member: (
            requester_permissions if member is self.requester else bot_permissions
        )
        return channel

    async def test_requires_history_and_view_permissions_for_both_members(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        cannot_read_history = SimpleNamespace(
            view_channel=True,
            read_message_history=False,
            manage_threads=False,
        )

        self.assertTrue(
            await MessageSearchCog._channel_is_searchable(
                self.channel(allowed, allowed),
                self.requester,
                self.bot_member,
            )
        )
        self.assertFalse(
            await MessageSearchCog._channel_is_searchable(
                self.channel(cannot_read_history, allowed),
                self.requester,
                self.bot_member,
            )
        )
        self.assertFalse(
            await MessageSearchCog._channel_is_searchable(
                self.channel(allowed, cannot_read_history),
                self.requester,
                self.bot_member,
            )
        )

    async def test_private_threads_require_current_membership(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        thread = MagicMock(spec=discord.Thread)
        thread.permissions_for.return_value = allowed
        thread.is_private.return_value = True
        response = SimpleNamespace(status=404, reason="Not Found")
        thread.fetch_member = AsyncMock(
            side_effect=discord.NotFound(response, "missing")
        )
        self.assertFalse(
            await MessageSearchCog._channel_is_searchable(
                thread,
                self.requester,
                self.bot_member,
            )
        )

        thread.fetch_member = AsyncMock(return_value=SimpleNamespace(id=self.requester.id))
        self.assertTrue(
            await MessageSearchCog._channel_is_searchable(
                thread,
                self.requester,
                self.bot_member,
            )
        )

    async def test_private_thread_api_failure_is_reported_not_silently_omitted(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        thread = MagicMock(spec=discord.Thread)
        thread.id = 20
        thread.permissions_for.return_value = allowed
        thread.is_private.return_value = True
        response = SimpleNamespace(status=403, reason="Forbidden")
        thread.fetch_member = AsyncMock(
            side_effect=discord.Forbidden(response, "denied")
        )
        guild = SimpleNamespace(
            channels=[],
            threads=[],
            active_threads=AsyncMock(return_value=[thread]),
        )
        cog = MessageSearchCog(MagicMock())

        channels, failures = await cog._candidate_channels(
            guild,
            self.requester,
            self.bot_member,
            selected_channel=None,
            current_channel=thread,
        )

        self.assertEqual(channels, [])
        self.assertEqual(failures, 1)

    async def test_candidates_include_active_and_archived_public_threads(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )

        def readable(spec, channel_id):
            channel = MagicMock(spec=spec)
            channel.id = channel_id
            channel.permissions_for.return_value = allowed
            return channel

        text_channel = readable(discord.TextChannel, 10)
        forum_channel = readable(discord.ForumChannel, 11)
        active_thread = readable(discord.Thread, 20)
        active_thread.is_private.return_value = False
        archived_thread = readable(discord.Thread, 30)
        archived_thread.is_private.return_value = False
        private_thread = readable(discord.Thread, 40)
        private_thread.is_private.return_value = True
        private_thread.fetch_member = AsyncMock(
            return_value=SimpleNamespace(id=self.requester.id)
        )
        forum_thread = readable(discord.Thread, 50)
        forum_thread.is_private.return_value = False

        async def archived_threads(*, private=False, joined=False, limit=100):
            self.assertIsNone(limit)
            if private:
                self.assertTrue(joined)
                yield private_thread
            else:
                yield archived_thread

        async def forum_archived_threads(*, limit=100):
            self.assertIsNone(limit)
            yield forum_thread

        text_channel.archived_threads = archived_threads
        forum_channel.archived_threads = forum_archived_threads
        guild = SimpleNamespace(
            channels=[text_channel, forum_channel],
            threads=[],
            active_threads=AsyncMock(return_value=[active_thread]),
        )
        cog = MessageSearchCog(MagicMock())

        channels, failures = await cog._candidate_channels(
            guild,
            self.requester,
            self.bot_member,
            selected_channel=None,
            current_channel=text_channel,
        )

        self.assertEqual(
            [channel.id for channel in channels],
            [10, 20, 30, 40, 50],
        )
        self.assertEqual(failures, 0)

    async def test_candidate_channels_have_no_count_cap(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        channels = []
        for channel_id in range(1, 102):
            channel = MagicMock(spec=discord.VoiceChannel)
            channel.id = channel_id
            channel.permissions_for.return_value = allowed
            channels.append(channel)
        guild = SimpleNamespace(
            channels=channels,
            threads=[],
            active_threads=AsyncMock(return_value=[]),
        )
        cog = MessageSearchCog(MagicMock())

        candidates, failures = await cog._candidate_channels(
            guild,
            self.requester,
            self.bot_member,
            selected_channel=None,
            current_channel=channels[0],
        )

        self.assertEqual(len(candidates), 101)
        self.assertEqual(failures, 0)

    async def test_results_are_removed_if_access_is_revoked_during_search(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        denied = SimpleNamespace(
            view_channel=False,
            read_message_history=False,
            manage_threads=False,
        )
        readable_channel = SimpleNamespace(
            id=10,
            permissions_for=lambda member: allowed,
        )
        revoked_channel = SimpleNamespace(
            id=20,
            permissions_for=lambda member: (
                denied if member is self.requester else allowed
            ),
        )
        now = datetime.now(UTC)
        report = MessageSearchReport(
            results=(
                MessageSearchResult(
                    1,
                    10,
                    "readable",
                    "author",
                    "needle",
                    now,
                    "https://discord.com/channels/1/10/1",
                ),
                MessageSearchResult(
                    2,
                    20,
                    "revoked",
                    "author",
                    "needle",
                    now,
                    "https://discord.com/channels/1/20/2",
                ),
            ),
            searched_channels=2,
            scanned_messages=2,
            total_channels=2,
            content_messages=2,
        )

        filtered = await MessageSearchCog._filter_report_permissions(
            report,
            [readable_channel, revoked_channel],
            self.requester,
            self.bot_member,
        )

        self.assertEqual([result.message_id for result in filtered.results], [1])
        self.assertEqual(filtered.searched_channels, 1)
        self.assertEqual(filtered.failed_channels, 1)

    async def test_current_membership_is_required_before_cached_results_are_shown(self) -> None:
        now = datetime.now(UTC)
        report = MessageSearchReport(
            results=(
                MessageSearchResult(
                    1,
                    10,
                    "former-channel",
                    "author",
                    "needle",
                    now,
                    "https://discord.com/channels/1/10/1",
                ),
            ),
            searched_channels=1,
            scanned_messages=1,
            total_channels=1,
            content_messages=1,
        )
        response = SimpleNamespace(status=404, reason="Not Found")
        guild = SimpleNamespace(
            fetch_member=AsyncMock(
                side_effect=discord.NotFound(response, "member left")
            )
        )

        filtered = await MessageSearchCog._filter_report_current_permissions(
            report,
            [SimpleNamespace(id=10)],
            guild,
            requester_id=1,
            bot_member_id=2,
        )

        self.assertEqual(filtered.results, ())
        self.assertEqual(filtered.searched_channels, 0)
        self.assertEqual(filtered.failed_channels, 1)


class MessageSearchViewTests(unittest.IsolatedAsyncioTestCase):
    def result(self, message_id: int) -> MessageSearchResult:
        return MessageSearchResult(
            message_id=message_id,
            channel_id=20,
            channel_name="general",
            author_name="tester",
            content=f"result {message_id}",
            created_at=datetime.now(UTC),
            jump_url=f"https://discord.com/channels/1/20/{message_id}",
        )

    async def test_navigation_updates_button_state_and_jump_url(self) -> None:
        report = MessageSearchReport(
            results=(self.result(1), self.result(2)),
            searched_channels=2,
            scanned_messages=10,
            total_channels=2,
        )
        view = MessageSearchView(100, "result", report)

        self.assertTrue(view.previous.disabled)
        self.assertFalse(view.next.disabled)
        self.assertTrue(view.jump_button.url.endswith("/1"))
        self.assertEqual(
            [item.label for item in view.children],
            ["이전", "메시지로 이동", "다음"],
        )

        view.index = 1
        view._sync_buttons()

        self.assertFalse(view.previous.disabled)
        self.assertTrue(view.next.disabled)
        self.assertTrue(view.jump_button.url.endswith("/2"))

    async def test_rejects_a_different_requester_privately(self) -> None:
        report = MessageSearchReport(
            results=(self.result(1),),
            searched_channels=1,
            scanned_messages=1,
            total_channels=1,
        )
        view = MessageSearchView(100, "result", report)
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=200),
            response=SimpleNamespace(send_message=AsyncMock()),
        )

        allowed = await view.interaction_check(interaction)

        self.assertFalse(allowed)
        interaction.response.send_message.assert_awaited_once_with(
            "이 검색 결과는 명령을 실행한 사람만 조작할 수 있습니다.",
            ephemeral=True,
        )

    async def test_navigation_rechecks_permissions_before_revealing_a_page(self) -> None:
        initial = MessageSearchReport(
            results=(self.result(1), self.result(2)),
            searched_channels=1,
            scanned_messages=2,
            total_channels=1,
        )
        filtered = MessageSearchReport(
            results=(self.result(2),),
            searched_channels=1,
            scanned_messages=2,
            total_channels=1,
        )
        permission_filter = AsyncMock(return_value=filtered)
        view = MessageSearchView(
            100,
            "result",
            initial,
            permission_filter=permission_filter,
        )
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        await view.next.callback(interaction)

        permission_filter.assert_awaited_once_with(initial)
        interaction.response.defer.assert_awaited_once_with()
        _, kwargs = interaction.edit_original_response.await_args
        self.assertIn("result 2", kwargs["embed"].description or "")
        self.assertEqual(view.report, filtered)

    async def test_embed_stays_within_discord_limits_and_escapes_markdown(self) -> None:
        result = MessageSearchResult(
            message_id=1,
            channel_id=20,
            channel_name="general",
            author_name="**author**" * 200,
            content="[masked](https://example.com) " + "x" * 5_000,
            created_at=datetime.now(UTC),
            jump_url="https://discord.com/channels/1/20/1",
            attachment_count=3,
        )
        report = MessageSearchReport(
            results=(result,),
            searched_channels=100,
            scanned_messages=100_000,
            failed_channels=10,
            total_channels=110,
            content_messages=99_000,
        )

        embed = MessageSearchView(100, "**needle**", report).embed()

        self.assertLessEqual(len(embed), 6_000)
        self.assertLessEqual(len(embed.description or ""), 4_096)
        self.assertTrue(all(len(field.value) <= 1_024 for field in embed.fields))
        self.assertIn(r"\[masked]", embed.description or "")
        self.assertIn(r"\*\*needle\*\*", embed.title or "")


class MessageSearchCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_command_defers_and_sends_results_ephemerally(self) -> None:
        bot = MagicMock()
        bot.user = SimpleNamespace(id=9)
        cog = MessageSearchCog(bot)
        result = MessageSearchResult(
            message_id=1,
            channel_id=20,
            channel_name="general",
            author_name="tester",
            content="needle",
            created_at=datetime.now(UTC),
            jump_url="https://discord.com/channels/1/20/1",
        )
        report = MessageSearchReport(
            results=(result,),
            searched_channels=1,
            scanned_messages=5,
            total_channels=1,
            content_messages=5,
        )
        cog.engine.search = AsyncMock(return_value=report)
        cog._filter_report_current_permissions = AsyncMock(return_value=report)
        cog._candidate_channels = AsyncMock(return_value=([FakeChannel(20)], 0))
        requester = SimpleNamespace(id=100)
        bot_member = SimpleNamespace(id=9)
        guild = SimpleNamespace(
            id=1,
            me=bot_member,
            get_member=lambda member_id: requester if member_id == 100 else bot_member,
        )
        interaction = SimpleNamespace(
            user=requester,
            guild=guild,
            channel=SimpleNamespace(id=20),
            response=SimpleNamespace(
                defer=AsyncMock(),
                send_message=AsyncMock(),
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        await MessageSearchCog.search.callback(cog, interaction, "needle", None)

        interaction.response.defer.assert_awaited_once_with(
            ephemeral=True,
            thinking=True,
        )
        _, kwargs = interaction.followup.send.await_args
        self.assertTrue(kwargs["ephemeral"])
        self.assertTrue(kwargs["wait"])
        self.assertIsInstance(kwargs["allowed_mentions"], discord.AllowedMentions)
        self.assertIsInstance(kwargs["view"], MessageSearchView)
        self.assertIsNone(cog.engine.search.await_args.kwargs["after"])
        self.assertEqual(
            cog.engine.search.await_args.kwargs["scope_label"],
            "전체 기간",
        )
        self.assertEqual(cog._active_requesters, set())

    async def test_expired_private_response_falls_back_to_requester_dm(self) -> None:
        report = MessageSearchReport(
            results=(
                MessageSearchResult(
                    message_id=1,
                    channel_id=20,
                    channel_name="general",
                    author_name="tester",
                    content="needle",
                    created_at=datetime.now(UTC),
                    jump_url="https://discord.com/channels/1/20/1",
                ),
            ),
            searched_channels=1,
            scanned_messages=1,
            total_channels=1,
            content_messages=1,
        )
        view = MessageSearchView(100, "needle", report)
        response = SimpleNamespace(status=404, reason="Not Found")
        interaction = SimpleNamespace(
            followup=SimpleNamespace(
                send=AsyncMock(
                    side_effect=discord.NotFound(response, "expired")
                )
            )
        )
        delivered_message = MagicMock(spec=discord.Message)
        requester = MagicMock(spec=discord.Member)
        requester.id = 100
        requester.send = AsyncMock(return_value=delivered_message)

        await MessageSearchCog._deliver_results(interaction, requester, view)

        requester.send.assert_awaited_once()
        _, kwargs = requester.send.await_args
        self.assertIs(kwargs["view"], view)
        self.assertIsInstance(kwargs["allowed_mentions"], discord.AllowedMentions)
        self.assertIs(view.message, delivered_message)

    async def test_uses_interaction_member_when_member_cache_misses(self) -> None:
        bot = MagicMock()
        bot.user = SimpleNamespace(id=9)
        cog = MessageSearchCog(bot)
        cog.engine.search = AsyncMock(
            return_value=MessageSearchReport(
                results=(),
                searched_channels=1,
                scanned_messages=0,
                total_channels=1,
            )
        )
        cog._candidate_channels = AsyncMock(return_value=([FakeChannel(20)], 0))
        requester = MagicMock(spec=discord.Member)
        requester.id = 100
        bot_member = SimpleNamespace(id=9)
        guild = SimpleNamespace(
            id=1,
            me=bot_member,
            get_member=MagicMock(return_value=None),
        )
        interaction = SimpleNamespace(
            user=requester,
            guild=guild,
            channel=SimpleNamespace(id=20),
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        await MessageSearchCog.search.callback(cog, interaction, "needle", None)

        interaction.response.defer.assert_awaited_once()
        passed_requester = cog._candidate_channels.call_args.args[1]
        self.assertIs(passed_requester, requester)
        guild.get_member.assert_not_called()


class MessageSearchCommandDefinitionTests(unittest.TestCase):
    def test_command_payload_has_expected_scope_and_option_limits(self) -> None:
        client = discord.Client(intents=discord.Intents.none())
        tree = discord.app_commands.CommandTree(client)

        payload = MessageSearchCog.search.to_dict(tree)
        options = {option["name"]: option for option in payload["options"]}

        self.assertFalse(payload["dm_permission"])
        self.assertEqual(options["키워드"]["min_length"], 2)
        self.assertEqual(options["키워드"]["max_length"], 100)
        self.assertEqual(
            options["채널"]["channel_types"],
            [discord.ChannelType.text.value, discord.ChannelType.news.value],
        )
        self.assertFalse(options["기간"]["required"])
        self.assertEqual(
            [(choice["name"], choice["value"]) for choice in options["기간"]["choices"]],
            [
                ("최근 24시간", 1),
                ("최근 7일", 7),
                ("최근 30일", 30),
                ("최근 90일", 90),
                ("최근 1년", 365),
                ("전체 기간", 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
