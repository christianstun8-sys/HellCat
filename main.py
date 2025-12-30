import os
import discord
from discord.ext import commands
import dotenv

beta = False
crashed = False

dotenv.load_dotenv()
if beta:
    TOKEN = os.getenv("DISCORD_BETA_TOKEN")
elif beta == False:
    TOKEN = os.getenv("DISCORD_TOKEN")
else:
    print("Beta Function not defined. Stopping...")
    crashed = True

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

        if beta:
            synced = await self.tree.sync()
            print(f"[BETA] Erfolgreich {len(synced)} Slash-Befehle synchronisiert")

    async def on_ready(self):
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Macht die Hölle heiß! 😈🔥"))
        print(f"Bot eingeloggt als {self.user}")
        print("------------------------------")

if not crashed:
    bot = HellCat()
    bot.run(TOKEN)
