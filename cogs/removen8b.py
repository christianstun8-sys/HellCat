from discord.ext import commands

class RemoveN8BCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="removen8b")
    async def removen8b(self, ctx):
        user = ctx.author

        target_guild = self.bot.get_guild(1363137083148865598)
        if target_guild is None:
            await ctx.channel.send("Server nicht gefunden.", delete_after=10)
        else:
            await target_guild.leave()
            await ctx.channel.send("Hell Cat hat N8B verlassen.", delete_after=10)

async def setup(bot):
    await bot.add_cog(RemoveN8BCommand(bot))