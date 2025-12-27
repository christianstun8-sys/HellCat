import discord
from discord.ext import commands

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ignored = (
            commands.CommandNotFound,
            commands.NotOwner,
        )
        if isinstance(error, ignored):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Du hast ein Argument vergessen: `{error.param.name}`")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Ungültiges Argument: {error}")
            return
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ Du hast nicht die Rechte, diesen Command auszuführen.")
            return

        print(f"[ERROR] Command '{ctx.command}' von {ctx.author} schlug fehl:")
        print(f"       {type(error).__name__}: {error}")

        await ctx.send("⚠️ Es ist ein Fehler aufgetreten. Der Bot-Administrator wurde informiert.")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))