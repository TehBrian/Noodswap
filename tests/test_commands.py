import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from pathlib import Path

import discord
from discord.ext import commands

from noodswap.commands import _build_drop_preview_blocking, _get_card_image_bytes, register_commands
from noodswap.views import PaginatedLinesView


class _FakeGuild:
    def __init__(self, guild_id: int):
        self.id = guild_id


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

        with patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl:
            await wish_list_command.callback(ctx, player=None)

        wish_list_impl.assert_awaited_once_with(ctx, ctx.author)

    async def test_wish_list_uses_resolved_player_when_argument_provided(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        target = _FakeMember(200, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl,
        ):
            await wish_list_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        wish_list_impl.assert_awaited_once_with(ctx, target)

    async def test_wish_add_falls_back_to_exact_card_name(self) -> None:
        wish_add_command = _get_group_command(self.bot, "wish", "add")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        with patch("noodswap.commands.add_card_to_wishlist", return_value=True) as add_wishlist:
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

        with patch("noodswap.commands.add_card_to_wishlist", return_value=True) as add_wishlist:
            await wish_add_command.callback(ctx, card_id="cheddar")

        add_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist Matches")
        self.assertIn("1. **Cheddar**", sent_embed.description)
        self.assertIn("2. **Cheddar Jack**", sent_embed.description)

    async def test_wish_remove_lists_multiple_name_matches(self) -> None:
        wish_remove_command = _get_group_command(self.bot, "wish", "remove")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        with patch("noodswap.commands.remove_card_from_wishlist", return_value=True) as remove_wishlist:
            await wish_remove_command.callback(ctx, card_id="cheddar")

        remove_wishlist.assert_not_called()
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Wishlist Matches")
        self.assertIn("1. **Cheddar**", sent_embed.description)
        self.assertIn("2. **Cheddar Jack**", sent_embed.description)


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
        self.assertIn("cd", _get_command(self.bot, "cooldown").aliases)
        self.assertIn("d", _get_command(self.bot, "drop").aliases)
        self.assertIn("h", _get_command(self.bot, "help").aliases)
        self.assertIn("ca", _get_command(self.bot, "cards").aliases)
        self.assertIn("l", _get_command(self.bot, "lookup").aliases)
        self.assertIn("c", _get_command(self.bot, "collection").aliases)
        self.assertIn("i", _get_command(self.bot, "info").aliases)


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

        await lookup_command.callback(ctx, card_id=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Lookup")
        self.assertEqual(sent_embed.description, "Usage: `ns lookup <card_id|query>`.")

    async def test_lookup_shows_base_card_embed(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        await lookup_command.callback(ctx, card_id="spg")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)

    async def test_lookup_falls_back_to_exact_card_name(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

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

        await lookup_command.callback(ctx, card_id="cheddar")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Lookup Matches")
        self.assertIsInstance(sent_view, PaginatedLinesView)
        self.assertIn("1. **Cheddar**", sent_embed.description)
        self.assertIn("2. **Cheddar Jack**", sent_embed.description)

    async def test_lookup_lists_matches_for_series_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        await lookup_command.callback(ctx, card_id="cheese")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        sent_view = ctx.send.await_args.kwargs["view"]
        self.assertEqual(sent_embed.title, "Lookup Matches")
        self.assertIsInstance(sent_view, PaginatedLinesView)
        self.assertIn("1.", sent_embed.description)
        self.assertTrue(sent_embed.footer.text.startswith("Page 1/"))
        self.assertGreater(sent_view.total_pages, 1)

    async def test_lookup_unknown_card_id_falls_back_to_search_query(self) -> None:
        lookup_command = _get_command(self.bot, "lookup")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        with patch("noodswap.commands.search_card_ids", return_value=["SPG"]) as search_cards:
            await lookup_command.callback(ctx, card_id="spicy noodle")

        search_cards.assert_called_once_with("spicy noodle", include_series=True)
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)


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

    async def test_collection_sends_error_when_player_resolution_fails(self) -> None:
        collection_command = _get_command(self.bot, "collection")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

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

        instances = [
            (3, "SPG", 100, "0"),
            (4, "SPG", 100, "1"),
            (5, "SPG", 90, "2"),
        ]
        with patch("noodswap.commands.get_player_card_instances", return_value=instances):
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

        instances = [(idx, "SPG", 100 + idx, str(idx)) for idx in range(1, 13)]
        with patch("noodswap.commands.get_player_card_instances", return_value=instances):
            await collection_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], PaginatedLinesView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2")

    async def test_wish_list_uses_pagination_view_for_multi_page_results(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        wishlisted_ids = ["SPG", "PEN", "FUS", "CHD", "CHJ", "BGL", "BAG", "BOL", "PIT", "RYE", "SOU"]
        with patch("noodswap.commands.get_wishlist_cards", return_value=wishlisted_ids):
            await wish_list_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        send_kwargs = ctx.send.await_args.kwargs
        self.assertIn("view", send_kwargs)
        self.assertIsInstance(send_kwargs["view"], PaginatedLinesView)
        self.assertEqual(send_kwargs["embed"].footer.text, "Page 1/2")

    async def test_wish_list_sends_error_when_player_resolution_fails(self) -> None:
        wish_list_command = _get_group_command(self.bot, "wish", "list")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

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

        with (
            patch("noodswap.commands.get_player_stats", return_value=(0, 0.0, None)),
            patch("noodswap.commands.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Caller's Drop Cooldown")
        self.assertEqual(sent_embed.description, "Ready now.")

    async def test_cooldown_uses_resolved_player_when_argument_provided(self) -> None:
        cooldown_command = _get_command(self.bot, "cooldown")

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        target = _FakeMember(222, "Target")
        with (
            patch("noodswap.commands.resolve_member_argument", new=AsyncMock(return_value=(target, None))) as resolve_member,
            patch("noodswap.commands.get_player_stats", return_value=(0, 9_800.0, None)),
            patch("noodswap.commands.time.time", return_value=10_000.0),
        ):
            await cooldown_command.callback(ctx, player="@Target")

        resolve_member.assert_awaited_once_with(ctx, "@Target")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Target's Drop Cooldown")
        self.assertIn("Ready in", sent_embed.description)


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

        with (
            patch("noodswap.commands.get_player_stats", return_value=(123, 0.0, None)),
            patch("noodswap.commands.get_total_cards", return_value=7),
            patch("noodswap.commands.get_wishlist_cards", return_value=["SPG", "PEN", "FUS"]),
        ):
            await info_command.callback(ctx, player=None)

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        field_values = {field.name: field.value for field in sent_embed.fields}
        self.assertEqual(field_values.get("Cards"), "7")
        self.assertEqual(field_values.get("Dough"), "123")
        self.assertEqual(field_values.get("Wishes"), "3")


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
        self.assertIn("`#a`", sent_embed.description)
        self.assertNotIn("`#?`", sent_embed.description)


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

        with patch("noodswap.commands._fetch_image_bytes", side_effect=[raw_1, raw_2, None]):
            preview = _build_drop_preview_blocking([
                ("SPG", 1),
                ("PEN", 2),
                ("FUS", 3),
            ])

        self.assertIsNotNone(preview)
        if preview is None:
            self.fail("Expected drop preview bytes")
        composed = Image.open(io.BytesIO(preview)).convert("RGB")

        card_w = 360
        gap = 16
        pad = 16
        y = 120
        x_slot_2 = pad + card_w + gap + (card_w // 2)
        x_slot_3 = pad + (card_w + gap) * 2 + (card_w // 2)

        pixel_slot_2 = composed.getpixel((x_slot_2, y))
        pixel_slot_3 = composed.getpixel((x_slot_3, y))
        self.assertNotEqual(pixel_slot_2, pixel_slot_3)


class LazyImageCacheTests(unittest.TestCase):
    def test_get_card_image_bytes_uses_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manifest_path = cache_dir / "manifest.json"
            image_path = cache_dir / "SPG.jpg"
            image_path.write_bytes(b"cached-bytes")
            manifest_path.write_text(
                json.dumps({"SPG": {"file": "SPG.jpg", "source": "https://example.com/spg.jpg", "attempts": 1}}),
                encoding="utf-8",
            )

            with (
                patch("noodswap.commands.CARD_IMAGE_CACHE_MANIFEST", manifest_path),
                patch("noodswap.commands._fetch_image_bytes", return_value=None) as fetch_mock,
            ):
                resolved = _get_card_image_bytes("SPG")

            self.assertEqual(resolved, b"cached-bytes")
            fetch_mock.assert_not_called()

    def test_get_card_image_bytes_fetches_and_persists_on_miss(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manifest_path = cache_dir / "manifest.json"

            with (
                patch("noodswap.commands.CARD_IMAGE_CACHE_MANIFEST", manifest_path),
                patch("noodswap.commands.card_image_url", return_value="https://example.com/spg.jpg"),
                patch("noodswap.commands._fetch_image_bytes", return_value=b"fresh-bytes") as fetch_mock,
            ):
                resolved = _get_card_image_bytes("SPG")

            self.assertEqual(resolved, b"fresh-bytes")
            fetch_mock.assert_called_once_with("https://example.com/spg.jpg")
            self.assertEqual((cache_dir / "SPG.jpg").read_bytes(), b"fresh-bytes")

            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("SPG", manifest_data)
            self.assertEqual(manifest_data["SPG"]["file"], "SPG.jpg")
            self.assertEqual(manifest_data["SPG"]["source"], "https://example.com/spg.jpg")

if __name__ == "__main__":
    unittest.main()
