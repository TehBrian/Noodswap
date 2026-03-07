from collections.abc import Callable
import sqlite3


TARGET_SCHEMA_VERSION = 12
_BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]) == column for row in rows)


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


def _apply_migration_v1(conn: sqlite3.Connection, random_generation_func: Callable[[], int]) -> None:
    _ = random_generation_func
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


def _apply_migration_v4(conn: sqlite3.Connection, global_guild_id: int) -> None:
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
            (global_guild_id, user_id, total_dough, max_last_pull),
        )

    conn.execute(
        """
        UPDATE card_instances
        SET guild_id = ?
        """,
        (global_guild_id,),
    )
    conn.execute(
        """
        UPDATE wishlist_cards
        SET guild_id = ?
        """,
        (global_guild_id,),
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
        (global_guild_id,),
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
            """
            UPDATE card_instances
            SET dupe_code = ?
            WHERE instance_id = ?
            """,
            (_to_base36(idx), instance_id),
        )

    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_code")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_card_instances_dupe_code
            ON card_instances(dupe_code)
            WHERE dupe_code IS NOT NULL
        """
    )


def _apply_migration_v5(conn: sqlite3.Connection) -> None:
    has_dupe_code = _has_column(conn, "card_instances", "dupe_code")
    if not has_dupe_code:
        conn.execute("ALTER TABLE card_instances ADD COLUMN dupe_code TEXT")

    conn.execute("DROP INDEX IF EXISTS idx_card_instances_dupe_code")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_card_instances_dupe_code
            ON card_instances(dupe_code)
            WHERE dupe_code IS NOT NULL
        """
    )


def _apply_migration_v6(conn: sqlite3.Connection) -> None:
    players_table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'players'
        LIMIT 1
        """
    ).fetchone() is not None
    if not players_table_exists:
        return

    if not _has_column(conn, "players", "last_drop_at"):
        conn.execute("ALTER TABLE players ADD COLUMN last_drop_at REAL NOT NULL DEFAULT 0")

    # Before v6, last_pull_at tracked drop command usage. Preserve that history as
    # drop cooldown state and reset pull cooldown state for the new split model.
    conn.execute(
        """
        UPDATE players
        SET last_drop_at = last_pull_at
        WHERE last_drop_at = 0
        """
    )
    conn.execute(
        """
        UPDATE players
        SET last_pull_at = 0
        """
    )


def _apply_migration_v7(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "card_instances", "morph_key"):
        conn.execute("ALTER TABLE card_instances ADD COLUMN morph_key TEXT")


def _apply_migration_v8(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS player_tags (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            is_locked INTEGER NOT NULL DEFAULT 0 CHECK(is_locked IN (0, 1)),
            PRIMARY KEY (guild_id, user_id, tag_name),
            FOREIGN KEY (guild_id, user_id)
                REFERENCES players(guild_id, user_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_player_tags_owner
            ON player_tags(guild_id, user_id, tag_name);

        CREATE TABLE IF NOT EXISTS card_instance_tags (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            instance_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, instance_id, tag_name),
            FOREIGN KEY (guild_id, user_id, tag_name)
                REFERENCES player_tags(guild_id, user_id, tag_name)
                ON DELETE CASCADE,
            FOREIGN KEY (instance_id)
                REFERENCES card_instances(instance_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_card_instance_tags_owner
            ON card_instance_tags(guild_id, user_id, tag_name, instance_id);

        CREATE INDEX IF NOT EXISTS idx_card_instance_tags_instance
            ON card_instance_tags(instance_id);
        """
    )


def _apply_migration_v9(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "card_instances", "frame_key"):
        conn.execute("ALTER TABLE card_instances ADD COLUMN frame_key TEXT")


def _apply_migration_v10(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "card_instances", "font_key"):
        conn.execute("ALTER TABLE card_instances ADD COLUMN font_key TEXT")


def _apply_migration_v11(conn: sqlite3.Connection) -> None:
    _ = conn


def _apply_migration_v12(conn: sqlite3.Connection) -> None:
    players_table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'players'
        LIMIT 1
        """
    ).fetchone() is not None
    if not players_table_exists:
        return

    if not _has_column(conn, "players", "starter"):
        conn.execute("ALTER TABLE players ADD COLUMN starter INTEGER NOT NULL DEFAULT 0")

    if not _has_column(conn, "players", "last_vote_reward_at"):
        conn.execute("ALTER TABLE players ADD COLUMN last_vote_reward_at REAL NOT NULL DEFAULT 0")


def run_migrations(
    conn: sqlite3.Connection,
    *,
    target_schema_version: int,
    global_guild_id: int,
    random_generation_func: Callable[[], int],
) -> int:
    current_version = _get_schema_version(conn)

    if current_version < 1:
        _apply_migration_v1(conn, random_generation_func)
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
        _apply_migration_v4(conn, global_guild_id)
        _set_schema_version(conn, 4)
        current_version = 4

    if current_version < 5:
        _apply_migration_v5(conn)
        _set_schema_version(conn, 5)
        current_version = 5

    if current_version < 6:
        _apply_migration_v6(conn)
        _set_schema_version(conn, 6)
        current_version = 6

    if current_version < 7:
        _apply_migration_v7(conn)
        _set_schema_version(conn, 7)
        current_version = 7

    if current_version < 8:
        _apply_migration_v8(conn)
        _set_schema_version(conn, 8)
        current_version = 8

    if current_version < 9:
        _apply_migration_v9(conn)
        _set_schema_version(conn, 9)
        current_version = 9

    if current_version < 10:
        _apply_migration_v10(conn)
        _set_schema_version(conn, 10)
        current_version = 10

    if current_version < 11:
        _apply_migration_v11(conn)
        _set_schema_version(conn, 11)
        current_version = 11

    if current_version < 12:
        _apply_migration_v12(conn)
        _set_schema_version(conn, 12)
        current_version = 12

    if current_version > target_schema_version:
        raise RuntimeError(
            f"Database schema version {current_version} is newer than supported {target_schema_version}."
        )

    return current_version
