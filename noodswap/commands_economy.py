# pylint: disable=wildcard-import,unused-wildcard-import,undefined-variable
from .command_utils import *  # noqa: F403

def register_economy_commands(bot: commands.Bot) -> None:
    @bot.command(name="drop", aliases=["d"])
    async def drop(ctx: commands.Context):
        if not await _require_guild(ctx, "Drop"):
            return

        now = time.time()
        prepared = prepare_drop(_guild_id(ctx), ctx.author.id, now)

        if prepared.is_cooldown:
            await _reply(
                ctx,
                embed=italy_embed(
                    "Drop Cooldown",
                    f"You need to wait **{format_cooldown(prepared.cooldown_remaining_seconds)}** before your next drop.",
                ),
            )
            return

        choices = prepared.choices
        embed = italy_embed(f"{ctx.author.display_name}'s Drop", drop_choices_description(choices))
        footer_text = f"Pull timeout: {DROP_TIMEOUT_SECONDS}s"
        if prepared.used_drop_ticket:
            footer_text = f"{footer_text} | 1 drop ticket used"
        embed.set_footer(text=footer_text)

        preview_file = await build_drop_preview_file(choices)
        send_kwargs: dict[str, object] = {"embed": embed}
        if preview_file is not None:
            send_kwargs["file"] = preview_file

        view = DropView(_guild_id(ctx), ctx.author.id, choices)
        message = await _reply(ctx, view=view, **send_kwargs)
        view.message = message

    @bot.command(name="marry", aliases=["m"])
    async def marry(ctx: commands.Context, card_code: str | None = None):
        if not await _require_guild(ctx, "Marry", marry_style=True):
            return

        result = execute_marry(_guild_id(ctx), ctx.author.id, card_code)
        if result.is_error:
            await _reply(ctx, embed=italy_marry_embed("Marry", result.error_message or "Marry failed."))
            return

        if result.card_id is None or result.generation is None:
            await _reply(ctx, embed=italy_marry_embed("Marry", "Marry failed."))
            return

        marry_embed = italy_marry_embed(
            "Marry",
            f"You are now married to {card_dupe_display(result.card_id, result.generation, dupe_code=result.dupe_code)}.",
        )
        morph_key = None
        frame_key = None
        font_key = None
        if result.dupe_code is not None:
            married_instance = get_instance_by_code(_guild_id(ctx), ctx.author.id, result.dupe_code)
            if married_instance is not None:
                married_instance_id, _, _, _ = married_instance
                morph_key = get_instance_morph(_guild_id(ctx), married_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), married_instance_id)
                font_key = get_instance_font(_guild_id(ctx), married_instance_id)

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
        await _reply(ctx, **send_kwargs)

    @bot.command(name="divorce", aliases=["dv"])
    async def divorce(ctx: commands.Context):
        if not await _require_guild(ctx, "Divorce", marry_style=True):
            return

        result = execute_divorce(_guild_id(ctx), ctx.author.id)
        if result.is_error:
            await _reply(ctx, embed=italy_marry_embed("Divorce", result.error_message or "Divorce failed."))
            return

        if result.card_id is None or result.generation is None:
            await _reply(ctx, embed=italy_marry_embed("Divorce", "Divorce failed."))
            return

        divorce_embed = italy_marry_embed(
            "Divorce",
            f"You divorced {card_dupe_display(result.card_id, result.generation, dupe_code=result.dupe_code)}.",
        )
        morph_key = None
        frame_key = None
        font_key = None
        if result.dupe_code is not None:
            divorced_instance = get_instance_by_code(_guild_id(ctx), ctx.author.id, result.dupe_code)
            if divorced_instance is not None:
                divorced_instance_id, _, _, _ = divorced_instance
                morph_key = get_instance_morph(_guild_id(ctx), divorced_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), divorced_instance_id)
                font_key = get_instance_font(_guild_id(ctx), divorced_instance_id)

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
        await _reply(ctx, **send_kwargs)

    @bot.command(name="collection", aliases=["c"])
    async def collection(ctx: commands.Context, *, player: str | None = None):
        if not await _require_guild(ctx, "Collection"):
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await _reply(ctx, embed=italy_embed("Collection", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member

        instances = get_player_card_instances(_guild_id(ctx), target_member.id)
        title = f"{target_member.display_name}'s Collection"
        if not instances:
            if target_member.id == ctx.author.id:
                description = "Your collection is empty. Try `ns drop`."
            else:
                description = f"{target_member.display_name} has an empty collection."
            await _reply(ctx, embed=italy_embed(title, description))
            return

        view = SortableCollectionView(
            user_id=ctx.author.id,
            title=title,
            instances=instances,
            locked_instance_ids=get_locked_instance_ids(
                _guild_id(ctx),
                target_member.id,
                [instance_id for instance_id, _card_id, _generation, _dupe_code in instances],
            ),
            wish_counts=get_card_wish_counts(_guild_id(ctx)),
            folder_emojis_by_instance=_folder_emoji_map_for_instances(_guild_id(ctx), target_member.id, instances),
            instance_styles={
                instance_id: (
                    get_instance_morph(_guild_id(ctx), instance_id),
                    get_instance_frame(_guild_id(ctx), instance_id),
                    get_instance_font(_guild_id(ctx), instance_id),
                )
                for instance_id, _card_id, _generation, _dupe_code in instances
            },
            card_line_formatter=card_dupe_display_concise,
            guard_title="Collection",
        )
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="burn", aliases=["b"])
    async def burn(ctx: commands.Context, *targets: str):
        if not await _require_guild(ctx, "Burn"):
            return

        resolved_targets: list[tuple[int, str, int, str]] = []
        parsed_selectors, parse_error = _parse_burn_selector_tokens(targets)
        if parse_error is not None:
            await _reply(ctx, embed=italy_embed("Burn", parse_error))
            return

        if not parsed_selectors:
            prepared_single = prepare_burn(_guild_id(ctx), ctx.author.id, card_code=None)
            if prepared_single.is_error:
                await _reply(ctx, embed=italy_embed("Burn", prepared_single.error_message or "Burn failed."))
                return
            if (
                prepared_single.instance_id is None
                or prepared_single.card_id is None
                or prepared_single.generation is None
                or prepared_single.dupe_code is None
            ):
                await _reply(ctx, embed=italy_embed("Burn", "Burn failed."))
                return
            resolved_targets.append((prepared_single.instance_id, prepared_single.card_id, prepared_single.generation, prepared_single.dupe_code))
        else:
            for selector_type, selector_value in parsed_selectors:
                selected_instances, selection_error = _resolve_burn_selector_instances(
                    _guild_id(ctx),
                    ctx.author.id,
                    selector_type=selector_type,
                    selector_value=selector_value,
                )
                if selection_error is not None:
                    await _reply(ctx, embed=italy_embed("Burn", selection_error))
                    return
                resolved_targets.extend(selected_instances)

        deduped_targets: list[tuple[int, str, int, str]] = []
        seen_instance_ids: set[int] = set()
        for instance_id, card_id, generation, dupe_code in resolved_targets:
            if instance_id in seen_instance_ids:
                continue
            seen_instance_ids.add(instance_id)
            deduped_targets.append((instance_id, card_id, generation, dupe_code))

        prepared = prepare_burn_batch(_guild_id(ctx), ctx.author.id, deduped_targets)
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Burn", prepared.error_message or "Burn failed."))
            return

        if not prepared.items or prepared.total_value is None or prepared.total_delta_range is None:
            await _reply(ctx, embed=italy_embed("Burn", "Burn failed."))
            return

        item_lines: list[str] = []
        for item in prepared.items:
            item_lines.append(
                f"{card_dupe_display(item.card_id, item.generation, dupe_code=item.dupe_code)}\n"
                f"Base: **{item.base_value}** | Generation: **x{item.multiplier:.2f}** | "
                f"Value: **{item.value}** | Payout: **{item.value}** +- **{item.delta_range}**"
            )

        confirm_embed = italy_embed(
            "Burn Confirmation",
            "Burn these cards?\n\n"
            + "\n\n".join(item_lines)
            + "\n\n"
            + f"Cards: **{len(prepared.items)}**\n"
            + f"Total Value: **{prepared.total_value}**\n"
            + f"Total Payout Range: **{prepared.total_value}** +- **{prepared.total_delta_range}**",
        )

        primary_item = prepared.items[0]
        view = BurnConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=primary_item.instance_id,
            card_id=primary_item.card_id,
            generation=primary_item.generation,
            delta_range=primary_item.delta_range,
            burn_items=[(item.instance_id, item.delta_range) for item in prepared.items],
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if len(prepared.items) == 1:
            image_url, image_file = embed_image_payload(
                primary_item.card_id,
                generation=primary_item.generation,
                morph_key=get_instance_morph(_guild_id(ctx), primary_item.instance_id),
                frame_key=get_instance_frame(_guild_id(ctx), primary_item.instance_id),
                font_key=get_instance_font(_guild_id(ctx), primary_item.instance_id),
            )
            if image_url is not None:
                confirm_embed.set_thumbnail(url=image_url)
            if image_file is not None:
                send_kwargs["file"] = image_file

        message = await _reply(ctx, **send_kwargs)
        view.message = message

    @bot.command(name="morph", aliases=["mo"])
    async def morph(ctx: commands.Context, card_code: str | None = None):
        if not await _require_guild(ctx, "Morph"):
            return

        prepared = prepare_morph(_guild_id(ctx), ctx.author.id, card_code)
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Morph", prepared.error_message or "Morph failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Morph", "Morph failed."))
            return

        confirm_embed = italy_embed(
            "Morph Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Current Morph: **{morph_label(prepared.current_morph_key)}**\n"
                "Roll Result: **?**\n\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )
        before_frame_key = get_instance_frame(_guild_id(ctx), prepared.instance_id)
        before_font_key = get_instance_font(_guild_id(ctx), prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=prepared.current_morph_key,
            after_morph_key=prepared.current_morph_key,
            before_frame_key=before_frame_key,
            after_frame_key=before_frame_key,
            before_font_key=before_font_key,
            after_font_key=before_font_key,
            hide_after=True,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = MorphConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=prepared.current_morph_key,
            before_frame_key=before_frame_key,
            before_font_key=before_font_key,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await _reply(ctx, **send_kwargs)
        view.message = message

    @bot.command(name="frame", aliases=["fr"])
    async def frame(ctx: commands.Context, card_code: str | None = None):
        if not await _require_guild(ctx, "Frame"):
            return

        prepared = prepare_frame(_guild_id(ctx), ctx.author.id, card_code)
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Frame", prepared.error_message or "Frame failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Frame", "Frame failed."))
            return

        confirm_embed = italy_embed(
            "Frame Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Current Frame: **{frame_label(prepared.current_frame_key)}**\n"
                "Roll Result: **?**\n\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )
        current_morph_key = get_instance_morph(_guild_id(ctx), prepared.instance_id)
        current_font_key = get_instance_font(_guild_id(ctx), prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=current_morph_key,
            after_morph_key=current_morph_key,
            before_frame_key=prepared.current_frame_key,
            after_frame_key=prepared.current_frame_key,
            before_font_key=current_font_key,
            after_font_key=current_font_key,
            hide_after=True,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = FrameConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=current_morph_key,
            before_frame_key=prepared.current_frame_key,
            before_font_key=current_font_key,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await _reply(ctx, **send_kwargs)
        view.message = message

    @bot.command(name="font", aliases=["fo"])
    async def font(ctx: commands.Context, card_code: str | None = None):
        if not await _require_guild(ctx, "Font"):
            return

        prepared = prepare_font(_guild_id(ctx), ctx.author.id, card_code)
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Font", prepared.error_message or "Font failed."))
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.dupe_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Font", "Font failed."))
            return

        confirm_embed = italy_embed(
            "Font Confirmation",
            (
                f"{card_dupe_display(prepared.card_id, prepared.generation, dupe_code=prepared.dupe_code)}\n\n"
                f"Current Font: **{font_label(prepared.current_font_key)}**\n"
                "Roll Result: **?**\n\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )
        current_morph_key = get_instance_morph(_guild_id(ctx), prepared.instance_id)
        current_frame_key = get_instance_frame(_guild_id(ctx), prepared.instance_id)
        image_url, image_file = morph_transition_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            before_morph_key=current_morph_key,
            after_morph_key=current_morph_key,
            before_frame_key=current_frame_key,
            after_frame_key=current_frame_key,
            before_font_key=prepared.current_font_key,
            after_font_key=prepared.current_font_key,
            hide_after=True,
        )
        if image_url is not None:
            confirm_embed.set_image(url=image_url)

        view = FontConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            dupe_code=prepared.dupe_code,
            before_morph_key=current_morph_key,
            before_frame_key=current_frame_key,
            before_font_key=prepared.current_font_key,
            cost=prepared.cost,
        )

        send_kwargs: dict[str, object] = {"embed": confirm_embed, "view": view}
        if image_file is not None:
            send_kwargs["file"] = image_file
        message = await _reply(ctx, **send_kwargs)
        view.message = message

    @bot.command(name="trade", aliases=["t"])
    async def trade(ctx: commands.Context, player: str, card_code: str, amount: int):
        if not await _require_guild(ctx, "Trade"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(ctx, embed=italy_embed("Trade", resolve_error or "Could not resolve player."))
            return

        prepared = prepare_trade_offer(
            guild_id=_guild_id(ctx),
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            buyer_is_bot=resolved_member.bot,
            card_code=card_code,
            amount=amount,
        )

        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Trade", prepared.error_message or "Trade failed."))
            return

        if prepared.card_id is None or prepared.generation is None or prepared.dupe_code is None:
            await _reply(ctx, embed=italy_embed("Trade", "Trade failed."))
            return

        view = TradeView(
            guild_id=_guild_id(ctx),
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            card_id=prepared.card_id,
            dupe_code=prepared.dupe_code,
            amount=amount,
        )

        message = await _reply(
            ctx,
            embed=italy_embed(
                "Trade Offer",
                trade_offer_description(
                    resolved_member.mention,
                    ctx.author.mention,
                    prepared.card_id,
                    prepared.generation,
                    prepared.dupe_code,
                    amount,
                ),
            ),
            view=view,
        )
        view.message = message

    @bot.group(name="gift", aliases=["g"], invoke_without_command=True)
    async def gift(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Gift",
                "Usage: `ns gift dough <player> <dough>` or `ns gift card <player> <card_code>`.",
            ),
        )

    @gift.command(name="dough", aliases=["d"])
    async def gift_dough(ctx: commands.Context, player: str, amount: int):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(ctx, embed=italy_embed("Gift", resolve_error or "Could not resolve player."))
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift dough to bots."))
            return

        gifted, error_message, sender_balance, recipient_balance = execute_gift_dough(
            guild_id=_guild_id(ctx),
            sender_id=ctx.author.id,
            recipient_id=resolved_member.id,
            amount=amount,
        )
        if not gifted:
            await _reply(ctx, embed=italy_embed("Gift", error_message or "Gift failed."))
            return

        await _reply(
            ctx,
            embed=italy_embed(
                "Gift",
                multiline_text(
                    [
                        f"Sent: **{amount}** dough to <@{resolved_member.id}>",
                        f"Your Balance: **{sender_balance}** dough",
                        f"{resolved_member.display_name}'s Balance: **{recipient_balance}** dough",
                    ]
                ),
            ),
        )

    @gift.command(name="card", aliases=["c"])
    async def gift_card(ctx: commands.Context, player: str, card_code: str):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(ctx, embed=italy_embed("Gift", resolve_error or "Could not resolve player."))
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift cards to bots."))
            return

        prepared = prepare_gift_offer(
            guild_id=_guild_id(ctx),
            sender_id=ctx.author.id,
            recipient_id=resolved_member.id,
            recipient_is_bot=resolved_member.bot,
            card_code=card_code,
        )
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Gift", prepared.error_message or "Gift failed."))
            return

        if prepared.card_id is None or prepared.generation is None or prepared.dupe_code is None:
            await _reply(ctx, embed=italy_embed("Gift", "Gift failed."))
            return

        gifted_instance = get_instance_by_code(_guild_id(ctx), ctx.author.id, prepared.dupe_code)
        morph_key = None
        frame_key = None
        font_key = None
        if gifted_instance is not None:
            gifted_instance_id, _gifted_card_id, _gifted_generation, _gifted_dupe_code = gifted_instance
            morph_key = get_instance_morph(_guild_id(ctx), gifted_instance_id)
            frame_key = get_instance_frame(_guild_id(ctx), gifted_instance_id)
            font_key = get_instance_font(_guild_id(ctx), gifted_instance_id)

        image_url, image_file = embed_image_payload(
            prepared.card_id,
            generation=prepared.generation,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        )

        view = GiftCardView(
            guild_id=_guild_id(ctx),
            sender_id=ctx.author.id,
            recipient_id=resolved_member.id,
            card_code=card_code,
            card_id=prepared.card_id,
            dupe_code=prepared.dupe_code,
        )

        gift_embed = italy_embed(
            "Gift Offer",
            gift_offer_description(
                f"<@{resolved_member.id}>",
                f"<@{ctx.author.id}>",
                prepared.card_id,
                prepared.generation,
                prepared.dupe_code,
            ),
        )
        if image_url is not None:
            gift_embed.set_thumbnail(url=image_url)

        send_kwargs: dict[str, object] = {
            "embed": gift_embed,
            "view": view,
        }
        if image_file is not None:
            send_kwargs["file"] = image_file

        message = await _reply(
            ctx,
            **send_kwargs,
        )
        view.message = message
