import discord
from discord.ext import commands

class WelcomeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if not guild.system_channel:
            return

        if guild.id == 1181909214537461840:
            # HOD Server
            wembed = discord.Embed(
                title="Herzlich willkommen!",
                description=f"Willkommen in der Hölle, {member.mention}! 😈",
                color=discord.Color.dark_red()
            )
        else:
            wembed = discord.Embed(
                title="Herzlich willkommen!",
                description=f"Herzlich willkommen {member.mention}, in {guild.name}!",
                color=discord.Color.orange()
            )

        wembed.set_thumbnail(url=member.display_avatar.url)
        await guild.system_channel.send(embed=wembed)


class ByeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        if not guild.system_channel:
            return

        try:
            ban_entry = await guild.fetch_ban(member)
            reason = ban_entry.reason if ban_entry.reason else "kein Grund angegeben"

            bembed = discord.Embed(
                title="Mitglied gebannt",
                description=f"Die Person **{member.name}** wurde vom Server gebannt.\n**Grund:** {reason}",
                color=discord.Color.dark_red()
            )
        except discord.NotFound:
            if guild.id == 1181909214537461840:
                bembed = discord.Embed(
                    title="Mitglied hat die Hölle verlassen",
                    description=f"{member.name} hat uns allein stehen lassen...",
                    color=discord.Color.red()
                )
            else:
                bembed = discord.Embed(
                    title="Auf Wiedersehen",
                    description=f"{member.name} hat den Server verlassen.",
                    color=discord.Color.light_gray()
                )
        except discord.Forbidden:
            bembed = discord.Embed(description=f"{member.name} hat den Server verlassen (Status unbekannt).")

        bembed.set_thumbnail(url=member.display_avatar.url)
        await guild.system_channel.send(embed=bembed)


class BoostMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.premium_subscription_count < after.premium_subscription_count:
            if not after.system_channel:
                return

            booster_member = None
            for member in after.members:
                if member.premium_since and member.premium_since.date() == discord.utils.utcnow().date():
                    booster_member = member
                    break

            if booster_member:
                embed = discord.Embed(
                    title="✨ Neuer Server-Boost! ✨",
                    description=f"Vielen Dank an {booster_member.mention} für den Boost! Wir schätzen deine Unterstützung sehr!",
                    color=discord.Color.dark_magenta()
                )
                embed.set_thumbnail(url=booster_member.display_avatar.url)
                await after.system_channel.send(content=f"{booster_member.mention}", embed=embed)

async def setup(bot):
    await bot.add_cog(ByeMessage(bot))
    await bot.add_cog(BoostMessage(bot))
    await bot.add_cog(WelcomeMessage(bot))