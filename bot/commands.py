"""Command registration entrypoint.

This module intentionally stays thin and delegates command setup to
feature-focused registrar modules.
"""

from discord.ext import commands

from .commands_admin import register_admin_commands
from .commands_catalog import register_catalog_commands
from .commands_economy import register_economy_commands
from .commands_gambling import register_gambling_commands
from .commands_social import register_social_commands


def register_commands(bot: commands.Bot) -> None:
    register_social_commands(bot)
    register_catalog_commands(bot)
    register_economy_commands(bot)
    register_gambling_commands(bot)
    register_admin_commands(bot)
