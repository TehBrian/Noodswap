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
    get_player_pull_tickets as get_player_pull_tickets,
    get_player_drop_tickets as get_player_drop_tickets,
    get_player_flip_timestamp as get_player_flip_timestamp,
    get_player_info as get_player_info,
    get_player_leaderboard_info as get_player_leaderboard_info,
    get_player_oven_balances as get_player_oven_balances,
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
    _battle as _battle,
    _cooldown_status_line as _cooldown_status_line,
    _folder_add as _folder_add,
    _folder_assign as _folder_assign,
    _folder_cards as _folder_cards,
    _folder_emoji as _folder_emoji,
    _folder_list as _folder_list,
    _folder_lock as _folder_lock,
    _folder_remove as _folder_remove,
    _folder_unassign as _folder_unassign,
    _guild_id as _guild_id,
    _reply as _reply,
    _require_guild as _require_guild,
    _tag_add as _tag_add,
    _tag_assign as _tag_assign,
    _tag_cards as _tag_cards,
    _tag_list as _tag_list,
    _tag_lock as _tag_lock,
    _tag_remove as _tag_remove,
    _tag_unassign as _tag_unassign,
    _team_active as _team_active,
    _team_add as _team_add,
    _team_assign as _team_assign,
    _team_cards as _team_cards,
    _team_list as _team_list,
    _team_remove as _team_remove,
    _team_unassign as _team_unassign,
    _wish_add as _wish_add,
    _wish_list as _wish_list,
    _wish_remove as _wish_remove,
)  # noqa: F403


def register_social_commands(bot: commands.Bot) -> None:
    @bot.group(name="wish", aliases=["w"], invoke_without_command=True)
    async def wish(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Wishlist",
                "Usage: `ns wish add <card_type_id> [id ...]`, `ns wish remove <card_type_id> [id ...]`, or `ns wish list [player]`.",
            ),
        )

    @wish.command(name="add", aliases=["a"])
    async def wish_add(ctx: commands.Context, *card_ids: str):
        await _wish_add(ctx, *card_ids)

    @wish.command(name="remove", aliases=["r"])
    async def wish_remove(ctx: commands.Context, *card_ids: str):
        await _wish_remove(ctx, *card_ids)

    @wish.command(name="list", aliases=["l"])
    async def wish_list(ctx: commands.Context, *, player: str | None = None):
        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."),
            )
            return
        await _wish_list(ctx, resolved_member)

    @bot.command(name="wa")
    async def wish_add_short(ctx: commands.Context, *card_ids: str):
        await _wish_add(ctx, *card_ids)

    @bot.command(name="wr")
    async def wish_remove_short(ctx: commands.Context, *card_ids: str):
        await _wish_remove(ctx, *card_ids)

    @bot.command(name="wl")
    async def wish_list_short(ctx: commands.Context, *, player: str | None = None):
        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."),
            )
            return
        await _wish_list(ctx, resolved_member)

    @bot.group(name="tag", aliases=["tg"], invoke_without_command=True)
    async def tag(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Tags",
                (
                    "Usage: `ns tag add <tag_name>`, `ns tag remove <tag_name>`, `ns tag list`, "
                    "`ns tag lock <tag_name>`, `ns tag unlock <tag_name>`, "
                    "`ns tag assign <tag_name> <card_id> [code ...]`, `ns tag unassign <tag_name> <card_id> [code ...]`, "
                    "`ns tag cards <tag_name>`."
                ),
            ),
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
    async def tag_assign(ctx: commands.Context, tag_name: str, *card_ids: str):
        await _tag_assign(ctx, tag_name, *card_ids)

    @tag.command(name="unassign", aliases=["u"])
    async def tag_unassign(ctx: commands.Context, tag_name: str, *card_ids: str):
        await _tag_unassign(ctx, tag_name, *card_ids)

    @tag.command(name="cards", aliases=["c"])
    async def tag_cards(ctx: commands.Context, tag_name: str):
        await _tag_cards(ctx, tag_name)

    @bot.group(name="folder", aliases=["fd"], invoke_without_command=True)
    async def folder(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Folders",
                (
                    "Usage: `ns folder add <folder_name> [emoji]`, `ns folder remove <folder_name>`, "
                    "`ns folder list`, `ns folder lock <folder_name>`, `ns folder unlock <folder_name>`, "
                    "`ns folder assign <folder_name> <card_id> [code ...]`, `ns folder unassign <folder_name> <card_id> [code ...]`, "
                    "`ns folder cards <folder_name>`, `ns folder emoji <folder_name> <emoji>`."
                ),
            ),
        )

    @folder.command(name="add", aliases=["a", "create"])
    async def folder_add(ctx: commands.Context, folder_name: str, emoji: str | None = None):
        await _folder_add(ctx, folder_name, emoji)

    @folder.command(name="remove", aliases=["r", "delete"])
    async def folder_remove(ctx: commands.Context, folder_name: str):
        await _folder_remove(ctx, folder_name)

    @folder.command(name="list", aliases=["l"])
    async def folder_list(ctx: commands.Context):
        await _folder_list(ctx)

    @folder.command(name="lock")
    async def folder_lock(ctx: commands.Context, folder_name: str):
        await _folder_lock(ctx, folder_name, True)

    @folder.command(name="unlock")
    async def folder_unlock(ctx: commands.Context, folder_name: str):
        await _folder_lock(ctx, folder_name, False)

    @folder.command(name="assign", aliases=["as"])
    async def folder_assign(ctx: commands.Context, folder_name: str, *card_ids: str):
        await _folder_assign(ctx, folder_name, *card_ids)

    @folder.command(name="unassign", aliases=["u"])
    async def folder_unassign(ctx: commands.Context, folder_name: str, *card_ids: str):
        await _folder_unassign(ctx, folder_name, *card_ids)

    @folder.command(name="cards", aliases=["c"])
    async def folder_cards(ctx: commands.Context, folder_name: str):
        await _folder_cards(ctx, folder_name)

    @folder.command(name="emoji", aliases=["e"])
    async def folder_emoji(ctx: commands.Context, folder_name: str, emoji: str):
        await _folder_emoji(ctx, folder_name, emoji)

    @bot.group(name="team", aliases=["tm"], invoke_without_command=True)
    async def team(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Teams",
                (
                    "Usage: `ns team add <team_name>`, `ns team remove <team_name>`, `ns team list`, "
                    "`ns team assign <team_name> <card_id> [code ...]`, `ns team unassign <team_name> <card_id> [code ...]`, "
                    "`ns team cards <team_name>`, `ns team active [team_name]`."
                ),
            ),
        )

    @team.command(name="add", aliases=["a", "create"])
    async def team_add(ctx: commands.Context, team_name: str):
        await _team_add(ctx, team_name)

    @team.command(name="remove", aliases=["r", "delete"])
    async def team_remove(ctx: commands.Context, team_name: str):
        await _team_remove(ctx, team_name)

    @team.command(name="list", aliases=["l"])
    async def team_list(ctx: commands.Context):
        await _team_list(ctx)

    @team.command(name="assign", aliases=["as"])
    async def team_assign(ctx: commands.Context, team_name: str, *card_ids: str):
        await _team_assign(ctx, team_name, *card_ids)

    @team.command(name="unassign", aliases=["u"])
    async def team_unassign(ctx: commands.Context, team_name: str, *card_ids: str):
        await _team_unassign(ctx, team_name, *card_ids)

    @team.command(name="cards", aliases=["c"])
    async def team_cards(ctx: commands.Context, team_name: str):
        await _team_cards(ctx, team_name)

    @team.command(name="active")
    async def team_active(ctx: commands.Context, team_name: str | None = None):
        await _team_active(ctx, team_name)

    @bot.command(name="battle", aliases=["bt"])
    async def battle(ctx: commands.Context, player: str, stake: int):
        await _battle(ctx, player, stake)

    @bot.command(name="cooldown", aliases=["cd"])
    async def cooldown(ctx: commands.Context, player: str | None = None):
        if not await _require_guild(ctx, "Cooldowns"):
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Cooldowns", resolve_error or "Could not resolve player."),
            )
            return
        target_member = resolved_member

        last_drop_at, last_pull_at = get_player_cooldown_timestamps(_guild_id(ctx), target_member.id)
        last_slots_at = get_player_slots_timestamp(_guild_id(ctx), target_member.id)
        last_flip_at = get_player_flip_timestamp(_guild_id(ctx), target_member.id)
        _position, last_monopoly_roll_at, _in_jail, _jail_attempts, _doubles_count = get_monopoly_state(
            _guild_id(ctx),
            target_member.id,
        )
        now = time.time()
        description = multiline_text(
            [
                _cooldown_status_line("Drop", now - last_drop_at, DROP_COOLDOWN_SECONDS),
                _cooldown_status_line("Pull", now - last_pull_at, PULL_COOLDOWN_SECONDS),
                _cooldown_status_line("Slots", now - last_slots_at, SLOTS_COOLDOWN_SECONDS),
                _cooldown_status_line("Flip", now - last_flip_at, FLIP_COOLDOWN_SECONDS),
                _cooldown_status_line(
                    "Monopoly Roll",
                    now - last_monopoly_roll_at,
                    MONOPOLY_ROLL_COOLDOWN_SECONDS,
                ),
            ]
        )
        await _reply(
            ctx,
            embed=italy_embed(f"{target_member.display_name}'s Cooldowns", description),
        )

    @bot.command(name="leaderboard", aliases=["le"])
    async def leaderboard(ctx: commands.Context):
        if not await _require_guild(ctx, "Leaderboard"):
            return

        leaderboard_rows = get_player_leaderboard_info(_guild_id(ctx))
        if not leaderboard_rows:
            await _reply(
                ctx,
                embed=italy_embed("Leaderboard", "No players found yet. Try `ns drop` first."),
            )
            return

        view = PlayerLeaderboardView(
            user_id=ctx.author.id,
            title="Leaderboard",
            entries=leaderboard_rows,
            guard_title="Leaderboard",
        )
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    @bot.command(name="info", aliases=["i"])
    async def info(ctx: commands.Context, player: str | None = None):
        if not await _require_guild(ctx, "Info"):
            return

        resolved_member, resolve_error = await resolve_optional_player_argument(ctx, player)
        if resolved_member is None:
            await _reply(
                ctx,
                embed=italy_embed("Info", resolve_error or "Could not resolve player."),
            )
            return
        target_member = resolved_member

        dough, _, married_instance_id = get_player_info(_guild_id(ctx), target_member.id)
        oven_dough, oven_starter, oven_drop_tickets, oven_pull_tickets = get_player_oven_balances(
            _guild_id(ctx),
            target_member.id,
        )
        starter = get_player_starter(_guild_id(ctx), target_member.id)
        drop_tickets = get_player_drop_tickets(_guild_id(ctx), target_member.id)
        pull_tickets = get_player_pull_tickets(_guild_id(ctx), target_member.id)
        wishes_count = len(get_wishlist_cards(_guild_id(ctx), target_member.id))

        married = "None"
        married_image_url: str | None = None
        married_image_file: discord.File | None = None
        if married_instance_id is not None:
            married_instance = get_instance_by_id(_guild_id(ctx), married_instance_id)
            if married_instance is not None:
                _, married_card_type_id, married_generation, married_card_id = married_instance
                married = card_display(married_card_type_id, married_generation, card_id=married_card_id)
                married_image_url, married_image_file = embed_image_payload(
                    married_card_type_id,
                    generation=married_generation,
                    morph_key=get_instance_morph(_guild_id(ctx), married_instance_id),
                    frame_key=get_instance_frame(_guild_id(ctx), married_instance_id),
                    font_key=get_instance_font(_guild_id(ctx), married_instance_id),
                )

        embed = italy_embed(f"{target_member.display_name}'s Info")
        wallet_lines = [
            f"Dough: {dough}",
            f"Starter: {starter}",
            f"Drop Tickets: {drop_tickets}",
            f"Pull Tickets: {pull_tickets}",
        ]
        oven_lines = [
            f"Dough: {oven_dough}",
            f"Starter: {oven_starter}",
            f"Drop Tickets: {oven_drop_tickets}",
            f"Pull Tickets: {oven_pull_tickets}",
        ]
        embed.add_field(
            name="Cards",
            value=str(get_total_cards(_guild_id(ctx), target_member.id)),
            inline=True,
        )
        embed.add_field(name="**Wallet Items**", value="\n".join(wallet_lines), inline=True)
        embed.add_field(name="**Oven Items**", value="\n".join(oven_lines), inline=True)
        embed.add_field(name="Wishes", value=str(wishes_count), inline=True)
        embed.add_field(name="Married Card", value=married, inline=False)
        if married_image_url is not None:
            embed.set_image(url=married_image_url)

        send_kwargs: dict[str, object] = {"embed": embed}
        if married_image_file is not None:
            send_kwargs["file"] = married_image_file
        await _reply(ctx, **send_kwargs)
