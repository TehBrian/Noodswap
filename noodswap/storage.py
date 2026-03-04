import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from .cards import random_generation, split_card_code
from .settings import (
    DB_LOCK_TIMEOUT_SECONDS,
    DB_PATH,
    GENERATION_MAX,
    GENERATION_MIN,
    STARTING_DOUGH,
)


TARGET_SCHEMA_VERSION = 5
GLOBAL_GUILD_ID = 0
_BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def _scope_guild_id(_guild_id: int) -> int:
    return GLOBAL_GUILD_ID


def _to_base36(value: int) -> str:
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    if value == 0:
        return "0"

    digits: list[str] = []
    remainder = value
    while remainder > 0:
        remainder, index = divmod(remainder, 36)
        digits.append(_BASE36_ALPHABET[index])
    return "".join(reversed(digits))


def _from_base36(value: str) -> int:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("base36 string cannot be empty")

    result = 0
    for character in normalized:
        index = _BASE36_ALPHABET.find(character)
        if index < 0:
            raise ValueError(f"invalid base36 digit: {character}")
        result = (result * 36) + index
    return result


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


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]) == column for row in rows)


def _ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER NOT NULL
        )
        """
    )

    row = conn.execute("SELECT COUNT(*) AS c FROM schema_migrations").fetchone()
    count = int(row["c"]) if row is not None else 0
    if count == 0:
        conn.execute("INSERT INTO schema_migrations(version) VALUES (0)")
    elif count > 1:
        current = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        max_version = int(current["v"]) if current is not None and current["v"] is not None else 0
        conn.execute("DELETE FROM schema_migrations")
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (max_version,))


def _get_schema_version(conn: sqlite3.Connection) -> int:
    _ensure_schema_migrations_table(conn)
    row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
    if row is None:
        return 0
    return int(row["version"])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE schema_migrations SET version = ?", (version,))


def _apply_migration_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            dough INTEGER NOT NULL DEFAULT 0,
            last_pull_at REAL NOT NULL DEFAULT 0,
            married_card_id TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS player_cards (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_id TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            PRIMARY KEY (guild_id, user_id, card_id),
            FOREIGN KEY (guild_id, user_id)
                REFERENCES players(guild_id, user_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_players_married
            ON players(guild_id, married_card_id);

        CREATE TABLE IF NOT EXISTS card_instances (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_id TEXT NOT NULL,
            generation INTEGER NOT NULL,
            FOREIGN KEY (guild_id, user_id)
                REFERENCES players(guild_id, user_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_card_instances_owner
            ON card_instances(guild_id, user_id, card_id, generation);
        """
    )

    if not _has_column(conn, "players", "married_instance_id"):
        conn.execute("ALTER TABLE players ADD COLUMN married_instance_id INTEGER")
    if not _has_column(conn, "players", "last_dropped_instance_id"):
        conn.execute("ALTER TABLE players ADD COLUMN last_dropped_instance_id INTEGER")

    migrated_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM card_instances
        """
    ).fetchone()
    already_migrated = int(migrated_row["c"]) > 0 if migrated_row else False

    if not already_migrated:
        rows = conn.execute(
            """
            SELECT guild_id, user_id, card_id, quantity
            FROM player_cards
            """
        ).fetchall()
        for row in rows:
            quantity = int(row["quantity"])
            for _ in range(quantity):
                conn.execute(
                    """
                    INSERT INTO card_instances (guild_id, user_id, card_id, generation)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        int(row["guild_id"]),
                        int(row["user_id"]),
                        str(row["card_id"]),
                        random_generation(),
                    ),
                )


def _apply_migration_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS wishlist_cards (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            card_id TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, card_id),
            FOREIGN KEY (guild_id, user_id)
                REFERENCES players(guild_id, user_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_wishlist_owner
            ON wishlist_cards(guild_id, user_id, card_id);
        """
    )


def _next_available_dupe_code(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT dupe_code
        FROM card_instances
        WHERE dupe_code IS NOT NULL
        """,
    ).fetchall()

    used_numbers: set[int] = set()
    for row in rows:
        raw_dupe_code = row["dupe_code"]
        if raw_dupe_code is None:
            continue

        try:
            used_numbers.add(_from_base36(str(raw_dupe_code)))
        except ValueError:
            continue

    candidate = 0
    while candidate in used_numbers:
        candidate += 1
    return _to_base36(candidate)


def _apply_migration_v3(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "card_instances", "dupe_code"):
        conn.execute("ALTER TABLE card_instances ADD COLUMN dupe_code TEXT")

    guild_rows = conn.execute(
        """
        SELECT DISTINCT guild_id
        FROM card_instances
        ORDER BY guild_id ASC
        """
    ).fetchall()

    for guild_row in guild_rows:
        guild_id = int(guild_row["guild_id"])
        rows = conn.execute(
            """
            SELECT instance_id, dupe_code
            FROM card_instances
            WHERE guild_id = ?
            ORDER BY instance_id ASC
            """,
            (guild_id,),
        ).fetchall()

        assigned_numbers: set[int] = set()
        for row in rows:
            instance_id = int(row["instance_id"])
            raw_dupe_code = row["dupe_code"]

            if raw_dupe_code is not None:
                try:
                    number = _from_base36(str(raw_dupe_code))
                    if number not in assigned_numbers:
                        assigned_numbers.add(number)
                        continue
                except ValueError:
                    pass

            candidate = 0
            while candidate in assigned_numbers:
                candidate += 1
            assigned_numbers.add(candidate)

            conn.execute(
                """
                UPDATE card_instances
                SET dupe_code = ?
                WHERE instance_id = ?
                """,
                (_to_base36(candidate), instance_id),
            )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_card_instances_dupe_code
            ON card_instances(guild_id, dupe_code)
            WHERE dupe_code IS NOT NULL
        """
    )


def _apply_migration_v4(conn: sqlite3.Connection) -> None:
    dupe_column = "dupe_code" if _has_column(conn, "card_instances", "dupe_code") else "dupe_id"

    player_rows = conn.execute(
        """
        SELECT user_id, COALESCE(SUM(dough), 0) AS total_dough, COALESCE(MAX(last_pull_at), 0) AS max_last_pull
        FROM players
        GROUP BY user_id
        """
    ).fetchall()

    for row in player_rows:
        user_id = int(row["user_id"])
        total_dough = int(row["total_dough"])
        max_last_pull = float(row["max_last_pull"])
        conn.execute(
            """
            INSERT INTO players (guild_id, user_id, dough, last_pull_at, married_card_id, married_instance_id, last_dropped_instance_id)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ON CONFLICT(guild_id, user_id) DO UPDATE
            SET dough = excluded.dough,
                last_pull_at = excluded.last_pull_at,
                married_card_id = NULL,
                married_instance_id = NULL,
                last_dropped_instance_id = NULL
            """,
            (GLOBAL_GUILD_ID, user_id, total_dough, max_last_pull),
        )

    conn.execute(
        """
        UPDATE card_instances
        SET guild_id = ?
        """,
        (GLOBAL_GUILD_ID,),
    )
    conn.execute(
        """
        UPDATE wishlist_cards
        SET guild_id = ?
        """,
        (GLOBAL_GUILD_ID,),
    )

    conn.execute(
        """
        DELETE FROM wishlist_cards
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM wishlist_cards
            GROUP BY guild_id, user_id, card_id
        )
        """
    )

    conn.execute(
        """
        DELETE FROM players
        WHERE guild_id != ?
        """,
        (GLOBAL_GUILD_ID,),
    )

    rows = conn.execute(
        """
        SELECT instance_id
        FROM card_instances
        ORDER BY instance_id ASC
        """
    ).fetchall()
    for idx, row in enumerate(rows):
        instance_id = int(row["instance_id"])
        conn.execute(
            f"""
            UPDATE card_instances
            SET {dupe_column} = ?
            WHERE instance_id = ?
            """,
            (_to_base36(idx), instance_id),
        )

    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_id")
    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_code")
    conn.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_card_instances_dupe_code
            ON card_instances({dupe_column})
            WHERE {dupe_column} IS NOT NULL
        """
    )


def _apply_migration_v5(conn: sqlite3.Connection) -> None:
    has_dupe_code = _has_column(conn, "card_instances", "dupe_code")
    has_dupe_id = _has_column(conn, "card_instances", "dupe_id")

    if not has_dupe_code and has_dupe_id:
        conn.execute("ALTER TABLE card_instances RENAME COLUMN dupe_id TO dupe_code")
    elif not has_dupe_code and not has_dupe_id:
        conn.execute("ALTER TABLE card_instances ADD COLUMN dupe_code TEXT")

    has_dupe_code = _has_column(conn, "card_instances", "dupe_code")
    has_dupe_id = _has_column(conn, "card_instances", "dupe_id")
    if has_dupe_code and has_dupe_id:
        conn.execute(
            """
            UPDATE card_instances
            SET dupe_code = dupe_id
            WHERE dupe_code IS NULL AND dupe_id IS NOT NULL
            """
        )

    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_id")
    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_code")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_card_instances_dupe_code
            ON card_instances(dupe_code)
            WHERE dupe_code IS NOT NULL
        """
    )


def init_db() -> None:
    with get_db_connection() as conn:
        _begin_immediate(conn)
        current_version = _get_schema_version(conn)

        if current_version < 1:
            _apply_migration_v1(conn)
            _set_schema_version(conn, 1)
            current_version = 1

        if current_version < 2:
            _apply_migration_v2(conn)
            _set_schema_version(conn, 2)
            current_version = 2

        if current_version < 3:
            _apply_migration_v3(conn)
            _set_schema_version(conn, 3)
            current_version = 3

        if current_version < 4:
            _apply_migration_v4(conn)
            _set_schema_version(conn, 4)
            current_version = 4

        if current_version < 5:
            _apply_migration_v5(conn)
            _set_schema_version(conn, 5)
            current_version = 5

        if current_version > TARGET_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported {TARGET_SCHEMA_VERSION}."
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
        ensure_player(conn, guild_id, user_id)
        rows = conn.execute(
            """
            SELECT card_id
            FROM wishlist_cards
            WHERE guild_id = ? AND user_id = ?
            ORDER BY card_id ASC
            """,
            (guild_id, user_id),
        ).fetchall()
    return [str(row["card_id"]) for row in rows]


def add_card_to_wishlist(guild_id: int, user_id: int, card_id: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO wishlist_cards (guild_id, user_id, card_id)
            VALUES (?, ?, ?)
            """,
            (guild_id, user_id, card_id),
        )
        return int(cursor.rowcount) > 0


def remove_card_from_wishlist(guild_id: int, user_id: int, card_id: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        cursor = conn.execute(
            """
            DELETE FROM wishlist_cards
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            """,
            (guild_id, user_id, card_id),
        )
        return int(cursor.rowcount) > 0


def get_card_wish_counts(guild_id: int) -> dict[str, int]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT card_id, COUNT(*) AS wish_count
            FROM wishlist_cards
            WHERE guild_id = ?
            GROUP BY card_id
            """,
            (guild_id,),
        ).fetchall()
    return {str(row["card_id"]): int(row["wish_count"]) for row in rows}


def ensure_player(conn: sqlite3.Connection, guild_id: int, user_id: int) -> None:
    guild_id = _scope_guild_id(guild_id)
    conn.execute(
        """
        INSERT INTO players (
            guild_id,
            user_id,
            dough,
            last_pull_at,
            married_card_id,
            married_instance_id,
            last_dropped_instance_id
        )
        VALUES (?, ?, ?, 0, NULL, NULL, NULL)
        ON CONFLICT(guild_id, user_id) DO NOTHING
        """,
        (guild_id, user_id, STARTING_DOUGH),
    )


def get_player_stats(guild_id: int, user_id: int) -> tuple[int, float, Optional[int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT dough, last_pull_at, married_instance_id
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return STARTING_DOUGH, 0.0, None
        married_instance_id = row["married_instance_id"]
        return int(row["dough"]), float(row["last_pull_at"]), int(married_instance_id) if married_instance_id is not None else None


def get_instance_by_id(guild_id: int, instance_id: int) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT instance_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND instance_id = ?
            """,
            (guild_id, instance_id),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])


def get_instance_by_code(guild_id: int, user_id: int, card_code: str) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    parsed = split_card_code(card_code)
    if parsed is None:
        return None

    dupe_code = parsed
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT instance_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND dupe_code = ?
            LIMIT 1
            """,
            (guild_id, user_id, dupe_code),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])


def set_last_pull_at(guild_id: int, user_id: int, timestamp: float) -> None:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        conn.execute(
            """
            UPDATE players
            SET last_pull_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )


def get_card_quantity(guild_id: int, user_id: int, card_id: str) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            """,
            (guild_id, user_id, card_id),
        ).fetchone()
        return int(row["c"]) if row else 0


def add_card_to_player(guild_id: int, user_id: int, card_id: str, generation: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    if generation < GENERATION_MIN or generation > GENERATION_MAX:
        raise ValueError("generation out of allowed bounds")

    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        dupe_code = _next_available_dupe_code(conn)
        cursor = conn.execute(
            """
            INSERT INTO card_instances (guild_id, user_id, card_id, generation, dupe_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, card_id, generation, dupe_code),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to persist card instance")
        instance_id = int(cursor.lastrowid)
        conn.execute(
            """
            UPDATE players
            SET last_dropped_instance_id = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (instance_id, guild_id, user_id),
        )
        return instance_id


def get_last_dropped_instance(guild_id: int, user_id: int) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT p.last_dropped_instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM players p
            LEFT JOIN card_instances ci ON ci.instance_id = p.last_dropped_instance_id
            WHERE p.guild_id = ? AND p.user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if (
            row is None
            or row["last_dropped_instance_id"] is None
            or row["card_id"] is None
            or row["generation"] is None
            or row["dupe_code"] is None
        ):
            return None
        return int(row["last_dropped_instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])


def get_burn_candidate_by_card_id(guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT instance_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            ORDER BY generation DESC, instance_id ASC
            LIMIT 1
            """,
            (guild_id, user_id, card_id),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])


def get_player_card_instances(guild_id: int, user_id: int) -> list[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        rows = conn.execute(
            """
            SELECT instance_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            ORDER BY generation ASC, card_id ASC, instance_id ASC
            """,
            (guild_id, user_id),
        ).fetchall()

    return [
        (int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"]))
        for row in rows
    ]


def get_total_cards(guild_id: int, user_id: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT COUNT(*) AS total_cards
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["total_cards"]) if row else 0


def add_dough(guild_id: int, user_id: int, amount: int) -> None:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        conn.execute(
            """
            UPDATE players
            SET dough = dough + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )


def remove_card_from_player(guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT instance_id, generation
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            ORDER BY generation DESC, instance_id ASC
            LIMIT 1
            """,
            (guild_id, user_id, card_id),
        ).fetchone()
        if row is None:
            return None

        instance_id = int(row["instance_id"])
        generation = int(row["generation"])

        conn.execute(
            """
            DELETE FROM card_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        )

        conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL,
                married_card_id = NULL
            WHERE guild_id = ? AND user_id = ? AND married_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )
        conn.execute(
            """
            UPDATE players
            SET last_dropped_instance_id = NULL
            WHERE guild_id = ? AND user_id = ? AND last_dropped_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )

        return instance_id, generation


def burn_instance(guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT card_id, generation, dupe_code
            FROM card_instances
            WHERE instance_id = ? AND guild_id = ? AND user_id = ?
            """,
            (instance_id, guild_id, user_id),
        ).fetchone()
        if row is None:
            return None

        card_id = str(row["card_id"])
        generation = int(row["generation"])
        dupe_code = str(row["dupe_code"])

        conn.execute(
            """
            DELETE FROM card_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        )
        conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL,
                married_card_id = NULL
            WHERE guild_id = ? AND user_id = ? AND married_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )
        conn.execute(
            """
            UPDATE players
            SET last_dropped_instance_id = NULL
            WHERE guild_id = ? AND user_id = ? AND last_dropped_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )

        return card_id, generation, dupe_code


def _select_instance_for_marry(
    conn: sqlite3.Connection,
    guild_id: int,
    user_id: int,
    card_id: str,
) -> Optional[tuple[int, int]]:
    row = conn.execute(
        """
        SELECT instance_id, generation
        FROM card_instances
        WHERE guild_id = ? AND user_id = ? AND card_id = ?
        ORDER BY generation ASC, instance_id ASC
        LIMIT 1
        """,
        (guild_id, user_id, card_id),
    ).fetchone()
    if row is None:
        return None
    return int(row["instance_id"]), int(row["generation"])


def marry_card(guild_id: int, user_id: int, card_id: str) -> tuple[bool, str, Optional[int], Optional[int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)

        selected = _select_instance_for_marry(conn, guild_id, user_id, card_id)
        if selected is None:
            return False, "You can only marry a card you own.", None, None

        selected_instance_id, selected_generation = selected

        row = conn.execute(
            """
            SELECT married_instance_id
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        married_instance_id = int(row["married_instance_id"]) if row and row["married_instance_id"] is not None else None

        if married_instance_id is not None and married_instance_id != selected_instance_id:
            return False, "You are already married. Use `ns divorce` first.", None, None

        owner_row = conn.execute(
            """
            SELECT p.user_id
            FROM players p
            JOIN card_instances ci ON ci.instance_id = p.married_instance_id
            WHERE p.guild_id = ? AND ci.card_id = ? AND p.user_id != ?
            LIMIT 1
            """,
            (guild_id, card_id, user_id),
        ).fetchone()
        if owner_row is not None:
            return False, "That card is already married by another player in this server.", None, None

        conn.execute(
            """
            UPDATE players
            SET married_instance_id = ?, married_card_id = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (selected_instance_id, card_id, guild_id, user_id),
        )
        return True, "", selected_instance_id, selected_generation


def marry_card_instance(
    guild_id: int,
    user_id: int,
    instance_id: int,
) -> tuple[bool, str, Optional[str], Optional[int], Optional[str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)

        selected_row = conn.execute(
            """
            SELECT card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        ).fetchone()
        if selected_row is None:
            return False, "You can only marry a card you own.", None, None, None

        selected_card_id = str(selected_row["card_id"])
        selected_generation = int(selected_row["generation"])
        selected_dupe_code = str(selected_row["dupe_code"])

        row = conn.execute(
            """
            SELECT married_instance_id
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        married_instance_id = int(row["married_instance_id"]) if row and row["married_instance_id"] is not None else None

        if married_instance_id is not None and married_instance_id != instance_id:
            return False, "You are already married. Use `ns divorce` first.", None, None, None

        owner_row = conn.execute(
            """
            SELECT p.user_id
            FROM players p
            JOIN card_instances ci ON ci.instance_id = p.married_instance_id
            WHERE p.guild_id = ? AND ci.card_id = ? AND p.user_id != ?
            LIMIT 1
            """,
            (guild_id, selected_card_id, user_id),
        ).fetchone()
        if owner_row is not None:
            return False, "That card is already married by another player in this server.", None, None, None

        conn.execute(
            """
            UPDATE players
            SET married_instance_id = ?, married_card_id = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (instance_id, selected_card_id, guild_id, user_id),
        )
        return True, "", selected_card_id, selected_generation, selected_dupe_code


def divorce_card(guild_id: int, user_id: int) -> Optional[tuple[str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        ensure_player(conn, guild_id, user_id)
        row = conn.execute(
            """
            SELECT p.married_instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM players p
            LEFT JOIN card_instances ci ON ci.instance_id = p.married_instance_id
            WHERE p.guild_id = ? AND p.user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        if row is None or row["married_instance_id"] is None or row["card_id"] is None or row["dupe_code"] is None:
            conn.execute(
                """
                UPDATE players
                SET married_instance_id = NULL, married_card_id = NULL
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
            return None

        card_id = str(row["card_id"])
        generation = int(row["generation"])
        dupe_code = str(row["dupe_code"])

        conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL, married_card_id = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )

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
        ensure_player(conn, guild_id, seller_id)
        ensure_player(conn, guild_id, buyer_id)

        seller_card_row = conn.execute(
            """
            SELECT instance_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND dupe_code = ?
            LIMIT 1
            """,
            (guild_id, seller_id, dupe_code),
        ).fetchone()
        if seller_card_row is None:
            return False, "Trade failed: seller no longer has that card code.", None, None

        buyer_row = conn.execute(
            """
            SELECT dough
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, buyer_id),
        ).fetchone()
        buyer_dough = int(buyer_row["dough"]) if buyer_row else STARTING_DOUGH
        if buyer_dough < amount:
            return False, "Trade failed: buyer does not have enough dough.", None, None

        instance_id = int(seller_card_row["instance_id"])
        generation = int(seller_card_row["generation"])
        dupe_code = str(seller_card_row["dupe_code"])

        conn.execute(
            """
            UPDATE card_instances
            SET user_id = ?
            WHERE instance_id = ?
            """,
            (buyer_id, instance_id),
        )
        conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL,
                married_card_id = NULL
            WHERE guild_id = ? AND user_id = ? AND married_instance_id = ?
            """,
            (guild_id, seller_id, instance_id),
        )

        conn.execute(
            """
            UPDATE players
            SET dough = dough + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, seller_id),
        )
        conn.execute(
            """
            UPDATE players
            SET dough = dough - ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, buyer_id),
        )

        return True, "", generation, dupe_code
