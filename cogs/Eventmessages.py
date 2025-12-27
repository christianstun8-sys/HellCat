import discord
from discord.ext import commands

class WelcomeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

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

        wembed.set_thumbnail(url=member.avatar_url)
        await guild.system_channel.send(embed=wembed)


class ByeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_leave(self, member):
        guild = member.guild

        ban = await member.guild.fetch_ban(member)

        if ban:
            reason = ban.reason
            if reason != None:
                bembed = discord.Embed(
                    title="Mitglied gebannt",
                    description=f"Die Person {member.name} wurde von dem Server gebannt für den Grund: {reason}.",
                    color=discord.Color.dark_red()
                )
            else:
                bembed = discord.Embed(
                    title="Mitglied gebannt",
                    description=f"Die Person {member.name} wurde von dem Server gebannt.",
                    color=discord.Color.dark_red()
                )
            bembed.set_thumbnail(url=member.avatar_url)
            await guild.system_channel.send(embed=bembed)

        else:
            if guild.id == 1181909214537461840:
                bembed = discord.Embed(
                    title="Mitglied hat die Hölle verlassen",
                    description=f"{member.name} hat uns allein stehen lassen...",
                    color=discord.Color.red()
                )
            bembed.set_thumbnail(url=member.avatar_url)

            await guild.system_channel.send(embed=bembed)

class BoostMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        guild = before.guild
        if before.premium_subscription_count < after.premium_subscription_count:
            booster_member = None
            for member in after.members:
                if member.premium_since is not None and member.premium_since.date() == discord.utils.utcnow().date():
                    booster_member = member
                    break

            if booster_member and self.boost_channel_id:
                embed = discord.Embed(
                    title="✨ Neuer Server-Boost! ✨",
                    description=f"Vielen Dank an {booster_member.mention} für den Boost! Wir schätzen deine Unterstützung sehr!",
                    color=discord.Color.dark_magenta()
                )
                embed.set_thumbnail(url=booster_member.avatar_url)
                await guild.system_channel.send(embed=embed, content=f"{booster_member.mention}")

async def setup(bot):
    await bot.add_cog(ByeMessage(bot))
    await bot.add_cog(BoostMessage(bot))
    await bot.add_cog(WelcomeMessage(bot))