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
    return f"""{multiline_text(lines)}"""


def burn_confirmation_description(
    card_id: str,
    generation: int,
    dupe_code: str | None,
    value: int,
    base_value: int,
    delta_range: int,
    multiplier: float,
) -> str:
    return f"""Burn this card?

{card_dupe_display(card_id, generation, dupe_code=dupe_code)}

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
    return f"""Offered to: {offered_to_mention}
Seller: {seller_mention}

Card: {card_dupe_display(card_id, generation, dupe_code=dupe_code)}
Price: **{amount}** dough"""

HELP_CATEGORY_PAGES: tuple[tuple[str, str, str], ...] = (
    (
        "overview",
        "Overview",
        """- `ns info [player]` (`ns i`, `ni`) — View a player's stats; defaults to yourself or the replied user.
- `ns leaderboard` (`ns le`, `nle`) — View ranked players with selectable leaderboard criteria.
- `ns collection [player]` (`ns c`, `nc`) — View a player's cards; defaults to yourself or the replied user.
- `ns cards` (`ns ca`, `nca`) — View all cards, ranked by wish count.
- `ns lookup <card_id|card_code|query>` (`ns l`, `nl`) — Look up a base card or exact dupe code.
- `ns lookuphd <card_id|card_code|query>` (`ns lhd`, `nlhd`) — Look up a card with high-detail `1000x1400` rendering.
- `ns help` (`ns h`, `nh`) — Open this help menu.""",
    ),
    (
        "economy",
        "Economy",
        """- `ns drop` (`ns d`, `nd`) — Open a drop with 3 cards and pull 1.
- `ns cooldown [player]` (`ns cd`) — Check a player's cooldowns; defaults to yourself or the replied user.
- `ns vote` (`ns v`, `nv`) — Open top.gg vote link and claim starter reward if your vote is detected.
- `ns burn [card_code]` (`ns b`, `nb`) — Burn a card for dough; defaults to last pulled card.
- `ns trade <player> <card_code> <amount>` (`ns t`, `nt`) — Offer a card-for-dough trade.""",
    ),
    (
        "cosmetics",
        "Cosmetics",
        """- `ns morph [card_code]` (`ns mo`, `nmo`) — Spend dough to apply a random visual morph; defaults to last pulled card.
- `ns frame [card_code]` (`ns fr`, `nfr`) — Spend dough to apply a random cosmetic frame; defaults to last pulled card.
- `ns font [card_code]` (`ns fo`, `nfo`) — Spend dough to apply a random card font; defaults to last pulled card.""",
    ),
    (
        "wishlist",
        "Wishlist",
        """- `ns wish` (`ns w`, `nw`) — Wishlist command group.
- `ns wish add <card_id>` (`ns ... a`, `ns wa`, `nwa`) — Add a card to your wishlist.
- `ns wish remove <card_id>` (`ns ... r`, `ns wr`, `nwr`) — Remove a card from your wishlist.
- `ns wish list [player]` (`ns ... l`, `ns wl`, `nwl`) — Show a player's wishlist; defaults to yourself or the replied user.""",
    ),
    (
        "tags",
        "Tags",
        """- `ns tag` (`ns tg`) — Tag command group.
- `ns tag add <tag_name>` (`ns ... a`) — Create a personal tag collection.
- `ns tag remove <tag_name>` (`ns ... r`) — Delete one of your tags.
- `ns tag list` (`ns ... l`) — List your tags with lock state and card counts.
- `ns tag lock <tag_name>` / `ns tag unlock <tag_name>` — Toggle burn protection for that tag.
- `ns tag assign <tag_name> <card_code>` (`ns ... as`) — Add one of your dupes to a tag.
- `ns tag unassign <tag_name> <card_code>` (`ns ... u`) — Remove a tagged dupe from a tag.
- `ns tag cards <tag_name>` (`ns ... c`) — Show cards currently in that tag.""",
    ),
    (
        "relationship",
        "Relationship",
        """- `ns marry [card_code]` (`ns m`, `nm`) — Marry a card; defaults to your last pulled card.
- `ns divorce` (`ns dv`, `ndv`) — End your current marriage.""",
    ),
    (
        "owner",
        "Owner-only",
        """- `ns dbexport` — Export the SQLite DB file.
- `ns dbreset` — Reset all persisted bot data.""",
    ),
)


def help_overview_description() -> str:
    return """Noodswap is a card-collecting Discord bot with drops, trading, burning, cosmetics, wishlists, and collection management.

Use the dropdown below to browse help by category."""


def help_category_pages() -> tuple[tuple[str, str, str], ...]:
    return HELP_CATEGORY_PAGES


def help_category_content(category_key: str) -> tuple[str, str] | None:
    for key, label, description in HELP_CATEGORY_PAGES:
        if key == category_key:
            return label, description
    return None
