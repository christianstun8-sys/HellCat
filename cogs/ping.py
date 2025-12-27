import discord
from discord.ext import commands
from discord import app_commands
import time
import aiosqlite


class SystemCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Zeigt die aktuelle Latenz des Bots an.")
    async def ping_command(self, interaction: discord.Interaction):
        discord_latency_ms = round(self.bot.latency * 1000)
        start_time = time.perf_counter()
        await interaction.response.defer(thinking=True, ephemeral=True)

        db_start_time = time.perf_counter()
        db_latency_ms = "Fehler"

        try:
            db: aiosqlite.Connection = getattr(self.bot, 'db', None)

            if db:
                await db.execute("SELECT 1")
                await db.commit()
                db_end_time = time.perf_counter()
                db_latency_ms = round((db_end_time - db_start_time) * 1000)
            else:
                db_latency_ms = "Nicht verbunden"

        except Exception as e:
            db_latency_ms = f"DB-Fehler: {type(e).__name__}"

        end_time = time.perf_counter()
        processing_latency_ms = round((end_time - start_time) * 1000)

        embed = discord.Embed(
            title="⏱️ Ping-Ergebnisse",
            description="Latenzzeiten des Bots zu verschiedenen Komponenten:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🤖 Interne Verarbeitung",
            value=f"`{processing_latency_ms}ms`",
            inline=True
        )
        embed.add_field(
            name="🌐 Discord API (Heartbeat)",
            value=f"`{discord_latency_ms}ms`",
            inline=True
        )
        embed.add_field(
            name="💾 Datenbank (aiosqlite)",
            value=f"`{db_latency_ms}ms`",
            inline=True
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SystemCommands(bot))