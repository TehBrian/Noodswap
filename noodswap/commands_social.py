# pylint: disable=wildcard-import,unused-wildcard-import,undefined-variable
from .command_utils import *  # noqa: F403

def register_social_commands(bot: commands.Bot) -> None:
    @bot.group(name="wish", aliases=["w"], invoke_without_command=True)
    async def wish(ctx: commands.Context):
        await _reply(ctx, embed=italy_embed("Wishlist", "Usage: `ns wish add <card_id>`, `ns wish remove <card_id>`, or `ns wish list [player]`."))

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
            await _reply(ctx, embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
            return
        await _wish_list(ctx, resolved_member)

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
            await _reply(ctx, embed=italy_embed("Wishlist", resolve_error or "Could not resolve player."))
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
                    "`ns tag assign <tag_name> <card_code>`, `ns tag unassign <tag_name> <card_code>`, "
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
    async def tag_assign(ctx: commands.Context, tag_name: str, card_code: str):
        await _tag_assign(ctx, tag_name, card_code)

    @tag.command(name="unassign", aliases=["u"])
    async def tag_unassign(ctx: commands.Context, tag_name: str, card_code: str):
        await _tag_unassign(ctx, tag_name, card_code)

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
                    "`ns folder assign <folder_name> <card_code>`, `ns folder unassign <folder_name> <card_code>`, "
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
    async def folder_assign(ctx: commands.Context, folder_name: str, card_code: str):
        await _folder_assign(ctx, folder_name, card_code)

    @folder.command(name="unassign", aliases=["u"])
    async def folder_unassign(ctx: commands.Context, folder_name: str, card_code: str):
        await _folder_unassign(ctx, folder_name, card_code)

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
                    "`ns team assign <team_name> <card_code>`, `ns team unassign <team_name> <card_code>`, "
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
    async def team_assign(ctx: commands.Context, team_name: str, card_code: str):
        await _team_assign(ctx, team_name, card_code)

    @team.command(name="unassign", aliases=["u"])
    async def team_unassign(ctx: commands.Context, team_name: str, card_code: str):
        await _team_unassign(ctx, team_name, card_code)

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
            await _reply(ctx, embed=italy_embed("Cooldowns", resolve_error or "Could not resolve player."))
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
                _cooldown_status_line("Monopoly Roll", now - last_monopoly_roll_at, MONOPOLY_ROLL_COOLDOWN_SECONDS),
            ]
        )
        await _reply(ctx, embed=italy_embed(f"{target_member.display_name}'s Cooldowns", description))

    @bot.command(name="leaderboard", aliases=["le"])
    async def leaderboard(ctx: commands.Context):
        if not await _require_guild(ctx, "Leaderboard"):
            return

        leaderboard_rows = get_player_leaderboard_info(_guild_id(ctx))
        if not leaderboard_rows:
            await _reply(ctx, embed=italy_embed("Leaderboard", "No players found yet. Try `ns drop` first."))
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
            await _reply(ctx, embed=italy_embed("Info", resolve_error or "Could not resolve player."))
            return
        target_member = resolved_member

        dough, _, married_instance_id = get_player_info(_guild_id(ctx), target_member.id)
        starter = get_player_starter(_guild_id(ctx), target_member.id)
        drop_tickets = get_player_drop_tickets(_guild_id(ctx), target_member.id)
        wishes_count = len(get_wishlist_cards(_guild_id(ctx), target_member.id))

        married = "None"
        married_image_url: str | None = None
        married_image_file: discord.File | None = None
        if married_instance_id is not None:
            married_instance = get_instance_by_id(_guild_id(ctx), married_instance_id)
            if married_instance is not None:
                _, married_card_id, married_generation, married_dupe_code = married_instance
                married = card_dupe_display(married_card_id, married_generation, dupe_code=married_dupe_code)
                married_image_url, married_image_file = embed_image_payload(
                    married_card_id,
                    generation=married_generation,
                    morph_key=get_instance_morph(_guild_id(ctx), married_instance_id),
                    frame_key=get_instance_frame(_guild_id(ctx), married_instance_id),
                    font_key=get_instance_font(_guild_id(ctx), married_instance_id),
                )

        embed = italy_embed(f"{target_member.display_name}'s Info")
        embed.add_field(name="Cards", value=str(get_total_cards(_guild_id(ctx), target_member.id)), inline=True)
        embed.add_field(name="Dough", value=str(dough), inline=True)
        embed.add_field(name="Starter", value=str(starter), inline=True)
        embed.add_field(name="Drop Tickets", value=str(drop_tickets), inline=True)
        embed.add_field(name="Wishes", value=str(wishes_count), inline=True)
        embed.add_field(name="Married Card", value=married, inline=False)
        if married_image_url is not None:
            embed.set_image(url=married_image_url)

        send_kwargs: dict[str, object] = {"embed": embed}
        if married_image_file is not None:
            send_kwargs["file"] = married_image_file
        await _reply(ctx, **send_kwargs)
