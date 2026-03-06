import asyncio
import io
import inspect
import time

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]

import discord
from discord.ext import commands

from .cards import (
    CARD_CATALOG,
    card_base_display,
    card_dupe_display,
    normalize_card_id,
    search_card_ids,
    search_card_ids_by_name,
)
from .images import (
    DEFAULT_CARD_RENDER_SIZE,
    embed_image_payload,
    morph_transition_image_payload,
    read_local_card_image_bytes,
    render_card_surface,
)
from .fonts import font_label
from .frames import frame_label
from .morphs import morph_label
from .presentation import (
    burn_confirmation_description,
    drop_choices_description,
    italy_embed,
    italy_marry_embed,
    trade_offer_description,
)
from .services import (
    execute_divorce,
    execute_marry,
    prepare_burn,
    prepare_drop,
    prepare_font,
    prepare_frame,
    prepare_morph,
    prepare_trade_offer,
)
from .settings import DB_PATH, DROP_COOLDOWN_SECONDS, DROP_TIMEOUT_SECONDS, PULL_COOLDOWN_SECONDS
from .storage import (
    assign_tag_to_instance,
    create_player_tag,
    delete_player_tag,
    get_instance_by_code,
    get_instance_by_id,
    get_instance_by_dupe_code,
    get_instance_font,
    get_instance_frame,
    get_instance_morph,
    get_instances_by_tag,
    get_player_cooldown_timestamps,
    get_player_card_instances,
    list_player_tags,
    get_player_stats,
    get_total_cards,
    set_player_tag_locked,
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
    PaginatedLinesView,
    SortableCardListView,
    SortableCollectionView,
    TradeView,
)


async def resolve_member_argument(ctx: commands.Context, raw_member: str) -> tuple[discord.Member | None, str | None]:
    if ctx.guild is None:
        return None, "Use this command in a server."

    candidate = raw_member.strip()
    if not candidate:
        return None, "Provide a player (mention or username)."

    converter = commands.MemberConverter()
    try:
        return await converter.convert(ctx, candidate), None
    except commands.BadArgument:
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
) -> tuple[discord.Member | None, str | None]:
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
                referenced_message = await fetch_message(reference_message_id)
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
            return await fetch_member(replied_author_id), None
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
        surface = render_card_surface(card_id, generation=generation, size=(card_w, card_h))
        if surface is None:
            return None
        card_surfaces.append(surface)

    gap = 16
    pad = 16
    canvas_w = (card_w * len(choices)) + (gap * (len(choices) - 1)) + (pad * 2)
    canvas_h = card_h + (pad * 2)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (20, 20, 20, 255))

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


async def _wish_add(ctx: commands.Context, card_id: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Wishlist", "Use this command in a server."))
        return

    normalized_card_id = normalize_card_id(card_id)
    matched_card_ids = [normalized_card_id] if normalized_card_id in CARD_CATALOG else search_card_ids_by_name(card_id)
    if not matched_card_ids:
        await ctx.send(embed=italy_embed("Wishlist", "Unknown card id."))
        return

    if len(matched_card_ids) > 1:
        match_lines = [
            f"{index}. {card_base_display(matched_card_id)}"
            for index, matched_card_id in enumerate(matched_card_ids, start=1)
        ]
        await ctx.send(embed=italy_embed("Wishlist Matches", multiline_text(match_lines)))
        return

    resolved_card_id = matched_card_ids[0]

    was_added = add_card_to_wishlist(ctx.guild.id, ctx.author.id, resolved_card_id)
    if not was_added:
        await ctx.send(embed=italy_embed("Wishlist", f"Already wishlisted: {card_base_display(resolved_card_id)}"))
        return

    await ctx.send(embed=italy_embed("Wishlist", f"Added to wishlist: {card_base_display(resolved_card_id)}"))


async def _wish_remove(ctx: commands.Context, card_id: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Wishlist", "Use this command in a server."))
        return

    normalized_card_id = normalize_card_id(card_id)
    matched_card_ids = [normalized_card_id] if normalized_card_id in CARD_CATALOG else search_card_ids_by_name(card_id)
    if not matched_card_ids:
        await ctx.send(embed=italy_embed("Wishlist", "Unknown card id."))
        return

    if len(matched_card_ids) > 1:
        match_lines = [
            f"{index}. {card_base_display(matched_card_id)}"
            for index, matched_card_id in enumerate(matched_card_ids, start=1)
        ]
        await ctx.send(embed=italy_embed("Wishlist Matches", multiline_text(match_lines)))
        return

    resolved_card_id = matched_card_ids[0]

    was_removed = remove_card_from_wishlist(ctx.guild.id, ctx.author.id, resolved_card_id)
    if not was_removed:
        await ctx.send(embed=italy_embed("Wishlist", f"Not on wishlist: {card_base_display(resolved_card_id)}"))
        return

    await ctx.send(embed=italy_embed("Wishlist", f"Removed from wishlist: {card_base_display(resolved_card_id)}"))


async def _wish_list(ctx: commands.Context, target_member: discord.Member | None = None) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Wishlist", "Use this command in a server."))
        return

    if target_member is None:
        target_member = ctx.author

    wishlisted_card_ids = get_wishlist_cards(ctx.guild.id, target_member.id)
    title = f"{target_member.display_name}'s Wishlist"
    if not wishlisted_card_ids:
        if target_member.id == ctx.author.id:
            description = "Your wishlist is empty. Add cards with `ns wish add <card_id>`."
        else:
            description = f"{target_member.display_name} has an empty wishlist."
        await ctx.send(embed=italy_embed(title, description))
        return

    view = SortableCardListView(
        user_id=ctx.author.id,
        title=title,
        card_ids=wishlisted_card_ids,
        wish_counts=get_card_wish_counts(ctx.guild.id),
        guard_title="Wishlist",
    )
    message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message


async def _tag_add(ctx: commands.Context, tag_name: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    created = create_player_tag(ctx.guild.id, ctx.author.id, tag_name)
    normalized = tag_name.strip().lower()
    if not created:
        await ctx.send(
            embed=italy_embed(
                "Tags",
                "Could not create that tag. Tags must be unique, non-empty, and up to 32 characters.",
            )
        )
        return

    await ctx.send(embed=italy_embed("Tags", f"Created tag: `{normalized}`"))


async def _tag_remove(ctx: commands.Context, tag_name: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    removed = delete_player_tag(ctx.guild.id, ctx.author.id, tag_name)
    normalized = tag_name.strip().lower()
    if not removed:
        await ctx.send(embed=italy_embed("Tags", f"Tag not found: `{normalized}`"))
        return

    await ctx.send(embed=italy_embed("Tags", f"Deleted tag: `{normalized}`"))


async def _tag_list(ctx: commands.Context) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    tags = list_player_tags(ctx.guild.id, ctx.author.id)
    if not tags:
        await ctx.send(embed=italy_embed("Your Tags", "No tags yet. Create one with `ns tag add <tag_name>`."))
        return

    lines = [
        f"`{tag_name}` - {'Locked' if is_locked else 'Unlocked'} - {card_count} card(s)"
        for tag_name, is_locked, card_count in tags
    ]
    await ctx.send(embed=italy_embed("Your Tags", multiline_text(lines)))


async def _tag_lock(ctx: commands.Context, tag_name: str, locked: bool) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    updated = set_player_tag_locked(ctx.guild.id, ctx.author.id, tag_name, locked)
    normalized = tag_name.strip().lower()
    if not updated:
        await ctx.send(embed=italy_embed("Tags", f"Tag not found: `{normalized}`"))
        return

    state = "locked" if locked else "unlocked"
    await ctx.send(embed=italy_embed("Tags", f"Tag `{normalized}` is now **{state}**."))


async def _tag_assign(ctx: commands.Context, tag_name: str, card_code: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    selected = get_instance_by_code(ctx.guild.id, ctx.author.id, card_code)
    if selected is None:
        await ctx.send(embed=italy_embed("Tags", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    assigned = assign_tag_to_instance(ctx.guild.id, ctx.author.id, instance_id, tag_name)
    normalized = tag_name.strip().lower()
    if not assigned:
        await ctx.send(
            embed=italy_embed(
                "Tags",
                "Could not tag that card. Make sure the tag exists and the card is yours.",
            )
        )
        return

    await ctx.send(
        embed=italy_embed(
            "Tags",
            f"Tagged {card_dupe_display(card_id, generation, dupe_code=dupe_code)} with `{normalized}`.",
        )
    )


async def _tag_unassign(ctx: commands.Context, tag_name: str, card_code: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    selected = get_instance_by_code(ctx.guild.id, ctx.author.id, card_code)
    if selected is None:
        await ctx.send(embed=italy_embed("Tags", "You do not own that card code."))
        return

    instance_id, card_id, generation, dupe_code = selected
    unassigned = unassign_tag_from_instance(ctx.guild.id, ctx.author.id, instance_id, tag_name)
    normalized = tag_name.strip().lower()
    if not unassigned:
        await ctx.send(embed=italy_embed("Tags", f"That card is not tagged with `{normalized}`."))
        return

    await ctx.send(
        embed=italy_embed(
            "Tags",
            f"Removed `{normalized}` from {card_dupe_display(card_id, generation, dupe_code=dupe_code)}.",
        )
    )


async def _tag_cards(ctx: commands.Context, tag_name: str) -> None:
    if ctx.guild is None:
        await ctx.send(embed=italy_embed("Tags", "Use this command in a server."))
        return

    normalized = tag_name.strip().lower()
    tagged_instances = get_instances_by_tag(ctx.guild.id, ctx.author.id, normalized)
    if not tagged_instances:
        await ctx.send(embed=italy_embed("Tags", f"No cards found for tag `{normalized}`."))
        return

    lines = [
        card_dupe_display(card_id, generation, dupe_code=dupe_code)
        for _instance_id, card_id, generation, dupe_code in tagged_instances
    ]
    await ctx.send(embed=italy_embed(f"Tag: `{normalized}`", multiline_text(lines)))


def register_commands(bot: commands.Bot) -> None:
    @bot.group(name="wish", aliases=["w"], invoke_without_command=True)
    async def wish(ctx: commands.Context):
        await ctx.send(
            embed=italy_embed(
                "Wishlist",
                "Usage: `ns wish add <card_id>`, `ns wish remove <card_id>`, or `ns wish list [player]`.",
            )
        )

    @wish.command(name="add", aliases=["a"])
    async def wish_add(ctx: commands.Context, card_id: str):
        await _wish_add(ctx, card_id)

    @wish.command(name="remove", aliases=["r"])
    async def wish_remove(ctx: commands.Context, card_id: str):
        await _wish_remove(ctx, card_id)

    @wish.command(name="list", aliases=["l"])
    async def wish_list(ctx: commands.Context, *, player: str | None = None):
        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member
        await _wish_list(ctx, target_member)

    @bot.command(name="wa")
    async def wish_add_short(ctx: commands.Context, card_id: str):
        await _wish_add(ctx, card_id)

    @bot.command(name="wr")
    async def wish_remove_short(ctx: commands.Context, card_id: str):
        await _wish_remove(ctx, card_id)

    @bot.command(name="wl")
    async def wish_list_short(ctx: commands.Context, *, player: str | None = None):
        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member
        await _wish_list(ctx, target_member)

    @bot.group(name="tag", aliases=["tg"], invoke_without_command=True)
    async def tag(ctx: commands.Context):
        await ctx.send(
            embed=italy_embed(
                "Tags",
                (
                    "Usage: `ns tag add <tag_name>`, `ns tag remove <tag_name>`, `ns tag list`, "
                    "`ns tag lock <tag_name>`, `ns tag unlock <tag_name>`, "
                    "`ns tag assign <tag_name> <card_code>`, `ns tag unassign <tag_name> <card_code>`, "
                    "`ns tag cards <tag_name>`."
                ),
            )
        )

    @tag.command(name="add", aliases=["a", "create"])
    async def tag_add(ctx: commands.Context, tag_name: str):
        await _tag_add(ctx, tag_name)

    @tag.command(name="remove", aliases=["r", "delete"])
    async def tag_remove(ctx: commands.Context, tag_name: str):
        await _tag_remove(ctx, tag_name)

    @tag.command(name="list", aliases=["l"])
    async def tag_list(ctx: commands.Context):
        await _tag_list(ctx)

    @tag.command(name="lock")
    async def tag_lock(ctx: commands.Context, tag_name: str):
        await _tag_lock(ctx, tag_name, True)

    @tag.command(name="unlock")
    async def tag_unlock(ctx: commands.Context, tag_name: str):
        await _tag_lock(ctx, tag_name, False)

    @tag.command(name="assign", aliases=["as"])
    async def tag_assign(ctx: commands.Context, tag_name: str, card_code: str):
        await _tag_assign(ctx, tag_name, card_code)

    @tag.command(name="unassign", aliases=["u"])
    async def tag_unassign(ctx: commands.Context, tag_name: str, card_code: str):
        await _tag_unassign(ctx, tag_name, card_code)

    @tag.command(name="cards", aliases=["c"])
    async def tag_cards(ctx: commands.Context, tag_name: str):
        await _tag_cards(ctx, tag_name)

    @bot.command(name="cards", aliases=["ca"])
    async def cards(ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("All Cards", "Use this command in a server."))
            return

        wish_counts = get_card_wish_counts(ctx.guild.id)
        entries = [(card_id, wish_counts.get(card_id, 0)) for card_id in CARD_CATALOG.keys()]

        view = CardCatalogView(user_id=ctx.author.id, entries=entries)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="lookup", aliases=["l"])
    async def lookup(ctx: commands.Context, *, card_id: str | None = None):
        if card_id is None:
            await ctx.send(embed=italy_embed("Lookup", "Usage: `ns lookup <card_id|card_code|query>`."))
            return

        if ctx.guild is not None:
            matched_instance = get_instance_by_dupe_code(ctx.guild.id, card_id)
            if matched_instance is not None:
                matched_instance_id, matched_card_id, matched_generation, matched_dupe_code = matched_instance
                lookup_embed = italy_embed(
                    "Card Lookup",
                    card_dupe_display(matched_card_id, matched_generation, dupe_code=matched_dupe_code),
                )
                image_url, image_file = embed_image_payload(
                    matched_card_id,
                    generation=matched_generation,
                    morph_key=get_instance_morph(ctx.guild.id, matched_instance_id),
                    frame_key=get_instance_frame(ctx.guild.id, matched_instance_id),
                    font_key=get_instance_font(ctx.guild.id, matched_instance_id),
                )
                if image_url is not None:
                    lookup_embed.set_image(url=image_url)
                send_kwargs: dict[str, object] = {"embed": lookup_embed}
                if image_file is not None:
                    send_kwargs["file"] = image_file
                await ctx.send(**send_kwargs)
                return

        normalized_card_id = normalize_card_id(card_id)
        if normalized_card_id in CARD_CATALOG:
            lookup_embed = italy_embed("Card Lookup", card_base_display(normalized_card_id))
            image_url, image_file = embed_image_payload(normalized_card_id)
            if image_url is not None:
                lookup_embed.set_image(url=image_url)
            send_kwargs: dict[str, object] = {"embed": lookup_embed}
            if image_file is not None:
                send_kwargs["file"] = image_file
            await ctx.send(**send_kwargs)
            return

        name_matches = search_card_ids(card_id, include_series=True)
        if not name_matches:
            await ctx.send(embed=italy_embed("Lookup", "No results found."))
            return

        if len(name_matches) == 1:
            matched_card_id = name_matches[0]
            lookup_embed = italy_embed("Card Lookup", card_base_display(matched_card_id))
            image_url, image_file = embed_image_payload(matched_card_id)
            if image_url is not None:
                lookup_embed.set_image(url=image_url)
            send_kwargs: dict[str, object] = {"embed": lookup_embed}
            if image_file is not None:
                send_kwargs["file"] = image_file
            await ctx.send(**send_kwargs)
            return

        lookup_wish_counts = get_card_wish_counts(ctx.guild.id) if ctx.guild is not None else {}
        view = SortableCardListView(
            user_id=ctx.author.id,
            title="Lookup Matches",
            card_ids=name_matches,
            wish_counts=lookup_wish_counts,
            guard_title="Lookup",
        )
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message
        return

    @bot.command(name="drop", aliases=["d"])
    async def drop(ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Drop", "Use this command in a server."))
            return

        now = time.time()
        prepared = prepare_drop(ctx.guild.id, ctx.author.id, now)

        if prepared.is_cooldown:
            await ctx.send(
                embed=italy_embed(
                    "Drop Cooldown",
                    f"You need to wait **{format_cooldown(prepared.cooldown_remaining_seconds)}** before your next drop.",
                )
            )
            return

        choices = prepared.choices

        embed = italy_embed(
            f"{ctx.author.display_name}'s Drop",
            drop_choices_description(choices),
        )
        embed.set_footer(text=f"Pull timeout: {DROP_TIMEOUT_SECONDS}s")

        preview_file = await build_drop_preview_file(choices)
        send_kwargs: dict[str, object] = {"embed": embed}
        if preview_file is not None:
            embed.set_image(url="attachment://drop_choices.png")
            send_kwargs["file"] = preview_file

        view = DropView(ctx.guild.id, ctx.author.id, choices)
        message = await ctx.send(view=view, **send_kwargs)
        view.message = message

    @bot.command(name="marry", aliases=["m"])
    async def marry(ctx: commands.Context, card_code: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_marry_embed("Marry", "Use this command in a server."))
            return

        result = execute_marry(ctx.guild.id, ctx.author.id, card_code)
        if result.is_error:
            await ctx.send(embed=italy_marry_embed("Marry", result.error_message or "Marry failed."))
            return

        if result.card_id is None or result.generation is None:
            await ctx.send(embed=italy_marry_embed("Marry", "Marry failed."))
            return

        marry_embed = italy_marry_embed(
            "Marry",
            f"You are now married to {card_dupe_display(result.card_id, result.generation, dupe_code=result.dupe_code)}.",
        )
        morph_key = None
        frame_key = None
        font_key = None
        if result.dupe_code is not None:
            married_instance = get_instance_by_code(ctx.guild.id, ctx.author.id, result.dupe_code)
            if married_instance is not None:
                married_instance_id, _, _, _ = married_instance
                morph_key = get_instance_morph(ctx.guild.id, married_instance_id)
                frame_key = get_instance_frame(ctx.guild.id, married_instance_id)
            font_key = get_instance_font(ctx.guild.id, married_instance_id)

        image_url, image_file = embed_image_payload(
            result.card_id,
            generation=result.generation,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        )
        if image_url is not None:
            marry_embed.set_image(url=image_url)
        send_kwargs: dict[str, object] = {"embed": marry_embed}
        if image_file is not None:
            send_kwargs["file"] = image_file
        await ctx.send(**send_kwargs)

    @bot.command(name="divorce", aliases=["dv"])
    async def divorce(ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(embed=italy_marry_embed("Divorce", "Use this command in a server."))
            return

        result = execute_divorce(ctx.guild.id, ctx.author.id)
        if result.is_error:
            await ctx.send(embed=italy_marry_embed("Divorce", result.error_message or "Divorce failed."))
            return

        if result.card_id is None or result.generation is None:
            await ctx.send(embed=italy_marry_embed("Divorce", "Divorce failed."))
            return

        divorce_embed = italy_marry_embed(
            "Divorce",
            f"You divorced {card_dupe_display(result.card_id, result.generation, dupe_code=result.dupe_code)}.",
        )
        morph_key = None
        frame_key = None
        font_key = None
        if result.dupe_code is not None:
            divorced_instance = get_instance_by_code(ctx.guild.id, ctx.author.id, result.dupe_code)
            if divorced_instance is not None:
                divorced_instance_id, _, _, _ = divorced_instance
                morph_key = get_instance_morph(ctx.guild.id, divorced_instance_id)
                frame_key = get_instance_frame(ctx.guild.id, divorced_instance_id)
            font_key = get_instance_font(ctx.guild.id, divorced_instance_id)

        image_url, image_file = embed_image_payload(
            result.card_id,
            generation=result.generation,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        )
        if image_url is not None:
            divorce_embed.set_image(url=image_url)
        send_kwargs: dict[str, object] = {"embed": divorce_embed}
        if image_file is not None:
            send_kwargs["file"] = image_file
        await ctx.send(**send_kwargs)

    @bot.command(name="collection", aliases=["c"])
    async def collection(ctx: commands.Context, *, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Collection", "Use this command in a server."))
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Collection", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member

        instances = get_player_card_instances(ctx.guild.id, target_member.id)
        title = f"{target_member.display_name}'s Collection"
        if not instances:
            description = (
                "Your collection is empty. Try `ns drop`."
                if target_member.id == ctx.author.id
                else f"{target_member.display_name} has an empty collection."
            )
            await ctx.send(embed=italy_embed(title, description))
            return

        view = SortableCollectionView(
            user_id=ctx.author.id,
            title=title,
            instances=instances,
            wish_counts=get_card_wish_counts(ctx.guild.id),
            instance_styles={
                instance_id: (
                    get_instance_morph(ctx.guild.id, instance_id),
                    get_instance_frame(ctx.guild.id, instance_id),
                    get_instance_font(ctx.guild.id, instance_id),
                )
                for instance_id, _card_id, _generation, _dupe_code in instances
            },
            guard_title="Collection",
        )
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="burn", aliases=["b"])
    async def burn(ctx: commands.Context, card_code: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Burn", "Use this command in a server."))
            return

        prepared = prepare_burn(ctx.guild.id, ctx.author.id, card_code)
        if prepared.is_error:
            await ctx.send(embed=italy_embed("Burn", prepared.error_message or "Burn failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.payout is None
            or prepared.value is None
            or prepared.base_value is None
            or prepared.delta_range is None
            or prepared.multiplier is None
        ):
            await ctx.send(embed=italy_embed("Burn", "Burn failed."))
            return

        instance_id = prepared.instance_id
        burn_card_id = prepared.card_id
        burn_generation = prepared.generation
        burn_dupe_code = prepared.dupe_code
        value = prepared.value
        base_value = prepared.base_value
        delta_range = prepared.delta_range
        multiplier = prepared.multiplier

        confirm_embed = italy_embed(
            "Burn Confirmation",
            burn_confirmation_description(
                card_id=burn_card_id,
                generation=burn_generation,
                dupe_code=burn_dupe_code,
                value=value,
                base_value=base_value,
                delta_range=delta_range,
                multiplier=multiplier,
            ),
        )
        image_url, image_file = embed_image_payload(
            burn_card_id,
            generation=burn_generation,
            morph_key=get_instance_morph(ctx.guild.id, instance_id),
            frame_key=get_instance_frame(ctx.guild.id, instance_id),
            font_key=get_instance_font(ctx.guild.id, instance_id),
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = BurnConfirmView(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            instance_id=instance_id,
            card_id=burn_card_id,
            generation=burn_generation,
            delta_range=delta_range,
        )
        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await ctx.send(**send_kwargs)
        view.message = message

    @bot.command(name="morph", aliases=["mo"])
    async def morph(ctx: commands.Context, card_code: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Morph", "Use this command in a server."))
            return

        prepared = prepare_morph(ctx.guild.id, ctx.author.id, card_code)
        if prepared.is_error:
            await ctx.send(embed=italy_embed("Morph", prepared.error_message or "Morph failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.morph_key is None
            or prepared.morph_name is None
            or prepared.cost is None
        ):
            await ctx.send(embed=italy_embed("Morph", "Morph failed."))
            return

        confirm_embed = italy_embed(
            "Morph Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Before: **{morph_label(prepared.current_morph_key)}**\n"
                f"After (if confirmed): **{prepared.morph_name}**\n\n"
                f"Morph Cost: **{prepared.cost}** dough"
            ),
        )
        before_frame_key = get_instance_frame(ctx.guild.id, prepared.instance_id)
        before_font_key = get_instance_font(ctx.guild.id, prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=prepared.current_morph_key,
            after_morph_key=prepared.morph_key,
            before_frame_key=before_frame_key,
            after_frame_key=before_frame_key,
            before_font_key=before_font_key,
            after_font_key=before_font_key,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = MorphConfirmView(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=prepared.current_morph_key,
            after_morph_key=prepared.morph_key,
            after_morph_name=prepared.morph_name,
            before_frame_key=before_frame_key,
            before_font_key=before_font_key,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await ctx.send(**send_kwargs)
        view.message = message

    @bot.command(name="frame", aliases=["fr"])
    async def frame(ctx: commands.Context, card_code: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Frame", "Use this command in a server."))
            return

        prepared = prepare_frame(ctx.guild.id, ctx.author.id, card_code)
        if prepared.is_error:
            await ctx.send(embed=italy_embed("Frame", prepared.error_message or "Frame failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.frame_key is None
            or prepared.frame_name is None
            or prepared.cost is None
        ):
            await ctx.send(embed=italy_embed("Frame", "Frame failed."))
            return

        confirm_embed = italy_embed(
            "Frame Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Before: **{frame_label(prepared.current_frame_key)}**\n"
                f"After (if confirmed): **{prepared.frame_name}**\n\n"
                f"Frame Cost: **{prepared.cost}** dough"
            ),
        )
        current_morph_key = get_instance_morph(ctx.guild.id, prepared.instance_id)
        current_font_key = get_instance_font(ctx.guild.id, prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=current_morph_key,
            after_morph_key=current_morph_key,
            before_frame_key=prepared.current_frame_key,
            after_frame_key=prepared.frame_key,
            before_font_key=current_font_key,
            after_font_key=current_font_key,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = FrameConfirmView(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=current_morph_key,
            before_frame_key=prepared.current_frame_key,
            before_font_key=current_font_key,
            after_frame_key=prepared.frame_key,
            after_frame_name=prepared.frame_name,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await ctx.send(**send_kwargs)
        view.message = message

    @bot.command(name="font", aliases=["fo"])
    async def font(ctx: commands.Context, card_code: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Font", "Use this command in a server."))
            return

        prepared = prepare_font(ctx.guild.id, ctx.author.id, card_code)
        if prepared.is_error:
            await ctx.send(embed=italy_embed("Font", prepared.error_message or "Font failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.font_key is None
            or prepared.font_name is None
            or prepared.cost is None
        ):
            await ctx.send(embed=italy_embed("Font", "Font failed."))
            return

        confirm_embed = italy_embed(
            "Font Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Before: **{font_label(prepared.current_font_key)}**\n"
                f"After (if confirmed): **{prepared.font_name}**\n\n"
                f"Font Cost: **{prepared.cost}** dough"
            ),
        )
        current_morph_key = get_instance_morph(ctx.guild.id, prepared.instance_id)
        current_frame_key = get_instance_frame(ctx.guild.id, prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=current_morph_key,
            after_morph_key=current_morph_key,
            before_frame_key=current_frame_key,
            after_frame_key=current_frame_key,
            before_font_key=prepared.current_font_key,
            after_font_key=prepared.font_key,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = FontConfirmView(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=current_morph_key,
            before_frame_key=current_frame_key,
            before_font_key=prepared.current_font_key,
            after_font_key=prepared.font_key,
            after_font_name=prepared.font_name,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await ctx.send(**send_kwargs)
        view.message = message

    @bot.command(name="cooldown", aliases=["cd"])
    async def cooldown(ctx: commands.Context, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Cooldowns", "Use this command in a server."))
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Cooldowns", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member

        last_drop_at, last_pull_at = get_player_cooldown_timestamps(ctx.guild.id, target_member.id)
        now = time.time()
        drop_elapsed = now - last_drop_at
        pull_elapsed = now - last_pull_at

        description = multiline_text(
            [
                _cooldown_status_line("Drop", drop_elapsed, DROP_COOLDOWN_SECONDS),
                _cooldown_status_line("Pull", pull_elapsed, PULL_COOLDOWN_SECONDS),
            ]
        )

        await ctx.send(embed=italy_embed(f"{target_member.display_name}'s Cooldowns", description))

    @bot.command(name="info", aliases=["i"])
    async def info(ctx: commands.Context, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Info", "Use this command in a server."))
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Info", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member

        dough, _, married_instance_id = get_player_stats(ctx.guild.id, target_member.id)
        wishes_count = len(get_wishlist_cards(ctx.guild.id, target_member.id))
        married = "None"
        married_image_url: str | None = None
        married_image_file: discord.File | None = None
        married_generation: int | None = None
        if married_instance_id is not None:
            married_instance = get_instance_by_id(ctx.guild.id, married_instance_id)
            if married_instance is not None:
                _, married_card_id, married_generation, married_dupe_code = married_instance
                married = card_dupe_display(married_card_id, married_generation, dupe_code=married_dupe_code)
                married_image_url, married_image_file = embed_image_payload(
                    married_card_id,
                    generation=married_generation,
                    morph_key=get_instance_morph(ctx.guild.id, married_instance_id),
                    frame_key=get_instance_frame(ctx.guild.id, married_instance_id),
                    font_key=get_instance_font(ctx.guild.id, married_instance_id),
                )

        embed = italy_embed(f"{target_member.display_name}'s Stats")
        embed.add_field(name="Cards", value=str(get_total_cards(ctx.guild.id, target_member.id)), inline=True)
        embed.add_field(name="Dough", value=str(dough), inline=True)
        embed.add_field(name="Wishes", value=str(wishes_count), inline=True)
        embed.add_field(name="Married Card", value=married, inline=False)
        if married_image_url is not None:
            embed.set_image(url=married_image_url)

        send_kwargs: dict[str, object] = {"embed": embed}
        if married_image_file is not None:
            send_kwargs["file"] = married_image_file
        await ctx.send(**send_kwargs)

    @bot.command(name="trade", aliases=["t"])
    async def trade(
        ctx: commands.Context,
        player: str,
        card_code: str,
        amount: int,
    ):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Trade", "Use this command in a server."))
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await ctx.send(embed=italy_embed("Trade", resolve_error or "Could not resolve player."))
            return

        prepared = prepare_trade_offer(
            guild_id=ctx.guild.id,
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            buyer_is_bot=resolved_member.bot,
            card_code=card_code,
            amount=amount,
        )

        if prepared.is_error:
            await ctx.send(embed=italy_embed("Trade", prepared.error_message or "Trade failed."))
            return

        if prepared.card_id is None or prepared.generation is None or prepared.dupe_code is None:
            await ctx.send(embed=italy_embed("Trade", "Trade failed."))
            return

        card_id = prepared.card_id
        generation = prepared.generation
        dupe_code = prepared.dupe_code

        view = TradeView(
            guild_id=ctx.guild.id,
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            card_id=card_id,
            dupe_code=dupe_code,
            amount=amount,
        )

        message = await ctx.send(
            embed=italy_embed(
                "Trade Offer",
                trade_offer_description(resolved_member.mention, ctx.author.mention, card_id, generation, dupe_code, amount),
            ),
            view=view,
        )
        view.message = message

    @bot.command(name="help", aliases=["h"])
    async def help_command(ctx: commands.Context):
        view = HelpView(user_id=ctx.author.id)
        message = await ctx.send(embed=view.build_overview_embed(), view=view)
        view.message = message

    @bot.command(name="dbexport")
    @commands.is_owner()
    async def dbexport(ctx: commands.Context):
        if not DB_PATH.exists():
            await ctx.send(embed=italy_embed("DB Export", "No database file found yet."))
            return

        await ctx.send(
            embed=italy_embed("DB Export", "Exporting current `noodswap.db`."),
            file=discord.File(DB_PATH, filename="noodswap.db"),
        )

    @bot.command(name="dbreset")
    @commands.is_owner()
    async def dbreset(ctx: commands.Context):
        reset_db_data()
        await ctx.send(
            embed=italy_embed(
                "DB Reset",
                "Database reset complete. All persisted Noodswap data has been deleted.",
            )
        )
