import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from noodswap import services, storage


class ServicesTests(unittest.TestCase):
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

    def test_prepare_drop_returns_choices_when_ready(self) -> None:
        guild_id = 1
        user_id = 11
        now = time.time()

        prepared = services.prepare_drop(guild_id, user_id, now)

        self.assertFalse(prepared.is_cooldown)
        self.assertEqual(len(prepared.choices), 3)
        self.assertEqual(prepared.cooldown_remaining_seconds, 0.0)

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
        self.assertEqual(prepared.error_message, "Invalid card code. Use format like `0`, `a`, `10`, or `#10`.")

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

        with patch("noodswap.services.AVAILABLE_MORPHS", ["black_and_white"]):
            result = services.prepare_morph(guild_id=guild_id, user_id=user_id, card_code=None)

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_message, "No new morphs are currently available for this card.")

    def test_prepare_frame_returns_preview_without_applying(self) -> None:
        guild_id = 1
        user_id = 26
        storage.add_dough(guild_id, user_id, 200)
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)

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

        with patch("noodswap.services.available_frame_keys", return_value=["buttery"]):
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

        with patch("noodswap.services.AVAILABLE_FONTS", ["serif"]):
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
            amount=-1,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "Amount must be 0 or greater.")

    def test_prepare_trade_offer_rejects_invalid_card_code(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=55,
            buyer_id=56,
            buyer_is_bot=False,
            card_code="?",
            amount=10,
        )

        self.assertTrue(prepared.is_error)
        self.assertEqual(prepared.error_message, "Invalid card code. Use format like `0`, `a`, `10`, or `#10`.")

    def test_prepare_trade_offer_rejects_unowned_card(self) -> None:
        prepared = services.prepare_trade_offer(
            guild_id=1,
            seller_id=57,
            buyer_id=58,
            buyer_is_bot=False,
            card_code="0",
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
            amount=10,
        )

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 444)

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
            amount=10,
        )

        self.assertFalse(prepared.is_error)
        self.assertEqual(prepared.card_id, "SPG")
        self.assertEqual(prepared.generation, 444)


if __name__ == "__main__":
    unittest.main()
