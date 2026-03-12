import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from noodswap import storage
from noodswap.services import TradeTerms


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._original_db_path = storage.DB_PATH
        storage.DB_PATH = Path(self._tmp_dir.name) / "test.db"

    def tearDown(self) -> None:
        storage.DB_PATH = self._original_db_path
        self._tmp_dir.cleanup()

    def test_init_db_creates_schema_version_and_columns(self) -> None:
        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row[0]), storage.TARGET_SCHEMA_VERSION)

            columns = conn.execute("PRAGMA table_info(players)").fetchall()
            column_names = {str(column[1]) for column in columns}
            self.assertIn("married_instance_id", column_names)
            self.assertIn("last_dropped_instance_id", column_names)
            self.assertIn("starter", column_names)
            self.assertIn("drop_tickets", column_names)
            self.assertIn("last_slots_at", column_names)
            self.assertIn("last_flip_at", column_names)
            self.assertIn("active_team_name", column_names)
            self.assertIn("monopoly_position", column_names)
            self.assertIn("last_monopoly_roll_at", column_names)
            self.assertIn("monopoly_in_jail", column_names)
            self.assertIn("monopoly_jail_roll_attempts", column_names)
            self.assertIn("monopoly_consecutive_doubles", column_names)

            pot_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'gambling_pot'").fetchone()
            self.assertIsNotNone(pot_row)

            instance_columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            instance_column_names = {str(column[1]) for column in instance_columns}
            self.assertIn("morph_key", instance_column_names)
            self.assertIn("frame_key", instance_column_names)
            self.assertIn("font_key", instance_column_names)

            wishlist_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'wishlist_cards'").fetchone()
            self.assertIsNotNone(wishlist_row)

            tags_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_tags'").fetchone()
            self.assertIsNotNone(tags_row)

            instance_tags_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'card_instance_tags'").fetchone()
            self.assertIsNotNone(instance_tags_row)

            teams_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_teams'").fetchone()
            self.assertIsNotNone(teams_row)

            team_members_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'team_members'").fetchone()
            self.assertIsNotNone(team_members_row)

            battles_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'battle_sessions'").fetchone()
            self.assertIsNotNone(battles_row)

    def test_init_db_does_not_create_player_cards_table(self) -> None:
        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_cards'").fetchone()
            self.assertIsNone(row)

    def test_marry_selects_lowest_generation_copy(self) -> None:
        guild_id = 1
        user_id = 100
        card_id = "SPG"

        storage.init_db()
        instance_a = storage.add_card_to_player(guild_id, user_id, card_id, 500)
        instance_b = storage.add_card_to_player(guild_id, user_id, card_id, 50)
        storage.add_card_to_player(guild_id, user_id, card_id, 900)

        success, message, married_instance_id, married_generation = storage.marry_card(guild_id, user_id, card_id)
        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(married_generation, 50)
        self.assertEqual(married_instance_id, instance_b)
        self.assertNotEqual(married_instance_id, instance_a)

    def test_claim_vote_reward_always_adds_starter(self) -> None:
        guild_id = 1
        user_id = 1234

        storage.init_db()

        starter_total = storage.claim_vote_reward(
            guild_id=guild_id,
            user_id=user_id,
            reward_amount=1,
        )
        self.assertEqual(starter_total, 1)

        starter_total = storage.claim_vote_reward(
            guild_id=guild_id,
            user_id=user_id,
            reward_amount=1,
        )
        self.assertEqual(starter_total, 2)

    def test_slots_cooldown_and_starter_award(self) -> None:
        guild_id = 1
        user_id = 1240

        storage.init_db()

        first_remaining = storage.consume_slots_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=5_000.0,
            cooldown_seconds=1_320.0,
        )
        self.assertEqual(first_remaining, 0.0)

        second_remaining = storage.consume_slots_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=5_100.0,
            cooldown_seconds=1_320.0,
        )
        self.assertGreater(second_remaining, 0.0)

        starter_total = storage.add_starter(guild_id, user_id, 3)
        self.assertEqual(starter_total, 3)
        self.assertEqual(storage.get_player_starter(guild_id, user_id), 3)

    def test_buy_drop_tickets_with_starter_requires_sufficient_balance(self) -> None:
        guild_id = 1
        user_id = 1244

        storage.init_db()
        purchased, starter_balance, drop_tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 2)
        self.assertFalse(purchased)
        self.assertEqual(starter_balance, 0)
        self.assertEqual(drop_tickets, 0)
        self.assertEqual(spent, 0)

        storage.add_starter(guild_id, user_id, 3)
        purchased, starter_balance, drop_tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 2)
        self.assertTrue(purchased)
        self.assertEqual(starter_balance, 1)
        self.assertEqual(drop_tickets, 2)
        self.assertEqual(spent, 2)

    def test_consume_drop_cooldown_or_ticket_bypasses_without_changing_timestamp(
        self,
    ) -> None:
        guild_id = 1
        user_id = 1245

        storage.init_db()
        storage.add_starter(guild_id, user_id, 1)
        storage.buy_drop_tickets_with_starter(guild_id, user_id, 1)

        now = 4_000.0
        storage.set_last_drop_at(guild_id, user_id, now)
        before_last_drop_at, _ = storage.get_player_cooldown_timestamps(guild_id, user_id)

        used_ticket, remaining = storage.consume_drop_cooldown_or_ticket(
            guild_id,
            user_id,
            now=now + 1.0,
            cooldown_seconds=360.0,
        )
        after_last_drop_at, _ = storage.get_player_cooldown_timestamps(guild_id, user_id)

        self.assertTrue(used_ticket)
        self.assertEqual(remaining, 0.0)
        self.assertEqual(before_last_drop_at, after_last_drop_at)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, user_id), 0)

    def test_flip_cooldown_helper_and_timestamp(self) -> None:
        guild_id = 1
        user_id = 1241

        storage.init_db()

        first_remaining = storage.consume_flip_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=10_000.0,
            cooldown_seconds=120.0,
        )
        self.assertEqual(first_remaining, 0.0)
        self.assertEqual(storage.get_player_flip_timestamp(guild_id, user_id), 10_000.0)

        second_remaining = storage.consume_flip_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=10_050.0,
            cooldown_seconds=120.0,
        )
        self.assertGreater(second_remaining, 0.0)

    def test_execute_flip_wager_validates_stake_and_balance(self) -> None:
        guild_id = 1
        user_id = 1242
        storage.init_db()

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=0,
            now=1_000.0,
            cooldown_seconds=120.0,
            did_win=True,
        )
        self.assertEqual(status, "invalid_stake")
        self.assertEqual(remaining, 0.0)
        self.assertEqual(balance, 0)

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=1_000.0,
            cooldown_seconds=120.0,
            did_win=True,
        )
        self.assertEqual(status, "insufficient_dough")

    def test_flip_loss_adds_to_gambling_pot(self) -> None:
        guild_id = 1
        user_id = 1247
        storage.init_db()
        storage.add_dough(guild_id, user_id, 100)

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=25,
            now=4_000.0,
            cooldown_seconds=1.0,
            did_win=False,
        )

        self.assertEqual(status, "lost")
        self.assertEqual(remaining, 0.0)
        self.assertEqual(balance, 75)
        pot_dough, pot_starter, pot_tickets = storage.get_gambling_pot(guild_id)
        self.assertEqual(pot_dough, 25)
        self.assertEqual(pot_starter, 0)
        self.assertEqual(pot_tickets, 0)

    def test_monopoly_roll_sets_cooldown_when_not_doubles(self) -> None:
        guild_id = 1
        user_id = 1248
        storage.init_db()

        with patch("noodswap.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=10_000.0,
                cooldown_seconds=660.0,
            )

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.doubles)
        _position, last_roll_at, in_jail, _jail_attempts, doubles_count = storage.get_monopoly_state(guild_id, user_id)
        self.assertEqual(last_roll_at, 10_000.0)
        self.assertFalse(in_jail)
        self.assertEqual(doubles_count, 0)

    def test_monopoly_roll_doubles_does_not_consume_cooldown(self) -> None:
        guild_id = 1
        user_id = 1249
        storage.init_db()

        with patch("noodswap.storage.roll_dice", return_value=(3, 3, True)):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=20_000.0,
                cooldown_seconds=660.0,
            )

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.doubles)
        _position, last_roll_at, in_jail, _jail_attempts, doubles_count = storage.get_monopoly_state(guild_id, user_id)
        self.assertEqual(last_roll_at, 0.0)
        self.assertFalse(in_jail)
        self.assertEqual(doubles_count, 1)

    def test_monopoly_property_rent_is_one_twelfth_of_card_value(self) -> None:
        guild_id = 1
        roller_id = 1250
        owner_id = 1251
        storage.init_db()

        common_card_id = next(card_id for card_id, data in storage.CARD_CATALOG.items() if str(data["rarity"]).lower() == "common")
        generation = 100
        storage.add_card_to_player(guild_id, owner_id, common_card_id, generation)
        storage.add_dough(guild_id, roller_id, 10_000)

        full_value = storage.card_value(
            common_card_id,
            generation,
            morph_key=None,
            frame_key=None,
            font_key=None,
        )
        expected_rent = full_value // 12

        with patch("noodswap.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                roller_id,
                now=30_000.0,
                cooldown_seconds=660.0,
            )

        self.assertEqual(result.status, "ok")

        roller_dough, _, _ = storage.get_player_info(guild_id, roller_id)
        owner_dough, _, _ = storage.get_player_info(guild_id, owner_id)
        self.assertEqual(roller_dough, 10_000 - expected_rent)
        self.assertEqual(owner_dough, expected_rent)

    def test_monopoly_property_landing_uses_dupe_card_name_and_thumbnail_metadata(
        self,
    ) -> None:
        guild_id = 1
        roller_id = 2250
        owner_id = 2251
        storage.init_db()

        common_card_id = next(card_id for card_id, data in storage.CARD_CATALOG.items() if str(data["rarity"]).lower() == "common")
        generation = 123
        storage.add_card_to_player(guild_id, owner_id, common_card_id, generation)
        storage.add_dough(guild_id, roller_id, 10_000)

        with patch("noodswap.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                roller_id,
                now=31_000.0,
                cooldown_seconds=660.0,
            )

        card_name = str(storage.CARD_CATALOG[common_card_id]["name"])
        self.assertTrue(any(f"Landed on **{card_name}**" in line for line in result.lines))
        self.assertEqual(result.thumbnail_card_id, common_card_id)
        self.assertEqual(result.thumbnail_generation, generation)

    def test_monopoly_roll_mpreg_includes_metadata_and_display_line(self) -> None:
        guild_id = 1
        user_id = 1252
        storage.init_db()

        with (
            patch("noodswap.storage.roll_dice", return_value=(1, 2, False)),
            patch(
                "noodswap.storage.board_space",
                return_value=SimpleNamespace(kind="mpreg", name="Mpreg", emoji="🤰", rarity=None),
            ),
            patch("noodswap.storage.random_epic_or_better_card_id", return_value="SPG"),
            patch("noodswap.storage.random_generation", return_value=321),
        ):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=40_000.0,
                cooldown_seconds=660.0,
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.mpreg_card_id, "SPG")
        self.assertEqual(result.mpreg_generation, 321)
        self.assertIsNotNone(result.mpreg_dupe_code)
        self.assertEqual(result.thumbnail_card_id, "SPG")
        self.assertEqual(result.thumbnail_generation, 321)

        expected_line = storage.card_dupe_display(
            "SPG",
            321,
            dupe_code=result.mpreg_dupe_code,
            morph_key=result.mpreg_morph_key,
            frame_key=result.mpreg_frame_key,
            font_key=result.mpreg_font_key,
        )
        self.assertIn(expected_line, result.lines)

    def test_execute_flip_wager_win_loss_and_cooldown(self) -> None:
        guild_id = 1
        user_id = 1243
        storage.init_db()
        storage.add_dough(guild_id, user_id, 50)

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=2_000.0,
            cooldown_seconds=120.0,
            did_win=True,
        )
        self.assertEqual(status, "won")
        self.assertEqual(remaining, 0.0)
        self.assertEqual(balance, 60)

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=2_030.0,
            cooldown_seconds=120.0,
            did_win=False,
        )
        self.assertEqual(status, "cooldown")
        self.assertGreater(remaining, 0.0)
        self.assertEqual(balance, 60)

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=2_150.0,
            cooldown_seconds=120.0,
            did_win=False,
        )
        self.assertEqual(status, "lost")
        self.assertEqual(remaining, 0.0)
        self.assertEqual(balance, 50)

    def test_burn_candidate_selects_highest_generation_copy(self) -> None:
        guild_id = 1
        user_id = 101
        card_id = "PEN"

        storage.init_db()
        storage.add_card_to_player(guild_id, user_id, card_id, 5)
        storage.add_card_to_player(guild_id, user_id, card_id, 900)
        storage.add_card_to_player(guild_id, user_id, card_id, 400)

        selected = storage.get_burn_candidate_by_card_id(guild_id, user_id, card_id)
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _instance_id, selected_card_id, selected_generation, _selected_dupe_code = selected
        self.assertEqual(selected_card_id, card_id)
        self.assertEqual(selected_generation, 900)

    def test_trade_transfers_highest_generation_and_updates_dough(self) -> None:
        guild_id = 1
        seller_id = 500
        buyer_id = 600
        card_id = "SPG"

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, card_id, 20)
        storage.add_card_to_player(guild_id, seller_id, card_id, 800)
        storage.add_dough(guild_id, buyer_id, 100)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, card_id)
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, selected_dupe_code = selected

        success, message, traded_generation, traded_dupe_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            dupe_code=selected_dupe_code,
            terms=TradeTerms(mode="dough", amount=30),
        )

        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(traded_generation, 800)
        self.assertIsNotNone(traded_dupe_code)

        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)

        self.assertEqual(len(seller_instances), 1)
        self.assertEqual(seller_instances[0][2], 20)
        self.assertEqual(len(buyer_instances), 1)
        self.assertEqual(buyer_instances[0][2], 800)

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        self.assertEqual(seller_dough, 30)
        self.assertEqual(buyer_dough, 70)

    def test_trade_fails_when_seller_has_no_card(self) -> None:
        guild_id = 1
        seller_id = 700
        buyer_id = 701

        storage.init_db()
        storage.add_dough(guild_id, buyer_id, 100)

        success, message, traded_generation, traded_dupe_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code="0",
            terms=TradeTerms(mode="dough", amount=10),
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: seller no longer has that card code.")
        self.assertIsNone(traded_generation)
        self.assertIsNone(traded_dupe_code)

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        self.assertEqual(seller_dough, 0)
        self.assertEqual(buyer_dough, 100)

    def test_trade_fails_when_buyer_has_insufficient_dough(self) -> None:
        guild_id = 1
        seller_id = 702
        buyer_id = 703

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_dough(guild_id, buyer_id, 5)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, selected_dupe_code = selected

        success, message, traded_generation, traded_dupe_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=selected_dupe_code,
            terms=TradeTerms(mode="dough", amount=20),
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: buyer does not have enough dough.")
        self.assertIsNone(traded_generation)
        self.assertIsNone(traded_dupe_code)

        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(seller_instances), 1)
        self.assertEqual(len(buyer_instances), 0)

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        self.assertEqual(seller_dough, 0)
        self.assertEqual(buyer_dough, 5)

    def test_trade_starter_mode_transfers_card_and_starter(self) -> None:
        guild_id = 1
        seller_id = 740
        buyer_id = 741

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 10)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, dupe_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=TradeTerms(mode="starter", amount=4),
        )

        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(gen, 100)
        self.assertIsNone(received)

        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(buyer_instances), 1)
        self.assertEqual(buyer_instances[0][1], "SPG")
        self.assertEqual(storage.get_player_starter(guild_id, seller_id), 4)
        self.assertEqual(storage.get_player_starter(guild_id, buyer_id), 6)

    def test_trade_starter_mode_fails_when_buyer_has_insufficient_starter(self) -> None:
        guild_id = 1
        seller_id = 742
        buyer_id = 743

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 2)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, dupe_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=TradeTerms(mode="starter", amount=5),
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: buyer does not have enough starter.")
        self.assertIsNone(gen)
        self.assertIsNone(received)
        # Nothing transferred
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        self.assertEqual(len(seller_instances), 1)
        self.assertEqual(storage.get_player_starter(guild_id, buyer_id), 2)

    def test_trade_tickets_mode_transfers_card_and_tickets(self) -> None:
        guild_id = 1
        seller_id = 744
        buyer_id = 745

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 5)
        storage.buy_drop_tickets_with_starter(guild_id, buyer_id, 5)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, dupe_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=TradeTerms(mode="tickets", amount=3),
        )

        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(gen, 100)
        self.assertIsNone(received)

        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(buyer_instances), 1)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, seller_id), 3)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, buyer_id), 2)

    def test_trade_tickets_mode_fails_when_buyer_has_insufficient_tickets(self) -> None:
        guild_id = 1
        seller_id = 746
        buyer_id = 747

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 1)
        storage.buy_drop_tickets_with_starter(guild_id, buyer_id, 1)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _, _, dupe_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=dupe_code,
            terms=TradeTerms(mode="tickets", amount=5),
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: buyer does not have enough drop tickets.")
        self.assertIsNone(gen)
        self.assertIsNone(received)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        self.assertEqual(len(seller_instances), 1)

    def test_trade_card_mode_swaps_both_instances(self) -> None:
        guild_id = 1
        seller_id = 748
        buyer_id = 749

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_card_to_player(guild_id, buyer_id, "PEN", 200)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        seller_dupe = seller_instances[0][3]
        buyer_dupe = buyer_instances[0][3]

        success, message, gen, _sold_dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=seller_dupe,
            terms=TradeTerms(mode="card", req_dupe_code=buyer_dupe),
        )

        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(gen, 100)
        self.assertIsNotNone(received)
        if received is None:
            return
        r_card_id, r_gen, _r_dupe = received
        self.assertEqual(r_card_id, "PEN")
        self.assertEqual(r_gen, 200)

        seller_after = storage.get_player_card_instances(guild_id, seller_id)
        buyer_after = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(seller_after), 1)
        self.assertEqual(seller_after[0][1], "PEN")
        self.assertEqual(len(buyer_after), 1)
        self.assertEqual(buyer_after[0][1], "SPG")

    def test_trade_card_mode_fails_when_buyer_no_longer_has_req_card(self) -> None:
        guild_id = 1
        seller_id = 750
        buyer_id = 751

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        seller_dupe = seller_instances[0][3]

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=seller_dupe,
            terms=TradeTerms(mode="card", req_dupe_code="zzz"),
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: buyer no longer has the requested card.")
        self.assertIsNone(gen)
        self.assertIsNone(received)
        # Seller still has their card
        seller_instances_after = storage.get_player_card_instances(guild_id, seller_id)
        self.assertEqual(len(seller_instances_after), 1)

    def test_trade_card_mode_clears_marriage_for_both_users(self) -> None:
        guild_id = 1
        seller_id = 752
        buyer_id = 753

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_card_to_player(guild_id, buyer_id, "PEN", 200)
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        seller_dupe = seller_instances[0][3]
        buyer_dupe = buyer_instances[0][3]

        # Marry both cards
        storage.marry_card(guild_id, seller_id, "SPG")
        storage.marry_card(guild_id, buyer_id, "PEN")
        self.assertIsNotNone(storage.get_last_pulled_instance(guild_id, seller_id))
        self.assertIsNotNone(storage.get_last_pulled_instance(guild_id, buyer_id))

        success, _, _, _, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=seller_dupe,
            terms=TradeTerms(mode="card", req_dupe_code=buyer_dupe),
        )
        self.assertTrue(success)

        # Both marriages cleared (index 2 = married_instance_id)
        seller_info = storage.get_player_info(guild_id, seller_id)
        buyer_info = storage.get_player_info(guild_id, buyer_id)
        self.assertIsNone(seller_info[2])
        self.assertIsNone(buyer_info[2])

    def test_gift_card_transfers_selected_instance_without_dough_change(self) -> None:
        guild_id = 1
        sender_id = 720
        recipient_id = 721

        storage.init_db()
        storage.add_card_to_player(guild_id, sender_id, "SPG", 100)
        storage.add_card_to_player(guild_id, sender_id, "SPG", 200)
        selected = storage.get_burn_candidate_by_card_id(guild_id, sender_id, "SPG")
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _, _card_id, _generation, selected_dupe_code = selected

        success, message, gifted_card_id, gifted_generation, gifted_dupe_code = storage.execute_gift_card(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            card_code=selected_dupe_code,
        )

        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(gifted_card_id, "SPG")
        self.assertEqual(gifted_generation, 200)
        self.assertEqual(gifted_dupe_code, selected_dupe_code)

        sender_instances = storage.get_player_card_instances(guild_id, sender_id)
        recipient_instances = storage.get_player_card_instances(guild_id, recipient_id)
        self.assertEqual(len(sender_instances), 1)
        self.assertEqual(sender_instances[0][2], 100)
        self.assertEqual(len(recipient_instances), 1)
        self.assertEqual(recipient_instances[0][2], 200)

        sender_dough, _, _ = storage.get_player_info(guild_id, sender_id)
        recipient_dough, _, _ = storage.get_player_info(guild_id, recipient_id)
        self.assertEqual(sender_dough, 0)
        self.assertEqual(recipient_dough, 0)

    def test_gift_card_clears_sender_last_pulled_pointer(self) -> None:
        guild_id = 1
        sender_id = 722
        recipient_id = 723

        storage.init_db()
        storage.add_card_to_player(guild_id, sender_id, "SPG", 300)
        selected = storage.get_last_pulled_instance(guild_id, sender_id)
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _instance_id, _card_id, _generation, dupe_code = selected

        success, message, gifted_card_id, gifted_generation, gifted_dupe_code = storage.execute_gift_card(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            card_code=dupe_code,
        )
        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(gifted_card_id, "SPG")
        self.assertEqual(gifted_generation, 300)
        self.assertEqual(gifted_dupe_code, dupe_code)
        self.assertIsNone(storage.get_last_pulled_instance(guild_id, sender_id))

    def test_gift_starter_transfers_balances(self) -> None:
        guild_id = 1
        sender_id = 730
        recipient_id = 731

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 5)

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_starter(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=3,
        )

        self.assertTrue(gifted)
        self.assertEqual(message, "")
        self.assertEqual(sender_balance, 2)
        self.assertEqual(recipient_balance, 3)
        self.assertEqual(storage.get_player_starter(guild_id, sender_id), 2)
        self.assertEqual(storage.get_player_starter(guild_id, recipient_id), 3)

    def test_gift_starter_fails_when_insufficient_balance(self) -> None:
        guild_id = 1
        sender_id = 732
        recipient_id = 733

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 1)

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_starter(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=2,
        )

        self.assertFalse(gifted)
        self.assertEqual(message, "You do not have enough starter.")
        self.assertEqual(sender_balance, 1)
        self.assertEqual(recipient_balance, 0)
        self.assertEqual(storage.get_player_starter(guild_id, sender_id), 1)
        self.assertEqual(storage.get_player_starter(guild_id, recipient_id), 0)

    def test_gift_drop_tickets_transfers_balances(self) -> None:
        guild_id = 1
        sender_id = 734
        recipient_id = 735

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 4)
        purchased, _starter, _tickets, _spent = storage.buy_drop_tickets_with_starter(guild_id, sender_id, 4)
        self.assertTrue(purchased)

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_drop_tickets(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=3,
        )

        self.assertTrue(gifted)
        self.assertEqual(message, "")
        self.assertEqual(sender_balance, 1)
        self.assertEqual(recipient_balance, 3)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, sender_id), 1)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, recipient_id), 3)

    def test_gift_drop_tickets_fails_when_insufficient_balance(self) -> None:
        guild_id = 1
        sender_id = 736
        recipient_id = 737

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 1)
        purchased, _starter, _tickets, _spent = storage.buy_drop_tickets_with_starter(guild_id, sender_id, 1)
        self.assertTrue(purchased)

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_drop_tickets(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=2,
        )

        self.assertFalse(gifted)
        self.assertEqual(message, "You do not have enough drop tickets.")
        self.assertEqual(sender_balance, 1)
        self.assertEqual(recipient_balance, 0)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, sender_id), 1)
        self.assertEqual(storage.get_player_drop_tickets(guild_id, recipient_id), 0)

    def test_player_leaderboard_info_aggregates_cards_wishes_and_value(self) -> None:
        guild_id = 1
        first_user = 1100
        second_user = 1200

        storage.init_db()
        storage.add_card_to_player(guild_id, first_user, "SPG", 100)
        storage.add_card_to_player(guild_id, first_user, "PEN", 300)
        storage.add_card_to_player(guild_id, second_user, "SPG", 900)

        storage.add_dough(guild_id, first_user, 25)
        storage.add_dough(guild_id, second_user, 80)
        storage.claim_vote_reward(guild_id, first_user, reward_amount=2)

        storage.add_card_to_wishlist(guild_id, first_user, "SPG")
        storage.add_card_to_wishlist(guild_id, first_user, "PEN")
        storage.add_card_to_wishlist(guild_id, second_user, "BAR")

        rows = storage.get_player_leaderboard_info(guild_id)
        by_user = {row[0]: row for row in rows}

        first = by_user[first_user]
        second = by_user[second_user]

        self.assertEqual(first[1], 2)
        self.assertEqual(first[2], 2)
        self.assertEqual(first[3], 25)
        self.assertEqual(first[4], 2)
        self.assertEqual(first[5], 1)
        self.assertGreater(first[6], 0)

        self.assertEqual(second[1], 1)
        self.assertEqual(second[2], 1)
        self.assertEqual(second[3], 80)
        self.assertEqual(second[4], 0)
        self.assertEqual(second[5], 0)
        self.assertGreater(second[6], 0)

    def test_marry_fails_if_card_already_married_by_another_player(self) -> None:
        guild_id = 1
        first_user = 800
        second_user = 801
        card_id = "SPG"

        storage.init_db()
        storage.add_card_to_player(guild_id, first_user, card_id, 120)
        storage.add_card_to_player(guild_id, second_user, card_id, 130)

        first_success, first_message, _, _ = storage.marry_card(guild_id, first_user, card_id)
        self.assertTrue(first_success)
        self.assertEqual(first_message, "")

        second_success, second_message, second_instance_id, second_generation = storage.marry_card(
            guild_id,
            second_user,
            card_id,
        )
        self.assertFalse(second_success)
        self.assertEqual(second_message, "That card is already married by another player.")
        self.assertIsNone(second_instance_id)
        self.assertIsNone(second_generation)

    def test_marry_card_instance_fails_if_already_married_to_different_instance(
        self,
    ) -> None:
        guild_id = 1
        user_id = 900
        card_id = "SPG"

        storage.init_db()
        first_instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 100)
        second_instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 200)

        success, message, _, _, _ = storage.marry_card_instance(guild_id, user_id, first_instance_id)
        self.assertTrue(success)
        self.assertEqual(message, "")

        (
            second_success,
            second_message,
            second_card_id,
            second_generation,
            second_dupe_code,
        ) = storage.marry_card_instance(
            guild_id,
            user_id,
            second_instance_id,
        )
        self.assertFalse(second_success)
        self.assertEqual(second_message, "You are already married. Use `ns divorce` first.")
        self.assertIsNone(second_card_id)
        self.assertIsNone(second_generation)
        self.assertIsNone(second_dupe_code)

    def test_remove_card_clears_last_pulled_pointer(self) -> None:
        guild_id = 1
        user_id = 910
        card_id = "SPG"

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 250)

        removed = storage.remove_card_from_player(guild_id, user_id, card_id)
        self.assertIsNotNone(removed)
        if removed is None:
            return
        removed_instance_id, removed_generation = removed
        self.assertEqual(removed_instance_id, instance_id)
        self.assertEqual(removed_generation, 250)

        self.assertIsNone(storage.get_last_pulled_instance(guild_id, user_id))

    def test_get_last_pulled_instance_clears_stale_pointer(self) -> None:
        guild_id = 1
        user_id = 912
        card_id = "SPG"

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 300)

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            with conn:
                conn.execute(
                    "DELETE FROM card_instances WHERE instance_id = ?",
                    (instance_id,),
                )

        self.assertIsNone(storage.get_last_pulled_instance(guild_id, user_id))

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT last_dropped_instance_id FROM players WHERE guild_id = ? AND user_id = ?",
                (storage.GLOBAL_GUILD_ID, user_id),
            ).fetchone()
        self.assertIsNotNone(row)
        if row is None:
            return
        self.assertIsNone(row[0])

    def test_get_last_pulled_instance_clears_pointer_after_trade_transfer(self) -> None:
        guild_id = 1
        seller_id = 913
        buyer_id = 914
        card_id = "SPG"

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, card_id, 300)
        selected = storage.get_last_pulled_instance(guild_id, seller_id)
        self.assertIsNotNone(selected)
        if selected is None:
            return
        _instance_id, _card_id, _generation, dupe_code = selected

        storage.add_dough(guild_id, buyer_id, 100)
        success, message, traded_generation, traded_dupe_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            dupe_code=dupe_code,
            terms=TradeTerms(mode="dough", amount=10),
        )
        self.assertTrue(success)
        self.assertEqual(message, "")
        self.assertEqual(traded_generation, 300)
        self.assertEqual(traded_dupe_code, dupe_code)

        self.assertIsNone(storage.get_last_pulled_instance(guild_id, seller_id))

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT last_dropped_instance_id FROM players WHERE guild_id = ? AND user_id = ?",
                (storage.GLOBAL_GUILD_ID, seller_id),
            ).fetchone()
        self.assertIsNotNone(row)
        if row is None:
            return
        self.assertIsNone(row[0])

    def test_dupe_codes_assign_sequential_and_reuse_lowest_free(self) -> None:
        guild_id = 1
        user_id = 911

        storage.init_db()
        instance_0 = storage.add_card_to_player(guild_id, user_id, "SPG", 100)
        instance_1 = storage.add_card_to_player(guild_id, user_id, "PEN", 101)
        instance_2 = storage.add_card_to_player(guild_id, user_id, "FUS", 102)

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            dupe_rows = conn.execute(
                "SELECT instance_id, dupe_code FROM card_instances WHERE guild_id = ? ORDER BY instance_id ASC",
                (storage.GLOBAL_GUILD_ID,),
            ).fetchall()
        dupe_by_instance = {int(row[0]): str(row[1]) for row in dupe_rows}
        self.assertEqual(dupe_by_instance[instance_0], "0")
        self.assertEqual(dupe_by_instance[instance_1], "1")
        self.assertEqual(dupe_by_instance[instance_2], "2")

        burned = storage.burn_instance(guild_id, user_id, instance_1)
        self.assertIsNotNone(burned)

        reused_instance = storage.add_card_to_player(guild_id, user_id, "MAC", 103)
        next_instance = storage.add_card_to_player(guild_id, user_id, "LIN", 104)

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            dupe_rows = conn.execute(
                "SELECT instance_id, dupe_code FROM card_instances WHERE guild_id = ? ORDER BY instance_id ASC",
                (storage.GLOBAL_GUILD_ID,),
            ).fetchall()
        dupe_by_instance = {int(row[0]): str(row[1]) for row in dupe_rows}
        self.assertEqual(dupe_by_instance[reused_instance], "1")
        self.assertEqual(dupe_by_instance[next_instance], "3")

    def test_get_instance_by_code_accepts_hash_prefix(self) -> None:
        guild_id = 1
        user_id = 915

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)
        instance = storage.get_instance_by_id(guild_id, instance_id)
        self.assertIsNotNone(instance)
        if instance is None:
            return
        _found_instance_id, _card_id, _generation, dupe_code = instance

        by_plain_code = storage.get_instance_by_code(guild_id, user_id, dupe_code.upper())
        by_hash_code = storage.get_instance_by_code(guild_id, user_id, f"#{dupe_code.upper()}")
        by_hash_global = storage.get_instance_by_dupe_code(guild_id, f"#{dupe_code.upper()}")

        self.assertEqual(by_plain_code, by_hash_code)
        self.assertIsNotNone(by_hash_global)
        if by_hash_global is None or by_plain_code is None:
            return

        (
            global_instance_id,
            global_user_id,
            global_card_id,
            global_generation,
            global_dupe_code,
        ) = by_hash_global
        plain_instance_id, plain_card_id, plain_generation, plain_dupe_code = by_plain_code
        self.assertEqual(global_user_id, user_id)
        self.assertEqual(
            (global_instance_id, global_card_id, global_generation, global_dupe_code),
            (plain_instance_id, plain_card_id, plain_generation, plain_dupe_code),
        )

    def test_init_db_v5_ensures_dupe_code_column_and_index(self) -> None:
        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            with conn:
                conn.executescript("""
                    CREATE TABLE schema_migrations (
                        version INTEGER NOT NULL
                    );
                    INSERT INTO schema_migrations(version) VALUES (4);

                    CREATE TABLE card_instances (
                        instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        card_id TEXT NOT NULL,
                        generation INTEGER NOT NULL
                    );

                    INSERT INTO card_instances (guild_id, user_id, card_id, generation)
                    VALUES (0, 42, 'SPG', 123);
                    """)

        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            self.assertIsNotNone(version_row)
            self.assertEqual(int(version_row[0]), storage.TARGET_SCHEMA_VERSION)

            columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            column_names = {str(column[1]) for column in columns}
            self.assertIn("dupe_code", column_names)

            index_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_card_instances_dupe_code'").fetchone()
            self.assertIsNotNone(index_row)

    def test_wishlist_add_remove_and_read(self) -> None:
        guild_id = 1
        user_id = 920

        storage.init_db()

        added = storage.add_card_to_wishlist(guild_id, user_id, "SPG")
        self.assertTrue(added)

        added_again = storage.add_card_to_wishlist(guild_id, user_id, "SPG")
        self.assertFalse(added_again)

        storage.add_card_to_wishlist(guild_id, user_id, "PEN")

        cards = storage.get_wishlist_cards(guild_id, user_id)
        self.assertEqual(cards, ["PEN", "SPG"])

        removed = storage.remove_card_from_wishlist(guild_id, user_id, "SPG")
        self.assertTrue(removed)
        self.assertEqual(storage.get_wishlist_cards(guild_id, user_id), ["PEN"])

        removed_missing = storage.remove_card_from_wishlist(guild_id, user_id, "SPG")
        self.assertFalse(removed_missing)

    def test_apply_morph_to_instance_persists_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 940

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)
        storage.add_dough(guild_id, user_id, 50)

        applied, message = storage.apply_morph_to_instance(
            guild_id,
            user_id,
            instance_id,
            "black_and_white",
            9,
        )
        self.assertTrue(applied)
        self.assertEqual(message, "")
        self.assertEqual(storage.get_instance_morph(guild_id, instance_id), "black_and_white")

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        self.assertEqual(dough, 41)

    def test_apply_morph_to_instance_rejects_insufficient_dough(self) -> None:
        guild_id = 1
        user_id = 941

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)

        applied, message = storage.apply_morph_to_instance(
            guild_id,
            user_id,
            instance_id,
            "black_and_white",
            99,
        )
        self.assertFalse(applied)
        self.assertEqual(message, "You do not have enough dough.")
        self.assertIsNone(storage.get_instance_morph(guild_id, instance_id))

    def test_apply_frame_to_instance_persists_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 942

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)
        storage.add_dough(guild_id, user_id, 50)

        applied, message = storage.apply_frame_to_instance(
            guild_id,
            user_id,
            instance_id,
            "buttery",
            9,
        )
        self.assertTrue(applied)
        self.assertEqual(message, "")
        self.assertEqual(storage.get_instance_frame(guild_id, instance_id), "buttery")

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        self.assertEqual(dough, 41)

    def test_apply_frame_to_instance_rejects_insufficient_dough(self) -> None:
        guild_id = 1
        user_id = 943

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)

        applied, message = storage.apply_frame_to_instance(
            guild_id,
            user_id,
            instance_id,
            "buttery",
            99,
        )
        self.assertFalse(applied)
        self.assertEqual(message, "You do not have enough dough.")
        self.assertIsNone(storage.get_instance_frame(guild_id, instance_id))

    def test_apply_font_to_instance_persists_and_charges_dough(self) -> None:
        guild_id = 1
        user_id = 944

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)
        storage.add_dough(guild_id, user_id, 50)

        applied, message = storage.apply_font_to_instance(
            guild_id,
            user_id,
            instance_id,
            "serif",
            9,
        )
        self.assertTrue(applied)
        self.assertEqual(message, "")
        self.assertEqual(storage.get_instance_font(guild_id, instance_id), "serif")

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        self.assertEqual(dough, 41)

    def test_apply_font_to_instance_rejects_insufficient_dough(self) -> None:
        guild_id = 1
        user_id = 945

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)

        applied, message = storage.apply_font_to_instance(
            guild_id,
            user_id,
            instance_id,
            "mono",
            99,
        )
        self.assertFalse(applied)
        self.assertEqual(message, "You do not have enough dough.")
        self.assertIsNone(storage.get_instance_font(guild_id, instance_id))

    def test_wishlist_is_global_across_guilds(self) -> None:
        user_id = 930

        storage.init_db()

        storage.add_card_to_wishlist(1, user_id, "SPG")
        storage.add_card_to_wishlist(2, user_id, "PEN")

        self.assertEqual(storage.get_wishlist_cards(1, user_id), ["PEN", "SPG"])
        self.assertEqual(storage.get_wishlist_cards(2, user_id), ["PEN", "SPG"])

    def test_get_card_wish_counts_aggregates_per_card(self) -> None:
        storage.init_db()

        storage.add_card_to_wishlist(1, 1000, "SPG")
        storage.add_card_to_wishlist(1, 1001, "SPG")
        storage.add_card_to_wishlist(1, 1002, "PEN")
        storage.add_card_to_wishlist(2, 1003, "SPG")

        counts_guild_1 = storage.get_card_wish_counts(1)
        counts_guild_2 = storage.get_card_wish_counts(2)

        self.assertEqual(counts_guild_1.get("SPG"), 3)
        self.assertEqual(counts_guild_1.get("PEN"), 1)
        self.assertIsNone(counts_guild_1.get("FUS"))
        self.assertEqual(counts_guild_2.get("SPG"), 3)

    def test_player_tags_create_list_lock_and_delete(self) -> None:
        guild_id = 1
        user_id = 1200

        storage.init_db()

        self.assertTrue(storage.create_player_tag(guild_id, user_id, "Favorites"))
        self.assertFalse(storage.create_player_tag(guild_id, user_id, "favorites"))

        listed = storage.list_player_tags(guild_id, user_id)
        self.assertEqual(listed, [("favorites", False, 0)])

        self.assertTrue(storage.set_player_tag_locked(guild_id, user_id, "Favorites", True))
        listed_after_lock = storage.list_player_tags(guild_id, user_id)
        self.assertEqual(listed_after_lock, [("favorites", True, 0)])

        self.assertTrue(storage.delete_player_tag(guild_id, user_id, "Favorites"))
        self.assertEqual(storage.list_player_tags(guild_id, user_id), [])

    def test_assign_and_unassign_tag_to_card_instance(self) -> None:
        guild_id = 1
        user_id = 1201

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 111)
        storage.create_player_tag(guild_id, user_id, "food")

        self.assertTrue(storage.assign_tag_to_instance(guild_id, user_id, instance_id, "food"))
        self.assertFalse(storage.assign_tag_to_instance(guild_id, user_id, instance_id, "food"))

        tagged = storage.get_instances_by_tag(guild_id, user_id, "food")
        self.assertEqual(len(tagged), 1)
        self.assertEqual(tagged[0][0], instance_id)

        self.assertTrue(storage.unassign_tag_from_instance(guild_id, user_id, instance_id, "food"))
        self.assertFalse(storage.unassign_tag_from_instance(guild_id, user_id, instance_id, "food"))

    def test_locked_tag_blocks_burn(self) -> None:
        guild_id = 1
        user_id = 1202

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 222)
        storage.create_player_tag(guild_id, user_id, "keep")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "keep")
        storage.set_player_tag_locked(guild_id, user_id, "keep", True)

        locked_tags = storage.get_locked_tags_for_instance(guild_id, user_id, instance_id)
        self.assertEqual(locked_tags, ["keep"])

        burned = storage.burn_instance(guild_id, user_id, instance_id)
        self.assertIsNone(burned)

        still_owned = storage.get_instance_by_id(guild_id, instance_id)
        self.assertIsNotNone(still_owned)

    def test_burn_instances_blocks_all_when_any_locked(self) -> None:
        guild_id = 1
        user_id = 1204

        storage.init_db()
        open_instance = storage.add_card_to_player(guild_id, user_id, "SPG", 111)
        locked_instance = storage.add_card_to_player(guild_id, user_id, "PEN", 222)
        storage.create_player_tag(guild_id, user_id, "keep")
        storage.assign_tag_to_instance(guild_id, user_id, locked_instance, "keep")
        storage.set_player_tag_locked(guild_id, user_id, "keep", True)

        burned_rows, locked_by_instance = storage.burn_instances(guild_id, user_id, [open_instance, locked_instance])

        self.assertIsNone(burned_rows)
        self.assertIn(locked_instance, locked_by_instance)
        self.assertIsNotNone(storage.get_instance_by_id(guild_id, open_instance))
        self.assertIsNotNone(storage.get_instance_by_id(guild_id, locked_instance))

    def test_deleting_tag_cascades_instance_assignments(self) -> None:
        guild_id = 1
        user_id = 1203

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_tag(guild_id, user_id, "archive")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "archive")

        self.assertTrue(storage.delete_player_tag(guild_id, user_id, "archive"))
        self.assertEqual(storage.get_instances_by_tag(guild_id, user_id, "archive"), [])

    def test_team_assignment_enforces_three_card_limit(self) -> None:
        guild_id = 1
        user_id = 1301

        storage.init_db()
        self.assertTrue(storage.create_player_team(guild_id, user_id, "alpha"))

        instance_ids = [
            storage.add_card_to_player(guild_id, user_id, "SPG", 100),
            storage.add_card_to_player(guild_id, user_id, "PEN", 200),
            storage.add_card_to_player(guild_id, user_id, "FUS", 300),
            storage.add_card_to_player(guild_id, user_id, "MAC", 400),
        ]

        for instance_id in instance_ids[:3]:
            success, message = storage.assign_instance_to_team(guild_id, user_id, instance_id, "alpha")
            self.assertTrue(success)
            self.assertEqual(message, "")

        success, message = storage.assign_instance_to_team(guild_id, user_id, instance_ids[3], "alpha")
        self.assertFalse(success)
        self.assertEqual(message, "Team capacity reached (3 cards max).")

    def test_set_active_team_and_list_marks_active(self) -> None:
        guild_id = 1
        user_id = 1302

        storage.init_db()
        storage.create_player_team(guild_id, user_id, "alpha")
        storage.create_player_team(guild_id, user_id, "beta")

        self.assertTrue(storage.set_active_team(guild_id, user_id, "beta"))
        self.assertEqual(storage.get_active_team_name(guild_id, user_id), "beta")

        listed = storage.list_player_teams(guild_id, user_id)
        self.assertEqual(listed, [("alpha", 0, False), ("beta", 0, True)])

    def test_create_and_accept_battle_proposal(self) -> None:
        guild_id = 1
        challenger_id = 1401
        challenged_id = 1402

        storage.init_db()
        storage.add_dough(guild_id, challenger_id, 100)
        storage.add_dough(guild_id, challenged_id, 100)

        storage.create_player_team(guild_id, challenger_id, "a")
        storage.create_player_team(guild_id, challenged_id, "b")
        storage.set_active_team(guild_id, challenger_id, "a")
        storage.set_active_team(guild_id, challenged_id, "b")

        challenger_instance = storage.add_card_to_player(guild_id, challenger_id, "SPG", 120)
        challenged_instance = storage.add_card_to_player(guild_id, challenged_id, "PEN", 340)
        storage.assign_instance_to_team(guild_id, challenger_id, challenger_instance, "a")
        storage.assign_instance_to_team(guild_id, challenged_id, challenged_instance, "b")

        created, message, battle_id, challenger_team, challenged_team = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            25,
        )
        self.assertTrue(created)
        self.assertEqual(message, "")
        self.assertIsNotNone(battle_id)
        self.assertEqual(challenger_team, "a")
        self.assertEqual(challenged_team, "b")

        if battle_id is None:
            return

        with patch("noodswap.storage.random.choice", return_value=challenged_id):
            status, resolve_message = storage.resolve_battle_proposal(
                guild_id,
                battle_id,
                challenged_id,
                accepted=True,
            )
        self.assertEqual(status, "accepted")
        self.assertEqual(resolve_message, "Battle accepted. The battle arena is now active.")

        battle = storage.get_battle_session(guild_id, battle_id)
        self.assertIsNotNone(battle)
        if battle is None:
            return
        self.assertEqual(battle["status"], "active")
        self.assertEqual(battle["acting_user_id"], challenged_id)

        challenger_dough, _, _ = storage.get_player_info(guild_id, challenger_id)
        challenged_dough, _, _ = storage.get_player_info(guild_id, challenged_id)
        self.assertEqual(challenger_dough, 75)
        self.assertEqual(challenged_dough, 75)

        state = storage.get_battle_state(guild_id, battle_id)
        self.assertIsNotNone(state)
        if state is None:
            return
        challenger_combatants = state["challenger_combatants"]
        challenged_combatants = state["challenged_combatants"]
        self.assertTrue(isinstance(challenger_combatants, list))
        self.assertTrue(isinstance(challenged_combatants, list))
        if isinstance(challenger_combatants, list):
            self.assertEqual(len(challenger_combatants), 1)
            self.assertTrue(bool(challenger_combatants[0]["is_active"]))
            self.assertGreater(int(challenger_combatants[0]["attack"]), 0)
            self.assertGreater(int(challenger_combatants[0]["defense"]), 0)
        if isinstance(challenged_combatants, list):
            self.assertEqual(len(challenged_combatants), 1)
            self.assertTrue(bool(challenged_combatants[0]["is_active"]))
            self.assertGreater(int(challenged_combatants[0]["attack"]), 0)
            self.assertGreater(int(challenged_combatants[0]["defense"]), 0)

    def test_battle_attack_advances_turn(self) -> None:
        guild_id = 1
        challenger_id = 1411
        challenged_id = 1412

        storage.init_db()
        storage.add_dough(guild_id, challenger_id, 100)
        storage.add_dough(guild_id, challenged_id, 100)

        storage.create_player_team(guild_id, challenger_id, "a")
        storage.create_player_team(guild_id, challenged_id, "b")
        storage.set_active_team(guild_id, challenger_id, "a")
        storage.set_active_team(guild_id, challenged_id, "b")

        storage.assign_instance_to_team(
            guild_id,
            challenger_id,
            storage.add_card_to_player(guild_id, challenger_id, "SPG", 120),
            "a",
        )
        storage.assign_instance_to_team(
            guild_id,
            challenged_id,
            storage.add_card_to_player(guild_id, challenged_id, "PEN", 340),
            "b",
        )

        created, _msg, battle_id, _a, _b = storage.create_battle_proposal(guild_id, challenger_id, challenged_id, 10)
        self.assertTrue(created)
        self.assertIsNotNone(battle_id)
        if battle_id is None:
            return
        with patch("noodswap.storage.random.choice", return_value=challenger_id):
            status, _accept_msg = storage.resolve_battle_proposal(guild_id, battle_id, challenged_id, accepted=True)
        self.assertEqual(status, "accepted")

        action_status, _action_message, _winner_id, next_actor_id = storage.execute_battle_turn_action(
            guild_id,
            battle_id,
            challenger_id,
            "attack",
        )
        self.assertIn(action_status, {"advanced", "finished"})
        if action_status == "advanced":
            self.assertEqual(next_actor_id, challenged_id)
            battle = storage.get_battle_session(guild_id, battle_id)
            self.assertIsNotNone(battle)
            if battle is not None:
                self.assertEqual(battle["acting_user_id"], challenged_id)

    def test_battle_surrender_pays_winner(self) -> None:
        guild_id = 1
        challenger_id = 1421
        challenged_id = 1422

        storage.init_db()
        storage.add_dough(guild_id, challenger_id, 100)
        storage.add_dough(guild_id, challenged_id, 100)

        storage.create_player_team(guild_id, challenger_id, "a")
        storage.create_player_team(guild_id, challenged_id, "b")
        storage.set_active_team(guild_id, challenger_id, "a")
        storage.set_active_team(guild_id, challenged_id, "b")

        storage.assign_instance_to_team(
            guild_id,
            challenger_id,
            storage.add_card_to_player(guild_id, challenger_id, "SPG", 120),
            "a",
        )
        storage.assign_instance_to_team(
            guild_id,
            challenged_id,
            storage.add_card_to_player(guild_id, challenged_id, "PEN", 340),
            "b",
        )

        created, _msg, battle_id, _a, _b = storage.create_battle_proposal(guild_id, challenger_id, challenged_id, 25)
        self.assertTrue(created)
        self.assertIsNotNone(battle_id)
        if battle_id is None:
            return
        with patch("noodswap.storage.random.choice", return_value=challenger_id):
            status, _accept_msg = storage.resolve_battle_proposal(guild_id, battle_id, challenged_id, accepted=True)
        self.assertEqual(status, "accepted")

        action_status, _action_message, winner_id, _next_actor = storage.execute_battle_turn_action(
            guild_id,
            battle_id,
            challenger_id,
            "surrender",
        )
        self.assertEqual(action_status, "finished")
        self.assertEqual(winner_id, challenged_id)

        challenger_dough, _, _ = storage.get_player_info(guild_id, challenger_id)
        challenged_dough, _, _ = storage.get_player_info(guild_id, challenged_id)
        self.assertEqual(challenger_dough, 75)
        self.assertEqual(challenged_dough, 125)

    def test_create_battle_proposal_rejects_player_with_open_battle(self) -> None:
        guild_id = 1
        challenger_id = 1501
        challenged_id = 1502
        third_user_id = 1503

        storage.init_db()
        for user_id in (challenger_id, challenged_id, third_user_id):
            storage.add_dough(guild_id, user_id, 100)

        storage.create_player_team(guild_id, challenger_id, "a")
        storage.create_player_team(guild_id, challenged_id, "b")
        storage.create_player_team(guild_id, third_user_id, "c")
        storage.set_active_team(guild_id, challenger_id, "a")
        storage.set_active_team(guild_id, challenged_id, "b")
        storage.set_active_team(guild_id, third_user_id, "c")

        challenger_instance = storage.add_card_to_player(guild_id, challenger_id, "SPG", 100)
        challenged_instance = storage.add_card_to_player(guild_id, challenged_id, "PEN", 101)
        third_instance = storage.add_card_to_player(guild_id, third_user_id, "FUS", 102)
        storage.assign_instance_to_team(guild_id, challenger_id, challenger_instance, "a")
        storage.assign_instance_to_team(guild_id, challenged_id, challenged_instance, "b")
        storage.assign_instance_to_team(guild_id, third_user_id, third_instance, "c")

        created, _message, battle_id, _challenger_team, _challenged_team = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            10,
        )
        self.assertTrue(created)
        self.assertIsNotNone(battle_id)

        created_second, message_second, _battle_id_second, _team_a, _team_c = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            third_user_id,
            10,
        )
        self.assertFalse(created_second)
        self.assertEqual(message_second, "You already have an active or pending battle.")

    def test_end_open_battles_for_shutdown_closes_pending_and_active(self) -> None:
        guild_id = 1
        challenger_id = 1601
        challenged_id = 1602
        pending_challenger_id = 1603
        pending_challenged_id = 1604

        storage.init_db()
        storage.add_dough(guild_id, challenger_id, 100)
        storage.add_dough(guild_id, challenged_id, 100)

        storage.create_player_team(guild_id, challenger_id, "a")
        storage.create_player_team(guild_id, challenged_id, "b")
        storage.set_active_team(guild_id, challenger_id, "a")
        storage.set_active_team(guild_id, challenged_id, "b")

        storage.add_dough(guild_id, pending_challenger_id, 100)
        storage.add_dough(guild_id, pending_challenged_id, 100)
        storage.create_player_team(guild_id, pending_challenger_id, "c")
        storage.create_player_team(guild_id, pending_challenged_id, "d")
        storage.set_active_team(guild_id, pending_challenger_id, "c")
        storage.set_active_team(guild_id, pending_challenged_id, "d")

        challenger_instance = storage.add_card_to_player(guild_id, challenger_id, "SPG", 120)
        challenged_instance = storage.add_card_to_player(guild_id, challenged_id, "PEN", 340)
        storage.assign_instance_to_team(guild_id, challenger_id, challenger_instance, "a")
        storage.assign_instance_to_team(guild_id, challenged_id, challenged_instance, "b")

        pending_challenger_instance = storage.add_card_to_player(guild_id, pending_challenger_id, "FUS", 123)
        pending_challenged_instance = storage.add_card_to_player(guild_id, pending_challenged_id, "MAC", 456)
        storage.assign_instance_to_team(guild_id, pending_challenger_id, pending_challenger_instance, "c")
        storage.assign_instance_to_team(guild_id, pending_challenged_id, pending_challenged_instance, "d")

        created_pending, _msg, pending_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            10,
        )
        self.assertTrue(created_pending)
        self.assertIsNotNone(pending_battle_id)
        if pending_battle_id is None:
            return

        status, _resolve_message = storage.resolve_battle_proposal(
            guild_id,
            pending_battle_id,
            challenged_id,
            accepted=False,
        )
        self.assertEqual(status, "denied")

        created_pending_open, _msg, pending_open_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            pending_challenger_id,
            pending_challenged_id,
            9,
        )
        self.assertTrue(created_pending_open)
        self.assertIsNotNone(pending_open_battle_id)
        if pending_open_battle_id is None:
            return

        created_active, _msg, active_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            15,
        )
        self.assertTrue(created_active)
        self.assertIsNotNone(active_battle_id)
        if active_battle_id is None:
            return

        with patch("noodswap.storage.random.choice", return_value=challenger_id):
            status, _resolve_message = storage.resolve_battle_proposal(
                guild_id,
                active_battle_id,
                challenged_id,
                accepted=True,
            )
        self.assertEqual(status, "accepted")

        created_new_pending, _msg, new_pending_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            20,
        )
        self.assertFalse(created_new_pending)
        self.assertIsNone(new_pending_battle_id)

        ended_count = storage.end_open_battles_for_shutdown()
        self.assertEqual(ended_count, 2)

        active_battle = storage.get_battle_session(guild_id, active_battle_id)
        self.assertIsNotNone(active_battle)
        if active_battle is not None:
            self.assertEqual(active_battle["status"], "finished")
            self.assertEqual(active_battle["last_action"], "Battle ended: bot shutdown.")
            self.assertIsNone(active_battle["acting_user_id"])

        pending_battle = storage.get_battle_session(guild_id, pending_open_battle_id)
        self.assertIsNotNone(pending_battle)
        if pending_battle is not None:
            self.assertEqual(pending_battle["status"], "finished")
            self.assertEqual(pending_battle["last_action"], "Battle ended: bot shutdown.")

        created_after_shutdown, message_after_shutdown, _battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            20,
        )
        self.assertTrue(created_after_shutdown)
        self.assertEqual(message_after_shutdown, "")


if __name__ == "__main__":
    unittest.main()
