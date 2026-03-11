# pylint: disable=unused-import,wrong-import-order

import asyncio
import io
import os
import random
import time
from typing import Awaitable, Callable, cast

from . import compat as _compat  # noqa: F401 - applies asyncio patch before discord import

import aiohttp
import discord
from discord.ext import commands

from .battle_engine import value_to_stats
from .cards import (
    CARD_CATALOG,
    card_base_value,
    card_base_display,
    card_dupe_display,
    card_dupe_display_concise,
    card_value,
    generation_value_multiplier,
    normalize_card_id,
    search_card_ids,
    search_card_ids_by_name,
    trait_value_multiplier,
)
from .images import (
    DEFAULT_CARD_RENDER_SIZE,
    DROP_CARD_BODY_SCALE,
    HD_CARD_RENDER_SIZE,
    embed_image_payload,
    morph_transition_image_payload,
    read_local_card_image_bytes,
    render_card_surface,
)
from .fonts import font_label, font_rarity
from .frames import frame_label, frame_rarity
from .morphs import morph_label, morph_rarity
from .trait_rarities import trait_rarity_multiplier
from .presentation import (
    battle_offer_description,
    drop_choices_description,
    gift_offer_description,
    italy_embed,
    italy_marry_embed,
    trade_offer_description,
)
from .services import (
    execute_divorce,
    execute_marry,
    prepare_burn,
    prepare_burn_batch,
    prepare_drop,
    prepare_font,
    prepare_frame,
    prepare_morph,
    prepare_battle_offer,
    prepare_gift_offer,
    prepare_trade_offer,
)
from .settings import (
    DB_PATH,
    DROP_COOLDOWN_SECONDS,
    DROP_TIMEOUT_SECONDS,
    FLIP_COOLDOWN_SECONDS,
    FLIP_WIN_PROBABILITY,
    MONOPOLY_JAIL_FINE_DOUGH,
    MONOPOLY_ROLL_COOLDOWN_SECONDS,
    PULL_COOLDOWN_SECONDS,
    SLOTS_COOLDOWN_SECONDS,
    VOTE_STARTER_REWARD,
)
from .storage import (
    add_starter,
    buy_drop_tickets_with_starter,
    assign_instance_to_folder,
    assign_instance_to_team,
    assign_tag_to_instance,
    claim_vote_reward,
    consume_slots_cooldown_if_ready,
    execute_flip_wager,
    execute_monopoly_fine,
    execute_monopoly_roll,
    create_player_folder,
    create_player_tag,
    create_player_team,
    delete_player_folder,
    delete_player_team,
    delete_player_tag,
    get_folder_emojis_for_instances,
    execute_gift_dough,
    get_instance_by_code,
    get_instance_by_id,
    get_instance_by_dupe_code,
    get_instance_font,
    get_instance_frame,
    get_instance_morph,
    get_burn_candidate_by_card_id,
    get_instances_by_folder,
    get_instances_by_tag,
    get_instances_by_team,
    get_locked_instance_ids,
    is_instance_assigned_to_folder,
    is_tag_assigned_to_instance,
    get_player_cooldown_timestamps,
    get_player_card_instances,
    get_player_flip_timestamp,
    get_player_leaderboard_info,
    get_player_slots_timestamp,
    list_player_folders,
    list_player_tags,
    list_player_teams,
    get_player_starter,
    get_player_info,
    get_player_drop_tickets,
    get_gambling_pot,
    get_monopoly_board_state,
    get_monopoly_state,
    get_total_cards,
    set_player_folder_emoji,
    set_player_folder_locked,
    set_player_tag_locked,
    set_active_team,
    get_active_team_name,
    is_instance_assigned_to_team,
    unassign_instance_from_folder,
    unassign_instance_from_team,
    unassign_tag_from_instance,
    add_card_to_wishlist,
    get_card_wish_counts,
    get_wishlist_cards,
    remove_card_from_wishlist,
    reset_db_data,
)
from .utils import format_cooldown, multiline_text
from .views import (
    BurnConfirmView,
    CardCatalogView,
    DropView,
    FontConfirmView,
    HelpView,
    FrameConfirmView,
    MorphConfirmView,
    PlayerLeaderboardView,
    SortableCardListView,
    SortableCollectionView,
    BattleProposalView,
    GiftCardView,
    TradeView,
)


def _title_case_rarity(rarity: str) -> str:
    return rarity.strip().replace("_", " ").title()


def _lookup_trait_breakdown_description(
    card_id: str,
    generation: int,
    dupe_code: str | None,
    *,
    owner_mention: str | None,
    morph_key: str | None,
    frame_key: str | None,
    font_key: str | None,
) -> str:
    morph_rarity_label = morph_rarity(morph_key)
    frame_rarity_label = frame_rarity(frame_key)
    font_rarity_label = font_rarity(font_key)

    morph_multiplier = trait_rarity_multiplier(morph_rarity_label)
    frame_multiplier = trait_rarity_multiplier(frame_rarity_label)
    font_multiplier = trait_rarity_multiplier(font_rarity_label)

    trait_multiplier = trait_value_multiplier(
        morph_key=morph_key,
        frame_key=frame_key,
        font_key=font_key,
    )
    base_value = card_base_value(card_id)
    generation_multiplier = generation_value_multiplier(generation)
    total_multiplier = generation_multiplier * trait_multiplier
    computed_value = card_value(
        card_id,
        generation,
        morph_key=morph_key,
        frame_key=frame_key,
        font_key=font_key,
    )

    lines = [
        card_dupe_display(
            card_id,
            generation,
            dupe_code=dupe_code,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        ),
    ]
    if owner_mention is not None:
        lines.append(f"Owner: {owner_mention}")

    lines.extend(
        [
            "",
            "**Traits**",
            (
                f"Morph: **{morph_label(morph_key)}** "
                f"({_title_case_rarity(morph_rarity_label)}) • **x{morph_multiplier:.2f}**"
            ),
            (
                f"Frame: **{frame_label(frame_key)}** "
                f"({_title_case_rarity(frame_rarity_label)}) • **x{frame_multiplier:.2f}**"
            ),
            (
                f"Font: **{font_label(font_key)}** "
                f"({_title_case_rarity(font_rarity_label)}) • **x{font_multiplier:.2f}**"
            ),
            "",
            "**Value Breakdown**",
            f"Base Value: **{base_value}**",
            f"Generation Multiplier: **x{generation_multiplier:.2f}**",
            f"Trait Multiplier: **x{trait_multiplier:.2f}**",
            f"Total Multiplier: **x{total_multiplier:.2f}**",
            f"Computed Value: **{computed_value}** dough",
        ]
    )
    return multiline_text(lines)


async def resolve_member_argument(ctx: commands.Context, raw_member: str) -> tuple[discord.Member | None, str | None]:
    if ctx.guild is None:
        return None, "Use this command in a server."

    candidate = raw_member.strip()
    if not candidate:
        return None, "Provide a player (mention or username)."

    converter = commands.MemberConverter()
    try:
        return await converter.convert(ctx, candidate), None
    except (commands.BadArgument, AttributeError):
        pass

    if candidate.startswith("@"):
        candidate = candidate[1:].strip()

    if not candidate:
        return None, "Could not find that player. Mention them like `@Friend` or use their exact username."

    matches = [
        member
        for member in ctx.guild.members
        if member.name.casefold() == candidate.casefold()
        or member.display_name.casefold() == candidate.casefold()
    ]

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "Multiple users match that name. Mention the user directly to disambiguate."

    return None, "Could not find that player. Mention them like `@Friend` or use their exact username."


async def resolve_optional_player_argument(
    ctx: commands.Context,
    player: str | None,
) -> tuple[discord.abc.User | None, str | None]:
    if player is not None:
        return await resolve_member_argument(ctx, player)

    if ctx.guild is None:
        return None, "Use this command in a server."

    message = getattr(ctx, "message", None)
    reference = getattr(message, "reference", None)
    if reference is None:
        return ctx.author, None

    replied_author_id: int | None = None
    resolved_reference = getattr(reference, "resolved", None)
    if isinstance(resolved_reference, discord.Message):
        replied_author_id = resolved_reference.author.id
    else:
        resolved_author = getattr(resolved_reference, "author", None)
        resolved_author_id = getattr(resolved_author, "id", None)
        if isinstance(resolved_author_id, int):
            replied_author_id = resolved_author_id

    if replied_author_id is None:
        reference_message_id = getattr(reference, "message_id", None)
        if not isinstance(reference_message_id, int):
            return ctx.author, None

        channel = getattr(ctx, "channel", None)
        fetch_message = getattr(channel, "fetch_message", None)
        if callable(fetch_message):
            try:
                fetch_message_coro = cast(Callable[[int], Awaitable[discord.Message]], fetch_message)
                referenced_message = await fetch_message_coro(reference_message_id)
                fetched_author_id = getattr(referenced_message.author, "id", None)
                if isinstance(fetched_author_id, int):
                    replied_author_id = fetched_author_id
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                replied_author_id = None

    if replied_author_id is None:
        return ctx.author, None

    target_member = ctx.guild.get_member(replied_author_id)
    if target_member is not None:
        return target_member, None

    fetch_member = getattr(ctx.guild, "fetch_member", None)
    if callable(fetch_member):
        try:
            fetch_member_coro = cast(Callable[[int], Awaitable[discord.Member]], fetch_member)
            return await fetch_member_coro(replied_author_id), None
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return ctx.author, None

    return ctx.author, None


def _get_card_image_bytes(card_id: str) -> bytes | None:
    return read_local_card_image_bytes(card_id)


def _build_drop_preview_blocking(choices: list[tuple[str, int]]) -> bytes | None:
    try:
        from PIL import Image
    except ImportError:
        return None

    card_w, card_h = DEFAULT_CARD_RENDER_SIZE
    card_surfaces: list[Image.Image] = []
    for card_id, generation in choices:
        surface = render_card_surface(
            card_id,
            generation=generation,
            body_scale=DROP_CARD_BODY_SCALE,
            size=(card_w, card_h),
        )
        if surface is None:
            return None
        card_surfaces.append(surface)

    gap = 16
    pad = 16
    canvas_w = (card_w * len(choices)) + (gap * (len(choices) - 1)) + (pad * 2)
    canvas_h = card_h + (pad * 2)

    # Keep drop preview background transparent so Discord surfaces the channel theme behind cards.
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    for idx in range(len(choices)):
        image = card_surfaces[idx]
        x = pad + idx * (card_w + gap)
        y = pad
        canvas.paste(image, (x, y), image)

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


async def build_drop_preview_file(choices: list[tuple[str, int]]) -> discord.File | None:
    image_bytes = await asyncio.to_thread(_build_drop_preview_blocking, choices)
    if image_bytes is None:
        return None
    return discord.File(io.BytesIO(image_bytes), filename="drop_choices.png")


def _cooldown_status_line(label: str, elapsed_seconds: float, cooldown_seconds: float) -> str:
    remaining = max(0.0, cooldown_seconds - elapsed_seconds)
    if remaining > 0:
        return f"{label}: **Cooling Down** (ready in **{format_cooldown(remaining)}**)"
    return f"{label}: **Ready** (can use now)"


def _vote_link_view(vote_url: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Vote on top.gg", style=discord.ButtonStyle.link, url=vote_url))
    return view


SLOTS_REEL_EMOJIS: tuple[str, ...] = ("🍞", "🍷", "🧀", "🍕", "🍇", "🥖", "🍝")
SLOTS_REEL_COUNT = 3
SLOTS_SPIN_MIN_STEPS = 4
SLOTS_SPIN_MAX_STEPS = 7
SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS = 0.7
SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS = 1.5
SLOTS_MIN_REWARD = 1
SLOTS_MAX_REWARD = 3
FLIP_REVEAL_DELAY_SECONDS = 3.0
FLIP_ACTIVITY_PHRASES: tuple[str, ...] = (
    "spinning",
    "flipping",
    "rolling",
    "tumbling",
    "whirling",
    "somersaulting",
)


def _slots_reel_line(symbols: list[str]) -> str:
    return "".join(symbols)


def _slots_reel_content(symbols: list[str], result_emoji: str | None = None) -> str:
    line = _slots_reel_line(symbols)
    status_emoji = result_emoji if result_emoji is not None else ""
    return f"{line}{status_emoji}"


def _normalize_flip_side(side_raw: str | None) -> str | None:
    if side_raw is None:
        return None
    normalized = side_raw.strip().casefold()
    if normalized in {"heads", "h"}:
        return "heads"
    if normalized in {"tails", "t"}:
        return "tails"
    return None


def _parse_burn_selector_tokens(raw_targets: tuple[str, ...]) -> tuple[list[tuple[str, str]], str | None]:
    if not raw_targets:
        return [], None

    selectors: list[tuple[str, str]] = []
    index = 0
    while index < len(raw_targets):
        token = raw_targets[index].strip()
        if not token:
            index += 1
            continue

        lowered = token.casefold()
        if ":" in token:
            prefix, value = token.split(":", 1)
            selector_prefix = prefix.strip().casefold()
            selector_value = value.strip()
            selector_type = {
                "c": "card",
                "card": "card",
                "t": "tag",
                "f": "folder",
            }.get(selector_prefix)
            if selector_type is not None:
                if not selector_value:
                    return [], f"Missing value for `{selector_prefix}:` selector."
                selectors.append((selector_type, selector_value))
                index += 1
                continue
            if selector_prefix in {"tag", "folder"}:
                return [], "Use `t:<tag_name>` and `f:<folder_name>` for burn selectors."

        if lowered == "card":
            if index + 1 >= len(raw_targets):
                return [], f"Missing value after `{token}`."
            selector_value = raw_targets[index + 1].strip()
            if not selector_value:
                return [], f"Missing value after `{token}`."
            selectors.append((lowered, selector_value))
            index += 2
            continue

        if lowered in {"tag", "folder"}:
            if index + 1 >= len(raw_targets):
                return [], f"Missing value after `{token}`."
            selector_value = raw_targets[index + 1].strip()
            if not selector_value:
                return [], f"Missing value after `{token}`."
            selectors.append((lowered, selector_value))
            index += 2
            continue

        selectors.append(("card", token))
        index += 1

    return selectors, None


def _resolve_burn_selector_instances(
    guild_id: int,
    user_id: int,
    *,
    selector_type: str,
    selector_value: str,
) -> tuple[list[tuple[int, str, int, str]], str | None]:
    if selector_type == "card":
        normalized_card_id = normalize_card_id(selector_value)
        if normalized_card_id in CARD_CATALOG:
            selected = get_burn_candidate_by_card_id(guild_id, user_id, normalized_card_id)
            if selected is None:
                return [], f"You do not own any copies of `{normalized_card_id}`."
            return [selected], None

        selected = get_instance_by_code(guild_id, user_id, selector_value)
        if selected is None:
            return [], f"You do not own the card code `{selector_value}`."
        return [selected], None

    if selector_type == "tag":
        selected = get_instances_by_tag(guild_id, user_id, selector_value)
        if not selected:
            return [], f"Tag `{selector_value}` has no cards to burn."
        return selected, None

    if selector_type == "folder":
        selected = get_instances_by_folder(guild_id, user_id, selector_value)
        if not selected:
            return [], f"Folder `{selector_value}` has no cards to burn."
        return selected, None

    return [], f"Unknown burn selector `{selector_type}`."


def _opposite_flip_side(side: str) -> str:
    return "tails" if side == "heads" else "heads"


def _revealed_flip_side(did_win: bool, selected_side: str | None) -> str:
    if selected_side is None:
        return "heads" if did_win else "tails"
    if did_win:
        return selected_side
    return _opposite_flip_side(selected_side)


def _slots_embed(status_lines: list[str]) -> discord.Embed:
    return italy_embed(
        "Slots",
        multiline_text([
            *status_lines,
        ]),
    )


async def _animate_slots_spin(message: discord.Message, final_symbols: list[str]) -> None:
    spin_steps = random.randint(SLOTS_SPIN_MIN_STEPS, SLOTS_SPIN_MAX_STEPS)
    for step in range(spin_steps):
        frame_symbols: list[str] = []
        for reel_index in range(SLOTS_REEL_COUNT):
            lock_step = spin_steps - (SLOTS_REEL_COUNT - reel_index)
            if step >= lock_step:
                frame_symbols.append(final_symbols[reel_index])
            else:
                frame_symbols.append(random.choice(SLOTS_REEL_EMOJIS))

        await message.edit(content=_slots_reel_content(frame_symbols))
        if spin_steps <= 1:
            delay_seconds = SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS
        else:
            progress = step / (spin_steps - 1)
            delay_seconds = (
                SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS
                + (SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS - SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS) * progress
            )
        await asyncio.sleep(delay_seconds)


async def _reply(ctx: commands.Context, **kwargs):
    """Reply to the invoking command message without pinging the author."""
    return await ctx.reply(mention_author=False, **kwargs)


def _guild_id(ctx: commands.Context) -> int:
    assert ctx.guild is not None
    return ctx.guild.id


async def _require_guild(
    ctx: commands.Context,
    title: str,
    *,
    marry_style: bool = False,
) -> bool:
    if ctx.guild is not None:
        return True
    embed_factory = italy_marry_embed if marry_style else italy_embed
    await _reply(ctx, embed=embed_factory(title, "Use this command in a server."))
    return False


def _topgg_auth_header(api_token: str) -> str:
    token = api_token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


async def _topgg_recent_vote_status(user_id: int, api_token: str) -> tuple[bool | None, str | None]:
    # top.gg v1 endpoint for checking a single user's vote status on the authenticated project.
    check_url = f"https://top.gg/api/v1/projects/@me/votes/{user_id}?source=discord"
    headers = {"Authorization": _topgg_auth_header(api_token)}
    timeout = aiohttp.ClientTimeout(total=8)
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(check_url, headers=headers) as response:
                    if response.status == 404:
                        return False, None

                    if response.status == 429 and attempt < max_attempts - 1:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue

                    if 500 <= response.status < 600 and attempt < max_attempts - 1:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue

                    if response.status != 200:
                        return None, f"top.gg API responded with status {response.status}."

                    payload = await response.json(content_type=None)
                    break
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            if isinstance(exc, asyncio.TimeoutError):
                return None, "top.gg request timed out."
            return None, f"top.gg request failed: {exc}"
        except ValueError:
            return None, "top.gg response was not valid JSON."
    else:
        return None, "top.gg request failed after retries."

    created_at = payload.get("created_at")
    expires_at = payload.get("expires_at")
    if created_at is None and expires_at is None:
        return None, "top.gg response did not include vote status fields."
    return True, None


async def _wish_add(ctx: commands.Context, card_id: str) -> None:
    if not await _require_guild(ctx, "Wishlist"):
        return

    normalized_card_id = normalize_card_id(card_id)
    matched_card_ids = [normalized_card_id] if normalized_card_id in CARD_CATALOG else search_card_ids_by_name(card_id)
    if not matched_card_ids:
        await _reply(ctx, embed=italy_embed("Wishlist", "Unknown card id."))
        return

    if len(matched_card_ids) > 1:
        match_lines = [
            f"{index}. {card_base_display(matched_card_id)}"
            for index, matched_card_id in enumerate(matched_card_ids, start=1)
        ]
        await _reply(ctx, embed=italy_embed("Wishlist Matches", multiline_text(match_lines)))
        return

    resolved_card_id = matched_card_ids[0]

    was_added = add_card_to_wishlist(_guild_id(ctx), ctx.author.id, resolved_card_id)
    if not was_added:
        await _reply(ctx, embed=italy_embed("Wishlist", f"Already wishlisted: {card_base_display(resolved_card_id)}"))
        return

    await _reply(ctx, embed=italy_embed("Wishlist", f"Added to wishlist: {card_base_display(resolved_card_id)}"))


async def _wish_remove(ctx: commands.Context, card_id: str) -> None:
    if not await _require_guild(ctx, "Wishlist"):
        return

    normalized_card_id = normalize_card_id(card_id)
    matched_card_ids = [normalized_card_id] if normalized_card_id in CARD_CATALOG else search_card_ids_by_name(card_id)
    if not matched_card_ids:
        await _reply(ctx, embed=italy_embed("Wishlist", "Unknown card id."))
        return

    if len(matched_card_ids) > 1:
        match_lines = [
            f"{index}. {card_base_display(matched_card_id)}"
            for index, matched_card_id in enumerate(matched_card_ids, start=1)
        ]
        await _reply(ctx, embed=italy_embed("Wishlist Matches", multiline_text(match_lines)))
        return

    resolved_card_id = matched_card_ids[0]

    was_removed = remove_card_from_wishlist(_guild_id(ctx), ctx.author.id, resolved_card_id)
    if not was_removed:
        await _reply(ctx, embed=italy_embed("Wishlist", f"Not on wishlist: {card_base_display(resolved_card_id)}"))
        return

    await _reply(ctx, embed=italy_embed("Wishlist", f"Removed from wishlist: {card_base_display(resolved_card_id)}"))


async def _wish_list(ctx: commands.Context, target_member: discord.abc.User | None = None) -> None:
    if not await _require_guild(ctx, "Wishlist"):
        return

    if target_member is None:
        target_member = ctx.author

    wishlisted_card_ids = get_wishlist_cards(_guild_id(ctx), target_member.id)
    title = f"{target_member.display_name}'s Wishlist"
    if not wishlisted_card_ids:
        if target_member.id == ctx.author.id:
            description = "Your wishlist is empty. Add cards with `ns wish add <card_id>`."
        else:
            description = f"{target_member.display_name} has an empty wishlist."
        await _reply(ctx, embed=italy_embed(title, description))
        return

    view = SortableCardListView(
        user_id=ctx.author.id,
        title=title,
        card_ids=wishlisted_card_ids,
        wish_counts=get_card_wish_counts(_guild_id(ctx)),
        guard_title="Wishlist",
    )
    message = await _reply(ctx, embed=view.build_embed(), view=view)
    view.message = message


def _folder_emoji_map_for_instances(
    guild_id: int,
    user_id: int,
    instances: list[tuple[int, str, int, str]],
) -> dict[int, str]:
    return get_folder_emojis_for_instances(
        guild_id,
        user_id,
        [instance_id for instance_id, _card_id, _generation, _dupe_code in instances],
    )


async def _tag_add(ctx: commands.Context, tag_name: str) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    created = create_player_tag(_guild_id(ctx), ctx.author.id, tag_name)
    normalized = tag_name.strip().lower()
    if not created:
        await _reply(ctx,
            embed=italy_embed(
                "Tags",
                "Could not create that tag. Tags must be unique, non-empty, and up to 32 characters.",
            )
        )
        return

    await _reply(ctx, embed=italy_embed("Tags", f"Created tag: `{normalized}`"))


async def _tag_remove(ctx: commands.Context, tag_name: str) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    removed = delete_player_tag(_guild_id(ctx), ctx.author.id, tag_name)
    normalized = tag_name.strip().lower()
    if not removed:
        await _reply(ctx, embed=italy_embed("Tags", f"Tag not found: `{normalized}`"))
        return

    await _reply(ctx, embed=italy_embed("Tags", f"Deleted tag: `{normalized}`"))


async def _tag_list(ctx: commands.Context) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    tags = list_player_tags(_guild_id(ctx), ctx.author.id)
    if not tags:
        await _reply(ctx, embed=italy_embed("Your Tags", "No tags yet. Create one with `ns tag add <tag_name>`."))
        return

    lines = [
        f"{'🔒 ' if is_locked else '`  ` '}" f"`{tag_name}` - {'Locked' if is_locked else 'Unlocked'} - {card_count} card(s)"
        for tag_name, is_locked, card_count in tags
    ]
    await _reply(ctx, embed=italy_embed("Your Tags", multiline_text(lines)))


async def _tag_lock(ctx: commands.Context, tag_name: str, locked: bool) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    updated = set_player_tag_locked(_guild_id(ctx), ctx.author.id, tag_name, locked)
    normalized = tag_name.strip().lower()
    if not updated:
        await _reply(ctx, embed=italy_embed("Tags", f"Tag not found: `{normalized}`"))
        return

    state = "locked" if locked else "unlocked"
    await _reply(ctx, embed=italy_embed("Tags", f"Tag `{normalized}` is now **{state}**."))


async def _tag_assign(ctx: commands.Context, tag_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Tags", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    if is_tag_assigned_to_instance(_guild_id(ctx), ctx.author.id, instance_id, tag_name):
        await _reply(ctx, embed=italy_embed("Tags", "That card is already assigned to this tag."))
        return

    assigned = assign_tag_to_instance(_guild_id(ctx), ctx.author.id, instance_id, tag_name)
    normalized = tag_name.strip().lower()
    if not assigned:
        await _reply(ctx,
            embed=italy_embed(
                "Tags",
                "Could not tag that card. Make sure the tag exists and the card is yours.",
            )
        )
        return

    await _reply(ctx,
        embed=italy_embed(
            "Tags",
            f"Tagged {card_dupe_display(card_id, generation, dupe_code=dupe_code)} with `{normalized}`.",
        )
    )


async def _tag_unassign(ctx: commands.Context, tag_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Tags", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    unassigned = unassign_tag_from_instance(_guild_id(ctx), ctx.author.id, instance_id, tag_name)
    normalized = tag_name.strip().lower()
    if not unassigned:
        await _reply(ctx, embed=italy_embed("Tags", f"That card is not tagged with `{normalized}`."))
        return

    await _reply(ctx,
        embed=italy_embed(
            "Tags",
            f"Removed `{normalized}` from {card_dupe_display(card_id, generation, dupe_code=dupe_code)}.",
        )
    )


async def _tag_cards(ctx: commands.Context, tag_name: str) -> None:
    if not await _require_guild(ctx, "Tags"):
        return

    normalized = tag_name.strip().lower()
    tagged_instances = get_instances_by_tag(_guild_id(ctx), ctx.author.id, normalized)
    if not tagged_instances:
        await _reply(ctx, embed=italy_embed("Tags", f"No cards found for tag `{normalized}`."))
        return

    view = SortableCollectionView(
        user_id=ctx.author.id,
        title=f"Tag: `{normalized}`",
        instances=tagged_instances,
        locked_instance_ids=get_locked_instance_ids(
            _guild_id(ctx),
            ctx.author.id,
            [instance_id for instance_id, _card_id, _generation, _dupe_code in tagged_instances],
        ),
        wish_counts=get_card_wish_counts(_guild_id(ctx)),
        folder_emojis_by_instance=_folder_emoji_map_for_instances(_guild_id(ctx), ctx.author.id, tagged_instances),
        instance_styles={
            instance_id: (
                get_instance_morph(_guild_id(ctx), instance_id),
                get_instance_frame(_guild_id(ctx), instance_id),
                get_instance_font(_guild_id(ctx), instance_id),
            )
            for instance_id, _card_id, _generation, _dupe_code in tagged_instances
        },
        guard_title="Tags",
    )
    message = await _reply(ctx, embed=view.build_embed(), view=view)
    view.message = message


async def _folder_add(ctx: commands.Context, folder_name: str, emoji: str | None) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    created = create_player_folder(_guild_id(ctx), ctx.author.id, folder_name, emoji)
    normalized = folder_name.strip().lower()
    if not created:
        await _reply(
            ctx,
            embed=italy_embed(
                "Folders",
                "Could not create that folder. Folder names must be unique, non-empty, and up to 32 characters.",
            ),
        )
        return

    await _reply(ctx, embed=italy_embed("Folders", f"Created folder: `{normalized}`"))


async def _folder_remove(ctx: commands.Context, folder_name: str) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    removed = delete_player_folder(_guild_id(ctx), ctx.author.id, folder_name)
    normalized = folder_name.strip().lower()
    if not removed:
        await _reply(ctx, embed=italy_embed("Folders", f"Folder not found: `{normalized}`"))
        return

    await _reply(ctx, embed=italy_embed("Folders", f"Deleted folder: `{normalized}`"))


async def _folder_list(ctx: commands.Context) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    folders = list_player_folders(_guild_id(ctx), ctx.author.id)
    if not folders:
        await _reply(ctx, embed=italy_embed("Your Folders", "No folders yet. Create one with `ns folder add <folder_name> [emoji]`."))
        return

    lines = [
        (
            f"{'🔒 ' if is_locked else '`  ` '}"
            f"{emoji} `{folder_name}` - {'Locked' if is_locked else 'Unlocked'} - {card_count} card(s)"
        )
        for folder_name, emoji, is_locked, card_count in folders
    ]
    await _reply(ctx, embed=italy_embed("Your Folders", multiline_text(lines)))


async def _folder_lock(ctx: commands.Context, folder_name: str, locked: bool) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    updated = set_player_folder_locked(_guild_id(ctx), ctx.author.id, folder_name, locked)
    normalized = folder_name.strip().lower()
    if not updated:
        await _reply(ctx, embed=italy_embed("Folders", f"Folder not found: `{normalized}`"))
        return

    state = "locked" if locked else "unlocked"
    await _reply(ctx, embed=italy_embed("Folders", f"Folder `{normalized}` is now **{state}**."))


async def _folder_emoji(ctx: commands.Context, folder_name: str, emoji: str) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    updated = set_player_folder_emoji(_guild_id(ctx), ctx.author.id, folder_name, emoji)
    normalized = folder_name.strip().lower()
    if not updated:
        await _reply(ctx, embed=italy_embed("Folders", f"Folder not found: `{normalized}`"))
        return

    await _reply(ctx, embed=italy_embed("Folders", f"Updated emoji for `{normalized}`."))


async def _folder_assign(ctx: commands.Context, folder_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Folders", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    if is_instance_assigned_to_folder(_guild_id(ctx), ctx.author.id, instance_id, folder_name):
        await _reply(ctx, embed=italy_embed("Folders", "That card is already assigned to this folder."))
        return

    assigned = assign_instance_to_folder(_guild_id(ctx), ctx.author.id, instance_id, folder_name)
    normalized = folder_name.strip().lower()
    if not assigned:
        await _reply(
            ctx,
            embed=italy_embed(
                "Folders",
                "Could not assign that card to this folder. Make sure the folder exists and the card is yours.",
            ),
        )
        return

    await _reply(
        ctx,
        embed=italy_embed(
            "Folders",
            f"Assigned {card_dupe_display(card_id, generation, dupe_code=dupe_code)} to `{normalized}`.",
        ),
    )


async def _folder_unassign(ctx: commands.Context, folder_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Folders", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    removed = unassign_instance_from_folder(_guild_id(ctx), ctx.author.id, instance_id, folder_name)
    normalized = folder_name.strip().lower()
    if not removed:
        await _reply(ctx, embed=italy_embed("Folders", f"That card is not assigned to `{normalized}`."))
        return

    await _reply(
        ctx,
        embed=italy_embed(
            "Folders",
            f"Removed {card_dupe_display(card_id, generation, dupe_code=dupe_code)} from `{normalized}`.",
        ),
    )


async def _folder_cards(ctx: commands.Context, folder_name: str) -> None:
    if not await _require_guild(ctx, "Folders"):
        return

    normalized = folder_name.strip().lower()
    folder_instances = get_instances_by_folder(_guild_id(ctx), ctx.author.id, normalized)
    if not folder_instances:
        await _reply(ctx, embed=italy_embed("Folders", f"No cards found for folder `{normalized}`."))
        return

    view = SortableCollectionView(
        user_id=ctx.author.id,
        title=f"Folder: `{normalized}`",
        instances=folder_instances,
        locked_instance_ids=get_locked_instance_ids(
            _guild_id(ctx),
            ctx.author.id,
            [instance_id for instance_id, _card_id, _generation, _dupe_code in folder_instances],
        ),
        wish_counts=get_card_wish_counts(_guild_id(ctx)),
        folder_emojis_by_instance=_folder_emoji_map_for_instances(_guild_id(ctx), ctx.author.id, folder_instances),
        instance_styles={
            instance_id: (
                get_instance_morph(_guild_id(ctx), instance_id),
                get_instance_frame(_guild_id(ctx), instance_id),
                get_instance_font(_guild_id(ctx), instance_id),
            )
            for instance_id, _card_id, _generation, _dupe_code in folder_instances
        },
        guard_title="Folders",
    )
    message = await _reply(ctx, embed=view.build_embed(), view=view)
    view.message = message


async def _team_add(ctx: commands.Context, team_name: str) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    created = create_player_team(_guild_id(ctx), ctx.author.id, team_name)
    normalized = team_name.strip().lower()
    if not created:
        await _reply(
            ctx,
            embed=italy_embed(
                "Teams",
                "Could not create that team. Team names must be unique, non-empty, and up to 32 characters.",
            ),
        )
        return

    await _reply(ctx, embed=italy_embed("Teams", f"Created team: `{normalized}`"))


async def _team_remove(ctx: commands.Context, team_name: str) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    normalized = team_name.strip().lower()
    removed = delete_player_team(_guild_id(ctx), ctx.author.id, team_name)
    if not removed:
        await _reply(ctx, embed=italy_embed("Teams", f"Team not found: `{normalized}`"))
        return

    await _reply(ctx, embed=italy_embed("Teams", f"Deleted team: `{normalized}`"))


async def _team_list(ctx: commands.Context) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    teams = list_player_teams(_guild_id(ctx), ctx.author.id)
    if not teams:
        await _reply(ctx, embed=italy_embed("Your Teams", "No teams yet. Create one with `ns team add <team_name>`."))
        return

    lines = [
        f"{'\u2b50 ' if is_active else '`  ` '} `{team_name}` - {card_count}/3 card(s)"
        for team_name, card_count, is_active in teams
    ]
    await _reply(ctx, embed=italy_embed("Your Teams", multiline_text(lines)))


async def _team_assign(ctx: commands.Context, team_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Teams", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    if is_instance_assigned_to_team(_guild_id(ctx), ctx.author.id, instance_id, team_name):
        await _reply(ctx, embed=italy_embed("Teams", "That card is already on this team."))
        return

    success, message = assign_instance_to_team(_guild_id(ctx), ctx.author.id, instance_id, team_name)
    normalized = team_name.strip().lower()
    if not success:
        await _reply(ctx, embed=italy_embed("Teams", message or "Could not assign that card to this team."))
        return

    await _reply(
        ctx,
        embed=italy_embed(
            "Teams",
            f"Assigned {card_dupe_display(card_id, generation, dupe_code=dupe_code)} to `{normalized}`.",
        ),
    )


async def _team_unassign(ctx: commands.Context, team_name: str, card_code: str) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    selected = get_instance_by_code(_guild_id(ctx), ctx.author.id, card_code)
    if selected is None:
        await _reply(ctx, embed=italy_embed("Teams", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    removed = unassign_instance_from_team(_guild_id(ctx), ctx.author.id, instance_id, team_name)
    normalized = team_name.strip().lower()
    if not removed:
        await _reply(ctx, embed=italy_embed("Teams", f"That card is not assigned to `{normalized}`."))
        return

    await _reply(
        ctx,
        embed=italy_embed(
            "Teams",
            f"Removed {card_dupe_display(card_id, generation, dupe_code=dupe_code)} from `{normalized}`.",
        ),
    )


async def _team_cards(ctx: commands.Context, team_name: str) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    normalized = team_name.strip().lower()
    team_instances = get_instances_by_team(_guild_id(ctx), ctx.author.id, normalized)
    if not team_instances:
        await _reply(ctx, embed=italy_embed("Teams", f"No cards found for team `{normalized}`."))
        return

    view = SortableCollectionView(
        user_id=ctx.author.id,
        title=f"Team: `{normalized}`",
        instances=team_instances,
        locked_instance_ids=get_locked_instance_ids(
            _guild_id(ctx),
            ctx.author.id,
            [instance_id for instance_id, _card_id, _generation, _dupe_code in team_instances],
        ),
        wish_counts=get_card_wish_counts(_guild_id(ctx)),
        folder_emojis_by_instance=_folder_emoji_map_for_instances(_guild_id(ctx), ctx.author.id, team_instances),
        instance_styles={
            instance_id: (
                get_instance_morph(_guild_id(ctx), instance_id),
                get_instance_frame(_guild_id(ctx), instance_id),
                get_instance_font(_guild_id(ctx), instance_id),
            )
            for instance_id, _card_id, _generation, _dupe_code in team_instances
        },
        card_line_formatter=_team_card_line_with_stats,
        guard_title="Teams",
    )
    message = await _reply(ctx, embed=view.build_embed(), view=view)
    view.message = message


def _team_card_line_with_stats(
    card_id: str,
    generation: int,
    dupe_code: str | None,
    *,
    morph_key: str | None = None,
    frame_key: str | None = None,
    font_key: str | None = None,
) -> str:
    hp, attack, defense = value_to_stats(
        card_value(
            card_id,
            generation,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        )
    )
    return (
        f"{card_dupe_display(card_id, generation, dupe_code, morph_key=morph_key, frame_key=frame_key, font_key=font_key)} "
        f"• HP:{hp} ATK:{attack} DEF:{defense}"
    )


async def _team_active(ctx: commands.Context, team_name: str | None) -> None:
    if not await _require_guild(ctx, "Teams"):
        return

    if team_name is None:
        active_team_name = get_active_team_name(_guild_id(ctx), ctx.author.id)
        if active_team_name is None:
            await _reply(ctx, embed=italy_embed("Teams", "No active team set. Use `ns team active <team_name>`."))
            return
        await _reply(ctx, embed=italy_embed("Teams", f"Active team: `{active_team_name}`"))
        return

    normalized = team_name.strip().lower()
    updated = set_active_team(_guild_id(ctx), ctx.author.id, team_name)
    if not updated:
        await _reply(ctx, embed=italy_embed("Teams", f"Team not found: `{normalized}`"))
        return
    await _reply(ctx, embed=italy_embed("Teams", f"Active team set to `{normalized}`."))


async def _battle(ctx: commands.Context, player: str, stake: int) -> None:
    if not await _require_guild(ctx, "Battle"):
        return

    resolved_member, resolve_error = await resolve_member_argument(ctx, player)
    if resolved_member is None:
        await _reply(ctx, embed=italy_embed("Battle", resolve_error or "Could not resolve player."))
        return

    prepared = prepare_battle_offer(
        guild_id=_guild_id(ctx),
        challenger_id=ctx.author.id,
        challenged_id=resolved_member.id,
        challenged_is_bot=resolved_member.bot,
        stake=stake,
    )
    if prepared.is_error:
        await _reply(ctx, embed=italy_embed("Battle", prepared.error_message or "Could not create battle proposal."))
        return

    if (
        prepared.battle_id is None
        or prepared.challenger_team_name is None
        or prepared.challenged_team_name is None
    ):
        await _reply(ctx, embed=italy_embed("Battle", "Could not create battle proposal."))
        return

    view = BattleProposalView(
        guild_id=_guild_id(ctx),
        battle_id=prepared.battle_id,
        challenger_id=ctx.author.id,
        challenged_id=resolved_member.id,
    )

    message = await _reply(
        ctx,
        embed=italy_embed(
            "Battle Proposal",
            battle_offer_description(
                challenged_mention=resolved_member.mention,
                challenger_mention=ctx.author.mention,
                stake=stake,
                challenger_team_name=prepared.challenger_team_name,
                challenged_team_name=prepared.challenged_team_name,
            ),
        ),
        view=view,
    )
    view.message = message


__all__ = [name for name in globals() if not name.startswith("__")]
