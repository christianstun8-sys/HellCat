import os
import discord
from discord.ext import commands
import dotenv

dotenv.load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()

class HellCat(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="h!", intents=intents, help_command=None)
        os.makedirs("cogs", exist_ok=True)
        os.makedirs("databases", exist_ok=True)
        os.makedirs("data", exist_ok=True)


    async def setup_hook(self):
        done = True

        print("Starte Cogs-Ladevorgang...")
        for filename in os.listdir("cogs"):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                except Exception as e:
                    print(f"❌ Fehler beim Laden von Cog '{filename[:-3]}': {e}")
                    done = False
        if done:
            print("✅ Alle Cogs geladen!")

    async def on_ready(self):
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Macht die Hölle heiß! 😈🔥"))
        print(f"Bot eingeloggt als {self.user}")
        print("------------------------------")

bot = HellCat()
bot.run(TOKEN)
