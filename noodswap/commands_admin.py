from .command_utils import *  # noqa: F403


# pylint: disable=wildcard-import,unused-wildcard-import

def register_admin_commands(bot: commands.Bot) -> None:
    @bot.command(name="dbexport")
    @commands.is_owner()
    async def dbexport(ctx: commands.Context):
        if not DB_PATH.exists():
            await _reply(ctx, embed=italy_embed("DB Export", "No database file found yet."))
            return

        await _reply(
            ctx,
            embed=italy_embed("DB Export", "Exporting current `noodswap.db`."),
            file=discord.File(DB_PATH, filename="noodswap.db"),
        )

    @bot.command(name="dbreset")
    @commands.is_owner()
    async def dbreset(ctx: commands.Context):
        reset_db_data()
        await _reply(
            ctx,
            embed=italy_embed(
                "DB Reset",
                "Database reset complete. All persisted Noodswap data has been deleted.",
            ),
        )
