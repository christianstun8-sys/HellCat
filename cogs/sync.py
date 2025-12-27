import discord
from discord.ext import commands


class Synccommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dev-sync")
    async def sync(self, ctx):
        if ctx.author.id != 1235134572157603841:
            pass

        loading_embed = discord.Embed(
            title="<a:loading:1442608388134535269> Befehle werden synchronisiert, einen Moment bitte...",
            color=discord.Color.light_grey(),
        )

        await ctx.send(embed=loading_embed)

        try:
            synced = await self.bot.tree.sync()

            success_embed = discord.Embed(
            title=f"<:success:1442608648303022110> Erfolgreich {len(synced)} Slash-Befehle synchronisiert!",
            color=discord.Color.green()
            )

            await ctx.send(embed=success_embed)
        except Exception as e:

            failed_embed = discord.Embed(
                title=f"<:error:1442609033046523975> Fehler beim Synchronisieren der Slash-Befehle: {e}",
                color=discord.Color.red(),
            )

            await ctx.send(embed=failed_embed)
async def setup(bot):
    await bot.add_cog(Synccommand(bot))