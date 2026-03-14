import io
import re
import tempfile
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from pathlib import Path

import discord
from discord.ext import commands

from bot import storage
from bot.command_utils import (
    SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS,
    SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS,
    _animate_slots_spin,
    _build_drop_preview_blocking,
    _get_card_image_bytes,
    _slots_reel_content,
    ship_compatibility_percent,
)
from bot.commands import register_commands
from bot.images import (
    DEFAULT_CARD_RENDER_SIZE,
    HD_CARD_RENDER_SIZE,
    RARITY_BORDER_COLORS,
    render_card_image_bytes,
)
from bot.morphs import AVAILABLE_MORPHS
from bot.presentation import HELP_CATEGORY_PAGES
from bot.views import (
    HelpView,
    PlayerLeaderboardView,
    SortableCardListView,
    SortableCollectionView,
)

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

    @property
    def members(self) -> list[Any]:
        return list(self._members.values())


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


@asynccontextmanager
async def _gate_result(entered: bool):
    yield entered


def _expand_help_alias(alias: str, parent_tokens: list[str]) -> str | None:
    if not alias.startswith("... "):
        return _normalize_help_command_path(alias)

    if len(parent_tokens) < 2:
        return None
    alias_suffix = _normalize_help_command_path(alias[4:])
    if not alias_suffix:
        return None
    return " ".join([*parent_tokens[:-1], alias_suffix])


def _iter_alias_command_paths(line: str, command_path: str) -> list[str]:
    alias_paths: list[str] = []
    parent_tokens = command_path.split()
    for alias_text in re.findall(r"\(([^)]*)\)", line):
        for alias in re.findall(r"`([^`]+)`", alias_text):
            alias_command_path = _expand_help_alias(alias, parent_tokens)
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


class CommandHelpAliasConsistencyTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    def test_help_menu_aliases_resolve_to_registered_commands(self) -> None:
        for alias_command_path, expected_target_path in _iter_help_alias_expectations():
            resolved = self.bot.get_command(alias_command_path)
            assert resolved is not None, f"Help alias `{alias_command_path}` does not resolve to a registered command."

            allowed_targets = {expected_target_path}
            if alias_command_path in _HELP_ALIAS_SHORTCUT_TARGETS:
                allowed_targets.add(alias_command_path)
            assert resolved.qualified_name in allowed_targets, (
                f"Help alias `{alias_command_path}` resolves to `{resolved.qualified_name}` instead of one of {sorted(allowed_targets)}."
            )


class CommandsWishlistTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_wish_list_defaults_to_author_when_player_omitted(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.commands_social._wish_list", new=AsyncMock()) as wish_list_impl:
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
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ) as resolve_member,
            patch("bot.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
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

        with patch("bot.commands_social._wish_list", new=AsyncMock()) as wish_list_impl:
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
            patch("bot.command_utils.search_card_ids_by_name", return_value=["SPG"]),
            patch("bot.command_utils.add_card_to_wishlist", return_value=True) as add_wishlist,
        ):
            await wish_add_command.callback(ctx, "spaghetti")

        add_wishlist.assert_called_once_with(1, 100, "SPG")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist"
        assert "Added to wishlist" in sent_embed.description
        assert "(`SPG`)" in sent_embed.description

    async def test_wish_add_lists_multiple_name_matches_with_numbering(self) -> None:
        wish_add_command = _get_group_command(self.bot, "wish", "add")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.command_utils.add_card_to_wishlist", return_value=True) as add_wishlist:
            await wish_add_command.callback(ctx, "cheddar")

        add_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist Matches"
        assert "1. (`CHD`) [🧀] **Cheddar**" in sent_embed.description
        assert "2. (`CHJ`) [🧀] **Cheddar Jack**" in sent_embed.description

    async def test_wish_add_batch_lists_added_cards_on_separate_lines(self) -> None:
        wish_add_command = _get_group_command(self.bot, "wish", "add")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("bot.command_utils.search_card_ids_by_name", side_effect=[[], []]),
            patch(
                "bot.command_utils.add_card_to_wishlist",
                side_effect=[True, True],
            ),
            patch(
                "bot.command_utils.card_base_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await wish_add_command.callback(ctx, "SPG", "BAR")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist"
        assert sent_embed.description == "Added cards to wishlist:\ncard zero\ncard one"

    async def test_wish_remove_batch_lists_removed_cards_on_separate_lines(self) -> None:
        wish_remove_command = _get_group_command(self.bot, "wish", "remove")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("bot.command_utils.search_card_ids_by_name", side_effect=[[], []]),
            patch(
                "bot.command_utils.remove_card_from_wishlist",
                side_effect=[True, True],
            ),
            patch(
                "bot.command_utils.card_base_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await wish_remove_command.callback(ctx, "SPG", "BAR")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist"
        assert sent_embed.description == "Removed cards from wishlist:\ncard zero\ncard one"


class CommandsTagTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_tag_list_shows_empty_state(self) -> None:
        tag_list_command = _get_group_command(self.bot, "tag", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.command_utils.list_player_tags", return_value=[]):
            await tag_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Your Tags"
        assert "No tags yet" in sent_embed.description

    async def test_tag_list_shows_lock_markers_for_locked_and_unlocked_tags(
        self,
    ) -> None:
        tag_list_command = _get_group_command(self.bot, "tag", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.command_utils.list_player_tags",
            return_value=[("safe", True, 2), ("trash", False, 1)],
        ):
            await tag_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Your Tags"
        assert "🔒 `safe` • 2 cards" in sent_embed.description
        assert "`  ` `trash` • 1 card" in sent_embed.description

    async def test_tag_assign_rejects_unowned_card_id(self) -> None:
        tag_assign_command = _get_group_command(self.bot, "tag", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.command_utils.get_instance_by_code", return_value=None):
            await tag_assign_command.callback(ctx, "safe", "0")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Tags"
        assert sent_embed.description == "You do not own that card ID."

    async def test_tag_assign_rejects_duplicate_assignment_explicitly(self) -> None:
        tag_assign_command = _get_group_command(self.bot, "tag", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        selected = (5, "SPG", 1200, "0")
        with (
            patch("bot.command_utils.get_instance_by_code", return_value=selected),
            patch("bot.command_utils.is_tag_assigned_to_instance", return_value=True),
            patch("bot.command_utils.assign_tag_to_instance", return_value=False) as assign_tag,
        ):
            await tag_assign_command.callback(ctx, "safe", "0")

        assign_tag.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Tags"
        assert sent_embed.description == "That card is already assigned to this tag."

    async def test_tag_assign_batch_lists_assigned_cards_on_separate_lines(self) -> None:
        tag_assign_command = _get_group_command(self.bot, "tag", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch("bot.command_utils.is_tag_assigned_to_instance", return_value=False),
            patch("bot.command_utils.assign_tag_to_instance", return_value=True),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await tag_assign_command.callback(ctx, "safe", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Tags"
        assert sent_embed.description == "Assigned cards to tag `safe`:\ncard zero\ncard one"

    async def test_tag_unassign_batch_lists_removed_cards_on_separate_lines(self) -> None:
        tag_unassign_command = _get_group_command(self.bot, "tag", "unassign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch("bot.command_utils.unassign_tag_from_instance", return_value=True),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await tag_unassign_command.callback(ctx, "safe", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Tags"
        assert sent_embed.description == "Removed cards from tag `safe`:\ncard zero\ncard one"

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
            patch(
                "bot.command_utils.get_instances_by_tag",
                return_value=tagged_instances,
            ),
            patch("bot.command_utils.get_locked_instance_ids", return_value=set()),
            patch(
                "bot.command_utils.get_card_wish_counts",
                return_value={"SPG": 1, "BAR": 2},
            ),
            patch("bot.command_utils.get_instance_morph", return_value=None),
            patch("bot.command_utils.get_instance_frame", return_value=None),
            patch("bot.command_utils.get_instance_font", return_value=None),
        ):
            await tag_cards_command.callback(ctx, tag_name="safe")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Tag: `safe`"
        assert isinstance(sent_view, SortableCollectionView)
        assert sent_view.message is ctx.send.return_value

    async def test_wish_remove_lists_multiple_name_matches(self) -> None:
        wish_remove_command = _get_group_command(self.bot, "wish", "remove")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.command_utils.remove_card_from_wishlist", return_value=True) as remove_wishlist:
            await wish_remove_command.callback(ctx, "cheddar")

        remove_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist Matches"
        assert "1. (`CHD`) [🧀] **Cheddar**" in sent_embed.description
        assert "2. (`CHJ`) [🧀] **Cheddar Jack**" in sent_embed.description


class CommandsShipTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_ship_defaults_other_user_to_author(self) -> None:
        ship_command = _get_command(self.bot, "ship")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        file_obj = object()

        with (
            patch(
                "bot.commands_social.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ) as resolve_member,
            patch(
                "bot.commands_social.ship_compatibility_percent",
                return_value=84,
            ) as compatibility,
            patch(
                "bot.commands_social.fetch_avatar_image_bytes",
                new=AsyncMock(side_effect=[b"left", b"right"]),
            ) as fetch_avatar,
            patch(
                "bot.commands_social.build_ship_image_file",
                new=AsyncMock(return_value=file_obj),
            ) as build_image,
        ):
            await ship_command.callback(ctx, user="@Target", other_user=None)

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        compatibility.assert_called_once_with(target.id, ctx.author.id)
        assert fetch_avatar.await_count == 2
        fetch_avatar.assert_any_await(ctx.author)
        fetch_avatar.assert_any_await(target)
        build_image.assert_awaited_once_with(
            left_avatar_bytes=b"left",
            right_avatar_bytes=b"right",
            compatibility_percent=84,
        )

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Ship"
        assert "Compatibility: **84%**" in sent_embed.description
        assert sent_embed.image.url == "attachment://ship_result.png"
        assert ctx.send.await_args.kwargs["file"] is file_obj

    async def test_ship_uses_replied_player_when_user_omitted(self) -> None:
        ship_command = _get_command(self.bot, "ship")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        replied_user = _FakeMember(200, "Replied")
        file_obj = object()

        with (
            patch(
                "bot.commands_social.resolve_replied_player_argument",
                new=AsyncMock(return_value=(replied_user, None)),
            ) as resolve_replied,
            patch(
                "bot.commands_social.ship_compatibility_percent",
                return_value=65,
            ),
            patch(
                "bot.commands_social.fetch_avatar_image_bytes",
                new=AsyncMock(side_effect=[b"left", b"right"]),
            ),
            patch(
                "bot.commands_social.build_ship_image_file",
                new=AsyncMock(return_value=file_obj),
            ),
        ):
            await ship_command.callback(ctx, user=None, other_user=None)

        resolve_replied.assert_awaited_once_with(ctx)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert "Left: **Caller**" in sent_embed.description
        assert "Right: **Replied**" in sent_embed.description

    async def test_ship_with_missing_user_and_no_reply_shows_usage(self) -> None:
        ship_command = _get_command(self.bot, "ship")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_social.resolve_replied_player_argument",
            new=AsyncMock(return_value=(None, "Provide a player or reply to that player's message.")),
        ):
            await ship_command.callback(ctx, user=None, other_user=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Ship"
        assert "Usage: `ns ship <user> [other_user]`." in sent_embed.description

    def test_ship_compatibility_percent_is_deterministic_and_order_independent(self) -> None:
        first = ship_compatibility_percent(111, 999)
        second = ship_compatibility_percent(999, 111)
        third = ship_compatibility_percent(111, 999)

        assert first == second
        assert second == third
        assert 0 <= first <= 100


class CommandsFolderTests:
    def setup_method(self) -> None:
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
            "bot.command_utils.list_player_folders",
            return_value=[("vault", "📦", True, 2), ("dump", "🗑️", False, 1)],
        ):
            await folder_list_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Your Folders"
        assert "🔒 📦 `vault` • 2 cards" in sent_embed.description
        assert "`  ` 🗑️ `dump` • 1 card" in sent_embed.description

    async def test_folder_assign_rejects_duplicate_assignment(self) -> None:
        folder_assign_command = _get_group_command(self.bot, "folder", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        selected = (5, "SPG", 1200, "0")
        with (
            patch("bot.command_utils.get_instance_by_code", return_value=selected),
            patch(
                "bot.command_utils.is_instance_assigned_to_folder",
                return_value=True,
            ),
            patch("bot.command_utils.assign_instance_to_folder", return_value=False) as assign_folder,
        ):
            await folder_assign_command.callback(ctx, "vault", "0")

        assign_folder.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Folders"
        assert sent_embed.description == "That card is already assigned to this folder."

    async def test_folder_assign_batch_lists_assigned_cards_on_separate_lines(self) -> None:
        folder_assign_command = _get_group_command(self.bot, "folder", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch(
                "bot.command_utils.is_instance_assigned_to_folder",
                return_value=False,
            ),
            patch("bot.command_utils.assign_instance_to_folder", return_value=(True, None)),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await folder_assign_command.callback(ctx, "vault", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Folders"
        assert sent_embed.description == "Assigned cards to folder `vault`:\ncard zero\ncard one"

    async def test_folder_unassign_batch_lists_removed_cards_on_separate_lines(self) -> None:
        folder_unassign_command = _get_group_command(self.bot, "folder", "unassign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch("bot.command_utils.unassign_instance_from_folder", return_value=True),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await folder_unassign_command.callback(ctx, "vault", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Folders"
        assert sent_embed.description == "Removed cards from folder `vault`:\ncard zero\ncard one"


class CommandsBurnSelectorTests:
    def setup_method(self) -> None:
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
        assert sent_embed.title == "Burn"
        assert sent_embed.description == "Missing value for `t:` selector."

    async def test_burn_supports_folder_selector(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instances_by_folder",
                return_value=[(10, "SPG", 100, "0")],
            ),
            patch(
                "bot.commands_economy.prepare_burn_batch",
                return_value=SimpleNamespace(
                    is_error=False,
                    error_message=None,
                    items=(
                        SimpleNamespace(
                            instance_id=10,
                            card_type_id="SPG",
                            generation=100,
                            card_id="0",
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
            patch("bot.command_utils.get_instance_morph", return_value=None),
            patch("bot.command_utils.get_instance_frame", return_value=None),
            patch("bot.command_utils.get_instance_font", return_value=None),
            patch(
                "bot.commands_economy.embed_image_payload",
                return_value=(None, None),
            ),
        ):
            await burn_command.callback(ctx, "f:vault")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn Confirmation"

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
                card_type_id="SPG",
                generation=100,
                card_id="0",
                value=12,
                base_value=3,
                delta_range=2,
                multiplier=1.5,
            ),
            SimpleNamespace(
                instance_id=11,
                card_type_id="PEN",
                generation=200,
                card_id="1",
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
            patch(
                "bot.command_utils.get_instances_by_tag",
                return_value=[(10, "SPG", 100, "0")],
            ),
            patch(
                "bot.command_utils.get_instance_by_code",
                return_value=(11, "PEN", 200, "1"),
            ),
            patch("bot.commands_economy.prepare_burn_batch", return_value=prepared),
            patch("bot.commands_economy.BurnConfirmView", _FakeBurnView),
        ):
            await burn_command.callback(ctx, "t:safe", "a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Burn Confirmation"
        assert "Cards: **2**" in sent_embed.description
        assert sent_view.kwargs["burn_items"] == [(10, 2), (11, 3)]

    async def test_burn_rejects_card_type_id_targets(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await burn_command.callback(ctx, "SPG")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn"
        assert "Direct burn targets must be card IDs" in sent_embed.description

    async def test_burn_rejects_card_selector_with_card_type_id(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await burn_command.callback(ctx, "card", "SPG")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn"
        assert "Direct burn targets must be card IDs" in sent_embed.description


class CommandsTeamTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_team_assign_batch_lists_assigned_cards_on_separate_lines(self) -> None:
        team_assign_command = _get_group_command(self.bot, "team", "assign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch("bot.command_utils.is_instance_assigned_to_team", return_value=False),
            patch("bot.command_utils.assign_instance_to_team", return_value=(True, None)),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await team_assign_command.callback(ctx, "alpha", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Teams"
        assert sent_embed.description == "Assigned cards to team `alpha`:\ncard zero\ncard one"

    async def test_team_unassign_batch_lists_removed_cards_on_separate_lines(self) -> None:
        team_unassign_command = _get_group_command(self.bot, "team", "unassign")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.get_instance_by_code",
                side_effect=[
                    (5, "SPG", 1200, "0"),
                    (6, "SPG", 1201, "1"),
                ],
            ),
            patch("bot.command_utils.unassign_instance_from_team", return_value=True),
            patch(
                "bot.command_utils._instance_dupe_display",
                side_effect=["card zero", "card one"],
            ),
        ):
            await team_unassign_command.callback(ctx, "alpha", "0", "1")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Teams"
        assert sent_embed.description == "Removed cards from team `alpha`:\ncard zero\ncard one"

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
            patch(
                "bot.command_utils.get_instances_by_team",
                return_value=team_instances,
            ),
            patch("bot.command_utils.get_locked_instance_ids", return_value=set()),
            patch(
                "bot.command_utils.get_card_wish_counts",
                return_value={"SPG": 1, "BAR": 2},
            ),
            patch("bot.command_utils.get_instance_morph", return_value=None),
            patch("bot.command_utils.get_instance_frame", return_value=None),
            patch("bot.command_utils.get_instance_font", return_value=None),
        ):
            await team_cards_command.callback(ctx, team_name="alpha")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Team: `alpha`"
        assert isinstance(sent_view, SortableCollectionView)
        assert sent_view.message is ctx.send.return_value


class CommandsAliasRegistrationTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    def test_requested_aliases_exist(self) -> None:
        assert _get_command(self.bot, "wa") is not None
        assert _get_command(self.bot, "wr") is not None
        assert _get_command(self.bot, "wl") is not None
        assert "m" in _get_command(self.bot, "marry").aliases
        assert "dv" in _get_command(self.bot, "divorce").aliases
        assert "t" in _get_command(self.bot, "trade").aliases
        assert "b" in _get_command(self.bot, "burn").aliases
        assert "mo" in _get_command(self.bot, "morph").aliases
        assert "fr" in _get_command(self.bot, "frame").aliases
        assert "fo" in _get_command(self.bot, "font").aliases
        cooldown_command = _get_command(self.bot, "cooldown")
        assert "cd" in cooldown_command.aliases
        assert "d" in _get_command(self.bot, "drop").aliases
        assert "h" in _get_command(self.bot, "help").aliases
        assert "ty" in _get_command(self.bot, "types").aliases
        assert "ca" in _get_command(self.bot, "cards").aliases
        assert "l" in _get_command(self.bot, "lookup").aliases
        assert "lhd" in _get_command(self.bot, "lookuphd").aliases
        assert "c" in _get_command(self.bot, "collection").aliases
        assert "le" in _get_command(self.bot, "leaderboard").aliases
        assert "i" in _get_command(self.bot, "info").aliases
        assert "v" in _get_command(self.bot, "vote").aliases
        assert "sl" in _get_command(self.bot, "slots").aliases
        assert "f" in _get_command(self.bot, "flip").aliases
        assert "g" in _get_command(self.bot, "gift").aliases
        assert _get_command(self.bot, "oven") is not None
        assert _get_command(self.bot, "deposit") is not None
        assert _get_command(self.bot, "withdraw") is not None
        assert "tg" in _get_command(self.bot, "tag").aliases
        assert "fd" in _get_command(self.bot, "folder").aliases
        assert "as" in _get_group_command(self.bot, "tag", "assign").aliases
        assert "as" in _get_group_command(self.bot, "folder", "assign").aliases
        assert "as" in _get_group_command(self.bot, "team", "assign").aliases


class CommandsLeaderboardTests:
    def setup_method(self) -> None:
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
        with patch(
            "bot.commands_social.get_player_leaderboard_info",
            return_value=leaderboard_rows,
        ):
            await leaderboard_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Leaderboard"
        assert isinstance(sent_view, PlayerLeaderboardView)
        assert sent_view.message is ctx.send.return_value


class CommandsHelpTests:
    def setup_method(self) -> None:
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
        assert sent_embed.title == "Help"
        assert "Noodswap" in sent_embed.description
        assert isinstance(sent_view, HelpView)
        assert sent_view.message is ctx.send.return_value


class CommandsLookupTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_lookup_rejects_unknown_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_type_id="zzz")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Lookup"
        assert sent_embed.description == "No results found."

    async def test_lookup_shows_usage_when_missing_argument(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_type_id=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Lookup"
        assert sent_embed.description == "Usage: `ns lookup <card_type_id|card_id|query>`."

    async def test_lookup_shows_card_type_embed(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_type_id="spg")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "(`SPG`)" in sent_embed.description

    async def test_lookup_shows_card_embed_for_exact_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.get_instance_by_card_id",
            return_value=(123, 999, "SPG", 101, "abc", 222, 333, 1_700_000_000.0),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_type_id="AbC")

        lookup_dupe.assert_called_once_with(1, "AbC")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "`#abc`" in sent_embed.description
        assert "Owned by: <@999>" in sent_embed.description
        assert "Dropped by: <@222>" in sent_embed.description
        assert "Pulled by: <@333>" in sent_embed.description
        assert "Time pulled: <t:" in sent_embed.description
        assert "G-101" in sent_embed.description
        assert "dough" in sent_embed.description
        assert "**Value Breakdown**" in sent_embed.description
        assert "Trait Multiplier" in sent_embed.description
        assert re.search(r"HP: \*\*\d+\*\* • ATK: \*\*\d+\*\* • DEF: \*\*\d+\*\*", sent_embed.description)

    async def test_lookup_shows_card_embed_for_hash_prefixed_card_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.get_instance_by_card_id",
            return_value=(123, 999, "SPG", 101, "abc", None, None, None),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_type_id="#AbC")

        lookup_dupe.assert_called_once_with(1, "#AbC")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "`#abc`" in sent_embed.description
        assert "Owned by: <@999>" in sent_embed.description
        assert "Dropped by: Unknown" in sent_embed.description
        assert "Pulled by: Unknown" in sent_embed.description
        assert "Time pulled: Unknown" in sent_embed.description
        assert "G-101" in sent_embed.description
        assert "dough" in sent_embed.description
        assert "**Value Breakdown**" in sent_embed.description
        assert re.search(r"HP: \*\*\d+\*\* • ATK: \*\*\d+\*\* • DEF: \*\*\d+\*\*", sent_embed.description)

    async def test_lookuphd_shows_card_embed_with_stats_for_exact_card_id(
        self,
    ) -> None:
        lookup_command = _get_command(self.bot, "lookuphd")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.get_instance_by_card_id",
            return_value=(123, 999, "SPG", 101, "abc", 222, 333, 1_700_000_000.0),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_type_id="AbC")

        lookup_dupe.assert_called_once_with(1, "AbC")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup (HD)"
        assert "`#abc`" in sent_embed.description
        assert "Owned by: <@999>" in sent_embed.description
        assert "Dropped by: <@222>" in sent_embed.description
        assert "Pulled by: <@333>" in sent_embed.description
        assert "Time pulled: <t:" in sent_embed.description
        assert re.search(r"HP: \*\*\d+\*\* • ATK: \*\*\d+\*\* • DEF: \*\*\d+\*\*", sent_embed.description)

    async def test_lookup_prefers_exact_owned_card_id_over_card_type_id(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.get_instance_by_card_id",
            return_value=(777, 999, "SPG", 88, "spg", 999, 111, 1_700_000_000.0),
        ) as lookup_dupe:
            await lookup_command.callback(ctx, card_type_id="spg")

        lookup_dupe.assert_called_once_with(1, "spg")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "`#spg`" in sent_embed.description
        assert "Owned by: <@999>" in sent_embed.description
        assert "Dropped by: <@999>" in sent_embed.description
        assert "Pulled by: <@111>" in sent_embed.description
        assert "dough" in sent_embed.description
        assert "Base:" not in sent_embed.description
        assert "Trait Multiplier" in sent_embed.description

    async def test_lookup_falls_back_to_exact_card_name(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.commands_catalog.search_card_ids", return_value=["SPG"]):
            await lookup_command.callback(ctx, card_type_id="spaghetti")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "(`SPG`)" in sent_embed.description

    async def test_lookup_lists_multiple_name_matches(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_type_id="cheddar")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Lookup Matches"
        assert isinstance(sent_view, SortableCardListView)
        assert "Cheddar" in sent_embed.description
        assert "Cheddar Jack" in sent_embed.description
        assert "Sort: Alphabetical" in sent_embed.footer.text

    async def test_lookup_lists_matches_for_series_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        await lookup_command.callback(ctx, card_type_id="cheese")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Lookup Matches"
        assert isinstance(sent_view, SortableCardListView)
        assert "1." in sent_embed.description
        assert sent_embed.footer.text.startswith("Page 1/")
        assert "Sort: Alphabetical" in sent_embed.footer.text
        assert sent_view.total_pages > 1

    async def test_lookup_unknown_card_id_falls_back_to_search_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.commands_catalog.search_card_ids", return_value=["SPG"]) as search_cards:
            await lookup_command.callback(ctx, card_type_id="spicy noodle")

        search_cards.assert_called_once_with("spicy noodle", include_series=True)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup"
        assert "(`SPG`)" in sent_embed.description

    async def test_lookuphd_requests_hd_render_size(self) -> None:
        lookup_command = _get_command(self.bot, "lookuphd")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.embed_image_payload",
            return_value=("attachment://spg_card.png", None),
        ) as embed_payload:
            await lookup_command.callback(ctx, card_type_id="spg")

        embed_payload.assert_called_once()
        assert embed_payload.call_args.kwargs["size"] == HD_CARD_RENDER_SIZE
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Card Lookup (HD)"


class CommandsCollectionTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_collection_defaults_to_author_when_player_omitted(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch("bot.commands_economy.get_player_card_instances_with_pulled_at", return_value=[]):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Caller's Collection"
        assert sent_embed.description == "Your collection is empty. Try `ns drop`."

    async def test_collection_uses_resolved_player_when_argument_provided(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ) as resolve_member,
            patch("bot.commands_economy.get_player_card_instances_with_pulled_at", return_value=[]),
        ):
            await collection_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Target's Collection"
        assert sent_embed.description == "Target has an empty collection."

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

        with patch("bot.commands_economy.get_player_card_instances_with_pulled_at", return_value=[]):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Target's Collection"
        assert sent_embed.description == "Target has an empty collection."

    async def test_collection_sends_error_when_player_resolution_fails(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("bot.commands_economy.get_player_card_instances_with_pulled_at", return_value=[]),
        ):
            await collection_command.callback(ctx, player="ghost")

        resolve_member.assert_awaited_once_with(ctx, "ghost")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Collection"
        assert sent_embed.description == "Could not find that player."

    async def test_collection_lists_each_instance_separately(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        instances = [
            (3, "SPG", 100, "0", 1_700_000_100.0),
            (4, "SPG", 100, "1", 1_700_000_200.0),
            (5, "SPG", 90, "2", 1_700_000_300.0),
        ]
        with (
            patch(
                "bot.commands_economy.get_player_card_instances_with_pulled_at",
                return_value=instances,
            ),
            patch("bot.command_utils.get_locked_instance_ids", return_value=set()),
        ):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Caller's Collection"
        assert sent_embed.description.count("Spaghetti") == 3
        assert "×" not in sent_embed.description
        assert "#" in sent_embed.description

    async def test_collection_uses_pagination_view_for_multi_page_results(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        instances = [(idx, "SPG", 100 + idx, str(idx), float(1_700_000_000 + idx)) for idx in range(1, 13)]
        with (
            patch(
                "bot.commands_economy.get_player_card_instances_with_pulled_at",
                return_value=instances,
            ),
            patch("bot.command_utils.get_locked_instance_ids", return_value=set()),
        ):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        assert "view" in send_kwargs
        assert isinstance(send_kwargs["view"], SortableCollectionView)
        assert send_kwargs["embed"].footer.text == "Page 1/2 • Sort: Time Pulled (Desc)"

    async def test_cards_shows_empty_state_when_no_cards(self) -> None:
        cards_command = _get_command(self.bot, "cards")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        empty_instances: list = []
        with patch(
            "bot.commands_economy.get_all_owned_card_instances_with_pulled_at",
            return_value=empty_instances,
        ):
            await cards_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "All Cards"
        assert sent_embed.description == "No cards have been claimed yet. Try `ns drop`."

    async def test_cards_lists_all_owned_instances_without_owner_details(self) -> None:
        cards_command = _get_command(self.bot, "cards")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(
            1,
            members={
                100: _FakeMember(100, "Caller"),
                200: _FakeMember(200, "Friend"),
            },
        )
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        instances = [
            (1, 100, "SPG", 100, "0", 1_700_000_100.0, None, None, None),
            (2, 200, "SPG", 101, "1", 1_700_000_200.0, None, None, None),
            (3, 200, "BAR", 200, "2", 1_700_000_300.0, None, None, None),
            (4, 300, "PEN", 300, "3", 1_700_000_400.0, None, None, None),
        ]
        with (
            patch(
                "bot.commands_economy.get_all_owned_card_instances_with_pulled_at",
                return_value=instances,
            ),
            patch("bot.commands_economy.get_card_wish_counts", return_value={"SPG": 3, "PEN": 1}),
        ):
            await cards_command.callback(ctx)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        sent_embed = send_kwargs["embed"]
        sent_view = send_kwargs["view"]
        assert sent_embed.title == "All Cards"
        assert sent_embed.description.count("Spaghetti") == 2
        assert sent_embed.description.count("Penne") == 1
        assert sent_embed.description.count("Barolo") == 1
        assert "Owner:" not in sent_embed.description
        assert "<@100>" not in sent_embed.description
        assert "<@200>" not in sent_embed.description
        assert "<@300>" not in sent_embed.description
        assert isinstance(sent_view, SortableCollectionView)
        assert sent_embed.footer.text == "Page 1/1 • Sort: Time Pulled (Desc)"

    async def test_cards_populates_lock_and_folder_markers_by_instance_owner(self) -> None:
        cards_command = _get_command(self.bot, "cards")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(
            1,
            members={
                100: _FakeMember(100, "Caller"),
                200: _FakeMember(200, "Friend"),
            },
        )
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=SimpleNamespace())
        ctx.reply = ctx.send

        instances = [
            (1, 100, "BAR", 200, "0", 1_700_000_100.0, None, None, None),
            (2, 100, "PEN", 300, "1", 1_700_000_200.0, None, None, None),
            (3, 200, "SPG", 100, "2", 1_700_000_300.0, None, None, None),
        ]

        def _locked_instances_for_owner(_guild_id: int, owner_id: int, instance_ids: list[int]) -> set[int]:
            assert _guild_id == 1
            if owner_id == 100:
                assert instance_ids == [1, 2]
                return {1}
            if owner_id == 200:
                assert instance_ids == [3]
                return {3}
            raise AssertionError(f"Unexpected owner id: {owner_id}")

        def _folder_emojis_for_owner(_guild_id: int, owner_id: int, instance_ids: list[int]) -> dict[int, str]:
            assert _guild_id == 1
            if owner_id == 100:
                assert instance_ids == [1, 2]
                return {2: "📦"}
            if owner_id == 200:
                assert instance_ids == [3]
                return {3: "🔥"}
            raise AssertionError(f"Unexpected owner id: {owner_id}")

        with (
            patch(
                "bot.commands_economy.get_all_owned_card_instances_with_pulled_at",
                return_value=instances,
            ),
            patch("bot.commands_economy.get_card_wish_counts", return_value={}),
            patch(
                "bot.commands_economy.get_locked_instance_ids",
                side_effect=_locked_instances_for_owner,
            ) as get_locked,
            patch(
                "bot.commands_economy.get_folder_emojis_for_instances",
                side_effect=_folder_emojis_for_owner,
            ) as get_folder_emojis,
        ):
            await cards_command.callback(ctx)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        sent_embed = send_kwargs["embed"]
        sent_view = send_kwargs["view"]
        assert isinstance(sent_view, SortableCollectionView)
        assert sent_view.locked_instance_ids == {1, 3}
        assert sent_view.folder_emojis_by_instance == {2: "📦", 3: "🔥"}
        assert "🔒 " in sent_embed.description
        assert "📦 " in sent_embed.description
        assert "🔥 🔒 " in sent_embed.description
        assert get_locked.call_count == 2
        assert get_folder_emojis.call_count == 2

    async def test_wish_list_uses_pagination_view_for_multi_page_results(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        wishlisted_ids = [
            "SPG",
            "PEN",
            "FUS",
            "CHD",
            "CHJ",
            "BGL",
            "BAG",
            "BOL",
            "PIT",
            "RYE",
            "SOU",
        ]
        with patch("bot.command_utils.get_wishlist_cards", return_value=wishlisted_ids):
            await wish_list_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        assert "view" in send_kwargs
        assert isinstance(send_kwargs["view"], SortableCardListView)
        assert send_kwargs["embed"].footer.text == "Page 1/2 • Sort: Alphabetical (Asc)"

    async def test_wish_list_sends_error_when_player_resolution_fails(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(None, "Could not find that player.")),
            ) as resolve_member,
            patch("bot.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_command.callback(ctx, player="ghost")

        resolve_member.assert_awaited_once_with(ctx, "ghost")
        wish_list_impl.assert_not_awaited()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Wishlist"
        assert sent_embed.description == "Could not find that player."

    async def test_wl_accepts_optional_player_argument(self) -> None:
        wish_list_short = _get_command(self.bot, "wl")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(222, "Target")
        with (
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ) as resolve_member,
            patch("bot.commands_social._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_short.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        wish_list_impl.assert_awaited_once_with(ctx, target)


class CommandsCooldownTests:
    def setup_method(self) -> None:
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
            patch(
                "bot.commands_social.get_player_cooldown_timestamps",
                return_value=(0.0, 0.0),
            ),
            patch("bot.commands_social.get_player_slots_timestamp", return_value=0.0),
            patch("bot.commands_social.get_player_flip_timestamp", return_value=0.0),
            patch("bot.commands_gambling.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Caller's Cooldowns"
        assert "Drop:" in sent_embed.description
        assert "Pull:" in sent_embed.description
        assert "Slots:" in sent_embed.description
        assert "Flip:" in sent_embed.description
        assert "Ready" in sent_embed.description

    async def test_cooldown_uses_resolved_player_when_argument_provided(self) -> None:
        cooldown_command = _get_command(self.bot, "cooldown")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(222, "Target")
        with (
            patch(
                "bot.command_utils.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ) as resolve_member,
            patch(
                "bot.commands_social.get_player_cooldown_timestamps",
                return_value=(9_800.0, 9_850.0),
            ),
            patch(
                "bot.commands_social.get_player_slots_timestamp",
                return_value=9_950.0,
            ),
            patch(
                "bot.commands_social.get_player_flip_timestamp",
                return_value=9_980.0,
            ),
            patch("bot.commands_gambling.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Target's Cooldowns"


class CommandsBuyTests:
    def setup_method(self) -> None:
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
        assert sent_embed.title == "Buy"
        assert "ns buy drop" in sent_embed.description

    async def test_buy_drop_purchases_with_starter(self) -> None:
        buy_drop_command = _get_group_command(self.bot, "buy", "drop")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.buy_drop_tickets_with_starter",
            return_value=(True, 4, 7, 3),
        ) as buy_tickets:
            await buy_drop_command.callback(ctx, quantity=3)

        buy_tickets.assert_called_once_with(1, 100, 3)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Buy"
        assert "Purchased: **3 drop tickets**" in sent_embed.description
        assert "Starter: **4**" in sent_embed.description
        assert "Drop Tickets: **7**" in sent_embed.description

    async def test_buy_pull_purchases_with_starter(self) -> None:
        buy_pull_command = _get_group_command(self.bot, "buy", "pull")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.buy_pull_tickets_with_starter",
            return_value=(True, 4, 8, 3),
        ) as buy_tickets:
            await buy_pull_command.callback(ctx, quantity=3)

        buy_tickets.assert_called_once_with(1, 100, 3)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Buy"
        assert "Purchased: **3 pull tickets**" in sent_embed.description
        assert "Starter: **4**" in sent_embed.description
        assert "Pull Tickets: **8**" in sent_embed.description


class CommandsDropTests:
    def setup_method(self) -> None:
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
            patch("bot.commands_economy.prepare_drop", return_value=prepared),
            patch(
                "bot.commands_economy.build_drop_preview_file",
                new=AsyncMock(return_value=None),
            ),
            patch("bot.commands_economy.DropView") as drop_view_cls,
        ):
            view = SimpleNamespace(message=None)
            drop_view_cls.return_value = view
            await drop_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert "drop ticket used" in sent_embed.footer.text

    async def test_drop_rejects_when_in_flight(self) -> None:
        drop_command = _get_command(self.bot, "drop")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_economy.command_execution_gate",
                side_effect=lambda *_args, **_kwargs: _gate_result(False),
            ),
            patch("bot.commands_economy.prepare_drop") as prepare_drop,
        ):
            await drop_command.callback(ctx)

        prepare_drop.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Drop"
        assert "already in progress" in sent_embed.description


class CommandsCooldownReplyTargetTests:
    def setup_method(self) -> None:
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
            patch(
                "bot.commands_social.get_player_cooldown_timestamps",
                return_value=(9_800.0, 9_850.0),
            ),
            patch(
                "bot.commands_social.get_player_slots_timestamp",
                return_value=9_950.0,
            ),
            patch(
                "bot.commands_social.get_player_flip_timestamp",
                return_value=9_980.0,
            ),
            patch("bot.commands_gambling.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Target's Cooldowns"


class CommandsSlotsTests:
    def setup_method(self) -> None:
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
            patch(
                "bot.commands_gambling.consume_slots_cooldown_if_ready",
                return_value=60.0,
            ),
            patch("bot.commands_gambling.add_dough") as add_dough,
            patch("bot.commands_gambling.add_starter") as add_starter,
            patch("bot.commands_gambling._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_dough.assert_not_called()
        add_starter.assert_not_called()
        animate.assert_not_awaited()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Slots Cooldown"
        assert "remaining" in sent_embed.description

    async def test_slots_rejects_when_in_flight(self) -> None:
        slots_command = _get_command(self.bot, "slots")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_gambling.command_execution_gate",
                side_effect=lambda *_args, **_kwargs: _gate_result(False),
            ),
            patch("bot.commands_gambling.consume_slots_cooldown_if_ready") as consume,
        ):
            await slots_command.callback(ctx)

        consume.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Slots"
        assert "already in progress" in sent_embed.description

    async def test_slots_awards_dough_on_two_match(self) -> None:
        slots_command = _get_command(self.bot, "slots")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_gambling.consume_slots_cooldown_if_ready",
                return_value=0.0,
            ),
            patch(
                "bot.commands_gambling.random.choice",
                side_effect=["🍞", "🍞", "🍷", "🍝", "🧀", "🍇"],
            ),
            patch("bot.commands_gambling.random.randint", return_value=250),
            patch("bot.commands_gambling.add_dough") as add_dough,
            patch(
                "bot.commands_gambling.get_player_info",
                return_value=(4250, 0.0, None),
            ),
            patch("bot.commands_gambling.add_starter") as add_starter,
            patch("bot.commands_gambling._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_dough.assert_called_once_with(1, 100, 250)
        add_starter.assert_not_called()
        animate.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        assert final_embed.title == "Slots"
        assert "Two matched" in final_embed.description
        assert "+250 dough" in final_embed.description
        assert "4250" in final_embed.description

    async def test_slots_awards_dough_and_starter_on_three_match(self) -> None:
        slots_command = _get_command(self.bot, "slots")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_gambling.consume_slots_cooldown_if_ready",
                return_value=0.0,
            ),
            patch("bot.commands_gambling.random.choice", return_value="🍞"),
            patch("bot.commands_gambling.random.randint", side_effect=[900, 2]),
            patch("bot.commands_gambling.add_dough") as add_dough,
            patch(
                "bot.commands_gambling.get_player_info",
                return_value=(4900, 0.0, None),
            ),
            patch("bot.commands_gambling.add_starter", return_value=7) as add_starter,
            patch("bot.commands_gambling._animate_slots_spin", new=AsyncMock()) as animate,
        ):
            await slots_command.callback(ctx)

        add_dough.assert_called_once_with(1, 100, 900)
        add_starter.assert_called_once_with(1, 100, 2)
        animate.assert_awaited_once()
        assert message.edit.await_count >= 1
        final_embed = message.edit.await_args.kwargs["embed"]
        assert final_embed.title == "Slots"
        assert "Jackpot" in final_embed.description
        assert "+900 dough" in final_embed.description
        assert "+2 starter" in final_embed.description


class CommandsFlipTests:
    def setup_method(self) -> None:
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
        assert sent_embed.title == "Flip"
        assert "positive integer" in sent_embed.description

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
        assert sent_embed.title == "Flip"
        assert "heads" in sent_embed.description
        assert "tails" in sent_embed.description

    async def test_flip_shows_cooldown_message(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_gambling.execute_flip_wager",
            return_value=("cooldown", 30.0, 50),
        ):
            await flip_command.callback(ctx, stake_str="10")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Flip Cooldown"
        assert "remaining" in sent_embed.description

    async def test_flip_rejects_when_in_flight(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_gambling.command_execution_gate",
                side_effect=lambda *_args, **_kwargs: _gate_result(False),
            ),
            patch("bot.commands_gambling.execute_flip_wager") as execute_flip,
        ):
            await flip_command.callback(ctx, stake_str="10")

        execute_flip.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Flip"
        assert "already in progress" in sent_embed.description

    async def test_flip_shows_insufficient_dough_message(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_gambling.execute_flip_wager",
            return_value=("insufficient_dough", 0.0, 5),
        ):
            await flip_command.callback(ctx, stake_str="10")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Flip"
        assert "do not have enough dough" in sent_embed.description
        assert "Balance: **5**" in sent_embed.description

    async def test_flip_shows_heads_on_win_after_delay(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("bot.commands_gambling.random.random", return_value=0.1),
            patch("bot.commands_gambling.random.choice", return_value="rolling"),
            patch(
                "bot.commands_gambling.execute_flip_wager",
                return_value=("won", 0.0, 68),
            ) as execute_flip,
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await flip_command.callback(ctx, stake_str="10")

        execute_flip.assert_called_once()
        ctx.send.assert_awaited_once()
        first_embed = ctx.send.await_args.kwargs["embed"]
        assert first_embed.title == "Flip"
        assert "coin is" in first_embed.description
        assert "Result" not in first_embed.description
        sleep_mock.assert_awaited_once_with(3.0)

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        assert "Heads" in final_embed.description
        assert "+7" in final_embed.description

    async def test_flip_shows_tails_on_loss_after_delay(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("bot.commands_gambling.random.random", return_value=0.9),
            patch("bot.commands_gambling.random.choice", return_value="spinning"),
            patch(
                "bot.commands_gambling.execute_flip_wager",
                return_value=("lost", 0.0, 40),
            ) as execute_flip,
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await flip_command.callback(ctx, stake_str="10")

        execute_flip.assert_called_once()
        ctx.send.assert_awaited_once()
        first_embed = ctx.send.await_args.kwargs["embed"]
        assert "coin is" in first_embed.description
        sleep_mock.assert_awaited_once_with(3.0)

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        assert "Tails" in final_embed.description
        assert "-10" in final_embed.description

    async def test_flip_respects_heads_call_illusion(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("bot.commands_gambling.random.random", return_value=0.1),
            patch("bot.commands_gambling.random.choice", return_value="whirling"),
            patch(
                "bot.commands_gambling.execute_flip_wager",
                return_value=("won", 0.0, 68),
            ),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()),
        ):
            await flip_command.callback(ctx, stake_str="10", side_str="heads")

        first_embed = ctx.send.await_args.kwargs["embed"]
        assert "Call: **Heads**" in first_embed.description
        final_embed = message.edit.await_args.kwargs["embed"]
        assert "Result: **Heads**" in final_embed.description

    async def test_flip_respects_t_alias_call_illusion(self) -> None:
        flip_command = _get_command(self.bot, "flip")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        with (
            patch("bot.commands_gambling.random.random", return_value=0.1),
            patch("bot.commands_gambling.random.choice", return_value="tumbling"),
            patch(
                "bot.commands_gambling.execute_flip_wager",
                return_value=("won", 0.0, 68),
            ),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()),
        ):
            await flip_command.callback(ctx, stake_str="10", side_str="t")

        first_embed = ctx.send.await_args.kwargs["embed"]
        assert "Call: **Tails**" in first_embed.description
        final_embed = message.edit.await_args.kwargs["embed"]
        assert "Result: **Tails**" in final_embed.description


class CommandsSlotsAnimationTests:
    async def test_slots_reel_content_hides_status_emoji_until_result(self) -> None:
        symbols = ["🍞", "🍞", "🍞"]
        assert _slots_reel_content(symbols) == "🍞🍞🍞"
        assert _slots_reel_content(symbols, result_emoji="🎉") == "🍞🍞🍞      🎉"

    async def test_animate_slots_spin_uses_tapered_frame_delays(self) -> None:
        message = AsyncMock()

        with (
            patch("bot.commands_gambling.random.randint", return_value=4),
            patch("bot.commands_gambling.random.choice", return_value="🍞"),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            await _animate_slots_spin(message, ["🍇", "🍝", "🧀"])
        assert message.edit.await_count == 4

        observed_delays = [call.args[0] for call in sleep_mock.await_args_list]
        assert len(observed_delays) == 4
        assert round(abs((observed_delays[0]) - (SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS)), 7) == 0
        assert round(abs((observed_delays[-1]) - (SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS)), 7) == 0
        assert all(left <= right for left, right in zip(observed_delays, observed_delays[1:]))

        intermediate_contents = [call.kwargs["content"] for call in message.edit.await_args_list]
        assert all("✅" not in text and "❌" not in text and "🎉" not in text for text in intermediate_contents)


class CommandsInfoTests:
    def setup_method(self) -> None:
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
            patch(
                "bot.commands_social.get_player_info",
                return_value=(123, 0.0, None),
            ),
            patch("bot.commands_social.get_player_starter", return_value=9),
            patch("bot.commands_social.get_player_drop_tickets", return_value=4),
            patch("bot.commands_social.get_player_pull_tickets", return_value=6),
            patch("bot.commands_social.get_player_oven_balances", return_value=(21, 3, 2, 1)),
            patch("bot.commands_social.get_total_cards", return_value=7),
            patch(
                "bot.commands_social.get_wishlist_cards",
                return_value=["SPG", "PEN", "FUS"],
            ),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        field_values = {field.name: field.value for field in sent_embed.fields}
        assert field_values.get("Cards") == "7"
        assert field_values.get("**Wallet Items**") == "\n".join(
            [
                "- 123 dough",
                "- 9 starter",
                "- 4 drop tickets",
                "- 6 pull tickets",
            ]
        )
        assert field_values.get("**Oven Items**") == "\n".join(
            [
                "- 21 dough",
                "- 3 starter",
                "- 2 drop tickets",
                "- 1 pull tickets",
            ]
        )
        assert field_values.get("Wishes") == "3"

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
            patch(
                "bot.commands_social.get_player_info",
                return_value=(999, 0.0, None),
            ),
            patch("bot.commands_social.get_player_starter", return_value=2),
            patch("bot.commands_social.get_player_drop_tickets", return_value=0),
            patch("bot.commands_social.get_player_pull_tickets", return_value=0),
            patch("bot.commands_social.get_player_oven_balances", return_value=(0, 0, 0, 0)),
            patch("bot.commands_social.get_total_cards", return_value=4),
            patch("bot.commands_social.get_wishlist_cards", return_value=["SPG"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Target's Info"


class CommandsOvenTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_oven_balance_displays_oven_and_wallet(self) -> None:
        oven_balance_command = _get_group_command(self.bot, "oven", "balance")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch("bot.commands_economy.get_player_info", return_value=(300, 0.0, None)),
            patch("bot.commands_economy.get_player_starter", return_value=8),
            patch("bot.commands_economy.get_player_drop_tickets", return_value=7),
            patch("bot.commands_economy.get_player_pull_tickets", return_value=6),
            patch("bot.commands_economy.get_player_oven_balances", return_value=(125, 4, 3, 2)),
        ):
            await oven_balance_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Oven"
        assert "Oven Dough: **125**" in sent_embed.description
        assert "Oven Starter: **4**" in sent_embed.description
        assert "Oven Drop Tickets: **3**" in sent_embed.description
        assert "Oven Pull Tickets: **2**" in sent_embed.description

    async def test_oven_deposit_success_shows_fee_breakdown(self) -> None:
        oven_deposit_command = _get_group_command(self.bot, "oven", "deposit")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_economy.execute_oven_deposit",
            return_value=storage.OvenTransferResult(
                status="ok",
                item="starter",
                amount=100,
                fee=3,
                net_amount=97,
                pot_contribution=1,
                spendable_balance=900,
                oven_balance=97,
            ),
        ):
            await oven_deposit_command.callback(ctx, amount=100, item="starter")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Deposit"
        assert "Fee (3%): **3 starter**" in sent_embed.description
        assert "Moved to Oven: **97 starter**" in sent_embed.description

    async def test_oven_withdraw_rejects_insufficient_oven_balance(self) -> None:
        oven_withdraw_command = _get_group_command(self.bot, "oven", "withdraw")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_economy.execute_oven_withdraw",
            return_value=storage.OvenTransferResult(
                status="insufficient_oven",
                item="pull",
                amount=100,
                fee=8,
                net_amount=92,
                pot_contribution=0,
                spendable_balance=5,
                oven_balance=40,
            ),
        ):
            await oven_withdraw_command.callback(ctx, amount=100, item="pull")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Oven"
        assert "Current oven balance: **40**" in sent_embed.description


class CommandsGiftTests:
    def setup_method(self) -> None:
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
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(bot_target, None)),
            ),
            patch("bot.commands_economy.execute_gift_card") as gift_card,
        ):
            await gift_card_command.callback(ctx, player="@BotTarget", card_id="0")

        gift_card.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "cannot gift cards to bots" in sent_embed.description

    async def test_gift_card_success_sends_immediate_embed(self) -> None:
        gift_card_command = _get_group_command(self.bot, "gift", "card")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ),
            patch(
                "bot.commands_economy.execute_gift_card",
                return_value=(True, "", "SPG", 123, "a"),
            ) as gift_card,
            patch(
                "bot.commands_economy.get_instance_by_code",
                return_value=(10, "SPG", 123, "a"),
            ) as get_instance,
            patch("bot.commands_economy.get_instance_morph", return_value=None),
            patch("bot.commands_economy.get_instance_frame", return_value=None),
            patch("bot.commands_economy.get_instance_font", return_value=None),
            patch(
                "bot.commands_economy.embed_image_payload",
                return_value=("attachment://gift.png", None),
            ),
        ):
            await gift_card_command.callback(ctx, player="@Target", card_id="0")

        gift_card.assert_called_once_with(
            guild_id=1,
            sender_id=100,
            recipient_id=200,
            card_id="0",
        )
        get_instance.assert_called_once_with(1, 200, "a")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "Recipient: <@200>" in sent_embed.description
        assert "Sender: <@100>" in sent_embed.description
        assert "Card:" in sent_embed.description
        assert "view" not in ctx.send.await_args.kwargs
        assert sent_embed.thumbnail.url == "attachment://gift.png"

    async def test_gift_dough_success_updates_balances(self) -> None:
        gift_dough_command = _get_group_command(self.bot, "gift", "dough")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ),
            patch(
                "bot.commands_economy.execute_gift_dough",
                return_value=(True, "", 70, 30),
            ) as gift_dough,
        ):
            await gift_dough_command.callback(ctx, player="@Target", amount=20)

        gift_dough.assert_called_once_with(guild_id=1, sender_id=100, recipient_id=200, amount=20)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "Sent: **20** dough" in sent_embed.description
        assert "Your Balance: **70** dough" in sent_embed.description
        assert "Target's Balance: **30** dough" in sent_embed.description

    async def test_gift_starter_success_updates_balances(self) -> None:
        gift_starter_command = _get_group_command(self.bot, "gift", "starter")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ),
            patch(
                "bot.commands_economy.execute_gift_starter",
                return_value=(True, "", 9, 4),
            ) as gift_starter,
        ):
            await gift_starter_command.callback(ctx, player="@Target", amount=3)

        gift_starter.assert_called_once_with(guild_id=1, sender_id=100, recipient_id=200, amount=3)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "Sent: **3** starter" in sent_embed.description
        assert "Your Starter: **9**" in sent_embed.description
        assert "Target's Starter: **4**" in sent_embed.description

    async def test_gift_drop_success_updates_balances(self) -> None:
        gift_drop_command = _get_group_command(self.bot, "gift", "drop")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ),
            patch(
                "bot.commands_economy.execute_gift_drop_tickets",
                return_value=(True, "", 6, 2),
            ) as gift_drop,
        ):
            await gift_drop_command.callback(ctx, player="@Target", amount=2)

        gift_drop.assert_called_once_with(guild_id=1, sender_id=100, recipient_id=200, amount=2)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "Sent: **2** drop tickets" in sent_embed.description
        assert "Your Drop Tickets: **6**" in sent_embed.description
        assert "Target's Drop Tickets: **2**" in sent_embed.description

    async def test_gift_pull_success_updates_balances(self) -> None:
        gift_pull_command = _get_group_command(self.bot, "gift", "pull")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        target = _FakeMember(200, "Target")
        with (
            patch(
                "bot.commands_economy.resolve_member_argument",
                new=AsyncMock(return_value=(target, None)),
            ),
            patch(
                "bot.commands_economy.execute_gift_pull_tickets",
                return_value=(True, "", 6, 2),
            ) as gift_pull,
        ):
            await gift_pull_command.callback(ctx, player="@Target", amount=2)

        gift_pull.assert_called_once_with(guild_id=1, sender_id=100, recipient_id=200, amount=2)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Gift"
        assert "Sent: **2** pull tickets" in sent_embed.description
        assert "Your Pull Tickets: **6**" in sent_embed.description
        assert "Target's Pull Tickets: **2**" in sent_embed.description


class CommandsVoteTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_vote_embed_shows_dual_provider_rewards_and_status(self) -> None:
        vote_command = _get_command(self.bot, "vote")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with patch(
            "bot.commands_catalog.get_player_vote_snapshot",
            return_value=(12, 4, True, False, 1_900_000_000),
        ):
            await vote_command.callback(ctx)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        assert sent_embed.title == "Vote for Noodswap"
        assert "Earn rewards and support Noodswap by voting!" in sent_embed.description
        assert "Reward: **+3 starter** and **+500 dough**" in sent_embed.description
        assert "Reward: **+2 drop tickets** and **+1 pull ticket**" in sent_embed.description
        assert "Voted on [Top.gg](https://top.gg/bot/1478727078286196909/vote) yet: ✅" in sent_embed.description
        assert "Voted on [DiscordBotList](https://discordbotlist.com/bots/noodswap/upvote) yet: ❌" in sent_embed.description
        assert "- **Total** Votes: **12**" in sent_embed.description
        assert "- **Monthly** Votes: **4**" in sent_embed.description
        assert isinstance(sent_view, discord.ui.View)
        assert len(sent_view.children) == 2
        assert sent_view.children[0].label == "Vote on Top.gg"
        assert sent_view.children[1].label == "Vote on DiscordBotList"


class CommandsBurnTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_burn_confirmation_embed_shows_card_id(self) -> None:
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
                    card_type_id="SPG",
                    generation=321,
                    card_id="a",
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
            patch(
                "bot.command_utils.get_instance_by_code",
                return_value=(77, "SPG", 321, "a"),
            ),
            patch("bot.commands_economy.prepare_burn_batch", return_value=prepared),
        ):
            await burn_command.callback(ctx, "a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn Confirmation"
        assert "`#a" in sent_embed.description
        assert "`#?`" not in sent_embed.description

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
                    card_type_id="SPG",
                    generation=100,
                    card_id="0",
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
            patch(
                "bot.command_utils.get_instances_by_folder",
                return_value=[(10, "SPG", 100, "0")],
            ),
            patch("bot.commands_economy.prepare_burn_batch", return_value=prepared),
            patch("bot.command_utils.get_instance_morph", return_value=None),
            patch("bot.command_utils.get_instance_frame", return_value=None),
            patch("bot.command_utils.get_instance_font", return_value=None),
            patch(
                "bot.commands_economy.embed_image_payload",
                return_value=(None, None),
            ),
        ):
            await burn_command.callback(ctx, "f:vault")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn Confirmation"

    async def test_burn_reports_when_all_selected_targets_are_skipped(self) -> None:
        burn_command = _get_command(self.bot, "burn")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        prepared = SimpleNamespace(
            is_error=False,
            error_message=None,
            items=(),
            skipped_items=("`0` (locked tag(s): `safe`)",),
            total_value=0,
            total_delta_range=0,
        )

        with (
            patch(
                "bot.command_utils.get_instances_by_tag",
                return_value=[(10, "SPG", 100, "0")],
            ),
            patch("bot.commands_economy.prepare_burn_batch", return_value=prepared),
        ):
            await burn_command.callback(ctx, "t:safe")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Burn Blocked"
        assert "No selected cards can be burned." in sent_embed.description
        assert "locked tag(s)" in sent_embed.description


class CommandsMonopolyTests:
    def setup_method(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_monopoly_roll_mpreg_attaches_thumbnail_file(self) -> None:
        monopoly_roll_command = _get_group_command(self.bot, "monopoly", "roll")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        image_file = discord.File(io.BytesIO(b"png"), filename="mpreg.png")
        result = SimpleNamespace(
            status="ok",
            cooldown_remaining=0.0,
            die_a=1,
            die_b=2,
            position=3,
            in_jail=False,
            doubles=False,
            lines=(
                "Dice: **1 + 2 = 3**",
                "",
                "Mpreg square effect: you gave birth to a dupe.",
            ),
            mpreg_card_type_id="SPG",
            mpreg_generation=321,
            mpreg_card_id="a",
            mpreg_morph_key=None,
            mpreg_frame_key=None,
            mpreg_font_key=None,
        )

        with (
            patch("bot.commands_gambling.execute_monopoly_roll", return_value=result),
            patch("bot.commands_gambling.random.choice", return_value="rolling"),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
            patch(
                "bot.commands_gambling.embed_image_payload",
                return_value=("attachment://mpreg.png", image_file),
            ) as image_payload,
        ):
            await monopoly_roll_command.callback(ctx)

        image_payload.assert_called_once()
        payload_args, payload_kwargs = image_payload.call_args
        assert payload_args == ("SPG", 321)
        assert payload_kwargs["morph_key"] is None
        assert payload_kwargs["frame_key"] is None
        assert payload_kwargs["font_key"] is None
        sleep_mock.assert_awaited_once_with(3.0)

        ctx.send.assert_awaited_once()
        suspense_embed = ctx.send.await_args.kwargs["embed"]
        assert "The dice are" in suspense_embed.description

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        final_attachments = message.edit.await_args.kwargs["attachments"]
        assert final_embed.thumbnail.url == "attachment://mpreg.png"
        assert final_attachments == [image_file]

    async def test_monopoly_roll_rejects_when_in_flight(self) -> None:
        monopoly_roll_command = _get_group_command(self.bot, "monopoly", "roll")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()
        ctx.reply = ctx.send

        with (
            patch(
                "bot.commands_gambling.command_execution_gate",
                side_effect=lambda *_args, **_kwargs: _gate_result(False),
            ),
            patch("bot.commands_gambling.execute_monopoly_roll") as execute_roll,
        ):
            await monopoly_roll_command.callback(ctx)

        execute_roll.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Monopoly Roll"
        assert "already in progress" in sent_embed.description

    async def test_monopoly_roll_uses_generic_thumbnail_metadata(self) -> None:
        monopoly_roll_command = _get_group_command(self.bot, "monopoly", "roll")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        image_file = discord.File(io.BytesIO(b"png"), filename="property.png")
        result = SimpleNamespace(
            status="ok",
            cooldown_remaining=0.0,
            die_a=1,
            die_b=2,
            position=3,
            in_jail=False,
            doubles=False,
            lines=("Dice: **1 + 2 = 3**", "", "Landed on **Sample Card** 🟫"),
            mpreg_card_type_id=None,
            mpreg_card_id=None,
            mpreg_generation=None,
            mpreg_morph_key=None,
            mpreg_frame_key=None,
            mpreg_font_key=None,
            thumbnail_card_id="SPG",
            thumbnail_generation=222,
            thumbnail_morph_key="foil",
            thumbnail_frame_key="gold",
            thumbnail_font_key="papyrus",
        )

        with (
            patch("bot.commands_gambling.execute_monopoly_roll", return_value=result),
            patch("bot.commands_gambling.random.choice", return_value="spinning"),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
            patch(
                "bot.commands_gambling.embed_image_payload",
                return_value=("attachment://property.png", image_file),
            ) as image_payload,
        ):
            await monopoly_roll_command.callback(ctx)

        image_payload.assert_called_once()
        payload_args, payload_kwargs = image_payload.call_args
        assert payload_args == ("SPG", 222)
        assert payload_kwargs["morph_key"] == "foil"
        assert payload_kwargs["frame_key"] == "gold"
        assert payload_kwargs["font_key"] == "papyrus"
        sleep_mock.assert_awaited_once_with(3.0)

        ctx.send.assert_awaited_once()
        suspense_embed = ctx.send.await_args.kwargs["embed"]
        assert "The dice are" in suspense_embed.description

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        final_attachments = message.edit.await_args.kwargs["attachments"]
        assert final_embed.thumbnail.url == "attachment://property.png"
        assert final_attachments == [image_file]

    async def test_monopoly_roll_preserves_property_owner_ping_in_rent_line(self) -> None:
        monopoly_roll_command = _get_group_command(self.bot, "monopoly", "roll")

        message = AsyncMock()
        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock(return_value=message)
        ctx.reply = ctx.send

        image_file = discord.File(io.BytesIO(b"png"), filename="rent.png")
        result = SimpleNamespace(
            status="ok",
            cooldown_remaining=0.0,
            die_a=2,
            die_b=3,
            position=5,
            in_jail=False,
            doubles=False,
            lines=(
                "Dice: **2 + 3 = 5**",
                "",
                "Landed on **Sample Card** 🟫 (#abc123)",
                "Rent paid to <@200>: **50 dough**",
            ),
            mpreg_card_type_id=None,
            mpreg_card_id=None,
            mpreg_generation=None,
            mpreg_morph_key=None,
            mpreg_frame_key=None,
            mpreg_font_key=None,
            thumbnail_card_id="SPG",
            thumbnail_generation=222,
            thumbnail_morph_key=None,
            thumbnail_frame_key=None,
            thumbnail_font_key=None,
        )

        with (
            patch("bot.commands_gambling.execute_monopoly_roll", return_value=result),
            patch("bot.commands_gambling.random.choice", return_value="spinning"),
            patch("bot.commands_gambling.asyncio.sleep", new=AsyncMock()) as sleep_mock,
            patch(
                "bot.commands_gambling.embed_image_payload",
                return_value=("attachment://rent.png", image_file),
            ) as image_payload,
        ):
            await monopoly_roll_command.callback(ctx)

        image_payload.assert_called_once()
        sleep_mock.assert_awaited_once_with(3.0)

        message.edit.assert_awaited_once()
        final_embed = message.edit.await_args.kwargs["embed"]
        assert "Rent paid to <@200>: **50 dough**" in final_embed.description


class CommandsMorphTests:
    def setup_method(self) -> None:
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
            card_type_id="SPG",
            generation=321,
            card_id="a",
            current_morph_key=None,
            cost=9,
        )

        with patch("bot.commands_economy.prepare_morph", return_value=result):
            await morph_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Morph Confirmation"
        assert "Current Morph" in sent_embed.description
        assert "Roll Cost: **9** dough" in sent_embed.description
        assert "view" in ctx.send.await_args.kwargs

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

        with patch("bot.commands_economy.prepare_morph", return_value=result):
            await morph_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Morph"
        assert sent_embed.description == "You do not have enough dough."


class CommandsFrameTests:
    def setup_method(self) -> None:
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
            card_type_id="SPG",
            generation=321,
            card_id="a",
            current_frame_key=None,
            cost=9,
        )

        with patch("bot.commands_economy.prepare_frame", return_value=result):
            await frame_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Frame Confirmation"
        assert "Current Frame" in sent_embed.description
        assert "Roll Cost: **9** dough" in sent_embed.description
        assert "view" in ctx.send.await_args.kwargs

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

        with patch("bot.commands_economy.prepare_frame", return_value=result):
            await frame_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Frame"
        assert sent_embed.description == "You do not have enough dough."


class CommandsFontTests:
    def setup_method(self) -> None:
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
            card_type_id="SPG",
            generation=321,
            card_id="a",
            current_font_key=None,
            cost=9,
        )

        with patch("bot.commands_economy.prepare_font", return_value=result):
            await font_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Font Confirmation"
        assert "Current Font" in sent_embed.description
        assert "Roll Cost: **9** dough" in sent_embed.description
        assert "view" in ctx.send.await_args.kwargs

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

        with patch("bot.commands_economy.prepare_font", return_value=result):
            await font_command.callback(ctx, card_id="a")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        assert sent_embed.title == "Font"
        assert sent_embed.description == "You do not have enough dough."


class DropPreviewRegressionTests:
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

        with patch(
            "bot.images.read_local_card_image_bytes",
            side_effect=[raw_1, raw_2, None],
        ):
            preview = _build_drop_preview_blocking(
                [
                    ("SPG", 1),
                    ("PEN", 2),
                    ("FUS", 3),
                ]
            )
        assert preview is not None
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
        assert pixel_slot_2 != pixel_slot_3

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
        with patch("bot.images.read_local_card_image_bytes", side_effect=[raw, raw, raw]):
            preview = _build_drop_preview_blocking(
                [
                    ("SPG", 1),
                    ("PEN", 2),
                    ("FUS", 3),
                ]
            )
        assert preview is not None
        if preview is None:
            self.fail("Expected drop preview bytes")

        composed = Image.open(io.BytesIO(preview)).convert("RGB")
        card_w, card_h = DEFAULT_CARD_RENDER_SIZE
        gap = 16
        pad = 16
        expected_width = (card_w * 3) + (gap * 2) + (pad * 2)
        expected_height = card_h + (pad * 2)
        assert composed.size == (expected_width, expected_height)

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
        with patch("bot.images.read_local_card_image_bytes", side_effect=[raw, raw, raw]):
            preview = _build_drop_preview_blocking(
                [
                    ("SPG", 1),
                    ("PEN", 2),
                    ("FUS", 3),
                ]
            )
        assert preview is not None
        if preview is None:
            self.fail("Expected drop preview bytes")

        composed = Image.open(io.BytesIO(preview)).convert("RGBA")
        assert composed.getpixel((0, 0)) == (0, 0, 0, 0)


class CardRenderRegressionTests:
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

        with patch(
            "bot.images.read_local_card_image_bytes",
            return_value=png_bytes((220, 30, 30)),
        ):
            rendered = render_card_image_bytes("SPG")
        assert rendered is not None
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGBA")
        assert image.size == DEFAULT_CARD_RENDER_SIZE

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
        assert max(channel_diffs) <= 8

    def test_render_card_image_bytes_applies_bottom_gradient_and_generation_text(
        self,
    ) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(color: tuple[int, int, int]) -> bytes:
            image = Image.new("RGB", (24, 24), color)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with patch(
            "bot.images.read_local_card_image_bytes",
            return_value=png_bytes((50, 50, 50)),
        ):
            rendered_gen_1 = render_card_image_bytes("SPG", generation=1)
            rendered_gen_2 = render_card_image_bytes("SPG", generation=2)
        assert rendered_gen_1 is not None
        assert rendered_gen_2 is not None
        if rendered_gen_1 is None or rendered_gen_2 is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered_gen_1)).convert("RGB")

        bottom_sample = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] - 32))
        upper_sample = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        assert bottom_sample != upper_sample
        assert rendered_gen_1 != rendered_gen_2

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
            patch(
                "bot.images.read_local_card_image_bytes",
                return_value=png_bytes((100, 120, 140)),
            ),
            patch("bot.images._load_frame_image", return_value=overlay),
        ):
            base_rendered = render_card_image_bytes("SPG", generation=10)
            framed_rendered = render_card_image_bytes("SPG", generation=10, frame_key="buttery")
        assert base_rendered is not None
        assert framed_rendered is not None
        if base_rendered is None or framed_rendered is None:
            self.fail("Expected rendered card image bytes")
        assert base_rendered != framed_rendered

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
            patch(
                "bot.images.read_local_card_image_bytes",
                return_value=png_bytes((120, 140, 160)),
            ),
            patch("bot.images._load_frame_image", return_value=transparent_overlay),
        ):
            base_rendered = render_card_image_bytes("SPG", generation=10)
            framed_rendered = render_card_image_bytes("SPG", generation=10, frame_key="buttery")
        assert base_rendered is not None
        assert framed_rendered is not None
        if base_rendered is None or framed_rendered is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base_rendered)).convert("RGBA")
        framed_image = Image.open(io.BytesIO(framed_rendered)).convert("RGBA")

        sample_x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        sample_y = 12
        assert base_image.getpixel((sample_x, sample_y))[3] > 0
        assert framed_image.getpixel((sample_x, sample_y))[3] == 0

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

        with patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()):
            rendered = render_card_image_bytes("SPG", generation=10, morph_key="black_and_white")
        assert rendered is not None
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGB")
        sampled = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        red, green, blue = sampled
        assert abs(red - green) <= 10
        assert abs(green - blue) <= 10

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
            patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch(
                "bot.images._apply_text_legibility_overlay",
                side_effect=lambda img, **_: img,
            ),
        ):
            rendered = render_card_image_bytes("SPG", generation=10, morph_key="inverse")
        assert rendered is not None
        if rendered is None:
            self.fail("Expected rendered card image bytes")

        image = Image.open(io.BytesIO(rendered)).convert("RGB")
        sampled = image.getpixel((DEFAULT_CARD_RENDER_SIZE[0] // 2, DEFAULT_CARD_RENDER_SIZE[1] // 2))
        assert sampled == (215, 145, 75)

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
            patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch(
                "bot.images._apply_text_legibility_overlay",
                side_effect=lambda img, **_: img,
            ),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            tinted = render_card_image_bytes("SPG", generation=10, morph_key="tint_rose")
        assert base is not None
        assert tinted is not None
        if base is None or tinted is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base)).convert("RGB")
        tinted_image = Image.open(io.BytesIO(tinted)).convert("RGB")
        x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        y = DEFAULT_CARD_RENDER_SIZE[1] // 2
        base_r, base_g, base_b = base_image.getpixel((x, y))
        tinted_r, tinted_g, tinted_b = tinted_image.getpixel((x, y))
        assert tinted_r > base_r
        assert tinted_g < base_g
        assert tinted_b < base_b

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
            patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch(
                "bot.images._apply_text_legibility_overlay",
                side_effect=lambda img, **_: img,
            ),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            warm = render_card_image_bytes("SPG", generation=10, morph_key="tint_warm")
        assert base is not None
        assert warm is not None
        if base is None or warm is None:
            self.fail("Expected rendered card image bytes")

        base_image = Image.open(io.BytesIO(base)).convert("RGB")
        warm_image = Image.open(io.BytesIO(warm)).convert("RGB")
        x = DEFAULT_CARD_RENDER_SIZE[0] // 2
        y = DEFAULT_CARD_RENDER_SIZE[1] // 2
        base_r, base_g, base_b = base_image.getpixel((x, y))
        warm_r, warm_g, warm_b = warm_image.getpixel((x, y))
        assert warm_r > base_r
        assert warm_g > base_g
        assert warm_b < base_b

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
            patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch(
                "bot.images._apply_text_legibility_overlay",
                side_effect=lambda img, **_: img,
            ),
        ):
            base = render_card_image_bytes("SPG", generation=10)
            upside_down = render_card_image_bytes("SPG", generation=10, morph_key="upside_down")
        assert base is not None
        assert upside_down is not None
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
        assert flipped_top == base_bottom
        assert flipped_bottom == base_top

    def test_render_card_image_bytes_supports_all_available_morph_keys(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes() -> bytes:
            image = Image.new("RGB", (36, 36), (65, 110, 170))
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()

        with (
            patch("bot.images.read_local_card_image_bytes", return_value=png_bytes()),
            patch(
                "bot.images._apply_text_legibility_overlay",
                side_effect=lambda img, **_: img,
            ),
        ):
            for morph_key in AVAILABLE_MORPHS:
                rendered = render_card_image_bytes("SPG", generation=10, morph_key=morph_key)
                assert rendered is not None, f"Expected rendered bytes for morph {morph_key}"
                if rendered is None:
                    self.fail(f"Expected rendered card image bytes for morph {morph_key}")
                image = Image.open(io.BytesIO(rendered)).convert("RGB")
                assert image.size == DEFAULT_CARD_RENDER_SIZE


class LocalImageBytesTests:
    def test_get_card_image_bytes_returns_local_bytes(self) -> None:
        with patch(
            "bot.command_utils.read_local_card_image_bytes",
            return_value=b"local-bytes",
        ) as read_local:
            resolved = _get_card_image_bytes("SPG")
        assert resolved == b"local-bytes"
        read_local.assert_called_once_with("SPG")

    def test_get_card_image_bytes_returns_none_when_local_missing(self) -> None:
        with patch("bot.command_utils.read_local_card_image_bytes", return_value=None) as read_local:
            resolved = _get_card_image_bytes("SPG")
        assert resolved is None
        read_local.assert_called_once_with("SPG")
