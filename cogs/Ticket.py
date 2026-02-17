from pathlib import Path
import discord
import discord.app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import io
from channels import get_config

# --- HILFSFUNKTIONEN (angepasst auf übergebene DB) ---

async def get_ticket_data(db: aiosqlite.Connection, channel_id: int):
    async with db.execute("SELECT user_id, status, claimed_by FROM tickets WHERE channel_id = ?", (channel_id,)) as cursor:
        return await cursor.fetchone()

async def create_transcript(channel: discord.TextChannel):
    transcript_text = f"Transkript für Ticket: {channel.name}\n"
    transcript_text += f"ID: {channel.id}\n"
    transcript_text = "-" * 30 + "\n\n"

    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        content = message.content

        if message.embeds:
            for embed in message.embeds:
                embed_info = f"[Embed: {embed.title if embed.title else ''} - {embed.description if embed.description else ''}]"
                content += f"\n{embed_info}"

        transcript_text += f"[{timestamp}] {message.author}: {content}\n"

    return io.BytesIO(transcript_text.encode('utf-8'))

async def log_to_channel(bot, guild, embed, file=None):
    config = get_config(guild.id)
    if config:
        log_channel = bot.get_channel(config.log_channel_id)
        if log_channel:
            await log_channel.send(embed=embed, file=file)

async def move_ticket_category(channel: discord.TextChannel, status: str, claimed_by_id: int = None):
    config = get_config(channel.guild.id)
    if not config:
        return

    category_id = None
    if status == 'geschlossen':
        category_id = config.CLOSED_CATEGORY_ID
    elif status == 'offen':
        if claimed_by_id:
            category_id = config.CLAIMED_CATEGORY_ID
        else:
            category_id = config.OPEN_CATEGORY_ID

    if category_id:
        category = channel.guild.get_channel(category_id)
        if category and isinstance(category, discord.CategoryChannel):
            await channel.edit(category=category)

# --- VIEWS ---

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="✅ Ja, löschen", style=discord.ButtonStyle.red, custom_id="confirm_delete_button")
    async def confirm_delete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_ticket_data(self.db, interaction.channel_id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Dieses Ticket existiert nicht mehr in der Datenbank.", ephemeral=True)

        await interaction.response.send_message("Ticket wird in 5 Sekunden gelöscht...", ephemeral=True)
        channel = interaction.channel
        transcript_file = await create_transcript(channel)
        file = discord.File(transcript_file, filename=f"transcript-{channel.name}.txt")

        log_embed = discord.Embed(
            title="Ticket Gelöscht",
            description=f"Ticket **{channel.name}** wurde von {interaction.user.mention} gelöscht.",
            color=discord.Color.dark_red()
        )

        await asyncio.sleep(5)
        await self.db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel.id,))
        await self.db.commit()

        await log_to_channel(interaction.client, interaction.guild, log_embed, file=file)
        await channel.delete()

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.green, custom_id="cancel_delete_button")
    async def cancel_delete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="✅ Löschvorgang abgebrochen", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)

class ClosedTicketView(discord.ui.View):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="🔓 Wieder öffnen", style=discord.ButtonStyle.green, custom_id="ticket_open_button")
    async def open_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast nicht die Berechtigung, dieses Ticket zu öffnen!", ephemeral=True)

        channel = interaction.channel
        ticket_data = await get_ticket_data(self.db, channel.id)

        if not ticket_data:
            return await interaction.response.send_message("❌ Fehler: Ticket nicht in der Datenbank gefunden.", ephemeral=True)
        if ticket_data[1] == 'offen':
            return await interaction.response.send_message("⚠️ Dieses Ticket ist bereits geöffnet.", ephemeral=True)

        overwrites_to_update = {}
        for target, permissions in channel.overwrites.items():
            if isinstance(target, (discord.Member, discord.User, discord.Role)) and permissions.read_messages:
                overwrites_to_update[target] = discord.PermissionOverwrite(
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True
                )

        for target, overwrite in overwrites_to_update.items():
            await channel.set_permissions(target, overwrite=overwrite)

        await self.db.execute("UPDATE tickets SET status = ? WHERE channel_id = ?", ('offen', channel.id))
        await self.db.commit()

        await move_ticket_category(channel, 'offen')

        log_embed = discord.Embed(
            title="Ticket Wiedereröffnet",
            description=f"Ticket {channel.mention} wurde von {interaction.user.mention} wieder geöffnet.",
            color=discord.Color.green()
        )
        await log_to_channel(interaction.client, interaction.guild, log_embed)

        embed = discord.Embed(title="🔓 Ticket wieder geöffnet", description=f"{interaction.user.mention} hat das Ticket geöffnet!", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=embed, view=OpenTicketView(self.db))

    @discord.ui.button(label="⛔ Löschen", style=discord.ButtonStyle.red, custom_id="delete_ticket_button")
    async def delete_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast nicht die Berechtigung, dieses Ticket zu löschen!", ephemeral=True)

        embed = discord.Embed(
            title="❗ Bist du sicher?",
            description="Diese Aktion kann **nicht** rückgängig gemacht werden. Der Channel wird permanent gelöscht.",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmDeleteView(self.db), ephemeral=True)

class OpenTicketView(discord.ui.View):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.red, custom_id="ticket_close_button")
    async def close_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast nicht die Berechtigung, dieses Ticket zu schließen.", ephemeral=True)

        channel = interaction.channel
        ticket_data = await get_ticket_data(self.db, channel.id)

        if not ticket_data:
            return await interaction.response.send_message("❌ Fehler: Ticket nicht in der Datenbank gefunden.", ephemeral=True)
        if ticket_data[1] == 'geschlossen':
            return await interaction.response.send_message("⚠️ Dieses Ticket ist bereits geschlossen.", ephemeral=True)

        config = get_config(interaction.guild.id)
        if not config:
            return await interaction.response.send_message("❌ Fehler: Konfiguration für diesen Server nicht gefunden.", ephemeral=True)

        overwrites_to_update = {}
        for target, permissions in channel.overwrites.items():
            is_team_or_bot = isinstance(target, discord.Role) and target.id == config.team_role_id or target.id == interaction.guild.me.id
            if not is_team_or_bot and permissions.send_messages:
                overwrites_to_update[target] = discord.PermissionOverwrite(
                    send_messages=False,
                    read_messages=True,
                    read_message_history=True
                )

        user_id = ticket_data[0]
        member = interaction.guild.get_member(user_id)
        if member and member not in overwrites_to_update:
            overwrites_to_update[member] = discord.PermissionOverwrite(
                send_messages=False,
                read_messages=True,
                read_message_history=True
            )

        for target, overwrite in overwrites_to_update.items():
            await channel.set_permissions(target, overwrite=overwrite)

        await self.db.execute("UPDATE tickets SET status = ?, claimed_by = NULL WHERE channel_id = ?", ('geschlossen', channel.id))
        await self.db.commit()

        await move_ticket_category(channel, 'geschlossen')

        log_embed = discord.Embed(
            title="Ticket Geschlossen",
            description=f"Ticket {channel.mention} wurde von {interaction.user.mention} geschlossen.",
            color=discord.Color.orange()
        )
        await log_to_channel(interaction.client, interaction.guild, log_embed)

        embed = discord.Embed(
            title="🔒 Ticket geschlossen",
            description=f"{interaction.user.mention} hat das Ticket geschlossen.",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed, view=ClosedTicketView(self.db))

class TicketClaimView(discord.ui.View):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="👍 Claim", style=discord.ButtonStyle.secondary, custom_id="ticket_claim_button")
    async def claim_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast nicht die Berechtigung, dieses Ticket zu claimen.", ephemeral=True)

        ticket_data = await get_ticket_data(self.db, interaction.channel.id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Fehler: Ticket nicht in der Datenbank gefunden.", ephemeral=True)

        if ticket_data[1] != 'offen':
            return await interaction.response.send_message("⚠️ Nur offene Tickets können geclaimt werden.", ephemeral=True)

        claimed_by_id = ticket_data[2]
        new_claimed_by_id = None

        if claimed_by_id is None:
            new_claimed_by_id = interaction.user.id
            await self.db.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (new_claimed_by_id, interaction.channel.id))
            embed = discord.Embed(description=f"{interaction.user.mention} hat dieses Ticket geclaimt.", color=discord.Color.dark_red())
            await move_ticket_category(interaction.channel, 'offen', claimed_by_id=new_claimed_by_id)

            log_embed = discord.Embed(
                title="Ticket Geclaimt",
                description=f"Ticket {interaction.channel.mention} wurde von {interaction.user.mention} geclaimt.",
                color=discord.Color.blue()
            )
            await log_to_channel(interaction.client, interaction.guild, log_embed)

        elif claimed_by_id == interaction.user.id:
            await self.db.execute("UPDATE tickets SET claimed_by = NULL WHERE channel_id = ?", (interaction.channel.id,))
            embed = discord.Embed(description=f"{interaction.user.mention} hat den Claim für dieses Ticket entfernt.", color=discord.Color.dark_red())
            await move_ticket_category(interaction.channel, 'offen', claimed_by_id=None)

            log_embed = discord.Embed(
                title="Ticket Unclaimed",
                description=f"{interaction.user.mention} hat den Claim für {interaction.channel.mention} aufgehoben.",
                color=discord.Color.light_grey()
            )
            await log_to_channel(interaction.client, interaction.guild, log_embed)

        else:
            claimer = interaction.guild.get_member(claimed_by_id)
            return await interaction.response.send_message(f"Dieses Ticket ist bereits von {claimer.mention if claimer else 'einem Teammitglied'} geclaimt.", ephemeral=True)

        await self.db.commit()
        await interaction.response.send_message(embed=embed)

class TicketCreateView(discord.ui.View):
    def __init__(self, db: aiosqlite.Connection):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="✉️ Ticket erstellen", style=discord.ButtonStyle.green, custom_id="ticket_create_button")
    async def create_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        config = get_config(interaction.guild.id)
        if not config:
            return await interaction.followup.send("Fehler: Konfiguration für diesen Server nicht gefunden.", ephemeral=True)

        async with self.db.execute("SELECT channel_id FROM tickets WHERE user_id = ? AND status = ?", (interaction.user.id, 'offen')) as cursor:
            existing_ticket = await cursor.fetchone()

        if existing_ticket:
            return await interaction.followup.send(f"Du hast bereits ein offenes Ticket: <#{existing_ticket[0]}>", ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(config.OPEN_CATEGORY_ID)
        if not category:
            return await interaction.followup.send("Fehler: Die Kategorie für offene Tickets wurde nicht gefunden.", ephemeral=True)

        op = interaction.user
        team_role = guild.get_role(config.team_role_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            op: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            team_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)
        }

        channel_name = f"ticket-{interaction.user.name}"
        new_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)

        await self.db.execute(
            "INSERT INTO tickets (channel_id, user_id, status) VALUES (?, ?, ?)",
            (new_channel.id, interaction.user.id, 'offen')
        )
        await self.db.commit()

        embed = discord.Embed(
            title=f"Willkommen, {interaction.user.display_name}!",
            description="Bitte beschreibe dein Anliegen so detailliert wie möglich. Ein Teammitglied wird sich in Kürze um dich kümmern.",
            color=discord.Color.dark_red()
        )
        log_embed = discord.Embed(
            title="Neues Ticket!",
            description=f"{interaction.user.mention} ({interaction.user.id}) hat ein neues Ticket erstellt: {new_channel.mention}",
            color=discord.Color.dark_red()
        )

        await new_channel.send(embed=embed, view=OpenTicketView(self.db), content=f"{interaction.user.mention}")
        await new_channel.send(view=TicketClaimView(self.db))
        await interaction.followup.send(f"Dein Ticket wurde erstellt: {new_channel.mention}", ephemeral=True)
        await log_to_channel(interaction.client, interaction.guild, log_embed)

# --- COGS ---

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.tickets_db

    async def cog_load(self):
        await self.init_db()
        self.bot.add_view(TicketCreateView(self.db))
        self.bot.add_view(OpenTicketView(self.db))
        self.bot.add_view(ClosedTicketView(self.db))
        self.bot.add_view(ConfirmDeleteView(self.db))
        self.bot.add_view(TicketClaimView(self.db))

    async def init_db(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                                                   channel_id INTEGER PRIMARY KEY,
                                                   user_id INTEGER NOT NULL,
                                                   status TEXT NOT NULL,
                                                   claimed_by INTEGER
            )
            """
        )
        await self.db.commit()

    @commands.command(name="ticket-panel")
    @commands.has_permissions(manage_messages=True)
    async def ticketpanel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Ticket erstellen",
            description="Klicke auf den Button, um ein neues Ticket zu erstellen und unser Team zu kontaktieren.",
            color=discord.Color.dark_red()
        )
        await ctx.send(embed=embed, view=TicketCreateView(self.db))

class AddMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.tickets_db

    @discord.app_commands.command(name="ticket-addmember", description="Fügt einen Benutzer zum aktuellen Ticket hinzu.")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def ticket_add_member(self, interaction: discord.Interaction, member: discord.Member):
        channel = interaction.channel
        ticket_data = await get_ticket_data(self.db, channel.id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Dieser Befehl kann nur in einem registrierten Ticket-Kanal verwendet werden.", ephemeral=True)

        overwrites = channel.overwrites_for(member)
        overwrites.read_messages = True
        overwrites.send_messages = True

        await channel.set_permissions(member, overwrite=overwrites)
        await interaction.response.send_message(f"{member.mention} wurde dem Ticket erfolgreich hinzugefügt.")

        log_embed = discord.Embed(
            title="Mitglied Hinzugefügt",
            description=f"{interaction.user.mention} hat {member.mention} zum Ticket {channel.mention} hinzugefügt.",
            color=discord.Color.blue()
        )
        await log_to_channel(self.bot, interaction.guild, log_embed)

class RemoveMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.tickets_db

    @discord.app_commands.command(name="ticket-removemember", description="Entfernt einen Nutzer aus dem aktuellen Ticket.")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    async def ticket_remove_member(self, interaction: discord.Interaction, member: discord.Member):
        channel = interaction.channel
        ticket_data = await get_ticket_data(self.db, channel.id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Dieser Befehl kann nur in einem registrierten Ticket-Kanal verwendet werden.", ephemeral=True)

        overwrites = channel.overwrites_for(member)
        overwrites.read_messages = False
        overwrites.send_messages = False

        await channel.set_permissions(member, overwrite=overwrites)
        await interaction.response.send_message(f"{member.mention} wurde vom Ticket erfolgreich entfernt.")

        log_embed = discord.Embed(
            title="Mitglied Entfernt",
            description=f"{interaction.user.mention} hat {member.mention} aus dem Ticket {channel.mention} entfernt.",
            color=discord.Color.blue()
        )
        await log_to_channel(self.bot, interaction.guild, log_embed)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
    await bot.add_cog(AddMember(bot))
    await bot.add_cog(RemoveMember(bot))