import discord
from discord.ext import commands


class deleteintroduction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        if guild.id != 1363137083148865598:
            return

        introduction_channel_id = 1363178643622199567
        introduction_channel = guild.get_channel(introduction_channel_id)

        async for message in introduction_channel.history(limit=100):
            if message.author.id == member.id:
                try:
                    await message.delete()
                except discord.Forbidden:
                    print(f"I don't have permission to delete the message in channel {introduction_channel.name} by {member.name}.")