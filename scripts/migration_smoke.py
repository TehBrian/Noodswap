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
                _assert(_column_exists(conn, "card_instances", "morph_key"), "card_instances.morph_key missing")
                _assert(_column_exists(conn, "card_instances", "frame_key"), "card_instances.frame_key missing")
                _assert(_column_exists(conn, "card_instances", "font_key"), "card_instances.font_key missing")
        finally:
            storage.DB_PATH = original_db_path


def main() -> None:
    _run_fresh_init_validation()
    print("migration_smoke: PASS")


if __name__ == "__main__":
    main()
