import os
import discord
from discord.ext import commands
import dotenv

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_PREFIX"] = "hdev!"

# --- Beta Config ---
beta = False
# -------------------

crashed = False

dotenv.load_dotenv()
if beta == True:
    TOKEN = os.getenv("DISCORD_BETA_TOKEN")
elif beta == False:
    TOKEN = os.getenv("DISCORD_TOKEN")
else:
    print("Beta Function not defined. Stopping...")
    crashed = True

intents = discord.Intents.all()

class HellCat(commands.Bot):
    def __init__(self):
        async def dynamic_prefix(bot, message):
            prefixes = ["h!"]
            if await bot.is_owner(message.author):
                prefixes.append("hdev!")
            return prefixes

        super().__init__(command_prefix=dynamic_prefix, intents=intents, help_command=None)
        os.makedirs("cogs", exist_ok=True)
        os.makedirs("databases", exist_ok=True)
        os.makedirs("data", exist_ok=True)

    async def setup_hook(self):
        @self.command(name="restart", hidden=True)
        async def restart_cmd(ctx):
            if await self.is_owner(ctx.author):
                await ctx.send("⌛ Starte neu...")
                await self.close()
            else:
                return

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

        try:
            await self.load_extension('jishaku')
            jsk = self.get_command('jsk')
            if jsk:
                jsk.hidden = True
            print("✅ Jishaku erfolgreich geladen!")
        except Exception as e:
            print(f"Fehler beim Laden von Jishaku: {e}")

        if beta:
            synced = await self.tree.sync()
            print(f"[BETA] Erfolgreich {len(synced)} Slash-Befehle synchronisiert")

    async def on_ready(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Macht die Hölle heiß! 😈🔥"))
        print(f"Bot eingeloggt als {self.user}")
        print("------------------------------")

if not crashed:
    bot = HellCat()
    bot.run(TOKEN)