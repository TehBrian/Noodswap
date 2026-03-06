import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from noodswap import storage


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
            self.assertIn("last_vote_reward_at", column_names)

            instance_columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            instance_column_names = {str(column[1]) for column in instance_columns}
            self.assertIn("morph_key", instance_column_names)
            self.assertIn("frame_key", instance_column_names)
            self.assertIn("font_key", instance_column_names)

            wishlist_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'wishlist_cards'"
            ).fetchone()
            self.assertIsNotNone(wishlist_row)

            tags_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_tags'"
            ).fetchone()
            self.assertIsNotNone(tags_row)

            instance_tags_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'card_instance_tags'"
            ).fetchone()
            self.assertIsNotNone(instance_tags_row)

    def test_init_db_backfills_legacy_player_cards(self) -> None:
        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            with conn:
                conn.executescript(
                    """
                    CREATE TABLE players (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        dough INTEGER NOT NULL DEFAULT 0,
                        last_pull_at REAL NOT NULL DEFAULT 0,
                        married_card_id TEXT,
                        PRIMARY KEY (guild_id, user_id)
                    );

                    CREATE TABLE player_cards (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        card_id TEXT NOT NULL,
                        quantity INTEGER NOT NULL CHECK(quantity > 0),
                        PRIMARY KEY (guild_id, user_id, card_id)
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO players (guild_id, user_id, dough, last_pull_at, married_card_id) VALUES (?, ?, ?, ?, ?)",
                    (1, 42, 0, 0, None),
                )
                conn.execute(
                    "INSERT INTO player_cards (guild_id, user_id, card_id, quantity) VALUES (?, ?, ?, ?)",
                    (1, 42, "SPG", 2),
                )
                conn.execute(
                    "INSERT INTO player_cards (guild_id, user_id, card_id, quantity) VALUES (?, ?, ?, ?)",
                    (1, 42, "PEN", 1),
                )

        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            count_row = conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()
            self.assertIsNotNone(count_row)
            self.assertEqual(int(count_row[0]), 3)

            version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            self.assertIsNotNone(version_row)
            self.assertEqual(int(version_row[0]), storage.TARGET_SCHEMA_VERSION)

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

    def test_claim_vote_reward_enforces_cooldown_and_adds_starter(self) -> None:
        guild_id = 1
        user_id = 1234

        storage.init_db()

        claimed, remaining, starter_total = storage.claim_vote_reward_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=100_000.0,
            cooldown_seconds=86_400.0,
            reward_amount=1,
        )
        self.assertTrue(claimed)
        self.assertEqual(remaining, 0.0)
        self.assertEqual(starter_total, 1)

        claimed, remaining, starter_total = storage.claim_vote_reward_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=100_001.0,
            cooldown_seconds=86_400.0,
            reward_amount=1,
        )
        self.assertFalse(claimed)
        self.assertGreater(remaining, 0.0)
        self.assertEqual(starter_total, 1)

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

        success, message, traded_generation, traded_dupe_code = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            dupe_code=selected_dupe_code,
            amount=30,
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

        seller_dough, _, _ = storage.get_player_stats(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_stats(guild_id, buyer_id)
        self.assertEqual(seller_dough, 30)
        self.assertEqual(buyer_dough, 70)

    def test_trade_fails_when_seller_has_no_card(self) -> None:
        guild_id = 1
        seller_id = 700
        buyer_id = 701

        storage.init_db()
        storage.add_dough(guild_id, buyer_id, 100)

        success, message, traded_generation, traded_dupe_code = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code="0",
            amount=10,
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: seller no longer has that card code.")
        self.assertIsNone(traded_generation)
        self.assertIsNone(traded_dupe_code)

        seller_dough, _, _ = storage.get_player_stats(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_stats(guild_id, buyer_id)
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

        success, message, traded_generation, traded_dupe_code = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            dupe_code=selected_dupe_code,
            amount=20,
        )

        self.assertFalse(success)
        self.assertEqual(message, "Trade failed: buyer does not have enough dough.")
        self.assertIsNone(traded_generation)
        self.assertIsNone(traded_dupe_code)

        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        self.assertEqual(len(seller_instances), 1)
        self.assertEqual(len(buyer_instances), 0)

        seller_dough, _, _ = storage.get_player_stats(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_stats(guild_id, buyer_id)
        self.assertEqual(seller_dough, 0)
        self.assertEqual(buyer_dough, 5)

    def test_player_leaderboard_stats_aggregates_cards_wishes_and_value(self) -> None:
        guild_id = 1
        first_user = 1100
        second_user = 1200

        storage.init_db()
        storage.add_card_to_player(guild_id, first_user, "SPG", 100)
        storage.add_card_to_player(guild_id, first_user, "PEN", 300)
        storage.add_card_to_player(guild_id, second_user, "SPG", 900)

        storage.add_dough(guild_id, first_user, 25)
        storage.add_dough(guild_id, second_user, 80)
        storage.claim_vote_reward_if_ready(guild_id, first_user, now=1000.0, cooldown_seconds=1.0, reward_amount=2)

        storage.add_card_to_wishlist(guild_id, first_user, "SPG")
        storage.add_card_to_wishlist(guild_id, first_user, "PEN")
        storage.add_card_to_wishlist(guild_id, second_user, "BAR")

        rows = storage.get_player_leaderboard_stats(guild_id)
        by_user = {row[0]: row for row in rows}

        first = by_user[first_user]
        second = by_user[second_user]

        self.assertEqual(first[1], 2)
        self.assertEqual(first[2], 2)
        self.assertEqual(first[3], 25)
        self.assertEqual(first[4], 2)
        self.assertGreater(first[5], 0)

        self.assertEqual(second[1], 1)
        self.assertEqual(second[2], 1)
        self.assertEqual(second[3], 80)
        self.assertEqual(second[4], 0)
        self.assertGreater(second[5], 0)

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
        self.assertEqual(second_message, "That card is already married by another player in this server.")
        self.assertIsNone(second_instance_id)
        self.assertIsNone(second_generation)

    def test_marry_card_instance_fails_if_already_married_to_different_instance(self) -> None:
        guild_id = 1
        user_id = 900
        card_id = "SPG"

        storage.init_db()
        first_instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 100)
        second_instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 200)

        success, message, _, _, _ = storage.marry_card_instance(guild_id, user_id, first_instance_id)
        self.assertTrue(success)
        self.assertEqual(message, "")

        second_success, second_message, second_card_id, second_generation, second_dupe_code = storage.marry_card_instance(
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
        success, message, traded_generation, traded_dupe_code = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            dupe_code=dupe_code,
            amount=10,
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
        self.assertEqual(by_plain_code, by_hash_global)

    def test_init_db_v5_renames_legacy_dupe_id_column(self) -> None:
        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            with conn:
                conn.executescript(
                    """
                    CREATE TABLE schema_migrations (
                        version INTEGER NOT NULL
                    );
                    INSERT INTO schema_migrations(version) VALUES (4);

                    CREATE TABLE card_instances (
                        instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        card_id TEXT NOT NULL,
                        generation INTEGER NOT NULL,
                        dupe_id TEXT
                    );

                    INSERT INTO card_instances (guild_id, user_id, card_id, generation, dupe_id)
                    VALUES (0, 42, 'SPG', 123, 'a');

                    CREATE UNIQUE INDEX idx_card_instances_dupe_id
                        ON card_instances(dupe_id)
                        WHERE dupe_id IS NOT NULL;
                    """
                )

        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            self.assertIsNotNone(version_row)
            self.assertEqual(int(version_row[0]), storage.TARGET_SCHEMA_VERSION)

            columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            column_names = {str(column[1]) for column in columns}
            self.assertIn("dupe_code", column_names)

            value_row = conn.execute("SELECT dupe_code FROM card_instances WHERE instance_id = 1").fetchone()
            self.assertIsNotNone(value_row)
            self.assertEqual(str(value_row[0]), "a")

            index_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_card_instances_dupe_code'"
            ).fetchone()
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

        dough, _, _ = storage.get_player_stats(guild_id, user_id)
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

        dough, _, _ = storage.get_player_stats(guild_id, user_id)
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

        dough, _, _ = storage.get_player_stats(guild_id, user_id)
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

    def test_deleting_tag_cascades_instance_assignments(self) -> None:
        guild_id = 1
        user_id = 1203

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_tag(guild_id, user_id, "archive")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "archive")

        self.assertTrue(storage.delete_player_tag(guild_id, user_id, "archive"))
        self.assertEqual(storage.get_instances_by_tag(guild_id, user_id, "archive"), [])


if __name__ == "__main__":
    unittest.main()
