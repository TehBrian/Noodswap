import os
import logging
import asyncio
import inspect

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]

import discord
from discord.ext import commands

from .commands import register_commands
from .fonts import AVAILABLE_FONTS, font_asset_files
from .presentation import command_syntax_for_error, italy_embed
from .services import end_open_battles_for_shutdown
from .settings import (
    CARD_FONTS_DIR,
    COMMAND_PREFIX,
    SHORT_COMMAND_PREFIX,
    TOPGG_BOT_ID,
    TOPGG_WEBHOOK_ALLOWED_IPS,
    TOPGG_WEBHOOK_HOST,
    TOPGG_WEBHOOK_MAX_BODY_BYTES,
    TOPGG_WEBHOOK_PATH,
    TOPGG_WEBHOOK_PORT,
    TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE,
    TOPGG_WEBHOOK_SECRET,
)
from .storage import init_db
from .topgg_webhook import TopggWebhookConfig, TopggWebhookServer

logger = logging.getLogger(__name__)


def _normalize_secret(value: str) -> str:
    """Trim whitespace and one surrounding quote pair from env/file secrets."""
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


async def _reply(ctx: commands.Context, **kwargs):
    return await ctx.reply(mention_author=False, **kwargs)


def _resolve_command_syntax(ctx: commands.Context) -> str | None:
    if ctx.command is None:
        return None

    keys: list[str] = []
    qualified_name = getattr(ctx.command, "qualified_name", "")
    if qualified_name:
        keys.append(qualified_name)

    name = getattr(ctx.command, "name", "")
    if name and name not in keys:
        keys.append(name)

    for key in keys:
        syntax = command_syntax_for_error(key)
        if syntax:
            return syntax
    return None


def _format_input_error_description(ctx: commands.Context, reason: str) -> str:
    syntax = _resolve_command_syntax(ctx)
    if syntax is None:
        return reason
    return f"{reason}\nUsage: `{syntax}`."


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
    class NoodswapBot(commands.Bot):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._topgg_webhook_server = TopggWebhookServer(
                TopggWebhookConfig(
                    secret=TOPGG_WEBHOOK_SECRET,
                    host=TOPGG_WEBHOOK_HOST,
                    port=TOPGG_WEBHOOK_PORT,
                    path=TOPGG_WEBHOOK_PATH,
                    expected_bot_id=TOPGG_BOT_ID,
                    max_body_bytes=TOPGG_WEBHOOK_MAX_BODY_BYTES,
                    require_json_content_type=TOPGG_WEBHOOK_REQUIRE_JSON_CONTENT_TYPE,
                    allowed_ip_networks=TOPGG_WEBHOOK_ALLOWED_IPS,
                )
            )

        async def setup_hook(self) -> None:
            await self._topgg_webhook_server.start()

        async def close(self) -> None:
            await self._topgg_webhook_server.stop()
            try:
                ended_battles = end_open_battles_for_shutdown()
                if ended_battles > 0:
                    logger.info("Ended %s open battle(s) during shutdown.", ended_battles)
            except Exception:  # pragma: no cover - defensive shutdown path
                logger.exception("Failed to end open battles during shutdown.")
            await super().close()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = NoodswapBot(
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
            description = _format_input_error_description(
                ctx,
                f"Missing required argument: **{error.param.name}**.",
            )
            await _reply(
                ctx,
                embed=italy_embed(
                    "Command Error",
                    description,
                )
            )
            return

        if isinstance(error, commands.TooManyArguments):
            description = _format_input_error_description(
                ctx,
                "Too many arguments were provided.",
            )
            await _reply(ctx, embed=italy_embed("Command Error", description))
            return

        if isinstance(error, commands.BadArgument):
            detail = str(error).strip() or "Invalid argument provided."
            description = _format_input_error_description(ctx, detail)
            await _reply(ctx, embed=italy_embed("Command Error", description))
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
        regular_name, bold_name = font_asset_files(font_key)
        regular_path = CARD_FONTS_DIR / regular_name
        bold_path = CARD_FONTS_DIR / bold_name
        if not regular_path.is_file():
            missing.append(f"{font_key}: {regular_name}")
        if not bold_path.is_file():
            missing.append(f"{font_key}: {bold_name}")

    if missing:
        missing_display = ", ".join(sorted(missing))
        raise RuntimeError(
            "Runtime fonts are incomplete in "
            f"{CARD_FONTS_DIR}. Missing mapped files for: {missing_display}. "
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
