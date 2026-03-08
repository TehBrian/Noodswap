import discord

from .cards import card_dupe_display
from .utils import multiline_text

ITALY_RED = 0xCE2B37
ITALY_PINK = 0xF4B6C2


def italy_embed(title: str, description: str = "", color: int = ITALY_RED) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def italy_marry_embed(title: str, description: str = "") -> discord.Embed:
    return italy_embed(title=title, description=description, color=ITALY_PINK)


def format_drop_choice_line(card_id: str, generation: int) -> str:
    return card_dupe_display(card_id, generation, pad_dupe_code=False)


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


def battle_offer_description(
    challenged_mention: str,
    challenger_mention: str,
    stake: int,
    challenger_team_name: str,
    challenged_team_name: str,
) -> str:
    return f"""Offered to: {challenged_mention}
Challenger: {challenger_mention}

Stake: **{stake}** dough each
{challenger_mention} active team: `{challenger_team_name}`
{challenged_mention} active team: `{challenged_team_name}`

Accept to start the arena setup."""


def _hp_bar(current_hp: int, max_hp: int, width: int = 12) -> str:
    if max_hp <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, current_hp / max_hp))
    filled = int(round(ratio * width))
    return ("█" * filled) + ("░" * (width - filled))


def _combatant_line(row: dict[str, int | str | bool]) -> str:
    card_id = str(row["card_id"])
    dupe_code = str(row["dupe_code"])
    current_hp = int(row["current_hp"])
    max_hp = int(row["max_hp"])
    defending = bool(row["is_defending"])
    knocked_out = bool(row["is_knocked_out"])
    active = bool(row["is_active"])
    state_bits: list[str] = []
    if active:
        state_bits.append("ACTIVE")
    if defending:
        state_bits.append("DEFEND")
    if knocked_out:
        state_bits.append("KO")
    state_text = f" ({', '.join(state_bits)})" if state_bits else ""
    return f"`{card_id}#{dupe_code}`{state_text} {current_hp}/{max_hp} {_hp_bar(current_hp, max_hp)}"


def battle_arena_description(
    *,
    challenger_mention: str,
    challenged_mention: str,
    stake: int,
    turn_number: int,
    acting_user_id: int | None,
    winner_user_id: int | None,
    challenger_team_name: str,
    challenged_team_name: str,
    challenger_rows: tuple[dict[str, int | str | bool], ...],
    challenged_rows: tuple[dict[str, int | str | bool], ...],
    last_action: str,
) -> str:
    actor_text = f"<@{acting_user_id}>" if acting_user_id is not None else "None"
    winner_text = f"🏆 <@{winner_user_id}> 🥇" if winner_user_id is not None else "-"
    challenger_lines = [_combatant_line(row) for row in challenger_rows] or ["(no cards)"]
    challenged_lines = [_combatant_line(row) for row in challenged_rows] or ["(no cards)"]
    return (
        f"Turn: **{turn_number}**\n"
        f"Acting: {actor_text}\n"
        f"Winner: {winner_text}\n"
        f"Stake Pot: **{stake * 2}** dough\n\n"
        f"{challenger_mention} Team `{challenger_team_name}`\n"
        f"{multiline_text(challenger_lines)}\n\n"
        f"{challenged_mention} Team `{challenged_team_name}`\n"
        f"{multiline_text(challenged_lines)}\n\n"
        f"Last Action: {last_action}"
    )


# Canonical command syntax used in command error embeds.
COMMAND_SYNTAX_BY_KEY: dict[str, str] = {
    "battle": "ns battle <player> <stake>",
    "burn": "ns burn [targets...]",
    "buy": "ns buy drop [quantity]",
    "buy drop": "ns buy drop [quantity]",
    "cards": "ns cards",
    "collection": "ns collection [player]",
    "cooldown": "ns cooldown [player]",
    "dbexport": "ns dbexport",
    "dbreset": "ns dbreset",
    "divorce": "ns divorce",
    "drop": "ns drop",
    "flip": "ns flip <stake> [heads|tails]",
    "folder": "ns folder add <folder_name> [emoji], ns folder remove <folder_name>, ns folder list, ns folder lock <folder_name>, ns folder unlock <folder_name>, ns folder assign <folder_name> <card_code>, ns folder unassign <folder_name> <card_code>, ns folder cards <folder_name>, ns folder emoji <folder_name> <emoji>",
    "folder add": "ns folder add <folder_name> [emoji]",
    "folder assign": "ns folder assign <folder_name> <card_code>",
    "folder cards": "ns folder cards <folder_name>",
    "folder emoji": "ns folder emoji <folder_name> <emoji>",
    "folder list": "ns folder list",
    "folder lock": "ns folder lock <folder_name>",
    "folder remove": "ns folder remove <folder_name>",
    "folder unassign": "ns folder unassign <folder_name> <card_code>",
    "folder unlock": "ns folder unlock <folder_name>",
    "font": "ns font [card_code]",
    "frame": "ns frame [card_code]",
    "gift": "ns gift <player> <dough>",
    "help": "ns help",
    "info": "ns info [player]",
    "leaderboard": "ns leaderboard",
    "lookup": "ns lookup <card_id|card_code|query>",
    "lookuphd": "ns lookuphd <card_id|card_code|query>",
    "marry": "ns marry [card_code]",
    "morph": "ns morph [card_code]",
    "slots": "ns slots",
    "tag": "ns tag add <tag_name>, ns tag remove <tag_name>, ns tag list, ns tag lock <tag_name>, ns tag unlock <tag_name>, ns tag assign <tag_name> <card_code>, ns tag unassign <tag_name> <card_code>, ns tag cards <tag_name>",
    "tag add": "ns tag add <tag_name>",
    "tag assign": "ns tag assign <tag_name> <card_code>",
    "tag cards": "ns tag cards <tag_name>",
    "tag list": "ns tag list",
    "tag lock": "ns tag lock <tag_name>",
    "tag remove": "ns tag remove <tag_name>",
    "tag unassign": "ns tag unassign <tag_name> <card_code>",
    "tag unlock": "ns tag unlock <tag_name>",
    "team": "ns team add <team_name>, ns team remove <team_name>, ns team list, ns team assign <team_name> <card_code>, ns team unassign <team_name> <card_code>, ns team cards <team_name>, ns team active [team_name]",
    "team active": "ns team active [team_name]",
    "team add": "ns team add <team_name>",
    "team assign": "ns team assign <team_name> <card_code>",
    "team cards": "ns team cards <team_name>",
    "team list": "ns team list",
    "team remove": "ns team remove <team_name>",
    "team unassign": "ns team unassign <team_name> <card_code>",
    "trade": "ns trade <player> <card_code> <amount>",
    "vote": "ns vote",
    "wa": "ns wish add <card_id>",
    "wish": "ns wish add <card_id>, ns wish remove <card_id>, ns wish list [player]",
    "wish add": "ns wish add <card_id>",
    "wish list": "ns wish list [player]",
    "wish remove": "ns wish remove <card_id>",
    "wl": "ns wish list [player]",
    "wr": "ns wish remove <card_id>",
}


def command_syntax_for_error(command_key: str) -> str | None:
    return COMMAND_SYNTAX_BY_KEY.get(command_key)

HELP_CATEGORY_PAGES: tuple[tuple[str, str, str], ...] = (
    (
        "overview",
        "Overview",
        """- `ns info [player]` (`ns i`, `ni`) — View a player's info; defaults to yourself or the replied user.
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
        """- `ns drop` (`ns d`, `nd`) — Open a drop with 3 cards and pull 1 (auto-uses 1 drop ticket if drop cooldown is active).
    - `ns buy drop [quantity]` — Buy drop tickets for 1 starter each (default quantity: 1).
- `ns cooldown [player]` (`ns cd`) — Check a player's cooldowns; defaults to yourself or the replied user.
- `ns vote` (`ns v`, `nv`) — Open top.gg vote link and claim starter reward if your vote is detected.
- `ns burn [targets...]` (`ns b`, `nb`) — Burn one or many targets for dough; supports card codes/IDs and `tag <name>`; defaults to last pulled card.
    - `ns gift <player> <dough>` (`ns g`) — Send dough to another player.
    - `ns trade <player> <card_code> <amount>` (`ns t`, `nt`) — Offer a card-for-dough trade.""",
    ),
    (
        "gambling",
        "Gambling",
        """- `ns slots` (`ns sl`) — Spin 3 food reels; matching all 3 wins 1-3 starter.
- `ns flip <stake> [heads|tails]` (`ns f`, `nf`) — Flip a coin wager (46% heads win / 54% tails lose), 2m cooldown.""",
    ),
    (
        "battle",
        "Battle",
        """- `ns team ...` (`ns tm ...`) — Manage battle teams and set your active team.
- `ns battle <player> <stake>` (`ns bt`) — Propose a stake battle to another player.""",
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
