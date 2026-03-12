from typing import Optional

import discord

from .presentation import battle_arena_description, italy_embed
from .services import (
    get_battle_snapshot,
    resolve_battle_offer,
    resolve_battle_turn_action,
)
from .settings import BATTLE_PROPOSAL_TIMEOUT_SECONDS, BATTLE_TURN_TIMEOUT_SECONDS


def _battle_embed(snapshot) -> discord.Embed:
    title = "Battle Arena"
    if snapshot.status == "finished" and snapshot.winner_user_id is not None:
        title = "Battle Arena 🏆"
    return italy_embed(
        title,
        battle_arena_description(
            challenger_mention=f"<@{snapshot.challenger_id}>",
            challenged_mention=f"<@{snapshot.challenged_id}>",
            stake=snapshot.stake,
            turn_number=snapshot.turn_number,
            acting_user_id=snapshot.acting_user_id,
            winner_user_id=snapshot.winner_user_id,
            challenger_team_name=snapshot.challenger_team_name,
            challenged_team_name=snapshot.challenged_team_name,
            challenger_rows=snapshot.challenger_combatants,
            challenged_rows=snapshot.challenged_combatants,
            last_action=snapshot.last_action,
        ),
    )


class BattleTurnView(discord.ui.View):
    def __init__(self, guild_id: int, battle_id: int):
        super().__init__(timeout=BATTLE_TURN_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.battle_id = battle_id
        self.finished = False
        self.message: Optional[discord.Message] = None

    async def _apply_action(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        snapshot = get_battle_snapshot(self.guild_id, self.battle_id)
        if snapshot is None:
            await interaction.response.send_message(
                embed=italy_embed("Battle", "Battle state could not be loaded."),
                ephemeral=True,
            )
            return
        if snapshot.status != "active":
            self.finished = True
            await interaction.response.send_message(
                embed=italy_embed("Battle", "This battle is no longer active."),
                ephemeral=True,
            )
            return
        if snapshot.acting_user_id != interaction.user.id:
            await interaction.response.send_message(
                embed=italy_embed("Battle", "It is not your turn."),
                ephemeral=True,
            )
            return

        result = resolve_battle_turn_action(
            self.guild_id,
            self.battle_id,
            interaction.user.id,
            action,
        )
        if result.is_failed:
            await interaction.response.send_message(
                embed=italy_embed("Battle", result.message),
                ephemeral=True,
            )
            return

        if result.snapshot is None:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                embed=italy_embed("Battle", result.message),
                view=self,
            )
            return

        if result.is_finished:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                embed=_battle_embed(result.snapshot),
                view=self,
            )
            return

        next_view = BattleTurnView(self.guild_id, self.battle_id)
        next_view.message = interaction.message
        self.finished = True
        self.stop()
        await interaction.response.edit_message(
            embed=_battle_embed(result.snapshot),
            view=next_view,
        )

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._apply_action(interaction, "attack")

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.primary)
    async def defend_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._apply_action(interaction, "defend")

    @discord.ui.button(label="Switch", style=discord.ButtonStyle.secondary)
    async def switch_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._apply_action(interaction, "switch")

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.secondary)
    async def surrender_button(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        await self._apply_action(interaction, "surrender")

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        snapshot = get_battle_snapshot(self.guild_id, self.battle_id)
        if (
            snapshot is None
            or snapshot.status != "active"
            or snapshot.acting_user_id is None
        ):
            self._disable_buttons()
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
            return

        result = resolve_battle_turn_action(
            self.guild_id,
            self.battle_id,
            snapshot.acting_user_id,
            "timeout_skip",
        )
        if result.snapshot is None:
            self._disable_buttons()
            try:
                await self.message.edit(
                    embed=italy_embed("Battle", "Battle state could not be refreshed."),
                    view=self,
                )
            except discord.HTTPException:
                pass
            return

        if result.is_finished:
            self._disable_buttons()
            try:
                await self.message.edit(embed=_battle_embed(result.snapshot), view=self)
            except discord.HTTPException:
                pass
            return

        next_view = BattleTurnView(self.guild_id, self.battle_id)
        next_view.message = self.message
        try:
            await self.message.edit(
                embed=_battle_embed(result.snapshot), view=next_view
            )
        except discord.HTTPException:
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class BattleProposalView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        battle_id: int,
        challenger_id: int,
        challenged_id: int,
    ):
        super().__init__(timeout=BATTLE_PROPOSAL_TIMEOUT_SECONDS)
        self.guild_id = guild_id
        self.battle_id = battle_id
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.finished = False
        self.message: Optional[discord.Message] = None

    async def _resolve(self, interaction: discord.Interaction, accepted: bool) -> None:
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Battle", "Only the challenged member can respond to this battle."
                ),
                ephemeral=True,
            )
            return

        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed(
                    "Battle", "This battle proposal has already been resolved."
                ),
                ephemeral=True,
            )
            return

        result = resolve_battle_offer(
            guild_id=self.guild_id,
            battle_id=self.battle_id,
            responder_id=self.challenged_id,
            accepted=accepted,
        )
        if result.is_failed:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                content=None,
                embed=italy_embed("Battle Failed", result.message),
                view=self,
            )
            return

        if result.is_denied:
            self.finished = True
            self._disable_buttons()
            await interaction.response.edit_message(
                content=None,
                embed=italy_embed("Battle Denied", result.message),
                view=self,
            )
            return

        self.finished = True
        self._disable_buttons()
        snapshot = get_battle_snapshot(self.guild_id, self.battle_id)
        if snapshot is None:
            await interaction.response.edit_message(
                content=None,
                embed=italy_embed(
                    "Battle Failed", "Battle setup failed while loading arena state."
                ),
                view=self,
            )
            return

        battle_view = BattleTurnView(self.guild_id, self.battle_id)
        battle_view.message = interaction.message
        await interaction.response.edit_message(
            content=None,
            embed=_battle_embed(snapshot),
            view=battle_view,
        )

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await self._resolve(interaction, accepted=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        await self._resolve(interaction, accepted=False)

    async def on_timeout(self) -> None:
        if self.finished or self.message is None:
            return

        self._disable_buttons()

        try:
            await self.message.edit(
                content=None,
                embed=italy_embed("Battle Expired", "Battle proposal expired."),
                view=self,
            )
        except discord.HTTPException:
            pass

    def _disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
