import tempfile
import time
from tests.pytest_compat import TestCase
from pathlib import Path
from unittest.mock import patch

from bot import services, storage


class ServicesTests(TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._original_db_path = storage.DB_PATH
        storage.DB_PATH = Path(self._tmp_dir.name) / "test.db"
        storage.init_db()

    def tearDown(self) -> None:
        storage.DB_PATH = self._original_db_path
        self._tmp_dir.cleanup()

    def test_prepare_drop_returns_cooldown_when_recent_drop(self) -> None:
        guild_id = 1
        user_id = 10
        now = time.time()
        storage.set_last_drop_at(guild_id, user_id, now)

        prepared = services.prepare_drop(guild_id, user_id, now + 1)

        self.assertTrue(prepared.is_cooldown)
        self.assertEqual(prepared.choices, [])
        self.assertGreater(prepared.cooldown_remaining_seconds, 0)
        self.assertFalse(prepared.used_drop_ticket)

    def test_prepare_drop_returns_choices_when_ready(self) -> None:
        guild_id = 1
        user_id = 11
        now = time.time()

        prepared = services.prepare_drop(guild_id, user_id, now)

        self.assertFalse(prepared.is_cooldown)
        self.assertEqual(len(prepared.choices), 3)
        self.assertEqual(prepared.cooldown_remaining_seconds, 0.0)
        self.assertFalse(prepared.used_drop_ticket)

    def test_prepare_drop_cooldown_is_global_across_guilds_for_same_user(self) -> None:
        first_guild_id = 1
        second_guild_id = 999
        user_id = 111
        now = time.time()

        first = services.prepare_drop(first_guild_id, user_id, now)
        self.assertFalse(first.is_cooldown)

        second = services.prepare_drop(second_guild_id, user_id, now + 1)
        self.assertTrue(second.is_cooldown)
        self.assertGreater(second.cooldown_remaining_seconds, 0)
        self.assertFalse(second.used_drop_ticket)

    def test_prepare_drop_uses_drop_ticket_during_cooldown(self) -> None:
        guild_id = 1
        user_id = 112
        now = time.time()

        storage.set_last_drop_at(guild_id, user_id, now)
        purchased, starter_balance, tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 1)
        self.assertFalse(purchased)
        self.assertEqual(starter_balance, 0)
        self.assertEqual(tickets, 0)
        self.assertEqual(spent, 0)

        storage.add_starter(guild_id, user_id, 1)
        purchased, _, tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 1)
        self.assertTrue(purchased)
        self.assertEqual(tickets, 1)
        self.assertEqual(spent, 1)

        prepared = services.prepare_drop(guild_id, user_id, now + 1)
        self.assertFalse(prepared.is_cooldown)
        self.assertTrue(prepared.used_drop_ticket)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, user_id), 0)

    def test_prepare_burn_errors_without_last_pulled(self) -> None:
        prepared = services.prepare_burn(guild_id=1, user_id=20, card_code=None)

        self.assertTrue(prepared.is_error)
        self.assertEqual(
            prepared.error_message,
            "No previous pulled card found. Provide a card code, e.g. `ns burn 0`.",
        )

    def test_prepare_burn_errors_for_invalid_card_code(self) -> None:
        prepared = services.prepare_burn(guild_id=1, user_id=21, card_code="?")

        self.assertTrue(prepared.is_error)
        self.assertEqual(
            prepared.error_message,
            "Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
        )

    def test_prepare_burn_accepts_hash_prefixed_card_code(self) -> None:
        guild_id = 1
        user_id = 212
        storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        instances = storage.get_player_card_instances(guild_id, user_id)
        dupe_code = instances[0][3]

        prepared = services.prepare_burn(guild_id=guild_id, user_id=user_id, card_code=f"#{dupe_code.upper()}")

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 333)

    def test_prepare_burn_errors_when_card_code_not_owned(self) -> None:
        prepared = services.prepare_burn(guild_id=1, user_id=22, card_code="0")

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "You do not own that card code.")

    def test_prepare_burn_returns_target_and_projection(self) -> None:
        guild_id = 1
        user_id = 23
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        prepared = services.prepare_burn(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.instance_id, instance_id)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 333)
        self.assertIsNotNone(prepared.payout)
        self.assertIsNotNone(prepared.value)
        self.assertIsNotNone(prepared.base_value)
        self.assertIsNotNone(prepared.delta)
        self.assertIsNotNone(prepared.delta_range)
        self.assertIsNotNone(prepared.multiplier)

    def test_prepare_burn_rejects_locked_tagged_card(self) -> None:
        guild_id = 1
        user_id = 231
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_tag(guild_id, user_id, "safe")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "safe")
        storage.set_player_tag_locked(guild_id, user_id, "safe", True)

        prepared = services.prepare_burn(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(prepared.is_error)
        self.assertEqual(
            prepared.error_message,
            "That card is protected by locked tag(s): `safe`.",
        )

    def test_prepare_burn_rejects_locked_folder_card(self) -> None:
        guild_id = 1
        user_id = 2311
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_folder(guild_id, user_id, "vault", "📦")
        storage.assign_instance_to_folder(guild_id, user_id, instance_id, "vault")
        storage.set_player_folder_locked(guild_id, user_id, "vault", True)

        prepared = services.prepare_burn(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(prepared.is_error)
        if prepared.error_message is None:
            return
        self.assertIn("locked folder", prepared.error_message)
        self.assertIn("`vault`", prepared.error_message)

    def test_execute_burn_confirmation_returns_blocked_for_locked_tags(self) -> None:
        guild_id = 1
        user_id = 232
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_tag(guild_id, user_id, "safe")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "safe")
        storage.set_player_tag_locked(guild_id, user_id, "safe", True)

        result = services.execute_burn_confirmation(
            guild_id,
            user_id,
            instance_id=instance_id,
            delta_range=8,
        )

        self.assertTrue(result.is_blocked)
        self.assertEqual(result.locked_tags, ("safe",))

    def test_execute_burn_confirmation_returns_blocked_for_locked_folder(self) -> None:
        guild_id = 1
        user_id = 2321
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_folder(guild_id, user_id, "vault", "📦")
        storage.assign_instance_to_folder(guild_id, user_id, instance_id, "vault")
        storage.set_player_folder_locked(guild_id, user_id, "vault", True)

        result = services.execute_burn_confirmation(
            guild_id,
            user_id,
            instance_id=instance_id,
            delta_range=8,
        )

        self.assertTrue(result.is_blocked)
        self.assertEqual(result.locked_tags, ("folder:vault",))

    def test_execute_burn_confirmation_returns_failed_when_instance_missing(
        self,
    ) -> None:
        result = services.execute_burn_confirmation(1, 233, instance_id=999_999, delta_range=8)

        self.assertTrue(result.is_failed)
        self.assertEqual(result.message, "That card instance is no longer available.")

    def test_execute_burn_confirmation_burns_and_awards_dough(self) -> None:
        guild_id = 1
        user_id = 234
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        dough_before, _, _ = storage.get_player_info(guild_id, user_id)

        result = services.execute_burn_confirmation(
            guild_id,
            user_id,
            instance_id=instance_id,
            delta_range=8,
        )

        self.assertTrue(result.is_burned)
        self.assertEqual(result.card_id, "SPG")
        self.assertEqual(result.generation, 333)
        self.assertIsNotNone(result.payout)
        self.assertIsNotNone(result.delta)
        self.assertIsNone(storage.get_instance_by_id(guild_id, instance_id))
        dough_after, _, _ = storage.get_player_info(guild_id, user_id)
        self.assertEqual(dough_after, dough_before + int(result.payout or 0))

    def test_prepare_burn_batch_skips_locked_targets(self) -> None:
        guild_id = 1
        user_id = 235
        open_instance = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        locked_instance = storage.add_card_to_player(guild_id, user_id, "PEN", 444)
        storage.create_player_tag(guild_id, user_id, "safe")
        storage.assign_tag_to_instance(guild_id, user_id, locked_instance, "safe")
        storage.set_player_tag_locked(guild_id, user_id, "safe", True)

        targets = [
            (open_instance, "SPG", 333, "0"),
            (locked_instance, "PEN", 444, "1"),
        ]

        prepared = services.prepare_burn_batch(guild_id, user_id, targets)

        self.assertFalse(prepared.is_error)
        self.assertEqual(len(prepared.items), 1)
        self.assertEqual(prepared.items[0].instance_id, open_instance)
        self.assertEqual(len(prepared.skipped_items), 1)
        self.assertIn("locked tag(s)", prepared.skipped_items[0])

    def test_execute_burn_batch_confirmation_burns_available_and_skips_locked(
        self,
    ) -> None:
        guild_id = 1
        user_id = 236
        open_instance = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        locked_instance = storage.add_card_to_player(guild_id, user_id, "PEN", 444)
        storage.create_player_tag(guild_id, user_id, "safe")
        storage.assign_tag_to_instance(guild_id, user_id, locked_instance, "safe")
        storage.set_player_tag_locked(guild_id, user_id, "safe", True)

        result = services.execute_burn_batch_confirmation(
            guild_id,
            user_id,
            burn_targets=[(open_instance, 8), (locked_instance, 9)],
        )

        self.assertTrue(result.is_partial)
        self.assertEqual(len(result.burned_entries), 1)
        self.assertIsNone(storage.get_instance_by_id(guild_id, open_instance))
        self.assertIsNotNone(storage.get_instance_by_id(guild_id, locked_instance))
        self.assertEqual(len(result.skipped_instances), 1)
        self.assertEqual(result.skipped_instances[0][0], locked_instance)

    def test_execute_burn_batch_confirmation_burns_all_and_awards_dough(self) -> None:
        guild_id = 1
        user_id = 237
        first_instance = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        second_instance = storage.add_card_to_player(guild_id, user_id, "PEN", 444)
        dough_before, _, _ = storage.get_player_info(guild_id, user_id)

        result = services.execute_burn_batch_confirmation(
            guild_id,
            user_id,
            burn_targets=[(first_instance, 8), (second_instance, 9)],
        )

        self.assertTrue(result.is_burned)
        self.assertEqual(len(result.burned_entries), 2)
        total_payout = sum(entry.payout for entry in result.burned_entries)
        self.assertIsNone(storage.get_instance_by_id(guild_id, first_instance))
        self.assertIsNone(storage.get_instance_by_id(guild_id, second_instance))
        dough_after, _, _ = storage.get_player_info(guild_id, user_id)
        self.assertEqual(dough_after, dough_before + total_payout)

    def test_prepare_morph_returns_preview_without_applying(self) -> None:
        guild_id = 1
        user_id = 24
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        result = services.prepare_morph(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.card_id, "SPG")
        self.assertIsNone(result.morph_key)
        self.assertIsNone(result.morph_name)
        self.assertIsNotNone(result.cost)
        self.assertEqual(storage.get_instance_morph(guild_id, instance_id), None)

    def test_confirm_morph_applies_black_and_white_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 240
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        result = services.confirm_morph(
            guild_id,
            user_id,
            instance_id=instance_id,
            card_id="SPG",
            generation=333,
            dupe_code="0",
            morph_key="black_and_white",
            morph_name="Black and White",
            rolled_rarity="common",
            rolled_multiplier=1.0,
            cost=1,
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.morph_key, "black_and_white")
        self.assertIsNotNone(result.remaining_dough)
        self.assertEqual(storage.get_instance_morph(guild_id, instance_id), "black_and_white")

    def test_prepare_morph_rejects_when_no_new_morphs_available(self) -> None:
        guild_id = 1
        user_id = 25
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.apply_morph_to_instance(guild_id, user_id, instance_id, "black_and_white", 1)

        with patch("bot.services.AVAILABLE_MORPHS", ["black_and_white"]):
            result = services.prepare_morph(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "No new morphs are currently available for this card.")

    def test_prepare_frame_returns_preview_without_applying(self) -> None:
        guild_id = 1
        user_id = 26
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        with patch(
            "bot.services.available_frame_keys",
            return_value=["buttery", "gilded", "drizzled"],
        ):
            result = services.prepare_frame(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.card_id, "SPG")
        self.assertIsNone(result.frame_key)
        self.assertIsNone(result.frame_name)
        self.assertIsNotNone(result.cost)
        self.assertEqual(storage.get_instance_frame(guild_id, instance_id), None)

    def test_confirm_frame_applies_buttery_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 260
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        result = services.confirm_frame(
            guild_id,
            user_id,
            instance_id=instance_id,
            card_id="SPG",
            generation=333,
            dupe_code="0",
            frame_key="buttery",
            frame_name="Buttery",
            rolled_rarity="common",
            rolled_multiplier=1.0,
            cost=1,
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.frame_key, "buttery")
        self.assertIsNotNone(result.remaining_dough)
        self.assertEqual(storage.get_instance_frame(guild_id, instance_id), "buttery")

    def test_prepare_frame_rejects_when_no_new_frames_available(self) -> None:
        guild_id = 1
        user_id = 27
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.apply_frame_to_instance(guild_id, user_id, instance_id, "buttery", 1)

        with patch("bot.services.available_frame_keys", return_value=["buttery"]):
            result = services.prepare_frame(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "No new frames are currently available for this card.")

    def test_prepare_font_returns_preview_without_applying(self) -> None:
        guild_id = 1
        user_id = 28
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        result = services.prepare_font(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.card_id, "SPG")
        self.assertIsNone(result.font_key)
        self.assertIsNone(result.font_name)
        self.assertIsNotNone(result.cost)
        self.assertEqual(storage.get_instance_font(guild_id, instance_id), None)

    def test_confirm_font_applies_serif_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 280
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        result = services.confirm_font(
            guild_id,
            user_id,
            instance_id=instance_id,
            card_id="SPG",
            generation=333,
            dupe_code="0",
            font_key="serif",
            font_name="Serif",
            rolled_rarity="uncommon",
            rolled_multiplier=1.02,
            cost=1,
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.instance_id, instance_id)
        self.assertEqual(result.font_key, "serif")
        self.assertIsNotNone(result.remaining_dough)
        self.assertEqual(storage.get_instance_font(guild_id, instance_id), "serif")

    def test_prepare_font_rejects_when_no_new_fonts_available(self) -> None:
        guild_id = 1
        user_id = 29
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.apply_font_to_instance(guild_id, user_id, instance_id, "serif", 1)

        with patch("bot.services.AVAILABLE_FONTS", ["serif"]):
            result = services.prepare_font(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "No new fonts are currently available for this card.")

    def test_execute_marry_errors_without_last_pulled(self) -> None:
        result = services.execute_marry(guild_id=1, user_id=30, card_code=None)

        self.assertTrue(result.is_error)
        self.assertEqual(
            result.error_message,
            "No previous pulled card found. Use `ns marry <card_code>` or pull from `ns drop` first.",
        )

    def test_execute_marry_errors_for_invalid_card_code(self) -> None:
        result = services.execute_marry(guild_id=1, user_id=31, card_code="?")

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "You can only marry a card code you own.")

    def test_execute_marry_with_card_code_succeeds(self) -> None:
        guild_id = 1
        user_id = 32
        storage.add_card_to_player(guild_id, user_id, "SPG", 400)
        storage.add_card_to_player(guild_id, user_id, "SPG", 40)
        instances = storage.get_player_card_instances(guild_id, user_id)
        first_code = instances[0][3]

        result = services.execute_marry(guild_id=guild_id, user_id=user_id, card_code=first_code)

        self.assertFalse(result.is_error)
        self.assertEqual(result.card_id, instances[0][1])
        self.assertEqual(result.generation, instances[0][2])
        self.assertEqual(result.dupe_code, instances[0][3])

    def test_execute_marry_without_card_uses_last_pulled(self) -> None:
        guild_id = 1
        user_id = 33
        storage.add_card_to_player(guild_id, user_id, "PEN", 222)

        result = services.execute_marry(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertFalse(result.is_error)
        self.assertEqual(result.card_id, "PEN")
        self.assertEqual(result.generation, 222)

    def test_execute_divorce_errors_when_not_married(self) -> None:
        result = services.execute_divorce(guild_id=1, user_id=40)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "You are not married right now.")

    def test_execute_divorce_returns_card_when_married(self) -> None:
        guild_id = 1
        user_id = 41
        storage.add_card_to_player(guild_id, user_id, "SPG", 111)
        instances = storage.get_player_card_instances(guild_id, user_id)
        only_code = instances[0][3]
        marry_result = services.execute_marry(guild_id=guild_id, user_id=user_id, card_code=only_code)
        self.assertFalse(marry_result.is_error)

        divorce_result = services.execute_divorce(guild_id=guild_id, user_id=user_id)

        self.assertFalse(divorce_result.is_error)
        self.assertEqual(divorce_result.card_id, "SPG")
        self.assertEqual(divorce_result.generation, 111)

    def test_prepare_trade_offer_rejects_self_trade(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=50,
            buyer_id=50,
            buyer_is_bot=False,
            card_code="0",
            mode="dough",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "You cannot trade with yourself.")

    def test_prepare_trade_offer_rejects_bot_buyer(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=51,
            buyer_id=52,
            buyer_is_bot=True,
            card_code="0",
            mode="dough",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "You cannot trade with bots.")

    def test_prepare_trade_offer_rejects_negative_amount(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=53,
            buyer_id=54,
            buyer_is_bot=False,
            card_code="0",
            mode="dough",
            amount=-1,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "Amount must be greater than 0.")

    def test_prepare_trade_offer_rejects_zero_amount(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=53,
            buyer_id=54,
            buyer_is_bot=False,
            card_code="0",
            mode="dough",
            amount=0,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "Amount must be greater than 0.")

    def test_prepare_trade_offer_rejects_invalid_mode(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=53,
            buyer_id=54,
            buyer_is_bot=False,
            card_code="0",
            mode="gems",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertIn("Invalid trade mode", prepared.error_message or "")

    def test_prepare_trade_offer_rejects_invalid_card_code(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=55,
            buyer_id=56,
            buyer_is_bot=False,
            card_code="?",
            mode="dough",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(
            prepared.error_message,
            "Invalid card code. Use format like `0`, `a`, `10`, or `#10`.",
        )

    def test_prepare_trade_offer_rejects_unowned_card(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=57,
            buyer_id=58,
            buyer_is_bot=False,
            card_code="0",
            mode="dough",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "You do not own that card code.")

    def test_prepare_trade_offer_succeeds_with_normalized_card_code(self) -> None:
        guild_id = 1
        seller_id = 59
        storage.add_card_to_player(guild_id, seller_id, "SPG", 444)
        instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = instances[0][3]

        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=60,
            buyer_is_bot=False,
            card_code=dupe_code.upper(),
            mode="dough",
            amount=10,
        )

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 444)
        self.assertIsNotNone(prepared.terms)
        self.assertEqual(prepared.terms.mode, "dough")
        self.assertEqual(prepared.terms.amount, 10)

    def test_prepare_trade_offer_accepts_hash_prefixed_card_code(self) -> None:
        guild_id = 1
        seller_id = 591
        storage.add_card_to_player(guild_id, seller_id, "SPG", 444)
        instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = instances[0][3]

        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=60,
            buyer_is_bot=False,
            card_code=f"#{dupe_code.upper()}",
            mode="dough",
            amount=10,
        )

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 444)

    def test_prepare_trade_offer_starter_mode_stores_terms(self) -> None:
        guild_id = 1
        seller_id = 592
        storage.add_card_to_player(guild_id, seller_id, "SPG", 200)
        instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = instances[0][3]

        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=593,
            buyer_is_bot=False,
            card_code=dupe_code,
            mode="starter",
            amount=5,
        )

        self.assertFalse(prepared.is_error)
        self.assertIsNotNone(prepared.terms)
        self.assertEqual(prepared.terms.mode, "starter")  # type: ignore[union-attr]
        self.assertEqual(prepared.terms.amount, 5)  # type: ignore[union-attr]

    def test_prepare_trade_offer_tickets_mode_aliases_normalised(self) -> None:
        guild_id = 1
        seller_id = 594
        storage.add_card_to_player(guild_id, seller_id, "SPG", 300)
        instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = instances[0][3]

        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=595,
            buyer_is_bot=False,
            card_code=dupe_code,
            mode="drop",
            amount=2,
        )

        self.assertFalse(prepared.is_error)
        self.assertIsNotNone(prepared.terms)
        self.assertEqual(prepared.terms.mode, "drop")  # type: ignore[union-attr]
        self.assertEqual(prepared.terms.amount, 2)  # type: ignore[union-attr]

    def test_prepare_trade_offer_card_mode_requires_buyer_to_own_req_card(self) -> None:
        guild_id = 1
        seller_id = 596
        buyer_id = 597
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        seller_dupe = seller_instances[0][3]

        # buyer has no card — use a req code different from the seller's dupe to avoid the
        # "cannot request the same card" guard and reach the ownership check.
        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            buyer_is_bot=False,
            card_code=seller_dupe,
            mode="card",
            req_card_code="zz",
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "The other player does not own that card code.")

    def test_prepare_trade_offer_card_mode_succeeds_when_both_own_cards(self) -> None:
        guild_id = 1
        seller_id = 598
        buyer_id = 599
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_card_to_player(guild_id, buyer_id, "PEN", 200)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        seller_dupe = seller_instances[0][3]
        buyer_dupe = buyer_instances[0][3]

        prepared = services.prepare_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            buyer_is_bot=False,
            card_code=seller_dupe,
            mode="card",
            req_card_code=buyer_dupe,
        )

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertIsNotNone(prepared.terms)
        self.assertEqual(prepared.terms.mode, "card")  # type: ignore[union-attr]
        self.assertEqual(prepared.terms.req_card_id, "PEN")  # type: ignore[union-attr]
        self.assertEqual(prepared.terms.req_dupe_code, buyer_dupe)  # type: ignore[union-attr]

    def test_execute_drop_claim_returns_cooldown_error_when_pull_not_ready(
        self,
    ) -> None:
        guild_id = 1
        user_id = 600
        now = time.time()

        first_claim = services.execute_drop_claim(
            guild_id,
            user_id,
            "SPG",
            500,
            now=now,
            pull_cooldown_seconds=240,
        )
        self.assertFalse(first_claim.is_error)

        second_claim = services.execute_drop_claim(
            guild_id,
            user_id,
            "PEN",
            550,
            now=now + 1,
            pull_cooldown_seconds=240,
        )
        self.assertTrue(second_claim.is_error)
        self.assertGreater(second_claim.cooldown_remaining_seconds or 0.0, 0.0)

    def test_execute_drop_claim_returns_resolved_dupe_code(self) -> None:
        guild_id = 1
        user_id = 601

        claim = services.execute_drop_claim(
            guild_id,
            user_id,
            "SPG",
            777,
            now=time.time(),
            pull_cooldown_seconds=240,
        )

        self.assertFalse(claim.is_error)
        self.assertEqual(claim.card_id, "SPG")
        self.assertEqual(claim.generation, 777)
        self.assertIsNotNone(claim.instance_id)
        self.assertIsNotNone(claim.dupe_code)

    def test_resolve_trade_offer_denied_returns_denied_status(self) -> None:
        result = services.resolve_trade_offer(
            guild_id=1,
            seller_id=700,
            buyer_id=701,
            card_id="SPG",
            dupe_code="0",
            terms=services.TradeTerms(mode="dough", amount=25),
            accepted=False,
        )

        self.assertTrue(result.is_denied)
        self.assertEqual(result.message, "The trade was denied.")

    def test_resolve_trade_offer_accepted_transfers_instance(self) -> None:
        guild_id = 1
        seller_id = 710
        buyer_id = 711
        storage.add_card_to_player(guild_id, seller_id, "SPG", 420)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = seller_instances[0][3]
        storage.add_dough(guild_id, buyer_id, 100)

        result = services.resolve_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=services.TradeTerms(mode="dough", amount=25),
            accepted=True,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(result.generation, 420)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(buyer_instances), 1)
        self.assertEqual(buyer_instances[0][1], "SPG")

    def test_resolve_trade_offer_starter_mode_accepted(self) -> None:
        guild_id = 1
        seller_id = 712
        buyer_id = 713
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = seller_instances[0][3]
        storage.add_starter(guild_id, buyer_id, 10)

        result = services.resolve_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=services.TradeTerms(mode="starter", amount=5),
            accepted=True,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(storage.get_player_starter(guild_id, seller_id), 5)
        self.assertEqual(storage.get_player_starter(guild_id, buyer_id), 5)

    def test_resolve_trade_offer_tickets_mode_accepted(self) -> None:
        guild_id = 1
        seller_id = 714
        buyer_id = 715
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = seller_instances[0][3]
        storage.add_starter(guild_id, buyer_id, 3)
        storage.buy_drop_tickets_with_starter(guild_id, buyer_id, 3)

        result = services.resolve_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=services.TradeTerms(mode="drop", amount=2),
            accepted=True,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, seller_id), 2)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, buyer_id), 1)

    def test_resolve_trade_offer_pull_tickets_mode_accepted(self) -> None:
        guild_id = 1
        seller_id = 1714
        buyer_id = 1715
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        dupe_code = seller_instances[0][3]
        storage.add_starter(guild_id, buyer_id, 3)
        storage.buy_pull_tickets_with_starter(guild_id, buyer_id, 3)

        result = services.resolve_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=services.TradeTerms(mode="pull", amount=2),
            accepted=True,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(storage.get_player_pull_tickets(guild_id, seller_id), 2)
        self.assertEqual(storage.get_player_pull_tickets(guild_id, buyer_id), 1)

    def test_resolve_trade_offer_card_mode_accepted_swaps_both_cards(self) -> None:
        guild_id = 1
        seller_id = 716
        buyer_id = 717
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_card_to_player(guild_id, buyer_id, "PEN", 200)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        seller_dupe = seller_instances[0][3]
        buyer_dupe = buyer_instances[0][3]

        result = services.resolve_trade_offer(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=seller_dupe,
            terms=services.TradeTerms(
                mode="card",
                req_card_id="PEN",
                req_generation=200,
                req_dupe_code=buyer_dupe,
            ),
            accepted=True,
        )

        self.assertTrue(result.is_accepted)
        self.assertEqual(result.received_card_id, "PEN")
        self.assertEqual(result.received_generation, 200)

        seller_after = storage.get_player_card_instances(guild_id, seller_id)
        buyer_after = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(seller_after), 1)
        self.assertEqual(seller_after[0][1], "PEN")
        self.assertEqual(len(buyer_after), 1)
        self.assertEqual(buyer_after[0][1], "SPG")

    def test_resolve_morph_roll_applies_selected_morph(self) -> None:
        guild_id = 1
        user_id = 720
        storage.add_dough(guild_id, user_id, 50)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        with patch("bot.services.weighted_trait_choice", return_value="black_and_white"):
            result = services.resolve_morph_roll(
                guild_id,
                user_id,
                instance_id=instance_id,
                card_id="SPG",
                generation=333,
                dupe_code="0",
                current_morph_key=None,
                cost=1,
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.morph_key, "black_and_white")
        self.assertEqual(result.rolled_rarity, "common")
        self.assertEqual(result.rolled_multiplier, 1.0)
        self.assertEqual(storage.get_instance_morph(guild_id, instance_id), "black_and_white")

    def test_resolve_frame_roll_applies_selected_frame(self) -> None:
        guild_id = 1
        user_id = 721
        storage.add_dough(guild_id, user_id, 50)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        with (
            patch(
                "bot.services.available_frame_keys",
                return_value=["buttery", "gilded", "drizzled"],
            ),
            patch("bot.services.weighted_trait_choice", return_value="buttery"),
        ):
            result = services.resolve_frame_roll(
                guild_id,
                user_id,
                instance_id=instance_id,
                card_id="SPG",
                generation=333,
                dupe_code="0",
                current_frame_key=None,
                cost=1,
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.frame_key, "buttery")
        self.assertEqual(result.rolled_rarity, "mythical")
        self.assertEqual(result.rolled_multiplier, 1.28)
        self.assertEqual(storage.get_instance_frame(guild_id, instance_id), "buttery")

    def test_resolve_font_roll_applies_selected_font(self) -> None:
        guild_id = 1
        user_id = 722
        storage.add_dough(guild_id, user_id, 50)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

        with patch("bot.services.weighted_trait_choice", return_value="serif"):
            result = services.resolve_font_roll(
                guild_id,
                user_id,
                instance_id=instance_id,
                card_id="SPG",
                generation=333,
                dupe_code="0",
                current_font_key=None,
                cost=1,
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.font_key, "serif")
        self.assertEqual(result.rolled_rarity, "uncommon")
        self.assertEqual(result.rolled_multiplier, 1.02)
        self.assertEqual(storage.get_instance_font(guild_id, instance_id), "serif")
