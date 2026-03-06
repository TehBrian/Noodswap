import unittest
from unittest.mock import patch

from noodswap.views import (
    BurnConfirmView,
    CardCatalogView,
    DropView,
    PaginatedLinesView,
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
    async def test_drop_allows_any_user_to_claim(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        interaction = _FakeInteraction(user_id=200)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with (
            patch("noodswap.views.add_card_to_player", return_value=777) as add_card,
            patch("noodswap.views.get_instance_by_id", return_value=(777, "SPG", 50, "abc")),
            patch("noodswap.views.consume_pull_cooldown_if_ready", return_value=0.0),
        ):
            await callback(interaction)

        add_card.assert_called_once_with(1, 200, "SPG", 50)
        self.assertEqual(len(interaction.response.edited_messages), 1)
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertIn("<@200> pulled", interaction.message.replies[0]["embed"].description)

    async def test_drop_rejects_when_already_resolved(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50)])
        view.finished = True
        interaction = _FakeInteraction(user_id=100)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with patch("noodswap.views.add_card_to_player") as add_card:
            await callback(interaction)
            add_card.assert_not_called()

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

        with (
            patch("noodswap.views.add_card_to_player", return_value=777) as add_card,
            patch("noodswap.views.get_instance_by_id", return_value=(777, "SPG", 50, "abc")),
            patch("noodswap.views.consume_pull_cooldown_if_ready", return_value=0.0),
        ):
            await callback(first_interaction)
            await callback(second_interaction)

        add_card.assert_called_once_with(1, 200, "SPG", 50)
        self.assertEqual(len(second_interaction.response.sent_messages), 1)
        self.assertIn("already been claimed", second_interaction.response.sent_messages[0]["embed"].description)

    async def test_drop_stays_open_until_all_cards_claimed(self) -> None:
        view = DropView(guild_id=1, user_id=100, choices=[("SPG", 50), ("PEN", 60)])
        first_interaction = _FakeInteraction(user_id=200)
        callback = view.children[0].callback
        self.assertIsNotNone(callback)

        with (
            patch("noodswap.views.add_card_to_player", return_value=777),
            patch("noodswap.views.get_instance_by_id", return_value=(777, "SPG", 50, "abc")),
            patch("noodswap.views.consume_pull_cooldown_if_ready", return_value=0.0),
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

        with (
            patch("noodswap.views.consume_pull_cooldown_if_ready", return_value=30.0) as consume,
            patch("noodswap.views.add_card_to_player") as add_card,
        ):
            await callback(interaction)

        consume.assert_called_once()
        add_card.assert_not_called()
        self.assertEqual(len(interaction.response.sent_messages), 1)
        sent = interaction.response.sent_messages[0]
        self.assertEqual(sent["embed"].title, "Pull Cooldown")
        self.assertTrue(sent.get("ephemeral"))

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

        with (
            patch("noodswap.views.get_locked_tags_for_instance", return_value=[]),
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
        self.assertEqual(len(interaction.message.replies), 1)
        self.assertEqual(interaction.message.replies[0]["embed"].title, "**Card Burned**")

    async def test_burn_confirm_blocks_when_card_in_locked_tag(self) -> None:
        view = BurnConfirmView(guild_id=1, user_id=10, instance_id=77, card_id="SPG", generation=321, delta_range=8)
        interaction = _FakeInteraction(user_id=10)

        with (
            patch("noodswap.views.get_locked_tags_for_instance", return_value=["safe"]),
            patch("noodswap.views.burn_instance") as burn,
        ):
            await view.confirm_button.callback(interaction)

        burn.assert_not_called()
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
        with patch("noodswap.views.embed_image_payload", return_value=("attachment://SPG.png", fake_file)):
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
        with patch("noodswap.views.embed_image_payload", return_value=("attachment://SPG.png", fake_file)):
            await view.next_page_button.callback(interaction)

        edit_kwargs = interaction.response.edited_messages[0]
        self.assertIn("attachments", edit_kwargs)
        self.assertEqual(edit_kwargs["attachments"], [fake_file])


if __name__ == "__main__":
    unittest.main()
