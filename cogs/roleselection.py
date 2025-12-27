from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Dict, Any, List

class RoleConfigModal(discord.ui.Modal, title='Rollenkonfiguration abschließen'):
    def __init__(self, selected_role: discord.Role, cog_instance: Any):
        super().__init__()
        self.selected_role = selected_role
        self.cog_instance = cog_instance

        self.option_input = discord.ui.TextInput(
            label='1. Optionstext (Im Dropdown sichtbar)',
            placeholder=f'z.B. Wähle {selected_role.name}',
            style=discord.TextStyle.short,
            max_length=100,
            row=0
        )
        self.add_item(self.option_input)

        self.description_input = discord.ui.TextInput(
            label='2. Beschreibung (Tooltip/unter Optionstext)',
            placeholder='z.B. Zeigt an, dass du ein Moderator bist.',
            style=discord.TextStyle.short,
            max_length=100,
            row=1
        )
        self.add_item(self.description_input)

        self.emoji_input = discord.ui.TextInput(
            label='3. Emoji (Unicode oder Custom Emoji ID)',
            placeholder='z.B. 🌟 oder <a:tada:1234567890>',
            style=discord.TextStyle.short,
            max_length=50,
            row=2
        )
        self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        option_name = self.option_input.value.strip()
        option_description = self.description_input.value.strip()
        emoji_text = self.emoji_input.value.strip()

        guild_id_str = str(interaction.guild.id)

        if guild_id_str not in self.cog_instance.server_roles:
            self.cog_instance.server_roles[guild_id_str] = []

        new_role_data = {
            "role_id": self.selected_role.id,
            "role_name": self.selected_role.name,
            "option_name": option_name,
            "option_description": option_description,
            "emoji": emoji_text
        }

        existing_roles = self.cog_instance.server_roles[guild_id_str]
        role_id_to_check = self.selected_role.id

        found_index = -1
        for i, role_entry in enumerate(existing_roles):
            if role_entry["role_id"] == role_id_to_check:
                found_index = i
                break

        if found_index != -1:
            existing_roles[found_index] = new_role_data
            action = "aktualisiert"
        else:
            existing_roles.append(new_role_data)
            action = "konfiguriert"

        self.cog_instance.save_roles_data()

        await interaction.response.send_message(
            f"✅ Die Rolle **{self.selected_role.name}** wurde erfolgreich **{action}**.",
            ephemeral=True
        )

class RoleSelectView(discord.ui.View):
    """View mit dem Dropdown-Menü zur Rollenauswahl durch den Benutzer."""
    def __init__(self, bot: commands.Bot, configured_roles: List[Dict[str, Any]]):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(self._create_role_select(configured_roles))

    def _create_role_select(self, configured_roles: List[Dict[str, Any]]) -> discord.ui.Select:
        """Erstellt das Select-Menü basierend auf den konfigurierten Rollen."""

        options = []
        for role_data in configured_roles:
            options.append(
                discord.SelectOption(
                    label=role_data["option_name"],
                    value=str(role_data["role_id"]),
                    description=role_data["option_description"],
                    emoji=role_data["emoji"]
                )
            )

        select = discord.ui.Select(
            custom_id="role_panel_select",
            placeholder="Wähle deine Rollen aus...",
            min_values=0,
            max_values=len(options),
            options=options
        )
        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: discord.Interaction):
        """Verarbeitet die Rollenauswahl des Benutzers."""

        member = interaction.user
        guild_roles = interaction.guild.roles


        cog = self.bot.get_cog("RolePanel")
        if not cog:
            await interaction.response.send_message("Interner Fehler: Cog 'RolePanel' nicht gefunden.", ephemeral=True)
            return

        configured_role_ids = {int(role["role_id"]) for role in cog.server_roles.get(str(interaction.guild.id), [])}

        selected_role_ids = {int(value) for value in interaction.data['values']}
        current_member_role_ids = {r.id for r in member.roles}

        roles_to_add = []
        roles_to_remove = []

        for role_id in configured_role_ids:
            role = interaction.guild.get_role(role_id)
            if not role:
                continue

            if role_id in selected_role_ids and role_id not in current_member_role_ids:
                roles_to_add.append(role)
            elif role_id not in selected_role_ids and role_id in current_member_role_ids:
                roles_to_remove.append(role)

        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Rolle über Rollenauswahl-Panel hinzugefügt")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Rolle über Rollenauswahl-Panel entfernt")

            feedback = []
            if roles_to_add:
                feedback.append(f"Hinzugefügt: {', '.join([r.name for r in roles_to_add])}")
            if roles_to_remove:
                feedback.append(f"Entfernt: {', '.join([r.name for r in roles_to_remove])}")

            if not feedback:
                await interaction.response.send_message("Deine Rollen sind bereits aktuell!", ephemeral=True)
            else:
                await interaction.response.send_message("Deine Rollen wurden aktualisiert:\n" + "\n".join(feedback), ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("Ich habe keine Berechtigung, Rollen hinzuzufügen/zu entfernen. Bitte überprüfe meine Rollen-Hierarchie.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ein Fehler ist aufgetreten: {e}", ephemeral=True)


class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.BASE_DIR = Path(__file__).parent.parent / "databases"
        self.roles_file = self.BASE_DIR / "roles_data.json"
        self.server_roles = self.load_roles_data()

    def load_roles_data(self):
        """Lädt die gespeicherten Rollen aus der JSON-Datei."""
        if os.path.exists(self.roles_file):
            with open(self.roles_file, "r") as f:
                return {str(k): v for k, v in json.load(f).items()}
        else:
            return {}

    def save_roles_data(self):
        """Speichert die aktuellen Rollen in der JSON-Datei."""
        with open(self.roles_file, "w") as f:
            json.dump(self.server_roles, f, indent=4)

    @app_commands.command(name="config-roles", description="Konfiguriere die Rollen.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_roles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        select = discord.ui.RoleSelect(
            placeholder="Wähle eine Rolle aus der Liste...",
            min_values=1,
            max_values=1
        )

        async def callback(inter: discord.Interaction):
            selected_role = select.values[0]

            if selected_role >= inter.guild.me.top_role:
                await inter.response.send_message("Diese Rolle steht über mir in der Hierarchie!", ephemeral=True)
                return

            await inter.response.send_modal(RoleConfigModal(selected_role, self))

        select.callback = callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.followup.send("Wähle eine Rolle aus, um sie zum Panel hinzuzufügen:", view=view)

    @commands.command(name="sendpanel")
    @commands.has_permissions(administrator=True)
    async def send_role_panel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel

        guild_roles_data = self.server_roles.get(str(ctx.guild.id))

        if not guild_roles_data:
            await ctx.send("❌ **Fehler:** Es sind noch keine Rollen für diesen Server konfiguriert. Bitte benutze `/config-roles` zuerst.", delete_after=10)
            return

        embed = discord.Embed(
            title="➡️ Wähle deine Rollen",
            description="Benutze das Dropdown-Menü, um Rollen hinzuzufügen oder zu entfernen.",
            color=discord.Color.blue()
        )

        view = RoleSelectView(self.bot, guild_roles_data)

        try:
            await channel.send(embed=embed, view=view)
            await ctx.message.delete()
        except discord.Forbidden:
            await ctx.send("❌ Ich kann keine Nachrichten in diesen Kanal senden oder habe keine Berechtigung für Views.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Ein unerwarteter Fehler ist aufgetreten: {e}", delete_after=10)

    @app_commands.command(name="remove-role-config", description="Entfernt eine Rolle aus dem Auswahl-Panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_role_config(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.server_roles or not self.server_roles[guild_id]:
            await interaction.response.send_message("Es sind keine Rollen konfiguriert.", ephemeral=True)
            return

        # Erstelle ein Dropdown mit den bereits konfigurierten Rollen
        options = [
            discord.SelectOption(label=r["role_name"], value=str(r["role_id"]))
            for r in self.server_roles[guild_id]
        ]

        select = discord.ui.Select(placeholder="Wähle die Rolle zum Löschen...", options=options)

        async def callback(inter: discord.Interaction):
            role_id_to_remove = int(select.values[0])

            # Filtere die Liste: Behalte alle Rollen außer der gewählten
            self.server_roles[guild_id] = [
                r for r in self.server_roles[guild_id]
                if r["role_id"] != role_id_to_remove
            ]

            self.save_roles_data()
            await inter.response.send_message(f"✅ Rolle wurde aus der Konfiguration entfernt.", ephemeral=True)

        select.callback = callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Welche Rolle soll aus dem Panel verschwinden?", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RolePanel(bot))