import unittest
from unittest.mock import patch

from noodswap.presentation import battle_arena_description
from noodswap.services import BattleSnapshot
from noodswap.view_battle import _battle_embed
from noodswap.views import (
    BurnConfirmView,
    CardCatalogView,
    DropView,
    FrameConfirmView,
    FontConfirmView,
    HelpView,
    MorphConfirmView,
    PaginatedLinesView,
    PlayerLeaderboardView,
    SortableCardListView,
    SortableCollectionView,
    TradeView,
)


class _FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class _FakeResponse:
    def __init__(self):
        self.sent_messages: list[dict] = []
        self.edited_messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)

    async def edit_message(self, **kwargs):
        self.edited_messages.append(kwargs)


class _FakeFollowup:
    def __init__(self):
        self.sent_messages: list[dict] = []

    async def send(self, **kwargs):
        self.sent_messages.append(kwargs)


class _FakeInteraction:
    def __init__(self, user_id: int):
        self.user = _FakeUser(user_id)
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()
        self.message = _FakeMessage()


class _FakeMessage:
    class _FakeChannel:
        def __init__(self):
            self.sent_messages: list[dict] = []

        async def send(self, **kwargs):
            self.sent_messages.append(kwargs)

    def __init__(self):
        self.edits: list[dict] = []
        self.replies: list[dict] = []
        self.channel = self._FakeChannel()

    async def edit(self, **kwargs):
        self.edits.append(kwargs)

    async def reply(self, **kwargs):
        self.replies.append(kwargs)


class ViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_battle_arena_description_adds_winner_celebration_emojis(self) -> None:
        description = battle_arena_description(
            challenger_mention="<@10>",
            challenged_mention="<@20>",
            stake=25,
            turn_number=4,
            acting_user_id=None,
            winner_user_id=20,
            challenger_team_name="Pasta",
            challenged_team_name="Sauce",
            challenger_rows=(
                {
                    "card_id": "SPG",
                    "dupe_code": "0",
                    "current_hp": 80,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": False,
                    "is_active": True,
                },
            ),
            challenged_rows=(
                {
                    "card_id": "PEN",
                    "dupe_code": "1",
                    "current_hp": 0,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": True,
                    "is_active": True,
                },
            ),
            last_action="<@20> won.",
        )

        self.assertIn("Winner: 🏆 <@20> 🥇", description)

    async def test_battle_embed_title_celebrates_finished_winner(self) -> None:
        snapshot = BattleSnapshot(
            battle_id=1,
            status="finished",
            challenger_id=10,
            challenged_id=20,
            acting_user_id=None,
            winner_user_id=20,
            turn_number=6,
            stake=50,
            last_action="<@20> dealt **45** and knocked out the last opposing card.",
            challenger_team_name="Pasta",
            challenged_team_name="Sauce",
            challenger_combatants=(
                {
                    "card_id": "SPG",
                    "dupe_code": "0",
                    "current_hp": 0,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": True,
                    "is_active": True,
                },
            ),
            challenged_combatants=(
                {
                    "card_id": "PEN",
                    "dupe_code": "1",
                    "current_hp": 45,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": False,
                    "is_active": True,
                },
            ),
        )

        embed = _battle_embed(snapshot)
        self.assertEqual(embed.title, "Battle Arena 🏆")

    async def test_battle_embed_title_stays_plain_for_active_battle(self) -> None:
        snapshot = BattleSnapshot(
            battle_id=2,
            status="active",
            challenger_id=10,
            challenged_id=20,
            acting_user_id=10,
            winner_user_id=None,
            turn_number=2,
            stake=50,
            last_action="<@10> dealt **12** (1.00x).",
            challenger_team_name="Pasta",
            challenged_team_name="Sauce",
            challenger_combatants=(
                {
                    "card_id": "SPG",
                    "dupe_code": "0",
                    "current_hp": 88,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": False,
                    "is_active": True,
                },
            ),
            challenged_combatants=(
                {
                    "card_id": "PEN",
                    "dupe_code": "1",
                    "current_hp": 72,
                    "max_hp": 100,
                    "is_defending": False,
                    "is_knocked_out": False,
                    "is_active": True,
                },
            ),
        )

        embed = _battle_embed(snapshot)
        self.assertEqual(embed.title, "Battle Arena")

    async def test_player_leaderboard_view_ranks_by_selected_criteria(self) -> None:
        view = PlayerLeaderboardView(
            user_id=10,
            title="Leaderboard",
            entries=[
                (1, 3, 8, 12, 2, 5, 120),
                (2, 9, 1, 30, 1, 1, 300),
                (3, 1, 5, 100, 0, 9, 20),
            ],
            guard_title="Leaderboard",
            page_size=10,
        )

        cards_embed = view.build_embed()
        self.assertIn("<@2>", cards_embed.description)
        self.assertIn("Cards: **9**", cards_embed.description)
        self.assertIn("Cards: **9** • <@2>", cards_embed.description)

        interaction = _FakeInteraction(user_id=10)
        view.criteria_select._values = ["wishes"]
        await view.criteria_select.callback(interaction)

        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("<@1>", edited_embed.description)
        self.assertIn("Wishes: **8**", edited_embed.description)
        self.assertIn("Wishes: **8** • <@1>", edited_embed.description)

        interaction_votes = _FakeInteraction(user_id=10)
        view.criteria_select._values = ["votes"]
        await view.criteria_select.callback(interaction_votes)

        votes_embed = interaction_votes.response.edited_messages[0]["embed"]
        self.assertIn("<@3>", votes_embed.description)
        self.assertIn("Votes: **9**", votes_embed.description)
        self.assertIn("Votes: **9** • <@3>", votes_embed.description)

    async def test_player_leaderboard_view_rejects_unauthorized_user(self) -> None:
        view = PlayerLeaderboardView(
            user_id=10,
            title="Leaderboard",
            entries=[(1, 3, 2, 10, 1, 4, 50)],
            guard_title="Leaderboard",
        )

        interaction = _FakeInteraction(user_id=99)
        view.criteria_select._values = ["dough"]
        await view.criteria_select.callback(interaction)

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertIn("Only the command user", sent["embed"].description)

    async def test_help_view_shows_overview_by_default(self) -> None:
        view = HelpView(user_id=10)
        embed = view.build_overview_embed()

        self.assertEqual(embed.title, "Help")
        self.assertIn("Noodswap", embed.description)

    async def test_help_view_select_swaps_to_category_page(self) -> None:
        view = HelpView(user_id=10)
        interaction = _FakeInteraction(user_id=10)

        view.category_select._values = ["economy"]
        await view.category_select.callback(interaction)

        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertEqual(edited_embed.title, "Help: Economy")
        self.assertIn("ns drop", edited_embed.description)
        self.assertNotIn("ns slots", edited_embed.description)
        self.assertNotIn("ns flip", edited_embed.description)
        self.assertNotIn("ns team", edited_embed.description)
        self.assertNotIn("ns battle", edited_embed.description)

        interaction.response.edited_messages.clear()
        view.category_select._values = ["gambling"]
        await view.category_select.callback(interaction)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        gambling_embed = interaction.response.edited_messages[0]["embed"]
        self.assertEqual(gambling_embed.title, "Help: Gambling")
        self.assertIn("ns slots", gambling_embed.description)
        self.assertIn("ns flip", gambling_embed.description)

        interaction.response.edited_messages.clear()
        view.category_select._values = ["battle"]
        await view.category_select.callback(interaction)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        battle_embed = interaction.response.edited_messages[0]["embed"]
        self.assertEqual(battle_embed.title, "Help: Battle")
        self.assertIn("ns team add", battle_embed.description)
        self.assertIn("ns team remove", battle_embed.description)
        self.assertIn("ns team list", battle_embed.description)
        self.assertIn("ns team assign", battle_embed.description)
        self.assertIn("ns team unassign", battle_embed.description)
        self.assertIn("ns team cards", battle_embed.description)
        self.assertIn("ns team active", battle_embed.description)
        self.assertIn("ns battle", battle_embed.description)

    async def test_help_view_category_option_order_includes_gambling_and_battle(self) -> None:
        view = HelpView(user_id=10)
        option_values = [option.value for option in view.category_select.options]
        self.assertIn("gambling", option_values)
        self.assertIn("battle", option_values)
        self.assertLess(option_values.index("economy"), option_values.index("gambling"))
        self.assertLess(option_values.index("gambling"), option_values.index("battle"))

    async def test_help_view_select_rejects_unauthorized_user(self) -> None:
        view = HelpView(user_id=10)
        interaction = _FakeInteraction(user_id=99)

        view.category_select._values = ["overview"]
        await view.category_select.callback(interaction)

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertIn("Only the command user", sent["embed"].description)

    async def test_drop_allows_any_user_to_claim(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        interaction = _FakeInteraction(user_id=200)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch(
            "noodswap.view_drop.execute_drop_claim",
            return_value=type("Result", (), {"is_error": False, "dupe_code": "abc"})(),
        ) as execute_claim:
            await callback(interaction)

        execute_claim.assert_called_once()
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertIn("<@200> pulled", interaction.message.replies[0]["embed"].description)

    async def test_drop_rejects_when_already_resolved(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        view.finished = True
        interaction = _FakeInteraction(user_id=100)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch("noodswap.view_drop.execute_drop_claim") as execute_claim:
            await callback(interaction)
            execute_claim.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertIn("already resolved", sent["embed"].description)

    async def test_drop_rejects_claim_when_card_already_claimed(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50), ("PEN", 60)])
        first_interaction = _FakeInteraction(user_id=200)
        second_interaction = _FakeInteraction(user_id=300)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch(
            "noodswap.view_drop.execute_drop_claim",
            return_value=type("Result", (), {"is_error": False, "dupe_code": "abc"})(),
        ) as execute_claim:
            await callback(first_interaction)
            await callback(second_interaction)

        execute_claim.assert_called_once()
        self.assertEqual(len(second_interaction.response.sent_messages), 1)
        self.assertIn("already been claimed", second_interaction.response.sent_messages[0]["embed"].description)

    async def test_drop_stays_open_until_all_cards_claimed(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50), ("PEN", 60)])
        first_interaction = _FakeInteraction(user_id=200)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch(
            "noodswap.view_drop.execute_drop_claim",
            return_value=type("Result", (), {"is_error": False, "dupe_code": "abc"})(),
        ):
            await callback(first_interaction)

        self.assertFalse(view.finished)
        self.assertTrue(view.children[0].disabled)
        self.assertFalse(view.children[1].disabled)

    async def test_drop_timeout_disables_buttons_and_edits_message(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50), ("PEN", 60)])
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(all(getattr(item, "disabled", False) for item in view.children))
        self.assertEqual(len(fake_message.edits), 1)
        self.assertEqual(fake_message.edits[0].get("view"), view)
        self.assertNotIn("embed", fake_message.edits[0])
        self.assertEqual(len(fake_message.replies), 0)

    async def test_drop_rejects_when_user_pull_cooldown_active(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        interaction = _FakeInteraction(user_id=200)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch(
            "noodswap.view_drop.execute_drop_claim",
            return_value=type("Result", (), {"is_error": True, "cooldown_remaining_seconds": 30.0})(),
        ) as execute_claim:
            await callback(interaction)

        execute_claim.assert_called_once()
        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertEqual(sent["embed"].title, "Pull Cooldown")
        self.assertTrue(sent.get("ephemeral"))

    async def test_trade_rejects_non_buyer(self) -> None:
        view = TradeView(guild_id=1, seller_id=10, buyer_id=20, card_id="SPG", dupe_code="0", amount=25)
        interaction = _FakeInteraction(user_id=30)

        with patch("noodswap.view_trade.resolve_trade_offer") as resolve_trade:
            await view._resolve(interaction, accepted=True)
            resolve_trade.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertEqual(sent["embed"].title, "Trade")

    async def test_trade_accept_success_sends_followup_and_keeps_offer(self) -> None:
        view = TradeView(guild_id=1, seller_id=10, buyer_id=20, card_id="SPG", dupe_code="0", amount=25)
        interaction = _FakeInteraction(user_id=20)

        with patch(
            "noodswap.view_trade.resolve_trade_offer",
            return_value=type("TradeResult", (), {"is_failed": False, "generation": 123, "dupe_code": "a"})(),
        ) as resolve_trade:
            await view._resolve(interaction, accepted=True)
            resolve_trade.assert_called_once()

        self.assertTrue(view.finished)
        self.assertTrue(all(getattr(item, "disabled", False) for item in view.children))
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited = interaction.response.edited_messages[0]
        self.assertEqual(edited.get("view"), view)
        self.assertNotIn("embed", edited)
        self.assertEqual(len(interaction.message.replies), 1)
        accepted = interaction.message.replies[0]
        self.assertEqual(accepted["embed"].title, "Trade Accepted")
        self.assertIn("G-123", accepted["embed"].description)

    async def test_trade_timeout_disables_buttons_and_edits_message(self) -> None:
        view = TradeView(guild_id=1, seller_id=10, buyer_id=20, card_id="SPG", dupe_code="0", amount=25)
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(all(getattr(item, "disabled", False) for item in view.children))
        self.assertEqual(len(fake_message.edits), 1)
        self.assertEqual(fake_message.edits[0]["embed"].title, "Trade Expired")

    async def test_burn_confirm_sends_followup_embed_and_keeps_prompt(self) -> None:
        view = BurnConfirmView(guild_id=1, user_id=10, instance_id=77, card_id="SPG", generation=321, delta_range=8)
        interaction = _FakeInteraction(user_id=10)

        burn_result = type(
            "BurnResult",
            (),
            {
                "is_blocked": False,
                "is_failed": False,
                "card_id": "SPG",
                "generation": 321,
                "dupe_code": "a",
                "payout": 42,
                "delta": 2,
                "locked_tags": (),
                "message": "",
            },
        )()

        with patch("noodswap.view_confirmations.execute_burn_confirmation", return_value=burn_result) as execute_burn:
            await view.confirm_button.callback(interaction)

        execute_burn.assert_called_once_with(1, 10, instance_id=77, delta_range=8)
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertNotIn("embed", interaction.response.edited_messages[0])
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertEqual(interaction.message.replies[0]["embed"].title, "**Card Burned**")

    async def test_burn_confirm_blocks_when_card_in_locked_tag(self) -> None:
        view = BurnConfirmView(guild_id=1, user_id=10, instance_id=77, card_id="SPG", generation=321, delta_range=8)
        interaction = _FakeInteraction(user_id=10)

        burn_result = type(
            "BurnResult",
            (),
            {
                "is_blocked": True,
                "is_failed": False,
                "card_id": None,
                "generation": None,
                "dupe_code": None,
                "payout": None,
                "delta": None,
                "locked_tags": ("safe",),
                "message": "",
            },
        )()

        with patch("noodswap.view_confirmations.execute_burn_confirmation", return_value=burn_result) as execute_burn:
            await view.confirm_button.callback(interaction)

        execute_burn.assert_called_once_with(1, 10, instance_id=77, delta_range=8)
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertEqual(interaction.message.replies[0]["embed"].title, "Burn Blocked")

    async def test_burn_cancel_sends_followup_embed_and_keeps_prompt(self) -> None:
        view = BurnConfirmView(guild_id=1, user_id=10, instance_id=77, card_id="SPG", generation=321, delta_range=8)
        interaction = _FakeInteraction(user_id=10)

        await view.cancel_button.callback(interaction)

        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertNotIn("embed", interaction.response.edited_messages[0])
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertEqual(interaction.message.replies[0]["embed"].title, "Burn Cancelled")

    async def test_morph_confirm_applies_and_replies_with_summary(self) -> None:
        view = MorphConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        interaction = _FakeInteraction(user_id=10)

        with patch(
            "noodswap.view_confirmations.resolve_morph_roll",
            return_value=type(
                "MorphResult",
                (),
                {
                    "is_error": False,
                    "morph_key": "black_and_white",
                    "morph_name": "Black and White",
                    "remaining_dough": 41,
                },
            )(),
        ) as resolve_morph:
            await view.confirm_button.callback(interaction)

        resolve_morph.assert_called_once()
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertEqual(len(interaction.message.replies), 1)
        sent_embed = interaction.message.replies[0]["embed"]
        self.assertEqual(sent_embed.title, "Morph Rolled")
        self.assertIn("Morph Cost: **9**", sent_embed.description)
        self.assertIn("Dough Remaining: **41**", sent_embed.description)

    async def test_morph_confirm_rejects_unauthorized_user(self) -> None:
        view = MorphConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        interaction = _FakeInteraction(user_id=99)

        with patch("noodswap.view_confirmations.resolve_morph_roll") as resolve_morph:
            await view.confirm_button.callback(interaction)
            resolve_morph.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))
        self.assertIn("Only the command user", interaction.response.sent_messages[0]["embed"].description)

    async def test_morph_timeout_clears_attachments_and_edits_embed(self) -> None:
        view = MorphConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(view.confirm_button.disabled)
        self.assertTrue(view.cancel_button.disabled)
        self.assertEqual(len(fake_message.edits), 1)
        edit_kwargs = fake_message.edits[0]
        self.assertEqual(edit_kwargs["view"], view)
        self.assertNotIn("embed", edit_kwargs)
        self.assertNotIn("attachments", edit_kwargs)

    async def test_frame_confirm_applies_and_replies_with_summary(self) -> None:
        view = FrameConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        interaction = _FakeInteraction(user_id=10)

        with patch(
            "noodswap.view_confirmations.resolve_frame_roll",
            return_value=type(
                "FrameResult",
                (),
                {
                    "is_error": False,
                    "frame_key": "buttery",
                    "frame_name": "Buttery",
                    "remaining_dough": 41,
                },
            )(),
        ) as resolve_frame:
            await view.confirm_button.callback(interaction)

        resolve_frame.assert_called_once()
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertEqual(len(interaction.message.replies), 1)
        sent_embed = interaction.message.replies[0]["embed"]
        self.assertEqual(sent_embed.title, "Frame Rolled")
        self.assertIn("Frame Cost: **9**", sent_embed.description)
        self.assertIn("Dough Remaining: **41**", sent_embed.description)

    async def test_frame_timeout_clears_attachments_and_edits_embed(self) -> None:
        view = FrameConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(view.confirm_button.disabled)
        self.assertTrue(view.cancel_button.disabled)
        self.assertEqual(len(fake_message.edits), 1)
        edit_kwargs = fake_message.edits[0]
        self.assertEqual(edit_kwargs["view"], view)
        self.assertNotIn("embed", edit_kwargs)
        self.assertNotIn("attachments", edit_kwargs)

    async def test_font_confirm_applies_and_replies_with_summary(self) -> None:
        view = FontConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        interaction = _FakeInteraction(user_id=10)

        with patch(
            "noodswap.view_confirmations.resolve_font_roll",
            return_value=type(
                "FontResult",
                (),
                {
                    "is_error": False,
                    "font_key": "serif",
                    "font_name": "Serif",
                    "remaining_dough": 41,
                },
            )(),
        ) as resolve_font:
            await view.confirm_button.callback(interaction)

        resolve_font.assert_called_once()
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertEqual(len(interaction.message.replies), 1)
        sent_embed = interaction.message.replies[0]["embed"]
        self.assertEqual(sent_embed.title, "Font Rolled")
        self.assertIn("Font Cost: **9**", sent_embed.description)
        self.assertIn("Dough Remaining: **41**", sent_embed.description)

    async def test_font_timeout_clears_attachments_and_edits_embed(self) -> None:
        view = FontConfirmView(
            guild_id=1,
            user_id=10,
            instance_id=77,
            card_id="SPG",
            generation=321,
            dupe_code="a",
            before_morph_key=None,
            before_frame_key=None,
            before_font_key=None,
            cost=9,
        )
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(view.confirm_button.disabled)
        self.assertTrue(view.cancel_button.disabled)
        self.assertEqual(len(fake_message.edits), 1)
        edit_kwargs = fake_message.edits[0]
        self.assertEqual(edit_kwargs["view"], view)
        self.assertNotIn("embed", edit_kwargs)
        self.assertNotIn("attachments", edit_kwargs)

    async def test_card_catalog_pagination_buttons_update_page(self) -> None:
        entries = [
            ("SPG", 4),
            ("PEN", 3),
            ("FUS", 2),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)

        interaction = _FakeInteraction(user_id=10)
        await view.next_page_button.callback(interaction)

        self.assertEqual(view.page_index, 1)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("PEN", edited_embed.description)

    async def test_card_catalog_rejects_unauthorized_navigation(self) -> None:
        entries = [("SPG", 4), ("PEN", 3)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)

        interaction = _FakeInteraction(user_id=99)
        await view.next_page_button.callback(interaction)

        self.assertEqual(view.page_index, 0)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))

    async def test_card_catalog_sort_select_changes_order_and_resets_page(self) -> None:
        entries = [
            ("SPG", 2),
            ("BLA", 1),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)
        view.page_index = 1

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["alphabetical"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.page_index, 0)
        self.assertEqual(view.sort_mode, "alphabetical")
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Barolo", edited_embed.description)
        self.assertIn("Sort: Alphabetical", edited_embed.footer.text)

    def test_card_catalog_defaults_to_alphabetical_sort(self) -> None:
        entries = [
            ("SPG", 2),
            ("BLA", 1),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)

        embed = view.build_embed()
        self.assertIn("Barolo", embed.description)
        self.assertIn("Sort: Alphabetical", embed.footer.text)

    async def test_card_catalog_wishes_sort_prioritizes_highest_count(self) -> None:
        entries = [
            ("SPG", 2),
            ("BLA", 1),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["wishes"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "wishes")
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Barolo", edited_embed.description)
        self.assertIn("Wishes: **3**", edited_embed.description)
        self.assertIn("Sort: Wishes", edited_embed.footer.text)

    async def test_card_catalog_sort_direction_toggle_flips_order_and_resets_page(self) -> None:
        entries = [
            ("SPG", 1),
            ("BLA", 2),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)
        interaction = _FakeInteraction(user_id=10)

        view.sort_select._values = ["wishes"]
        await view.sort_select.callback(interaction)

        view.page_index = 2
        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)

        self.assertEqual(view.page_index, 0)
        self.assertFalse(view.sort_descending)
        edited_embed = toggle_interaction.response.edited_messages[0]["embed"]
        self.assertIn("Spaghetti", edited_embed.description)
        self.assertIn("Sort: Wishes (Asc)", edited_embed.footer.text)

    async def test_card_catalog_sort_mode_resets_direction_to_default(self) -> None:
        entries = [
            ("SPG", 1),
            ("BLA", 2),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)
        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)
        self.assertTrue(view.sort_descending)

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["series"]
        await view.sort_select.callback(interaction)

        self.assertFalse(view.sort_descending)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Series (Asc)", edited_embed.footer.text)

    async def test_card_catalog_rejects_unauthorized_sort_direction_toggle(self) -> None:
        entries = [("SPG", 2), ("PEN", 3)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=1)

        interaction = _FakeInteraction(user_id=99)
        await view.sort_direction_button.callback(interaction)

        self.assertFalse(view.sort_descending)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))

    async def test_card_catalog_gallery_toggle_enables_single_card_mode(self) -> None:
        entries = [
            ("SPG", 2),
            ("BLA", 1),
            ("BAR", 3),
        ]
        view = CardCatalogView(user_id=10, entries=entries, page_size=10)

        interaction = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(interaction)

        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.gallery_toggle_button.label, "Gallery: On")
        self.assertEqual(view.total_pages, 3)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("1.", edited_embed.description)

    async def test_card_catalog_gallery_toggle_preserves_currentish_page_floor(self) -> None:
        entries = [("SPG", idx) for idx in range(25)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=10)
        view.page_index = 1

        to_gallery = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(to_gallery)
        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.page_index, 10)

        back_to_list = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(back_to_list)
        self.assertFalse(view.gallery_mode)
        self.assertEqual(view.page_index, 1)

    async def test_card_catalog_gallery_to_list_biases_backward(self) -> None:
        entries = [("SPG", idx) for idx in range(25)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=10)
        view.gallery_mode = True
        view.page_index = 16
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(interaction)

        self.assertFalse(view.gallery_mode)
        self.assertEqual(view.page_index, 1)

    async def test_card_catalog_gallery_last_page_stays_gallery_mode(self) -> None:
        entries = [("SPG", idx) for idx in range(12)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=10)
        view.gallery_mode = True
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        await view.last_page_button.callback(interaction)

        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.page_index, 11)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("12.", edited_embed.description)

    async def test_card_catalog_gallery_mode_includes_attachment_when_image_available(self) -> None:
        entries = [("SPG", 2)]
        view = CardCatalogView(user_id=10, entries=entries, page_size=10)
        view.gallery_mode = True
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        fake_file = object()
        with patch("noodswap.view_catalog.embed_image_payload", return_value=("attachment://SPG.png", fake_file)):
            await view.next_page_button.callback(interaction)

        edit_kwargs = interaction.response.edited_messages[0]
        self.assertIn("attachments", edit_kwargs)
        self.assertEqual(edit_kwargs["attachments"], [fake_file])

    async def test_paginated_lines_view_navigation_updates_page(self) -> None:
        lines = ["One", "Two", "Three"]
        view = PaginatedLinesView(user_id=10, title="Collection", lines=lines, guard_title="Collection", page_size=1)

        interaction = _FakeInteraction(user_id=10)
        await view.next_page_button.callback(interaction)

        self.assertEqual(view.page_index, 1)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertEqual(edited_embed.description, "Two")

    async def test_paginated_lines_view_rejects_unauthorized_navigation(self) -> None:
        lines = ["One", "Two"]
        view = PaginatedLinesView(user_id=10, title="Wishlist", lines=lines, guard_title="Wishlist", page_size=1)

        interaction = _FakeInteraction(user_id=99)
        await view.next_page_button.callback(interaction)

        self.assertEqual(view.page_index, 0)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))
        self.assertEqual(interaction.response.sent_messages[0]["embed"].title, "Wishlist")

    async def test_sortable_card_list_sort_select_changes_order_and_resets_page(self) -> None:
        card_ids = ["SPG", "BLA", "BAR"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=1,
        )
        view.page_index = 1

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["alphabetical"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.page_index, 0)
        self.assertEqual(view.sort_mode, "alphabetical")
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Barolo", edited_embed.description)
        self.assertIn("Sort: Alphabetical", edited_embed.footer.text)

    async def test_sortable_card_list_rejects_unauthorized_sort_select(self) -> None:
        card_ids = ["SPG", "PEN"]
        view = SortableCardListView(
            user_id=10,
            title="Wishlist",
            card_ids=card_ids,
            guard_title="Wishlist",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=99)
        view.sort_select._values = ["alphabetical"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "alphabetical")
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))
        self.assertEqual(interaction.response.sent_messages[0]["embed"].title, "Wishlist")

    async def test_sortable_card_list_wishes_sort_uses_wish_counts(self) -> None:
        card_ids = ["SPG", "BLA", "BAR"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            wish_counts={"SPG": 1, "BLA": 3, "BAR": 2},
            guard_title="Lookup",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["wishes"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "wishes")
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Black Truffle Ravioli", edited_embed.description)
        self.assertIn("Sort: Wishes", edited_embed.footer.text)

    async def test_sortable_card_list_sort_direction_toggle_flips_order_and_resets_page(self) -> None:
        card_ids = ["SPG", "BLA", "BAR"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            wish_counts={"SPG": 1, "BLA": 2, "BAR": 3},
            guard_title="Lookup",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["wishes"]
        await view.sort_select.callback(interaction)

        view.page_index = 2
        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)

        self.assertEqual(view.page_index, 0)
        self.assertFalse(view.sort_descending)
        edited_embed = toggle_interaction.response.edited_messages[0]["embed"]
        self.assertIn("Spaghetti", edited_embed.description)
        self.assertIn("Sort: Wishes (Asc)", edited_embed.footer.text)

    async def test_sortable_card_list_sort_mode_resets_direction_to_default(self) -> None:
        card_ids = ["SPG", "BLA", "BAR"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=1,
        )

        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)
        self.assertTrue(view.sort_descending)

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["series"]
        await view.sort_select.callback(interaction)

        self.assertFalse(view.sort_descending)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Series (Asc)", edited_embed.footer.text)

    async def test_sortable_card_list_rejects_unauthorized_sort_direction_toggle(self) -> None:
        card_ids = ["SPG", "PEN"]
        view = SortableCardListView(
            user_id=10,
            title="Wishlist",
            card_ids=card_ids,
            guard_title="Wishlist",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=99)
        await view.sort_direction_button.callback(interaction)

        self.assertFalse(view.sort_descending)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))

    async def test_sortable_card_list_gallery_toggle_enables_single_card_mode(self) -> None:
        card_ids = ["SPG", "BLA", "BAR"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=10,
        )

        interaction = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(interaction)

        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.gallery_toggle_button.label, "Gallery: On")
        self.assertEqual(view.total_pages, 3)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("1.", edited_embed.description)

    async def test_sortable_card_list_gallery_toggle_preserves_currentish_page_floor(self) -> None:
        card_ids = ["SPG" for _ in range(25)]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=10,
        )
        view.page_index = 1

        to_gallery = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(to_gallery)
        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.page_index, 10)

        back_to_list = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(back_to_list)
        self.assertFalse(view.gallery_mode)
        self.assertEqual(view.page_index, 1)

    async def test_sortable_card_list_gallery_to_list_biases_backward(self) -> None:
        card_ids = ["SPG" for _ in range(25)]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=10,
        )
        view.gallery_mode = True
        view.page_index = 16
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(interaction)

        self.assertFalse(view.gallery_mode)
        self.assertEqual(view.page_index, 1)

    async def test_sortable_card_list_gallery_last_page_stays_gallery_mode(self) -> None:
        card_ids = ["SPG" for _ in range(12)]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=10,
        )
        view.gallery_mode = True
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        await view.last_page_button.callback(interaction)

        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.page_index, 11)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("12.", edited_embed.description)

    async def test_sortable_collection_view_defaults_to_alphabetical_sort(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
            (3, "BAR", 90, "2"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2, "BLA": 3, "BAR": 1},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        embed = view.build_embed()
        self.assertIn("Barolo", embed.description)
        self.assertIn("Sort: Alphabetical", embed.footer.text)

    async def test_sortable_collection_view_wishes_sort(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
            (3, "BAR", 90, "2"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2, "BLA": 3, "BAR": 1},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["wishes"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "wishes")
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Black Truffle Ravioli", edited_embed.description)
        self.assertIn("Sort: Wishes", edited_embed.footer.text)

    async def test_sortable_collection_view_actual_value_sort_prioritizes_computed_value(self) -> None:
        instances = [
            (1, "SPG", 2000, "0"),
            (2, "SPG", 1, "1"),
            (3, "SPG", 1500, "2"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["actual_value"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "actual_value")
        self.assertEqual(view._sorted_instances[0][0], 2)
        self.assertEqual(view._sorted_instances[1][0], 3)
        self.assertEqual(view._sorted_instances[2][0], 1)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Actual Value", edited_embed.footer.text)

    async def test_sortable_collection_view_generation_sort_prioritizes_lowest_generation(self) -> None:
        instances = [
            (1, "SPG", 500, "0"),
            (2, "BAR", 20, "1"),
            (3, "BLA", 20, "2"),
            (4, "SPG", 10, "3"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={},
            instance_styles={},
            guard_title="Collection",
            page_size=10,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["generation"]
        await view.sort_select.callback(interaction)

        self.assertEqual(view.sort_mode, "generation")
        self.assertEqual([row[0] for row in view._sorted_instances], [4, 2, 3, 1])
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Generation", edited_embed.footer.text)

    async def test_sortable_collection_view_sort_direction_toggle_flips_order_and_resets_page(self) -> None:
        instances = [
            (1, "SPG", 500, "0"),
            (2, "BAR", 20, "1"),
            (3, "BLA", 20, "2"),
            (4, "SPG", 10, "3"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["generation"]
        await view.sort_select.callback(interaction)

        view.page_index = 2
        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)

        self.assertEqual(view.page_index, 0)
        self.assertTrue(view.sort_descending)
        self.assertEqual([row[0] for row in view._sorted_instances], [1, 2, 3, 4])
        edited_embed = toggle_interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Generation (Desc)", edited_embed.footer.text)

    async def test_sortable_collection_view_sort_mode_resets_direction_to_default(self) -> None:
        instances = [
            (1, "SPG", 500, "0"),
            (2, "BAR", 20, "1"),
            (3, "BLA", 20, "2"),
            (4, "SPG", 10, "3"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        toggle_interaction = _FakeInteraction(user_id=10)
        await view.sort_direction_button.callback(toggle_interaction)
        self.assertTrue(view.sort_descending)

        interaction = _FakeInteraction(user_id=10)
        view.sort_select._values = ["actual_value"]
        await view.sort_select.callback(interaction)

        self.assertTrue(view.sort_descending)
        edited_embed = interaction.response.edited_messages[0]["embed"]
        self.assertIn("Sort: Actual Value (Desc)", edited_embed.footer.text)

    async def test_sortable_collection_view_rejects_unauthorized_sort_direction_toggle(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2, "BLA": 3},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=99)
        await view.sort_direction_button.callback(interaction)

        self.assertFalse(view.sort_descending)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))

    async def test_sortable_collection_view_marks_locked_instances_with_emoji(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={},
            instance_styles={},
            guard_title="Collection",
            locked_instance_ids={1},
            page_size=10,
        )

        embed = view.build_embed()
        self.assertIn("🔒", embed.description)
        self.assertIn("`  `", embed.description)

    async def test_sortable_collection_view_shows_folder_emoji_before_lock_marker(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={},
            instance_styles={},
            guard_title="Collection",
            locked_instance_ids={1},
            folder_emojis_by_instance={1: "🔥", 2: "📦"},
            page_size=10,
        )

        embed = view.build_embed()
        self.assertIn("🔥 🔒", embed.description)
        self.assertIn("📦 `  `", embed.description)

    async def test_sortable_collection_view_gallery_toggle(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
            (3, "BAR", 90, "2"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2, "BLA": 3, "BAR": 1},
            instance_styles={},
            guard_title="Collection",
            page_size=10,
        )

        interaction = _FakeInteraction(user_id=10)
        await view.gallery_toggle_button.callback(interaction)

        self.assertTrue(view.gallery_mode)
        self.assertEqual(view.gallery_toggle_button.label, "Gallery: On")
        self.assertEqual(view.total_pages, 3)

    async def test_sortable_collection_view_rejects_unauthorized_navigation(self) -> None:
        instances = [
            (1, "SPG", 100, "0"),
            (2, "BLA", 120, "1"),
        ]
        view = SortableCollectionView(
            user_id=10,
            title="Caller's Collection",
            instances=instances,
            wish_counts={"SPG": 2, "BLA": 3},
            instance_styles={},
            guard_title="Collection",
            page_size=1,
        )

        interaction = _FakeInteraction(user_id=99)
        await view.next_page_button.callback(interaction)

        self.assertEqual(view.page_index, 0)
        self.assertEqual(len(interaction.response.sent_messages), 1)
        self.assertTrue(interaction.response.sent_messages[0].get("ephemeral"))
        self.assertEqual(interaction.response.sent_messages[0]["embed"].title, "Collection")

    async def test_sortable_card_list_gallery_mode_includes_attachment_when_image_available(self) -> None:
        card_ids = ["SPG"]
        view = SortableCardListView(
            user_id=10,
            title="Lookup Matches",
            card_ids=card_ids,
            guard_title="Lookup",
            page_size=10,
        )
        view.gallery_mode = True
        view._set_gallery_button_label()

        interaction = _FakeInteraction(user_id=10)
        fake_file = object()
        with patch("noodswap.view_sortable_lists.embed_image_payload", return_value=("attachment://SPG.png", fake_file)):
            await view.next_page_button.callback(interaction)

        edit_kwargs = interaction.response.edited_messages[0]
        self.assertIn("attachments", edit_kwargs)
        self.assertEqual(edit_kwargs["attachments"], [fake_file])


if __name__ == "__main__":
    unittest.main()
