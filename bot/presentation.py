import discord

from .cards import card_display
from .utils import multiline_text

ITALY_RED = 0xCE2B37
ITALY_PINK = 0xF4B6C2


def italy_embed(title: str, description: str = "", color: int = ITALY_RED) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def italy_marry_embed(title: str, description: str = "") -> discord.Embed:
    return italy_embed(title=title, description=description, color=ITALY_PINK)


def format_drop_choice_line(card_type_id: str, generation: int) -> str:
    return card_display(card_type_id, generation, pad_card_id=False)


def drop_choices_description(choices: list[tuple[str, int]]) -> str:
    lines = [format_drop_choice_line(card_type_id, generation) for card_type_id, generation in choices]
    return f"""{multiline_text(lines)}"""


def burn_confirmation_description(
    card_type_id: str,
    generation: int,
    card_id: str | None,
    value: int,
    base_value: int,
    delta_range: int,
    multiplier: float,
) -> str:
    return f"""Burn this card?

{card_display(card_type_id, generation, card_id=card_id)}

Base Value: **{base_value}**
Total Multiplier: **x{multiplier:.2f}**
Value: **{value}**
Payout: **{value}** ± **{delta_range}**"""


def trade_offer_description(
    offered_to_mention: str,
    seller_mention: str,
    card_type_id: str,
    generation: int,
    card_id: str | None,
    terms: object,  # TradeTerms; typed as object to avoid circular import
) -> str:
    mode: str = getattr(terms, "mode")
    if mode == "dough":
        price_line = f"Price: **{getattr(terms, 'amount')}** dough"
    elif mode == "starter":
        price_line = f"Price: **{getattr(terms, 'amount')}** starter"
    elif mode == "drop":
        price_line = f"Price: **{getattr(terms, 'amount')}** drop ticket(s)"
    elif mode == "pull":
        price_line = f"Price: **{getattr(terms, 'amount')}** pull ticket(s)"
    else:
        # card mode
        req_card_type_id = getattr(terms, "req_card_type_id", None)
        req_gen = getattr(terms, "req_generation", None)
        req_dupe = getattr(terms, "req_card_id", None)
        if req_card_type_id is not None and req_gen is not None:
            req_text = card_display(req_card_type_id, req_gen, card_id=req_dupe)
        else:
            req_text = "unknown card"
        price_line = f"Requesting: {req_text}"
    return f"""Offered to: {offered_to_mention}
Seller: {seller_mention}

Card: {card_display(card_type_id, generation, card_id=card_id)}
{price_line}"""


def gift_offer_description(
    offered_to_mention: str,
    sender_mention: str,
    card_type_id: str,
    generation: int,
    card_id: str | None,
) -> str:
    return f"""Offered to: {offered_to_mention}
Sender: {sender_mention}

Card: {card_display(card_type_id, generation, card_id=card_id)}"""


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
    card_type_id = str(row["card_type_id"])
    card_id = str(row["card_id"])
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
    info_line = f"`{card_type_id}#{card_id}`{state_text} • HP:{current_hp} ATK:{attack} DEF:{defense}"
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
    "buy": "ns buy <drop|pull> [quantity]",
    "buy drop": "ns buy drop [quantity]",
    "buy pull": "ns buy pull [quantity]",
    "cards": "ns cards",
    "collection": "ns collection [player]",
    "types": "ns types",
    "cooldown": "ns cooldown [player]",
    "dbexport": "ns dbexport",
    "dbreset": "ns dbreset",
    "divorce": "ns divorce",
    "deposit": "ns deposit <amount> [dough|starter|drop|pull]",
    "drop": "ns drop",
    "flip": "ns flip <stake> [heads|tails]",
    "folder": (
        "ns folder add <folder_name> [emoji], ns folder remove <folder_name>, ns folder list, "
        "ns folder lock <folder_name>, ns folder unlock <folder_name>, "
        "ns folder assign <folder_name> <card_id>, ns folder unassign <folder_name> <card_id>, "
        "ns folder cards <folder_name>, ns folder emoji <folder_name> <emoji>"
    ),
    "folder add": "ns folder add <folder_name> [emoji]",
    "folder assign": "ns folder assign <folder_name> <card_id>",
    "folder cards": "ns folder cards <folder_name>",
    "folder emoji": "ns folder emoji <folder_name> <emoji>",
    "folder list": "ns folder list",
    "folder lock": "ns folder lock <folder_name>",
    "folder remove": "ns folder remove <folder_name>",
    "folder unassign": "ns folder unassign <folder_name> <card_id>",
    "folder unlock": "ns folder unlock <folder_name>",
    "font": "ns font [card_id]",
    "frame": "ns frame [card_id]",
    "gift": "ns gift <dough|starter|drop|pull|card> <player> <amount|card_id>",
    "gift card": "ns gift card <player> <card_id>",
    "gift dough": "ns gift dough <player> <dough>",
    "gift drop": "ns gift drop <player> <tickets>",
    "gift pull": "ns gift pull <player> <tickets>",
    "gift starter": "ns gift starter <player> <starter>",
    "help": "ns help",
    "info": "ns info [player]",
    "leaderboard": "ns leaderboard",
    "lookup": "ns lookup <card_type_id|card_id|query>",
    "lookuphd": "ns lookuphd <card_type_id|card_id|query>",
    "marry": "ns marry [card_id]",
    "monopoly": "ns monopoly <roll|fine|board|pot>",
    "monopoly board": "ns monopoly board",
    "monopoly fine": "ns monopoly fine",
    "monopoly pot": "ns monopoly pot",
    "monopoly roll": "ns monopoly roll",
    "oven": "ns oven <deposit|withdraw|balance> [amount]",
    "oven balance": "ns oven balance",
    "oven deposit": "ns oven deposit <amount>",
    "oven withdraw": "ns oven withdraw <amount>",
    "morph": "ns morph [card_id]",
    "slots": "ns slots",
    "ship": "ns ship <user> [other_user]",
    "tag": (
        "ns tag add <tag_name>, ns tag remove <tag_name>, ns tag list, "
        "ns tag lock <tag_name>, ns tag unlock <tag_name>, "
        "ns tag assign <tag_name> <card_id>, ns tag unassign <tag_name> <card_id>, "
        "ns tag cards <tag_name>"
    ),
    "tag add": "ns tag add <tag_name>",
    "tag assign": "ns tag assign <tag_name> <card_id>",
    "tag cards": "ns tag cards <tag_name>",
    "tag list": "ns tag list",
    "tag lock": "ns tag lock <tag_name>",
    "tag remove": "ns tag remove <tag_name>",
    "tag unassign": "ns tag unassign <tag_name> <card_id>",
    "tag unlock": "ns tag unlock <tag_name>",
    "team": (
        "ns team add <team_name>, ns team remove <team_name>, ns team list, "
        "ns team assign <team_name> <card_id>, ns team unassign <team_name> <card_id>, "
        "ns team cards <team_name>, ns team active [team_name]"
    ),
    "team active": "ns team active [team_name]",
    "team add": "ns team add <team_name>",
    "team assign": "ns team assign <team_name> <card_id>",
    "team cards": "ns team cards <team_name>",
    "team list": "ns team list",
    "team remove": "ns team remove <team_name>",
    "team unassign": "ns team unassign <team_name> <card_id>",
    "trade": "ns trade <player> <card_id> <mode> <amount|card_id>",
    "withdraw": "ns withdraw <amount> [dough|starter|drop|pull]",
    "vote": "ns vote",
    "wa": "ns wish add <card_type_id>",
    "wish": "ns wish add <card_type_id>, ns wish remove <card_type_id>, ns wish list [player]",
    "wish add": "ns wish add <card_type_id>",
    "wish list": "ns wish list [player]",
    "wish remove": "ns wish remove <card_type_id>",
    "wl": "ns wish list [player]",
    "wr": "ns wish remove <card_type_id>",
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
- `cards` (`ca`) — View all owned card instances across all players.
- `types` (`ty`) — View all card types.
- `lookup <card_type_id|card_id|query>` (`l`) — Look up a card type by type ID or query, or an owned copy by card ID.
- `lookuphd <card_type_id|card_id|query>` (`lhd`) — View a card in high resolution.
- `help` (`h`) — Open this help menu.""",
    ),
    (
        "economy",
        "Economy",
        """- `drop` (`d`) — Drop 3 cards.
- `buy drop [quantity]` — Buy drop tickets for 1 starter each. Defaults to 1.
- `buy pull [quantity]` — Buy pull tickets for 1 starter each. Defaults to 1.
- `cooldown [player]` (`cd`) — Check a player's cooldowns. Defaults to yourself or the replied user.
- `vote` (`v`) — Vote for the bot to claim rewards.
- `burn [target...]` (`b`) — Burn targets for dough. Supports card IDs plus
    `t:<tag>` and `f:<folder>` selectors. Defaults to last pulled card.
- `cards` (`ca`) — View all owned card instances across all players, with sortable ranking.
- `gift dough <player> <dough>` (`gift d`) — Send dough to a player.
- `gift starter <player> <starter>` (`gift s`) — Send starter to a player.
- `gift drop <player> <tickets>` — Send drop tickets to a player.
- `gift pull <player> <tickets>` — Send pull tickets to a player.
- `gift card <player> <card_id>` (`gift c`) — Send a card to a player.
- `oven balance` — Show all oven balances and wallet balances.
- `oven deposit <amount> [dough|starter|drop|pull]` — Move an item from your wallet into the oven (default: dough).
- `oven withdraw <amount> [dough|starter|drop|pull]` — Move an item out of the oven and back to your wallet (default: dough).
- `deposit` — Alias for `oven deposit`.
- `withdraw` — Alias for `oven withdraw`.
- `trade <player> <card_id> <mode> <amount|req_code>` (`t`) — Offer a trade. Mode: `dough`, `starter`, `drop`, `pull`, or `card`.""",
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
- `monopoly pot` (`... p`) — View the Free Parking pot.""",
    ),
    (
        "battle",
        "Battle",
        """- `team` (`tm`) — Manage your teams.
- `team add <team_name>` (`... a`) — Create a team.
- `team remove <team_name>` (`... r`) — Delete one of your teams.
- `team list` (`... l`) — List your teams.
- `team assign <team_name> <card_id>` (`... as`) — Add a card to a team.
- `team unassign <team_name> <card_id>` (`... u`) — Remove a card from a team.
- `team cards <team_name>` (`... c`) — List cards in a team.
- `team active [team_name]` — Show or set your active battle team.
- `battle <player> <stake>` (`bt`) — Propose a battle to another player.""",
    ),
    (
        "traits",
        "Traits",
        """- `morph [card_id]` (`mo`) — Roll for a morph. Defaults to last pulled card.
- `frame [card_id]` (`fr`) — Roll for a frame. Defaults to last pulled card.
- `font [card_id]` (`fo`) — Roll for a font. Defaults to last pulled card.""",
    ),
    (
        "wishlist",
        "Wishlist",
        """- `wish` (`w`) — Manage your wishlist.
- `wish add <card_type_id>` (`... a`, `wa`) — Add a card to your wishlist.
- `wish remove <card_type_id>` (`... r`, `wr`) — Remove a card from your wishlist.
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
- `tag assign <tag_name> <card_id>` (`... as`) — Add a card to a tag.
- `tag unassign <tag_name> <card_id>` (`... u`) — Remove a card from a tag.
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
- `folder assign <folder_name> <card_id>` (`... as`) — Add a card to a folder.
- `folder unassign <folder_name> <card_id>` (`... u`) — Remove a card from a folder.
- `folder cards <folder_name>` (`... c`) — Show cards in that folder.
- `folder emoji <folder_name> <emoji>` (`... e`) — Update a folder emoji.""",
    ),
    (
        "relationship",
        "Relationship",
        """- `ship <user> [other_user]` — Show deterministic compatibility between two players; `[other_user]` defaults to yourself.
- `marry [card_id]` (`m`) — Marry a card. Defaults to last pulled card.
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


# ---------------------------------------------------------------------------
# Economy — cosmetic rolls (morph / frame / font confirmations)
# ---------------------------------------------------------------------------


def cosmetic_roll_confirmation_description(
    card_display_str: str,
    trait_name: str,
    current_trait_label: str,
    cost: int,
) -> str:
    return f"{card_display_str}\n\nCurrent {trait_name}: **{current_trait_label}**\nRoll Cost: **{cost}** dough"


# ---------------------------------------------------------------------------
# Economy — oven
# ---------------------------------------------------------------------------


def oven_balance_description(dough: int, starter: int, drop_tickets: int, pull_tickets: int) -> str:
    return multiline_text(
        [
            f"Oven Dough: **{dough}**",
            f"Oven Starter: **{starter}**",
            f"Oven Drop Tickets: **{drop_tickets}**",
            f"Oven Pull Tickets: **{pull_tickets}**",
        ]
    )


def oven_transaction_description(
    direction: str,  # "deposit" or "withdraw"
    item_label: str,
    amount: int,
    fee: int,
    net_amount: int,
    spendable_balance: int,
    oven_balance: int,
) -> str:
    moved_label = "Moved to Oven" if direction == "deposit" else "Moved to Wallet"
    return multiline_text(
        [
            f"Requested: **{amount} {item_label}**",
            f"Fee (3%): **{fee} {item_label}**",
            f"{moved_label}: **{net_amount} {item_label}**",
            "",
            f"Wallet: **{spendable_balance} {item_label}**",
            f"Oven: **{oven_balance} {item_label}**",
        ]
    )


# ---------------------------------------------------------------------------
# Economy — gifts
# ---------------------------------------------------------------------------


def gift_currency_description(
    item_label: str,
    balance_noun: str,
    amount: int,
    recipient_id: int,
    recipient_name: str,
    sender_balance: int,
    recipient_balance: int,
) -> str:
    # When balance_noun differs from the item label (e.g. "Balance" vs "dough"),
    # the unit is appended after the balance value; otherwise the noun already
    # serves as the unit label and no suffix is needed.
    balance_unit = f" {item_label}" if balance_noun.lower() != item_label.lower() else ""
    return multiline_text(
        [
            f"Sent: **{amount}** {item_label} to <@{recipient_id}>",
            f"Your {balance_noun}: **{sender_balance}**{balance_unit}",
            f"{recipient_name}'s {balance_noun}: **{recipient_balance}**{balance_unit}",
        ]
    )


def gift_card_result_description(
    recipient_mention: str,
    sender_mention: str,
    card_display_str: str,
) -> str:
    return multiline_text(
        [
            f"Recipient: {recipient_mention}",
            f"Sender: {sender_mention}",
            "",
            f"Card: {card_display_str}",
        ]
    )


# ---------------------------------------------------------------------------
# Catalog — buy tickets
# ---------------------------------------------------------------------------


def buy_insufficient_description(quantity: int, starter_balance: int) -> str:
    return multiline_text(
        [
            f"Cost: **{quantity} starter**",
            f"Starter Balance: **{starter_balance}**",
            "You do not have enough starter.",
        ]
    )


def buy_ticket_success_description(
    ticket_type: str,  # "drop" or "pull"
    spent: int,
    starter_balance: int,
    ticket_balance: int,
    spent_label: str = "Cost",
) -> str:
    plural = "s" if spent != 1 else ""
    ticket_label = "Drop Tickets" if ticket_type == "drop" else "Pull Tickets"
    return multiline_text(
        [
            f"Purchased: **{spent} {ticket_type} ticket{plural}**",
            f"{spent_label}: **{spent} starter**",
            "",
            f"Starter: **{starter_balance}**",
            f"{ticket_label}: **{ticket_balance}**",
        ]
    )


def player_cooldowns_description(cooldown_lines: list[str]) -> str:
    return multiline_text(cooldown_lines)


# ---------------------------------------------------------------------------
# Catalog — vote
# ---------------------------------------------------------------------------


def vote_status_description(
    topgg_url: str,
    topgg_reward_starter: int,
    topgg_reward_dough: int,
    voted_topgg_recent: bool,
    dbl_url: str,
    dbl_reward_drop: int,
    dbl_reward_pull: int,
    voted_dbl_recent: bool,
    total_votes: int,
    monthly_votes: int,
    next_month_reset_unix: int,
) -> str:
    yes_emoji = "✅"
    no_emoji = "❌"
    topgg_status = yes_emoji if voted_topgg_recent else no_emoji
    dbl_status = yes_emoji if voted_dbl_recent else no_emoji
    return multiline_text(
        [
            "Earn rewards and support Noodswap by voting!",
            "",
            f"Reward: **+{topgg_reward_starter} starter** and **+{topgg_reward_dough} dough** per **vote** on [Top.gg]({topgg_url})",
            f"> Voted on [Top.gg]({topgg_url}): {topgg_status}",
            "",
            f"Reward: **+{dbl_reward_drop} drop tickets** and **+{dbl_reward_pull} pull ticket** per **vote** on [DiscordBotList]({dbl_url})",
            f"> Voted on [DiscordBotList]({dbl_url}): {dbl_status}",
            "",
            f"- **Total** Votes: **{total_votes}**",
            f"- **Monthly** Votes: **{monthly_votes}** (resets <t:{next_month_reset_unix}:R>)",
        ]
    )


# ---------------------------------------------------------------------------
# Social — ship
# ---------------------------------------------------------------------------


def ship_result_description(left_name: str, right_name: str, compatibility_percent: int) -> str:
    return multiline_text(
        [
            f"Left: **{left_name}**",
            f"Right: **{right_name}**",
            f"Compastability: **{compatibility_percent}%**",
        ]
    )


# ---------------------------------------------------------------------------
# Gambling — flip
# ---------------------------------------------------------------------------


def flip_suspense_description(activity_phrase: str, selected_side: str | None) -> str:
    lines = [f"The coin is **{activity_phrase}**..."]
    if selected_side is not None:
        lines.append(f"Call: **{selected_side.capitalize()}**")
    return multiline_text(lines)


def flip_result_description(
    result_side: str,
    did_win: bool,
    payout_or_stake: int,
    dough_total: int,
) -> str:
    second_line = (
        f"Payout: **+{payout_or_stake}** dough"
        if did_win
        else f"Lost: **-{payout_or_stake}** dough"
    )
    return multiline_text(
        [
            f"Result: **{result_side.capitalize()}**",
            second_line,
            f"Balance: **{dough_total}** dough",
        ]
    )


# ---------------------------------------------------------------------------
# Gambling — monopoly
# ---------------------------------------------------------------------------


def monopoly_board_description(
    position: int,
    in_jail: bool,
    jail_attempts: int,
    doubles_count: int,
    board_render: str,
) -> str:
    return multiline_text(
        [
            f"Position: **{position}**",
            f"In Jail: **{'Yes' if in_jail else 'No'}**",
            f"Jail Failed Rolls: **{jail_attempts}/3**",
            f"Consecutive Doubles: **{doubles_count}**",
            "",
            f"```\n{board_render}\n```",
        ]
    )


def monopoly_pot_description(dough: int, starter: int, drop_tickets: int, pull_tickets: int) -> str:
    return multiline_text(
        [
            f"Dough: **{dough}**",
            f"Starter: **{starter}**",
            f"Drop Tickets: **{drop_tickets}**",
            f"Pull Tickets: **{pull_tickets}**",
        ]
    )


def monopoly_usage_description() -> str:
    return multiline_text(
        [
            "Usage:",
            "`ns monopoly roll`",
            "`ns monopoly fine`",
            "`ns monopoly board`",
            "`ns monopoly pot`",
        ]
    )


def slots_jackpot_lines(
    dough_reward: int,
    starter_reward: int,
    dough_total: int,
    starter_total: int,
) -> list[str]:
    return [
        "Jackpot! All three matched.",
        f"Reward: **+{dough_reward} dough** and **+{starter_reward} starter**",
        f"Dough Balance: **{dough_total}** dough",
        f"Starter Balance: **{starter_total}**",
    ]


def slots_partial_win_lines(dough_reward: int, dough_total: int) -> list[str]:
    return [
        "Two matched.",
        f"Reward: **+{dough_reward} dough**",
        f"Dough Balance: **{dough_total}** dough",
    ]


def slots_no_match_lines(cooldown_text: str) -> list[str]:
    return [
        "No match this time.",
        f"Try again in **{cooldown_text}**.",
    ]


def player_wallet_items_value(dough: int, starter: int, drop_tickets: int, pull_tickets: int) -> str:
    return "\n".join(
        [
            f"- {dough} dough",
            f"- {starter} starter",
            f"- {drop_tickets} drop tickets",
            f"- {pull_tickets} pull tickets",
        ]
    )


def player_oven_items_value(oven_dough: int, oven_starter: int, oven_drop_tickets: int, oven_pull_tickets: int) -> str:
    return "\n".join(
        [
            f"- {oven_dough} dough",
            f"- {oven_starter} starter",
            f"- {oven_drop_tickets} drop tickets",
            f"- {oven_pull_tickets} pull tickets",
        ]
    )
