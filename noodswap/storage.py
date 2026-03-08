import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from .cards import card_value, random_generation, split_card_code
from .migrations import TARGET_SCHEMA_VERSION, run_migrations
from .repositories import (
    BattleSessionRepository,
    CardInstanceRepository,
    CardInstanceTagRepository,
    PlayerRepository,
    PlayerTagRepository,
    PlayerTeamRepository,
    TeamMemberRepository,
    WishlistRepository,
)
from .settings import (
    DB_LOCK_TIMEOUT_SECONDS,
    DB_PATH,
    GENERATION_MAX,
    GENERATION_MIN,
    STARTING_DOUGH,
    TEAM_MAX_CARDS,
)


GLOBAL_GUILD_ID = 0


def _scope_guild_id(_guild_id: int) -> int:
    return GLOBAL_GUILD_ID


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
        conn.execute("DELETE FROM card_instance_tags")
        conn.execute("DELETE FROM player_tags")
        conn.execute("DELETE FROM wishlist_cards")
        conn.execute("DELETE FROM card_instances")
        conn.execute("DELETE FROM players")


def _normalize_tag_name(tag_name: str) -> Optional[str]:
    normalized = tag_name.strip().lower()
    if not normalized:
        return None
    if len(normalized) > 32:
        return None
    return normalized


def _normalize_team_name(team_name: str) -> Optional[str]:
    normalized = team_name.strip().lower()
    if not normalized:
        return None
    if len(normalized) > 32:
        return None
    return normalized


def create_player_team(guild_id: int, user_id: int, team_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        players.ensure_player(guild_id, user_id)
        return teams.create(guild_id, user_id, normalized, time.time())


def delete_player_team(guild_id: int, user_id: int, team_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        players.ensure_player(guild_id, user_id)
        deleted = teams.delete(guild_id, user_id, normalized)
        if not deleted:
            return False

        if players.get_active_team_name(guild_id, user_id) == normalized:
            players.set_active_team_name(guild_id, user_id, None)
        return True


def list_player_teams(guild_id: int, user_id: int) -> list[tuple[str, int, bool]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        players.ensure_player(guild_id, user_id)
        active_team_name = players.get_active_team_name(guild_id, user_id)
        return [
            (team_name, count, team_name == active_team_name)
            for team_name, count in teams.list_with_counts(guild_id, user_id)
        ]


def set_active_team(guild_id: int, user_id: int, team_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        players.ensure_player(guild_id, user_id)
        if not teams.exists(guild_id, user_id, normalized):
            return False
        players.set_active_team_name(guild_id, user_id, normalized)
        return True


def get_active_team_name(guild_id: int, user_id: int) -> Optional[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_active_team_name(guild_id, user_id)


def assign_instance_to_team(guild_id: int, user_id: int, instance_id: int, team_name: str) -> tuple[bool, str]:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False, "Invalid team name."

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        teams = PlayerTeamRepository(conn)
        members = TeamMemberRepository(conn)
        players.ensure_player(guild_id, user_id)

        if instances.get_owned_instance_for_marry(guild_id, user_id, instance_id) is None:
            return False, "You do not own that card code."
        if not teams.exists(guild_id, user_id, normalized):
            return False, "Team not found."
        if members.is_assigned(guild_id, user_id, normalized, instance_id):
            return False, "That card is already assigned to this team."
        if members.count_members(guild_id, user_id, normalized) >= TEAM_MAX_CARDS:
            return False, f"Team capacity reached ({TEAM_MAX_CARDS} cards max)."

        if not members.add(guild_id, user_id, normalized, instance_id, time.time()):
            return False, "Could not assign that card to the team."
        return True, ""


def is_instance_assigned_to_team(guild_id: int, user_id: int, instance_id: int, team_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        members = TeamMemberRepository(conn)
        players.ensure_player(guild_id, user_id)
        if not teams.exists(guild_id, user_id, normalized):
            return False
        return members.is_assigned(guild_id, user_id, normalized, instance_id)


def unassign_instance_from_team(guild_id: int, user_id: int, instance_id: int, team_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        members = TeamMemberRepository(conn)
        players.ensure_player(guild_id, user_id)
        return members.remove(guild_id, user_id, normalized, instance_id)


def get_instances_by_team(guild_id: int, user_id: int, team_name: str) -> list[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_team_name(team_name)
    if normalized is None:
        return []

    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = PlayerTeamRepository(conn)
        members = TeamMemberRepository(conn)
        players.ensure_player(guild_id, user_id)
        if not teams.exists(guild_id, user_id, normalized):
            return []
        return members.list_team_instances(guild_id, user_id, normalized)


def get_active_team_instances(guild_id: int, user_id: int) -> list[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        members = TeamMemberRepository(conn)
        players.ensure_player(guild_id, user_id)
        active_team_name = players.get_active_team_name(guild_id, user_id)
        if active_team_name is None:
            return []
        return members.list_team_instances(guild_id, user_id, active_team_name)


def create_battle_proposal(
    guild_id: int,
    challenger_id: int,
    challenged_id: int,
    stake: int,
) -> tuple[bool, str, Optional[int], Optional[str], Optional[str]]:
    guild_id = _scope_guild_id(guild_id)
    if stake < 1:
        return False, "Stake must be at least 1 dough.", None, None, None
    if challenger_id == challenged_id:
        return False, "You cannot battle yourself.", None, None, None

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        teams = TeamMemberRepository(conn)
        battles = BattleSessionRepository(conn)
        players.ensure_player(guild_id, challenger_id)
        players.ensure_player(guild_id, challenged_id)

        challenger_team_name = players.get_active_team_name(guild_id, challenger_id)
        challenged_team_name = players.get_active_team_name(guild_id, challenged_id)
        if challenger_team_name is None:
            return False, "Set an active team first with `ns team active <team_name>`.", None, None, None
        if challenged_team_name is None:
            return False, "Target player does not have an active team.", None, None, None

        if teams.count_members(guild_id, challenger_id, challenger_team_name) < 1:
            return False, "Your active team has no cards.", None, None, None
        if teams.count_members(guild_id, challenged_id, challenged_team_name) < 1:
            return False, "Target player's active team has no cards.", None, None, None

        if players.get_dough(guild_id, challenger_id) < stake:
            return False, "You do not have enough dough for that stake.", None, None, None
        if players.get_dough(guild_id, challenged_id) < stake:
            return False, "Target player does not have enough dough for that stake.", None, None, None

        if battles.has_open_battle_for_user(guild_id, challenger_id):
            return False, "You already have an active or pending battle.", None, None, None
        if battles.has_open_battle_for_user(guild_id, challenged_id):
            return False, "That player already has an active or pending battle.", None, None, None

        battle_id = battles.create_pending(
            guild_id,
            challenger_id,
            challenged_id,
            stake,
            challenger_team_name,
            challenged_team_name,
            time.time(),
        )
        if battle_id is None:
            return False, "Could not create battle proposal.", None, None, None

        return True, "", battle_id, challenger_team_name, challenged_team_name


def get_battle_session(guild_id: int, battle_id: int) -> Optional[dict[str, int | float | str | None]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        battles = BattleSessionRepository(conn)
        return battles.get_by_id(guild_id, battle_id)


def resolve_battle_proposal(
    guild_id: int,
    battle_id: int,
    responder_id: int,
    *,
    accepted: bool,
) -> tuple[str, str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        members = TeamMemberRepository(conn)
        battles = BattleSessionRepository(conn)
        battle = battles.get_by_id(guild_id, battle_id)
        if battle is None:
            return "failed", "Battle proposal not found."

        if battle["status"] != "pending":
            return "failed", "This battle has already been resolved."

        challenged_id = int(battle["challenged_id"])
        challenger_id = int(battle["challenger_id"])
        stake = int(battle["stake"])
        if responder_id != challenged_id:
            return "failed", "Only the challenged player can respond to this battle."

        if not accepted:
            denied = battles.mark_denied(guild_id, battle_id, time.time(), "Battle denied.")
            if not denied:
                return "failed", "Could not deny battle proposal."
            return "denied", "The battle was denied."

        players.ensure_player(guild_id, challenger_id)
        players.ensure_player(guild_id, challenged_id)
        challenger_team_name = players.get_active_team_name(guild_id, challenger_id)
        challenged_team_name = players.get_active_team_name(guild_id, challenged_id)
        if challenger_team_name is None or challenged_team_name is None:
            return "failed", "Both players need an active team to start this battle."
        if members.count_members(guild_id, challenger_id, challenger_team_name) < 1:
            return "failed", "Challenger active team has no cards."
        if members.count_members(guild_id, challenged_id, challenged_team_name) < 1:
            return "failed", "Your active team has no cards."
        if players.get_dough(guild_id, challenger_id) < stake:
            return "failed", "Battle failed: challenger no longer has enough dough for stake."
        if players.get_dough(guild_id, challenged_id) < stake:
            return "failed", "Battle failed: challenged player no longer has enough dough for stake."

        marked = battles.mark_active(guild_id, battle_id, challenger_id, time.time())
        if not marked:
            return "failed", "Could not start the battle."
        return "accepted", "Battle accepted. The battle arena is now active."


def create_player_tag(guild_id: int, user_id: int, tag_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.create(guild_id, user_id, normalized)


def delete_player_tag(guild_id: int, user_id: int, tag_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.delete(guild_id, user_id, normalized)


def list_player_tags(guild_id: int, user_id: int) -> list[tuple[str, bool, int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.list_with_counts(guild_id, user_id)


def set_player_tag_locked(guild_id: int, user_id: int, tag_name: str, locked: bool) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.set_locked(guild_id, user_id, normalized, locked)


def assign_tag_to_instance(guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        tags = PlayerTagRepository(conn)
        instance_tags = CardInstanceTagRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned is None:
            return False
        if not tags.exists(guild_id, user_id, normalized):
            return False

        return instance_tags.add(guild_id, user_id, instance_id, normalized)


def is_tag_assigned_to_instance(guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        tags = PlayerTagRepository(conn)
        instance_tags = CardInstanceTagRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned is None:
            return False
        if not tags.exists(guild_id, user_id, normalized):
            return False

        return instance_tags.exists(guild_id, user_id, instance_id, normalized)


def unassign_tag_from_instance(guild_id: int, user_id: int, instance_id: int, tag_name: str) -> bool:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return False

    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        instance_tags = CardInstanceTagRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned is None:
            return False

        return instance_tags.remove(guild_id, user_id, instance_id, normalized)


def get_locked_tags_for_instance(guild_id: int, user_id: int, instance_id: int) -> list[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.list_locked_for_instance(guild_id, user_id, instance_id)


def get_locked_instance_ids(guild_id: int, user_id: int, instance_ids: list[int] | None = None) -> set[int]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        return tags.list_locked_instance_ids(guild_id, user_id, instance_ids)


def get_instances_by_tag(guild_id: int, user_id: int, tag_name: str) -> list[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    normalized = _normalize_tag_name(tag_name)
    if normalized is None:
        return []

    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        tags = PlayerTagRepository(conn)
        instance_tags = CardInstanceTagRepository(conn)
        players.ensure_player(guild_id, user_id)
        if not tags.exists(guild_id, user_id, normalized):
            return []
        return instance_tags.list_tagged_instances(guild_id, user_id, normalized)


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


def get_player_info(guild_id: int, user_id: int) -> tuple[int, float, Optional[int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_info(guild_id, user_id)


def get_player_starter(guild_id: int, user_id: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_starter(guild_id, user_id)


def get_instance_by_id(guild_id: int, instance_id: int) -> Optional[tuple[int, str, int, str]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_by_id(guild_id, instance_id)


def get_instance_morph(guild_id: int, instance_id: int) -> Optional[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_morph_key(guild_id, instance_id)


def get_instance_frame(guild_id: int, instance_id: int) -> Optional[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_frame_key(guild_id, instance_id)


def get_instance_font(guild_id: int, instance_id: int) -> Optional[str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        instances = CardInstanceRepository(conn)
        return instances.get_font_key(guild_id, instance_id)


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


def apply_morph_to_instance(
    guild_id: int,
    user_id: int,
    instance_id: int,
    morph_key: str,
    cost: int,
) -> tuple[bool, str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned_instance = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned_instance is None:
            return False, "You do not own that card code."

        existing_morph = instances.get_morph_key(guild_id, instance_id)
        if existing_morph == morph_key:
            return False, "That card already has this morph."

        dough = players.get_dough(guild_id, user_id)
        if dough < cost:
            return False, "You do not have enough dough."

        did_update = instances.set_morph_key(guild_id, user_id, instance_id, morph_key)
        if not did_update:
            return False, "Morph failed: card instance was not updated."

        players.add_dough(guild_id, user_id, -cost)
        return True, ""


def apply_frame_to_instance(
    guild_id: int,
    user_id: int,
    instance_id: int,
    frame_key: str,
    cost: int,
) -> tuple[bool, str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned_instance = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned_instance is None:
            return False, "You do not own that card code."

        existing_frame = instances.get_frame_key(guild_id, instance_id)
        if existing_frame == frame_key:
            return False, "That card already has this frame."

        dough = players.get_dough(guild_id, user_id)
        if dough < cost:
            return False, "You do not have enough dough."

        did_update = instances.set_frame_key(guild_id, user_id, instance_id, frame_key)
        if not did_update:
            return False, "Frame failed: card instance was not updated."

        players.add_dough(guild_id, user_id, -cost)
        return True, ""


def apply_font_to_instance(
    guild_id: int,
    user_id: int,
    instance_id: int,
    font_key: str,
    cost: int,
) -> tuple[bool, str]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        players.ensure_player(guild_id, user_id)

        owned_instance = instances.get_owned_instance_for_marry(guild_id, user_id, instance_id)
        if owned_instance is None:
            return False, "You do not own that card code."

        existing_font = instances.get_font_key(guild_id, instance_id)
        if existing_font == font_key:
            return False, "That card already has this font."

        dough = players.get_dough(guild_id, user_id)
        if dough < cost:
            return False, "You do not have enough dough."

        did_update = instances.set_font_key(guild_id, user_id, instance_id, font_key)
        if not did_update:
            return False, "Font failed: card instance was not updated."

        players.add_dough(guild_id, user_id, -cost)
        return True, ""


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


def get_player_cooldown_timestamps(guild_id: int, user_id: int) -> tuple[float, float]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_last_drop_at(guild_id, user_id), players.get_last_pull_at(guild_id, user_id)


def get_player_vote_reward_timestamp(guild_id: int, user_id: int) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_last_vote_reward_at(guild_id, user_id)


def get_player_slots_timestamp(guild_id: int, user_id: int) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_last_slots_at(guild_id, user_id)


def get_player_flip_timestamp(guild_id: int, user_id: int) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        return players.get_last_flip_at(guild_id, user_id)


def claim_vote_reward_if_ready(
    guild_id: int,
    user_id: int,
    now: float,
    cooldown_seconds: float,
    reward_amount: int,
) -> tuple[bool, float, int]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        last_vote_reward_at = players.get_last_vote_reward_at(guild_id, user_id)
        elapsed = now - last_vote_reward_at
        if elapsed < cooldown_seconds:
            return False, cooldown_seconds - elapsed, players.get_starter(guild_id, user_id)

        players.set_last_vote_reward_at(guild_id, user_id, now)
        players.add_starter(guild_id, user_id, reward_amount)
        return True, 0.0, players.get_starter(guild_id, user_id)


def consume_slots_cooldown_if_ready(
    guild_id: int,
    user_id: int,
    now: float,
    cooldown_seconds: float,
) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        last_slots_at = players.get_last_slots_at(guild_id, user_id)
        elapsed = now - last_slots_at
        if elapsed < cooldown_seconds:
            return cooldown_seconds - elapsed

        players.set_last_slots_at(guild_id, user_id, now)
        return 0.0


def consume_flip_cooldown_if_ready(
    guild_id: int,
    user_id: int,
    now: float,
    cooldown_seconds: float,
) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        last_flip_at = players.get_last_flip_at(guild_id, user_id)
        elapsed = now - last_flip_at
        if elapsed < cooldown_seconds:
            return cooldown_seconds - elapsed

        players.set_last_flip_at(guild_id, user_id, now)
        return 0.0


def execute_flip_wager(
    guild_id: int,
    user_id: int,
    *,
    stake: int,
    now: float,
    cooldown_seconds: float,
    did_win: bool,
) -> tuple[str, float, int]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        current_dough = players.get_dough(guild_id, user_id)
        if stake <= 0:
            return "invalid_stake", 0.0, current_dough

        last_flip_at = players.get_last_flip_at(guild_id, user_id)
        elapsed = now - last_flip_at
        if elapsed < cooldown_seconds:
            return "cooldown", cooldown_seconds - elapsed, current_dough

        if current_dough < stake:
            return "insufficient_dough", 0.0, current_dough

        dough_delta = stake if did_win else -stake
        players.add_dough(guild_id, user_id, dough_delta)
        players.set_last_flip_at(guild_id, user_id, now)
        return ("won" if did_win else "lost"), 0.0, current_dough + dough_delta


def add_starter(guild_id: int, user_id: int, amount: int) -> int:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)
        players.add_starter(guild_id, user_id, amount)
        return players.get_starter(guild_id, user_id)


def consume_pull_cooldown_if_ready(
    guild_id: int,
    user_id: int,
    now: float,
    cooldown_seconds: float,
) -> float:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        _begin_immediate(conn)
        players = PlayerRepository(conn, STARTING_DOUGH)
        players.ensure_player(guild_id, user_id)

        last_pull_at = players.get_last_pull_at(guild_id, user_id)
        elapsed = now - last_pull_at
        if elapsed < cooldown_seconds:
            return cooldown_seconds - elapsed

        players.set_last_pull_at(guild_id, user_id, now)
        return 0.0


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


def get_player_leaderboard_info(guild_id: int) -> list[tuple[int, int, int, int, int, int]]:
    guild_id = _scope_guild_id(guild_id)
    with get_db_connection() as conn:
        players = PlayerRepository(conn, STARTING_DOUGH)
        instances = CardInstanceRepository(conn)
        wishlist = WishlistRepository(conn)

        balances = players.list_balances(guild_id)
        wish_counts = wishlist.get_wish_counts_by_user(guild_id)
        all_instances = instances.list_owner_cards_for_guild(guild_id)

    cards_count_by_user: dict[int, int] = {}
    total_value_by_user: dict[int, int] = {}
    for owner_id, card_id, generation in all_instances:
        cards_count_by_user[owner_id] = cards_count_by_user.get(owner_id, 0) + 1
        total_value_by_user[owner_id] = total_value_by_user.get(owner_id, 0) + card_value(card_id, generation)

    users: dict[int, tuple[int, int]] = {
        user_id: (dough, starter)
        for user_id, dough, starter in balances
    }
    all_user_ids = set(users.keys()) | set(wish_counts.keys()) | set(cards_count_by_user.keys())

    rows: list[tuple[int, int, int, int, int, int]] = []
    for user_id in sorted(all_user_ids):
        dough, starter = users.get(user_id, (STARTING_DOUGH, 0))
        rows.append(
            (
                user_id,
                cards_count_by_user.get(user_id, 0),
                wish_counts.get(user_id, 0),
                dough,
                starter,
                total_value_by_user.get(user_id, 0),
            )
        )

    return rows


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
        tags = PlayerTagRepository(conn)
        players.ensure_player(guild_id, user_id)

        if tags.list_locked_for_instance(guild_id, user_id, instance_id):
            return None

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
    _ = card_id
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
