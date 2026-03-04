import sqlite3
from typing import Optional


_BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


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


class PlayerRepository:
    def __init__(self, conn: sqlite3.Connection, starting_dough: int):
        self.conn = conn
        self.starting_dough = starting_dough

    def ensure_player(self, guild_id: int, user_id: int) -> None:
        self.conn.execute(
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
            (guild_id, user_id, self.starting_dough),
        )

    def get_stats(self, guild_id: int, user_id: int) -> tuple[int, float, Optional[int]]:
        row = self.conn.execute(
            """
            SELECT dough, last_pull_at, married_instance_id
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return self.starting_dough, 0.0, None
        married_instance_id = row["married_instance_id"]
        return int(row["dough"]), float(row["last_pull_at"]), int(married_instance_id) if married_instance_id is not None else None

    def set_last_drop_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_pull_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )

    def set_last_pulled_instance(self, guild_id: int, user_id: int, instance_id: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_dropped_instance_id = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (instance_id, guild_id, user_id),
        )

    def clear_last_pulled_if_matches(self, guild_id: int, user_id: int, instance_id: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_dropped_instance_id = NULL
            WHERE guild_id = ? AND user_id = ? AND last_dropped_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )

    def clear_marriage_if_matches(self, guild_id: int, user_id: int, instance_id: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL,
                married_card_id = NULL
            WHERE guild_id = ? AND user_id = ? AND married_instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        )

    def get_last_pulled_instance(self, guild_id: int, user_id: int) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
            """
            SELECT p.last_dropped_instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM players p
            LEFT JOIN card_instances ci
                ON ci.instance_id = p.last_dropped_instance_id
                AND ci.guild_id = p.guild_id
                AND ci.user_id = p.user_id
            WHERE p.guild_id = ? AND p.user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return None

        last_dropped_instance_id = row["last_dropped_instance_id"]
        card_id = row["card_id"]
        generation = row["generation"]
        dupe_code = row["dupe_code"]

        if last_dropped_instance_id is None:
            return None

        if card_id is None or generation is None or dupe_code is None:
            self.conn.execute(
                """
                UPDATE players
                SET last_dropped_instance_id = NULL
                WHERE guild_id = ? AND user_id = ? AND last_dropped_instance_id = ?
                """,
                (guild_id, user_id, int(last_dropped_instance_id)),
            )
            return None

        return int(last_dropped_instance_id), str(card_id), int(generation), str(dupe_code)

    def add_dough(self, guild_id: int, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET dough = dough + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )

    def get_married_instance_id(self, guild_id: int, user_id: int) -> Optional[int]:
        row = self.conn.execute(
            """
            SELECT married_instance_id
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None or row["married_instance_id"] is None:
            return None
        return int(row["married_instance_id"])

    def find_other_owner_of_married_card(self, guild_id: int, card_id: str, excluding_user_id: int) -> Optional[int]:
        row = self.conn.execute(
            """
            SELECT p.user_id
            FROM players p
            JOIN card_instances ci ON ci.instance_id = p.married_instance_id
            WHERE p.guild_id = ? AND ci.card_id = ? AND p.user_id != ?
            LIMIT 1
            """,
            (guild_id, card_id, excluding_user_id),
        ).fetchone()
        if row is None:
            return None
        return int(row["user_id"])

    def set_marriage(self, guild_id: int, user_id: int, instance_id: int, card_id: str) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET married_instance_id = ?, married_card_id = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (instance_id, card_id, guild_id, user_id),
        )

    def clear_marriage(self, guild_id: int, user_id: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET married_instance_id = NULL, married_card_id = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )

    def get_divorce_instance(self, guild_id: int, user_id: int) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
            """
            SELECT p.married_instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM players p
            LEFT JOIN card_instances ci ON ci.instance_id = p.married_instance_id
            WHERE p.guild_id = ? AND p.user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None or row["married_instance_id"] is None or row["card_id"] is None or row["dupe_code"] is None:
            return None
        return int(row["married_instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])

    def get_dough(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT dough
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["dough"]) if row is not None else self.starting_dough


class WishlistRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_cards(self, guild_id: int, user_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT card_id
            FROM wishlist_cards
            WHERE guild_id = ? AND user_id = ?
            ORDER BY card_id ASC
            """,
            (guild_id, user_id),
        ).fetchall()
        return [str(row["card_id"]) for row in rows]

    def add(self, guild_id: int, user_id: int, card_id: str) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO wishlist_cards (guild_id, user_id, card_id)
            VALUES (?, ?, ?)
            """,
            (guild_id, user_id, card_id),
        )
        return int(cursor.rowcount) > 0

    def remove(self, guild_id: int, user_id: int, card_id: str) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM wishlist_cards
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            """,
            (guild_id, user_id, card_id),
        )
        return int(cursor.rowcount) > 0

    def get_card_wish_counts(self, guild_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT card_id, COUNT(*) AS wish_count
            FROM wishlist_cards
            WHERE guild_id = ?
            GROUP BY card_id
            """,
            (guild_id,),
        ).fetchall()
        return {str(row["card_id"]): int(row["wish_count"]) for row in rows}


class CardInstanceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _next_available_dupe_code(self) -> str:
        rows = self.conn.execute(
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

    def get_by_id(self, guild_id: int, instance_id: int) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
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

    def get_by_code(self, guild_id: int, user_id: int, dupe_code: str) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
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

    def count_by_card(self, guild_id: int, user_id: int, card_id: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND card_id = ?
            """,
            (guild_id, user_id, card_id),
        ).fetchone()
        return int(row["c"]) if row else 0

    def create_owned_instance(self, guild_id: int, user_id: int, card_id: str, generation: int) -> int:
        dupe_code = self._next_available_dupe_code()
        cursor = self.conn.execute(
            """
            INSERT INTO card_instances (guild_id, user_id, card_id, generation, dupe_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, card_id, generation, dupe_code),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to persist card instance")
        return int(cursor.lastrowid)

    def get_burn_candidate_by_card_id(self, guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
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

    def list_by_owner(self, guild_id: int, user_id: int) -> list[tuple[int, str, int, str]]:
        rows = self.conn.execute(
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

    def count_by_owner(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total_cards
            FROM card_instances
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["total_cards"]) if row else 0

    def pop_highest_generation_by_card(self, guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, int]]:
        row = self.conn.execute(
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
        self.conn.execute(
            """
            DELETE FROM card_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        )
        return instance_id, generation

    def burn_owned_instance(self, guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, int, str]]:
        row = self.conn.execute(
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

        self.conn.execute(
            """
            DELETE FROM card_instances
            WHERE instance_id = ?
            """,
            (instance_id,),
        )

        return card_id, generation, dupe_code

    def select_instance_for_marry(self, guild_id: int, user_id: int, card_id: str) -> Optional[tuple[int, int]]:
        row = self.conn.execute(
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

    def get_owned_instance_for_marry(self, guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, int, str]]:
        selected_row = self.conn.execute(
            """
            SELECT card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND instance_id = ?
            """,
            (guild_id, user_id, instance_id),
        ).fetchone()
        if selected_row is None:
            return None
        return str(selected_row["card_id"]), int(selected_row["generation"]), str(selected_row["dupe_code"])

    def get_seller_trade_instance(self, guild_id: int, seller_id: int, dupe_code: str) -> Optional[tuple[int, int, str]]:
        row = self.conn.execute(
            """
            SELECT instance_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND dupe_code = ?
            LIMIT 1
            """,
            (guild_id, seller_id, dupe_code),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), int(row["generation"]), str(row["dupe_code"])

    def transfer_to_user(self, instance_id: int, buyer_id: int) -> None:
        self.conn.execute(
            """
            UPDATE card_instances
            SET user_id = ?
            WHERE instance_id = ?
            """,
            (buyer_id, instance_id),
        )
