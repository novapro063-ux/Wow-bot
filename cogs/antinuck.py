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
            "whitelisted_users": {},
            "whitelisted_roles": {},
            "protections": {
                "ban": True,
                "channel": True,
                "role": True,
                "bot": True,
                "webhook": True
            },
            "nuke_limits": {
                "max_actions": 3,
                "time_window": 10
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
# IN-MEMORY TRACKERS (For Spam & Nuke Limits)
# ---------------------------------------------------------
spam_tracker = {}
nuke_tracker = {}

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

# ---------------------------------------------------------
# PERMISSION EVALUATOR (Hybrid System)
# ---------------------------------------------------------
def evaluate_permission(member: discord.Member, action_key: str, config: dict) -> str:
    if member.id == MY_USER_ID or member.id == member.guild.owner_id:
        return "WHITELISTED"
        
    user_id_str = str(member.id)
    if user_id_str in config.get("whitelisted_users", {}):
        if config["whitelisted_users"][user_id_str].get(action_key, False):
            return "WHITELISTED"
            
    for role in member.roles:
        role_id_str = str(role.id)
        if role_id_str in config.get("whitelisted_roles", {}):
            if config["whitelisted_roles"][role_id_str].get(action_key, False):
                return "WHITELISTED"
                
    perms = member.guild_permissions
    if action_key == 'ban' and perms.ban_members: return "NATIVE"
    if action_key == 'channel' and perms.manage_channels: return "NATIVE"
    if action_key == 'role' and perms.manage_roles: return "NATIVE"
    if action_key == 'webhook' and perms.manage_webhooks: return "NATIVE"
    if action_key == 'bot' and (perms.manage_guild or perms.administrator): return "NATIVE"
        
    return "DENIED"

# ---------------------------------------------------------
# EMBED GENERATORS
# ---------------------------------------------------------
def get_nuke_embed(config):
    embed = discord.Embed(title="🛡️ Ultimate Hybrid Security Dashboard", color=discord.Color.from_str("#2b2d31"))
    
    status = "✅ Active" if config['is_enabled'] else "❌ Disabled"
    limit_info = f"{config['nuke_limits']['max_actions']} actions / {config['nuke_limits']['time_window']}s"
    
    embed.add_field(name="📌 Anti-Nuke Status", value=f"**Status:** {status}\n**Punishment:** 🔴 BAN\n**Native Perms Limit:** {limit_info}", inline=False)
    
    p = config['protections']
    p_text = (
        f"**Anti Mass Ban/Kick:** {'✅' if p['ban'] else '❌'}\n"
        f"**Anti Channel Nuke:** {'✅' if p['channel'] else '❌'}\n"
        f"**Anti Role Nuke:** {'✅' if p['role'] else '❌'}\n"
        f"**Anti Bot & Apps:** {'✅' if p['bot'] else '❌'}\n"
        f"**Anti Webhook Nuke:** {'✅' if p['webhook'] else '❌'}"
    )
    embed.add_field(name="🔒 Global Protections", value=p_text, inline=True)
    
    s = config['anti_spam']
    spam_stat = "✅ Active" if s['enabled'] else "❌ Disabled"
    embed.add_field(name="💬 Anti-Spam", value=f"**Status:** {spam_stat}\n**Limit:** {s['max_msg']} msgs / {s['time_window']}s\n**Action:** 5 Min Timeout", inline=True)
    
    embed.add_field(name="🛡️ Trust Levels", value="🟩 **Dashboard Whitelist:** Unlimited bypass.\n🟨 **Discord Admins:** Rate-limited by config.\n🟥 **No Perms:** Instant Ban.", inline=False)
    
    return embed

def get_permissions_embed(target_name, target_type):
    embed = discord.Embed(title=f"⚙️ Configure Permissions for {target_type.capitalize()}", color=discord.Color.blue())
    embed.description = f"**Target:** {target_name}\n\nUse the dropdown menu below to explicitly allow actions (Bypasses all limits).\n✅ **Selected** = Unlimited Access\n❌ **Unselected** = Relies on Discord limits"
    return embed

# ---------------------------------------------------------
# MODALS
# ---------------------------------------------------------
class ProtectionsModal(discord.ui.Modal, title="🔒 Global Protections (yes/no)"):
    p_ban = discord.ui.TextInput(label="Anti Mass Ban & Kick", style=discord.TextStyle.short)
    p_chan = discord.ui.TextInput(label="Anti Channel Delete", style=discord.TextStyle.short)
    p_role = discord.ui.TextInput(label="Anti Role Delete", style=discord.TextStyle.short)
    p_bot = discord.ui.TextInput(label="Anti Malicious Bot/App", style=discord.TextStyle.short)
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

class NukeLimitsModal(discord.ui.Modal, title="⚙️ Native Admin Limits"):
    act_count = discord.ui.TextInput(label="Max Actions (before ban)", style=discord.TextStyle.short)
    time_win = discord.ui.TextInput(label="Time Window (Seconds)", style=discord.TextStyle.short)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        l = config.get('nuke_limits', {"max_actions": 3, "time_window": 10})
        self.act_count.default = str(l['max_actions'])
        self.time_win.default = str(l['time_window'])

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config['nuke_limits']['max_actions'] = int(self.act_count.value)
            self.config['nuke_limits']['time_window'] = int(self.time_win.value)
            save_nuke_config(self.guild_id, self.config)
        except: pass
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

# ---------------------------------------------------------
# UI VIEWS (DASHBOARD & PERMISSIONS)
# ---------------------------------------------------------
class GranularPermissionsView(discord.ui.View):
    def __init__(self, guild_id: int, target_id: str, target_type: str, target_name: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.target_id = target_id
        self.target_type = target_type
        self.target_name = target_name
        self.db_key = "whitelisted_users" if target_type == "user" else "whitelisted_roles"
        
        self.setup_menu()

    def setup_menu(self):
        config = get_nuke_config(self.guild_id)
        if self.target_id not in config[self.db_key]:
            config[self.db_key][self.target_id] = {"ban": False, "channel": False, "role": False, "bot": False, "webhook": False}
        perms = config[self.db_key][self.target_id]

        options = [
            discord.SelectOption(label="Allow Ban & Kick", value="ban", description="Bypass ban/kick limits", default=perms.get("ban", False), emoji="🔨"),
            discord.SelectOption(label="Allow Manage Channels", value="channel", description="Bypass channel delete limits", default=perms.get("channel", False), emoji="📁"),
            discord.SelectOption(label="Allow Manage Roles", value="role", description="Bypass role delete limits", default=perms.get("role", False), emoji="🛡️"),
            discord.SelectOption(label="Allow Adding Bots/Apps", value="bot", description="Bypass bot invite limits", default=perms.get("bot", False), emoji="🤖"),
            discord.SelectOption(label="Allow Webhooks", value="webhook", description="Bypass webhook limits", default=perms.get("webhook", False), emoji="🔗")
        ]

        select = discord.ui.Select(
            placeholder="Select permissions to explicitly allow...",
            min_values=0,
            max_values=5,
            options=options,
            row=0
        )
        select.callback = self.select_callback
        self.add_item(select)
        
        btn_back = discord.ui.Button(label="⬅️ Back to Dashboard", style=discord.ButtonStyle.secondary, row=1)
        btn_back.callback = self.back_callback
        self.add_item(btn_back)

    async def select_callback(self, interaction: discord.Interaction):
        config = get_nuke_config(self.guild_id)
        selected_values = interaction.data.get('values', [])
        
        config[self.db_key][self.target_id] = {
            "ban": "ban" in selected_values,
            "channel": "channel" in selected_values,
            "role": "role" in selected_values,
            "bot": "bot" in selected_values,
            "webhook": "webhook" in selected_values
        }
        save_nuke_config(self.guild_id, config)
        
        # UI রিফ্রেশ করা হচ্ছে যাতে সিলেকশন সেভ থাকে
        self.clear_items()
        self.setup_menu()
        await interaction.response.edit_message(view=self)

    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=get_nuke_embed(get_nuke_config(self.guild_id)), view=AntiNukeView(self.guild_id))

class TargetSelectView(discord.ui.View):
    def __init__(self, guild_id: int, select_type: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        
        if select_type == "user":
            select = discord.ui.UserSelect(placeholder="Search and select a User...", row=0)
            select.callback = self.user_callback
        else:
            select = discord.ui.RoleSelect(placeholder="Search and select a Role...", row=0)
            select.callback = self.role_callback
            
        self.add_item(select)
        
        btn_back = discord.ui.Button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=1)
        btn_back.callback = self.back_callback
        self.add_item(btn_back)

    async def user_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=get_permissions_embed(f"<@{interaction.data['values'][0]}>", "user"), 
            view=GranularPermissionsView(self.guild_id, str(interaction.data['values'][0]), "user", f"<@{interaction.data['values'][0]}>")
        )

    async def role_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=get_permissions_embed(f"<@&{interaction.data['values'][0]}>", "role"), 
            view=GranularPermissionsView(self.guild_id, str(interaction.data['values'][0]), "role", f"<@&{interaction.data['values'][0]}>")
        )

    async def back_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=get_nuke_embed(get_nuke_config(self.guild_id)), view=AntiNukeView(self.guild_id))

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

    @discord.ui.button(label="Toggle Status", custom_id="btn_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_nuke_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_nuke_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_nuke_embed(config), view=AntiNukeView(self.guild_id))

    @discord.ui.button(label="🔒 Protections", style=discord.ButtonStyle.primary, row=0)
    async def btn_prot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ProtectionsModal(self.guild_id, get_nuke_config(self.guild_id)))

    @discord.ui.button(label="⚙️ Limits (For Admins)", style=discord.ButtonStyle.primary, row=0)
    async def btn_limits(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NukeLimitsModal(self.guild_id, get_nuke_config(self.guild_id)))

    @discord.ui.button(label="👤 User Bypass", style=discord.ButtonStyle.secondary, row=1)
    async def btn_user_wl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=None, content="Select a user:", view=TargetSelectView(self.guild_id, "user"))

    @discord.ui.button(label="🛡️ Role Bypass", style=discord.ButtonStyle.secondary, row=1)
    async def btn_role_wl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=None, content="Select a role:", view=TargetSelectView(self.guild_id, "role"))

    @discord.ui.button(label="💬 Anti-Spam", style=discord.ButtonStyle.secondary, row=1)
    async def btn_spam(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AntiSpamModal(self.guild_id, get_nuke_config(self.guild_id)))

# ---------------------------------------------------------
# MAIN COG & CORE LOGIC
# ---------------------------------------------------------
class AntiNukeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="security_setup", description="Open the Ultimate Hybrid Anti-Nuke Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def security_setup(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            return await interaction.response.send_message("❌ Only the Server Owner or Bot Developer can configure Security!", ephemeral=True)
        await interaction.response.send_message(embed=get_nuke_embed(get_nuke_config(interaction.guild.id)), view=AntiNukeView(interaction.guild.id), ephemeral=True)

    # ==========================================
    # CORE ANTI-NUKE PROCESSOR
    # ==========================================
    async def process_nuke_action(self, guild: discord.Guild, action_type: discord.AuditLogAction, protection_key: str):
        config = get_nuke_config(guild.id)
        if not config.get('is_enabled', False) or not config['protections'][protection_key]: return
        await asyncio.sleep(1.5)
        
        try:
            async for entry in guild.audit_logs(limit=1, action=action_type):
                user = entry.user
                if not user or user.id == self.bot.user.id: return
                member = guild.get_member(user.id)
                if not member: return

                perm_level = evaluate_permission(member, protection_key, config)

                if perm_level == "WHITELISTED":
                    return
                
                elif perm_level == "DENIED":
                    try: await member.ban(reason=f"Strict Anti-Nuke: Unauthorized action -> {protection_key}")
                    except discord.Forbidden: pass

                elif perm_level == "NATIVE":
                    limits = config.get('nuke_limits', {"max_actions": 3, "time_window": 10})
                    strikes = add_strike(nuke_tracker, guild.id, user.id, limits['time_window'])
                    if strikes >= limits['max_actions']:
                        try: await member.ban(reason=f"Anti-Nuke: Exceeded {protection_key} limit ({limits['max_actions']} in {limits['time_window']}s)")
                        except discord.Forbidden: pass
                break
        except Exception: pass

    # ==========================================
    # EVENT LISTENERS
    # ==========================================
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
    async def on_integration_create(self, integration):
        await self.process_nuke_action(integration.guild, discord.AuditLogAction.integration_create, 'bot')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = get_nuke_config(member.guild.id)
        if member.bot and config.get('is_enabled', False) and config['protections']['bot']:
            await asyncio.sleep(1.5)
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    user = entry.user
                    inviter = member.guild.get_member(user.id)
                    if not inviter or inviter.id == self.bot.user.id: return
                    
                    perm_level = evaluate_permission(inviter, 'bot', config)
                    
                    if perm_level == "DENIED":
                        try: await member.kick(reason="Unauthorized Bot")
                        except: pass
                        try: await inviter.ban(reason="Anti-Nuke: Adding Unverified Bots")
                        except: pass
                    
                    elif perm_level == "NATIVE":
                        limits = config.get('nuke_limits', {"max_actions": 3, "time_window": 10})
                        strikes = add_strike(nuke_tracker, member.guild.id, inviter.id, limits['time_window'])
                        if strikes >= limits['max_actions']:
                            try: await inviter.ban(reason="Anti-Nuke: Mass Bot Invite Spam")
                            except: pass
                    break

async def setup(bot):
    await bot.add_cog(AntiNukeCog(bot))
