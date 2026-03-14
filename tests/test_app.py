from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock, patch

import discord
from discord.ext import commands

from bot.app import _resolve_command_prefix, create_bot
from bot.presentation import command_syntax_for_error


@pytest.fixture
def prefix_bot() -> commands.Bot:
    return commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)


def test_resolve_prefix_matches_uppercase_long_prefix(prefix_bot: commands.Bot) -> None:
    message = SimpleNamespace(content="Ns help")

    prefixes = _resolve_command_prefix(prefix_bot, message)

    assert "Ns " in prefixes


def test_resolve_prefix_matches_uppercase_short_prefix(prefix_bot: commands.Bot) -> None:
    message = SimpleNamespace(content="Nhelp")

    prefixes = _resolve_command_prefix(prefix_bot, message)

    assert "N" in prefixes


def test_resolve_prefix_ignores_non_prefix_content(prefix_bot: commands.Bot) -> None:
    message = SimpleNamespace(content="hello ns help")

    prefixes = _resolve_command_prefix(prefix_bot, message)

    assert "he" not in prefixes
    assert "hello" not in prefixes


async def test_close_ends_open_battles_before_shutdown() -> None:
    with patch("bot.app.end_open_battles_for_shutdown", return_value=2) as mocked_cleanup:
        bot = create_bot()
        try:
            await bot.close()
        finally:
            if not bot.is_closed():
                await commands.Bot.close(bot)

    mocked_cleanup.assert_called_once_with()


@pytest.fixture
async def error_bot() -> commands.Bot:
    bot = create_bot()
    yield bot
    if not bot.is_closed():
        with patch("bot.app.end_open_battles_for_shutdown", return_value=0):
            await bot.close()


async def test_missing_required_argument_includes_reason_and_usage(error_bot: commands.Bot) -> None:
    ctx = AsyncMock()
    ctx.command = error_bot.get_command("trade")
    ctx.reply = AsyncMock()

    assert ctx.command is not None
    param = ctx.command.clean_params["mode"]
    error = commands.MissingRequiredArgument(param)

    await error_bot.on_command_error(ctx, error)

    ctx.reply.assert_awaited_once()
    sent_embed = ctx.reply.await_args.kwargs["embed"]
    assert sent_embed.title == "Command Error"
    assert "Missing required argument: **mode**." in sent_embed.description
    assert "Usage: `ns trade <player> <card_id> <mode> <amount|card_id>`." in sent_embed.description


async def test_bad_argument_includes_reason_and_subcommand_usage(error_bot: commands.Bot) -> None:
    ctx = AsyncMock()
    buy_group = error_bot.get_command("buy")
    assert buy_group is not None
    ctx.command = buy_group.get_command("drop")
    assert ctx.command is not None
    ctx.reply = AsyncMock()

    error = commands.BadArgument('Converting to "int" failed for parameter "quantity".')

    await error_bot.on_command_error(ctx, error)

    ctx.reply.assert_awaited_once()
    sent_embed = ctx.reply.await_args.kwargs["embed"]
    assert sent_embed.title == "Command Error"
    assert 'Converting to "int" failed for parameter "quantity".' in sent_embed.description
    assert "Usage: `ns buy drop [quantity]`." in sent_embed.description


async def test_too_many_arguments_includes_reason_and_usage(error_bot: commands.Bot) -> None:
    ctx = AsyncMock()
    ctx.command = error_bot.get_command("flip")
    ctx.reply = AsyncMock()

    error = commands.TooManyArguments()

    await error_bot.on_command_error(ctx, error)

    ctx.reply.assert_awaited_once()
    sent_embed = ctx.reply.await_args.kwargs["embed"]
    assert sent_embed.title == "Command Error"
    assert "Too many arguments were provided." in sent_embed.description
    assert "Usage: `ns flip <stake> [heads|tails]`." in sent_embed.description


async def test_on_message_ignores_bot_authors(error_bot: commands.Bot) -> None:
    error_bot.process_commands = AsyncMock()
    message = SimpleNamespace(author=SimpleNamespace(bot=True))

    await error_bot.on_message(message)

    error_bot.process_commands.assert_not_awaited()


async def test_on_message_processes_human_authors(error_bot: commands.Bot) -> None:
    error_bot.process_commands = AsyncMock()
    message = SimpleNamespace(author=SimpleNamespace(bot=False))

    await error_bot.on_message(message)

    error_bot.process_commands.assert_awaited_once_with(message)


def test_all_public_commands_have_curated_error_syntax() -> None:
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

    assert missing_keys == [], f"Missing curated command syntax for: {', '.join(sorted(missing_keys))}"
