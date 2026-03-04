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
            await ctx.send(
                embed=italy_embed(
                    "Command Error",
                    f"Missing required argument: **{error.param.name}**.",
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
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN in your environment.")

    init_db()
    bot = create_bot()
    bot.run(token)
