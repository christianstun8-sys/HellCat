import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import aiosqlite
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

import channels

class LeaderboardView(discord.ui.View):
    def __init__(self, cog, total_users, interaction, embed_color):
        super().__init__(timeout=180)
        self.cog = cog
        self.total_users = total_users
        self.interaction = interaction
        self.embed_color = embed_color
        self.current_page = 0
        self.users_per_page = 10
        self.max_pages = (total_users + self.users_per_page - 1) // self.users_per_page

        if self.max_pages <= 1:
            self.children[0].disabled = True
            self.children[1].disabled = True
        else:
            self.children[0].disabled = True

    @discord.ui.button(label="← Zurück", style=discord.ButtonStyle.blurple)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("Du kannst nicht mit dem Leaderboard eines anderen interagieren.", ephemeral=True)
        self.current_page -= 1
        await self.update_leaderboard(interaction)

    @discord.ui.button(label="Weiter →", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("Du kannst nicht mit dem Leaderboard eines anderen interagieren.", ephemeral=True)
        self.current_page += 1
        await self.update_leaderboard(interaction)

    async def update_leaderboard(self, interaction: discord.Interaction):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1
        offset = self.current_page * self.users_per_page
        new_embed = await self.cog._create_leaderboard_embed(interaction.guild, offset, self.users_per_page, self.total_users)
        await interaction.response.edit_message(embed=new_embed, view=self)

    async def on_timeout(self):
        try:
            message = await self.interaction.original_response()
            await message.edit(view=None)
        except:
            pass

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_dir = Path(__file__).parent.parent / "databases"
        self.db_name = self.db_dir / 'levels.db'
        self.db = None

        self.MESSAGE_XP = 1
        self.VOICE_XP_PER_MINUTE = 2
        self.MAX_MESSAGES_PER_DAY = 200
        self.MAX_VOICE_MINUTES_PER_DAY = 180
        self.STREAK_XP_BONUS_MULTIPLIER = 10

        self.data_base_path = Path(__file__).parent.parent / "data"
        self.RANK_CARD_BACKGROUND_PATH = self.data_base_path / "rank_card_background.png"
        self.FONT_PATH = self.data_base_path / "arial.ttf"

        self.bot.loop.create_task(self.setup_db())
        self.voice_xp_task.start()


    async def setup_db(self):
        self.db = await aiosqlite.connect(self.db_name)
        await self.db.execute("""
                              CREATE TABLE IF NOT EXISTS levels (
                                                                    guild_id INTEGER NOT NULL,
                                                                    user_id INTEGER NOT NULL,
                                                                    xp INTEGER DEFAULT 0,
                                                                    level INTEGER DEFAULT 0,
                                                                    daily_messages INTEGER DEFAULT 0,
                                                                    daily_voice_minutes INTEGER DEFAULT 0,
                                                                    last_update_date TEXT,
                                                                    current_streak INTEGER DEFAULT 0,
                                                                    last_streak_date TEXT,
                                                                    PRIMARY KEY (guild_id, user_id)
                                  )
                              """)
        await self.db.commit()

    def xp_needed_for_level(self, level):
        return 5 * (level ** 2) + (50 * level) + 100

    def get_xp_multiplier(self):
        return 2 if datetime.now().weekday() >= 5 else 1

    async def _get_user_data_and_reset_daily_limits(self, guild_id, user_id):
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        async with self.db.execute("""
                                   SELECT xp, level, daily_messages, daily_voice_minutes, last_update_date, current_streak, last_streak_date
                                   FROM levels WHERE guild_id = ? AND user_id = ?
                                   """, (guild_id, user_id)) as cursor:
            row = await cursor.fetchone()

        if not row:
            await self.db.execute("""
                                  INSERT INTO levels (guild_id, user_id, last_update_date, current_streak, last_streak_date)
                                  VALUES (?, ?, ?, 0, ?)
                                  """, (guild_id, user_id, today, yesterday))
            return 0, 0, 0, 0, 0, yesterday

        xp, level, daily_messages, daily_voice_minutes, last_update_date, current_streak, last_streak_date = row
        if last_update_date != today:
            daily_messages, daily_voice_minutes = 0, 0
            await self.db.execute("""
                                  UPDATE levels SET daily_messages = 0, daily_voice_minutes = 0, last_update_date = ?
                                  WHERE guild_id = ? AND user_id = ?
                                  """, (today, guild_id, user_id))

        return xp, level, daily_messages, daily_voice_minutes, current_streak, last_streak_date

    async def _check_and_assign_level_role(self, member: discord.Member, new_level: int):
        """Weist dynamisch die höchste verfügbare Levelrolle basierend auf channels.py zu."""
        config = channels.get_config(member.guild.id)
        if not config or not member.guild.me.guild_permissions.manage_roles:
            return

        server_roles = {
            100: config.lvl100,
            50: config.lvl50,
            25: config.lvl25,
            10: config.lvl10
        }
        all_role_ids = [r_id for r_id in server_roles.values() if r_id]

        target_role_id = None
        for lvl in sorted(server_roles.keys(), reverse=True):
            if new_level >= lvl and server_roles[lvl]:
                target_role_id = server_roles[lvl]
                break

        member_role_ids = {role.id for role in member.roles}
        roles_to_remove = [member.guild.get_role(rid) for rid in all_role_ids
                           if rid != target_role_id and rid in member_role_ids]

        if roles_to_remove:
            await member.remove_roles(*[r for r in roles_to_remove if r], reason="Alte Levelrolle entfernen")

        if target_role_id and target_role_id not in member_role_ids:
            target_role = member.guild.get_role(target_role_id)
            if target_role:
                await member.add_roles(target_role, reason=f"Level {new_level} erreicht")

    async def send_level_up_message(self, member: discord.Member, new_level: int):
        config = channels.get_config(member.guild.id)
        if not config or not config.levelup_channel_id:
            return

        channel = self.bot.get_channel(config.levelup_channel_id)
        if channel:
            embed = discord.Embed(
                title="🎉 Levelaufstieg!",
                description=f"{member.mention} ist auf **Level {new_level}** aufgestiegen!",
                color=discord.Color.dark_red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await channel.send(embed=embed)
            except:
                pass

    async def _update_xp_and_counters(self, guild_id, user_id, xp, level, xp_to_add, new_msg_count, new_vc_minutes, new_streak, new_last_streak_date):
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id) if guild else None

        new_xp = xp + xp_to_add
        new_level = level
        level_up = False

        while new_xp >= self.xp_needed_for_level(new_level):
            new_xp -= self.xp_needed_for_level(new_level)
            new_level += 1
            level_up = True

        today = datetime.now().strftime('%Y-%m-%d')
        await self.db.execute("""
                              UPDATE levels SET xp = ?, level = ?, daily_messages = ?, daily_voice_minutes = ?,
                                                last_update_date = ?, current_streak = ?, last_streak_date = ?
                              WHERE guild_id = ? AND user_id = ?
                              """, (new_xp, new_level, new_msg_count, new_vc_minutes, today, new_streak, new_last_streak_date, guild_id, user_id))

        if level_up and member:
            await self.send_level_up_message(member, new_level)
            await self._check_and_assign_level_role(member, new_level)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not self.db:
            return

        guild_id, user_id = message.guild.id, message.author.id
        xp_multiplier = self.get_xp_multiplier()
        xp, level, daily_messages, daily_voice_minutes, current_streak, last_streak_date = await self._get_user_data_and_reset_daily_limits(guild_id, user_id)

        new_streak, new_last_streak_date, streak_bonus = current_streak, last_streak_date, 0

        if daily_messages < self.MAX_MESSAGES_PER_DAY:
            if daily_messages == 0:
                today_date = datetime.now().date()
                last_streak_dt = datetime.strptime(last_streak_date, '%Y-%m-%d').date()
                yesterday = today_date - timedelta(days=1)

                if last_streak_dt == yesterday:
                    new_streak += 1
                elif last_streak_dt < yesterday:
                    new_streak = 1
                new_last_streak_date = today_date.strftime('%Y-%m-%d')

                if new_streak > 1:
                    streakembed = discord.Embed(
                        title="🔥 Streak verlängert!",
                        description=f"{message.author.mention} hat jetzt einen **Streak von {new_streak} Tagen**!",
                        color=discord.Color.dark_red()
                    )
                    streakembed.set_thumbnail(url=message.author.display_avatar.url)
                    await message.channel.send(embed=streakembed)
                    streak_bonus = new_streak * self.STREAK_XP_BONUS_MULTIPLIER

            xp_to_add = (self.MESSAGE_XP * xp_multiplier) + streak_bonus
            await self._update_xp_and_counters(guild_id, user_id, xp, level, xp_to_add, daily_messages + 1, daily_voice_minutes, new_streak, new_last_streak_date)
            await self.db.commit()

    @tasks.loop(minutes=1)
    async def voice_xp_task(self):
        if not self.db or not self.bot.is_ready():
            return

        xp_multiplier = self.get_xp_multiplier()
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.voice and member.voice.channel and not member.bot and not member.voice.self_mute:
                    xp, level, dm, dvm, streak, lsd = await self._get_user_data_and_reset_daily_limits(guild.id, member.id)
                    if dvm < self.MAX_VOICE_MINUTES_PER_DAY:
                        await self._update_xp_and_counters(guild.id, member.id, xp, level, self.VOICE_XP_PER_MINUTE * xp_multiplier, dm, dvm + 1, streak, lsd)
        await self.db.commit()

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

    async def _create_leaderboard_embed(self, guild, offset, limit, total_users):
        async with self.db.execute("""
                                   SELECT user_id, xp, level FROM levels WHERE guild_id = ?
                                   ORDER BY level DESC, xp DESC LIMIT ? OFFSET ?
                                   """, (guild.id, limit, offset)) as cursor:
            top_users = await cursor.fetchall()

        leaderboard_msg = ""
        for index, (u_id, u_xp, u_lvl) in enumerate(top_users):
            member = guild.get_member(u_id)
            name = member.display_name if member else f"User {u_id}"
            leaderboard_msg += f"**#{offset + index + 1}.** {name} - **Level {u_lvl}** ({u_xp} XP)\n"

        embed = discord.Embed(title="🏆 Server Leaderboard", description=leaderboard_msg or "Keine Daten.", color=discord.Color.dark_red())
        embed.set_footer(text=f"Seite {(offset // limit) + 1}/{(total_users + limit - 1) // limit}")
        return embed

    @discord.app_commands.command(name="leaderboard", description="Zeigt das Level-Ranking an.")
    async def leaderboard_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with self.db.execute("SELECT COUNT(*) FROM levels WHERE guild_id = ?", (interaction.guild_id,)) as cursor:
            total = (await cursor.fetchone())[0]

        if total == 0:
            return await interaction.followup.send("Noch keine Daten vorhanden.")

        embed = await self._create_leaderboard_embed(interaction.guild, 0, 10, total)
        await interaction.followup.send(embed=embed, view=LeaderboardView(self, total, interaction, discord.Color.dark_red()))

    async def _create_rank_card(self, username, avatar_bytes, current_xp, required_xp, level, streak):
        WIDTH, HEIGHT = 1278, 852
        img = Image.new("RGBA", (WIDTH, HEIGHT), (30, 30, 30, 255))

        if self.RANK_CARD_BACKGROUND_PATH.exists():
            img = Image.open(self.RANK_CARD_BACKGROUND_PATH).convert("RGBA").resize((WIDTH, HEIGHT))

        draw = ImageDraw.Draw(img)

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((260, 260))
        img.paste(avatar, (100, HEIGHT // 2 - 130), avatar.split()[3])

        try:
            font = ImageFont.truetype(str(self.FONT_PATH), 50)
            small_font = ImageFont.truetype(str(self.FONT_PATH), 35)
        except OSError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            print(f"WARNUNG: Schriftart nicht unter {self.FONT_PATH} gefunden!")

        draw.text((420, 300), f"{username}", font=font, fill="white")
        draw.text((420, 370), f"Level {level} | Streak: {streak} Tage", font=small_font, fill=(200, 200, 200))

        bar_x, bar_y, bar_w, bar_h = 420, 450, 600, 500
        draw.rounded_rectangle((bar_x, 450, bar_x + 600, 500), radius=25, fill=(60, 60, 60))

        progress = min(current_xp / required_xp, 1.0)
        if progress > 0:
            draw.rounded_rectangle((bar_x, 450, bar_x + int(600 * progress), 500), radius=25, fill=(120, 190, 255))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @discord.app_commands.command(name="rank", description="Zeigt deinen Level-Fortschritt an.")
    async def rank_command(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        user = member or interaction.user
        xp, lvl, dm, dvm, streak, lsd = await self._get_user_data_and_reset_daily_limits(interaction.guild_id, user.id)

        card = await self._create_rank_card(user.display_name, await user.display_avatar.read(), xp, self.xp_needed_for_level(lvl), lvl, streak)
        await interaction.followup.send(file=discord.File(card, filename="rank.png"))

    async def cog_unload(self):
        self.voice_xp_task.cancel()
        if self.db:
            await self.db.close()

async def setup(bot):
    await bot.add_cog(Leveling(bot))