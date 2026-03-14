from bot.presentation import (
    buy_insufficient_description,
    buy_ticket_success_description,
    cosmetic_roll_confirmation_description,
    flip_result_description,
    flip_suspense_description,
    gift_card_result_description,
    gift_currency_description,
    monopoly_board_description,
    monopoly_pot_description,
    monopoly_usage_description,
    oven_balance_description,
    oven_transaction_description,
    player_oven_items_value,
    player_cooldowns_description,
    player_wallet_items_value,
    ship_result_description,
    slots_jackpot_lines,
    slots_no_match_lines,
    slots_partial_win_lines,
    vote_status_description,
)


def test_cosmetic_roll_confirmation_description() -> None:
    description = cosmetic_roll_confirmation_description("🍜 #123", "Morph", "None", 250)
    assert description == "🍜 #123\n\nCurrent Morph: **None**\nRoll Cost: **250** dough"


def test_oven_balance_description() -> None:
    description = oven_balance_description(11, 22, 3, 4)
    assert description == (
        "Oven Dough: **11**\n"
        "Oven Starter: **22**\n"
        "Oven Drop Tickets: **3**\n"
        "Oven Pull Tickets: **4**"
    )


def test_oven_transaction_description_deposit() -> None:
    description = oven_transaction_description(
        "deposit",
        "dough",
        amount=100,
        fee=3,
        net_amount=97,
        spendable_balance=500,
        oven_balance=123,
    )
    assert description == (
        "Requested: **100 dough**\n"
        "Fee (3%): **3 dough**\n"
        "Moved to Oven: **97 dough**\n"
        "\n"
        "Wallet: **500 dough**\n"
        "Oven: **123 dough**"
    )


def test_oven_transaction_description_withdraw() -> None:
    description = oven_transaction_description(
        "withdraw",
        "starter",
        amount=50,
        fee=1,
        net_amount=49,
        spendable_balance=9,
        oven_balance=40,
    )
    assert "Moved to Wallet: **49 starter**" in description


def test_gift_currency_description_dough_balance() -> None:
    description = gift_currency_description(
        item_label="dough",
        balance_noun="Balance",
        amount=20,
        recipient_id=42,
        recipient_name="Pasta",
        sender_balance=100,
        recipient_balance=44,
    )
    assert description == (
        "Sent: **20** dough to <@42>\n"
        "Your Balance: **100** dough\n"
        "Pasta's Balance: **44** dough"
    )


def test_gift_currency_description_drop_tickets() -> None:
    description = gift_currency_description(
        item_label="drop tickets",
        balance_noun="Drop Tickets",
        amount=2,
        recipient_id=99,
        recipient_name="Noodle",
        sender_balance=5,
        recipient_balance=7,
    )
    assert description == (
        "Sent: **2** drop tickets to <@99>\n"
        "Your Drop Tickets: **5**\n"
        "Noodle's Drop Tickets: **7**"
    )


def test_gift_card_result_description() -> None:
    description = gift_card_result_description("<@2>", "<@1>", "🍝 #777")
    assert description == "Recipient: <@2>\nSender: <@1>\n\nCard: 🍝 #777"


def test_buy_insufficient_description() -> None:
    description = buy_insufficient_description(3, 1)
    assert description == (
        "Cost: **3 starter**\n"
        "Starter Balance: **1**\n"
        "You do not have enough starter."
    )


def test_buy_ticket_success_description_drop_and_pull_labels() -> None:
    drop = buy_ticket_success_description("drop", 2, 8, 11)
    pull = buy_ticket_success_description("pull", 1, 7, 5, spent_label="Spent")
    assert "Cost: **2 starter**" in drop
    assert "Drop Tickets: **11**" in drop
    assert "Spent: **1 starter**" in pull
    assert "Pull Tickets: **5**" in pull


def test_vote_status_description() -> None:
    description = vote_status_description(
        "https://top.gg/bot/abc",
        10,
        25,
        voted_topgg_recent=True,
        dbl_url="https://discordbotlist.com/bots/abc",
        dbl_reward_drop=2,
        dbl_reward_pull=1,
        voted_dbl_recent=False,
        total_votes=300,
        monthly_votes=45,
        next_month_reset_unix=1_700_000_000,
    )
    assert "Voted on [Top.gg](https://top.gg/bot/abc) yet: ✅" in description
    assert "Voted on [DiscordBotList](https://discordbotlist.com/bots/abc) yet: ❌" in description
    assert "- **Monthly** Votes: **45** (resets <t:1700000000:R>)" in description


def test_player_cooldowns_description() -> None:
    description = player_cooldowns_description(["Drop: ready", "Pull: 30s"])
    assert description == "Drop: ready\nPull: 30s"


def test_ship_result_description() -> None:
    description = ship_result_description("Left User", "Right User", 88)
    assert description == "Left: **Left User**\nRight: **Right User**\nCompatibility: **88%**"


def test_flip_suspense_description_with_and_without_call() -> None:
    with_call = flip_suspense_description("spinning", "heads")
    without_call = flip_suspense_description("rolling", None)
    assert with_call == "The coin is **spinning**...\nCall: **Heads**"
    assert without_call == "The coin is **rolling**..."


def test_flip_result_description_win_and_loss() -> None:
    win = flip_result_description("heads", did_win=True, payout_or_stake=40, dough_total=210)
    loss = flip_result_description("tails", did_win=False, payout_or_stake=25, dough_total=145)
    assert win == "Result: **Heads**\nPayout: **+40** dough\nBalance: **210** dough"
    assert loss == "Result: **Tails**\nLost: **-25** dough\nBalance: **145** dough"


def test_monopoly_board_description() -> None:
    description = monopoly_board_description(7, True, 2, 1, "A1 B1")
    assert description == (
        "Position: **7**\n"
        "In Jail: **Yes**\n"
        "Jail Failed Rolls: **2/3**\n"
        "Consecutive Doubles: **1**\n"
        "\n"
        "```\nA1 B1\n```"
    )


def test_monopoly_pot_description() -> None:
    description = monopoly_pot_description(9, 8, 7, 6)
    assert description == "Dough: **9**\nStarter: **8**\nDrop Tickets: **7**\nPull Tickets: **6**"


def test_monopoly_usage_description() -> None:
    description = monopoly_usage_description()
    assert description == (
        "Usage:\n"
        "`ns monopoly roll`\n"
        "`ns monopoly fine`\n"
        "`ns monopoly board`\n"
        "`ns monopoly pot`"
    )


def test_slots_result_lines_helpers() -> None:
    jackpot = slots_jackpot_lines(100, 2, 1500, 30)
    partial = slots_partial_win_lines(25, 900)
    miss = slots_no_match_lines("11m")
    assert jackpot == [
        "Jackpot! All three matched.",
        "Reward: **+100 dough** and **+2 starter**",
        "Dough Balance: **1500** dough",
        "Starter Balance: **30**",
    ]
    assert partial == [
        "Two matched.",
        "Reward: **+25 dough**",
        "Dough Balance: **900** dough",
    ]
    assert miss == [
        "No match this time.",
        "Try again in **11m**.",
    ]


def test_player_info_field_value_helpers() -> None:
    wallet = player_wallet_items_value(20, 10, 2, 1)
    oven = player_oven_items_value(5, 4, 3, 2)
    assert wallet == "- 20 dough\n- 10 starter\n- 2 drop tickets\n- 1 pull tickets"
    assert oven == "- 5 dough\n- 4 starter\n- 3 drop tickets\n- 2 pull tickets"
