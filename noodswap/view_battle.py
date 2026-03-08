from typing import Optional

import discord

from .presentation import italy_embed
from .services import resolve_battle_offer
from .settings import BATTLE_PROPOSAL_TIMEOUT_SECONDS


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
                embed=italy_embed("Battle", "Only the challenged member can respond to this battle."),
                ephemeral=True,
            )
            return

        if self.finished:
            await interaction.response.send_message(
                embed=italy_embed("Battle", "This battle proposal has already been resolved."),
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
        stake_text = str(result.stake) if result.stake is not None else "unknown"
        await interaction.response.edit_message(
            content=None,
            embed=italy_embed(
                "Battle Accepted",
                (
                    f"Challenger: <@{self.challenger_id}>\n"
                    f"Challenged: <@{self.challenged_id}>\n"
                    f"Stake: **{stake_text}** dough each\n\n"
                    "Battle setup is complete. Turn controls will be posted next."
                ),
            ),
            view=self,
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
