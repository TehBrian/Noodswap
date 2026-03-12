from .command_utils import (
    Awaitable as Awaitable,
    BattleProposalView as BattleProposalView,
    BurnConfirmView as BurnConfirmView,
    CARD_CATALOG as CARD_CATALOG,
    Callable as Callable,
    CardCatalogView as CardCatalogView,
    DB_PATH as DB_PATH,
    DEFAULT_CARD_RENDER_SIZE as DEFAULT_CARD_RENDER_SIZE,
    DROP_CARD_BODY_SCALE as DROP_CARD_BODY_SCALE,
    DROP_COOLDOWN_SECONDS as DROP_COOLDOWN_SECONDS,
    DROP_TIMEOUT_SECONDS as DROP_TIMEOUT_SECONDS,
    DropView as DropView,
    FLIP_ACTIVITY_PHRASES as FLIP_ACTIVITY_PHRASES,
    FLIP_COOLDOWN_SECONDS as FLIP_COOLDOWN_SECONDS,
    FLIP_REVEAL_DELAY_SECONDS as FLIP_REVEAL_DELAY_SECONDS,
    FLIP_WIN_PROBABILITY as FLIP_WIN_PROBABILITY,
    FontConfirmView as FontConfirmView,
    FrameConfirmView as FrameConfirmView,
    HD_CARD_RENDER_SIZE as HD_CARD_RENDER_SIZE,
    HelpView as HelpView,
    MONOPOLY_JAIL_FINE_DOUGH as MONOPOLY_JAIL_FINE_DOUGH,
    MONOPOLY_ROLL_COOLDOWN_SECONDS as MONOPOLY_ROLL_COOLDOWN_SECONDS,
    MorphConfirmView as MorphConfirmView,
    PULL_COOLDOWN_SECONDS as PULL_COOLDOWN_SECONDS,
    PlayerLeaderboardView as PlayerLeaderboardView,
    SLOTS_COOLDOWN_SECONDS as SLOTS_COOLDOWN_SECONDS,
    SLOTS_MAX_REWARD as SLOTS_MAX_REWARD,
    SLOTS_MIN_REWARD as SLOTS_MIN_REWARD,
    SLOTS_REEL_COUNT as SLOTS_REEL_COUNT,
    SLOTS_REEL_EMOJIS as SLOTS_REEL_EMOJIS,
    SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS as SLOTS_SPIN_FRAME_MAX_DELAY_SECONDS,
    SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS as SLOTS_SPIN_FRAME_MIN_DELAY_SECONDS,
    SLOTS_SPIN_MAX_STEPS as SLOTS_SPIN_MAX_STEPS,
    SLOTS_SPIN_MIN_STEPS as SLOTS_SPIN_MIN_STEPS,
    SortableCardListView as SortableCardListView,
    SortableCollectionView as SortableCollectionView,
    TradeView as TradeView,
    VOTE_STARTER_REWARD as VOTE_STARTER_REWARD,
    add_card_to_wishlist as add_card_to_wishlist,
    add_starter as add_starter,
    aiohttp as aiohttp,
    assign_instance_to_folder as assign_instance_to_folder,
    assign_instance_to_team as assign_instance_to_team,
    assign_tag_to_instance as assign_tag_to_instance,
    asyncio as asyncio,
    battle_offer_description as battle_offer_description,
    build_drop_preview_file as build_drop_preview_file,
    buy_drop_tickets_with_starter as buy_drop_tickets_with_starter,
    card_base_display as card_base_display,
    card_base_value as card_base_value,
    card_display as card_display,
    card_display_concise as card_display_concise,
    card_value as card_value,
    cast as cast,
    claim_vote_reward as claim_vote_reward,
    commands as commands,
    consume_slots_cooldown_if_ready as consume_slots_cooldown_if_ready,
    create_player_folder as create_player_folder,
    create_player_tag as create_player_tag,
    create_player_team as create_player_team,
    delete_player_folder as delete_player_folder,
    delete_player_tag as delete_player_tag,
    delete_player_team as delete_player_team,
    discord as discord,
    drop_choices_description as drop_choices_description,
    embed_image_payload as embed_image_payload,
    execute_divorce as execute_divorce,
    execute_flip_wager as execute_flip_wager,
    execute_gift_card as execute_gift_card,
    execute_gift_dough as execute_gift_dough,
    execute_gift_drop_tickets as execute_gift_drop_tickets,
    execute_gift_pull_tickets as execute_gift_pull_tickets,
    execute_gift_starter as execute_gift_starter,
    execute_marry as execute_marry,
    execute_monopoly_fine as execute_monopoly_fine,
    execute_monopoly_roll as execute_monopoly_roll,
    font_label as font_label,
    font_rarity as font_rarity,
    format_cooldown as format_cooldown,
    frame_label as frame_label,
    frame_rarity as frame_rarity,
    generation_value_multiplier as generation_value_multiplier,
    get_active_team_name as get_active_team_name,
    get_all_owned_card_instances as get_all_owned_card_instances,
    get_burn_candidate_by_card_id as get_burn_candidate_by_card_id,
    get_card_wish_counts as get_card_wish_counts,
    get_folder_emojis_for_instances as get_folder_emojis_for_instances,
    get_gambling_pot as get_gambling_pot,
    get_instance_by_code as get_instance_by_code,
    get_instance_by_card_code as get_instance_by_card_code,
    get_instance_by_id as get_instance_by_id,
    get_instance_font as get_instance_font,
    get_instance_frame as get_instance_frame,
    get_instance_morph as get_instance_morph,
    get_instances_by_folder as get_instances_by_folder,
    get_instances_by_tag as get_instances_by_tag,
    get_instances_by_team as get_instances_by_team,
    get_locked_instance_ids as get_locked_instance_ids,
    get_monopoly_board_state as get_monopoly_board_state,
    get_monopoly_state as get_monopoly_state,
    get_player_card_instances as get_player_card_instances,
    get_player_cooldown_timestamps as get_player_cooldown_timestamps,
    get_player_drop_tickets as get_player_drop_tickets,
    get_player_flip_timestamp as get_player_flip_timestamp,
    get_player_info as get_player_info,
    get_player_leaderboard_info as get_player_leaderboard_info,
    get_player_slots_timestamp as get_player_slots_timestamp,
    get_player_starter as get_player_starter,
    get_total_cards as get_total_cards,
    get_wishlist_cards as get_wishlist_cards,
    io as io,
    is_instance_assigned_to_folder as is_instance_assigned_to_folder,
    is_instance_assigned_to_team as is_instance_assigned_to_team,
    is_tag_assigned_to_instance as is_tag_assigned_to_instance,
    italy_embed as italy_embed,
    italy_marry_embed as italy_marry_embed,
    list_player_folders as list_player_folders,
    list_player_tags as list_player_tags,
    list_player_teams as list_player_teams,
    morph_label as morph_label,
    morph_rarity as morph_rarity,
    multiline_text as multiline_text,
    normalize_card_id as normalize_card_id,
    normalize_trade_mode as normalize_trade_mode,
    os as os,
    prepare_battle_offer as prepare_battle_offer,
    prepare_burn as prepare_burn,
    prepare_burn_batch as prepare_burn_batch,
    prepare_drop as prepare_drop,
    prepare_font as prepare_font,
    prepare_frame as prepare_frame,
    prepare_morph as prepare_morph,
    prepare_trade_offer as prepare_trade_offer,
    random as random,
    read_local_card_image_bytes as read_local_card_image_bytes,
    remove_card_from_wishlist as remove_card_from_wishlist,
    render_card_surface as render_card_surface,
    reset_db_data as reset_db_data,
    resolve_member_argument as resolve_member_argument,
    resolve_optional_player_argument as resolve_optional_player_argument,
    search_card_ids as search_card_ids,
    search_card_ids_by_name as search_card_ids_by_name,
    set_active_team as set_active_team,
    set_player_folder_emoji as set_player_folder_emoji,
    set_player_folder_locked as set_player_folder_locked,
    set_player_tag_locked as set_player_tag_locked,
    time as time,
    trade_offer_description as trade_offer_description,
    trait_rarity_multiplier as trait_rarity_multiplier,
    trait_value_multiplier as trait_value_multiplier,
    unassign_instance_from_folder as unassign_instance_from_folder,
    unassign_instance_from_team as unassign_instance_from_team,
    unassign_tag_from_instance as unassign_tag_from_instance,
    value_to_stats as value_to_stats,
    _folder_emoji_map_for_instances as _folder_emoji_map_for_instances,
    _guild_id as _guild_id,
    _parse_burn_selector_tokens as _parse_burn_selector_tokens,
    _reply as _reply,
    _require_guild as _require_guild,
    _resolve_burn_selector_instances as _resolve_burn_selector_instances,
)  # noqa: F403


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
            await _reply(
                ctx,
                embed=italy_marry_embed("Marry", result.error_message or "Marry failed."),
            )
            return

        if result.card_id is None or result.generation is None:
            await _reply(ctx, embed=italy_marry_embed("Marry", "Marry failed."))
            return

        morph_key = None
        frame_key = None
        font_key = None
        if result.card_code is not None:
            married_instance = get_instance_by_code(_guild_id(ctx), ctx.author.id, result.card_code)
            if married_instance is not None:
                married_instance_id, _, _, _ = married_instance
                morph_key = get_instance_morph(_guild_id(ctx), married_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), married_instance_id)
                font_key = get_instance_font(_guild_id(ctx), married_instance_id)

        marry_embed = italy_marry_embed(
            "Marry",
            f"You are now married to {card_display(result.card_id, result.generation, card_code=result.card_code, morph_key=morph_key, frame_key=frame_key, font_key=font_key)}.",
        )

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
            await _reply(
                ctx,
                embed=italy_marry_embed("Divorce", result.error_message or "Divorce failed."),
            )
            return

        if result.card_id is None or result.generation is None:
            await _reply(ctx, embed=italy_marry_embed("Divorce", "Divorce failed."))
            return

        morph_key = None
        frame_key = None
        font_key = None
        if result.card_code is not None:
            divorced_instance = get_instance_by_code(_guild_id(ctx), ctx.author.id, result.card_code)
            if divorced_instance is not None:
                divorced_instance_id, _, _, _ = divorced_instance
                morph_key = get_instance_morph(_guild_id(ctx), divorced_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), divorced_instance_id)
                font_key = get_instance_font(_guild_id(ctx), divorced_instance_id)

        divorce_embed = italy_marry_embed(
            "Divorce",
            f"You divorced {card_display(result.card_id, result.generation, card_code=result.card_code, morph_key=morph_key, frame_key=frame_key, font_key=font_key)}.",
        )

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
            await _reply(
                ctx,
                embed=italy_embed("Collection", resolve_error or "Could not resolve player."),
            )
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
                [instance_id for instance_id, _card_id, _generation, _card_code in instances],
            ),
            wish_counts=get_card_wish_counts(_guild_id(ctx)),
            folder_emojis_by_instance=_folder_emoji_map_for_instances(_guild_id(ctx), target_member.id, instances),
            instance_styles={
                instance_id: (
                    get_instance_morph(_guild_id(ctx), instance_id),
                    get_instance_frame(_guild_id(ctx), instance_id),
                    get_instance_font(_guild_id(ctx), instance_id),
                )
                for instance_id, _card_id, _generation, _card_code in instances
            },
            card_line_formatter=card_display_concise,
            guard_title="Collection",
        )
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="cards", aliases=["ca"])
    async def cards(ctx: commands.Context):
        if not await _require_guild(ctx, "Cards"):
            return

        guild_id = _guild_id(ctx)
        instance_rows = get_all_owned_card_instances(guild_id)
        title = "All Cards"
        if not instance_rows:
            await _reply(ctx, embed=italy_embed(title, "No cards have been claimed yet. Try `ns drop`."))
            return

        instances = [
            (instance_id, card_id, generation, card_code)
            for instance_id, _owner_id, card_id, generation, card_code, _morph_key, _frame_key, _font_key in instance_rows
        ]
        instance_styles = {
            instance_id: (morph_key, frame_key, font_key)
            for instance_id, _owner_id, _card_id, _generation, _card_code, morph_key, frame_key, font_key in instance_rows
        }
        owner_labels_by_instance: dict[int, str] = {}
        instance_ids_by_owner: dict[int, list[int]] = {}
        for instance_id, owner_id, _card_id, _generation, _card_code, _morph_key, _frame_key, _font_key in instance_rows:
            member = ctx.guild.get_member(owner_id)
            owner_labels_by_instance[instance_id] = member.display_name if member is not None else f"User {owner_id}"
            instance_ids_by_owner.setdefault(owner_id, []).append(instance_id)

        locked_instance_ids: set[int] = set()
        folder_emojis_by_instance: dict[int, str] = {}
        for owner_id, owner_instance_ids in instance_ids_by_owner.items():
            locked_instance_ids |= get_locked_instance_ids(guild_id, owner_id, owner_instance_ids)
            folder_emojis_by_instance.update(get_folder_emojis_for_instances(guild_id, owner_id, owner_instance_ids))

        def _format_global_card_line(
            card_id: str,
            generation: int,
            card_code: str | None,
            *,
            instance_id: int | None = None,
            morph_key: str | None = None,
            frame_key: str | None = None,
            font_key: str | None = None,
        ) -> str:
            owner_text = owner_labels_by_instance.get(instance_id or -1, "Unknown")
            return (
                f"{card_display_concise(card_id, generation, card_code, morph_key=morph_key, frame_key=frame_key, font_key=font_key)}"
                f" • Owner: {owner_text}"
            )

        view = SortableCollectionView(
            user_id=ctx.author.id,
            title=title,
            instances=instances,
            wish_counts=get_card_wish_counts(_guild_id(ctx)),
            instance_styles=instance_styles,
            locked_instance_ids=locked_instance_ids,
            folder_emojis_by_instance=folder_emojis_by_instance,
            card_line_formatter=_format_global_card_line,
            guard_title="Cards",
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
                await _reply(
                    ctx,
                    embed=italy_embed("Burn", prepared_single.error_message or "Burn failed."),
                )
                return
            if (
                prepared_single.instance_id is None
                or prepared_single.card_id is None
                or prepared_single.generation is None
                or prepared_single.card_code is None
            ):
                await _reply(ctx, embed=italy_embed("Burn", "Burn failed."))
                return
            resolved_targets.append(
                (
                    prepared_single.instance_id,
                    prepared_single.card_id,
                    prepared_single.generation,
                    prepared_single.card_code,
                )
            )
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
        for instance_id, card_id, generation, card_code in resolved_targets:
            if instance_id in seen_instance_ids:
                continue
            seen_instance_ids.add(instance_id)
            deduped_targets.append((instance_id, card_id, generation, card_code))

        prepared = prepare_burn_batch(_guild_id(ctx), ctx.author.id, deduped_targets)
        if prepared.is_error:
            await _reply(ctx, embed=italy_embed("Burn", prepared.error_message or "Burn failed."))
            return

        if not prepared.items or prepared.total_value is None or prepared.total_delta_range is None:
            await _reply(ctx, embed=italy_embed("Burn", "Burn failed."))
            return

        item_lines: list[str] = []
        for item in prepared.items:
            item_morph_key = get_instance_morph(_guild_id(ctx), item.instance_id)
            item_frame_key = get_instance_frame(_guild_id(ctx), item.instance_id)
            item_font_key = get_instance_font(_guild_id(ctx), item.instance_id)
            item_lines.append(
                f"{card_display(item.card_id, item.generation, card_code=item.card_code, morph_key=item_morph_key, frame_key=item_frame_key, font_key=item_font_key)}\n"
                f"Base: **{item.base_value}** | Generation: **x{item.multiplier:.2f}** | "
                f"Value: **{item.value}** | Payout: **{item.value}** ± **{item.delta_range}**"
            )

        single = len(prepared.items) == 1
        summary = (
            ""
            if single
            else (
                "\n\n"
                + f"Cards: **{len(prepared.items)}**\n"
                + f"Total Value: **{prepared.total_value}**\n"
                + f"Total Payout Range: **{prepared.total_value}** ± **{prepared.total_delta_range}**"
            )
        )
        confirm_embed = italy_embed(
            "Burn Confirmation",
            ("Burn this card?" if single else "Burn these cards?") + "\n\n" + "\n\n".join(item_lines) + summary,
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
            await _reply(
                ctx,
                embed=italy_embed("Morph", prepared.error_message or "Morph failed."),
            )
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.card_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Morph", "Morph failed."))
            return

        before_frame_key = get_instance_frame(_guild_id(ctx), prepared.instance_id)
        before_font_key = get_instance_font(_guild_id(ctx), prepared.instance_id)

        confirm_embed = italy_embed(
            "Morph Confirmation",
            (
                f"{card_display(prepared.card_id, prepared.generation, card_code=prepared.card_code, morph_key=prepared.current_morph_key, frame_key=before_frame_key, font_key=before_font_key)}\n\n"
                f"Current Morph: **{morph_label(prepared.current_morph_key)}**\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )

        view = MorphConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            card_code=prepared.card_code,
            before_morph_key=prepared.current_morph_key,
            before_frame_key=before_frame_key,
            before_font_key=before_font_key,
            cost=prepared.cost,
        )

        message = await _reply(ctx, embed=confirm_embed, view=view)
        view.message = message

    @bot.command(name="frame", aliases=["fr"])
    async def frame(ctx: commands.Context, card_code: str | None = None):
        if not await _require_guild(ctx, "Frame"):
            return

        prepared = prepare_frame(_guild_id(ctx), ctx.author.id, card_code)
        if prepared.is_error:
            await _reply(
                ctx,
                embed=italy_embed("Frame", prepared.error_message or "Frame failed."),
            )
            return

        if (
            prepared.instance_id is None
            or prepared.card_id is None
            or prepared.generation is None
            or prepared.card_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Frame", "Frame failed."))
            return

        current_morph_key = get_instance_morph(_guild_id(ctx), prepared.instance_id)
        current_font_key = get_instance_font(_guild_id(ctx), prepared.instance_id)

        confirm_embed = italy_embed(
            "Frame Confirmation",
            (
                f"{card_display(prepared.card_id, prepared.generation, card_code=prepared.card_code, morph_key=current_morph_key, frame_key=prepared.current_frame_key, font_key=current_font_key)}\n\n"
                f"Current Frame: **{frame_label(prepared.current_frame_key)}**\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )

        view = FrameConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            card_code=prepared.card_code,
            before_morph_key=current_morph_key,
            before_frame_key=prepared.current_frame_key,
            before_font_key=current_font_key,
            cost=prepared.cost,
        )

        message = await _reply(ctx, embed=confirm_embed, view=view)
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
            or prepared.card_code is None
            or prepared.cost is None
        ):
            await _reply(ctx, embed=italy_embed("Font", "Font failed."))
            return

        current_morph_key = get_instance_morph(_guild_id(ctx), prepared.instance_id)
        current_frame_key = get_instance_frame(_guild_id(ctx), prepared.instance_id)

        confirm_embed = italy_embed(
            "Font Confirmation",
            (
                f"{card_display(prepared.card_id, prepared.generation, card_code=prepared.card_code, morph_key=current_morph_key, frame_key=current_frame_key, font_key=prepared.current_font_key)}\n\n"
                f"Current Font: **{font_label(prepared.current_font_key)}**\n"
                f"Roll Cost: **{prepared.cost}** dough"
            ),
        )

        view = FontConfirmView(
            guild_id=_guild_id(ctx),
            user_id=ctx.author.id,
            instance_id=prepared.instance_id,
            card_id=prepared.card_id,
            generation=prepared.generation,
            card_code=prepared.card_code,
            before_morph_key=current_morph_key,
            before_frame_key=current_frame_key,
            before_font_key=prepared.current_font_key,
            cost=prepared.cost,
        )

        message = await _reply(ctx, embed=confirm_embed, view=view)
        view.message = message

    @bot.command(name="trade", aliases=["t"])
    async def trade(ctx: commands.Context, player: str, card_code: str, mode: str, value: str):
        if not await _require_guild(ctx, "Trade"):
            return

        canonical_mode = normalize_trade_mode(mode)
        if canonical_mode is None:
            await _reply(
                ctx,
                embed=italy_embed(
                    "Trade",
                    f"Unknown trade mode `{mode}`. Use `dough`, `starter`, `drop`, `pull`, or `card`.",
                ),
            )
            return

        amount: int | None = None
        req_card_code: str | None = None
        if canonical_mode == "card":
            req_card_code = value
        else:
            try:
                amount = int(value)
            except ValueError:
                await _reply(
                    ctx,
                    embed=italy_embed(
                        "Trade",
                        f"Expected a whole number for `{canonical_mode}` amount, got `{value}`.",
                    ),
                )
                return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Trade", resolve_error or "Could not resolve player."),
            )
            return

        prepared = prepare_trade_offer(
            guild_id=_guild_id(ctx),
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            buyer_is_bot=resolved_member.bot,
            card_code=card_code,
            mode=canonical_mode,
            amount=amount,
            req_card_code=req_card_code,
        )

        if prepared.is_error:
            await _reply(
                ctx,
                embed=italy_embed("Trade", prepared.error_message or "Trade failed."),
            )
            return

        if prepared.card_id is None or prepared.generation is None or prepared.card_code is None or prepared.terms is None:
            await _reply(ctx, embed=italy_embed("Trade", "Trade failed."))
            return

        view = TradeView(
            guild_id=_guild_id(ctx),
            seller_id=ctx.author.id,
            buyer_id=resolved_member.id,
            card_id=prepared.card_id,
            card_code=prepared.card_code,
            terms=prepared.terms,
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
                    prepared.card_code,
                    prepared.terms,
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
                (
                    "Usage: `ns gift dough <player> <dough>`, "
                    "`ns gift starter <player> <starter>`, "
                    "`ns gift drop <player> <tickets>`, "
                    "`ns gift pull <player> <tickets>`, "
                    "or `ns gift card <player> <card_code>`."
                ),
            ),
        )

    @gift.command(name="dough", aliases=["d"])
    async def gift_dough(ctx: commands.Context, player: str, amount: int):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Gift", resolve_error or "Could not resolve player."),
            )
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

    @gift.command(name="starter", aliases=["s"])
    async def gift_starter(ctx: commands.Context, player: str, amount: int):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Gift", resolve_error or "Could not resolve player."),
            )
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift starter to bots."))
            return

        gifted, error_message, sender_balance, recipient_balance = execute_gift_starter(
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
                        f"Sent: **{amount}** starter to <@{resolved_member.id}>",
                        f"Your Starter: **{sender_balance}**",
                        f"{resolved_member.display_name}'s Starter: **{recipient_balance}**",
                    ]
                ),
            ),
        )

    @gift.command(name="drop")
    async def gift_drop(ctx: commands.Context, player: str, amount: int):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Gift", resolve_error or "Could not resolve player."),
            )
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift drop tickets to bots."))
            return

        gifted, error_message, sender_balance, recipient_balance = execute_gift_drop_tickets(
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
                        f"Sent: **{amount}** drop tickets to <@{resolved_member.id}>",
                        f"Your Drop Tickets: **{sender_balance}**",
                        f"{resolved_member.display_name}'s Drop Tickets: **{recipient_balance}**",
                    ]
                ),
            ),
        )

    @gift.command(name="pull")
    async def gift_pull(ctx: commands.Context, player: str, amount: int):
        if not await _require_guild(ctx, "Gift"):
            return

        resolved_member, resolve_error = await resolve_member_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Gift", resolve_error or "Could not resolve player."),
            )
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift pull tickets to bots."))
            return

        gifted, error_message, sender_balance, recipient_balance = execute_gift_pull_tickets(
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
                        f"Sent: **{amount}** pull tickets to <@{resolved_member.id}>",
                        f"Your Pull Tickets: **{sender_balance}**",
                        f"{resolved_member.display_name}'s Pull Tickets: **{recipient_balance}**",
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
            await _reply(
                ctx,
                embed=italy_embed("Gift", resolve_error or "Could not resolve player."),
            )
            return

        if resolved_member.bot:
            await _reply(ctx, embed=italy_embed("Gift", "You cannot gift cards to bots."))
            return

        gifted, error_message, card_id, generation, card_code = execute_gift_card(
            guild_id=_guild_id(ctx),
            sender_id=ctx.author.id,
            recipient_id=resolved_member.id,
            card_code=card_code,
        )
        if not gifted:
            await _reply(ctx, embed=italy_embed("Gift", error_message or "Gift failed."))
            return

        if card_id is None or generation is None:
            await _reply(ctx, embed=italy_embed("Gift", "Gift failed."))
            return

        gifted_instance = None
        if card_code is not None:
            gifted_instance = get_instance_by_code(_guild_id(ctx), resolved_member.id, card_code)
        morph_key = None
        frame_key = None
        font_key = None
        if gifted_instance is not None:
            (
                gifted_instance_id,
                _gifted_card_id,
                _gifted_generation,
                _gifted_card_code,
            ) = gifted_instance
            morph_key = get_instance_morph(_guild_id(ctx), gifted_instance_id)
            frame_key = get_instance_frame(_guild_id(ctx), gifted_instance_id)
            font_key = get_instance_font(_guild_id(ctx), gifted_instance_id)

        gifted_card_text = card_base_display(card_id)
        if card_code is not None:
            gifted_card_text = card_display(
                card_id,
                generation,
                card_code=card_code,
                morph_key=morph_key,
                frame_key=frame_key,
                font_key=font_key,
            )

        image_url, image_file = embed_image_payload(
            card_id,
            generation=generation,
            morph_key=morph_key,
            frame_key=frame_key,
            font_key=font_key,
        )

        gift_embed = italy_embed(
            "Gift",
            multiline_text(
                [
                    f"Sent to: <@{resolved_member.id}>",
                    f"Sender: <@{ctx.author.id}>",
                    "",
                    f"Card: {gifted_card_text}",
                ]
            ),
        )
        if image_url is not None:
            gift_embed.set_thumbnail(url=image_url)

        send_kwargs: dict[str, object] = {"embed": gift_embed}
        if image_file is not None:
            send_kwargs["file"] = image_file

        await _reply(ctx, **send_kwargs)
