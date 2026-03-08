import os
import logging
import asyncio
import inspect

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]

import discord
from discord.ext import commands

from .commands import register_commands
from .fonts import AVAILABLE_FONTS
from .presentation import italy_embed
from .settings import CARD_FONTS_DIR, COMMAND_PREFIX, SHORT_COMMAND_PREFIX
from .storage import init_db

logger = logging.getLogger(__name__)


def _normalize_secret(value: str) -> str:
    """Trim whitespace and one surrounding quote pair from env/file secrets."""
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


async def _reply(ctx: commands.Context, **kwargs):
    return await ctx.reply(mention_author=False, **kwargs)


def resolve_discord_token() -> str:
    token = os.getenv("DISCORD_TOKEN")
    if token:
        resolved = _normalize_secret(token)
        if resolved and resolved != "replace-with-real-token":
            return resolved
        raise RuntimeError(
            "DISCORD_TOKEN is set but is empty/placeholder after normalization."
        )

    token_file = os.getenv("DISCORD_TOKEN_FILE")
    if token_file:
        token_file_path = _normalize_secret(token_file)
        if not token_file_path:
            raise RuntimeError("DISCORD_TOKEN_FILE is set but empty.")
        try:
            with open(token_file_path, "r", encoding="utf-8") as file:
                token_from_file = file.read().strip()
        except OSError as exc:
            raise RuntimeError(
                "DISCORD_TOKEN_FILE is set but could not be read."
            ) from exc

        resolved = _normalize_secret(token_from_file)
        if resolved and resolved != "replace-with-real-token":
            return resolved

        raise RuntimeError(
            "DISCORD_TOKEN_FILE is set but token content is empty/placeholder after normalization."
        )

    raise RuntimeError("Set DISCORD_TOKEN or DISCORD_TOKEN_FILE in your environment.")


def _resolve_command_prefix(bot: commands.Bot, message: discord.Message) -> list[str]:
    prefixes: list[str] = []
    if bot.user is not None:
        prefixes.extend(commands.when_mentioned(bot, message))
    content = message.content or ""

    # Return the exact prefix slice from the incoming content so mixed-case
    # variants like "Ns " still match while keeping canonical config values.
    for configured in (COMMAND_PREFIX, SHORT_COMMAND_PREFIX):
        candidate = content[: len(configured)]
        if candidate.lower() == configured.lower() and candidate not in prefixes:
            prefixes.append(candidate)

    return prefixes


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(
        command_prefix=_resolve_command_prefix,
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
            message = ctx.message.content.strip().lower()
            if message in {COMMAND_PREFIX.strip().lower(), SHORT_COMMAND_PREFIX.strip().lower()}:
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

            await _reply(
                ctx,
                embed=italy_embed(
                    "Command Error",
                    description,
                )
            )
            return

        if isinstance(error, commands.BadArgument):
            await _reply(ctx, embed=italy_embed("Command Error", "Invalid argument provided."))
            return

        if isinstance(error, commands.CheckFailure):
            await _reply(ctx, embed=italy_embed("Permission", "You are not allowed to run this command."))
            return

        logger.exception("Unhandled command error", exc_info=error)
        await _reply(
            ctx,
            embed=italy_embed(
                "Unexpected Error",
                "Something went wrong while processing that command.",
            )
        )

    register_commands(bot)
    return bot


def _validate_runtime_font_assets() -> None:
    if not CARD_FONTS_DIR.is_dir():
        raise RuntimeError(
            "Font directory is missing: "
            f"{CARD_FONTS_DIR}. Run scripts/init_runtime.py before starting the bot."
        )

    missing: list[str] = []
    for font_key in AVAILABLE_FONTS:
        has_file = any((CARD_FONTS_DIR / f"{font_key}{extension}").is_file() for extension in (".ttf", ".otf", ".ttc"))
        if not has_file:
            missing.append(font_key)

    if missing:
        missing_display = ", ".join(sorted(missing))
        raise RuntimeError(
            "Runtime fonts are incomplete in "
            f"{CARD_FONTS_DIR}. Missing base files for: {missing_display}. "
            "Re-run scripts/init_runtime.py and verify runtime volume permissions."
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = resolve_discord_token()

    _validate_runtime_font_assets()
    init_db()
    bot = create_bot()
    try:
        bot.run(token)
    except discord.LoginFailure as exc:
        raise RuntimeError(
            "Discord token was rejected (401 Unauthorized). "
            "Check deploy/runtime.env DISCORD_TOKEN for typos/rotation, and remove surrounding quotes."
        ) from exc
