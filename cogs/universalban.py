import discord
from discord.ext import commands
import channels

TARGET_GUILDS = [
    channels.HOUSE_OF_DEMONS.guild_id,
    channels.NACHTBUS.guild_id,
    channels.INFINITY_EMPIRE.guild_id
]


class UniversalBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if guild.id not in TARGET_GUILDS:
            return

        ban_embed = discord.Embed(
            title="🔨 Universal-Bann",
            description="Du wurdest aus dem Server-Netzwerk von House of Demons, Nachtbus und Infinity Empire ausgeschlossen.",
            color=discord.Color.red()
        )
        try:
            await user.send(embed=ban_embed)
        except discord.Forbidden:
            print(f"Konnte DM an {user.name} nicht senden.")

        for guild_id in TARGET_GUILDS:
            if guild_id == guild.id:
                continue

            target_guild = self.bot.get_guild(guild_id)
            if target_guild:
                try:
                    await target_guild.ban(user, reason="Globaler Bann-Verbund")
                    print(f"User {user.name} auf {target_guild.name} gebannt.")
                except discord.NotFound:
                    print(f"User auf {target_guild.name} bereits gebannt oder nicht gefunden.")
                except discord.Forbidden:
                    print(f"Keine Rechte auf {target_guild.name} zu bannen.")
                except Exception as e:
                    print(f"Fehler auf {guild_id}: {e}")

async def setup(bot):
    await bot.add_cog(UniversalBan(bot))