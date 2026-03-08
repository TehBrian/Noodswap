import io
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from pathlib import Path

import discord
from discord.ext import commands

from noodswap import storage
from noodswap.commands import (
    SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS,
    SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS,
    _animate_slots_spin,
    _build_drop_preview_blocking,
    _get_card_image_bytes,
    _slots_reel_content,
    register_commands,
)
from noodswap.images import DEFAULT_CARD_RENDER_SIZE, HD_CARD_RENDER_SIZE, RARITY_BORDER_COLORS, render_card_image_bytes
from noodswap.views import HelpView, PlayerLeaderboardView, SortableCardListView, SortableCollectionView


_TEST_DB_TMP: tempfile.TemporaryDirectory[str] | None = None
_ORIGINAL_DB_PATH: Path | None = None


def setUpModule() -> None:
    global _TEST_DB_TMP, _ORIGINAL_DB_PATH
    _TEST_DB_TMP = tempfile.TemporaryDirectory()
    _ORIGINAL_DB_PATH = storage.DB_PATH
    storage.DB_PATH = Path(_TEST_DB_TMP.name) / "test_commands.db"
    storage.init_db()


def tearDownModule() -> None:
    global _TEST_DB_TMP, _ORIGINAL_DB_PATH
    if _ORIGINAL_DB_PATH is not None:
        storage.DB_PATH = _ORIGINAL_DB_PATH
    if _TEST_DB_TMP is not None:
        _TEST_DB_TMP.cleanup()
    _TEST_DB_TMP = None
    _ORIGINAL_DB_PATH = None


class _FakeGuild:
    def __init__(self, guild_id: int, members: dict[int, Any] | None = None):
        self.id = guild_id
        self._members = members or {}

    def get_member(self, user_id: int) -> Any | None:
        return self._members.get(user_id)


class _FakeMember:
    def __init__(self, user_id: int, display_name: str = "User"):
        self.id = user_id
        self.display_name = display_name
        self.bot = False


def _get_command(bot: commands.Bot, name: str) -> Any:
    command = bot.get_command(name)
    assert command is not None
    return command


def _get_group_command(bot: commands.Bot, group_name: str, command_name: str) -> Any:
    group = _get_command(bot, group_name)
    command = group.get_command(command_name)
    assert command is not None
    return command


class CommandsWishlistTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_wish_list_defaults_to_author_when_player_omitted(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl:
            await wish_list_command.callback(ctx, player=None)

        wish_list_impl.assert_awaited_once_with(ctx, ctx.author)

    async def test_wish_list_uses_resolved_player_when_argument_provided(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        wish_list_impl.assert_awaited_once_with(ctx, target)

    async def test_wish_list_uses_replied_player_when_argument_omitted(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        target = _FakeMember(200, "Target")
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1, members={200: target})
        ctx.author = _FakeMember(100, "Caller")
        ctx.message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=SimpleNamespace(author=SimpleNamespace(id=200)),
                message_id=123,
            )
        )
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl:
            await wish_list_command.callback(ctx, player=None)

        wish_list_impl.assert_awaited_once_with(ctx, target)

    async def test_wish_add_falls_back_to_exact_card_name(self) -> None:
        wish_add_command = _get_group_command(self.bot, "wish", "add")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.search_card_ids_by_name", return_value=["SPG"]),
            patch("noodswap.commands.add_card_to_wishlist", return_value=True) as add_wishlist,
        ):
            await wish_add_command.callback(ctx, card_id="spaghetti")

        add_wishlist.assert_called_once_with(1, 100, "SPG")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist")
        self.assertIn("Added to wishlist", sent_embed.description)
        self.assertIn("(`SPG`)", sent_embed.description)

    async def test_wish_add_lists_multiple_name_matches_with_numbering(self) -> None:
        wish_add_command = _get_group_command(self.bot, "wish", "add")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.add_card_to_wishlist", return_value=True) as add_wishlist:
            await wish_add_command.callback(ctx, card_id="cheddar")

        add_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist Matches")
        self.assertIn("1. (`CHD`) [🧀] **Cheddar**", sent_embed.description)
        self.assertIn("2. (`CHJ`) [🧀] **Cheddar Jack**", sent_embed.description)


class CommandsTagTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_tag_list_shows_empty_state(self) -> None:
        tag_list_command = _get_group_command(self.bot, "tag", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.list_player_tags", return_value=[]):
            await tag_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Your Tags")
        self.assertIn("No tags yet", sent_embed.description)

    async def test_tag_list_shows_lock_markers_for_locked_and_unlocked_tags(self) -> None:
        tag_list_command = _get_group_command(self.bot, "tag", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands.list_player_tags",
            return_value=[("safe", True, 2), ("trash", False, 1)],
        ):
            await tag_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Your Tags")
        self.assertIn("🔒 `safe` - Locked - 2 card(s)", sent_embed.description)
        self.assertIn("`  ` `trash` - Unlocked - 1 card(s)", sent_embed.description)

    async def test_tag_assign_rejects_unowned_card_code(self) -> None:
        tag_assign_command = _get_group_command(self.bot, "tag", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.get_instance_by_code", return_value=None):
            await tag_assign_command.callback(ctx, tag_name="safe", card_code="0")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Tags")
        self.assertEqual(sent_embed.description, "You do not own that card code.")

    async def test_tag_assign_rejects_duplicate_assignment_explicitly(self) -> None:
        tag_assign_command = _get_group_command(self.bot, "tag", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        selected = (5, "SPG", 1200, "0")
        with (
            patch("noodswap.commands.get_instance_by_code", return_value=selected),
            patch("noodswap.commands.is_tag_assigned_to_instance", return_value=True),
            patch("noodswap.commands.assign_tag_to_instance", return_value=False) as assign_tag,
        ):
            await tag_assign_command.callback(ctx, tag_name="safe", card_code="0")

        assign_tag.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Tags")
        self.assertEqual(sent_embed.description, "You have already assigned that card that tag.")

    async def test_tag_cards_shows_sortable_collection_view(self) -> None:
        tag_cards_command = _get_group_command(self.bot, "tag", "cards")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        tagged_instances = [
            (1, "SPG", 1200, "0"),
            (2, "BAR", 900, "1"),
        ]
        with (
            patch("noodswap.commands.get_instances_by_tag", return_value=tagged_instances),
            patch("noodswap.commands.get_locked_instance_ids", return_value=set()),
            patch("noodswap.commands.get_card_wish_counts", return_value={"SPG": 1, "BAR": 2}),
            patch("noodswap.commands.get_instance_morph", return_value=None),
            patch("noodswap.commands.get_instance_frame", return_value=None),
            patch("noodswap.commands.get_instance_font", return_value=None),
        ):
            await tag_cards_command.callback(ctx, tag_name="safe")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Tag: `safe`")
        self.assertIsInstance(sent_view, SortableCollectionView)
        self.assertIs(sent_view.message, ctx.send.return_value)

    async def test_wish_remove_lists_multiple_name_matches(self) -> None:
        wish_remove_command = _get_group_command(self.bot, "wish", "remove")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.remove_card_from_wishlist", return_value=True) as remove_wishlist:
            await wish_remove_command.callback(ctx, card_id="cheddar")

        remove_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist Matches")
        self.assertIn("1. (`CHD`) [🧀] **Cheddar**", sent_embed.description)
        self.assertIn("2. (`CHJ`) [🧀] **Cheddar Jack**", sent_embed.description)


class CommandsAliasRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    def test_requested_aliases_exist(self) -> None:
        self.assertIsNotNone(_get_command(self.bot, "wa"))
        self.assertIsNotNone(_get_command(self.bot, "wr"))
        self.assertIsNotNone(_get_command(self.bot, "wl"))

        self.assertIn("m", _get_command(self.bot, "marry").aliases)
        self.assertIn("dv", _get_command(self.bot, "divorce").aliases)
        self.assertIn("t", _get_command(self.bot, "trade").aliases)
        self.assertIn("b", _get_command(self.bot, "burn").aliases)
        self.assertIn("mo", _get_command(self.bot, "morph").aliases)
        self.assertIn("fr", _get_command(self.bot, "frame").aliases)
        self.assertIn("fo", _get_command(self.bot, "font").aliases)
        cooldown_command = _get_command(self.bot, "cooldown")
        self.assertIn("cd", cooldown_command.aliases)
        self.assertIn("d", _get_command(self.bot, "drop").aliases)
        self.assertIn("h", _get_command(self.bot, "help").aliases)
        self.assertIn("ca", _get_command(self.bot, "cards").aliases)
        self.assertIn("l", _get_command(self.bot, "lookup").aliases)
        self.assertIn("lhd", _get_command(self.bot, "lookuphd").aliases)
        self.assertIn("c", _get_command(self.bot, "collection").aliases)
        self.assertIn("le", _get_command(self.bot, "leaderboard").aliases)
        self.assertIn("i", _get_command(self.bot, "info").aliases)
        self.assertIn("v", _get_command(self.bot, "vote").aliases)
        self.assertIn("s", _get_command(self.bot, "slots").aliases)
        self.assertIn("tg", _get_command(self.bot, "tag").aliases)


class CommandsLeaderboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_leaderboard_command_sends_player_leaderboard_view(self) -> None:
        leaderboard_command = _get_command(self.bot, "leaderboard")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        leaderboard_rows = [
            (100, 2, 1, 20, 0, 40),
            (200, 5, 3, 50, 2, 120),
        ]
        with patch("noodswap.commands.get_player_leaderboard_info", return_value=leaderboard_rows):
            await leaderboard_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Leaderboard")
        self.assertIsInstance(sent_view, PlayerLeaderboardView)
        self.assertIs(sent_view.message, ctx.send.return_value)


class CommandsHelpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_help_command_sends_overview_with_help_view(self) -> None:
        help_command = _get_command(self.bot, "help")

        ctx = AsyncMock()
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        await help_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Help")
        self.assertIn("Noodswap", sent_embed.description)
        self.assertIsInstance(sent_view, HelpView)
        self.assertIs(sent_view.message, ctx.send.return_value)


class CommandsLookupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_lookup_rejects_unknown_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_id="zzz")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Lookup")
        self.assertEqual(sent_embed.description, "No results found.")

    async def test_lookup_shows_usage_when_missing_argument(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_id=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Lookup")
        self.assertEqual(sent_embed.description, "Usage: `ns lookup <card_id|card_code|query>`.")

    async def test_lookup_shows_base_card_embed(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_id="spg")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)

    async def test_lookup_shows_dupe_card_embed_for_exact_code(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands.get_instance_by_dupe_code",
            return_value=(123, "SPG", 101, "abc"),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_id="AbC")

        lookup_dupe.assert_called_once_with(1, "AbC")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("`#abc`", sent_embed.description)
        self.assertIn("G-101", sent_embed.description)
        self.assertIn("dough", sent_embed.description)

    async def test_lookup_shows_dupe_card_embed_for_hash_prefixed_code(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands.get_instance_by_dupe_code",
            return_value=(123, "SPG", 101, "abc"),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_id="#AbC")

        lookup_dupe.assert_called_once_with(1, "#AbC")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("`#abc`", sent_embed.description)
        self.assertIn("G-101", sent_embed.description)
        self.assertIn("dough", sent_embed.description)

    async def test_lookup_prefers_exact_dupe_code_over_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands.get_instance_by_dupe_code",
            return_value=(777, "SPG", 88, "spg"),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_id="spg")

        lookup_dupe.assert_called_once_with(1, "spg")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("`#spg`", sent_embed.description)
        self.assertIn("dough", sent_embed.description)
        self.assertNotIn("Base:", sent_embed.description)

    async def test_lookup_falls_back_to_exact_card_name(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.search_card_ids", return_value=["SPG"]):
            await lookup_command.callback(ctx, card_id="spaghetti")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)

    async def test_lookup_lists_multiple_name_matches(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_id="cheddar")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Lookup Matches")
        self.assertIsInstance(sent_view, SortableCardListView)
        self.assertIn("Cheddar", sent_embed.description)
        self.assertIn("Cheddar Jack", sent_embed.description)
        self.assertIn("Sort: Alphabetical", sent_embed.footer.text)

    async def test_lookup_lists_matches_for_series_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_id="cheese")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Lookup Matches")
        self.assertIsInstance(sent_view, SortableCardListView)
        self.assertIn("1.", sent_embed.description)
        self.assertTrue(sent_embed.footer.text.startswith("Page 1/"))
        self.assertIn("Sort: Alphabetical", sent_embed.footer.text)
        self.assertGreater(sent_view.total_pages, 1)

    async def test_lookup_unknown_card_id_falls_back_to_search_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.search_card_ids", return_value=["SPG"]) as search_cards:
            await lookup_command.callback(ctx, card_id="spicy noodle")

        search_cards.assert_called_once_with("spicy noodle", include_series=True)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)

    async def test_lookuphd_requests_hd_render_size(self) -> None:
        lookup_command = _get_command(self.bot, "lookuphd")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands.embed_image_payload",
            return_value=("attachment://spg_card.png", None),
        ) as embed_payload:
            await lookup_command.callback(ctx, card_id="spg")

        embed_payload.assert_called_once()
        self.assertEqual(embed_payload.call_args.kwargs["size"], HD_CARD_RENDER_SIZE)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup (HD)")


class CommandsCollectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_collection_defaults_to_author_when_player_omitted(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.get_player_card_instances", return_value=[]):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Caller's Collection")
        self.assertEqual(sent_embed.description, "Your collection is empty. Try `ns drop`.")

    async def test_collection_uses_resolved_player_when_argument_provided(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands.get_player_card_instances", return_value=[]),
        ):
            await collection_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Collection")
        self.assertEqual(sent_embed.description, "Target has an empty collection.")

    async def test_collection_uses_replied_player_when_argument_omitted(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        target = _FakeMember(200, "Target")
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1, members={200: target})
        ctx.author = _FakeMember(100, "Caller")
        ctx.message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=SimpleNamespace(author=SimpleNamespace(id=200)),
                message_id=123,
            )
        )
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands.get_player_card_instances", return_value=[]):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Collection")
        self.assertEqual(sent_embed.description, "Target has an empty collection.")

    async def test_collection_sends_error_when_player_resolution_fails(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "noodswap.commands.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("noodswap.commands.get_player_card_instances", return_value=[]),
        ):
            await collection_command.callback(ctx, player="ghost")

        resolve_member.assert_awaited_once_with(ctx, "ghost")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Collection")
        self.assertEqual(sent_embed.description, "Could not find that player.")

    async def test_collection_lists_each_instance_separately(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        instances = [
            (3, "SPG", 100, "0"),
            (4, "SPG", 100, "1"),
            (5, "SPG", 90, "2"),
        ]
        with (
            patch("noodswap.commands.get_player_card_instances", return_value=instances),
            patch("noodswap.commands.get_locked_instance_ids", return_value=set()),
        ):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Caller's Collection")
        self.assertEqual(sent_embed.description.count("Spaghetti"), 3)
        self.assertNotIn("×", sent_embed.description)
        self.assertIn("#", sent_embed.description)

    async def test_collection_uses_pagination_view_for_multi_page_results(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        instances = [(idx, "SPG", 100 + idx, str(idx)) for idx in range(1, 13)]
        with (
            patch("noodswap.commands.get_player_card_instances", return_value=instances),
            patch("noodswap.commands.get_locked_instance_ids", return_value=set()),
        ):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], SortableCollectionView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2 • Sort: Alphabetical")

    async def test_wish_list_uses_pagination_view_for_multi_page_results(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        wishlisted_ids = ["SPG", "PEN", "FUS", "CHD", "CHJ", "BGL", "BAG", "BOL", "PIT", "RYE", "SOU"]
        with patch("noodswap.commands.get_wishlist_cards", return_value=wishlisted_ids):
            await wish_list_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], SortableCardListView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2 • Sort: Alphabetical")

    async def test_wish_list_sends_error_when_player_resolution_fails(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "noodswap.commands.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_command.callback(ctx, player="ghost")

        resolve_member.assert_awaited_once_with(ctx, "ghost")
        wish_list_impl.assert_not_awaited()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist")
        self.assertEqual(sent_embed.description, "Could not find that player.")

    async def test_wl_accepts_optional_player_argument(self) -> None:
        wish_list_short = _get_command(self.bot, "wl")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(222, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_short.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        wish_list_impl.assert_awaited_once_with(ctx, target)


class CommandsCooldownTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_cooldown_defaults_to_author(self) -> None:
        cooldown_command = _get_command(self.bot, "cooldown")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.get_player_cooldown_timestamps", return_value=(0.0, 0.0)),
            patch("noodswap.commands.get_player_vote_reward_timestamp", return_value=0.0),
            patch("noodswap.commands.get_player_slots_timestamp", return_value=0.0),
            patch("noodswap.commands.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Caller's Cooldowns")
        self.assertIn("Drop:", sent_embed.description)
        self.assertIn("Pull:", sent_embed.description)
        self.assertIn("Vote:", sent_embed.description)
        self.assertIn("Slots:", sent_embed.description)
        self.assertIn("Ready", sent_embed.description)

    async def test_cooldown_uses_resolved_player_when_argument_provided(self) -> None:
        cooldown_command = _get_command(self.bot, "cooldown")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(222, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands.get_player_cooldown_timestamps", return_value=(9_800.0, 9_850.0)),
            patch("noodswap.commands.get_player_vote_reward_timestamp", return_value=9_900.0),
            patch("noodswap.commands.get_player_slots_timestamp", return_value=9_950.0),
            patch("noodswap.commands.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Cooldowns")
        self.assertIn("Drop:", sent_embed.description)
        self.assertIn("Pull:", sent_embed.description)
        self.assertIn("Vote:", sent_embed.description)
        self.assertIn("Slots:", sent_embed.description)
        self.assertIn("Cooling Down", sent_embed.description)

    async def test_cooldown_uses_replied_player_when_argument_omitted(self) -> None:
        cooldown_command = _get_command(self.bot, "cooldown")

        target = _FakeMember(222, "Target")
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1, members={222: target})
        ctx.author = _FakeMember(100, "Caller")
        ctx.message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=SimpleNamespace(author=SimpleNamespace(id=222)),
                message_id=123,
            )
        )
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.get_player_cooldown_timestamps", return_value=(9_800.0, 9_850.0)),
            patch("noodswap.commands.get_player_vote_reward_timestamp", return_value=9_900.0),
            patch("noodswap.commands.get_player_slots_timestamp", return_value=9_950.0),
            patch("noodswap.commands.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Cooldowns")


class CommandsSlotsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_slots_enforces_cooldown(self) -> None:
        slots_command = _get_command(self.bot, "slots")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.consume_slots_cooldown_if_ready", return_value=60.0),
            patch("noodswap.commands.add_starter") as add_starter,
            patch("noodswap.commands._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_starter.assert_not_called()
        animate.assert_not_awaited()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Slots Cooldown")
        self.assertIn("remaining", sent_embed.description)

    async def test_slots_awards_starter_on_three_match(self) -> None:
        slots_command = _get_command(self.bot, "slots")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.consume_slots_cooldown_if_ready", return_value=0.0),
            patch("noodswap.commands.random.choice", return_value="🍞"),
            patch("noodswap.commands.random.randint", return_value=2),
            patch("noodswap.commands.add_starter", return_value=7) as add_starter,
            patch("noodswap.commands._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_starter.assert_called_once_with(1, 100, 2)
        animate.assert_awaited_once()
        self.assertGreaterEqual(message.edit.await_count, 1)
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertEqual(final_embed.title, "Slots")
        self.assertIn("Jackpot", final_embed.description)
        self.assertIn("+2 starter", final_embed.description)


class CommandsSlotsAnimationTests(unittest.IsolatedAsyncioTestCase):
    async def test_slots_reel_content_hides_status_emoji_until_result(self) -> None:
        symbols = ["🍞", "🍞", "🍞"]
        self.assertEqual(_slots_reel_content(symbols), "🍞🍞🍞")
        self.assertEqual(_slots_reel_content(symbols, result_emoji="🎉"), "🍞🍞🍞🎉")

    async def test_animate_slots_spin_uses_tapered_frame_delays(self) -> None:
        message = AsyncMock()

        with (
            patch("noodswap.commands.random.randint", return_value=4),
            patch("noodswap.commands.random.choice", return_value="🍞"),
            patch("noodswap.commands.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await _animate_slots_spin(message, ["🍇", "🍝", "🧀"])

        self.assertEqual(message.edit.await_count, 4)

        observed_delays = [call.args[0] for call in sleep_mock.await_args_list]
        self.assertEqual(len(observed_delays), 4)
        self.assertAlmostEqual(observed_delays[0], SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS)
        self.assertAlmostEqual(observed_delays[-1], SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS)
        self.assertTrue(all(left <= right for left, right in zip(observed_delays, observed_delays[1:])))

        intermediate_contents = [call.kwargs["content"] for call in message.edit.await_args_list]
        self.assertTrue(all("✅" not in text and "❌" not in text and "🎉" not in text for text in intermediate_contents))


class CommandsInfoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_info_includes_wishes_count_field(self) -> None:
        info_command = _get_command(self.bot, "info")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.get_player_info", return_value=(123, 0.0, None)),
            patch("noodswap.commands.get_player_starter", return_value=9),
            patch("noodswap.commands.get_total_cards", return_value=7),
            patch("noodswap.commands.get_wishlist_cards", return_value=["SPG", "PEN", "FUS"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        field_values = {field.name: field.value for field in sent_embed.fields}
        self.assertEqual(field_values.get("Cards"), "7")
        self.assertEqual(field_values.get("Dough"), "123")
        self.assertEqual(field_values.get("Starter"), "9")
        self.assertEqual(field_values.get("Wishes"), "3")

    async def test_info_uses_replied_player_when_argument_omitted(self) -> None:
        info_command = _get_command(self.bot, "info")

        target = _FakeMember(222, "Target")
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1, members={222: target})
        ctx.author = _FakeMember(100, "Caller")
        ctx.message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=SimpleNamespace(author=SimpleNamespace(id=222)),
                message_id=123,
            )
        )
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands.get_player_info", return_value=(999, 0.0, None)),
            patch("noodswap.commands.get_player_starter", return_value=2),
            patch("noodswap.commands.get_total_cards", return_value=4),
            patch("noodswap.commands.get_wishlist_cards", return_value=["SPG"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Info")


class CommandsVoteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_vote_shows_configuration_message_when_topgg_token_missing(self) -> None:
        vote_command = _get_command(self.bot, "vote")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch.dict("os.environ", {}, clear=True):
            await vote_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Vote")
        self.assertIn("Automatic vote verification is not configured", sent_embed.description)
        self.assertIn("Set `TOPGG_API_TOKEN` to enable reward claims", sent_embed.description)
        self.assertIsInstance(sent_view, discord.ui.View)

    async def test_vote_claims_starter_when_topgg_vote_detected(self) -> None:
        vote_command = _get_command(self.bot, "vote")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch.dict("os.environ", {"TOPGG_API_TOKEN": "token", "TOPGG_BOT_ID": "123"}, clear=True),
            patch("noodswap.commands._topgg_recent_vote_status", new=AsyncMock(return_value=(True, None))),
            patch("noodswap.commands.claim_vote_reward_if_ready", return_value=(True, 0.0, 5)),
        ):
            await vote_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertIn("Claimed:", sent_embed.description)
        self.assertIn("Starter Balance: **5**", sent_embed.description)


class CommandsBurnTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_burn_confirmation_embed_shows_dupe_code(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        prepared = SimpleNamespace(
            is_error=False,
            error_message=None,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            payout=42,
            value=40,
            base_value=38,
            delta=2,
            delta_range=8,
            multiplier=1.05,
        )

        with patch("noodswap.commands.prepare_burn", return_value=prepared):
            await burn_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Burn Confirmation")
        self.assertIn("`#a", sent_embed.description)
        self.assertNotIn("`#?`", sent_embed.description)


class CommandsMorphTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_morph_success_shows_confirmation_prompt(self) -> None:
        morph_command = _get_command(self.bot, "morph")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=False,
            error_message=None,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            current_morph_key=None,
            cost=9,
        )

        with patch("noodswap.commands.prepare_morph", return_value=result):
            await morph_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Morph Confirmation")
        self.assertIn("Current Morph", sent_embed.description)
        self.assertIn("Roll Result: **?**", sent_embed.description)
        self.assertIn("Roll Cost: **9** dough", sent_embed.description)
        self.assertIn("view", ctx.send.await_args.kwargs)

    async def test_morph_error_surfaces_service_message(self) -> None:
        morph_command = _get_command(self.bot, "morph")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=True,
            error_message="You do not have enough dough.",
        )

        with patch("noodswap.commands.prepare_morph", return_value=result):
            await morph_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Morph")
        self.assertEqual(sent_embed.description, "You do not have enough dough.")


class CommandsFrameTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_frame_success_shows_confirmation_prompt(self) -> None:
        frame_command = _get_command(self.bot, "frame")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=False,
            error_message=None,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            current_frame_key=None,
            cost=9,
        )

        with patch("noodswap.commands.prepare_frame", return_value=result):
            await frame_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Frame Confirmation")
        self.assertIn("Current Frame", sent_embed.description)
        self.assertIn("Roll Result: **?**", sent_embed.description)
        self.assertIn("Roll Cost: **9** dough", sent_embed.description)
        self.assertIn("view", ctx.send.await_args.kwargs)

    async def test_frame_error_surfaces_service_message(self) -> None:
        frame_command = _get_command(self.bot, "frame")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=True,
            error_message="You do not have enough dough.",
        )

        with patch("noodswap.commands.prepare_frame", return_value=result):
            await frame_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Frame")
        self.assertEqual(sent_embed.description, "You do not have enough dough.")


class CommandsFontTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_font_success_shows_confirmation_prompt(self) -> None:
        font_command = _get_command(self.bot, "font")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=False,
            error_message=None,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            current_font_key=None,
            cost=9,
        )

        with patch("noodswap.commands.prepare_font", return_value=result):
            await font_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Font Confirmation")
        self.assertIn("Current Font", sent_embed.description)
        self.assertIn("Roll Result: **?**", sent_embed.description)
        self.assertIn("Roll Cost: **9** dough", sent_embed.description)
        self.assertIn("view", ctx.send.await_args.kwargs)

    async def test_font_error_surfaces_service_message(self) -> None:
        font_command = _get_command(self.bot, "font")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        result = SimpleNamespace(
            is_error=True,
            error_message="You do not have enough dough.",
        )

        with patch("noodswap.commands.prepare_font", return_value=result):
            await font_command.callback(ctx, card_code="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Font")
        self.assertEqual(sent_embed.description, "You do not have enough dough.")


class DropPreviewRegressionTests(unittest.TestCase):
    def test_drop_preview_uses_placeholder_when_third_fetch_fails(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (32, 32), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        raw_1 = png_bytes((255, 0, 0))
        raw_2 = png_bytes((0, 255, 0))

        with patch("noodswap.images.read_local_card_image_bytes", side_effect=[raw_1, raw_2, None]):
            preview = _build_drop_preview_blocking([
                ("SPG", 1),
                ("PEN", 2),
                ("FUS", 3),
            ])

        self.assertIsNotNone(preview)
        if preview is None:
            self.fail("Expected drop preview bytes")
        composed = Image.open(io.BytesIO(preview)).convert("RGB")

        card_w, card_h = DEFAULT_CARD_RENDER_SIZE
        gap = 16
        pad = 16
        y = pad + (card_h // 2)
        x_slot_2 = pad + card_w + gap + (card_w // 2)
        x_slot_3 = pad + (card_w + gap) * 2 + (card_w // 2)

        pixel_slot_2 = composed.getpixel((x_slot_2, y))
        pixel_slot_3 = composed.getpixel((x_slot_3, y))
        self.assertNotEqual(pixel_slot_2, pixel_slot_3)

    def test_drop_preview_uses_normalized_card_size(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (32, 32), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        raw = png_bytes((64, 128, 196))
        with patch("noodswap.images.read_local_card_image_bytes", side_effect=[raw, raw, raw]):
            preview = _build_drop_preview_blocking([
                ("SPG", 1),
                ("PEN", 2),
                ("FUS", 3),
            ])

        self.assertIsNotNone(preview)
        if preview is None:
            self.fail("Expected drop preview bytes")

        composed = Image.open(io.BytesIO(preview)).convert("RGB")
        card_w, card_h = DEFAULT_CARD_RENDER_SIZE
        gap = 16
        pad = 16
        expected_width = (card_w * 3) + (gap * 2) + (pad * 2)
        expected_height = card_h + (pad * 2)
        self.assertEqual(composed.size, (expected_width, expected_height))

    def test_drop_preview_background_is_transparent(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (32, 32), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        raw = png_bytes((120, 40, 200))
        with patch("noodswap.images.read_local_card_image_bytes", side_effect=[raw, raw, raw]):
            preview = _build_drop_preview_blocking([
                ("SPG", 1),
                ("PEN", 2),
                ("FUS", 3),
            ])

        self.assertIsNotNone(preview)
        if preview is None:
            self.fail("Expected drop preview bytes")

        composed = Image.open(io.BytesIO(preview)).convert("RGBA")
        # The top-left pixel is outside all card surfaces and should stay fully transparent.
        self.assertEqual(composed.getpixel((0, 0)), (0, 0, 0, 0))


class CardRenderRegressionTests(unittest.TestCase):
    def test_render_card_image_bytes_applies_common_border_color(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (20, 20), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes((220, 30, 30))):
            rendered = render_card_image_bytes("SPG")

        self.assertIsNotNone(rendered)
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGBA")
        self.assertEqual(image.size, DEFAULT_CARD_RENDER_SIZE)

        expected_color = RARITY_BORDER_COLORS["common"]
        sample_x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        sample_y = 0
        for y in range(DEFAULT_CARD_RENDER_SIZE[1]):
            if image.getpixel((sample_x, y))[3] > 0:
                sample_y = y
                break
        sampled_rgba = image.getpixel((sample_x, min(DEFAULT_CARD_RENDER_SIZE[1] - 1, sample_y + 2)))
        sampled = (sampled_rgba[0], sampled_rgba[1], sampled_rgba[2])
        channel_diffs = [abs(sampled[idx] - expected_color[idx]) for idx in range(3)]
        self.assertLessEqual(max(channel_diffs), 8)

    def test_render_card_image_bytes_applies_bottom_gradient_and_generation_text(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (24, 24), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes((50, 50, 50))):
            rendered_gen_1 = render_card_image_bytes("SPG", generation=1)
            rendered_gen_2 = render_card_image_bytes("SPG", generation=2)

        self.assertIsNotNone(rendered_gen_1)
        self.assertIsNotNone(rendered_gen_2)
        if rendered_gen_1 is None or rendered_gen_2 is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered_gen_1)).convert("RGB")

        bottom_sample = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] - 32))
        upper_sample = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        self.assertNotEqual(bottom_sample, upper_sample)

        # Different generation text should produce different rendered output.
        self.assertNotEqual(rendered_gen_1, rendered_gen_2)

    def test_render_card_image_bytes_applies_buttery_frame(self) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (30, 30), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        overlay = Image.new("RGBA", DEFAULT_CARD_RENDER_SIZE, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, 0, DEFAULT_CARD_RENDER_SIZE[0] - 1, 20), fill=(255, 210, 80, 180))

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes((100, 120, 140))),
            patch("noodswap.images._load_frame_overlay_image", return_value=overlay),
        ):
            base_rendered = render_card_image_bytes("SPG", generation=10)
            framed_rendered = render_card_image_bytes("SPG", generation=10, frame_key="buttery")

        self.assertIsNotNone(base_rendered)
        self.assertIsNotNone(framed_rendered)
        if base_rendered is None or framed_rendered is None:
            self.fail("Expected rendered card image bytes")

        self.assertNotEqual(base_rendered, framed_rendered)

    def test_render_card_image_bytes_applies_black_and_white_morph(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (30, 30), (220, 40, 30))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes()):
            rendered = render_card_image_bytes("SPG", generation=10, morph_key="black_and_white")

        self.assertIsNotNone(rendered)
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGB")
        sampled = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        red, green, blue = sampled
        self.assertLessEqual(abs(red - green), 10)
        self.assertLessEqual(abs(green - blue), 10)

    def test_render_card_image_bytes_applies_inverse_morph(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (30, 30), (40, 110, 180))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch("noodswap.images._apply_text_legibility_overlay", side_effect=lambda img, **_: img),
        ):
            rendered = render_card_image_bytes("SPG", generation=10, morph_key="inverse")

        self.assertIsNotNone(rendered)
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGB")
        sampled = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        self.assertEqual(sampled, (215, 145, 75))

    def test_render_card_image_bytes_applies_rose_tint_morph(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (30, 30), (30, 120, 200))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch("noodswap.images._apply_text_legibility_overlay", side_effect=lambda img, **_: img),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            tinted = render_card_image_bytes("SPG", generation=10, morph_key="tint_rose")

        self.assertIsNotNone(base)
        self.assertIsNotNone(tinted)
        if base is None or tinted is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base)).convert("RGB")
        tinted_image = Image.open(io.BytesIO(tinted)).convert("RGB")
        x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        y = DEFAULT_CARD_RENDER_SIZE[1] // 2
        base_r, base_g, base_b = base_image.getpixel((x, y))
        tinted_r, tinted_g, tinted_b = tinted_image.getpixel((x, y))

        self.assertGreater(tinted_r, base_r)
        self.assertLess(tinted_g, base_g)
        self.assertLess(tinted_b, base_b)

    def test_render_card_image_bytes_applies_warm_tint_morph(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (30, 30), (40, 130, 210))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch("noodswap.images._apply_text_legibility_overlay", side_effect=lambda img, **_: img),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            warm = render_card_image_bytes("SPG", generation=10, morph_key="tint_warm")

        self.assertIsNotNone(base)
        self.assertIsNotNone(warm)
        if base is None or warm is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base)).convert("RGB")
        warm_image = Image.open(io.BytesIO(warm)).convert("RGB")
        x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        y = DEFAULT_CARD_RENDER_SIZE[1] // 2
        base_r, base_g, base_b = base_image.getpixel((x, y))
        warm_r, warm_g, warm_b = warm_image.getpixel((x, y))

        self.assertGreater(warm_r, base_r)
        self.assertGreater(warm_g, base_g)
        self.assertLess(warm_b, base_b)

    def test_render_card_image_bytes_applies_upside_down_morph(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (30, 30), (0, 0, 0))
            for y in range(30):
                color = (230, 30, 30) if y < 15 else (30, 60, 220)
                for x in range(30):
                    image.putpixel((x, y), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch("noodswap.images._apply_text_legibility_overlay", side_effect=lambda img, **_: img),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            upside_down = render_card_image_bytes("SPG", generation=10, morph_key="upside_down")

        self.assertIsNotNone(base)
        self.assertIsNotNone(upside_down)
        if base is None or upside_down is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base)).convert("RGB")
        upside_down_image = Image.open(io.BytesIO(upside_down)).convert("RGB")
        center_x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        top_y = DEFAULT_CARD_RENDER_SIZE[1] // 3
        bottom_y = (DEFAULT_CARD_RENDER_SIZE[1] * 2) // 3

        base_top = base_image.getpixel((center_x, top_y))
        base_bottom = base_image.getpixel((center_x, bottom_y))
        flipped_top = upside_down_image.getpixel((center_x, top_y))
        flipped_bottom = upside_down_image.getpixel((center_x, bottom_y))

        self.assertEqual(flipped_top, base_bottom)
        self.assertEqual(flipped_bottom, base_top)


class LocalImageBytesTests(unittest.TestCase):
    def test_get_card_image_bytes_returns_local_bytes(self) -> None:
        with patch("noodswap.commands.read_local_card_image_bytes", return_value=b"local-bytes") as read_local:
            resolved = _get_card_image_bytes("SPG")

        self.assertEqual(resolved, b"local-bytes")
        read_local.assert_called_once_with("SPG")

    def test_get_card_image_bytes_returns_none_when_local_missing(self) -> None:
        with patch("noodswap.commands.read_local_card_image_bytes", return_value=None) as read_local:
            resolved = _get_card_image_bytes("SPG")

        self.assertIsNone(resolved)
        read_local.assert_called_once_with("SPG")

if __name__ == "__main__":
    unittest.main()
