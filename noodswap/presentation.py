import discord

from .cards import card_base_display, card_dupe_display
from .utils import multiline_text

ITALY_RED = 0xCE2B37
ITALY_PINK = 0xF4B6C2


def italy_embed(title: str, description: str = "", color: int = ITALY_RED) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def italy_marry_embed(title: str, description: str = "") -> discord.Embed:
    return italy_embed(title=title, description=description, color=ITALY_PINK)


def format_drop_choice_line(card_id: str, generation: int) -> str:
    return card_dupe_display(card_id, generation)


def drop_choices_description(choices: list[tuple[str, int]]) -> str:
    lines = [format_drop_choice_line(card_id, generation) for card_id, generation in choices]
    return f"""Pull one card from this drop:

{multiline_text(lines)}"""


def burn_confirmation_description(
    card_id: str,
    generation: int,
    value: int,
    base_value: int,
    delta_range: int,
    multiplier: float,
) -> str:
    return f"""Burn this card?

{card_dupe_display(card_id, generation)}

Base Value: **{base_value}**
Generation Multiplier: **x{multiplier:.2f}**
Value: **{value}**
Payout: **{value}** ± **{delta_range}**"""



def trade_offer_description(
    offered_to_mention: str,
    seller_mention: str,
    card_id: str,
    generation: int,
    dupe_code: str | None,
    amount: int,
) -> str:
    return (
        f"Offered to: {offered_to_mention}\n"
        f"Seller: {seller_mention}\n"
        f"Card: {card_dupe_display(card_id, generation, dupe_code=dupe_code)}\n"
        "Copy Rule: highest generation number copy\n"
        f"Price: **{amount} dough**"
    )

def help_description() -> str:
    return """Commands:

Overview:
- `ns info [player]` (`ns i`, `ni`) — View a player's stats; defaults to yourself.
- `ns collection [player]` (`ns c`, `nc`) — View a player's cards; defaults to yourself.
- `ns cards` (`ns ca`, `nca`) — View all cards, ranked by wish count.
- `ns lookup <card_id>` (`ns l`, `nl`) — Look up a base card.
- `ns help` (`ns h`, `nh`) — Show this help menu.

Economy:
- `ns drop` (`ns d`, `nd`) — Open a drop with 3 cards and pull 1.
- `ns cooldown [player]` (`ns cd`) — Check a player's drop cooldown; defaults to yourself.
- `ns burn [card_code]` (`ns b`, `nb`) — Burn a card for dough; defaults to last pulled card.
- `ns trade <player> <card_code> <amount>` (`ns t`, `nt`) — Offer a card-for-dough trade.

Wishlist:
- `ns wish` (`ns w`, `nw`) — Wishlist command group.
- `ns wish add <card_id>` (`ns ... a`, `ns wa`, `nwa`) — Add a card to your wishlist.
- `ns wish remove <card_id>` (`ns ... r`, `ns wr`, `nwr`) — Remove a card from your wishlist.
- `ns wish list [player]` (`ns ... l`, `ns wl`, `nwl`) — Show a player's wishlist; defaults to yourself.

Relationship:
- `ns marry [card_code]` (`ns m`, `nm`) — Marry a card; defaults to your last pulled card.
- `ns divorce` (`ns dv`, `ndv`) — End your current marriage.

Owner-only:
- `ns dbexport` — Export the SQLite DB file.
- `ns dbreset` — Reset all persisted bot data."""
