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

    async def history(self, *, limit: int, oldest_first: bool):
        assert oldest_first is False
        for message in self.messages[:limit]:
            yield message


class MessageSearchConfigTests(unittest.TestCase):
    def test_environment_values_are_bounded_and_invalid_values_fall_back(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KALING_MESSAGE_SEARCH_HISTORY_PER_CHANNEL": "999999",
                "KALING_MESSAGE_SEARCH_MAX_RESULTS": "invalid",
                "KALING_MESSAGE_SEARCH_CONCURRENCY": "0",
                "KALING_MESSAGE_SEARCH_TIMEOUT_SECONDS": "120",
            },
            clear=False,
        ):
            config = MessageSearchConfig.from_env()

        self.assertEqual(config.history_per_channel, 10_000)
        self.assertEqual(config.max_results, 100)
        self.assertEqual(config.concurrency, 1)
        self.assertEqual(config.timeout_seconds, 60)


class MessageSearchEngineTests(unittest.IsolatedAsyncioTestCase):
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
            MessageSearchConfig(
                history_per_channel=50,
                max_results=10,
                max_channels=10,
                concurrency=2,
                timeout_seconds=5,
            )
        )

        report = await engine.search([first, second], "needle")

        self.assertEqual([result.message_id for result in report.results], [3, 1])
        self.assertEqual(report.searched_channels, 2)
        self.assertEqual(report.scanned_messages, 3)
        self.assertFalse(report.timed_out)

    async def test_timeout_returns_completed_channel_results(self) -> None:
        class SlowChannel(FakeChannel):
            async def history(self, *, limit: int, oldest_first: bool):
                del limit, oldest_first
                await asyncio.sleep(0.05)
                if False:
                    yield None

        now = datetime.now(UTC)
        fast = FakeChannel(10)
        fast.messages = [FakeMessage(1, fast, "needle", now)]
        engine = MessageSearchEngine(
            MessageSearchConfig(
                history_per_channel=50,
                max_results=10,
                max_channels=10,
                concurrency=2,
                timeout_seconds=0.01,
            )
        )

        report = await engine.search([fast, SlowChannel(20)], "needle")

        self.assertEqual([result.message_id for result in report.results], [1])
        self.assertEqual(report.searched_channels, 1)
        self.assertTrue(report.timed_out)

    async def test_global_result_limit_is_reported(self) -> None:
        now = datetime.now(UTC)
        channel = FakeChannel(10)
        channel.messages = [
            FakeMessage(index, channel, "needle", now - timedelta(seconds=index))
            for index in range(1, 4)
        ]
        engine = MessageSearchEngine(
            MessageSearchConfig(
                history_per_channel=50,
                max_results=2,
                max_channels=10,
                concurrency=1,
                timeout_seconds=5,
            )
        )

        report = await engine.search([channel], "needle")

        self.assertEqual(len(report.results), 2)
        self.assertTrue(report.results_truncated)

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
        engine = MessageSearchEngine(
            MessageSearchConfig(
                history_per_channel=50,
                max_results=10,
                max_channels=10,
                concurrency=2,
                timeout_seconds=5,
            )
        )

        report = await engine.search(
            [ForbiddenChannel(20), readable],
            "needle",
        )

        self.assertEqual([result.message_id for result in report.results], [1])
        self.assertEqual(report.searched_channels, 1)
        self.assertEqual(report.failed_channels, 1)


class MessageSearchPermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requester = SimpleNamespace(id=1)
        self.bot_member = SimpleNamespace(id=2)

    def channel(self, requester_permissions, bot_permissions):
        channel = MagicMock()
        channel.permissions_for.side_effect = lambda member: (
            requester_permissions if member is self.requester else bot_permissions
        )
        return channel

    def test_requires_history_and_view_permissions_for_both_members(self) -> None:
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
            MessageSearchCog._channel_is_searchable(
                self.channel(allowed, allowed),
                self.requester,
                self.bot_member,
            )
        )
        self.assertFalse(
            MessageSearchCog._channel_is_searchable(
                self.channel(cannot_read_history, allowed),
                self.requester,
                self.bot_member,
            )
        )
        self.assertFalse(
            MessageSearchCog._channel_is_searchable(
                self.channel(allowed, cannot_read_history),
                self.requester,
                self.bot_member,
            )
        )

    def test_private_threads_are_excluded(self) -> None:
        allowed = SimpleNamespace(
            view_channel=True,
            read_message_history=True,
            manage_threads=False,
        )
        thread = MagicMock(spec=discord.Thread)
        thread.permissions_for.return_value = allowed
        thread.is_private.return_value = True
        self.assertFalse(
            MessageSearchCog._channel_is_searchable(
                thread,
                self.requester,
                self.bot_member,
            )
        )

        thread.members = [self.requester, self.bot_member]
        thread.owner_id = self.requester.id
        self.assertFalse(
            MessageSearchCog._channel_is_searchable(
                thread,
                self.requester,
                self.bot_member,
            )
        )


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
            history_per_channel=1_000,
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
            history_per_channel=1_000,
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
            history_per_channel=1_000,
            omitted_channels=400,
            failed_channels=10,
            timed_out_channels=20,
            timed_out=True,
            results_truncated=True,
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
        cog.engine.search = AsyncMock(
            return_value=MessageSearchReport(
                results=(result,),
                searched_channels=1,
                scanned_messages=5,
                history_per_channel=1_000,
            )
        )
        cog._candidate_channels = MagicMock(return_value=([FakeChannel(20)], 0))
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
        self.assertEqual(cog._active_requesters, set())

    async def test_uses_interaction_member_when_member_cache_misses(self) -> None:
        bot = MagicMock()
        bot.user = SimpleNamespace(id=9)
        cog = MessageSearchCog(bot)
        cog.engine.search = AsyncMock(
            return_value=MessageSearchReport(
                results=(),
                searched_channels=1,
                scanned_messages=0,
                history_per_channel=1_000,
            )
        )
        cog._candidate_channels = MagicMock(return_value=([FakeChannel(20)], 0))
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
        self.assertEqual(options["키워드"]["min_length"], 1)
        self.assertEqual(options["키워드"]["max_length"], 100)
        self.assertEqual(
            options["채널"]["channel_types"],
            [discord.ChannelType.text.value, discord.ChannelType.news.value],
        )


if __name__ == "__main__":
    unittest.main()
