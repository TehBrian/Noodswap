import io
import re
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from pathlib import Path

import discord
from discord.ext import commands

from noodswap import storage
from noodswap.command_utils import (
    SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS,
    SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS,
    _animate_slots_spin,
    _build_drop_preview_blocking,
    _get_card_image_bytes,
    _slots_reel_content,
)
from noodswap.commands import register_commands
from noodswap.images import DEFAULT_CARD_RENDER_SIZE, HD_CARD_RENDER_SIZE, RARITY_BORDER_COLORS, render_card_image_bytes
from noodswap.presentation import HELP_CATEGORY_PAGES
from noodswap.views import GiftCardView, HelpView, PlayerLeaderboardView, SortableCardListView, SortableCollectionView


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


def _normalize_help_command_path(text: str) -> str:
    tokens: list[str] = []
    for token in text.strip().split():
        if token.startswith("<") or token.startswith("["):
            break
        tokens.append(token)
    return " ".join(tokens)


def _iter_alias_command_paths(line: str, command_path: str) -> list[str]:
    alias_paths: list[str] = []
    parent_tokens = command_path.split()
    for alias_text in re.findall(r"\(([^)]*)\)", line):
        for alias in re.findall(r"`([^`]+)`", alias_text):
            if alias.startswith("... "):
                if len(parent_tokens) < 2:
                    continue
                alias_suffix = _normalize_help_command_path(alias[4:])
                if not alias_suffix:
                    continue
                alias_paths.append(" ".join([*parent_tokens[:-1], alias_suffix]))
                continue

            alias_command_path = _normalize_help_command_path(alias)
            if alias_command_path:
                alias_paths.append(alias_command_path)
    return alias_paths


def _iter_help_alias_expectations() -> list[tuple[str, str]]:
    expectations: list[tuple[str, str]] = []
    for _category_key, _category_label, description in HELP_CATEGORY_PAGES:
        for line in description.splitlines():
            line = line.strip()
            if not line.startswith("- "):
                continue

            command_match = re.search(r"`([^`]+)`", line)
            if command_match is None:
                continue
            command_path = _normalize_help_command_path(command_match.group(1))
            if not command_path:
                continue

            for alias_command_path in _iter_alias_command_paths(line, command_path):
                expectations.append((alias_command_path, command_path))
    return expectations


_HELP_ALIAS_SHORTCUT_TARGETS: dict[str, str] = {
    "wa": "wish add",
    "wr": "wish remove",
    "wl": "wish list",
}


class CommandHelpAliasConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    def test_help_menu_aliases_resolve_to_registered_commands(self) -> None:
        for alias_command_path, expected_target_path in _iter_help_alias_expectations():
            with self.subTest(alias=alias_command_path, expected=expected_target_path):
                resolved = self.bot.get_command(alias_command_path)
                self.assertIsNotNone(
                    resolved,
                    msg=f"Help alias `{alias_command_path}` does not resolve to a registered command.",
                )

                assert resolved is not None
                allowed_targets = {expected_target_path}
                if alias_command_path in _HELP_ALIAS_SHORTCUT_TARGETS:
                    allowed_targets.add(alias_command_path)
                self.assertIn(
                    resolved.qualified_name,
                    allowed_targets,
                    msg=(
                        f"Help alias `{alias_command_path}` resolves to `{resolved.qualified_name}` "
                        f"instead of one of {sorted(allowed_targets)}."
                    ),
                )


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

        with patch("noodswap.commands_social._wish_list", new=AsyncMock()) as wish_list_impl:
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
            patch("noodswap.command_utils.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
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

        with patch("noodswap.commands_social._wish_list", new=AsyncMock()) as wish_list_impl:
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
            patch("noodswap.command_utils.search_card_ids_by_name", return_value=["SPG"]),
            patch("noodswap.command_utils.add_card_to_wishlist", return_value=True) as add_wishlist,
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

        with patch("noodswap.command_utils.add_card_to_wishlist", return_value=True) as add_wishlist:
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

        with patch("noodswap.command_utils.list_player_tags", return_value=[]):
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
            "noodswap.command_utils.list_player_tags",
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

        with patch("noodswap.command_utils.get_instance_by_code", return_value=None):
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
            patch("noodswap.command_utils.get_instance_by_code", return_value=selected),
            patch("noodswap.command_utils.is_tag_assigned_to_instance", return_value=True),
            patch("noodswap.command_utils.assign_tag_to_instance", return_value=False) as assign_tag,
        ):
            await tag_assign_command.callback(ctx, tag_name="safe", card_code="0")

        assign_tag.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Tags")
        self.assertEqual(sent_embed.description, "That card is already assigned to this tag.")

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
            patch("noodswap.command_utils.get_instances_by_tag", return_value=tagged_instances),
            patch("noodswap.command_utils.get_locked_instance_ids", return_value=set()),
            patch("noodswap.command_utils.get_card_wish_counts", return_value={"SPG": 1, "BAR": 2}),
            patch("noodswap.command_utils.get_instance_morph", return_value=None),
            patch("noodswap.command_utils.get_instance_frame", return_value=None),
            patch("noodswap.command_utils.get_instance_font", return_value=None),
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

        with patch("noodswap.command_utils.remove_card_from_wishlist", return_value=True) as remove_wishlist:
            await wish_remove_command.callback(ctx, card_id="cheddar")

        remove_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist Matches")
        self.assertIn("1. (`CHD`) [🧀] **Cheddar**", sent_embed.description)
        self.assertIn("2. (`CHJ`) [🧀] **Cheddar Jack**", sent_embed.description)


class CommandsFolderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_folder_list_shows_lock_markers_and_emoji(self) -> None:
        folder_list_command = _get_group_command(self.bot, "folder", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.command_utils.list_player_folders",
            return_value=[("vault", "📦", True, 2), ("dump", "🗑️", False, 1)],
        ):
            await folder_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Your Folders")
        self.assertIn("🔒 📦 `vault` - Locked - 2 card(s)", sent_embed.description)
        self.assertIn("`  ` 🗑️ `dump` - Unlocked - 1 card(s)", sent_embed.description)

    async def test_folder_assign_rejects_duplicate_assignment(self) -> None:
        folder_assign_command = _get_group_command(self.bot, "folder", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        selected = (5, "SPG", 1200, "0")
        with (
            patch("noodswap.command_utils.get_instance_by_code", return_value=selected),
            patch("noodswap.command_utils.is_instance_assigned_to_folder", return_value=True),
            patch("noodswap.command_utils.assign_instance_to_folder", return_value=False) as assign_folder,
        ):
            await folder_assign_command.callback(ctx, folder_name="vault", card_code="0")

        assign_folder.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Folders")
        self.assertEqual(sent_embed.description, "That card is already assigned to this folder.")


class CommandsBurnSelectorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_burn_rejects_selector_without_value(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await burn_command.callback(ctx, "t:")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Burn")
        self.assertEqual(sent_embed.description, "Missing value for `t:` selector.")

    async def test_burn_supports_folder_selector(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        with (
            patch("noodswap.command_utils.get_instances_by_folder", return_value=[(10, "SPG", 100, "0")]),
            patch(
                "noodswap.commands_economy.prepare_burn_batch",
                return_value=SimpleNamespace(
                    is_error=False,
                    error_message=None,
                    items=(
                        SimpleNamespace(
                            instance_id=10,
                            card_id="SPG",
                            generation=100,
                            dupe_code="0",
                            value=10,
                            base_value=9,
                            delta_range=1,
                            multiplier=1.1,
                        ),
                    ),
                    total_value=10,
                    total_delta_range=1,
                ),
            ),
            patch("noodswap.command_utils.get_instance_morph", return_value=None),
            patch("noodswap.command_utils.get_instance_frame", return_value=None),
            patch("noodswap.command_utils.get_instance_font", return_value=None),
            patch("noodswap.commands_economy.embed_image_payload", return_value=(None, None)),
        ):
            await burn_command.callback(ctx, "f:vault")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Burn Confirmation")

    async def test_burn_supports_tag_and_card_targets_together(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        fake_items = (
            SimpleNamespace(
                instance_id=10,
                card_id="SPG",
                generation=100,
                dupe_code="0",
                value=12,
                base_value=3,
                delta_range=2,
                multiplier=1.5,
            ),
            SimpleNamespace(
                instance_id=11,
                card_id="PEN",
                generation=200,
                dupe_code="1",
                value=14,
                base_value=4,
                delta_range=3,
                multiplier=1.7,
            ),
        )
        prepared = SimpleNamespace(
            is_error=False,
            error_message=None,
            items=fake_items,
            total_value=26,
            total_delta_range=5,
        )

        class _FakeBurnView:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.message = None

        with (
            patch("noodswap.command_utils.get_instances_by_tag", return_value=[(10, "SPG", 100, "0")]),
            patch("noodswap.command_utils.get_instance_by_code", return_value=(11, "PEN", 200, "1")),
            patch("noodswap.commands_economy.prepare_burn_batch", return_value=prepared),
            patch("noodswap.commands_economy.BurnConfirmView", _FakeBurnView),
        ):
            await burn_command.callback(ctx, "t:safe", "a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Burn Confirmation")
        self.assertIn("Cards: **2**", sent_embed.description)
        self.assertEqual(
            sent_view.kwargs["burn_items"],
            [(10, 2), (11, 3)],
        )


class CommandsTeamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_team_cards_shows_hp_atk_def_stats(self) -> None:
        team_cards_command = _get_group_command(self.bot, "team", "cards")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        team_instances = [
            (1, "SPG", 1200, "0"),
            (2, "BAR", 900, "1"),
        ]
        with (
            patch("noodswap.command_utils.get_instances_by_team", return_value=team_instances),
            patch("noodswap.command_utils.get_locked_instance_ids", return_value=set()),
            patch("noodswap.command_utils.get_card_wish_counts", return_value={"SPG": 1, "BAR": 2}),
            patch("noodswap.command_utils.get_instance_morph", return_value=None),
            patch("noodswap.command_utils.get_instance_frame", return_value=None),
            patch("noodswap.command_utils.get_instance_font", return_value=None),
        ):
            await team_cards_command.callback(ctx, team_name="alpha")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Team: `alpha`")
        self.assertRegex(sent_embed.description, r"HP:\d+ ATK:\d+ DEF:\d+")
        self.assertIsInstance(sent_view, SortableCollectionView)
        self.assertIs(sent_view.message, ctx.send.return_value)


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
        self.assertIn("sl", _get_command(self.bot, "slots").aliases)
        self.assertIn("f", _get_command(self.bot, "flip").aliases)
        self.assertIn("g", _get_command(self.bot, "gift").aliases)
        self.assertIn("tg", _get_command(self.bot, "tag").aliases)
        self.assertIn("fd", _get_command(self.bot, "folder").aliases)


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
            (100, 2, 1, 20, 0, 0, 40),
            (200, 5, 3, 50, 2, 1, 120),
        ]
        with patch("noodswap.commands_social.get_player_leaderboard_info", return_value=leaderboard_rows):
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
            "noodswap.commands_catalog.get_instance_by_dupe_code",
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
        self.assertIn("**Traits**", sent_embed.description)
        self.assertIn("**Value Breakdown**", sent_embed.description)
        self.assertIn("Trait Multiplier", sent_embed.description)

    async def test_lookup_shows_dupe_card_embed_for_hash_prefixed_code(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands_catalog.get_instance_by_dupe_code",
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
        self.assertIn("**Traits**", sent_embed.description)
        self.assertIn("**Value Breakdown**", sent_embed.description)

    async def test_lookup_prefers_exact_dupe_code_over_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands_catalog.get_instance_by_dupe_code",
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
        self.assertIn("Trait Multiplier", sent_embed.description)

    async def test_lookup_falls_back_to_exact_card_name(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands_catalog.search_card_ids", return_value=["SPG"]):
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

        with patch("noodswap.commands_catalog.search_card_ids", return_value=["SPG"]) as search_cards:
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
            "noodswap.commands_catalog.embed_image_payload",
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

        with patch("noodswap.commands_economy.get_player_card_instances", return_value=[]):
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
            patch("noodswap.command_utils.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands_economy.get_player_card_instances", return_value=[]),
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

        with patch("noodswap.commands_economy.get_player_card_instances", return_value=[]):
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
                "noodswap.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("noodswap.commands_economy.get_player_card_instances", return_value=[]),
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
            patch("noodswap.commands_economy.get_player_card_instances", return_value=instances),
            patch("noodswap.command_utils.get_locked_instance_ids", return_value=set()),
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
            patch("noodswap.commands_economy.get_player_card_instances", return_value=instances),
            patch("noodswap.command_utils.get_locked_instance_ids", return_value=set()),
        ):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], SortableCollectionView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2 • Sort: Alphabetical (Asc)")

    async def test_wish_list_uses_pagination_view_for_multi_page_results(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        wishlisted_ids = ["SPG", "PEN", "FUS", "CHD", "CHJ", "BGL", "BAG", "BOL", "PIT", "RYE", "SOU"]
        with patch("noodswap.command_utils.get_wishlist_cards", return_value=wishlisted_ids):
            await wish_list_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], SortableCardListView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2 • Sort: Alphabetical (Asc)")

    async def test_wish_list_sends_error_when_player_resolution_fails(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "noodswap.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("noodswap.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
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
            patch("noodswap.command_utils.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
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
            patch("noodswap.commands_social.get_player_cooldown_timestamps", return_value=(0.0, 0.0)),
            patch("noodswap.commands_social.get_player_slots_timestamp", return_value=0.0),
            patch("noodswap.commands_social.get_player_flip_timestamp", return_value=0.0),
            patch("noodswap.commands_gambling.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Caller's Cooldowns")
        self.assertIn("Drop:", sent_embed.description)
        self.assertIn("Pull:", sent_embed.description)
        self.assertIn("Slots:", sent_embed.description)
        self.assertIn("Flip:", sent_embed.description)
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
            patch("noodswap.command_utils.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands_social.get_player_cooldown_timestamps", return_value=(9_800.0, 9_850.0)),
            patch("noodswap.commands_social.get_player_slots_timestamp", return_value=9_950.0),
            patch("noodswap.commands_social.get_player_flip_timestamp", return_value=9_980.0),
            patch("noodswap.commands_gambling.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Cooldowns")


class CommandsBuyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_buy_drop_shows_usage_when_group_called(self) -> None:
        buy_command = _get_command(self.bot, "buy")

        ctx = AsyncMock()
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await buy_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Buy")
        self.assertIn("ns buy drop", sent_embed.description)

    async def test_buy_drop_purchases_with_starter(self) -> None:
        buy_drop_command = _get_group_command(self.bot, "buy", "drop")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("noodswap.commands_catalog.buy_drop_tickets_with_starter", return_value=(True, 4, 7, 3)) as buy_tickets:
            await buy_drop_command.callback(ctx, quantity=3)

        buy_tickets.assert_called_once_with(1, 100, 3)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Buy")
        self.assertIn("Purchased: **3 drop ticket(s)**", sent_embed.description)
        self.assertIn("Starter Balance: **4**", sent_embed.description)
        self.assertIn("Drop Tickets: **7**", sent_embed.description)


class CommandsDropTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_drop_footer_mentions_ticket_use(self) -> None:
        drop_command = _get_command(self.bot, "drop")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        prepared = SimpleNamespace(
            is_cooldown=False,
            cooldown_remaining_seconds=0.0,
            choices=[("SPG", 100), ("PEN", 200), ("FUS", 300)],
            used_drop_ticket=True,
        )
        with (
            patch("noodswap.commands_economy.prepare_drop", return_value=prepared),
            patch("noodswap.commands_economy.build_drop_preview_file", new=AsyncMock(return_value=None)),
            patch("noodswap.commands_economy.DropView") as drop_view_cls,
        ):
            view = SimpleNamespace(message=None)
            drop_view_cls.return_value = view
            await drop_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertIn("drop ticket used", sent_embed.footer.text)


class CommandsCooldownReplyTargetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

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
            patch("noodswap.commands_social.get_player_cooldown_timestamps", return_value=(9_800.0, 9_850.0)),
            patch("noodswap.commands_social.get_player_slots_timestamp", return_value=9_950.0),
            patch("noodswap.commands_social.get_player_flip_timestamp", return_value=9_980.0),
            patch("noodswap.commands_gambling.time.time", return_value=10_000.0),
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
            patch("noodswap.commands_gambling.consume_slots_cooldown_if_ready", return_value=60.0),
            patch("noodswap.commands_gambling.add_starter") as add_starter,
            patch("noodswap.commands_gambling._animate_slots_spin", new=AsyncMock()) as animate,
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
            patch("noodswap.commands_gambling.consume_slots_cooldown_if_ready", return_value=0.0),
            patch("noodswap.commands_gambling.random.choice", return_value="🍞"),
            patch("noodswap.commands_gambling.random.randint", return_value=2),
            patch("noodswap.commands_gambling.add_starter", return_value=7) as add_starter,
            patch("noodswap.commands_gambling._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_starter.assert_called_once_with(1, 100, 2)
        animate.assert_awaited_once()
        self.assertGreaterEqual(message.edit.await_count, 1)
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertEqual(final_embed.title, "Slots")
        self.assertIn("Jackpot", final_embed.description)
        self.assertIn("+2 starter", final_embed.description)


class CommandsFlipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_flip_rejects_non_integer_stake(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await flip_command.callback(ctx, stake_str="abc")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Flip")
        self.assertIn("positive integer", sent_embed.description)

    async def test_flip_rejects_invalid_side(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await flip_command.callback(ctx, stake_str="10", side_str="left")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Flip")
        self.assertIn("heads", sent_embed.description)
        self.assertIn("tails", sent_embed.description)

    async def test_flip_shows_cooldown_message(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands_gambling.execute_flip_wager",
            return_value=("cooldown", 30.0, 50),
        ):
            await flip_command.callback(ctx, stake_str="10")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Flip Cooldown")
        self.assertIn("remaining", sent_embed.description)

    async def test_flip_shows_insufficient_dough_message(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "noodswap.commands_gambling.execute_flip_wager",
            return_value=("insufficient_dough", 0.0, 5),
        ):
            await flip_command.callback(ctx, stake_str="10")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Flip")
        self.assertIn("do not have enough dough", sent_embed.description)
        self.assertIn("Balance: **5**", sent_embed.description)

    async def test_flip_shows_heads_on_win_after_delay(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands_gambling.random.random", return_value=0.1),
            patch("noodswap.commands_gambling.random.choice", return_value="rolling"),
            patch("noodswap.commands_gambling.execute_flip_wager", return_value=("won", 0.0, 60)) as execute_flip,
            patch("noodswap.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await flip_command.callback(ctx, stake_str="10")

        execute_flip.assert_called_once()
        ctx.send.assert_awaited_once()
        first_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(first_embed.title, "Flip")
        self.assertIn("coin is", first_embed.description)
        self.assertNotIn("Result", first_embed.description)
        sleep_mock.assert_awaited_once_with(3.0)

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertIn("Heads", final_embed.description)
        self.assertIn("+10", final_embed.description)

    async def test_flip_shows_tails_on_loss_after_delay(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands_gambling.random.random", return_value=0.9),
            patch("noodswap.commands_gambling.random.choice", return_value="spinning"),
            patch("noodswap.commands_gambling.execute_flip_wager", return_value=("lost", 0.0, 40)) as execute_flip,
            patch("noodswap.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await flip_command.callback(ctx, stake_str="10")

        execute_flip.assert_called_once()
        ctx.send.assert_awaited_once()
        first_embed = ctx.send.await_args.kwargs["embed"]
        self.assertIn("coin is", first_embed.description)
        sleep_mock.assert_awaited_once_with(3.0)

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertIn("Tails", final_embed.description)
        self.assertIn("-10", final_embed.description)

    async def test_flip_respects_heads_call_illusion(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands_gambling.random.random", return_value=0.1),
            patch("noodswap.commands_gambling.random.choice", return_value="whirling"),
            patch("noodswap.commands_gambling.execute_flip_wager", return_value=("won", 0.0, 60)),
            patch("noodswap.commands_gambling.asyncio.sleep", new=AsyncMock()),
        ):
            await flip_command.callback(ctx, stake_str="10", side_str="heads")

        first_embed = ctx.send.await_args.kwargs["embed"]
        self.assertIn("Call: **Heads**", first_embed.description)
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertIn("Result: **Heads**", final_embed.description)

    async def test_flip_respects_t_alias_call_illusion(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("noodswap.commands_gambling.random.random", return_value=0.1),
            patch("noodswap.commands_gambling.random.choice", return_value="tumbling"),
            patch("noodswap.commands_gambling.execute_flip_wager", return_value=("won", 0.0, 60)),
            patch("noodswap.commands_gambling.asyncio.sleep", new=AsyncMock()),
        ):
            await flip_command.callback(ctx, stake_str="10", side_str="t")

        first_embed = ctx.send.await_args.kwargs["embed"]
        self.assertIn("Call: **Tails**", first_embed.description)
        final_embed = message.edit.await_args.kwargs["embed"]
        self.assertIn("Result: **Tails**", final_embed.description)


class CommandsSlotsAnimationTests(unittest.IsolatedAsyncioTestCase):
    async def test_slots_reel_content_hides_status_emoji_until_result(self) -> None:
        symbols = ["🍞", "🍞", "🍞"]
        self.assertEqual(_slots_reel_content(symbols), "🍞🍞🍞")
        self.assertEqual(_slots_reel_content(symbols, result_emoji="🎉"), "🍞🍞🍞🎉")

    async def test_animate_slots_spin_uses_tapered_frame_delays(self) -> None:
        message = AsyncMock()

        with (
            patch("noodswap.commands_gambling.random.randint", return_value=4),
            patch("noodswap.commands_gambling.random.choice", return_value="🍞"),
            patch("noodswap.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
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
            patch("noodswap.commands_social.get_player_info", return_value=(123, 0.0, None)),
            patch("noodswap.commands_social.get_player_starter", return_value=9),
            patch("noodswap.commands_social.get_player_drop_tickets", return_value=4),
            patch("noodswap.commands_social.get_total_cards", return_value=7),
            patch("noodswap.commands_social.get_wishlist_cards", return_value=["SPG", "PEN", "FUS"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        field_values = {field.name: field.value for field in sent_embed.fields}
        self.assertEqual(field_values.get("Cards"), "7")
        self.assertEqual(field_values.get("Dough"), "123")
        self.assertEqual(field_values.get("Starter"), "9")
        self.assertEqual(field_values.get("Drop Tickets"), "4")
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
            patch("noodswap.commands_social.get_player_info", return_value=(999, 0.0, None)),
            patch("noodswap.commands_social.get_player_starter", return_value=2),
            patch("noodswap.commands_social.get_player_drop_tickets", return_value=0),
            patch("noodswap.commands_social.get_total_cards", return_value=4),
            patch("noodswap.commands_social.get_wishlist_cards", return_value=["SPG"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Info")


class CommandsGiftTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_gift_rejects_bot_target(self) -> None:
        gift_card_command = _get_group_command(self.bot, "gift", "card")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        bot_target = _FakeMember(200, "BotTarget")
        bot_target.bot = True
        with (
            patch("noodswap.commands_economy.resolve_member_argument", new=AsyncMock(return_value=(bot_target, None))),
            patch("noodswap.commands_economy.prepare_gift_offer") as prepare_gift,
        ):
            await gift_card_command.callback(ctx, player="@BotTarget", card_code="0")

        prepare_gift.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Gift")
        self.assertIn("cannot gift cards to bots", sent_embed.description)

    async def test_gift_success_sends_offer_embed_with_confirmation_view(self) -> None:
        gift_card_command = _get_group_command(self.bot, "gift", "card")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch("noodswap.commands_economy.resolve_member_argument", new=AsyncMock(return_value=(target, None))),
            patch(
                "noodswap.commands_economy.prepare_gift_offer",
                return_value=SimpleNamespace(
                    is_error=False,
                    error_message=None,
                    card_id="SPG",
                    generation=123,
                    dupe_code="a",
                ),
            ) as prepare_gift,
            patch("noodswap.commands_economy.get_instance_by_code", return_value=(10, "SPG", 123, "a")),
            patch("noodswap.commands_economy.get_instance_morph", return_value=None),
            patch("noodswap.commands_economy.get_instance_frame", return_value=None),
            patch("noodswap.commands_economy.get_instance_font", return_value=None),
            patch("noodswap.commands_economy.embed_image_payload", return_value=("attachment://gift.png", None)),
        ):
            await gift_card_command.callback(ctx, player="@Target", card_code="0")

        prepare_gift.assert_called_once_with(
            guild_id=1,
            sender_id=100,
            recipient_id=200,
            recipient_is_bot=False,
            card_code="0",
        )
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Gift Offer")
        self.assertIn("Offered to: <@200>", sent_embed.description)
        self.assertIn("Sender: <@100>", sent_embed.description)
        self.assertIsInstance(sent_view, GiftCardView)
        self.assertEqual(sent_embed.thumbnail.url, "attachment://gift.png")

    async def test_gift_dough_success_updates_balances(self) -> None:
        gift_dough_command = _get_group_command(self.bot, "gift", "dough")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch("noodswap.commands_economy.resolve_member_argument", new=AsyncMock(return_value=(target, None))),
            patch("noodswap.commands_economy.execute_gift_dough", return_value=(True, "", 70, 30)) as gift_dough,
        ):
            await gift_dough_command.callback(ctx, player="@Target", amount=20)

        gift_dough.assert_called_once_with(guild_id=1, sender_id=100, recipient_id=200, amount=20)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Gift")
        self.assertIn("Sent: **20** dough", sent_embed.description)
        self.assertIn("Your Balance: **70** dough", sent_embed.description)
        self.assertIn("Target's Balance: **30** dough", sent_embed.description)


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
        self.assertIn("Vote checking is temporarily unavailable", sent_embed.description)
        self.assertIn("vote using the button below", sent_embed.description)
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
            patch("noodswap.commands_catalog._topgg_recent_vote_status", new=AsyncMock(return_value=(True, None))),
            patch("noodswap.commands_catalog.claim_vote_reward", return_value=5),
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
            items=(
                SimpleNamespace(
                    instance_id=77,
                    card_id="SPG",
                    generation=321,
                    dupe_code="a",
                    value=40,
                    base_value=38,
                    delta_range=8,
                    multiplier=1.05,
                ),
            ),
            total_value=40,
            total_delta_range=8,
        )

        with (
            patch("noodswap.command_utils.get_instance_by_code", return_value=(77, "SPG", 321, "a")),
            patch("noodswap.commands_economy.prepare_burn_batch", return_value=prepared),
        ):
            await burn_command.callback(ctx, "a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Burn Confirmation")
        self.assertIn("`#a", sent_embed.description)
        self.assertNotIn("`#?`", sent_embed.description)

    async def test_burn_supports_folder_selector(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        prepared = SimpleNamespace(
            is_error=False,
            error_message=None,
            items=(
                SimpleNamespace(
                    instance_id=10,
                    card_id="SPG",
                    generation=100,
                    dupe_code="0",
                    value=10,
                    base_value=9,
                    delta_range=1,
                    multiplier=1.1,
                ),
            ),
            total_value=10,
            total_delta_range=1,
        )

        with (
            patch("noodswap.command_utils.get_instances_by_folder", return_value=[(10, "SPG", 100, "0")]),
            patch("noodswap.commands_economy.prepare_burn_batch", return_value=prepared),
            patch("noodswap.command_utils.get_instance_morph", return_value=None),
            patch("noodswap.command_utils.get_instance_frame", return_value=None),
            patch("noodswap.command_utils.get_instance_font", return_value=None),
            patch("noodswap.commands_economy.embed_image_payload", return_value=(None, None)),
        ):
            await burn_command.callback(ctx, "f:vault")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Burn Confirmation")


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

        with patch("noodswap.commands_economy.prepare_morph", return_value=result):
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

        with patch("noodswap.commands_economy.prepare_morph", return_value=result):
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

        with patch("noodswap.commands_economy.prepare_frame", return_value=result):
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

        with patch("noodswap.commands_economy.prepare_frame", return_value=result):
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

        with patch("noodswap.commands_economy.prepare_font", return_value=result):
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

        with patch("noodswap.commands_economy.prepare_font", return_value=result):
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
            patch("noodswap.images._load_frame_image", return_value=overlay),
        ):
            base_rendered = render_card_image_bytes("SPG", generation=10)
            framed_rendered = render_card_image_bytes("SPG", generation=10, frame_key="buttery")

        self.assertIsNotNone(base_rendered)
        self.assertIsNotNone(framed_rendered)
        if base_rendered is None or framed_rendered is None:
            self.fail("Expected rendered card image bytes")

        self.assertNotEqual(base_rendered, framed_rendered)

    def test_render_card_image_bytes_scales_body_down_when_frame_enabled(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (30, 30), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        transparent_overlay = Image.new("RGBA", DEFAULT_CARD_RENDER_SIZE, (0, 0, 0, 0))

        with (
            patch("noodswap.images.read_local_card_image_bytes", return_value=png_bytes((120, 140, 160))),
            patch("noodswap.images._load_frame_image", return_value=transparent_overlay),
        ):
            base_rendered = render_card_image_bytes("SPG", generation=10)
            framed_rendered = render_card_image_bytes("SPG", generation=10, frame_key="buttery")

        self.assertIsNotNone(base_rendered)
        self.assertIsNotNone(framed_rendered)
        if base_rendered is None or framed_rendered is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base_rendered)).convert("RGBA")
        framed_image = Image.open(io.BytesIO(framed_rendered)).convert("RGBA")

        sample_x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        sample_y = 12
        self.assertGreater(base_image.getpixel((sample_x, sample_y))[3], 0)
        self.assertEqual(framed_image.getpixel((sample_x, sample_y))[3], 0)

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
        with patch("noodswap.command_utils.read_local_card_image_bytes", return_value=b"local-bytes") as read_local:
            resolved = _get_card_image_bytes("SPG")

        self.assertEqual(resolved, b"local-bytes")
        read_local.assert_called_once_with("SPG")

    def test_get_card_image_bytes_returns_none_when_local_missing(self) -> None:
        with patch("noodswap.command_utils.read_local_card_image_bytes", return_value=None) as read_local:
            resolved = _get_card_image_bytes("SPG")

        self.assertIsNone(resolved)
        read_local.assert_called_once_with("SPG")

if __name__ == "__main__":
    unittest.main()
