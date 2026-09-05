import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import asyncio
import datetime

# ---------------------------------------------------------
# DEVELOPER / SUPER ADMIN ID
# ---------------------------------------------------------
MY_USER_ID = 1313370345851457569

# ---------------------------------------------------------
# JSON DATABASE SETUP
# ---------------------------------------------------------
DATA_FILE = "anti_nuke_configs.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_nuke_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "is_enabled": False,
            "punishment": "STRIP", # STRIP, KICK, BAN
            "threshold_count": 3,
            "threshold_time": 10,
            "whitelist": [],
            "protections": {
                "ban": True,
                "channel": True,
                "role": True,
                "bot": True,
                "webhook": True
            },
            "anti_spam": {
                "enabled": False,
                "max_msg": 5,
                "time_window": 5
            }
        }
        save_data(data)
    return data[g_id]

def save_nuke_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

# ---------------------------------------------------------
# IN-MEMORY TRACKERS (For Nuke & Spam)
# ---------------------------------------------------------
active_strikes = {}  # For Admin Anti-Nuke
spam_tracker = {}    # For Chat Anti-Spam

def add_strike(tracker_dict, guild_id: int, user_id: int, time_window: int) -> int:
    current_time = time.time()
    if guild_id not in tracker_dict:
        tracker_dict[guild_id] = {}
    if user_id not in tracker_dict[guild_id]:
        tracker_dict[guild_id][user_id] = []
        
    tracker_dict[guild_id][user_id] = [
        t for t in tracker_dict[guild_id][user_id] 
        if current_time - t <= time_window
    ]
    tracker_dict[guild_id][user_id].append(current_time)
    return len(tracker_dict[guild_id][user_id])

def clear_strikes(tracker_dict, guild_id: int, user_id: int):
    if guild_id in tracker_dict and user_id in tracker_dict[guild_id]:
        tracker_dict[guild_id][user_id] = []

# ---------------------------------------------------------
# DASHBOARD EMBED GENERATOR
# ---------------------------------------------------------
def get_nuke_embed(config):
    embed = discord.Embed(title="🛡️ Ultimate Security Dashboard", color=discord.Color.from_str("#2b2d31"))
    
    status = "✅ Active" if config['is_enabled'] else "❌ Disabled"
    punish = "🔴 BAN" if config['punishment'] == "BAN" else "🟠 KICK" if config['punishment'] == "KICK" else "🟡 STRIP ROLES"
    embed.add_field(name="📌 Anti-Nuke Status", value=f"**Status:** {status}\n**Punishment:** {punish}\n**Limit:** {config['threshold_count']} actions in {config['threshold_time']}s", inline=False)
    
    p = config['protections']
    p_text = (
        f"**Mass Ban/Kick:** {'✅' if p['ban'] else '❌'}\n"
        f"**Channel Nuke:** {'✅' if p['channel'] else '❌'}\n"
        f"**Role Nuke:** {'✅' if p['role'] else '❌'}\n"
        f"**Anti-Bot Add:** {'✅' if p['bot'] else '❌'}\n"
        f"**Anti-Webhook:** {'✅' if p['webhook'] else '❌'}"
    )
    embed.add_field(name="🔒 Nuke Protections", value=p_text, inline=True)
    
    s = config['anti_spam']
    spam_stat = "✅ Active" if s['enabled'] else "❌ Disabled"
    embed.add_field(name="💬 Anti-Spam", value=f"**Status:** {spam_stat}\n**Limit:** {s['max_msg']} msgs in {s['time_window']}s\n**Action:** 5 Min Timeout", inline=True)
    
    wl_count = len(config['whitelist'])
    embed.add_field(name="🛡️ Whitelist", value=f"**{wl_count}** Users bypassed\n*(Owners & Dev auto-bypassed)*", inline=False)
    
    return embed

# ---------------------------------------------------------
# MODALS & VIEWS
# ---------------------------------------------------------
class ProtectionsModal(discord.ui.Modal, title="🔒 Nuke Protections (yes/no)"):
    p_ban = discord.ui.TextInput(label="Anti Mass Ban & Kick", style=discord.TextStyle.short)
    p_chan = discord.ui.TextInput(label="Anti Channel Delete", style=discord.TextStyle.short)
    p_role = discord.ui.TextInput(label="Anti Role Delete", style=discord.TextStyle.short)
    p_bot = discord.ui.TextInput(label="Anti Malicious Bot Add", style=discord.TextStyle.short)
    p_web = discord.ui.TextInput(label="Anti Webhook Create", style=discord.TextStyle.short)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        p = config['protections']
        self.p_ban.default = "yes" if p['ban'] else "no"
        self.p_chan.default = "yes" if p['channel'] else "no"
        self.p_role.default = "yes" if p['role'] else "no"
        self.p_bot.default = "yes" if p['bot'] else "no"
        self.p_web.default = "yes" if p['webhook'] else "no"

    async def on_submit(self, interaction: discord.Interaction):
        self.config['protections']['ban'] = self.p_ban.value.strip().lower() == "yes"
        self.config['protections']['channel'] = self.p_chan.value.strip().lower() == "yes"
        self.config['protections']['role'] = self.p_role.value.strip().lower() == "yes"
        self.config['protections']['bot'] = self.p_bot.value.strip().lower() == "yes"
        self.config['protections']['webhook'] = self.p_web.value.strip().lower() == "yes"
        save_nuke_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_nuke_embed(self.config), view=AntiNukeView(self.guild_id))

class NukeLimitsModal(discord.ui.Modal, title="⚙️ Nuke Limits (Threshold)"):
    act_count = discord.ui.TextInput(label="Max Actions Allowed", style=discord.TextStyle.short)
    time_win = discord.ui.TextInput(label="Time Window (Seconds)", style=discord.TextStyle.short)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        self.act_count.default = str(config['threshold_count'])
        self.time_win.default = str(config['threshold_time'])

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config['threshold_count'] = int(self.act_count.value)
            self.config['threshold_time'] = int(self.time_win.value)
        except: pass
        save_nuke_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_nuke_embed(self.config), view=AntiNukeView(self.guild_id))

class AntiSpamModal(discord.ui.Modal, title="💬 Anti-Spam Settings"):
    spam_status = discord.ui.TextInput(label="Enable Anti-Spam? (yes/no)", style=discord.TextStyle.short)
    max_msg = discord.ui.TextInput(label="Max Messages", style=discord.TextStyle.short)
    time_win = discord.ui.TextInput(label="Time Window (Seconds)", style=discord.TextStyle.short)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        s = config['anti_spam']
        self.spam_status.default = "yes" if s['enabled'] else "no"
        self.max_msg.default = str(s['max_msg'])
        self.time_win.default = str(s['time_window'])

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config['anti_spam']['enabled'] = self.spam_status.value.strip().lower() == "yes"
            self.config['anti_spam']['max_msg'] = int(self.max_msg.value)
            self.config['anti_spam']['time_window'] = int(self.time_win.value)
        except: pass
        save_nuke_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_nuke_embed(self.config), view=AntiNukeView(self.guild_id))


class PunishmentSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="Choose Nuke Auto-Punishment",
        options=[
            discord.SelectOption(label="Strip Roles", description="Removes all admin roles (Safest)", value="STRIP", emoji="🟡"),
            discord.SelectOption(label="Kick", description="Kicks the user from server", value="KICK", emoji="🟠"),
            discord.SelectOption(label="Ban", description="Bans the user permanently", value="BAN", emoji="🔴")
        ], row=0)
    async def select_punish(self, interaction: discord.Interaction, select: discord.ui.Select):
        config = get_nuke_config(self.guild_id)
        config['punishment'] = select.values[0]
        save_nuke_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_nuke_embed(config), view=AntiNukeView(self.guild_id))

class WhitelistUserView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select a User to Add/Remove from Whitelist", row=0)
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        config = get_nuke_config(self.guild_id)
        user_id = str(select.values[0].id)
        
        if user_id in config['whitelist']:
            config['whitelist'].remove(user_id)
            msg = f"➖ Removed <@{user_id}> from Whitelist."
        else:
            config['whitelist'].append(user_id)
            msg = f"➕ Added <@{user_id}> to Whitelist."
            
        save_nuke_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_nuke_embed(config), view=AntiNukeView(self.guild_id))
        await interaction.followup.send(msg, ephemeral=True)


# ---------------------------------------------------------
# DASHBOARD VIEW (Compact 2 Rows)
# ---------------------------------------------------------
class AntiNukeView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_nuke_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable Security"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable Security"
            self.btn_toggle.style = discord.ButtonStyle.success

    # ROW 0
    @discord.ui.button(label="🔒 Nuke Protections", style=discord.ButtonStyle.primary, row=0)
    async def btn_prot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ProtectionsModal(self.guild_id, get_nuke_config(self.guild_id)))

    @discord.ui.button(label="⚙️ Nuke Limits", style=discord.ButtonStyle.primary, row=0)
    async def btn_limits(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NukeLimitsModal(self.guild_id, get_nuke_config(self.guild_id)))

    @discord.ui.button(label="⚖️ Punishment", style=discord.ButtonStyle.primary, row=0)
    async def btn_punish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=PunishmentSelectView(self.guild_id))

    # ROW 1
    @discord.ui.button(label="💬 Anti-Spam", style=discord.ButtonStyle.primary, row=1)
    async def btn_spam(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AntiSpamModal(self.guild_id, get_nuke_config(self.guild_id)))

    @discord.ui.button(label="🛡️ Whitelist", style=discord.ButtonStyle.secondary, row=1)
    async def btn_wl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=WhitelistUserView(self.guild_id))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=1)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_nuke_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_nuke_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_nuke_embed(config), view=AntiNukeView(self.guild_id))


# ---------------------------------------------------------
# MAIN COG & CORE LOGIC
# ---------------------------------------------------------
class AntiNukeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="security_setup", description="Open the Ultimate Anti-Nuke & Spam Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def security_setup(self, interaction: discord.Interaction):
        # ONLY Server Owner AND Developer (You) can open this dashboard
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.response.send_message("❌ Only the Server Owner or Bot Developer can configure Security!", ephemeral=True)
            return
            
        config = get_nuke_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_nuke_embed(config), view=AntiNukeView(interaction.guild.id), ephemeral=True)

    # ==========================================
    # 1. ANTI-SPAM LOGIC 
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.id == self.bot.user.id: return
        
        config = get_nuke_config(message.guild.id)
        if not config['is_enabled'] or not config.get('anti_spam', {}).get('enabled', False): return
        
        # Bypasses: Whitelist, Server Owner, and YOU (Bot Developer)
        if str(message.author.id) in config['whitelist'] or message.author.id == message.guild.owner_id or message.author.id == MY_USER_ID: return

        s_config = config['anti_spam']
        strikes = add_strike(spam_tracker, message.guild.id, message.author.id, s_config['time_window'])
        
        if strikes >= s_config['max_msg']:
            clear_strikes(spam_tracker, message.guild.id, message.author.id)
            try:
                await message.channel.purge(limit=s_config['max_msg'], check=lambda m: m.author == message.author)
                timeout_duration = datetime.timedelta(minutes=5)
                await message.author.timeout(timeout_duration, reason="Anti-Spam Triggered")
                alert = await message.channel.send(f"⚠️ {message.author.mention} has been **muted for 5 minutes** for spamming!")
                await alert.delete(delay=5)
            except discord.Forbidden:
                pass


    # ==========================================
    # 2. ANTI-NUKE LOGIC
    # ==========================================
    async def process_nuke_action(self, guild: discord.Guild, action_type: discord.AuditLogAction, protection_key: str):
        config = get_nuke_config(guild.id)
        if not config['is_enabled'] or not config['protections'][protection_key]: return
        await asyncio.sleep(1) # API Delay
        
        try:
            async for entry in guild.audit_logs(limit=1, action=action_type):
                user = entry.user
                
                # Bypasses: Bot itself, Server Owner, YOU (Bot Developer), and Whitelisted users
                if not user or user.id == self.bot.user.id or user.id == guild.owner_id or user.id == MY_USER_ID or str(user.id) in config['whitelist']: return

                strikes = add_strike(active_strikes, guild.id, user.id, config['threshold_time'])
                if strikes >= config['threshold_count']:
                    await self.execute_nuke_punishment(guild, user, config)
                    clear_strikes(active_strikes, guild.id, user.id)
                break
        except Exception as e: print(f"Anti-Nuke Error: {e}")

    async def execute_nuke_punishment(self, guild: discord.Guild, user: discord.Member, config: dict):
        try:
            member = guild.get_member(user.id)
            if not member: return

            punishment = config['punishment']
            reason = "Automated Anti-Nuke System Triggered"

            if punishment == "STRIP":
                roles = [role for role in member.roles if role.name != "@everyone" and not role.is_default()]
                await member.remove_roles(*roles, reason=reason)
            elif punishment == "KICK":
                await member.kick(reason=reason)
            elif punishment == "BAN":
                await member.ban(reason=reason)
        except Exception: pass

    # --- EVENTS MONITORED ---
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.process_nuke_action(channel.guild, discord.AuditLogAction.channel_delete, 'channel')

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.process_nuke_action(role.guild, discord.AuditLogAction.role_delete, 'role')

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.process_nuke_action(guild, discord.AuditLogAction.ban, 'ban')

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await self.process_nuke_action(channel.guild, discord.AuditLogAction.webhook_create, 'webhook')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = get_nuke_config(member.guild.id)
        if member.bot and config['is_enabled'] and config['protections']['bot']:
            await asyncio.sleep(1)
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    user = entry.user
                    
                    # Bypasses for Anti-Bot Add
                    if user.id == member.guild.owner_id or user.id == MY_USER_ID or str(user.id) in config['whitelist']: return
                    
                    try: await member.kick(reason="Unauthorized Bot")
                    except: pass
                    
                    strikes = add_strike(active_strikes, member.guild.id, user.id, config['threshold_time'])
                    if strikes >= config['threshold_count']:
                        await self.execute_nuke_punishment(member.guild, user, config)
                        clear_strikes(active_strikes, member.guild.id, user.id)
                    break

async def setup(bot):
    await bot.add_cog(AntiNukeCog(bot))
    
