import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import json
import os

class RolePanelView(discord.ui.View):
    def __init__(self, panel_data):
        super().__init__(timeout=None)
        self.panel_data = panel_data
        self.add_components()

    def add_components(self):
        roles_data = json.loads(self.panel_data['roles'])
        if self.panel_data['type'] == 'buttons':
            for role_info in roles_data:
                btn = discord.ui.Button(
                    label=role_info['label'],
                    emoji=role_info.get('emoji'),
                    style=discord.ButtonStyle(role_info.get('style', 1)),
                    custom_id=f"role_{self.panel_data['name']}_{role_info['id']}"
                )
                btn.callback = self.button_callback
                self.add_item(btn)
        else:
            options = []
            for role_info in roles_data:
                options.append(discord.SelectOption(
                    label=role_info['label'],
                    emoji=role_info.get('emoji'),
                    value=str(role_info['id'])
                ))
            select = discord.ui.Select(
                placeholder="Wähle deine Rollen aus...",
                options=options,
                custom_id=f"select_{self.panel_data['name']}",
                min_values=0,
                max_values=len(options)
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def button_callback(self, interaction: discord.Interaction):
        role_id = int(interaction.data['custom_id'].split('_')[-1])
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("Rolle nicht gefunden.", ephemeral=True)

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Rolle **{role.name}** entfernt.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Rolle **{role.name}** hinzugefügt.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Fehler: Fehlende Berechtigungen.", ephemeral=True)

    async def select_callback(self, interaction: discord.Interaction):
        roles_data = json.loads(self.panel_data['roles'])
        all_role_ids = [r['id'] for r in roles_data]
        selected_ids = [int(v) for v in interaction.data.get('values', [])]

        try:
            to_add = [interaction.guild.get_role(rid) for rid in selected_ids if interaction.guild.get_role(rid)]
            to_remove = [interaction.guild.get_role(rid) for rid in all_role_ids if rid not in selected_ids and interaction.guild.get_role(rid)]

            if to_add: await interaction.user.add_roles(*to_add)
            if to_remove: await interaction.user.remove_roles(*to_remove)

            await interaction.response.send_message("Deine Rollen wurden aktualisiert.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Fehler: Fehlende Berechtigungen.", ephemeral=True)

class RolePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists('data'):
            os.makedirs('data')

    def get_db(self, guild_id):
        conn = sqlite3.connect(f'data/guild_{guild_id}.db')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE IF NOT EXISTS panels (name TEXT PRIMARY KEY, title TEXT, desc TEXT, footer TEXT, type TEXT, channel_id INTEGER, message_id INTEGER, roles TEXT)')
        return conn

    async def cog_load(self):
        for filename in os.listdir('data'):
            if filename.startswith('guild_') and filename.endswith('.db'):
                guild_id = int(filename.split('_')[1].split('.')[0])
                db = self.get_db(guild_id)
                panels = db.execute('SELECT * FROM panels').fetchall()
                for p in panels:
                    self.bot.add_view(RolePanelView(dict(p)))
                db.close()

    async def panel_autocomplete(self, interaction: discord.Interaction, current: str):
        db = self.get_db(interaction.guild_id)
        panels = db.execute('SELECT name FROM panels WHERE name LIKE ?', (f'%{current}%',)).fetchall()
        db.close()
        return [app_commands.Choice(name=p['name'], value=p['name']) for p in panels][:25]

    @app_commands.command(name="setup-rolepanel")
    @app_commands.default_permissions(administrator=True)
    async def setup_rolepanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Rollen-Panel Setup",
            description="Klicke auf den Button unten, um die Basiskonfiguration deines Panels zu starten.",
            color=discord.Color.blue()
        )
        view = discord.ui.View()
        btn = discord.ui.Button(label="Starten", style=discord.ButtonStyle.success)
        btn.callback = lambda i: i.response.send_modal(PanelSetupModal(self))
        view.add_item(btn)
        await interaction.response.send_message(embed=embed, ephemeral=True, view=view)

    @app_commands.command(name="config-rolepanel")
    @app_commands.autocomplete(panelname=panel_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def config_rolepanel(self, interaction: discord.Interaction, panelname: str):
        db = self.get_db(interaction.guild_id)
        panel = db.execute('SELECT * FROM panels WHERE name = ?', (panelname,)).fetchone()
        db.close()
        if not panel:
            return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)
        await interaction.response.send_modal(PanelSetupModal(self, existing_data=dict(panel)))

    @app_commands.command(name="send-rolepanel")
    @app_commands.autocomplete(panelname=panel_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def send_rolepanel(self, interaction: discord.Interaction, panelname: str):
        db = self.get_db(interaction.guild_id)
        p = db.execute('SELECT * FROM panels WHERE name = ?', (panelname,)).fetchone()
        if not p:
            return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)

        panel_data = dict(p)
        channel = interaction.guild.get_channel(panel_data['channel_id']) or interaction.channel
        embed = discord.Embed(title=panel_data['title'], description=panel_data['desc'], color=discord.Color.blue())
        if panel_data['footer']: embed.set_footer(text=panel_data['footer'])

        view = RolePanelView(panel_data)
        msg = await channel.send(embed=embed, view=view)

        db.execute('UPDATE panels SET message_id = ?, channel_id = ? WHERE name = ?', (msg.id, channel.id, panelname))
        db.commit()
        db.close()
        await interaction.response.send_message(f"✅ Panel in {channel.mention} gesendet.", ephemeral=True)

    @app_commands.command(name="delete-rolepanel")
    @app_commands.autocomplete(panelname=panel_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def delete_rolepanel(self, interaction: discord.Interaction, panelname: str):
        db = self.get_db(interaction.guild_id)
        db.execute('DELETE FROM panels WHERE name = ?', (panelname,))
        db.commit()
        db.close()
        await interaction.response.send_message(f"✅ Panel `{panelname}` wurde gelöscht.", ephemeral=True)

class PanelSetupModal(discord.ui.Modal):
    def __init__(self, cog, existing_data=None):
        self.cog = cog
        self.existing_data = existing_data
        super().__init__(title="Konfiguration")

        self.p_name = discord.ui.TextInput(label="Panel-ID (Intern)", default=existing_data['name'] if existing_data else "")
        self.p_title = discord.ui.TextInput(label="Embed Titel", default=existing_data['title'] if existing_data else "")
        self.p_desc = discord.ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph, default=existing_data['desc'] if existing_data else "")
        self.p_footer = discord.ui.TextInput(label="Footer", required=False, default=existing_data['footer'] if existing_data else "")
        self.p_type = discord.ui.TextInput(label="Typ (buttons / dropdown)", placeholder="buttons oder dropdown", default=existing_data['type'] if existing_data else "buttons")

        for item in [self.p_name, self.p_title, self.p_desc, self.p_footer, self.p_type]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        p_type = self.p_type.value.lower()
        if p_type not in ['buttons', 'dropdown']:
            return await interaction.response.send_message("Ungültiger Typ! Bitte 'buttons' oder 'dropdown' eingeben.", ephemeral=True)

        data = {
            'name': self.p_name.value,
            'title': self.p_title.value,
            'desc': self.p_desc.value,
            'footer': self.p_footer.value,
            'type': p_type,
            'old_channel': self.existing_data['channel_id'] if self.existing_data else None,
            'old_message': self.existing_data['message_id'] if self.existing_data else None
        }
        await interaction.response.send_message("Wähle nun Kanäle und Rollen:", view=RoleSelectionView(self.cog, data), ephemeral=True)

class RoleSelectionView(discord.ui.View):
    def __init__(self, cog, data):
        super().__init__()
        self.cog = cog
        self.data = data
        self.roles_list = []

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rolle hinzufügen...")
    async def add_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        if self.data['type'] == 'buttons':
            await interaction.response.send_modal(RoleStyleModal(self, role))
        else:
            await interaction.response.send_modal(RoleStyleModal(self, role, hide_style=True))

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Zielkanal auswählen...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.data['channel_id'] = select.values[0].id
        await interaction.response.edit_message(content=f"✅ Kanal {select.values[0].mention} ausgewählt.", view=self)


    @discord.ui.button(label="Speichern & Senden", style=discord.ButtonStyle.green)
    async def finalize(self, interaction: discord.Interaction, button: discord.ui.Button):
        if 'channel_id' not in self.data:
            return await interaction.response.send_message("Bitte wähle zuerst einen Kanal!", ephemeral=True)

        db = self.cog.get_db(interaction.guild_id)
        self.data['roles'] = json.dumps(self.roles_list)

        embed = discord.Embed(title=self.data['title'], description=self.data['desc'], color=discord.Color.blue())
        if self.data['footer']: embed.set_footer(text=self.data['footer'])

        view = RolePanelView(self.data)
        channel = interaction.guild.get_channel(self.data['channel_id'])
        msg = await channel.send(embed=embed, view=view)

        db.execute('REPLACE INTO panels VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (self.data['name'], self.data['title'], self.data['desc'], self.data['footer'],
                    self.data['type'], self.data['channel_id'], msg.id, self.data['roles']))
        db.commit()
        db.close()
        self.cog.bot.add_view(view)
        await interaction.response.edit_message(content="✅ Panel erfolgreich veröffentlicht!", view=None)

class RoleStyleModal(discord.ui.Modal):
    def __init__(self, parent_view, role, hide_style=False):
        super().__init__(title="Rollen Design")
        self.parent_view = parent_view
        self.role = role
        self.hide_style = hide_style

        self.name = discord.ui.TextInput(label="Anzeige-Name", default=role.name)
        self.emoji = discord.ui.TextInput(label="Emoji (Optional)", required=False)
        self.add_item(self.name)
        self.add_item(self.emoji)

        if not hide_style:
            self.color = discord.ui.TextInput(label="Farbe (blurple, gray, green, red)", default="blurple")
            self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        styles = {"blurple": 1, "gray": 2, "green": 3, "red": 4}
        style_val = 1
        if not self.hide_style:
            style_val = styles.get(self.color.value.lower(), 1)

        self.parent_view.roles_list.append({
            "id": self.role.id,
            "label": self.name.value,
            "emoji": self.emoji.value or None,
            "style": style_val
        })
        await interaction.response.edit_message(content=f"✅ Rolle {self.role.name} hinzugefügt ({len(self.parent_view.roles_list)} Rollen).", view=self.parent_view)

async def setup(bot):
    cog = RolePanel(bot)
    await bot.add_cog(cog)

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Dazu hast du keine Rechte.", ephemeral=True)
        else:
            print(f"Fehler in Command: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Ein interner Fehler ist aufgetreten.", ephemeral=True)