from .command_utils import *  # noqa: F403


# pylint: disable=wildcard-import,unused-wildcard-import

def register_catalog_commands(bot: commands.Bot) -> None:
    @bot.group(name="buy", invoke_without_command=True)
    async def buy(ctx: commands.Context):
        await _reply(ctx, embed=italy_embed("Buy", "Usage: `ns buy drop [quantity]` (1 starter per drop ticket)."))

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
                        f"Purchased: **{spent} drop ticket(s)**",
                        f"Spent: **{spent} starter**",
                        f"Starter Balance: **{starter_balance}**",
                        f"Drop Tickets: **{drop_tickets}**",
                    ]
                ),
            ),
        )

    @bot.command(name="cards", aliases=["ca"])
    async def cards(ctx: commands.Context):
        if not await _require_guild(ctx, "All Cards"):
            return

        wish_counts = get_card_wish_counts(_guild_id(ctx))
        entries = [(card_id, wish_counts.get(card_id, 0)) for card_id in CARD_CATALOG]

        view = CardCatalogView(user_id=ctx.author.id, entries=entries)
        message = await _reply(ctx, embed=view.build_embed(), view=view)
        view.message = message

    async def _run_lookup(
        ctx: commands.Context,
        *,
        card_id: str | None,
        image_size: tuple[int, int],
        embed_title: str,
        usage_name: str,
    ) -> None:
        if card_id is None:
            await _reply(ctx, embed=italy_embed("Lookup", f"Usage: `ns {usage_name} <card_id|card_code|query>`."))
            return

        if ctx.guild is not None:
            matched_instance = get_instance_by_dupe_code(_guild_id(ctx), card_id)
            if matched_instance is not None:
                matched_instance_id, matched_card_id, matched_generation, matched_dupe_code = matched_instance
                morph_key = get_instance_morph(_guild_id(ctx), matched_instance_id)
                frame_key = get_instance_frame(_guild_id(ctx), matched_instance_id)
                font_key = get_instance_font(_guild_id(ctx), matched_instance_id)
                lookup_embed = italy_embed(
                    embed_title,
                    _lookup_trait_breakdown_description(
                        matched_card_id,
                        matched_generation,
                        matched_dupe_code,
                        morph_key=morph_key,
                        frame_key=frame_key,
                        font_key=font_key,
                    ),
                )
                image_url, image_file = embed_image_payload(
                    matched_card_id,
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

        normalized_card_id = normalize_card_id(card_id)
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

        name_matches = search_card_ids(card_id, include_series=True)
        if not name_matches:
            await _reply(ctx, embed=italy_embed("Lookup", "No results found."))
            return

        if len(name_matches) == 1:
            matched_card_id = name_matches[0]
            lookup_embed = italy_embed(embed_title, card_base_display(matched_card_id))
            image_url, image_file = embed_image_payload(matched_card_id, size=image_size)
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
    async def lookup(ctx: commands.Context, *, card_id: str | None = None):
        await _run_lookup(
            ctx,
            card_id=card_id,
            image_size=DEFAULT_CARD_RENDER_SIZE,
            embed_title="Card Lookup",
            usage_name="lookup",
        )

    @bot.command(name="lookuphd", aliases=["lhd"])
    async def lookup_hd(ctx: commands.Context, *, card_id: str | None = None):
        await _run_lookup(
            ctx,
            card_id=card_id,
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
            "Support Noodswap by voting on top.gg.",
            f"Reward: **+{VOTE_STARTER_REWARD} starter** when your vote is detected.",
            "",
            "After voting, run `ns vote` again to claim your reward.",
        ]

        api_token = os.getenv("TOPGG_API_TOKEN", "").strip()
        if not api_token:
            lines.extend(
                [
                    "",
                    "Vote checking is temporarily unavailable right now.",
                    "You can still vote using the button below and try claiming again soon.",
                ]
            )
            await _reply(ctx, embed=italy_embed("Vote", multiline_text(lines)), view=_vote_link_view(vote_url))
            return

        voted, vote_error = await _topgg_recent_vote_status(ctx.author.id, api_token)
        if voted:
            starter_total = claim_vote_reward(
                guild_id=_guild_id(ctx),
                user_id=ctx.author.id,
                reward_amount=VOTE_STARTER_REWARD,
            )
            lines.extend([
                "",
                f"Claimed: **+{VOTE_STARTER_REWARD} starter**",
                f"Starter Balance: **{starter_total}**",
            ])
        elif voted is False:
            lines.extend([
                "",
                "No recent top.gg vote detected for your account yet.",
                "Cast your vote using the button, then try `ns vote` again.",
            ])
        else:
            lines.extend(["", f"Could not verify your top.gg vote right now: {vote_error or 'unknown error'}"])

        await _reply(ctx, embed=italy_embed("Vote", multiline_text(lines)), view=_vote_link_view(vote_url))

    @bot.command(name="help", aliases=["h"])
    async def help_command(ctx: commands.Context):
        view = HelpView(user_id=ctx.author.id)
        message = await _reply(ctx, embed=view.build_overview_embed(), view=view)
        view.message = message
