import os
import logging
import asyncio
import inspect

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]

import discord
from discord.ext import commands

from .commands import register_commands
from .presentation import italy_embed
from .settings import COMMAND_PREFIX, SHORT_COMMAND_PREFIX
from .storage import init_db

logger = logging.getLogger(__name__)


def resolve_discord_token() -> str:
    token = os.getenv("DISCORD_TOKEN")
    if token:
        return token.strip()

    token_file = os.getenv("DISCORD_TOKEN_FILE")
    if token_file:
        try:
            with open(token_file, "r", encoding="utf-8") as file:
                token_from_file = file.read().strip()
        except OSError as exc:
            raise RuntimeError(
                "DISCORD_TOKEN_FILE is set but could not be read."
            ) from exc

        if token_from_file:
            return token_from_file

        raise RuntimeError("DISCORD_TOKEN_FILE is set but empty.")

    raise RuntimeError("Set DISCORD_TOKEN or DISCORD_TOKEN_FILE in your environment.")


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or(COMMAND_PREFIX, SHORT_COMMAND_PREFIX),
        intents=intents,
        help_command=None,
    )

    @bot.event
    async def on_ready():
        if bot.user is None:
            return
        logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id)

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, commands.CommandNotFound):
            message = ctx.message.content.strip()
            if message in {COMMAND_PREFIX.strip(), SHORT_COMMAND_PREFIX.strip()}:
                help_cmd = bot.get_command("help")
                if help_cmd is not None:
                    await help_cmd(ctx)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            usage_overrides = {
                "lookup": "Usage: `ns lookup <card_id|query>`."
            }
            usage_hint = ""
            if ctx.command is not None:
                usage_hint = usage_overrides.get(ctx.command.name, "")

            description = f"Missing required argument: **{error.param.name}**."
            if usage_hint:
                description = f"{description}\n{usage_hint}"

            await ctx.send(
                embed=italy_embed(
                    "Command Error",
                    description,
                )
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(embed=italy_embed("Command Error", "Invalid argument provided."))
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=italy_embed("Permission", "You are not allowed to run this command."))
            return

        logger.exception("Unhandled command error", exc_info=error)
        await ctx.send(
            embed=italy_embed(
                "Unexpected Error",
                "Something went wrong while processing that command.",
            )
        )

    register_commands(bot)
    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = resolve_discord_token()

    init_db()
    bot = create_bot()
    bot.run(token)
