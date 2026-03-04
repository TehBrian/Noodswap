import unittest
from unittest.mock import patch

from noodswap.views import BurnConfirmView, CardCatalogView, DropView, PaginatedLinesView, TradeView


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


class _FakeMessage:
    class _FakeChannel:
        def __init__(self):
            self.sent_messages: list[dict] = []

        async def send(self, **kwargs):
            self.sent_messages.append(kwargs)

    def __init__(self):
        self.edits: list[dict] = []
        self.channel = self._FakeChannel()

    async def edit(self, **kwargs):
        self.edits.append(kwargs)


class ViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_drop_rejects_unauthorized_puller(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        interaction = _FakeInteraction(user_id=200)
        callback = view._make_pull_callback("SPG", 50)

        with patch("noodswap.views.add_card_to_player") as add_card:
            await callback(interaction)
            add_card.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertEqual(sent["embed"].title, "Drop")

    async def test_drop_rejects_when_already_resolved(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        view.finished = True
        interaction = _FakeInteraction(user_id=100)
        callback = view._make_pull_callback("SPG", 50)

        with patch("noodswap.views.add_card_to_player") as add_card:
            await callback(interaction)
            add_card.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertIn("already resolved", sent["embed"].description)

    async def test_drop_timeout_disables_buttons_and_edits_message(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50), ("PEN", 60)])
        fake_message = _FakeMessage()
        view.message = fake_message

        await view.on_timeout()

        self.assertTrue(all(getattr(item, "disabled", False) for item in view.children))
        self.assertEqual(len(fake_message.edits), 1)
        self.assertEqual(fake_message.edits[0].get("view"), view)
        self.assertNotIn("embed", fake_message.edits[0])
        self.assertEqual(len(fake_message.channel.sent_messages), 1)
        self.assertEqual(fake_message.channel.sent_messages[0]["embed"].title, "Drop Expired")

    async def test_trade_rejects_non_buyer(self) -> None:
        view = TradeView(guild_id=1, seller_id=10, buyer_id=20, card_id="SPG", dupe_code="0", amount=25)
        interaction = _FakeInteraction(user_id=30)

        with patch("noodswap.views.execute_trade") as execute_trade:
            await view._resolve(interaction, accepted=True)
            execute_trade.assert_not_called()

        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertTrue(sent.get("ephemeral"))
        self.assertEqual(sent["embed"].title, "Trade")

    async def test_trade_accept_success_sends_followup_and_keeps_offer(self) -> None:
        view = TradeView(guild_id=1, seller_id=10, buyer_id=20, card_id="SPG", dupe_code="0", amount=25)
        interaction = _FakeInteraction(user_id=20)

        with patch("noodswap.views.execute_trade", return_value=(True, "", 123, "a")) as execute_trade:
            await view._resolve(interaction, accepted=True)
            execute_trade.assert_called_once()

        self.assertTrue(view.finished)
        self.assertTrue(all(getattr(item, "disabled", False) for item in view.children))
        self.assertEqual(len(interaction.response.edited_messages), 1)
        edited = interaction.response.edited_messages[0]
        self.assertEqual(edited.get("view"), view)
        self.assertNotIn("embed", edited)
        self.assertEqual(len(interaction.followup.sent_messages), 1)
        accepted = interaction.followup.sent_messages[0]
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

        with (
            patch("noodswap.views.burn_instance", return_value=("SPG", 321, "a")) as burn,
            patch("noodswap.views.get_burn_payout", return_value=(42, 40, 38, 2, 1.05, 8)) as payout,
            patch("noodswap.views.add_dough") as add_dough,
        ):
            await view.confirm_button.callback(interaction)

        burn.assert_called_once_with(1, 10, 77)
        payout.assert_called_once_with("SPG", 321, 8)
        add_dough.assert_called_once_with(1, 10, 42)
        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertNotIn("embed", interaction.response.edited_messages[0])
        self.assertEqual(len(interaction.followup.sent_messages), 1)
        self.assertEqual(interaction.followup.sent_messages[0]["embed"].title, "**Card Burned**")

    async def test_burn_cancel_sends_followup_embed_and_keeps_prompt(self) -> None:
        view = BurnConfirmView(guild_id=1, user_id=10, instance_id=77, card_id="SPG", generation=321, delta_range=8)
        interaction = _FakeInteraction(user_id=10)

        await view.cancel_button.callback(interaction)

        self.assertTrue(view.finished)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(interaction.response.edited_messages[0].get("view"), view)
        self.assertNotIn("embed", interaction.response.edited_messages[0])
        self.assertEqual(len(interaction.followup.sent_messages), 1)
        self.assertEqual(interaction.followup.sent_messages[0]["embed"].title, "Burn Cancelled")

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


if __name__ == "__main__":
    unittest.main()
