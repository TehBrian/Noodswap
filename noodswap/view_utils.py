"""Shared base class and utilities for all interactive discord.ui.View subclasses."""

import logging

import discord

logger = logging.getLogger(__name__)


class InteractionView(discord.ui.View):
    """Base class for interactive views.

    Provides a standardised on_error override that:
    - Logs the exception with full traceback context.
    - Defers the interaction (if not already responded) so Discord does not show
      "This interaction failed" to the user.
    """

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item,  # type: ignore[type-arg]
    ) -> None:
        logger.error(
            "Interaction error in %s (user=%s, item=%s): %s",
            type(self).__name__,
            interaction.user.id,
            type(item).__name__,
            error,
            exc_info=True,
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.HTTPException:
            pass
