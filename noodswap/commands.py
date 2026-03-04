import asyncio
import io
import inspect
import json
import time
import urllib.request
from pathlib import Path

asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[assignment]

import discord
from discord.ext import commands

from .cards import (
    CARD_CATALOG,
    card_base_display,
    card_dupe_display,
    card_image_url,
    normalize_card_id,
    search_card_ids_by_name,
)
from .presentation import (
    burn_confirmation_description,
    drop_choices_description,
    help_description,
    italy_embed,
    italy_marry_embed,
    trade_offer_description,
)
from .services import execute_divorce, execute_marry, prepare_burn, prepare_drop, prepare_trade_offer
from .settings import CARD_IMAGE_CACHE_MANIFEST, DB_PATH, DROP_TIMEOUT_SECONDS, PULL_COOLDOWN_SECONDS
from .storage import (
    get_instance_by_id,
    get_player_card_instances,
    get_player_stats,
    get_total_cards,
    add_card_to_wishlist,
    get_card_wish_counts,
    get_wishlist_cards,
    remove_card_from_wishlist,
    reset_db_data,
)
from .utils import format_cooldown, multiline_text
from .views import BurnConfirmView, CardCatalogView, DropView, TradeView


async def resolve_member_argument(ctx: commands.Context, raw_player: str) -> tuple[discord.Member | None, str | None]:
    if ctx.guild is None:
        return None, "Use this command in a server."

    candidate = raw_player.strip()
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


def _fetch_image_bytes(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "NoodswapBot/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.read()
    except Exception:
        return None


def _read_cached_image_bytes(card_id: str) -> bytes | None:
    try:
        manifest_data = json.loads(CARD_IMAGE_CACHE_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return None

    entry = manifest_data.get(card_id)
    if not isinstance(entry, dict):
        return None

    file_name = entry.get("file")
    if not isinstance(file_name, str) or not file_name:
        return None

    image_path = CARD_IMAGE_CACHE_MANIFEST.parent / Path(file_name)
    try:
        return image_path.read_bytes()
    except Exception:
        return None


def _build_drop_preview_blocking(choices: list[tuple[str, int]]) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        return None

    card_w = 360
    card_h = 240

    def _placeholder_image(card_id: str, generation: int) -> Image.Image:
        image = Image.new("RGB", (card_w, card_h), (32, 32, 32))
        draw = ImageDraw.Draw(image)
        draw.text((16, 16), f"{card_id}\nG-{generation:04d}", fill=(235, 235, 235))
        draw.text((16, card_h - 36), "Image unavailable", fill=(190, 190, 190))
        return image

    images: list[Image.Image] = []
    for card_id, generation in choices:
        raw = _read_cached_image_bytes(card_id)
        if raw is None:
            raw = _fetch_image_bytes(card_image_url(card_id))
        if raw is None:
            images.append(_placeholder_image(card_id, generation))
            continue

        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            images.append(image)
        except Exception:
            images.append(_placeholder_image(card_id, generation))

    gap = 16
    pad = 16
    canvas_w = (card_w * len(choices)) + (gap * (len(choices) - 1)) + (pad * 2)
    canvas_h = card_h + (pad * 2)

    canvas = Image.new("RGB", (canvas_w, canvas_h), (20, 20, 20))

    for idx in range(len(choices)):
        image = images[idx]
        fitted = ImageOps.fit(image, (card_w, card_h), method=Image.Resampling.LANCZOS)
        x = pad + idx * (card_w + gap)
        y = pad
        canvas.paste(fitted, (x, y))

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


async def build_drop_preview_file(choices: list[tuple[str, int]]) -> discord.File | None:
    image_bytes = await asyncio.to_thread(_build_drop_preview_blocking, choices)
    if image_bytes is None:
        return None
    return discord.File(io.BytesIO(image_bytes), filename="drop_choices.png")


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
        match_lines = [card_base_display(matched_card_id) for matched_card_id in matched_card_ids]
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
        match_lines = [card_base_display(matched_card_id) for matched_card_id in matched_card_ids]
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

    lines = [card_base_display(card_id) for card_id in wishlisted_card_ids]
    await ctx.send(embed=italy_embed(title, multiline_text(lines)))


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
        target_member = ctx.author
        if player is not None:
            resolved_player, resolve_error = await resolve_member_argument(ctx, player)
            if resolved_player is None:
                await ctx.send(embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
                return
            target_member = resolved_player
        await _wish_list(ctx, target_member)

    @bot.command(name="wa")
    async def wish_add_short(ctx: commands.Context, card_id: str):
        await _wish_add(ctx, card_id)

    @bot.command(name="wr")
    async def wish_remove_short(ctx: commands.Context, card_id: str):
        await _wish_remove(ctx, card_id)

    @bot.command(name="wl")
    async def wish_list_short(ctx: commands.Context, *, player: str | None = None):
        target_member = ctx.author
        if player is not None:
            resolved_player, resolve_error = await resolve_member_argument(ctx, player)
            if resolved_player is None:
                await ctx.send(embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
                return
            target_member = resolved_player
        await _wish_list(ctx, target_member)

    @bot.command(name="cards", aliases=["ca"])
    async def cards(ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("All Cards", "Use this command in a server."))
            return

        wish_counts = get_card_wish_counts(ctx.guild.id)
        sorted_card_ids = sorted(
            CARD_CATALOG.keys(),
            key=lambda card_id: (-wish_counts.get(card_id, 0), card_id),
        )
        entries = [(card_id, wish_counts.get(card_id, 0)) for card_id in sorted_card_ids]

        view = CardCatalogView(user_id=ctx.author.id, entries=entries)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="lookup", aliases=["l"])
    async def lookup(ctx: commands.Context, *, card_id: str | None = None):
        if card_id is None:
            await ctx.send(embed=italy_embed("Lookup", "Usage: `ns lookup <card_id>`."))
            return

        normalized_card_id = normalize_card_id(card_id)
        if normalized_card_id in CARD_CATALOG:
            lookup_embed = italy_embed("Card Lookup", card_base_display(normalized_card_id))
            lookup_embed.set_image(url=card_image_url(normalized_card_id))
            await ctx.send(embed=lookup_embed)
            return

        name_matches = search_card_ids_by_name(card_id)
        if not name_matches:
            await ctx.send(embed=italy_embed("Lookup", "Unknown card id."))
            return

        if len(name_matches) == 1:
            matched_card_id = name_matches[0]
            lookup_embed = italy_embed("Card Lookup", card_base_display(matched_card_id))
            lookup_embed.set_image(url=card_image_url(matched_card_id))
            await ctx.send(embed=lookup_embed)
            return

        match_lines = [card_base_display(matched_card_id) for matched_card_id in name_matches]
        await ctx.send(embed=italy_embed("Lookup Matches", multiline_text(match_lines)))
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
        marry_embed.set_image(url=card_image_url(result.card_id))
        await ctx.send(
            embed=marry_embed
        )

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
        divorce_embed.set_image(url=card_image_url(result.card_id))
        await ctx.send(
            embed=divorce_embed
        )

    @bot.command(name="collection", aliases=["c"])
    async def collection(ctx: commands.Context, *, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Collection", "Use this command in a server."))
            return

        target_member = ctx.author
        if player is not None:
            resolved_player, resolve_error = await resolve_member_argument(ctx, player)
            if resolved_player is None:
                await ctx.send(embed=italy_embed("Collection", resolve_error or "Could not resolve player."))
                return
            target_member = resolved_player

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

        sorted_instances = sorted(instances, key=lambda item: (item[2], item[1], item[0]))
        lines = [
            card_dupe_display(card_id, generation, dupe_code=dupe_code)
            for _, card_id, generation, dupe_code in sorted_instances
        ]
        await ctx.send(embed=italy_embed(title, multiline_text(lines)))

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
        value = prepared.value
        base_value = prepared.base_value
        delta_range = prepared.delta_range
        multiplier = prepared.multiplier

        confirm_embed = italy_embed(
            "Burn Confirmation",
            burn_confirmation_description(
                card_id=burn_card_id,
                generation=burn_generation,
                value=value,
                base_value=base_value,
                delta_range=delta_range,
                multiplier=multiplier,
            ),
        )
        confirm_embed.set_image(url=card_image_url(burn_card_id))

        view = BurnConfirmView(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            instance_id=instance_id,
            card_id=burn_card_id,
            generation=burn_generation,
            delta_range=delta_range,
        )
        message = await ctx.send(embed=confirm_embed, view=view)
        view.message = message

    @bot.command(name="cooldown", aliases=["cd"])
    async def cooldown(ctx: commands.Context, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Drop Cooldown", "Use this command in a server."))
            return

        target_member = ctx.author
        if player is not None:
            resolved_player, resolve_error = await resolve_member_argument(ctx, player)
            if resolved_player is None:
                await ctx.send(embed=italy_embed("Drop Cooldown", resolve_error or "Could not resolve player."))
                return
            target_member = resolved_player

        _, last_pull_at, _ = get_player_stats(ctx.guild.id, target_member.id)
        elapsed = time.time() - last_pull_at
        if elapsed < PULL_COOLDOWN_SECONDS:
            remaining = PULL_COOLDOWN_SECONDS - elapsed
            description = f"Ready in **{format_cooldown(remaining)}**."
        else:
            description = "Ready now."

        await ctx.send(embed=italy_embed(f"{target_member.display_name}'s Drop Cooldown", description))

    @bot.command(name="info", aliases=["i"])
    async def info(ctx: commands.Context, player: str | None = None):
        if ctx.guild is None:
            await ctx.send(embed=italy_embed("Info", "Use this command in a server."))
            return

        target_member = ctx.author
        if player is not None:
            resolved_player, resolve_error = await resolve_member_argument(ctx, player)
            if resolved_player is None:
                await ctx.send(embed=italy_embed("Info", resolve_error or "Could not resolve player."))
                return
            target_member = resolved_player

        dough, _, married_instance_id = get_player_stats(ctx.guild.id, target_member.id)
        wishes_count = len(get_wishlist_cards(ctx.guild.id, target_member.id))
        married = "None"
        married_image_url: str | None = None
        if married_instance_id is not None:
            married_instance = get_instance_by_id(ctx.guild.id, married_instance_id)
            if married_instance is not None:
                _, married_card_id, married_generation, married_dupe_code = married_instance
                married = card_dupe_display(married_card_id, married_generation, dupe_code=married_dupe_code)
                married_image_url = card_image_url(married_card_id)

        embed = italy_embed(f"{target_member.display_name}'s Stats")
        embed.add_field(name="Cards", value=str(get_total_cards(ctx.guild.id, target_member.id)), inline=True)
        embed.add_field(name="Dough", value=str(dough), inline=True)
        embed.add_field(name="Wishes", value=str(wishes_count), inline=True)
        embed.add_field(name="Married Card", value=married, inline=False)
        if married_image_url is not None:
            embed.set_image(url=married_image_url)

        await ctx.send(embed=embed)

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

        resolved_player, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_player is None:
            await ctx.send(embed=italy_embed("Trade", resolve_error or "Could not resolve player."))
            return

        prepared = prepare_trade_offer(
            guild_id=ctx.guild.id,
            seller_id=ctx.author.id,
            buyer_id=resolved_player.id,
            buyer_is_bot=resolved_player.bot,
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
            buyer_id=resolved_player.id,
            card_id=card_id,
            dupe_code=dupe_code,
            amount=amount,
        )

        message = await ctx.send(
            embed=italy_embed(
                "Trade Offer",
                trade_offer_description(resolved_player.mention, ctx.author.mention, card_id, generation, dupe_code, amount),
            ),
            view=view,
        )
        view.message = message

    @bot.command(name="help", aliases=["h"])
    async def help_command(ctx: commands.Context):
        await ctx.send(
            embed=italy_embed(
                "Help",
                help_description(),
            )
        )

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
