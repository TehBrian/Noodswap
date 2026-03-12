from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import discord
from discord.ext import commands

from noodswap.app import _resolve_command_prefix, create_bot
from noodswap.presentation import command_syntax_for_error


class AppPrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(
            command_prefix="ns ", intents=discord.Intents.none(), help_command=None
        )

    def test_resolve_prefix_matches_uppercase_long_prefix(self) -> None:
        message = SimpleNamespace(content="Ns help")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertIn("Ns ", prefixes)

    def test_resolve_prefix_matches_uppercase_short_prefix(self) -> None:
        message = SimpleNamespace(content="Nhelp")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertIn("N", prefixes)

    def test_resolve_prefix_ignores_non_prefix_content(self) -> None:
        message = SimpleNamespace(content="hello ns help")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertNotIn("he", prefixes)
        self.assertNotIn("hello", prefixes)


class AppShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_ends_open_battles_before_shutdown(self) -> None:
        with patch(
            "noodswap.app.end_open_battles_for_shutdown", return_value=2
        ) as mocked_cleanup:
            bot = create_bot()
            try:
                await bot.close()
            finally:
                if not bot.is_closed():
                    await commands.Bot.close(bot)

        mocked_cleanup.assert_called_once_with()


class AppCommandErrorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.bot = create_bot()

    async def asyncTearDown(self) -> None:
        if not self.bot.is_closed():
            with patch("noodswap.app.end_open_battles_for_shutdown", return_value=0):
                await self.bot.close()

    async def test_missing_required_argument_includes_reason_and_usage(self) -> None:
        ctx = AsyncMock()
        ctx.command = self.bot.get_command("trade")
        ctx.reply = AsyncMock()

        param = ctx.command.clean_params["mode"]
        error = commands.MissingRequiredArgument(param)

        await self.bot.on_command_error(ctx, error)

        ctx.reply.assert_awaited_once()
        sent_embed = ctx.reply.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Command Error")
        self.assertIn("Missing required argument: **mode**.", sent_embed.description)
        self.assertIn(
            "Usage: `ns trade <player> <card_code> <mode> <amount|card_code>`.",
            sent_embed.description,
        )

    async def test_bad_argument_includes_reason_and_subcommand_usage(self) -> None:
        ctx = AsyncMock()
        buy_group = self.bot.get_command("buy")
        self.assertIsNotNone(buy_group)
        ctx.command = buy_group.get_command("drop")
        ctx.reply = AsyncMock()

        error = commands.BadArgument(
            'Converting to "int" failed for parameter "quantity".'
        )

        await self.bot.on_command_error(ctx, error)

        ctx.reply.assert_awaited_once()
        sent_embed = ctx.reply.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Command Error")
        self.assertIn(
            'Converting to "int" failed for parameter "quantity".',
            sent_embed.description,
        )
        self.assertIn("Usage: `ns buy drop [quantity]`.", sent_embed.description)

    async def test_too_many_arguments_includes_reason_and_usage(self) -> None:
        ctx = AsyncMock()
        ctx.command = self.bot.get_command("flip")
        ctx.reply = AsyncMock()

        error = commands.TooManyArguments()

        await self.bot.on_command_error(ctx, error)

        ctx.reply.assert_awaited_once()
        sent_embed = ctx.reply.await_args.kwargs["embed"]
        self.assertEqual(sent_embed.title, "Command Error")
        self.assertIn("Too many arguments were provided.", sent_embed.description)
        self.assertIn("Usage: `ns flip <stake> [heads|tails]`.", sent_embed.description)


class AppCommandSyntaxCoverageTests(unittest.TestCase):
    def test_all_public_commands_have_curated_error_syntax(self) -> None:
        bot = create_bot()
        missing_keys: list[str] = []
        seen_keys: set[str] = set()

        for command in bot.walk_commands():
            if command.hidden:
                continue
            key = command.qualified_name
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if command_syntax_for_error(key) is None:
                missing_keys.append(key)

        self.assertEqual(
            missing_keys,
            [],
            msg=f"Missing curated command syntax for: {', '.join(sorted(missing_keys))}",
        )
