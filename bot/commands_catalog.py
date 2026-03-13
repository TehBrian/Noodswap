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
    buy_pull_tickets_with_starter as buy_pull_tickets_with_starter,
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
    get_burn_candidate_by_card_id as get_burn_candidate_by_card_id,
    get_card_wish_counts as get_card_wish_counts,
    get_folder_emojis_for_instances as get_folder_emojis_for_instances,
    get_gambling_pot as get_gambling_pot,
    get_instance_by_code as get_instance_by_code,
    get_instance_by_card_id as get_instance_by_card_id,
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
    morph_transition_image_payload as morph_transition_image_payload,
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
    _guild_id as _guild_id,
    _lookup_trait_breakdown_description as _lookup_trait_breakdown_description,
    _reply as _reply,
    _require_guild as _require_guild,
    _vote_link_view as _vote_link_view,
)  # noqa: F403


def register_catalog_commands(bot: commands.Bot) -> None:
    @bot.group(name="buy", invoke_without_command=True)
    async def buy(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Buy",
                "Usage: `ns buy drop [quantity]` or `ns buy pull [quantity]` (1 starter per ticket).",
            ),
        )

    @buy.command(name="drop")
    async def buy_drop(ctx: commands.Context, quantity: int = 1):
        if not await _require_guild(ctx, "Buy"):
            return

        if quantity <= 0:
            await _reply(ctx, embed=italy_embed("Buy", "Quantity must be a positive integer."))
            return

        purchased, starter_balance, drop_tickets, spent = buy_drop_tickets_with_starter(_guild_id(ctx), ctx.author.id, quantity)
        if not purchased:
            await _reply(
                ctx,
                embed=italy_embed(
                    "Buy",
                    multiline_text(
                        [
                            f"Cost: **{quantity} starter**",
                            f"Starter Balance: **{starter_balance}**",
                            "You do not have enough starter.",
                        ]
                    ),
                ),
            )
            return

        await _reply(
            ctx,
            embed=italy_embed(
                "Buy",
                multiline_text(
                    [
                        f"Purchased: **{spent} drop ticket{"s" if spent != 1 else ''}**",
                        f"Cost: **{spent} starter**",
                        "",
                        f"Starter: **{starter_balance}**",
                        f"Drop Tickets: **{drop_tickets}**",
                    ]
                ),
            ),
        )

    @buy.command(name="pull")
    async def buy_pull(ctx: commands.Context, quantity: int = 1):
        if not await _require_guild(ctx, "Buy"):
            return

        if quantity <= 0:
            await _reply(ctx, embed=italy_embed("Buy", "Quantity must be a positive integer."))
            return

        purchased, starter_balance, pull_tickets, spent = buy_pull_tickets_with_starter(_guild_id(ctx), ctx.author.id, quantity)
        if not purchased:
            await _reply(
                ctx,
                embed=italy_embed(
                    "Buy",
                    multiline_text(
                        [
                            f"Cost: **{quantity} starter**",
                            f"Starter Balance: **{starter_balance}**",
                            "You do not have enough starter.",
                        ]
                    ),
                ),
            )
            return

        await _reply(
            ctx,
            embed=italy_embed(
                "Buy",
                multiline_text(
                    [
                        f"Purchased: **{spent} pull ticket{"s" if spent != 1 else ''}**",
                        f"Spent: **{spent} starter**",
                        "",
                        f"Starter: **{starter_balance}**",
                        f"Pull Tickets: **{pull_tickets}**",
                    ]
                ),
            ),
        )

    @bot.command(name="types", aliases=["ty"])
    async def types(ctx: commands.Context):
        if not await _require_guild(ctx, "All Card Types"):
            return

        wish_counts = get_card_wish_counts(_guild_id(ctx))
        entries = [(card_type_id, wish_counts.get(card_type_id, 0)) for card_type_id in CARD_CATALOG]

        view = CardCatalogView(user_id=ctx.author.id, entries=entries)
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    async def _run_lookup(
        ctx: commands.Context,
        *,
        card_type_id: str | None,
        image_size: tuple[int, int],
        embed_title: str,
        usage_name: str,
    ) -> None:
        if card_type_id is None:
            await _reply(
                ctx,
                embed=italy_embed("Lookup", f"Usage: `ns {usage_name} <card_type_id|card_id|query>`."),
            )
            return

        if ctx.guild is not None:
            matched_instance = get_instance_by_card_id(_guild_id(ctx), card_type_id)
            if matched_instance is not None:
                (
                    matched_instance_id,
                    matched_owner_id,
                    matched_card_type_id,
                    matched_generation,
                    matched_card_id,
                    matched_dropped_by_id,
                    matched_pulled_by_id,
                    matched_pulled_at,
                ) = matched_instance
                morph_key = get_instance_morph(_guild_id(ctx), matched_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), matched_instance_id)
                font_key = get_instance_font(_guild_id(ctx), matched_instance_id)
                lookup_embed = italy_embed(
                    embed_title,
                    _lookup_trait_breakdown_description(
                        matched_card_type_id,
                        matched_generation,
                        matched_card_id,
                        owner_mention=f"<@{matched_owner_id}>",
                        dropped_by_mention=(f"<@{matched_dropped_by_id}>" if matched_dropped_by_id is not None else None),
                        pulled_by_mention=(f"<@{matched_pulled_by_id}>" if matched_pulled_by_id is not None else None),
                        pulled_at=matched_pulled_at,
                        morph_key=morph_key,
                        frame_key=frame_key,
                        font_key=font_key,
                    ),
                )
                image_url, image_file = embed_image_payload(
                    matched_card_type_id,
                    generation=matched_generation,
                    morph_key=morph_key,
                    frame_key=frame_key,
                    font_key=font_key,
                    size=image_size,
                )
                if image_url is not None:
                    lookup_embed.set_image(url=image_url)
                send_kwargs: dict[str, object] = {"embed": lookup_embed}
                if image_file is not None:
                    send_kwargs["file"] = image_file
                await _reply(ctx, **send_kwargs)
                return

        normalized_card_id = normalize_card_id(card_type_id)
        if normalized_card_id in CARD_CATALOG:
            lookup_embed = italy_embed(embed_title, card_base_display(normalized_card_id))
            image_url, image_file = embed_image_payload(normalized_card_id, size=image_size)
            if image_url is not None:
                lookup_embed.set_image(url=image_url)
            send_kwargs: dict[str, object] = {"embed": lookup_embed}
            if image_file is not None:
                send_kwargs["file"] = image_file
            await _reply(ctx, **send_kwargs)
            return

        name_matches = search_card_ids(card_type_id, include_series=True)
        if not name_matches:
            await _reply(ctx, embed=italy_embed("Lookup", "No results found."))
            return

        if len(name_matches) == 1:
            matched_card_type_id = name_matches[0]
            lookup_embed = italy_embed(embed_title, card_base_display(matched_card_type_id))
            image_url, image_file = embed_image_payload(matched_card_type_id, size=image_size)
            if image_url is not None:
                lookup_embed.set_image(url=image_url)
            send_kwargs: dict[str, object] = {"embed": lookup_embed}
            if image_file is not None:
                send_kwargs["file"] = image_file
            await _reply(ctx, **send_kwargs)
            return

        lookup_wish_counts = get_card_wish_counts(_guild_id(ctx)) if ctx.guild is not None else {}
        view = SortableCardListView(
            user_id=ctx.author.id,
            title="Lookup Matches",
            card_ids=name_matches,
            wish_counts=lookup_wish_counts,
            guard_title="Lookup",
        )
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="lookup", aliases=["l"])
    async def lookup(ctx: commands.Context, *, card_type_id: str | None = None):
        await _run_lookup(
            ctx,
            card_type_id=card_type_id,
            image_size=DEFAULT_CARD_RENDER_SIZE,
            embed_title="Card Lookup",
            usage_name="lookup",
        )

    @bot.command(name="lookuphd", aliases=["lhd"])
    async def lookup_hd(ctx: commands.Context, *, card_type_id: str | None = None):
        await _run_lookup(
            ctx,
            card_type_id=card_type_id,
            image_size=HD_CARD_RENDER_SIZE,
            embed_title="Card Lookup (HD)",
            usage_name="lookuphd",
        )

    @bot.command(name="vote", aliases=["v"])
    async def vote(ctx: commands.Context):
        if not await _require_guild(ctx, "Vote"):
            return

        bot_user = bot.user
        bot_id = bot_user.id if bot_user is not None else None
        if bot_id is None:
            env_bot_id = os.getenv("TOPGG_BOT_ID", "").strip()
            if env_bot_id.isdigit():
                bot_id = int(env_bot_id)

        vote_url = "https://top.gg/"
        if bot_id is not None:
            vote_url = f"https://top.gg/bot/{bot_id}/vote"

        lines: list[str] = [
            "Support Noodswap by voting on Top.gg!",
            f"Reward: **+{VOTE_STARTER_REWARD} starter**",
        ]

        await _reply(
            ctx,
            embed=italy_embed("Vote", multiline_text(lines)),
            view=_vote_link_view(vote_url),
        )

    @bot.command(name="help", aliases=["h"])
    async def help_command(ctx: commands.Context):
        view = HelpView(user_id=ctx.author.id)
        message = await _reply(ctx, embed=view.build_overview_embed(), view=view)
        view.message = message
