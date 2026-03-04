import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap import storage


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _run_fresh_init_validation() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "fresh.db"
        original_db_path = storage.DB_PATH
        try:
            storage.DB_PATH = db_path
            storage.init_db()

            with closing(sqlite3.connect(db_path)) as conn:
                _assert(_table_exists(conn, "schema_migrations"), "schema_migrations table was not created")
                version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
                _assert(version_row is not None, "schema_migrations has no version row")
                _assert(int(version_row[0]) == storage.TARGET_SCHEMA_VERSION, "schema version does not match target")

                _assert(_table_exists(conn, "players"), "players table was not created")
                _assert(_table_exists(conn, "card_instances"), "card_instances table was not created")
                _assert(_table_exists(conn, "wishlist_cards"), "wishlist_cards table was not created")
                _assert(_column_exists(conn, "players", "married_instance_id"), "players.married_instance_id missing")
                _assert(_column_exists(conn, "players", "last_dropped_instance_id"), "players.last_dropped_instance_id missing")
        finally:
            storage.DB_PATH = original_db_path


def _run_legacy_backfill_validation() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "legacy.db"

        with closing(sqlite3.connect(db_path)) as conn:
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
                    (1, 10, 0, 0, None),
                )
                conn.execute(
                    "INSERT INTO player_cards (guild_id, user_id, card_id, quantity) VALUES (?, ?, ?, ?)",
                    (1, 10, "SPG", 2),
                )
                conn.execute(
                    "INSERT INTO player_cards (guild_id, user_id, card_id, quantity) VALUES (?, ?, ?, ?)",
                    (1, 10, "PEN", 1),
                )

        original_db_path = storage.DB_PATH
        try:
            storage.DB_PATH = db_path
            storage.init_db()

            with closing(sqlite3.connect(db_path)) as conn:
                _assert(_table_exists(conn, "schema_migrations"), "schema_migrations table missing after migration")
                version_row = conn.execute("SELECT version FROM schema_migrations LIMIT 1").fetchone()
                _assert(version_row is not None, "schema_migrations has no version row after migration")
                _assert(int(version_row[0]) == storage.TARGET_SCHEMA_VERSION, "schema version was not upgraded")

                _assert(_column_exists(conn, "players", "married_instance_id"), "players.married_instance_id missing after migration")
                _assert(_column_exists(conn, "players", "last_dropped_instance_id"), "players.last_dropped_instance_id missing after migration")
                _assert(_table_exists(conn, "wishlist_cards"), "wishlist_cards table missing after migration")

                count_row = conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()
                _assert(count_row is not None, "card_instances count query failed")
                _assert(int(count_row[0]) == 3, "legacy quantity backfill did not create expected card instances")
        finally:
            storage.DB_PATH = original_db_path


def main() -> None:
    _run_fresh_init_validation()
    _run_legacy_backfill_validation()
    print("migration_smoke: PASS")


if __name__ == "__main__":
    main()
