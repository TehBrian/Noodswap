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
                starter,
                drop_tickets,
                last_drop_at,
                last_pull_at,
                last_slots_at,
                last_flip_at,
                married_card_id,
                married_instance_id,
                last_dropped_instance_id
            )
            VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, NULL, NULL, NULL)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id, self.starting_dough, 0, 0),
        )

    def get_info(self, guild_id: int, user_id: int) -> tuple[int, float, Optional[int]]:
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

    def get_active_team_name(self, guild_id: int, user_id: int) -> Optional[str]:
        row = self.conn.execute(
            """
            SELECT active_team_name
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None or row["active_team_name"] is None:
            return None
        return str(row["active_team_name"])

    def set_active_team_name(self, guild_id: int, user_id: int, team_name: Optional[str]) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET active_team_name = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (team_name, guild_id, user_id),
        )

    def set_last_drop_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_drop_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )

    def get_last_drop_at(self, guild_id: int, user_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT last_drop_at
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return float(row["last_drop_at"]) if row is not None else 0.0

    def get_last_pull_at(self, guild_id: int, user_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT last_pull_at
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return float(row["last_pull_at"]) if row is not None else 0.0

    def set_last_pull_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
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

    def get_starter(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT starter
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["starter"]) if row is not None else 0

    def add_starter(self, guild_id: int, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET starter = starter + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )

    def get_drop_tickets(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT drop_tickets
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["drop_tickets"]) if row is not None else 0

    def add_drop_tickets(self, guild_id: int, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET drop_tickets = drop_tickets + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )

    def list_balances(self, guild_id: int) -> list[tuple[int, int, int, int]]:
        rows = self.conn.execute(
            """
            SELECT user_id, dough, starter, votes
            FROM players
            WHERE guild_id = ?
            ORDER BY user_id ASC
            """,
            (guild_id,),
        ).fetchall()
        return [
            (
                int(row["user_id"]),
                int(row["dough"]),
                int(row["starter"]),
                int(row["votes"]),
            )
            for row in rows
        ]

    def get_votes(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT votes
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["votes"]) if row is not None else 0

    def add_votes(self, guild_id: int, user_id: int, amount: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET votes = votes + ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, guild_id, user_id),
        )

    def get_last_slots_at(self, guild_id: int, user_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT last_slots_at
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return float(row["last_slots_at"]) if row is not None else 0.0

    def set_last_slots_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_slots_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )

    def get_last_flip_at(self, guild_id: int, user_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT last_flip_at
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return float(row["last_flip_at"]) if row is not None else 0.0

    def set_last_flip_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_flip_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )

    def get_monopoly_position(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT monopoly_position
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["monopoly_position"]) if row is not None else 0

    def set_monopoly_position(self, guild_id: int, user_id: int, position: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET monopoly_position = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (position, guild_id, user_id),
        )

    def get_last_monopoly_roll_at(self, guild_id: int, user_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT last_monopoly_roll_at
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return float(row["last_monopoly_roll_at"]) if row is not None else 0.0

    def set_last_monopoly_roll_at(self, guild_id: int, user_id: int, timestamp: float) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET last_monopoly_roll_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (timestamp, guild_id, user_id),
        )

    def get_monopoly_in_jail(self, guild_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            """
            SELECT monopoly_in_jail
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return bool(int(row["monopoly_in_jail"])) if row is not None else False

    def set_monopoly_in_jail(self, guild_id: int, user_id: int, in_jail: bool) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET monopoly_in_jail = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (1 if in_jail else 0, guild_id, user_id),
        )

    def get_monopoly_jail_roll_attempts(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT monopoly_jail_roll_attempts
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["monopoly_jail_roll_attempts"]) if row is not None else 0

    def set_monopoly_jail_roll_attempts(self, guild_id: int, user_id: int, attempts: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET monopoly_jail_roll_attempts = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (attempts, guild_id, user_id),
        )

    def get_monopoly_consecutive_doubles(self, guild_id: int, user_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT monopoly_consecutive_doubles
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        return int(row["monopoly_consecutive_doubles"]) if row is not None else 0

    def set_monopoly_consecutive_doubles(self, guild_id: int, user_id: int, count: int) -> None:
        self.conn.execute(
            """
            UPDATE players
            SET monopoly_consecutive_doubles = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (count, guild_id, user_id),
        )

    def get_monopoly_state(self, guild_id: int, user_id: int) -> tuple[int, float, bool, int, int]:
        row = self.conn.execute(
            """
            SELECT monopoly_position, last_monopoly_roll_at, monopoly_in_jail,
                   monopoly_jail_roll_attempts, monopoly_consecutive_doubles
            FROM players
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        if row is None:
            return 0, 0.0, False, 0, 0
        return (
            int(row["monopoly_position"]),
            float(row["last_monopoly_roll_at"]),
            bool(int(row["monopoly_in_jail"])),
            int(row["monopoly_jail_roll_attempts"]),
            int(row["monopoly_consecutive_doubles"]),
        )


class GamblingPotRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_row(self, guild_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO gambling_pot (guild_id, dough, starter, drop_tickets)
            VALUES (?, 0, 0, 0)
            ON CONFLICT(guild_id) DO NOTHING
            """,
            (guild_id,),
        )

    def get_balances(self, guild_id: int) -> tuple[int, int, int]:
        row = self.conn.execute(
            """
            SELECT dough, starter, drop_tickets
            FROM gambling_pot
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()
        if row is None:
            return 0, 0, 0
        return int(row["dough"]), int(row["starter"]), int(row["drop_tickets"])

    def add(self, guild_id: int, *, dough: int = 0, starter: int = 0, drop_tickets: int = 0) -> None:
        self.ensure_row(guild_id)
        self.conn.execute(
            """
            UPDATE gambling_pot
            SET dough = dough + ?,
                starter = starter + ?,
                drop_tickets = drop_tickets + ?
            WHERE guild_id = ?
            """,
            (dough, starter, drop_tickets, guild_id),
        )

    def clear(self, guild_id: int) -> None:
        self.ensure_row(guild_id)
        self.conn.execute(
            """
            UPDATE gambling_pot
            SET dough = 0,
                starter = 0,
                drop_tickets = 0
            WHERE guild_id = ?
            """,
            (guild_id,),
        )


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

    def get_wish_counts_by_user(self, guild_id: int) -> dict[int, int]:
        rows = self.conn.execute(
            """
            SELECT user_id, COUNT(*) AS wish_count
            FROM wishlist_cards
            WHERE guild_id = ?
            GROUP BY user_id
            """,
            (guild_id,),
        ).fetchall()
        return {int(row["user_id"]): int(row["wish_count"]) for row in rows}


class PlayerTagRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, guild_id: int, user_id: int, tag_name: str) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO player_tags (guild_id, user_id, tag_name, is_locked)
            VALUES (?, ?, ?, 0)
            """,
            (guild_id, user_id, tag_name),
        )
        return int(cursor.rowcount) > 0

    def delete(self, guild_id: int, user_id: int, tag_name: str) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM player_tags
            WHERE guild_id = ? AND user_id = ? AND tag_name = ?
            """,
            (guild_id, user_id, tag_name),
        )
        return int(cursor.rowcount) > 0

    def exists(self, guild_id: int, user_id: int, tag_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM player_tags
            WHERE guild_id = ? AND user_id = ? AND tag_name = ?
            LIMIT 1
            """,
            (guild_id, user_id, tag_name),
        ).fetchone()
        return row is not None

    def set_locked(self, guild_id: int, user_id: int, tag_name: str, locked: bool) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE player_tags
            SET is_locked = ?
            WHERE guild_id = ? AND user_id = ? AND tag_name = ?
            """,
            (1 if locked else 0, guild_id, user_id, tag_name),
        )
        return int(cursor.rowcount) > 0

    def list_with_counts(self, guild_id: int, user_id: int) -> list[tuple[str, bool, int]]:
        rows = self.conn.execute(
            """
            SELECT pt.tag_name, pt.is_locked, COUNT(cit.instance_id) AS card_count
            FROM player_tags pt
            LEFT JOIN card_instance_tags cit
                ON cit.guild_id = pt.guild_id
                AND cit.user_id = pt.user_id
                AND cit.tag_name = pt.tag_name
            WHERE pt.guild_id = ? AND pt.user_id = ?
            GROUP BY pt.tag_name, pt.is_locked
            ORDER BY pt.tag_name ASC
            """,
            (guild_id, user_id),
        ).fetchall()
        return [
            (
                str(row["tag_name"]),
                bool(int(row["is_locked"])),
                int(row["card_count"]),
            )
            for row in rows
        ]

    def list_locked_for_instance(self, guild_id: int, user_id: int, instance_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT pt.tag_name
            FROM card_instance_tags cit
            JOIN player_tags pt
                ON pt.guild_id = cit.guild_id
                AND pt.user_id = cit.user_id
                AND pt.tag_name = cit.tag_name
            WHERE cit.guild_id = ?
                AND cit.user_id = ?
                AND cit.instance_id = ?
                AND pt.is_locked = 1
            ORDER BY pt.tag_name ASC
            """,
            (guild_id, user_id, instance_id),
        ).fetchall()
        return [str(row["tag_name"]) for row in rows]

    def list_locked_instance_ids(
        self,
        guild_id: int,
        user_id: int,
        instance_ids: list[int] | None = None,
    ) -> set[int]:
        base_query = (
            """
            SELECT DISTINCT cit.instance_id
            FROM card_instance_tags cit
            JOIN player_tags pt
                ON pt.guild_id = cit.guild_id
                AND pt.user_id = cit.user_id
                AND pt.tag_name = cit.tag_name
            WHERE cit.guild_id = ?
                AND cit.user_id = ?
                AND pt.is_locked = 1
            """
        )
        params: list[int] = [guild_id, user_id]

        if instance_ids is not None:
            if not instance_ids:
                return set()
            placeholders = ", ".join("?" for _ in instance_ids)
            base_query += f" AND cit.instance_id IN ({placeholders})"
            params.extend(instance_ids)

        rows = self.conn.execute(base_query, params).fetchall()
        return {int(row["instance_id"]) for row in rows}


class CardInstanceTagRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def exists(self, guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM card_instance_tags
            WHERE guild_id = ? AND user_id = ? AND instance_id = ? AND tag_name = ?
            LIMIT 1
            """,
            (guild_id, user_id, instance_id, tag_name),
        ).fetchone()
        return row is not None

    def add(self, guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO card_instance_tags (guild_id, user_id, instance_id, tag_name)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, user_id, instance_id, tag_name),
        )
        return int(cursor.rowcount) > 0

    def remove(self, guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM card_instance_tags
            WHERE guild_id = ? AND user_id = ? AND instance_id = ? AND tag_name = ?
            """,
            (guild_id, user_id, instance_id, tag_name),
        )
        return int(cursor.rowcount) > 0

    def list_tagged_instances(self, guild_id: int, user_id: int, tag_name: str) -> list[tuple[int, str, int, str]]:
        rows = self.conn.execute(
            """
            SELECT ci.instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM card_instance_tags cit
            JOIN card_instances ci
                ON ci.instance_id = cit.instance_id
                AND ci.guild_id = cit.guild_id
                AND ci.user_id = cit.user_id
            WHERE cit.guild_id = ? AND cit.user_id = ? AND cit.tag_name = ?
            ORDER BY ci.generation ASC, ci.card_id ASC, ci.instance_id ASC
            """,
            (guild_id, user_id, tag_name),
        ).fetchall()
        return [
            (int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"]))
            for row in rows
        ]


class PlayerFolderRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, guild_id: int, user_id: int, folder_name: str, emoji: str) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO player_folders (guild_id, user_id, folder_name, emoji, is_locked)
            VALUES (?, ?, ?, ?, 0)
            """,
            (guild_id, user_id, folder_name, emoji),
        )
        return int(cursor.rowcount) > 0

    def delete(self, guild_id: int, user_id: int, folder_name: str) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM player_folders
            WHERE guild_id = ? AND user_id = ? AND folder_name = ?
            """,
            (guild_id, user_id, folder_name),
        )
        return int(cursor.rowcount) > 0

    def exists(self, guild_id: int, user_id: int, folder_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM player_folders
            WHERE guild_id = ? AND user_id = ? AND folder_name = ?
            LIMIT 1
            """,
            (guild_id, user_id, folder_name),
        ).fetchone()
        return row is not None

    def set_locked(self, guild_id: int, user_id: int, folder_name: str, locked: bool) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE player_folders
            SET is_locked = ?
            WHERE guild_id = ? AND user_id = ? AND folder_name = ?
            """,
            (1 if locked else 0, guild_id, user_id, folder_name),
        )
        return int(cursor.rowcount) > 0

    def set_emoji(self, guild_id: int, user_id: int, folder_name: str, emoji: str) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE player_folders
            SET emoji = ?
            WHERE guild_id = ? AND user_id = ? AND folder_name = ?
            """,
            (emoji, guild_id, user_id, folder_name),
        )
        return int(cursor.rowcount) > 0

    def list_with_counts(self, guild_id: int, user_id: int) -> list[tuple[str, str, bool, int]]:
        rows = self.conn.execute(
            """
            SELECT pf.folder_name, pf.emoji, pf.is_locked, COUNT(cif.instance_id) AS card_count
            FROM player_folders pf
            LEFT JOIN card_instance_folders cif
                ON cif.guild_id = pf.guild_id
                AND cif.user_id = pf.user_id
                AND cif.folder_name = pf.folder_name
            WHERE pf.guild_id = ? AND pf.user_id = ?
            GROUP BY pf.folder_name, pf.emoji, pf.is_locked
            ORDER BY pf.folder_name ASC
            """,
            (guild_id, user_id),
        ).fetchall()
        return [
            (
                str(row["folder_name"]),
                str(row["emoji"]),
                bool(int(row["is_locked"])),
                int(row["card_count"]),
            )
            for row in rows
        ]

    def get_locked_for_instance(self, guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, str]]:
        row = self.conn.execute(
            """
            SELECT pf.folder_name, pf.emoji
            FROM card_instance_folders cif
            JOIN player_folders pf
                ON pf.guild_id = cif.guild_id
                AND pf.user_id = cif.user_id
                AND pf.folder_name = cif.folder_name
            WHERE cif.guild_id = ?
                AND cif.user_id = ?
                AND cif.instance_id = ?
                AND pf.is_locked = 1
            LIMIT 1
            """,
            (guild_id, user_id, instance_id),
        ).fetchone()
        if row is None:
            return None
        return str(row["folder_name"]), str(row["emoji"])

    def list_locked_instance_ids(
        self,
        guild_id: int,
        user_id: int,
        instance_ids: list[int] | None = None,
    ) -> set[int]:
        base_query = (
            """
            SELECT DISTINCT cif.instance_id
            FROM card_instance_folders cif
            JOIN player_folders pf
                ON pf.guild_id = cif.guild_id
                AND pf.user_id = cif.user_id
                AND pf.folder_name = cif.folder_name
            WHERE cif.guild_id = ?
                AND cif.user_id = ?
                AND pf.is_locked = 1
            """
        )
        params: list[int] = [guild_id, user_id]

        if instance_ids is not None:
            if not instance_ids:
                return set()
            placeholders = ", ".join("?" for _ in instance_ids)
            base_query += f" AND cif.instance_id IN ({placeholders})"
            params.extend(instance_ids)

        rows = self.conn.execute(base_query, params).fetchall()
        return {int(row["instance_id"]) for row in rows}


class CardInstanceFolderRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def set_folder(self, guild_id: int, user_id: int, instance_id: int, folder_name: str) -> bool:
        cursor = self.conn.execute(
            """
            INSERT INTO card_instance_folders (guild_id, user_id, instance_id, folder_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, instance_id)
            DO UPDATE SET folder_name = excluded.folder_name
            """,
            (guild_id, user_id, instance_id, folder_name),
        )
        return int(cursor.rowcount) > 0

    def clear_folder(self, guild_id: int, user_id: int, instance_id: int, folder_name: str | None = None) -> bool:
        if folder_name is None:
            cursor = self.conn.execute(
                """
                DELETE FROM card_instance_folders
                WHERE guild_id = ? AND user_id = ? AND instance_id = ?
                """,
                (guild_id, user_id, instance_id),
            )
            return int(cursor.rowcount) > 0

        cursor = self.conn.execute(
            """
            DELETE FROM card_instance_folders
            WHERE guild_id = ? AND user_id = ? AND instance_id = ? AND folder_name = ?
            """,
            (guild_id, user_id, instance_id, folder_name),
        )
        return int(cursor.rowcount) > 0

    def get_for_instance(self, guild_id: int, user_id: int, instance_id: int) -> Optional[tuple[str, str]]:
        row = self.conn.execute(
            """
            SELECT cif.folder_name, pf.emoji
            FROM card_instance_folders cif
            JOIN player_folders pf
                ON pf.guild_id = cif.guild_id
                AND pf.user_id = cif.user_id
                AND pf.folder_name = cif.folder_name
            WHERE cif.guild_id = ? AND cif.user_id = ? AND cif.instance_id = ?
            LIMIT 1
            """,
            (guild_id, user_id, instance_id),
        ).fetchone()
        if row is None:
            return None
        return str(row["folder_name"]), str(row["emoji"])

    def is_assigned(self, guild_id: int, user_id: int, instance_id: int, folder_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM card_instance_folders
            WHERE guild_id = ? AND user_id = ? AND instance_id = ? AND folder_name = ?
            LIMIT 1
            """,
            (guild_id, user_id, instance_id, folder_name),
        ).fetchone()
        return row is not None

    def list_foldered_instances(self, guild_id: int, user_id: int, folder_name: str) -> list[tuple[int, str, int, str]]:
        rows = self.conn.execute(
            """
            SELECT ci.instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM card_instance_folders cif
            JOIN card_instances ci
                ON ci.instance_id = cif.instance_id
                AND ci.guild_id = cif.guild_id
                AND ci.user_id = cif.user_id
            WHERE cif.guild_id = ? AND cif.user_id = ? AND cif.folder_name = ?
            ORDER BY ci.generation ASC, ci.card_id ASC, ci.instance_id ASC
            """,
            (guild_id, user_id, folder_name),
        ).fetchall()
        return [
            (int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"]))
            for row in rows
        ]

    def list_for_instances(self, guild_id: int, user_id: int, instance_ids: list[int]) -> dict[int, str]:
        if not instance_ids:
            return {}

        placeholders = ", ".join("?" for _ in instance_ids)
        query = (
            """
            SELECT cif.instance_id, pf.emoji
            FROM card_instance_folders cif
            JOIN player_folders pf
                ON pf.guild_id = cif.guild_id
                AND pf.user_id = cif.user_id
                AND pf.folder_name = cif.folder_name
            WHERE cif.guild_id = ?
                AND cif.user_id = ?
                AND cif.instance_id IN (
            """
            + placeholders
            + ")"
        )
        rows = self.conn.execute(query, [guild_id, user_id, *instance_ids]).fetchall()
        return {int(row["instance_id"]): str(row["emoji"]) for row in rows}


class PlayerTeamRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, guild_id: int, user_id: int, team_name: str, created_at: float) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO player_teams (guild_id, user_id, team_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, user_id, team_name, created_at),
        )
        return int(cursor.rowcount) > 0

    def exists(self, guild_id: int, user_id: int, team_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM player_teams
            WHERE guild_id = ? AND user_id = ? AND team_name = ?
            LIMIT 1
            """,
            (guild_id, user_id, team_name),
        ).fetchone()
        return row is not None

    def delete(self, guild_id: int, user_id: int, team_name: str) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM player_teams
            WHERE guild_id = ? AND user_id = ? AND team_name = ?
            """,
            (guild_id, user_id, team_name),
        )
        return int(cursor.rowcount) > 0

    def list_with_counts(self, guild_id: int, user_id: int) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            """
            SELECT pt.team_name, COUNT(tm.instance_id) AS card_count
            FROM player_teams pt
            LEFT JOIN team_members tm
                ON tm.guild_id = pt.guild_id
                AND tm.user_id = pt.user_id
                AND tm.team_name = pt.team_name
            WHERE pt.guild_id = ? AND pt.user_id = ?
            GROUP BY pt.team_name
            ORDER BY pt.team_name ASC
            """,
            (guild_id, user_id),
        ).fetchall()
        return [(str(row["team_name"]), int(row["card_count"])) for row in rows]


class TeamMemberRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def count_members(self, guild_id: int, user_id: int, team_name: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM team_members
            WHERE guild_id = ? AND user_id = ? AND team_name = ?
            """,
            (guild_id, user_id, team_name),
        ).fetchone()
        return int(row["c"]) if row is not None else 0

    def is_assigned(self, guild_id: int, user_id: int, team_name: str, instance_id: int) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM team_members
            WHERE guild_id = ? AND user_id = ? AND team_name = ? AND instance_id = ?
            LIMIT 1
            """,
            (guild_id, user_id, team_name, instance_id),
        ).fetchone()
        return row is not None

    def add(self, guild_id: int, user_id: int, team_name: str, instance_id: int, created_at: float) -> bool:
        cursor = self.conn.execute(
            """
            INSERT OR IGNORE INTO team_members (guild_id, user_id, team_name, instance_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, team_name, instance_id, created_at),
        )
        return int(cursor.rowcount) > 0

    def remove(self, guild_id: int, user_id: int, team_name: str, instance_id: int) -> bool:
        cursor = self.conn.execute(
            """
            DELETE FROM team_members
            WHERE guild_id = ? AND user_id = ? AND team_name = ? AND instance_id = ?
            """,
            (guild_id, user_id, team_name, instance_id),
        )
        return int(cursor.rowcount) > 0

    def list_team_instances(self, guild_id: int, user_id: int, team_name: str) -> list[tuple[int, str, int, str]]:
        rows = self.conn.execute(
            """
            SELECT ci.instance_id, ci.card_id, ci.generation, ci.dupe_code
            FROM team_members tm
            JOIN card_instances ci
                ON ci.instance_id = tm.instance_id
            WHERE tm.guild_id = ? AND tm.user_id = ? AND tm.team_name = ?
                AND ci.guild_id = tm.guild_id
                AND ci.user_id = tm.user_id
            ORDER BY ci.generation ASC, ci.card_id ASC, ci.instance_id ASC
            """,
            (guild_id, user_id, team_name),
        ).fetchall()
        return [
            (int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"]))
            for row in rows
        ]


class BattleSessionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_pending(
        self,
        guild_id: int,
        challenger_id: int,
        challenged_id: int,
        stake: int,
        challenger_team_name: str,
        challenged_team_name: str,
        created_at: float,
    ) -> Optional[int]:
        cursor = self.conn.execute(
            """
            INSERT INTO battle_sessions (
                guild_id,
                challenger_id,
                challenged_id,
                stake,
                status,
                challenger_team_name,
                challenged_team_name,
                created_at,
                acting_user_id,
                turn_number
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, NULL, 1)
            """,
            (guild_id, challenger_id, challenged_id, stake, challenger_team_name, challenged_team_name, created_at),
        )
        if cursor.lastrowid is None:
            return None
        return int(cursor.lastrowid)

    def get_by_id(self, guild_id: int, battle_id: int) -> Optional[dict[str, int | float | str | None]]:
        row = self.conn.execute(
            """
            SELECT battle_id, guild_id, challenger_id, challenged_id, stake, status,
                   challenger_team_name, challenged_team_name, created_at, accepted_at,
                   finished_at, acting_user_id, turn_number, winner_user_id, last_action
            FROM battle_sessions
            WHERE guild_id = ? AND battle_id = ?
            LIMIT 1
            """,
            (guild_id, battle_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "battle_id": int(row["battle_id"]),
            "guild_id": int(row["guild_id"]),
            "challenger_id": int(row["challenger_id"]),
            "challenged_id": int(row["challenged_id"]),
            "stake": int(row["stake"]),
            "status": str(row["status"]),
            "challenger_team_name": str(row["challenger_team_name"]),
            "challenged_team_name": str(row["challenged_team_name"]),
            "created_at": float(row["created_at"]),
            "accepted_at": float(row["accepted_at"]) if row["accepted_at"] is not None else None,
            "finished_at": float(row["finished_at"]) if row["finished_at"] is not None else None,
            "acting_user_id": int(row["acting_user_id"]) if row["acting_user_id"] is not None else None,
            "turn_number": int(row["turn_number"]),
            "winner_user_id": int(row["winner_user_id"]) if row["winner_user_id"] is not None else None,
            "last_action": str(row["last_action"]) if row["last_action"] is not None else None,
        }

    def has_open_battle_for_user(self, guild_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM battle_sessions
            WHERE guild_id = ?
                AND status IN ('pending', 'active')
                AND (challenger_id = ? OR challenged_id = ?)
            LIMIT 1
            """,
            (guild_id, user_id, user_id),
        ).fetchone()
        return row is not None

    def mark_denied(self, guild_id: int, battle_id: int, finished_at: float, last_action: str) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE battle_sessions
            SET status = 'denied',
                finished_at = ?,
                last_action = ?
            WHERE guild_id = ? AND battle_id = ? AND status = 'pending'
            """,
            (finished_at, last_action, guild_id, battle_id),
        )
        return int(cursor.rowcount) > 0

    def mark_active(self, guild_id: int, battle_id: int, acting_user_id: int, accepted_at: float) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE battle_sessions
            SET status = 'active',
                accepted_at = ?,
                acting_user_id = ?,
                turn_number = 1,
                last_action = 'Battle started.'
            WHERE guild_id = ? AND battle_id = ? AND status = 'pending'
            """,
            (accepted_at, acting_user_id, guild_id, battle_id),
        )
        return int(cursor.rowcount) > 0

    def update_turn_state(
        self,
        guild_id: int,
        battle_id: int,
        *,
        acting_user_id: int,
        turn_number: int,
        last_action: str,
    ) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE battle_sessions
            SET acting_user_id = ?,
                turn_number = ?,
                last_action = ?
            WHERE guild_id = ? AND battle_id = ? AND status = 'active'
            """,
            (acting_user_id, turn_number, last_action, guild_id, battle_id),
        )
        return int(cursor.rowcount) > 0

    def mark_finished(
        self,
        guild_id: int,
        battle_id: int,
        *,
        winner_user_id: int,
        finished_at: float,
        last_action: str,
    ) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE battle_sessions
            SET status = 'finished',
                winner_user_id = ?,
                finished_at = ?,
                acting_user_id = NULL,
                last_action = ?
            WHERE guild_id = ? AND battle_id = ? AND status = 'active'
            """,
            (winner_user_id, finished_at, last_action, guild_id, battle_id),
        )
        return int(cursor.rowcount) > 0

    def mark_all_open_finished(self, guild_id: int, finished_at: float, last_action: str) -> int:
        cursor = self.conn.execute(
            """
            UPDATE battle_sessions
            SET status = 'finished',
                finished_at = ?,
                acting_user_id = NULL,
                last_action = ?
            WHERE guild_id = ?
                AND status IN ('pending', 'active')
            """,
            (finished_at, last_action, guild_id),
        )
        return int(cursor.rowcount)


class BattleCombatantRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def replace_for_battle(self, battle_id: int, rows: list[tuple[int, int, str, int, int, str, int, str, int, int, bool, bool, bool]]) -> None:
        self.conn.execute(
            """
            DELETE FROM battle_combatants
            WHERE battle_id = ?
            """,
            (battle_id,),
        )
        self.conn.executemany(
            """
            INSERT INTO battle_combatants (
                battle_id,
                guild_id,
                user_id,
                side,
                slot_index,
                instance_id,
                card_id,
                generation,
                dupe_code,
                max_hp,
                current_hp,
                is_active,
                is_defending,
                is_knocked_out
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    battle_id,
                    guild_id,
                    user_id,
                    side,
                    slot_index,
                    instance_id,
                    card_id,
                    generation,
                    dupe_code,
                    max_hp,
                    current_hp,
                    1 if is_active else 0,
                    1 if is_defending else 0,
                    1 if is_knocked_out else 0,
                )
                for (
                    guild_id,
                    user_id,
                    side,
                    slot_index,
                    instance_id,
                    card_id,
                    generation,
                    dupe_code,
                    max_hp,
                    current_hp,
                    is_active,
                    is_defending,
                    is_knocked_out,
                ) in rows
            ],
        )

    def list_for_battle(self, battle_id: int) -> list[dict[str, int | str | bool]]:
        rows = self.conn.execute(
            """
            SELECT battle_id, guild_id, user_id, side, slot_index, instance_id, card_id,
                   generation, dupe_code, max_hp, current_hp, is_active, is_defending, is_knocked_out
            FROM battle_combatants
            WHERE battle_id = ?
            ORDER BY side ASC, slot_index ASC
            """,
            (battle_id,),
        ).fetchall()
        return [
            {
                "battle_id": int(row["battle_id"]),
                "guild_id": int(row["guild_id"]),
                "user_id": int(row["user_id"]),
                "side": str(row["side"]),
                "slot_index": int(row["slot_index"]),
                "instance_id": int(row["instance_id"]),
                "card_id": str(row["card_id"]),
                "generation": int(row["generation"]),
                "dupe_code": str(row["dupe_code"]),
                "max_hp": int(row["max_hp"]),
                "current_hp": int(row["current_hp"]),
                "is_active": bool(int(row["is_active"])),
                "is_defending": bool(int(row["is_defending"])),
                "is_knocked_out": bool(int(row["is_knocked_out"])),
            }
            for row in rows
        ]

    def clear_defending_for_side(self, battle_id: int, side: str) -> None:
        self.conn.execute(
            """
            UPDATE battle_combatants
            SET is_defending = 0
            WHERE battle_id = ? AND side = ?
            """,
            (battle_id, side),
        )

    def set_defending_for_active(self, battle_id: int, side: str, defending: bool) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE battle_combatants
            SET is_defending = ?
            WHERE battle_id = ? AND side = ? AND is_active = 1
            """,
            (1 if defending else 0, battle_id, side),
        )
        return int(cursor.rowcount) > 0

    def set_active_slot(self, battle_id: int, side: str, slot_index: int) -> bool:
        self.conn.execute(
            """
            UPDATE battle_combatants
            SET is_active = 0
            WHERE battle_id = ? AND side = ?
            """,
            (battle_id, side),
        )
        cursor = self.conn.execute(
            """
            UPDATE battle_combatants
            SET is_active = 1,
                is_defending = 0
            WHERE battle_id = ?
                AND side = ?
                AND slot_index = ?
                AND is_knocked_out = 0
                AND current_hp > 0
            """,
            (battle_id, side, slot_index),
        )
        return int(cursor.rowcount) > 0

    def apply_damage_to_active(self, battle_id: int, side: str, damage: int) -> Optional[dict[str, int | str | bool]]:
        row = self.conn.execute(
            """
            SELECT side, slot_index, current_hp
            FROM battle_combatants
            WHERE battle_id = ? AND side = ? AND is_active = 1
            LIMIT 1
            """,
            (battle_id, side),
        ).fetchone()
        if row is None:
            return None

        slot_index = int(row["slot_index"])
        current_hp = int(row["current_hp"])
        next_hp = max(0, current_hp - damage)
        is_knocked_out = next_hp <= 0

        self.conn.execute(
            """
            UPDATE battle_combatants
            SET current_hp = ?,
                is_knocked_out = ?,
                is_active = CASE WHEN ? = 1 THEN 0 ELSE is_active END,
                is_defending = 0
            WHERE battle_id = ? AND side = ? AND slot_index = ?
            """,
            (next_hp, 1 if is_knocked_out else 0, 1 if is_knocked_out else 0, battle_id, side, slot_index),
        )

        return {
            "side": side,
            "slot_index": slot_index,
            "current_hp": next_hp,
            "is_knocked_out": is_knocked_out,
        }


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

    def get_by_dupe_code(self, guild_id: int, dupe_code: str) -> Optional[tuple[int, int, str, int, str]]:
        row = self.conn.execute(
            """
            SELECT instance_id, user_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND dupe_code = ?
            LIMIT 1
            """,
            (guild_id, dupe_code),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), int(row["user_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])

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

    def list_owner_cards_for_guild(self, guild_id: int) -> list[tuple[int, str, int]]:
        rows = self.conn.execute(
            """
            SELECT user_id, card_id, generation
            FROM card_instances
            WHERE guild_id = ?
            ORDER BY user_id ASC, instance_id ASC
            """,
            (guild_id,),
        ).fetchall()
        return [
            (
                int(row["user_id"]),
                str(row["card_id"]),
                int(row["generation"]),
            )
            for row in rows
        ]

    def list_owner_instances_for_guild(self, guild_id: int) -> list[tuple[int, int, str, int, str]]:
        rows = self.conn.execute(
            """
            SELECT instance_id, user_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ?
            ORDER BY user_id ASC, instance_id ASC
            """,
            (guild_id,),
        ).fetchall()
        return [
            (
                int(row["instance_id"]),
                int(row["user_id"]),
                str(row["card_id"]),
                int(row["generation"]),
                str(row["dupe_code"]),
            )
            for row in rows
        ]

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

    def get_seller_trade_instance(self, guild_id: int, seller_id: int, dupe_code: str) -> Optional[tuple[int, str, int, str]]:
        row = self.conn.execute(
            """
            SELECT instance_id, card_id, generation, dupe_code
            FROM card_instances
            WHERE guild_id = ? AND user_id = ? AND dupe_code = ?
            LIMIT 1
            """,
            (guild_id, seller_id, dupe_code),
        ).fetchone()
        if row is None:
            return None
        return int(row["instance_id"]), str(row["card_id"]), int(row["generation"]), str(row["dupe_code"])

    def transfer_to_user(self, instance_id: int, buyer_id: int) -> None:
        self.conn.execute(
            """
            UPDATE card_instances
            SET user_id = ?
            WHERE instance_id = ?
            """,
            (buyer_id, instance_id),
        )

    def get_morph_key(self, guild_id: int, instance_id: int) -> Optional[str]:
        try:
            row = self.conn.execute(
                """
                SELECT morph_key
                FROM card_instances
                WHERE guild_id = ? AND instance_id = ?
                """,
                (guild_id, instance_id),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        morph_key = row["morph_key"]
        return str(morph_key) if morph_key is not None else None

    def set_morph_key(self, guild_id: int, user_id: int, instance_id: int, morph_key: Optional[str]) -> bool:
        try:
            cursor = self.conn.execute(
                """
                UPDATE card_instances
                SET morph_key = ?
                WHERE guild_id = ? AND user_id = ? AND instance_id = ?
                """,
                (morph_key, guild_id, user_id, instance_id),
            )
        except sqlite3.OperationalError:
            return False
        return int(cursor.rowcount) > 0

    def get_frame_key(self, guild_id: int, instance_id: int) -> Optional[str]:
        try:
            row = self.conn.execute(
                """
                SELECT frame_key
                FROM card_instances
                WHERE guild_id = ? AND instance_id = ?
                """,
                (guild_id, instance_id),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        frame_key = row["frame_key"]
        return str(frame_key) if frame_key is not None else None

    def set_frame_key(self, guild_id: int, user_id: int, instance_id: int, frame_key: Optional[str]) -> bool:
        try:
            cursor = self.conn.execute(
                """
                UPDATE card_instances
                SET frame_key = ?
                WHERE guild_id = ? AND user_id = ? AND instance_id = ?
                """,
                (frame_key, guild_id, user_id, instance_id),
            )
        except sqlite3.OperationalError:
            return False
        return int(cursor.rowcount) > 0

    def get_font_key(self, guild_id: int, instance_id: int) -> Optional[str]:
        try:
            row = self.conn.execute(
                """
                SELECT font_key
                FROM card_instances
                WHERE guild_id = ? AND instance_id = ?
                """,
                (guild_id, instance_id),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        font_key = row["font_key"]
        return str(font_key) if font_key is not None else None

    def set_font_key(self, guild_id: int, user_id: int, instance_id: int, font_key: Optional[str]) -> bool:
        try:
            cursor = self.conn.execute(
                """
                UPDATE card_instances
                SET font_key = ?
                WHERE guild_id = ? AND user_id = ? AND instance_id = ?
                """,
                (font_key, guild_id, user_id, instance_id),
            )
        except sqlite3.OperationalError:
            return False
        return int(cursor.rowcount) > 0

    def get_owner_by_id(self, guild_id: int, instance_id: int) -> Optional[int]:
        row = self.conn.execute(
            """
            SELECT user_id
            FROM card_instances
            WHERE guild_id = ? AND instance_id = ?
            """,
            (guild_id, instance_id),
        ).fetchone()
        if row is None:
            return None
        return int(row["user_id"])
