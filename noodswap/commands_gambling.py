from .command_utils import *  # noqa: F403


def register_gambling_commands(bot: commands.Bot) -> None:
    @bot.command(name="slots", aliases=["sl"])
    async def slots(ctx: commands.Context):
        if not await _require_guild(ctx, "Slots"):
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

        is_win = len(set(final_symbols)) == 1
        if is_win:
            starter_reward = random.randint(SLOTS_MIN_REWARD, SLOTS_MAX_REWARD)
            starter_total = add_starter(_guild_id(ctx), ctx.author.id, starter_reward)
            final_lines = [
                "Jackpot! All three matched.",
                f"Reward: **+{starter_reward} starter**",
                f"Starter Balance: **{starter_total}**",
            ]
        else:
            final_lines = [
                "No match this time.",
                f"Try again in **{format_cooldown(SLOTS_COOLDOWN_SECONDS)}**.",
            ]

        await message.edit(
            content=_slots_reel_content(final_symbols, result_emoji="🎉" if is_win else "❌"),
            embed=_slots_embed(final_lines),
        )

    @bot.command(name="flip", aliases=["f"])
    async def flip(ctx: commands.Context, stake_str: str, side_str: str | None = None):
        if not await _require_guild(ctx, "Flip"):
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
            final_lines = [
                f"Result: **{result_side.capitalize()}**",
                f"Payout: **+{stake}** dough",
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

        result = execute_monopoly_roll(
            _guild_id(ctx),
            ctx.author.id,
            now=time.time(),
            cooldown_seconds=MONOPOLY_ROLL_COOLDOWN_SECONDS,
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

        embed = italy_embed("Monopoly Roll", multiline_text(list(result.lines)))
        image_file = None
        thumbnail_card_id = getattr(result, "thumbnail_card_id", None) or result.mpreg_card_id
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

        await _reply(ctx, embed=embed, file=image_file)

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

        pot_dough, pot_starter, pot_drop_tickets = get_gambling_pot(_guild_id(ctx))
        await _reply(
            ctx,
            embed=italy_embed(
                "Monopoly Pot",
                multiline_text(
                    [
                        f"Dough: **{pot_dough}**",
                        f"Starter: **{pot_starter}**",
                        f"Drop Tickets: **{pot_drop_tickets}**",
                    ]
                ),
            ),
        )
