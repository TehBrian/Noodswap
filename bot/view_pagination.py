import discord

from .settings import (
    PAGINATION_FIRST_EMOJI,
    PAGINATION_LAST_EMOJI,
    PAGINATION_NEXT_EMOJI,
    PAGINATION_PREVIOUS_EMOJI,
)


def resolve_pagination_emoji(token: str, fallback: str) -> discord.PartialEmoji | str:
    cleaned = token.strip()
    if not cleaned:
        return fallback

    emoji = discord.PartialEmoji.from_str(cleaned)
    if emoji.id is None and not emoji.name:
        return fallback
    return emoji


FIRST_PAGE_EMOJI = resolve_pagination_emoji(PAGINATION_FIRST_EMOJI, "⏮️")
PREVIOUS_PAGE_EMOJI = resolve_pagination_emoji(PAGINATION_PREVIOUS_EMOJI, "◀️")
NEXT_PAGE_EMOJI = resolve_pagination_emoji(PAGINATION_NEXT_EMOJI, "▶️")
LAST_PAGE_EMOJI = resolve_pagination_emoji(PAGINATION_LAST_EMOJI, "⏭️")
