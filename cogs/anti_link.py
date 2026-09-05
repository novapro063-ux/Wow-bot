import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import time
import datetime
import asyncio

# ---------------------------------------------------------
# JSON DATABASE SETUP FOR ANTI-LINK
# ---------------------------------------------------------
DATA_FILE = "anti_link_configs.json"

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

def get_link_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "is_enabled": False,
            "block_all": True, # If True, blocks all links except whitelisted. If False, blocks ONLY blacklisted.
            "blacklisted": ["discord.gg", "discord.com/invite", "free-nitro"],
            "whitelisted": ["tenor.com", "giphy.com", "youtube.com", "youtu.be"],
            "bypassed_channels": [],
            "bypassed_roles": [],
            "bypassed_users": [],
            "max_warnings": 3,
            "timeout_mins": 10
        }
        save_data(data)
    return data[g_id]

def save_link_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

# ---------------------------------------------------------
# IN-MEMORY STRIKE TRACKER
# ---------------------------------------------------------
link_strikes = {}

def add_strike(guild_id: int, user_id: int, time_window: int = 1800) -> int:
    current_time = time.time()
    if guild_id not in link_strikes: link_strikes[guild_id] = {}
    if user_id not in link_strikes[guild_id]: link_strikes[guild_id][user_id] = []
        
    link_strikes[guild_id][user_id] = [t for t in link_strikes[guild_id][user_id] if current_time - t <= time_window]
    link_strikes[guild_id][user_id].append(current_time)
    return len(link_strikes[guild_id][user_id])

def clear_strikes(guild_id: int, user_id: int):
    if guild_id in link_strikes and user_id in link_strikes[guild_id]:
        link_strikes[guild_id][user_id] = []


# ---------------------------------------------------------
# DASHBOARD EMBED GENERATOR
# ---------------------------------------------------------
def get_link_embed(config):
    embed = discord.Embed(title="🔗 Anti-Link Security Dashboard", color=discord.Color.from_str("#2b2d31"))
    
    status = "✅ Active" if config['is_enabled'] else "❌ Disabled"
    mode = "🔴 Block ALL Links (Except Safe)" if config['block_all'] else "🟠 Block ONLY Custom List"
    embed.add_field(name="📌 Core Setup", value=f"**Status:** {status}\n**Mode:** {mode}", inline=False)
    
    ch_len = len(config['bypassed_channels'])
    role_len = len(config['bypassed_roles'])
    user_len = len(config['bypassed_users'])
    embed.add_field(name="🛡️ Bypassed (Allowed)", value=f"**Channels:** {ch_len}\n**Roles:** {role_len}\n**Users:** {user_len}", inline=True)
    
    bad_len = len(config['blacklisted'])
    safe_len = len(config['whitelisted'])
    embed.add_field(name="📋 Link Filters", value=f"**Blocked Words/Links:** {bad_len}\n**Safe Domains:** {safe_len}", inline=True)

    embed.add_field(name="⚖️ Punishment", value=f"**Max Warnings:** {config['max_warnings']}\n**Action:** {config['timeout_mins']} Mins Timeout", inline=False)
    
    return embed


# ---------------------------------------------------------
# SELECTION MENUS (For Bypasses)
# ---------------------------------------------------------
class BypassChannelSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select Allowed Channels", min_values=0, max_values=25, row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_link_config(self.guild_id)
        config['bypassed_channels'] = [str(ch.id) for ch in select.values]
        save_link_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_link_embed(config), view=AntiLinkView(self.guild_id))
        await interaction.followup.send("✅ Allowed Channels updated!", ephemeral=True)

class BypassRoleSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select Allowed Roles", min_values=0, max_values=25, row=0)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        config = get_link_config(self.guild_id)
        config['bypassed_roles'] = [str(r.id) for r in select.values]
        save_link_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_link_embed(config), view=AntiLinkView(self.guild_id))
        await interaction.followup.send("✅ Allowed Roles updated!", ephemeral=True)

class BypassUserSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select Allowed Users", min_values=0, max_values=25, row=0)
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        config = get_link_config(self.guild_id)
        config['bypassed_users'] = [str(u.id) for u in select.values]
        save_link_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_link_embed(config), view=AntiLinkView(self.guild_id))
        await interaction.followup.send("✅ Allowed Users updated!", ephemeral=True)


# ---------------------------------------------------------
# MODALS (Forms for Filters & Punishment)
# ---------------------------------------------------------
class LinkFiltersModal(discord.ui.Modal, title="🔗 Manage Link Filters"):
    block_all = discord.ui.TextInput(label="Block ALL Links? (yes/no)", style=discord.TextStyle.short)
    blacklisted = discord.ui.TextInput(label="Blocked Links (Separate with comma)", style=discord.TextStyle.paragraph, required=False)
    whitelisted = discord.ui.TextInput(label="Safe Domains (Separate with comma)", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        self.block_all.default = "yes" if config['block_all'] else "no"
        self.blacklisted.default = ", ".join(config['blacklisted'])
        self.whitelisted.default = ", ".join(config['whitelisted'])

    async def on_submit(self, interaction: discord.Interaction):
        self.config['block_all'] = self.block_all.value.strip().lower() == "yes"
        
        # Format lists by splitting commas
        bad = [x.strip() for x in self.blacklisted.value.split(",") if x.strip()]
        safe = [x.strip() for x in self.whitelisted.value.split(",") if x.strip()]
        
        self.config['blacklisted'] = bad
        self.config['whitelisted'] = safe
        
        save_link_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_link_embed(self.config), view=AntiLinkView(self.guild_id))
        await interaction.followup.send("✅ Link Filters updated successfully!", ephemeral=True)

class PunishmentModal(discord.ui.Modal, title="⚖️ Link Punishment Settings"):
    max_warn = discord.ui.TextInput(label="Max Warnings before Action", style=discord.TextStyle.short)
    time_out = discord.ui.TextInput(label="Timeout Duration (Minutes)", style=discord.TextStyle.short)

    def __init__(self, guild_id, config):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        self.max_warn.default = str(config['max_warnings'])
        self.time_out.default = str(config['timeout_mins'])

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config['max_warnings'] = int(self.max_warn.value)
            self.config['timeout_mins'] = int(self.time_out.value)
        except: pass
        save_link_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_link_embed(self.config), view=AntiLinkView(self.guild_id))


# ---------------------------------------------------------
# COMPACT DASHBOARD VIEW
# ---------------------------------------------------------
class AntiLinkView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_link_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable Anti-Link"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable Anti-Link"
            self.btn_toggle.style = discord.ButtonStyle.success

    # ROW 0: Bypasses
    @discord.ui.button(label="📢 Allow Channels", style=discord.ButtonStyle.secondary, row=0)
    async def btn_ch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=BypassChannelSelect(self.guild_id))

    @discord.ui.button(label="🎭 Allow Roles", style=discord.ButtonStyle.secondary, row=0)
    async def btn_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=BypassRoleSelect(self.guild_id))

    @discord.ui.button(label="👤 Allow Users", style=discord.ButtonStyle.secondary, row=0)
    async def btn_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=BypassUserSelect(self.guild_id))

    # ROW 1: Filters & Punishment
    @discord.ui.button(label="🔗 Edit Filters", style=discord.ButtonStyle.primary, row=1)
    async def btn_filters(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkFiltersModal(self.guild_id, get_link_config(self.guild_id)))

    @discord.ui.button(label="⚖️ Punishment", style=discord.ButtonStyle.primary, row=1)
    async def btn_punish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishmentModal(self.guild_id, get_link_config(self.guild_id)))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=1)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_link_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_link_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_link_embed(config), view=AntiLinkView(self.guild_id))


# ---------------------------------------------------------
# MAIN COG & ANTI-LINK LOGIC
# ---------------------------------------------------------
class AntiLinkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # URL detection regex
        self.url_pattern = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

    @app_commands.command(name="antilink_setup", description="Open the Ultimate Anti-Link Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def antilink_setup(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the Server Owner can configure Anti-Link!", ephemeral=True)
            return
        config = get_link_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_link_embed(config), view=AntiLinkView(interaction.guild.id), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.author.id == message.guild.owner_id:
            return

        config = get_link_config(message.guild.id)
        if not config['is_enabled']: return

        # 1. Check Bypasses
        if str(message.channel.id) in config['bypassed_channels']: return
        if str(message.author.id) in config['bypassed_users']: return
        if any(str(role.id) in config['bypassed_roles'] for role in message.author.roles): return

        # 2. Extract URLs
        urls = self.url_pattern.findall(message.content)
        if not urls: return

        content_lower = message.content.lower()
        is_blocked = False

        # 3. Check Blacklist First (Always Blocks)
        for bad in config['blacklisted']:
            if bad.lower() in content_lower:
                is_blocked = True
                break

        # 4. Check Block All / Whitelist logic
        if not is_blocked and config['block_all']:
            # If Block All is TRUE, every URL in the message must be in the whitelist
            for url in urls:
                url_lower = url.lower()
                is_safe = any(safe.lower() in url_lower for safe in config['whitelisted'])
                if not is_safe:
                    is_blocked = True
                    break

        # 5. Execute Punishment if Blocked
        if is_blocked:
            try:
                await message.delete()
                
                # Send Warning
                warn_msg = await message.channel.send(f"⚠️ {message.author.mention}, you are not allowed to send unauthorized links here!")
                await warn_msg.delete(delay=5)
                
                # Strike System
                strikes = add_strike(message.guild.id, message.author.id)
                if strikes >= config['max_warnings']:
                    clear_strikes(message.guild.id, message.author.id)
                    timeout_dur = datetime.timedelta(minutes=config['timeout_mins'])
                    try:
                        await message.author.timeout(timeout_dur, reason="Anti-Link Max Warnings Triggered")
                        mute_msg = await message.channel.send(f"🔇 {message.author.mention} has been **muted for {config['timeout_mins']} minutes** for sending unallowed links.")
                        await mute_msg.delete(delay=10)
                    except discord.Forbidden:
                        pass # Bot doesn't have timeout permissions
            except discord.Forbidden:
                pass # Bot doesn't have delete permissions

async def setup(bot):
    await bot.add_cog(AntiLinkCog(bot))
      
