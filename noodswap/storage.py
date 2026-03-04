import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from .cards import random_generation, split_card_code
from .migrations import TARGET_SCHEMA_VERSION, run_migrations
from .repositories import CardInstanceRepository, PlayerRepository, WishlistRepository
from .settings import (
    DB_LOCK_TIMEOUT_SECONDS,
    DB_PATH,
    GENERATION_MAX,
    GENERATION_MIN,
    STARTING_DOUGH,
)


GLOBAL_GUILD_ID = 0


def _scope_guild_id(_guild_id: int) -> int:
    return GLOBAL_GUILD_ID


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=DB_LOCK_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _begin_immediate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")


def init_db() -> None:
    with get_db_connection() as conn:
        _begin_immediate(conn)
        run_migrations(
            conn,
            target_schema_version=TARGET_SCHEMA_VERSION,
            global_guild_id=GLOBAL_GUILD_ID,
            random_generation_func=random_generation,
        )


def reset_db_data() -> None:
    with get_db_connection() as conn:
        _begin_immediate(conn)
        conn.execute("DELETE FROM wishlist_cards")
        conn.execute("DELETE FROM card_instances")
        conn.execute("DELETE FROM player_cards")
        conn.execute("DELETE FROM players")


def get_wishlist_cards(guild_id: int, user_id: int) -> list[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        wishlist = WishlistRepository(conn)
        players.ensure_player(guild_id, user_id)
        return wishlist.list_cards(guild_id, user_id)


def add_card_to_wishlist(guild_id: int, user_id: int, card_id: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        wishlist = WishlistRepository(conn)
        players.ensure_player(guild_id, user_id)
        return wishlist.add(guild_id, user_id, card_id)


def remove_card_from_wishlist(guild_id: int, user_id: int, card_id: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        wishlist = WishlistRepository(conn)
        players.ensure_player(guild_id, user_id)
        return wishlist.remove(guild_id, user_id, card_id)


def get_card_wish_counts(guild_id: int) -> dict[str, int]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        wishlist = WishlistRepository(conn)
        return wishlist.get_card_wish_counts(guild_id)


def ensure_player(conn: sqlite3.Connection, guild_id: int, user_id: int) -> None:
    guild_id = _scope_guild_id(guild_id)
    PlayerRepository(conn, STARTING_DOUGH).ensure_player(guild_id, user_id)


def get_player_stats(guild_id: int, user_id: int) -> tuple[int, float, Optional[int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_stats(guild_id, user_id)


def get_instance_by_id(guild_id: int, instance_id: int) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_by_id(guild_id, instance_id)


def get_instance_by_code(guild_id: int, user_id: int, card_code: str) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    parsed = split_card_code(card_code)
    if parsed is None:
        return None

    dupe_code = parsed
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        return instances.get_by_code(guild_id, user_id, dupe_code)


def get_instance_by_dupe_code(guild_id: int, card_code: str) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    parsed = split_card_code(card_code)
    if parsed is None:
        return None

    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_by_dupe_code(guild_id, parsed)


def set_last_drop_at(guild_id: int, user_id: int, timestamp: float) -> None:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        players.set_last_drop_at(guild_id, user_id, timestamp)


def get_card_quantity(guild_id: int, user_id: int, card_id: str) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        return instances.count_by_card(guild_id, user_id, card_id)


def add_card_to_player(guild_id: int, user_id: int, card_id: str, generation: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    if generation < GENERATION_MIN or generation > GENERATION_MAX:
        raise ValueError("generation out of allowed bounds")

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        instance_id = instances.create_owned_instance(guild_id, user_id, card_id, generation)
        players.set_last_pulled_instance(guild_id, user_id, instance_id)
        return instance_id


def get_last_pulled_instance(guild_id: int, user_id: int) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_last_pulled_instance(guild_id, user_id)


def get_burn_candidate_by_card_id(guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        return instances.get_burn_candidate_by_card_id(guild_id, user_id, card_id)


def get_player_card_instances(guild_id: int, user_id: int) -> list[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        return instances.list_by_owner(guild_id, user_id)


def get_total_cards(guild_id: int, user_id: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        return instances.count_by_owner(guild_id, user_id)


def add_dough(guild_id: int, user_id: int, amount: int) -> None:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        players.add_dough(guild_id, user_id, amount)


def remove_card_from_player(guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        removed = instances.pop_highest_generation_by_card(guild_id, user_id, card_id)
        if removed is None:
            return None

        instance_id, generation = removed
        players.clear_marriage_if_matches(guild_id, user_id, instance_id)
        players.clear_last_pulled_if_matches(guild_id, user_id, instance_id)

        return instance_id, generation


def burn_instance(guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)
        burned = instances.burn_owned_instance(guild_id, user_id, instance_id)
        if burned is None:
            return None

        players.clear_marriage_if_matches(guild_id, user_id, instance_id)
        players.clear_last_pulled_if_matches(guild_id, user_id, instance_id)
        return burned


def _select_instance_for_marry(
    conn: sqlite3.Connection,
    guild_id: int,
    user_id: int,
    card_id: str,
) -> Optional[tuple[int, int]]:
    instances = CardInstanceRepository(conn)
    return instances.select_instance_for_marry(guild_id, user_id, card_id)


def marry_card(guild_id: int, user_id: int, card_id: str) -> tuple[bool, str, Optional[int], Optional[int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        selected = _select_instance_for_marry(conn, guild_id, user_id, card_id)
        if selected is None:
            return False, "You can only marry a card you own.", None, None

        selected_instance_id, selected_generation = selected

        married_instance_id = players.get_married_instance_id(guild_id, user_id)

        if married_instance_id is not None and married_instance_id != selected_instance_id:
            return False, "You are already married. Use `ns divorce` first.", None, None

        owner = players.find_other_owner_of_married_card(guild_id, card_id, user_id)
        if owner is not None:
            return False, "That card is already married by another player in this server.", None, None

        players.set_marriage(guild_id, user_id, selected_instance_id, card_id)
        return True, "", selected_instance_id, selected_generation


def marry_card_instance(
    guild_id: int,
    user_id: int,
    instance_id: int,
) -> tuple[bool, str, Optional[str], Optional[int], Optional[str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)

        selected = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if selected is None:
            return False, "You can only marry a card you own.", None, None, None

        selected_card_id, selected_generation, selected_dupe_code = selected

        married_instance_id = players.get_married_instance_id(guild_id, user_id)

        if married_instance_id is not None and married_instance_id != instance_id:
            return False, "You are already married. Use `ns divorce` first.", None, None, None

        owner = players.find_other_owner_of_married_card(guild_id, selected_card_id, user_id)
        if owner is not None:
            return False, "That card is already married by another player in this server.", None, None, None

        players.set_marriage(guild_id, user_id, instance_id, selected_card_id)
        return True, "", selected_card_id, selected_generation, selected_dupe_code


def divorce_card(guild_id: int, user_id: int) -> Optional[tuple[str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        selected = players.get_divorce_instance(guild_id, user_id)

        if selected is None:
            players.clear_marriage(guild_id, user_id)
            return None

        _instance_id, card_id, generation, dupe_code = selected
        players.clear_marriage(guild_id, user_id)

        return card_id, generation, dupe_code


def execute_trade(
    guild_id: int,
    seller_id: int,
    buyer_id: int,
    card_id: str,
    dupe_code: str,
    amount: int,
) -> tuple[bool, str, Optional[int], Optional[str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, seller_id)
        players.ensure_player(guild_id, buyer_id)

        seller_trade_instance = instances.get_seller_trade_instance(guild_id, seller_id, dupe_code)
        if seller_trade_instance is None:
            return False, "Trade failed: seller no longer has that card code.", None, None

        buyer_dough = players.get_dough(guild_id, buyer_id)
        if buyer_dough < amount:
            return False, "Trade failed: buyer does not have enough dough.", None, None

        instance_id, generation, traded_dupe_code = seller_trade_instance

        instances.transfer_to_user(instance_id, buyer_id)
        players.clear_marriage_if_matches(guild_id, seller_id, instance_id)
        players.clear_last_pulled_if_matches(guild_id, seller_id, instance_id)
        players.add_dough(guild_id, seller_id, amount)
        players.add_dough(guild_id, buyer_id, -amount)

        return True, "", generation, traded_dupe_code
