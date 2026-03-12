import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bot import storage
from bot.services import TradeTerms


class StorageTests:
    def setup_method(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._original_db_path = storage.DB_PATH
        storage.DB_PATH = Path(self._tmp_dir.name) / "test.db"

    def teardown_method(self) -> None:
        storage.DB_PATH = self._original_db_path
        self._tmp_dir.cleanup()

    def test_init_db_creates_schema_version_and_columns(self) -> None:
        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            assert row is not None
            assert int(row[0]) == storage.TARGET_SCHEMA_VERSION

            columns = conn.execute("PRAGMA table_info(players)").fetchall()
            column_names = {str(column[1]) for column in columns}
            assert "married_instance_id" in column_names
            assert "last_dropped_instance_id" in column_names
            assert "starter" in column_names
            assert "drop_tickets" in column_names
            assert "pull_tickets" in column_names
            assert "last_slots_at" in column_names
            assert "last_flip_at" in column_names
            assert "active_team_name" in column_names
            assert "monopoly_position" in column_names
            assert "last_monopoly_roll_at" in column_names
            assert "monopoly_in_jail" in column_names
            assert "monopoly_jail_roll_attempts" in column_names
            assert "monopoly_consecutive_doubles" in column_names

            pot_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'gambling_pot'").fetchone()
            assert pot_row is not None

            instance_columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            instance_column_names = {str(column[1]) for column in instance_columns}
            assert "morph_key" in instance_column_names
            assert "frame_key" in instance_column_names
            assert "font_key" in instance_column_names

            wishlist_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'wishlist_cards'").fetchone()
            assert wishlist_row is not None

            tags_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_tags'").fetchone()
            assert tags_row is not None

            instance_tags_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'card_instance_tags'").fetchone()
            assert instance_tags_row is not None

            teams_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_teams'").fetchone()
            assert teams_row is not None

            team_members_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'team_members'").fetchone()
            assert team_members_row is not None

            battles_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'battle_sessions'").fetchone()
            assert battles_row is not None

    def test_init_db_does_not_create_player_cards_table(self) -> None:
        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_cards'").fetchone()
            assert row is None

    def test_marry_selects_lowest_generation_copy(self) -> None:
        guild_id = 1
        user_id = 100
        card_id = "SPG"

        storage.init_db()
        instance_a = storage.add_card_to_player(guild_id, user_id, card_id, 500)
        instance_b = storage.add_card_to_player(guild_id, user_id, card_id, 50)
        storage.add_card_to_player(guild_id, user_id, card_id, 900)

        success, message, married_instance_id, married_generation = storage.marry_card(guild_id, user_id, card_id)
        assert success
        assert message == ""
        assert married_generation == 50
        assert married_instance_id == instance_b
        assert married_instance_id != instance_a

    def test_get_all_owned_card_instances_returns_all_owners_and_styles(self) -> None:
        guild_id = 1
        owner_a = 100
        owner_b = 200

        storage.init_db()
        instance_a = storage.add_card_to_player(guild_id, owner_a, "SPG", 120)
        instance_b = storage.add_card_to_player(guild_id, owner_b, "PEN", 80)
        with storage.get_db_connection() as conn:
            scoped_guild_id = storage._scope_guild_id(guild_id)
            instances = storage.CardInstanceRepository(conn)
            assert instances.set_morph_key(scoped_guild_id, owner_a, instance_a, "inverse")
            assert instances.set_frame_key(scoped_guild_id, owner_b, instance_b, "buttery")
            assert instances.set_font_key(scoped_guild_id, owner_b, instance_b, "mono")

        rows = storage.get_all_owned_card_instances(guild_id)

        assert rows == [
            (instance_a, owner_a, "SPG", 120, "0", "inverse", None, None),
            (instance_b, owner_b, "PEN", 80, "1", None, "buttery", "mono"),
        ]

    def test_claim_vote_reward_always_adds_starter(self) -> None:
        guild_id = 1
        user_id = 1234

        storage.init_db()

        starter_total = storage.claim_vote_reward(
            guild_id=guild_id,
            user_id=user_id,
            reward_amount=1,
        )
        assert starter_total == 1

        starter_total = storage.claim_vote_reward(
            guild_id=guild_id,
            user_id=user_id,
            reward_amount=1,
        )
        assert starter_total == 2

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
        assert first_remaining == 0.0

        second_remaining = storage.consume_slots_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=5_100.0,
            cooldown_seconds=1_320.0,
        )
        assert second_remaining > 0.0

        starter_total = storage.add_starter(guild_id, user_id, 3)
        assert starter_total == 3
        assert storage.get_player_starter(guild_id, user_id) == 3

    def test_buy_drop_tickets_with_starter_requires_sufficient_balance(self) -> None:
        guild_id = 1
        user_id = 1244

        storage.init_db()
        purchased, starter_balance, drop_tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 2)
        assert not (purchased)
        assert starter_balance == 0
        assert drop_tickets == 0
        assert spent == 0

        storage.add_starter(guild_id, user_id, 3)
        purchased, starter_balance, drop_tickets, spent = storage.buy_drop_tickets_with_starter(guild_id, user_id, 2)
        assert purchased
        assert starter_balance == 1
        assert drop_tickets == 2
        assert spent == 2

    def test_buy_pull_tickets_with_starter_requires_sufficient_balance(self) -> None:
        guild_id = 1
        user_id = 2244

        storage.init_db()
        purchased, starter_balance, pull_tickets, spent = storage.buy_pull_tickets_with_starter(guild_id, user_id, 2)
        assert not (purchased)
        assert starter_balance == 0
        assert pull_tickets == 0
        assert spent == 0

        storage.add_starter(guild_id, user_id, 3)
        purchased, starter_balance, pull_tickets, spent = storage.buy_pull_tickets_with_starter(guild_id, user_id, 2)
        assert purchased
        assert starter_balance == 1
        assert pull_tickets == 2
        assert spent == 2

    def test_consume_pull_cooldown_or_ticket_bypasses_without_changing_timestamp(self) -> None:
        guild_id = 1
        user_id = 2245

        storage.init_db()
        storage.add_starter(guild_id, user_id, 1)
        storage.buy_pull_tickets_with_starter(guild_id, user_id, 1)

        now = 4_000.0
        with storage.get_db_connection() as conn:
            players = storage.PlayerRepository(conn, storage.STARTING_DOUGH)
            players.ensure_player(storage._scope_guild_id(guild_id), user_id)
            players.set_last_pull_at(storage._scope_guild_id(guild_id), user_id, now)

        _last_drop_at, before_last_pull_at = storage.get_player_cooldown_timestamps(guild_id, user_id)

        used_ticket, remaining = storage.consume_pull_cooldown_or_ticket(
            guild_id,
            user_id,
            now=now + 1.0,
            cooldown_seconds=360.0,
        )
        _last_drop_at, after_last_pull_at = storage.get_player_cooldown_timestamps(guild_id, user_id)
        assert used_ticket
        assert remaining == 0.0
        assert before_last_pull_at == after_last_pull_at
        assert storage.get_player_pull_tickets(guild_id, user_id) == 0

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
        assert used_ticket
        assert remaining == 0.0
        assert before_last_drop_at == after_last_drop_at
        assert storage.get_player_drop_tickets(guild_id, user_id) == 0

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
        assert first_remaining == 0.0
        assert storage.get_player_flip_timestamp(guild_id, user_id) == 10_000.0

        second_remaining = storage.consume_flip_cooldown_if_ready(
            guild_id=guild_id,
            user_id=user_id,
            now=10_050.0,
            cooldown_seconds=120.0,
        )
        assert second_remaining > 0.0

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
        assert status == "invalid_stake"
        assert remaining == 0.0
        assert balance == 0

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=1_000.0,
            cooldown_seconds=120.0,
            did_win=True,
        )
        assert status == "insufficient_dough"

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
        assert status == "lost"
        assert remaining == 0.0
        assert balance == 75
        pot_dough, pot_starter, pot_drop_tickets, pot_pull_tickets = storage.get_gambling_pot(guild_id)
        assert pot_dough == 25
        assert pot_starter == 0
        assert pot_drop_tickets == 0
        assert pot_pull_tickets == 0

    def test_monopoly_roll_sets_cooldown_when_not_doubles(self) -> None:
        guild_id = 1
        user_id = 1248
        storage.init_db()

        with patch("bot.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=10_000.0,
                cooldown_seconds=660.0,
            )
        assert result.status == "ok"
        assert not (result.doubles)
        _position, last_roll_at, in_jail, _jail_attempts, doubles_count = storage.get_monopoly_state(guild_id, user_id)
        assert last_roll_at == 10_000.0
        assert not (in_jail)
        assert doubles_count == 0

    def test_monopoly_roll_doubles_does_not_consume_cooldown(self) -> None:
        guild_id = 1
        user_id = 1249
        storage.init_db()

        with patch("bot.storage.roll_dice", return_value=(3, 3, True)):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=20_000.0,
                cooldown_seconds=660.0,
            )
        assert result.status == "ok"
        assert result.doubles
        _position, last_roll_at, in_jail, _jail_attempts, doubles_count = storage.get_monopoly_state(guild_id, user_id)
        assert last_roll_at == 0.0
        assert not (in_jail)
        assert doubles_count == 1

    def test_monopoly_property_rent_is_one_sixth_of_card_value(self) -> None:
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
        expected_rent = full_value // 6

        with patch("bot.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                roller_id,
                now=30_000.0,
                cooldown_seconds=660.0,
            )
        assert result.status == "ok"

        roller_dough, _, _ = storage.get_player_info(guild_id, roller_id)
        owner_dough, _, _ = storage.get_player_info(guild_id, owner_id)
        assert roller_dough == 10_000 - expected_rent
        assert owner_dough == expected_rent

    def test_monopoly_property_landing_uses_card_name_and_thumbnail_metadata(
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

        with patch("bot.storage.roll_dice", return_value=(1, 2, False)):
            result = storage.execute_monopoly_roll(
                guild_id,
                roller_id,
                now=31_000.0,
                cooldown_seconds=660.0,
            )

        card_name = str(storage.CARD_CATALOG[common_card_id]["name"])
        assert any(f"Landed on **{card_name}**" in line for line in result.lines)
        assert result.thumbnail_card_id == common_card_id
        assert result.thumbnail_generation == generation

    def test_monopoly_roll_mpreg_includes_metadata_and_display_line(self) -> None:
        guild_id = 1
        user_id = 1252
        storage.init_db()

        with (
            patch("bot.storage.roll_dice", return_value=(1, 2, False)),
            patch(
                "bot.storage.board_space",
                return_value=SimpleNamespace(kind="mpreg", name="Mpreg", emoji="🤰", rarity=None),
            ),
            patch("bot.storage.random_epic_or_better_card_id", return_value="SPG"),
            patch("bot.storage.random_generation", return_value=321),
        ):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=40_000.0,
                cooldown_seconds=660.0,
            )
        assert result.status == "ok"
        assert result.mpreg_card_id == "SPG"
        assert result.mpreg_generation == 321
        assert result.mpreg_card_code is not None
        assert result.thumbnail_card_id == "SPG"
        assert result.thumbnail_generation == 321

        expected_line = storage.card_display(
            "SPG",
            321,
            card_code=result.mpreg_card_code,
            morph_key=result.mpreg_morph_key,
            frame_key=result.mpreg_frame_key,
            font_key=result.mpreg_font_key,
        )
        assert expected_line in result.lines

    def test_monopoly_card_move_to_free_parking_awards_pot(self) -> None:
        guild_id = 1
        user_id = 1253
        storage.init_db()
        storage.add_dough(guild_id, user_id, 500)

        with storage.get_db_connection() as conn:
            from bot.repositories import GamblingPotRepository

            pot = GamblingPotRepository(conn)
            scoped_guild_id = storage._scope_guild_id(guild_id)
            pot.ensure_row(scoped_guild_id)
            pot.add(scoped_guild_id, dough=1234)

        chance_space = SimpleNamespace(kind="chance", name="Cheese Chance", emoji="❓", rarity=None)
        free_parking_space = SimpleNamespace(
            kind="free_parking",
            name="Free Parking",
            emoji="🅿️",
            rarity=None,
        )

        with (
            patch("bot.storage.roll_dice", return_value=(1, 2, False)),
            patch("bot.storage.board_space", side_effect=[chance_space, free_parking_space]),
            patch(
                "bot.storage.draw_cheese_chance",
                return_value=SimpleNamespace(
                    text="Advance to Free Parking.",
                    dough_delta=0,
                    starter_delta=0,
                    drop_tickets_delta=0,
                    pull_tickets_delta=0,
                    move_to=20,
                    go_to_jail=False,
                    reset_random_cooldown=False,
                ),
            ),
        ):
            result = storage.execute_monopoly_roll(
                guild_id,
                user_id,
                now=50_000.0,
                cooldown_seconds=660.0,
            )
        assert result.status == "ok"
        assert any("jackpot" in line for line in result.lines)

        pot_dough, pot_starter, pot_drop_tickets, pot_pull_tickets = storage.get_gambling_pot(guild_id)
        assert pot_dough == 0
        assert pot_starter == 0
        assert pot_drop_tickets == 0
        assert pot_pull_tickets == 0

        player_dough, _, _ = storage.get_player_info(guild_id, user_id)
        assert player_dough == 1734

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
        assert status == "won"
        assert remaining == 0.0
        assert balance == 60

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=2_030.0,
            cooldown_seconds=120.0,
            did_win=False,
        )
        assert status == "cooldown"
        assert remaining > 0.0
        assert balance == 60

        status, remaining, balance = storage.execute_flip_wager(
            guild_id,
            user_id,
            stake=10,
            now=2_150.0,
            cooldown_seconds=120.0,
            did_win=False,
        )
        assert status == "lost"
        assert remaining == 0.0
        assert balance == 50

    def test_burn_candidate_selects_highest_generation_copy(self) -> None:
        guild_id = 1
        user_id = 101
        card_id = "PEN"

        storage.init_db()
        storage.add_card_to_player(guild_id, user_id, card_id, 5)
        storage.add_card_to_player(guild_id, user_id, card_id, 900)
        storage.add_card_to_player(guild_id, user_id, card_id, 400)

        selected = storage.get_burn_candidate_by_card_id(guild_id, user_id, card_id)
        assert selected is not None
        if selected is None:
            return
        _instance_id, selected_card_id, selected_generation, _selected_card_code = selected
        assert selected_card_id == card_id
        assert selected_generation == 900

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
        assert selected is not None
        if selected is None:
            return
        _, _, _, selected_card_code = selected

        success, message, traded_generation, traded_card_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            card_code=selected_card_code,
            terms=TradeTerms(mode="dough", amount=30),
        )
        assert success
        assert message == ""
        assert traded_generation == 800
        assert traded_card_code is not None

        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        assert len(seller_instances) == 1
        assert seller_instances[0][2] == 20
        assert len(buyer_instances) == 1
        assert buyer_instances[0][2] == 800

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        assert seller_dough == 30
        assert buyer_dough == 70

    def test_trade_fails_when_seller_has_no_card(self) -> None:
        guild_id = 1
        seller_id = 700
        buyer_id = 701

        storage.init_db()
        storage.add_dough(guild_id, buyer_id, 100)

        success, message, traded_generation, traded_card_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code="0",
            terms=TradeTerms(mode="dough", amount=10),
        )
        assert not (success)
        assert message == "Trade failed: seller no longer has that card code."
        assert traded_generation is None
        assert traded_card_code is None

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        assert seller_dough == 0
        assert buyer_dough == 100

    def test_trade_fails_when_buyer_has_insufficient_dough(self) -> None:
        guild_id = 1
        seller_id = 702
        buyer_id = 703

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_dough(guild_id, buyer_id, 5)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, selected_card_code = selected

        success, message, traded_generation, traded_card_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=selected_card_code,
            terms=TradeTerms(mode="dough", amount=20),
        )
        assert not (success)
        assert message == "Trade failed: buyer does not have enough dough."
        assert traded_generation is None
        assert traded_card_code is None

        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        assert len(seller_instances) == 1
        assert len(buyer_instances) == 0

        seller_dough, _, _ = storage.get_player_info(guild_id, seller_id)
        buyer_dough, _, _ = storage.get_player_info(guild_id, buyer_id)
        assert seller_dough == 0
        assert buyer_dough == 5

    def test_trade_starter_mode_transfers_card_and_starter(self) -> None:
        guild_id = 1
        seller_id = 740
        buyer_id = 741

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 10)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, card_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=card_code,
            terms=TradeTerms(mode="starter", amount=4),
        )
        assert success
        assert message == ""
        assert gen == 100
        assert received is None

        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        assert len(buyer_instances) == 1
        assert buyer_instances[0][1] == "SPG"
        assert storage.get_player_starter(guild_id, seller_id) == 4
        assert storage.get_player_starter(guild_id, buyer_id) == 6

    def test_trade_starter_mode_fails_when_buyer_has_insufficient_starter(self) -> None:
        guild_id = 1
        seller_id = 742
        buyer_id = 743

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 2)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, card_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=card_code,
            terms=TradeTerms(mode="starter", amount=5),
        )
        assert not (success)
        assert message == "Trade failed: buyer does not have enough starter."
        assert gen is None
        assert received is None
        # Nothing transferred
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        assert len(seller_instances) == 1
        assert storage.get_player_starter(guild_id, buyer_id) == 2

    def test_trade_tickets_mode_transfers_card_and_tickets(self) -> None:
        guild_id = 1
        seller_id = 744
        buyer_id = 745

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 5)
        storage.buy_drop_tickets_with_starter(guild_id, buyer_id, 5)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, card_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=card_code,
            terms=TradeTerms(mode="drop", amount=3),
        )
        assert success
        assert message == ""
        assert gen == 100
        assert received is None

        buyer_instances = storage.get_player_card_instances(guild_id, buyer_id)
        assert len(buyer_instances) == 1
        assert storage.get_player_drop_tickets(guild_id, seller_id) == 3
        assert storage.get_player_drop_tickets(guild_id, buyer_id) == 2

    def test_trade_tickets_mode_fails_when_buyer_has_insufficient_tickets(self) -> None:
        guild_id = 1
        seller_id = 746
        buyer_id = 747

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 1)
        storage.buy_drop_tickets_with_starter(guild_id, buyer_id, 1)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, card_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=card_code,
            terms=TradeTerms(mode="drop", amount=5),
        )
        assert not (success)
        assert message == "Trade failed: buyer does not have enough drop tickets."
        assert gen is None
        assert received is None
        seller_instances = storage.get_player_card_instances(guild_id, seller_id)
        assert len(seller_instances) == 1

    def test_trade_pull_tickets_mode_transfers_card_and_tickets(self) -> None:
        guild_id = 1
        seller_id = 1744
        buyer_id = 1745

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, "SPG", 100)
        storage.add_starter(guild_id, buyer_id, 5)
        storage.buy_pull_tickets_with_starter(guild_id, buyer_id, 5)
        selected = storage.get_burn_candidate_by_card_id(guild_id, seller_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _, _, card_code = selected

        success, message, gen, _dupe, received = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=card_code,
            terms=TradeTerms(mode="pull", amount=3),
        )
        assert success
        assert message == ""
        assert gen == 100
        assert received is None
        assert storage.get_player_pull_tickets(guild_id, seller_id) == 3
        assert storage.get_player_pull_tickets(guild_id, buyer_id) == 2

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
            card_code=seller_dupe,
            terms=TradeTerms(mode="card", req_card_code=buyer_dupe),
        )
        assert success
        assert message == ""
        assert gen == 100
        assert received is not None
        if received is None:
            return
        r_card_id, r_gen, _r_dupe = received
        assert r_card_id == "PEN"
        assert r_gen == 200

        seller_after = storage.get_player_card_instances(guild_id, seller_id)
        buyer_after = storage.get_player_card_instances(guild_id, buyer_id)
        assert len(seller_after) == 1
        assert seller_after[0][1] == "PEN"
        assert len(buyer_after) == 1
        assert buyer_after[0][1] == "SPG"

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
            card_code=seller_dupe,
            terms=TradeTerms(mode="card", req_card_code="zzz"),
        )
        assert not (success)
        assert message == "Trade failed: buyer no longer has the requested card."
        assert gen is None
        assert received is None
        # Seller still has their card
        seller_instances_after = storage.get_player_card_instances(guild_id, seller_id)
        assert len(seller_instances_after) == 1

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
        assert storage.get_last_pulled_instance(guild_id, seller_id) is not None
        assert storage.get_last_pulled_instance(guild_id, buyer_id) is not None

        success, _, _, _, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id="SPG",
            card_code=seller_dupe,
            terms=TradeTerms(mode="card", req_card_code=buyer_dupe),
        )
        assert success

        # Both marriages cleared (index 2 = married_instance_id)
        seller_info = storage.get_player_info(guild_id, seller_id)
        buyer_info = storage.get_player_info(guild_id, buyer_id)
        assert seller_info[2] is None
        assert buyer_info[2] is None

    def test_gift_card_transfers_selected_instance_without_dough_change(self) -> None:
        guild_id = 1
        sender_id = 720
        recipient_id = 721

        storage.init_db()
        storage.add_card_to_player(guild_id, sender_id, "SPG", 100)
        storage.add_card_to_player(guild_id, sender_id, "SPG", 200)
        selected = storage.get_burn_candidate_by_card_id(guild_id, sender_id, "SPG")
        assert selected is not None
        if selected is None:
            return
        _, _card_id, _generation, selected_card_code = selected

        success, message, gifted_card_id, gifted_generation, gifted_card_code = storage.execute_gift_card(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            card_code=selected_card_code,
        )
        assert success
        assert message == ""
        assert gifted_card_id == "SPG"
        assert gifted_generation == 200
        assert gifted_card_code == selected_card_code

        sender_instances = storage.get_player_card_instances(guild_id, sender_id)
        recipient_instances = storage.get_player_card_instances(guild_id, recipient_id)
        assert len(sender_instances) == 1
        assert sender_instances[0][2] == 100
        assert len(recipient_instances) == 1
        assert recipient_instances[0][2] == 200

        sender_dough, _, _ = storage.get_player_info(guild_id, sender_id)
        recipient_dough, _, _ = storage.get_player_info(guild_id, recipient_id)
        assert sender_dough == 0
        assert recipient_dough == 0

    def test_gift_card_clears_sender_last_pulled_pointer(self) -> None:
        guild_id = 1
        sender_id = 722
        recipient_id = 723

        storage.init_db()
        storage.add_card_to_player(guild_id, sender_id, "SPG", 300)
        selected = storage.get_last_pulled_instance(guild_id, sender_id)
        assert selected is not None
        if selected is None:
            return
        _instance_id, _card_id, _generation, card_code = selected

        success, message, gifted_card_id, gifted_generation, gifted_card_code = storage.execute_gift_card(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            card_code=card_code,
        )
        assert success
        assert message == ""
        assert gifted_card_id == "SPG"
        assert gifted_generation == 300
        assert gifted_card_code == card_code
        assert storage.get_last_pulled_instance(guild_id, sender_id) is None

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
        assert gifted
        assert message == ""
        assert sender_balance == 2
        assert recipient_balance == 3
        assert storage.get_player_starter(guild_id, sender_id) == 2
        assert storage.get_player_starter(guild_id, recipient_id) == 3

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
        assert not (gifted)
        assert message == "You do not have enough starter."
        assert sender_balance == 1
        assert recipient_balance == 0
        assert storage.get_player_starter(guild_id, sender_id) == 1
        assert storage.get_player_starter(guild_id, recipient_id) == 0

    def test_gift_drop_tickets_transfers_balances(self) -> None:
        guild_id = 1
        sender_id = 734
        recipient_id = 735

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 4)
        purchased, _starter, _tickets, _spent = storage.buy_drop_tickets_with_starter(guild_id, sender_id, 4)
        assert purchased

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_drop_tickets(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=3,
        )
        assert gifted
        assert message == ""
        assert sender_balance == 1
        assert recipient_balance == 3
        assert storage.get_player_drop_tickets(guild_id, sender_id) == 1
        assert storage.get_player_drop_tickets(guild_id, recipient_id) == 3

    def test_gift_drop_tickets_fails_when_insufficient_balance(self) -> None:
        guild_id = 1
        sender_id = 736
        recipient_id = 737

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 1)
        purchased, _starter, _tickets, _spent = storage.buy_drop_tickets_with_starter(guild_id, sender_id, 1)
        assert purchased

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_drop_tickets(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=2,
        )
        assert not (gifted)
        assert message == "You do not have enough drop tickets."
        assert sender_balance == 1
        assert recipient_balance == 0
        assert storage.get_player_drop_tickets(guild_id, sender_id) == 1
        assert storage.get_player_drop_tickets(guild_id, recipient_id) == 0

    def test_gift_pull_tickets_transfers_balances(self) -> None:
        guild_id = 1
        sender_id = 1734
        recipient_id = 1735

        storage.init_db()
        storage.add_starter(guild_id, sender_id, 4)
        purchased, _starter, _tickets, _spent = storage.buy_pull_tickets_with_starter(guild_id, sender_id, 4)
        assert purchased

        gifted, message, sender_balance, recipient_balance = storage.execute_gift_pull_tickets(
            guild_id=guild_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=3,
        )
        assert gifted
        assert message == ""
        assert sender_balance == 1
        assert recipient_balance == 3
        assert storage.get_player_pull_tickets(guild_id, sender_id) == 1
        assert storage.get_player_pull_tickets(guild_id, recipient_id) == 3

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
        assert first[1] == 2
        assert first[2] == 2
        assert first[3] == 25
        assert first[4] == 2
        assert first[5] == 1
        assert first[6] > 0
        assert second[1] == 1
        assert second[2] == 1
        assert second[3] == 80
        assert second[4] == 0
        assert second[5] == 0
        assert second[6] > 0

    def test_marry_fails_if_card_already_married_by_another_player(self) -> None:
        guild_id = 1
        first_user = 800
        second_user = 801
        card_id = "SPG"

        storage.init_db()
        storage.add_card_to_player(guild_id, first_user, card_id, 120)
        storage.add_card_to_player(guild_id, second_user, card_id, 130)

        first_success, first_message, _, _ = storage.marry_card(guild_id, first_user, card_id)
        assert first_success
        assert first_message == ""

        second_success, second_message, second_instance_id, second_generation = storage.marry_card(
            guild_id,
            second_user,
            card_id,
        )
        assert not (second_success)
        assert second_message == "That card is already married by another player."
        assert second_instance_id is None
        assert second_generation is None

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
        assert success
        assert message == ""

        (
            second_success,
            second_message,
            second_card_id,
            second_generation,
            second_card_code,
        ) = storage.marry_card_instance(
            guild_id,
            user_id,
            second_instance_id,
        )
        assert not (second_success)
        assert second_message == "You are already married. Use `ns divorce` first."
        assert second_card_id is None
        assert second_generation is None
        assert second_card_code is None

    def test_remove_card_clears_last_pulled_pointer(self) -> None:
        guild_id = 1
        user_id = 910
        card_id = "SPG"

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, card_id, 250)

        removed = storage.remove_card_from_player(guild_id, user_id, card_id)
        assert removed is not None
        if removed is None:
            return
        removed_instance_id, removed_generation = removed
        assert removed_instance_id == instance_id
        assert removed_generation == 250
        assert storage.get_last_pulled_instance(guild_id, user_id) is None

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
        assert storage.get_last_pulled_instance(guild_id, user_id) is None

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT last_dropped_instance_id FROM players WHERE guild_id = ? AND user_id = ?",
                (storage.GLOBAL_GUILD_ID, user_id),
            ).fetchone()
        assert row is not None
        if row is None:
            return
        assert row[0] is None

    def test_get_last_pulled_instance_clears_pointer_after_trade_transfer(self) -> None:
        guild_id = 1
        seller_id = 913
        buyer_id = 914
        card_id = "SPG"

        storage.init_db()
        storage.add_card_to_player(guild_id, seller_id, card_id, 300)
        selected = storage.get_last_pulled_instance(guild_id, seller_id)
        assert selected is not None
        if selected is None:
            return
        _instance_id, _card_id, _generation, card_code = selected

        storage.add_dough(guild_id, buyer_id, 100)
        success, message, traded_generation, traded_card_code, _ = storage.execute_trade(
            guild_id=guild_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            card_id=card_id,
            card_code=card_code,
            terms=TradeTerms(mode="dough", amount=10),
        )
        assert success
        assert message == ""
        assert traded_generation == 300
        assert traded_card_code == card_code
        assert storage.get_last_pulled_instance(guild_id, seller_id) is None

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            row = conn.execute(
                "SELECT last_dropped_instance_id FROM players WHERE guild_id = ? AND user_id = ?",
                (storage.GLOBAL_GUILD_ID, seller_id),
            ).fetchone()
        assert row is not None
        if row is None:
            return
        assert row[0] is None

    def test_card_codes_assign_sequential_and_reuse_lowest_free(self) -> None:
        guild_id = 1
        user_id = 911

        storage.init_db()
        instance_0 = storage.add_card_to_player(guild_id, user_id, "SPG", 100)
        instance_1 = storage.add_card_to_player(guild_id, user_id, "PEN", 101)
        instance_2 = storage.add_card_to_player(guild_id, user_id, "FUS", 102)

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            dupe_rows = conn.execute(
                "SELECT instance_id, card_code FROM card_instances WHERE guild_id = ? ORDER BY instance_id ASC",
                (storage.GLOBAL_GUILD_ID,),
            ).fetchall()
        dupe_by_instance = {int(row[0]): str(row[1]) for row in dupe_rows}
        assert dupe_by_instance[instance_0] == "0"
        assert dupe_by_instance[instance_1] == "1"
        assert dupe_by_instance[instance_2] == "2"

        burned = storage.burn_instance(guild_id, user_id, instance_1)
        assert burned is not None

        reused_instance = storage.add_card_to_player(guild_id, user_id, "MAC", 103)
        next_instance = storage.add_card_to_player(guild_id, user_id, "LIN", 104)

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            dupe_rows = conn.execute(
                "SELECT instance_id, card_code FROM card_instances WHERE guild_id = ? ORDER BY instance_id ASC",
                (storage.GLOBAL_GUILD_ID,),
            ).fetchall()
        dupe_by_instance = {int(row[0]): str(row[1]) for row in dupe_rows}
        assert dupe_by_instance[reused_instance] == "1"
        assert dupe_by_instance[next_instance] == "3"

    def test_get_instance_by_code_accepts_hash_prefix(self) -> None:
        guild_id = 1
        user_id = 915

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 123)
        instance = storage.get_instance_by_id(guild_id, instance_id)
        assert instance is not None
        if instance is None:
            return
        _found_instance_id, _card_id, _generation, card_code = instance

        by_plain_code = storage.get_instance_by_code(guild_id, user_id, card_code.upper())
        by_hash_code = storage.get_instance_by_code(guild_id, user_id, f"#{card_code.upper()}")
        by_hash_global = storage.get_instance_by_card_code(guild_id, f"#{card_code.upper()}")
        assert by_plain_code == by_hash_code
        assert by_hash_global is not None
        if by_hash_global is None or by_plain_code is None:
            return

        (
            global_instance_id,
            global_user_id,
            global_card_id,
            global_generation,
            global_card_code,
            global_dropped_by_user_id,
            global_pulled_by_user_id,
        ) = by_hash_global
        plain_instance_id, plain_card_id, plain_generation, plain_card_code = by_plain_code
        assert global_user_id == user_id
        assert (global_instance_id, global_card_id, global_generation, global_card_code) == (plain_instance_id, plain_card_id, plain_generation, plain_card_code)
        assert global_dropped_by_user_id is None
        assert global_pulled_by_user_id is None

    def test_init_db_v5_ensures_card_code_column_and_index(self) -> None:
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
            assert version_row is not None
            assert int(version_row[0]) == storage.TARGET_SCHEMA_VERSION

            columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            column_names = {str(column[1]) for column in columns}
            assert "card_code" in column_names

            index_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_card_instances_card_code'").fetchone()
            assert index_row is not None

    def test_init_db_v26_renames_legacy_dupe_code_column(self) -> None:
        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            with conn:
                conn.executescript("""
                    CREATE TABLE schema_migrations (
                        version INTEGER NOT NULL
                    );
                    INSERT INTO schema_migrations(version) VALUES (25);

                    CREATE TABLE card_instances (
                        instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        card_type_id TEXT NOT NULL,
                        generation INTEGER NOT NULL,
                        dupe_code TEXT,
                        morph_key TEXT,
                        frame_key TEXT,
                        font_key TEXT
                    );

                    CREATE UNIQUE INDEX idx_card_instances_dupe_code
                        ON card_instances(dupe_code)
                        WHERE dupe_code IS NOT NULL;

                    INSERT INTO card_instances (guild_id, user_id, card_type_id, generation, dupe_code)
                    VALUES (0, 42, 'SPG', 123, 'a');
                    """)

        storage.init_db()

        with closing(sqlite3.connect(storage.DB_PATH)) as conn:
            version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
            assert version_row is not None
            assert int(version_row[0]) == storage.TARGET_SCHEMA_VERSION

            columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
            column_names = {str(column[1]) for column in columns}
            assert "card_code" in column_names
            assert "dupe_code" not in column_names

            row = conn.execute("SELECT card_code FROM card_instances LIMIT 1").fetchone()
            assert row is not None
            assert str(row[0]) == "a"

            index_row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_card_instances_card_code'").fetchone()
            assert index_row is not None

    def test_wishlist_add_remove_and_read(self) -> None:
        guild_id = 1
        user_id = 920

        storage.init_db()

        added = storage.add_card_to_wishlist(guild_id, user_id, "SPG")
        assert added

        added_again = storage.add_card_to_wishlist(guild_id, user_id, "SPG")
        assert not (added_again)

        storage.add_card_to_wishlist(guild_id, user_id, "PEN")

        cards = storage.get_wishlist_cards(guild_id, user_id)
        assert cards == ["PEN", "SPG"]

        removed = storage.remove_card_from_wishlist(guild_id, user_id, "SPG")
        assert removed
        assert storage.get_wishlist_cards(guild_id, user_id) == ["PEN"]

        removed_missing = storage.remove_card_from_wishlist(guild_id, user_id, "SPG")
        assert not (removed_missing)

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
        assert applied
        assert message == ""
        assert storage.get_instance_morph(guild_id, instance_id) == "black_and_white"

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        assert dough == 41

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
        assert not (applied)
        assert message == "You do not have enough dough."
        assert storage.get_instance_morph(guild_id, instance_id) is None

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
        assert applied
        assert message == ""
        assert storage.get_instance_frame(guild_id, instance_id) == "buttery"

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        assert dough == 41

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
        assert not (applied)
        assert message == "You do not have enough dough."
        assert storage.get_instance_frame(guild_id, instance_id) is None

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
        assert applied
        assert message == ""
        assert storage.get_instance_font(guild_id, instance_id) == "serif"

        dough, _, _ = storage.get_player_info(guild_id, user_id)
        assert dough == 41

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
        assert not (applied)
        assert message == "You do not have enough dough."
        assert storage.get_instance_font(guild_id, instance_id) is None

    def test_wishlist_is_global_across_guilds(self) -> None:
        user_id = 930

        storage.init_db()

        storage.add_card_to_wishlist(1, user_id, "SPG")
        storage.add_card_to_wishlist(2, user_id, "PEN")
        assert storage.get_wishlist_cards(1, user_id) == ["PEN", "SPG"]
        assert storage.get_wishlist_cards(2, user_id) == ["PEN", "SPG"]

    def test_get_card_wish_counts_aggregates_per_card(self) -> None:
        storage.init_db()

        storage.add_card_to_wishlist(1, 1000, "SPG")
        storage.add_card_to_wishlist(1, 1001, "SPG")
        storage.add_card_to_wishlist(1, 1002, "PEN")
        storage.add_card_to_wishlist(2, 1003, "SPG")

        counts_guild_1 = storage.get_card_wish_counts(1)
        counts_guild_2 = storage.get_card_wish_counts(2)
        assert counts_guild_1.get("SPG") == 3
        assert counts_guild_1.get("PEN") == 1
        assert counts_guild_1.get("FUS") is None
        assert counts_guild_2.get("SPG") == 3

    def test_player_tags_create_list_lock_and_delete(self) -> None:
        guild_id = 1
        user_id = 1200

        storage.init_db()
        assert storage.create_player_tag(guild_id, user_id, "Favorites")
        assert not (storage.create_player_tag(guild_id, user_id, "favorites"))

        listed = storage.list_player_tags(guild_id, user_id)
        assert listed == [("favorites", False, 0)]
        assert storage.set_player_tag_locked(guild_id, user_id, "Favorites", True)
        listed_after_lock = storage.list_player_tags(guild_id, user_id)
        assert listed_after_lock == [("favorites", True, 0)]
        assert storage.delete_player_tag(guild_id, user_id, "Favorites")
        assert storage.list_player_tags(guild_id, user_id) == []

    def test_assign_and_unassign_tag_to_card_instance(self) -> None:
        guild_id = 1
        user_id = 1201

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 111)
        storage.create_player_tag(guild_id, user_id, "food")
        assert storage.assign_tag_to_instance(guild_id, user_id, instance_id, "food")
        assert not (storage.assign_tag_to_instance(guild_id, user_id, instance_id, "food"))

        tagged = storage.get_instances_by_tag(guild_id, user_id, "food")
        assert len(tagged) == 1
        assert tagged[0][0] == instance_id
        assert storage.unassign_tag_from_instance(guild_id, user_id, instance_id, "food")
        assert not (storage.unassign_tag_from_instance(guild_id, user_id, instance_id, "food"))

    def test_locked_tag_blocks_burn(self) -> None:
        guild_id = 1
        user_id = 1202

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 222)
        storage.create_player_tag(guild_id, user_id, "keep")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "keep")
        storage.set_player_tag_locked(guild_id, user_id, "keep", True)

        locked_tags = storage.get_locked_tags_for_instance(guild_id, user_id, instance_id)
        assert locked_tags == ["keep"]

        burned = storage.burn_instance(guild_id, user_id, instance_id)
        assert burned is None

        still_owned = storage.get_instance_by_id(guild_id, instance_id)
        assert still_owned is not None

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
        assert burned_rows is None
        assert locked_instance in locked_by_instance
        assert storage.get_instance_by_id(guild_id, open_instance) is not None
        assert storage.get_instance_by_id(guild_id, locked_instance) is not None

    def test_deleting_tag_cascades_instance_assignments(self) -> None:
        guild_id = 1
        user_id = 1203

        storage.init_db()
        instance_id = storage.add_card_to_player(guild_id, user_id, "SPG", 333)
        storage.create_player_tag(guild_id, user_id, "archive")
        storage.assign_tag_to_instance(guild_id, user_id, instance_id, "archive")
        assert storage.delete_player_tag(guild_id, user_id, "archive")
        assert storage.get_instances_by_tag(guild_id, user_id, "archive") == []

    def test_team_assignment_enforces_three_card_limit(self) -> None:
        guild_id = 1
        user_id = 1301

        storage.init_db()
        assert storage.create_player_team(guild_id, user_id, "alpha")

        instance_ids = [
            storage.add_card_to_player(guild_id, user_id, "SPG", 100),
            storage.add_card_to_player(guild_id, user_id, "PEN", 200),
            storage.add_card_to_player(guild_id, user_id, "FUS", 300),
            storage.add_card_to_player(guild_id, user_id, "MAC", 400),
        ]

        for instance_id in instance_ids[:3]:
            success, message = storage.assign_instance_to_team(guild_id, user_id, instance_id, "alpha")
            assert success
            assert message == ""

        success, message = storage.assign_instance_to_team(guild_id, user_id, instance_ids[3], "alpha")
        assert not (success)
        assert message == "Team capacity reached (3 cards max)."

    def test_set_active_team_and_list_marks_active(self) -> None:
        guild_id = 1
        user_id = 1302

        storage.init_db()
        storage.create_player_team(guild_id, user_id, "alpha")
        storage.create_player_team(guild_id, user_id, "beta")
        assert storage.set_active_team(guild_id, user_id, "beta")
        assert storage.get_active_team_name(guild_id, user_id) == "beta"

        listed = storage.list_player_teams(guild_id, user_id)
        assert listed == [("alpha", 0, False), ("beta", 0, True)]

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
        assert created
        assert message == ""
        assert battle_id is not None
        assert challenger_team == "a"
        assert challenged_team == "b"

        if battle_id is None:
            return

        with patch("bot.storage.random.choice", return_value=challenged_id):
            status, resolve_message = storage.resolve_battle_proposal(
                guild_id,
                battle_id,
                challenged_id,
                accepted=True,
            )
        assert status == "accepted"
        assert resolve_message == "Battle accepted. The battle arena is now active."

        battle = storage.get_battle_session(guild_id, battle_id)
        assert battle is not None
        if battle is None:
            return
        assert battle["status"] == "active"
        assert battle["acting_user_id"] == challenged_id

        challenger_dough, _, _ = storage.get_player_info(guild_id, challenger_id)
        challenged_dough, _, _ = storage.get_player_info(guild_id, challenged_id)
        assert challenger_dough == 75
        assert challenged_dough == 75

        state = storage.get_battle_state(guild_id, battle_id)
        assert state is not None
        if state is None:
            return
        challenger_combatants = state["challenger_combatants"]
        challenged_combatants = state["challenged_combatants"]
        assert isinstance(challenger_combatants, list)
        assert isinstance(challenged_combatants, list)
        if isinstance(challenger_combatants, list):
            assert len(challenger_combatants) == 1
            assert bool(challenger_combatants[0]["is_active"])
            assert int(challenger_combatants[0]["attack"]) > 0
            assert int(challenger_combatants[0]["defense"]) > 0
        if isinstance(challenged_combatants, list):
            assert len(challenged_combatants) == 1
            assert bool(challenged_combatants[0]["is_active"])
            assert int(challenged_combatants[0]["attack"]) > 0
            assert int(challenged_combatants[0]["defense"]) > 0

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
        assert created
        assert battle_id is not None
        if battle_id is None:
            return
        with patch("bot.storage.random.choice", return_value=challenger_id):
            status, _accept_msg = storage.resolve_battle_proposal(guild_id, battle_id, challenged_id, accepted=True)
        assert status == "accepted"

        action_status, _action_message, _winner_id, next_actor_id = storage.execute_battle_turn_action(
            guild_id,
            battle_id,
            challenger_id,
            "attack",
        )
        assert action_status in {"advanced", "finished"}
        if action_status == "advanced":
            assert next_actor_id == challenged_id
            battle = storage.get_battle_session(guild_id, battle_id)
            assert battle is not None
            if battle is not None:
                assert battle["acting_user_id"] == challenged_id

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
        assert created
        assert battle_id is not None
        if battle_id is None:
            return
        with patch("bot.storage.random.choice", return_value=challenger_id):
            status, _accept_msg = storage.resolve_battle_proposal(guild_id, battle_id, challenged_id, accepted=True)
        assert status == "accepted"

        action_status, _action_message, winner_id, _next_actor = storage.execute_battle_turn_action(
            guild_id,
            battle_id,
            challenger_id,
            "surrender",
        )
        assert action_status == "finished"
        assert winner_id == challenged_id

        challenger_dough, _, _ = storage.get_player_info(guild_id, challenger_id)
        challenged_dough, _, _ = storage.get_player_info(guild_id, challenged_id)
        assert challenger_dough == 75
        assert challenged_dough == 125

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
        assert created
        assert battle_id is not None

        created_second, message_second, _battle_id_second, _team_a, _team_c = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            third_user_id,
            10,
        )
        assert not (created_second)
        assert message_second == "You already have an active or pending battle."

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
        assert created_pending
        assert pending_battle_id is not None
        if pending_battle_id is None:
            return

        status, _resolve_message = storage.resolve_battle_proposal(
            guild_id,
            pending_battle_id,
            challenged_id,
            accepted=False,
        )
        assert status == "denied"

        created_pending_open, _msg, pending_open_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            pending_challenger_id,
            pending_challenged_id,
            9,
        )
        assert created_pending_open
        assert pending_open_battle_id is not None
        if pending_open_battle_id is None:
            return

        created_active, _msg, active_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            15,
        )
        assert created_active
        assert active_battle_id is not None
        if active_battle_id is None:
            return

        with patch("bot.storage.random.choice", return_value=challenger_id):
            status, _resolve_message = storage.resolve_battle_proposal(
                guild_id,
                active_battle_id,
                challenged_id,
                accepted=True,
            )
        assert status == "accepted"

        created_new_pending, _msg, new_pending_battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            20,
        )
        assert not (created_new_pending)
        assert new_pending_battle_id is None

        ended_count = storage.end_open_battles_for_shutdown()
        assert ended_count == 2

        active_battle = storage.get_battle_session(guild_id, active_battle_id)
        assert active_battle is not None
        if active_battle is not None:
            assert active_battle["status"] == "finished"
            assert active_battle["last_action"] == "Battle ended: bot shutdown."
            assert active_battle["acting_user_id"] is None

        pending_battle = storage.get_battle_session(guild_id, pending_open_battle_id)
        assert pending_battle is not None
        if pending_battle is not None:
            assert pending_battle["status"] == "finished"
            assert pending_battle["last_action"] == "Battle ended: bot shutdown."

        created_after_shutdown, message_after_shutdown, _battle_id, _a, _b = storage.create_battle_proposal(
            guild_id,
            challenger_id,
            challenged_id,
            20,
        )
        assert created_after_shutdown
        assert message_after_shutdown == ""
