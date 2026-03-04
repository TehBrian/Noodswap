import io
import unittest
from unittest.mock import AsyncMock, patch

import discord
from discord.ext import commands

from noodswap.commands import _build_drop_preview_blocking, register_commands


class _FakeGuild:
    def __init__(self, guild_id: int):
        self.id = guild_id


class _FakeMember:
    def __init__(self, user_id: int, display_name: str = "User"):
        self.id = user_id
        self.display_name = display_name
        self.bot = False


class CommandsWishlistTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_wish_list_defaults_to_author_when_player_omitted(self) -> None:
        wish_group = self.bot.get_command("wish")
        self.assertIsNotNone(wish_group)
        wish_list_command = wish_group.get_command("list")
        self.assertIsNotNone(wish_list_command)

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        with patch("noodswap.commands._wish_list", new=AsyncMock()) as wish_list_impl:
            await wish_list_command.callback(ctx, player=None)

        wish_list_impl.assert_awaited_once_with(ctx, ctx.author)

    async def test_wish_list_uses_resolved_player_when_argument_provided(self) -> None:
        wish_group = self.bot.get_command("wish")
        self.assertIsNotNone(wish_group)
        wish_list_command = wish_group.get_command("list")
        self.assertIsNotNone(wish_list_command)

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
        wish_group = self.bot.get_command("wish")
        self.assertIsNotNone(wish_group)
        wish_add_command = wish_group.get_command("add")
        self.assertIsNotNone(wish_add_command)

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

    async def test_wish_remove_lists_multiple_name_matches(self) -> None:
        wish_group = self.bot.get_command("wish")
        self.assertIsNotNone(wish_group)
        wish_remove_command = wish_group.get_command("remove")
        self.assertIsNotNone(wish_remove_command)

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
        self.assertIn("(`CHD`)", sent_embed.description)
        self.assertIn("(`CHJ`)", sent_embed.description)


class CommandsAliasRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    def test_requested_aliases_exist(self) -> None:
        self.assertIsNotNone(self.bot.get_command("wa"))
        self.assertIsNotNone(self.bot.get_command("wr"))
        self.assertIsNotNone(self.bot.get_command("wl"))

        self.assertIn("m", self.bot.get_command("marry").aliases)
        self.assertIn("dv", self.bot.get_command("divorce").aliases)
        self.assertIn("t", self.bot.get_command("trade").aliases)
        self.assertIn("b", self.bot.get_command("burn").aliases)
        self.assertIn("cd", self.bot.get_command("cooldown").aliases)
        self.assertIn("d", self.bot.get_command("drop").aliases)
        self.assertIn("h", self.bot.get_command("help").aliases)
        self.assertIn("ca", self.bot.get_command("cards").aliases)
        self.assertIn("l", self.bot.get_command("lookup").aliases)
        self.assertIn("c", self.bot.get_command("collection").aliases)
        self.assertIn("i", self.bot.get_command("info").aliases)


class CommandsLookupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_lookup_rejects_unknown_card_id(self) -> None:
        lookup_command = self.bot.get_command("lookup")
        self.assertIsNotNone(lookup_command)

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        await lookup_command.callback(ctx, card_id="zzz")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Lookup")
        self.assertEqual(sent_embed.description, "Unknown card id.")

    async def test_lookup_shows_base_card_embed(self) -> None:
        lookup_command = self.bot.get_command("lookup")
        self.assertIsNotNone(lookup_command)

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
        lookup_command = self.bot.get_command("lookup")
        self.assertIsNotNone(lookup_command)

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
        lookup_command = self.bot.get_command("lookup")
        self.assertIsNotNone(lookup_command)

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        await lookup_command.callback(ctx, card_id="cheddar")

        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Lookup Matches")
        self.assertIn("(`CHD`)", sent_embed.description)
        self.assertIn("(`CHJ`)", sent_embed.description)

    async def test_lookup_unknown_card_id_falls_back_to_search_query(self) -> None:
        lookup_command = self.bot.get_command("lookup")
        self.assertIsNotNone(lookup_command)

        ctx = AsyncMock()
        ctx.guild = _FakeGuild(1)
        ctx.author = _FakeMember(100, "Caller")
        ctx.send = AsyncMock()

        with patch("noodswap.commands.search_card_ids_by_name", return_value=["SPG"]) as search_cards:
            await lookup_command.callback(ctx, card_id="spicy noodle")

        search_cards.assert_called_once_with("spicy noodle")
        ctx.send.assert_awaited_once()
        sent_embed = ctx.send.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Card Lookup")
        self.assertIn("(`SPG`)", sent_embed.description)


class CommandsCollectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)
        register_commands(self.bot)

    async def test_collection_defaults_to_author_when_player_omitted(self) -> None:
        collection_command = self.bot.get_command("collection")
        self.assertIsNotNone(collection_command)

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
        collection_command = self.bot.get_command("collection")
        self.assertIsNotNone(collection_command)

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
        collection_command = self.bot.get_command("collection")
        self.assertIsNotNone(collection_command)

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
        collection_command = self.bot.get_command("collection")
        self.assertIsNotNone(collection_command)

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

    async def test_wish_list_sends_error_when_player_resolution_fails(self) -> None:
        wish_group = self.bot.get_command("wish")
        self.assertIsNotNone(wish_group)
        wish_list_command = wish_group.get_command("list")
        self.assertIsNotNone(wish_list_command)

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
        wish_list_short = self.bot.get_command("wl")
        self.assertIsNotNone(wish_list_short)

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
        cooldown_command = self.bot.get_command("cooldown")
        self.assertIsNotNone(cooldown_command)

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
        cooldown_command = self.bot.get_command("cooldown")
        self.assertIsNotNone(cooldown_command)

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
        info_command = self.bot.get_command("info")
        self.assertIsNotNone(info_command)

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

if __name__ == "__main__":
    unittest.main()
