from pathlib import Path

import discord
from discord.ext import commands
from discord import ui
import aiosqlite
import time
import asyncio

import channels


vote_cooldowns = {}
BASE_DIR = Path(__file__).parent.parent / "databases"
DB_DIR = BASE_DIR / "suggestions.db"

async def init_db():
    async with aiosqlite.connect(DB_DIR) as db:
        await db.execute("""
                         CREATE TABLE IF NOT EXISTS votes (
                                                              message_id INTEGER,
                                                              user_id INTEGER,
                                                              vote INTEGER,
                                                              PRIMARY KEY (message_id, user_id)
                         )
                         """)
        await db.commit()

async def update_vote(interaction: discord.Interaction, message_id: int, new_vote: int):
    uid = interaction.user.id
    now = time.time()

    if uid in vote_cooldowns and now - vote_cooldowns[uid] < 10:
        remaining = int(10 - (now - vote_cooldowns[uid]))
        return await interaction.response.send_message(
            f"Bitte warte **{remaining} Sekunden**, bevor du erneut votest.",
            ephemeral=True
        )

    vote_cooldowns[uid] = now

    async with aiosqlite.connect(DB_DIR) as db:
        if new_vote == 0:
            await db.execute(
                "DELETE FROM votes WHERE message_id=? AND user_id=?",
                (message_id, uid)
            )
        else:
            await db.execute("""
                             INSERT INTO votes (message_id, user_id, vote)
                             VALUES (?, ?, ?)
                             ON CONFLICT(message_id, user_id)
                             DO UPDATE SET vote=excluded.vote
                             """, (message_id, uid, new_vote))

        await db.commit()

        async with db.execute("SELECT vote FROM votes WHERE message_id=?", (message_id,)) as cursor:
            rows = await cursor.fetchall()
            upvotes = sum(1 for r in rows if r[0] == 1)
            downvotes = sum(1 for r in rows if r[0] == -1)

    embed = interaction.message.embeds[0]
    embed.set_field_at(
        0,
        name="",
        value=f"👍Upvotes: **{upvotes}**\n👎Downvotes: **{downvotes}**",
        inline=False
    )

    await interaction.message.edit(embed=embed)
    await interaction.response.send_message("Deine Stimme wurde gespeichert!", ephemeral=True)


class UpvoteButton(ui.Button):
    def __init__(self):
        super().__init__(label="⬆️ Upvote", style=discord.ButtonStyle.success, custom_id="vote_up")

    async def callback(self, interaction):
        message_id = interaction.message.id
        await update_vote(interaction, message_id, 1)


class RemoveVoteButton(ui.Button):
    def __init__(self):
        super().__init__(label="🤷 Vote entfernen", style=discord.ButtonStyle.secondary, custom_id="vote_remove")

    async def callback(self, interaction):
        message_id = interaction.message.id
        await update_vote(interaction, message_id, 0)


class DownvoteButton(ui.Button):
    def __init__(self):
        super().__init__(label="⬇️ Downvote", style=discord.ButtonStyle.danger, custom_id="vote_down")

    async def callback(self, interaction):
        message_id = interaction.message.id
        await update_vote(interaction, message_id, -1)


class AcceptButton(ui.Button):
    def __init__(self):
        super().__init__(label="✅ Annehmen", style=discord.ButtonStyle.success, custom_id="vote_accept")

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

        embed = interaction.message.embeds[0]
        embed.title = "Vorschlag angenommen"
        embed.color = discord.Color.green()

        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Der Vorschlag wurde angenommen.", ephemeral=True)


class RejectButton(ui.Button):
    def __init__(self):
        super().__init__(label="❌ Ablehnen", style=discord.ButtonStyle.danger, custom_id="vote_reject")

    async def callback(self, interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

        embed = interaction.message.embeds[0]
        embed.title = "Vorschlag abgelehnt"
        embed.color = discord.Color.dark_red()

        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Der Vorschlag wurde abgelehnt.", ephemeral=True)


class VoteView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(UpvoteButton())
        self.add_item(RemoveVoteButton())
        self.add_item(DownvoteButton())
        self.add_item(AcceptButton())
        self.add_item(RejectButton())


class SuggestionForm(ui.Modal):
    def __init__(self):
        super().__init__(title="Vorschlag zum Voting einreichen")

        self.suggestion = ui.TextInput(
            label="Vorschlag",
            placeholder="Bitte beschreibe deinen Vorschlag so detailliert wie möglich.",
            style=discord.TextStyle.long,
            required=True
        )

        self.anonym = ui.TextInput(
            label="Anonym?",
            placeholder="Willst du anonym sein? Schreibe 'Ja' oder 'Nein'.",
            style=discord.TextStyle.short,
            required=True,
            min_length=2,
            max_length=4
        )

        self.add_item(self.suggestion)
        self.add_item(self.anonym)

    async def on_submit(self, interaction: discord.Interaction):
        suggestion = self.suggestion.value
        anonym = self.anonym.value.lower()

        embed = discord.Embed(
            title="Neuer Vorschlag",
            description=f"*,,{suggestion}''*",
            color=discord.Color.orange()
        )

        if anonym == "nein":
            embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.avatar.url,
                url=f"https://discord.com/users/{interaction.user.id}"
            )

        embed.add_field(
            name="",
            value="👍Upvotes: **0**\n👎Downvotes: **0**",
            inline=False
        )
        config = channels.get_config(interaction.guild_id)
        voting_channel_id = config.vote_channel_id
        channel = interaction.guild.get_channel(voting_channel_id)
        msg = await channel.send(embed=embed)
        await msg.edit(view=VoteView())

        await interaction.response.send_message(
            "Dein Vorschlag wurde erfolgreich eingereicht!", ephemeral=True
        )


class ModalButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="Vorschlag einreichen",
            style=discord.ButtonStyle.success,
            custom_id="modal_open",
            emoji="📫"
        )

    async def callback(self, interaction):
        await interaction.response.send_modal(SuggestionForm())


class ModalButtonView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ModalButton())


class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(ModalButtonView())
        bot.add_view(VoteView())
        bot.loop.create_task(init_db())

    @commands.command(name="panel-suggestion")
    @commands.has_permissions(administrator=True)
    async def panel_suggestion(self, ctx):

        config = channels.get_config(ctx.guild.id)
        if not config or not config.member_role_id:
            ctx.send("❌ Fehler: Server wurde nicht richtig konfiguiert!", delete_after=10)
            asyncio.sleep(10)
            ctx.message.delete()

        voting_channel_id = config.vote_channel_id

        embed = discord.Embed(
            title="Vorschlag zum Voting einreichen",
            description=(
                "Hey! 👋\n"
                "Du hast Verbesserungswünsche für den Server? Dann drücke unten auf den Button, "
                "um das Formular zu öffnen und deinen Vorschlag einzureichen!\n\n"
                f"Anschließend wird dein Vorschlag zu einem Voting in den Kanal <#{voting_channel_id}> gesendet.\n"
                "Dort können alle Mitglieder deinen Vorschlag ansehen und abstimmen.\n\n"
                "Sollte er der Community gefallen, sind die Chancen höher, dass er umgesetzt wird. Viel Glück! 🥳"
            ),
            color=discord.Color.dark_red()
        )

        await ctx.send(embed=embed, view=ModalButtonView())


async def setup(bot):
    await bot.add_cog(Panel(bot))