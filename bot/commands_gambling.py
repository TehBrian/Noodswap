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
    FLIP_WIN_PAYOUT_MULTIPLIER_DENOMINATOR as FLIP_WIN_PAYOUT_MULTIPLIER_DENOMINATOR,
    FLIP_WIN_PAYOUT_MULTIPLIER_NUMERATOR as FLIP_WIN_PAYOUT_MULTIPLIER_NUMERATOR,
    FLIP_REVEAL_DELAY_SECONDS as FLIP_REVEAL_DELAY_SECONDS,
    FLIP_WIN_PROBABILITY as FLIP_WIN_PROBABILITY,
    FontConfirmView as FontConfirmView,
    FrameConfirmView as FrameConfirmView,
    HD_CARD_RENDER_SIZE as HD_CARD_RENDER_SIZE,
    HelpView as HelpView,
    MONOPOLY_JAIL_FINE_DOUGH as MONOPOLY_JAIL_FINE_DOUGH,
    MONOPOLY_ROLL_ACTIVITY_PHRASES as MONOPOLY_ROLL_ACTIVITY_PHRASES,
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
    SLOTS_THREE_MATCH_MAX_DOUGH_REWARD as SLOTS_THREE_MATCH_MAX_DOUGH_REWARD,
    SLOTS_THREE_MATCH_MIN_DOUGH_REWARD as SLOTS_THREE_MATCH_MIN_DOUGH_REWARD,
    SLOTS_TWO_MATCH_MAX_DOUGH_REWARD as SLOTS_TWO_MATCH_MAX_DOUGH_REWARD,
    SLOTS_TWO_MATCH_MIN_DOUGH_REWARD as SLOTS_TWO_MATCH_MIN_DOUGH_REWARD,
    SortableCardListView as SortableCardListView,
    SortableCollectionView as SortableCollectionView,
    TradeView as TradeView,
    VOTE_STARTER_REWARD as VOTE_STARTER_REWARD,
    add_card_to_wishlist as add_card_to_wishlist,
    add_dough as add_dough,
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
    command_execution_gate as command_execution_gate,
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
    _animate_slots_spin as _animate_slots_spin,
    _guild_id as _guild_id,
    _normalize_flip_side as _normalize_flip_side,
    _reply as _reply,
    _require_guild as _require_guild,
    _revealed_flip_side as _revealed_flip_side,
    _slots_embed as _slots_embed,
    _slots_reel_content as _slots_reel_content,
)  # noqa: F403


def register_gambling_commands(bot: commands.Bot) -> None:
    @bot.command(name="slots", aliases=["sl"])
    async def slots(ctx: commands.Context):
        if not await _require_guild(ctx, "Slots"):
            return

        async with command_execution_gate(ctx.author.id, "slots") as entered:
            if not entered:
                await _reply(
                    ctx,
                    embed=italy_embed("Slots", "A slots spin is already in progress."),
                )
                return

            now = time.time()
            cooldown_remaining_seconds = consume_slots_cooldown_if_ready(
                guild_id=_guild_id(ctx),
                user_id=ctx.author.id,
                now=now,
                cooldown_seconds=SLOTS_COOLDOWN_SECONDS,
            )
            if cooldown_remaining_seconds > 0:
                await _reply(
                    ctx,
                    embed=italy_embed(
                        "Slots Cooldown",
                        f"You need to wait before spinning again (**{format_cooldown(cooldown_remaining_seconds)}** remaining).",
                    ),
                )
                return

            final_symbols = [random.choice(SLOTS_REEL_EMOJIS) for _ in range(SLOTS_REEL_COUNT)]
            initial_symbols = [random.choice(SLOTS_REEL_EMOJIS) for _ in range(SLOTS_REEL_COUNT)]
            message = await _reply(
                ctx,
                content=_slots_reel_content(initial_symbols),
                embed=_slots_embed(["Spinning..."]),
            )
            await _animate_slots_spin(message, final_symbols)

            match_count = max(final_symbols.count(symbol) for symbol in set(final_symbols))
            is_jackpot = match_count == 3
            is_partial_win = match_count == 2
            if is_jackpot:
                dough_reward = random.randint(
                    SLOTS_THREE_MATCH_MIN_DOUGH_REWARD,
                    SLOTS_THREE_MATCH_MAX_DOUGH_REWARD,
                )
                starter_reward = random.randint(SLOTS_MIN_REWARD, SLOTS_MAX_REWARD)
                add_dough(_guild_id(ctx), ctx.author.id, dough_reward)
                dough_total, _, _ = get_player_info(_guild_id(ctx), ctx.author.id)
                starter_total = add_starter(_guild_id(ctx), ctx.author.id, starter_reward)
                final_lines = [
                    "Jackpot! All three matched.",
                    f"Reward: **+{dough_reward} dough** and **+{starter_reward} starter**",
                    f"Dough Balance: **{dough_total}** dough",
                    f"Starter Balance: **{starter_total}**",
                ]
            elif is_partial_win:
                dough_reward = random.randint(
                    SLOTS_TWO_MATCH_MIN_DOUGH_REWARD,
                    SLOTS_TWO_MATCH_MAX_DOUGH_REWARD,
                )
                add_dough(_guild_id(ctx), ctx.author.id, dough_reward)
                dough_total, _, _ = get_player_info(_guild_id(ctx), ctx.author.id)
                final_lines = [
                    "Two matched.",
                    f"Reward: **+{dough_reward} dough**",
                    f"Dough Balance: **{dough_total}** dough",
                ]
            else:
                final_lines = [
                    "No match this time.",
                    f"Try again in **{format_cooldown(SLOTS_COOLDOWN_SECONDS)}**.",
                ]

            await message.edit(
                content=_slots_reel_content(
                    final_symbols,
                    result_emoji="🎉" if is_jackpot or is_partial_win else "❌",
                ),
                embed=_slots_embed(final_lines),
            )

    @bot.command(name="flip", aliases=["f"])
    async def flip(ctx: commands.Context, stake_str: str, side_str: str | None = None):
        if not await _require_guild(ctx, "Flip"):
            return

        async with command_execution_gate(ctx.author.id, "flip") as entered:
            if not entered:
                await _reply(
                    ctx,
                    embed=italy_embed("Flip", "A flip is already in progress."),
                )
                return

            try:
                stake = int(stake_str)
            except ValueError:
                await _reply(ctx, embed=italy_embed("Flip", "Stake must be a positive integer."))
                return

            if stake <= 0:
                await _reply(ctx, embed=italy_embed("Flip", "Stake must be a positive integer."))
                return

            selected_side = _normalize_flip_side(side_str)
            if side_str is not None and selected_side is None:
                await _reply(
                    ctx,
                    embed=italy_embed("Flip", "Side must be `heads`/`tails` (or `h`/`t`)."),
                )
                return

            status, cooldown_remaining_seconds, dough_total = execute_flip_wager(
                _guild_id(ctx),
                ctx.author.id,
                stake=stake,
                now=time.time(),
                cooldown_seconds=FLIP_COOLDOWN_SECONDS,
                did_win=random.random() < FLIP_WIN_PROBABILITY,
            )

            if status == "cooldown":
                await _reply(
                    ctx,
                    embed=italy_embed(
                        "Flip Cooldown",
                        f"You need to wait before flipping again (**{format_cooldown(cooldown_remaining_seconds)}** remaining).",
                    ),
                )
                return

            if status == "insufficient_dough":
                await _reply(
                    ctx,
                    embed=italy_embed(
                        "Flip",
                        multiline_text(
                            [
                                f"Stake: **{stake}** dough",
                                f"Balance: **{dough_total}** dough",
                                "You do not have enough dough.",
                            ]
                        ),
                    ),
                )
                return

            did_player_win = status == "won"
            result_side = _revealed_flip_side(did_player_win, selected_side)
            suspense_lines = [f"The coin is **{random.choice(FLIP_ACTIVITY_PHRASES)}**..."]
            if selected_side is not None:
                suspense_lines.append(f"Call: **{selected_side.capitalize()}**")

            message = await _reply(ctx, embed=italy_embed("Flip", multiline_text(suspense_lines)))
            await asyncio.sleep(FLIP_REVEAL_DELAY_SECONDS)

            if did_player_win:
                payout = (stake * FLIP_WIN_PAYOUT_MULTIPLIER_NUMERATOR) // FLIP_WIN_PAYOUT_MULTIPLIER_DENOMINATOR
                final_lines = [
                    f"Result: **{result_side.capitalize()}**",
                    f"Payout: **+{payout}** dough",
                    f"Balance: **{dough_total}** dough",
                ]
            else:
                final_lines = [
                    f"Result: **{result_side.capitalize()}**",
                    f"Lost: **-{stake}** dough",
                    f"Balance: **{dough_total}** dough",
                ]

            await message.edit(embed=italy_embed("Flip", multiline_text(final_lines)))

    @bot.group(name="monopoly", aliases=["mp"], invoke_without_command=True)
    async def monopoly(ctx: commands.Context):
        await _reply(
            ctx,
            embed=italy_embed(
                "Monopoly",
                multiline_text(
                    [
                        "Usage:",
                        "`ns monopoly roll`",
                        "`ns monopoly fine`",
                        "`ns monopoly board`",
                        "`ns monopoly pot`",
                    ]
                ),
            ),
        )

    @monopoly.command(name="roll", aliases=["r"])
    async def monopoly_roll(ctx: commands.Context):
        if not await _require_guild(ctx, "Monopoly"):
            return

        async with command_execution_gate(ctx.author.id, "monopoly_roll") as entered:
            if not entered:
                await _reply(
                    ctx,
                    embed=italy_embed("Monopoly Roll", "A monopoly roll is already in progress."),
                )
                return

            valid_guild_member_ids = None
            if ctx.guild is not None and hasattr(ctx.guild, "members"):
                valid_guild_member_ids = {member.id for member in ctx.guild.members}

            result = execute_monopoly_roll(
                _guild_id(ctx),
                ctx.author.id,
                now=time.time(),
                cooldown_seconds=MONOPOLY_ROLL_COOLDOWN_SECONDS,
                valid_guild_member_ids=valid_guild_member_ids,
            )
            if result.status == "cooldown":
                await _reply(
                    ctx,
                    embed=italy_embed(
                        "Monopoly Roll Cooldown",
                        f"You need to wait **{format_cooldown(result.cooldown_remaining)}** before rolling again.",
                    ),
                )
                return

            suspense_embed = italy_embed(
                "Monopoly Roll",
                f"The dice are **{random.choice(MONOPOLY_ROLL_ACTIVITY_PHRASES)}**...",
            )
            message = await _reply(ctx, embed=suspense_embed)
            await asyncio.sleep(FLIP_REVEAL_DELAY_SECONDS)

            embed = italy_embed("Monopoly Roll", multiline_text(list(result.lines)))
            image_file = None
            thumbnail_card_id = getattr(result, "thumbnail_card_id", None) or result.mpreg_card_type_id
            thumbnail_generation = getattr(result, "thumbnail_generation", None) or result.mpreg_generation
            thumbnail_morph_key = getattr(result, "thumbnail_morph_key", None)
            thumbnail_frame_key = getattr(result, "thumbnail_frame_key", None)
            thumbnail_font_key = getattr(result, "thumbnail_font_key", None)

            if thumbnail_card_id is not None and thumbnail_generation is not None:
                attachment_url, image_file = embed_image_payload(
                    thumbnail_card_id,
                    thumbnail_generation,
                    morph_key=(thumbnail_morph_key if thumbnail_morph_key is not None else result.mpreg_morph_key),
                    frame_key=(thumbnail_frame_key if thumbnail_frame_key is not None else result.mpreg_frame_key),
                    font_key=(thumbnail_font_key if thumbnail_font_key is not None else result.mpreg_font_key),
                )
                if attachment_url is not None:
                    embed.set_thumbnail(url=attachment_url)

            await message.edit(embed=embed, attachments=[image_file] if image_file is not None else [])

    @monopoly.command(name="fine")
    async def monopoly_fine(ctx: commands.Context):
        if not await _require_guild(ctx, "Monopoly Fine"):
            return

        result = execute_monopoly_fine(_guild_id(ctx), ctx.author.id)
        await _reply(ctx, embed=italy_embed("Monopoly Fine", multiline_text(list(result.lines))))

    @monopoly.command(name="board", aliases=["b"])
    async def monopoly_board(ctx: commands.Context):
        if not await _require_guild(ctx, "Monopoly Board"):
            return

        position, in_jail, jail_attempts, doubles_count, board_render = get_monopoly_board_state(_guild_id(ctx), ctx.author.id)
        await _reply(
            ctx,
            embed=italy_embed(
                "Monopoly Board",
                multiline_text(
                    [
                        f"Position: **{position}**",
                        f"In Jail: **{'Yes' if in_jail else 'No'}**",
                        f"Jail Failed Rolls: **{jail_attempts}/3**",
                        f"Consecutive Doubles: **{doubles_count}**",
                        "",
                        f"```\n{board_render}\n```",
                    ]
                ),
            ),
        )

    @monopoly.command(name="pot", aliases=["p"])
    async def monopoly_pot(ctx: commands.Context):
        if not await _require_guild(ctx, "Monopoly Pot"):
            return

        pot_dough, pot_starter, pot_drop_tickets, pot_pull_tickets = get_gambling_pot(_guild_id(ctx))
        await _reply(
            ctx,
            embed=italy_embed(
                "Monopoly Pot",
                multiline_text(
                    [
                        f"Dough: **{pot_dough}**",
                        f"Starter: **{pot_starter}**",
                        f"Drop Tickets: **{pot_drop_tickets}**",
                        f"Pull Tickets: **{pot_pull_tickets}**",
                    ]
                ),
            ),
        )
