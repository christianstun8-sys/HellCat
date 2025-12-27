import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path
import discord
from discord.ext import commands

import channels  # Deine channels.py

# --- CONFIG ---
BASE_DIR = Path(__file__).parent.parent / "databases"

DB_PATH = os.path.join(BASE_DIR, "applications.db")
MAX_QUESTIONS = 3

pending_questions = {}

# --- DATABASE FUNCTIONS ---
def ensure_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                    user_id INTEGER NOT NULL,
                                                    guild_id INTEGER NOT NULL,
                                                    name TEXT,
                                                    age INTEGER,
                                                    gender TEXT,
                                                    pronoun TEXT,
                                                    goal TEXT,
                                                    status TEXT NOT NULL DEFAULT 'pending',
                                                    admin_message_id INTEGER,
                                                    admin_channel_id INTEGER,
                                                    created_at TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
                                                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                 app_id INTEGER NOT NULL,
                                                 admin_id INTEGER NOT NULL,
                                                 question TEXT NOT NULL,
                                                 answer TEXT,
                                                 asked_at TEXT,
                                                 answered_at TEXT,
                                                 seq INTEGER NOT NULL,
                                                 FOREIGN KEY(app_id) REFERENCES applications(id)
            )
        """
    )
    conn.commit()
    conn.close()

def db_execute(query: str, params: tuple = (), fetch: bool = False):
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute(query, params)
    result = None
    if fetch:
        result = c.fetchall()
    conn.commit()
    conn.close()
    return result

def now_str() -> str:
    return datetime.utcnow().isoformat()

# --- EMBEDS ---
def build_application_embed(user: discord.User, record: dict, qas: List[Tuple[int, str, Optional[str]]]) -> discord.Embed:
    title_map = {
        "pending": "Bewerbung (offen)",
        "accepted": "Bewerbung akzeptiert",
        "declined": "Bewerbung abgelehnt"
    }
    status = record.get("status", "pending")
    title = title_map.get(status, "Bewerbung")
    color_map = {
        "pending": discord.Color.red(),
        "accepted": discord.Color.green(),
        "declined": discord.Color.dark_red()
    }
    color = color_map.get(status, discord.Color.red())

    embed = discord.Embed(
        title=title,
        description=f"{user.mention} ({user.id}) - Bewerbung",
        color=color
    )
    embed.add_field(name="Name", value=record.get("name", "—"), inline=False)
    embed.add_field(name="Alter", value=str(record.get("age", "—")), inline=False)
    embed.add_field(name="Geschlecht", value=record.get("gender", "—"), inline=False)
    embed.add_field(name="Pronomen", value=record.get("pronoun", "—"), inline=False)
    embed.add_field(name="Ziel", value=record.get("goal", "—"), inline=False)

    if qas:
        text_lines = []
        for seq, q, a in qas:
            text_lines.append(f"**Nachfrage {seq}:** {q}")
            if a is not None:
                text_lines.append(f"**Antwort {seq} von {user.name}:** {a}")
        messages = "\n".join(text_lines)
        embed.add_field(name="Nachrichtenverlauf", value=messages[:1024] if len(messages) > 0 else "—", inline=False)
    else:
        embed.add_field(name="Nachrichtenverlauf", value="Keine Rückfragen bisher.", inline=False)

    embed.set_footer(text=f"Angelegt: {record.get('created_at', '')}")
    return embed

# --- MODALS & BUTTONS ---

class AskModal(discord.ui.Modal):
    def __init__(self, admin_id: int, app_id: int, target_user: discord.User, admin_channel_id: int):
        super().__init__(title="Nachfrage an Bewerber senden")
        self.admin_id = admin_id
        self.app_id = app_id
        self.target_user = target_user
        self.admin_channel_id = admin_channel_id

    question = discord.ui.TextInput(
        label="Nachricht an das Mitglied",
        style=discord.TextStyle.long,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        rows = db_execute("SELECT COUNT(*) FROM questions WHERE app_id = ?", (self.app_id,), fetch=True)
        count = rows[0][0] if rows else 0
        if count >= MAX_QUESTIONS:
            return await interaction.response.send_message("Maximale Anzahl an Rückfragen erreicht.", ephemeral=True)

        seq = count + 1
        db_execute(
            "INSERT INTO questions (app_id, admin_id, question, asked_at, seq) VALUES (?, ?, ?, ?, ?)",
            (self.app_id, interaction.user.id, str(self.question.value), now_str(), seq)
        )

        embed = discord.Embed(
            title="Rückfrage zu deiner Bewerbung",
            description=f"Hallo {self.target_user.mention}, ein Admin hat folgende Frage:\n\n> *{self.question.value}*\n\n"
                        f"Bitte antworte in einer Nachricht in dieser DM — deine Antwort wird zu den Admins gesendet.",
            color=discord.Color.orange()
        )
        embed.set_author(name=interaction.user.name, icon_url=getattr(interaction.user.avatar, "url", None))

        try:
            await self.target_user.send(embed=embed)
        except Exception:
            db_execute("DELETE FROM questions WHERE app_id = ? AND seq = ?", (self.app_id, seq))
            return await interaction.response.send_message("User kann keine DMs empfangen.", ephemeral=True)

        pending_questions[self.target_user.id] = self.app_id
        await update_admin_embed_by_app_id(self.app_id, interaction.client)
        await interaction.response.send_message("Nachfrage gesendet.", ephemeral=True)

class AcceptButton(discord.ui.Button):
    def __init__(self, app_id: int):
        super().__init__(label="Akzeptieren", style=discord.ButtonStyle.green, custom_id=f"accept_{app_id}")
        self.app_id = app_id

    async def callback(self, interaction: discord.Interaction):
        app_row = db_execute("SELECT user_id, guild_id FROM applications WHERE id = ?", (self.app_id,), fetch=True)
        if not app_row:
            return await interaction.response.send_message("Bewerbung nicht gefunden.", ephemeral=True)

        user_id, guild_id = app_row[0]
        config = channels.get_config(guild_id)

        if not config or not config.member_role_id:
            return await interaction.response.send_message("Konfiguration für diesen Server fehlt (Rollen-ID).", ephemeral=True)

        db_execute("UPDATE applications SET status = ? WHERE id = ?", ("accepted", self.app_id))

        guild = interaction.client.get_guild(guild_id)
        member = guild.get_member(user_id) if guild else None

        if member:
            role = guild.get_role(config.member_role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Bewerbung akzeptiert")
                except Exception:
                    pass
            try:
                await member.send("Deine Bewerbung wurde akzeptiert! Herzlichen Glückwunsch.")
            except Exception:
                pass

        await update_admin_embed_by_app_id(self.app_id, interaction.client, disable_view=True)
        await interaction.response.send_message("Bewerbung akzeptiert.", ephemeral=True)

class DeclineButton(discord.ui.Button):
    def __init__(self, app_id: int):
        super().__init__(label="Ablehnen", style=discord.ButtonStyle.red, custom_id=f"decline_{app_id}")
        self.app_id = app_id

    async def callback(self, interaction: discord.Interaction):
        db_execute("UPDATE applications SET status = ? WHERE id = ?", ("declined", self.app_id))
        app_row = db_execute("SELECT user_id FROM applications WHERE id = ?", (self.app_id,), fetch=True)

        if app_row:
            user_id = app_row[0][0]
            try:
                user = await interaction.client.fetch_user(user_id)
                await user.send("Deine Bewerbung wurde leider abgelehnt.")
            except Exception:
                pass

        await update_admin_embed_by_app_id(self.app_id, interaction.client, disable_view=True)
        await interaction.response.send_message("Bewerbung abgelehnt.", ephemeral=True)

class AskButton(discord.ui.Button):
    def __init__(self, app_id: int, user_id: int):
        super().__init__(label="Nachfragen", style=discord.ButtonStyle.blurple, custom_id=f"ask_{app_id}")
        self.app_id = app_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        rows = db_execute("SELECT COUNT(*) FROM questions WHERE app_id = ?", (self.app_id,), fetch=True)
        if rows and rows[0][0] >= MAX_QUESTIONS:
            return await interaction.response.send_message("Maximale Rückfragen erreicht.", ephemeral=True)

        app_row = db_execute("SELECT user_id, guild_id, admin_channel_id FROM applications WHERE id = ?", (self.app_id,), fetch=True)
        if not app_row:
            return await interaction.response.send_message("Bewerbung nicht gefunden.", ephemeral=True)

        user_id, guild_id, admin_channel_id = app_row[0]
        try:
            target_user = await interaction.client.fetch_user(user_id)
            modal = AskModal(interaction.user.id, self.app_id, target_user, admin_channel_id)
            await interaction.response.send_modal(modal)
        except Exception:
            await interaction.response.send_message("User konnte nicht gefunden werden.", ephemeral=True)

class AdminDecisionView(discord.ui.View):
    def __init__(self, app_id: int, user_id: int):
        super().__init__(timeout=None)
        self.add_item(AcceptButton(app_id))
        self.add_item(AskButton(app_id, user_id))
        self.add_item(DeclineButton(app_id))

# --- FUNCTIONS ---

async def update_admin_embed_by_app_id(app_id: int, bot_client: commands.Bot, disable_view: bool = False):
    rows = db_execute("SELECT user_id, guild_id, name, age, gender, pronoun, goal, status, admin_channel_id, admin_message_id, created_at FROM applications WHERE id = ?", (app_id,), fetch=True)
    if not rows: return

    user_id, guild_id, name, age, gender, pronoun, goal, status, admin_channel_id, admin_message_id, created_at = rows[0]
    record = {"name": name, "age": age, "gender": gender, "pronoun": pronoun, "goal": goal, "status": status, "created_at": created_at}

    q_rows = db_execute("SELECT seq, question, answer FROM questions WHERE app_id = ? ORDER BY seq ASC", (app_id,), fetch=True)
    qas = [(r[0], r[1], r[2]) for r in q_rows] if q_rows else []

    try:
        user = await bot_client.fetch_user(user_id)
    except Exception:
        user = discord.Object(id=user_id)

    embed = build_application_embed(user, record, qas)
    channel = bot_client.get_channel(admin_channel_id)
    if not channel: return

    try:
        message = await channel.fetch_message(admin_message_id)
        view = AdminDecisionView(app_id, user_id)
        if disable_view:
            for child in view.children: child.disabled = True
        await message.edit(embed=embed, view=view)
    except Exception:
        pass

class ApplicationModal(discord.ui.Modal):
    def __init__(self, guild_config: channels.GuildConfig):
        super().__init__(title="Bewerben zum Beitritt", timeout=300)
        self.config = guild_config

    namequestion = discord.ui.TextInput(label="Name", required=True)
    agequestion = discord.ui.TextInput(label="Alter", required=True, max_length=2, min_length=1)
    genderquestion = discord.ui.TextInput(label="Geschlecht", required=True)
    pronounquestion = discord.ui.TextInput(label="Pronomen", required=True)
    goalquestion = discord.ui.TextInput(label="Welches Ziel hast du hier?", style=discord.TextStyle.long, max_length=1000, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        rows = db_execute("SELECT COUNT(*) FROM applications WHERE user_id = ? AND guild_id = ? AND status = 'pending'", (interaction.user.id, interaction.guild.id), fetch=True)
        if rows and rows[0][0] > 0:
            return await interaction.response.send_message("Du hast bereits eine offene Bewerbung auf diesem Server.", ephemeral=True)

        if not self.agequestion.value.isdigit():
            return await interaction.response.send_message("Bitte gib ein gültiges Alter an.", ephemeral=True)

        age = int(self.agequestion.value)
        created_at = now_str()

        admin_channel = interaction.guild.get_channel(self.config.log_channel_id) # Nutzt log_channel_id oder definiere eigenen admin_channel_id in GuildConfig
        if not admin_channel:
            return await interaction.response.send_message("Admin-Channel nicht konfiguriert.", ephemeral=True)

        db_execute(
            "INSERT INTO applications (user_id, guild_id, name, age, gender, pronoun, goal, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (interaction.user.id, interaction.guild.id, self.namequestion.value, age, self.genderquestion.value, self.pronounquestion.value, self.goalquestion.value, "pending", created_at)
        )

        app_id_row = db_execute("SELECT id FROM applications WHERE user_id = ? AND created_at = ?", (interaction.user.id, created_at), fetch=True)
        app_id = app_id_row[0][0]

        record = {"name": self.namequestion.value, "age": age, "gender": self.genderquestion.value, "pronoun": self.pronounquestion.value, "goal": self.goalquestion.value, "status": "pending", "created_at": created_at}
        embed = build_application_embed(interaction.user, record, [])

        view = AdminDecisionView(app_id, interaction.user.id)
        admin_message = await admin_channel.send(embed=embed, view=view)

        db_execute("UPDATE applications SET admin_message_id = ?, admin_channel_id = ? WHERE id = ?", (admin_message.id, admin_channel.id, app_id))
        await interaction.response.send_message("Deine Bewerbung wurde abgeschickt! ✅", ephemeral=True)

class SubmitButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="👉 Bewerben 👈", style=discord.ButtonStyle.green, custom_id="submit_application_button")

    async def callback(self, interaction: discord.Interaction):
        config = channels.get_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message("Dieser Server ist nicht im System registriert.", ephemeral=True)

        await interaction.response.send_modal(ApplicationModal(config))

class SubmitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SubmitButton())

class DMListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.guild or msg.author.bot: return

        app_id = pending_questions.get(msg.author.id)
        if not app_id: return

        rows = db_execute("SELECT id, seq FROM questions WHERE app_id = ? AND answer IS NULL ORDER BY seq ASC", (app_id,), fetch=True)
        if not rows:
            pending_questions.pop(msg.author.id, None)
            return

        q_id, seq = rows[0]
        db_execute("UPDATE questions SET answer = ?, answered_at = ? WHERE id = ?", (msg.content, now_str(), q_id))

        app_row = db_execute("SELECT admin_channel_id FROM applications WHERE id = ?", (app_id,), fetch=True)
        if app_row:
            channel = self.bot.get_channel(app_row[0][0])
            if channel:
                await channel.send(f"📩 Antwort von <@{msg.author.id}> zu Nachfrage {seq}: {msg.content}")

        await update_admin_embed_by_app_id(app_id, self.bot)

        remaining = db_execute("SELECT COUNT(*) FROM questions WHERE app_id = ? AND answer IS NULL", (app_id,), fetch=True)
        if not remaining or remaining[0][0] == 0:
            pending_questions.pop(msg.author.id, None)

class JoinApplicationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        ensure_db()
        self.bot.add_view(SubmitView())

        pending_apps = db_execute("SELECT id, user_id FROM applications WHERE status = 'pending' AND admin_message_id IS NOT NULL", fetch=True)
        for app_id, user_id in pending_apps:
            self.bot.add_view(AdminDecisionView(app_id, user_id))

    @commands.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def panel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Join-Anfrage 📫",
            description="Um Zugriff auf den Server zu erhalten, klicke bitte auf den Button unten und fülle die Bewerbung aus.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, view=SubmitView())

async def setup(bot):
    await bot.add_cog(JoinApplicationCog(bot))
    await bot.add_cog(DMListener(bot))