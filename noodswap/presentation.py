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
Total Multiplier: **x{multiplier:.2f}**
Value: **{value}**
Payout: **{value}** ± **{delta_range}**"""



def trade_offer_description(
    offered_to_mention: str,
    seller_mention: str,
    card_id: str,
    generation: int,
    dupe_code: str | None,
    terms: object,  # TradeTerms; typed as object to avoid circular import
) -> str:
    mode: str = getattr(terms, "mode")
    if mode == "dough":
        price_line = f"Price: **{getattr(terms, 'amount')}** dough"
    elif mode == "starter":
        price_line = f"Price: **{getattr(terms, 'amount')}** starter"
    elif mode == "tickets":
        price_line = f"Price: **{getattr(terms, 'amount')}** drop ticket(s)"
    else:
        # card mode
        req_card_id = getattr(terms, "req_card_id", None)
        req_gen = getattr(terms, "req_generation", None)
        req_dupe = getattr(terms, "req_dupe_code", None)
        if req_card_id is not None and req_gen is not None:
            req_text = card_dupe_display(req_card_id, req_gen, dupe_code=req_dupe)
        else:
            req_text = "unknown card"
        price_line = f"Requesting: {req_text}"
    return f"""Offered to: {offered_to_mention}
Seller: {seller_mention}

Card: {card_dupe_display(card_id, generation, dupe_code=dupe_code)}
{price_line}"""


def gift_offer_description(
    offered_to_mention: str,
    sender_mention: str,
    card_id: str,
    generation: int,
    dupe_code: str | None,
) -> str:
    return f"""Offered to: {offered_to_mention}
Sender: {sender_mention}

Card: {card_dupe_display(card_id, generation, dupe_code=dupe_code)}"""


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
    attack = int(row["attack"]) if row.get("attack") is not None else 0
    defense = int(row["defense"]) if row.get("defense") is not None else 0
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
    hp_text = f"{current_hp:>3}/{max_hp:<3}"
    health_line = f"`HP {hp_text}` {_hp_bar(current_hp, max_hp)}"
    info_line = f"`{card_id}#{dupe_code}`{state_text} • HP:{current_hp} ATK:{attack} DEF:{defense}"
    return f"{health_line}\n{info_line}"


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
    "folder": (
        "ns folder add <folder_name> [emoji], ns folder remove <folder_name>, ns folder list, "
        "ns folder lock <folder_name>, ns folder unlock <folder_name>, "
        "ns folder assign <folder_name> <card_code>, ns folder unassign <folder_name> <card_code>, "
        "ns folder cards <folder_name>, ns folder emoji <folder_name> <emoji>"
    ),
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
    "gift": "ns gift <dough|starter|drop|card> <player> <amount|card_code>",
    "gift card": "ns gift card <player> <card_code>",
    "gift dough": "ns gift dough <player> <dough>",
    "gift drop": "ns gift drop <player> <tickets>",
    "gift starter": "ns gift starter <player> <starter>",
    "help": "ns help",
    "info": "ns info [player]",
    "leaderboard": "ns leaderboard",
    "lookup": "ns lookup <card_id|card_code|query>",
    "lookuphd": "ns lookuphd <card_id|card_code|query>",
    "marry": "ns marry [card_code]",
    "monopoly": "ns monopoly <roll|fine|board|pot>",
    "monopoly board": "ns monopoly board",
    "monopoly fine": "ns monopoly fine",
    "monopoly pot": "ns monopoly pot",
    "monopoly roll": "ns monopoly roll",
    "morph": "ns morph [card_code]",
    "slots": "ns slots",
    "tag": (
        "ns tag add <tag_name>, ns tag remove <tag_name>, ns tag list, "
        "ns tag lock <tag_name>, ns tag unlock <tag_name>, "
        "ns tag assign <tag_name> <card_code>, ns tag unassign <tag_name> <card_code>, "
        "ns tag cards <tag_name>"
    ),
    "tag add": "ns tag add <tag_name>",
    "tag assign": "ns tag assign <tag_name> <card_code>",
    "tag cards": "ns tag cards <tag_name>",
    "tag list": "ns tag list",
    "tag lock": "ns tag lock <tag_name>",
    "tag remove": "ns tag remove <tag_name>",
    "tag unassign": "ns tag unassign <tag_name> <card_code>",
    "tag unlock": "ns tag unlock <tag_name>",
    "team": (
        "ns team add <team_name>, ns team remove <team_name>, ns team list, "
        "ns team assign <team_name> <card_code>, ns team unassign <team_name> <card_code>, "
        "ns team cards <team_name>, ns team active [team_name]"
    ),
    "team active": "ns team active [team_name]",
    "team add": "ns team add <team_name>",
    "team assign": "ns team assign <team_name> <card_code>",
    "team cards": "ns team cards <team_name>",
    "team list": "ns team list",
    "team remove": "ns team remove <team_name>",
    "team unassign": "ns team unassign <team_name> <card_code>",
    "trade": "ns trade <player> <card_code> <mode> <amount|card_code>",
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
        """- `info [player]` (`i`) — View a player's info. Defaults to yourself or the replied user.
- `leaderboard` (`le`) — View players ranked on various criteria.
- `collection [player]` (`c`) — View a player's cards. Defaults to yourself or the replied user.
- `cards` (`ca`) — View all cards.
- `lookup <card_id|card_code|query>` (`l`) — Look up a base card by ID or query or a dupe card by code.
- `lookuphd <card_id|card_code|query>` (`lhd`) — View a card in high resolution.
- `help` (`h`) — Open this help menu.""",
    ),
    (
        "economy",
        "Economy",
        """- `drop` (`d`) — Drop 3 cards.
- `buy drop [quantity]` — Buy drop tickets for 1 starter each. Defaults to 1.
- `cooldown [player]` (`cd`) — Check a player's cooldowns. Defaults to yourself or the replied user.
- `vote` (`v`) — Vote for the bot to claim rewards.
- `burn [target...]` (`b`) — Burn targets for dough. Supports card codes plus
    `t:<tag>` and `f:<folder>` selectors. Defaults to last pulled card.
- `gift dough <player> <dough>` (`gift d`) — Send dough to a player.
- `gift starter <player> <starter>` (`gift s`) — Send starter to a player.
- `gift drop <player> <tickets>` — Send drop tickets to a player.
- `gift card <player> <card_code>` (`gift c`) — Send a card to a player.
- `trade <player> <card_code> <mode> <amount|req_code>` (`t`) — Offer a trade. Mode: `dough`, `starter`, `tickets`, or `card`.""",
    ),
    (
        "gambling",
        "Gambling",
        """- `slots` (`sl`) — Spin 3 food reels. Matching all 3 wins 1-3 starter.
- `flip <stake> [heads|tails]` (`f`) — Flip a coin to double a wager.""",
    ),
    (
        "monopoly",
        "Monopoly",
        """- `monopoly` (`mp`) — Play Monopoly.
- `monopoly roll` (`... r`) — Roll two dice to move on the board.
- `monopoly fine` (`... fine`) — Pay the jail fine to get out.
- `monopoly board` (`... b`) — View the board and your position on it.
- `monopoly pot` (`... p`) — View the Free Parking pot."""
    ),
    (
        "battle",
        "Battle",
        """- `team` (`tm`) — Manage your teams.
- `team add <team_name>` (`... a`) — Create a team.
- `team remove <team_name>` (`... r`) — Delete one of your teams.
- `team list` (`... l`) — List your teams.
- `team assign <team_name> <card_code>` (`... as`) — Add a card to a team.
- `team unassign <team_name> <card_code>` (`... u`) — Remove a card from a team.
- `team cards <team_name>` (`... c`) — List cards in a team.
- `team active [team_name]` — Show or set your active battle team.
- `battle <player> <stake>` (`bt`) — Propose a battle to another player.""",
    ),
    (
        "cosmetics",
        "Cosmetics",
        """- `morph [card_code]` (`mo`) — Roll for a morph. Defaults to last pulled card.
- `frame [card_code]` (`fr`) — Roll for a frame. Defaults to last pulled card.
- `font [card_code]` (`fo`) — Roll for a font. Defaults to last pulled card.""",
    ),
    (
        "wishlist",
        "Wishlist",
        """- `wish` (`w`) — Manage your wishlist.
- `wish add <card_id>` (`... a`, `wa`) — Add a card to your wishlist.
- `wish remove <card_id>` (`... r`, `wr`) — Remove a card from your wishlist.
- `wish list [player]` (`... l`, `wl`) — Show a player's wishlist. Defaults to yourself or the replied user.""",
    ),
    (
        "tags",
        "Tags",
        """- `tag` — Manage your tags.
- `tag add <tag_name>` (`... a`) — Create a tag.
- `tag remove <tag_name>` (`... r`) — Delete one of your tags.
- `tag list` (`... l`) — List your tags.
- `tag lock <tag_name>` — Enable burn protection for that tag.
- `tag unlock <tag_name>` — Disable burn protection for that tag.
- `tag assign <tag_name> <card_code>` (`... as`) — Add a card to a tag.
- `tag unassign <tag_name> <card_code>` (`... u`) — Remove a card from a tag.
- `tag cards <tag_name>` (`... c`) — Show cards in that tag.""",
    ),
    (
        "folders",
        "Folders",
        """- `folder` — Manage your folders.
- `folder add <folder_name> [emoji]` (`... a`) — Create a folder.
- `folder remove <folder_name>` (`... r`) — Delete one of your folders.
- `folder list` (`... l`) — List your folders with emoji, lock state, and card counts.
- `folder lock <folder_name>` — Enable burn protection for that folder.
- `folder unlock <folder_name>` — Disable burn protection for that folder.
- `folder assign <folder_name> <card_code>` (`... as`) — Add a card to a folder.
- `folder unassign <folder_name> <card_code>` (`... u`) — Remove a card from a folder.
- `folder cards <folder_name>` (`... c`) — Show cards in that folder.
- `folder emoji <folder_name> <emoji>` (`... e`) — Update a folder emoji.""",
    ),
    (
        "relationship",
        "Relationship",
        """- `marry [card_code]` (`m`) — Marry a card. Defaults to last pulled card.
- `divorce` (`dv`) — End your current marriage.""",
    ),
)


def help_overview_description() -> str:
    return """Noodswap is a card-collecting Discord bot with drops, trading, burning, traits, wishlists, and collection management.

Its prefixes are `ns ` and `n`, so you may write, for example, `ns burn` or `nburn`.

Use the dropdown below to browse help by category."""


def help_category_pages() -> tuple[tuple[str, str, str], ...]:
    return HELP_CATEGORY_PAGES


def help_category_content(category_key: str) -> tuple[str, str] | None:
    for key, label, description in HELP_CATEGORY_PAGES:
        if key == category_key:
            return label, description
    return None
