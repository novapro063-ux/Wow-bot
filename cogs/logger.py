import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime

# ---------------------------------------------------------
# JSON DATABASE SETUP FOR LOGS
# ---------------------------------------------------------
DATA_FILE = "log_configs.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

def get_log_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {"channel_id": None, "is_enabled": False}
        save_data(data)
    return data[g_id]

def save_log_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

# ---------------------------------------------------------
# SETUP UI (Selection Menu)
# ---------------------------------------------------------
class LogChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a channel for Server Logs", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_log_config(self.guild_id)
        config['channel_id'] = str(select.values[0].id)
        config['is_enabled'] = True
        save_log_config(self.guild_id, config)
        
        embed = discord.Embed(title="⚙️ Ultimate Server Logger", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="System Status", value="✅ Enabled", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{config['channel_id']}>", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=LogDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Log Channel successfully set to <#{config['channel_id']}>!", ephemeral=True)

class LogDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_log_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable Logger"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable Logger"
            self.btn_toggle.style = discord.ButtonStyle.success

    @discord.ui.button(label="📢 Set Log Channel", style=discord.ButtonStyle.primary, row=0)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=LogChannelSelectView(self.guild_id))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_log_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_log_config(self.guild_id, config)
        
        embed = discord.Embed(title="⚙️ Ultimate Server Logger", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="System Status", value="✅ Enabled" if config['is_enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{config['channel_id']}>" if config['channel_id'] else "Not Set", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=LogDashboardView(self.guild_id))


# ---------------------------------------------------------
# MAIN COG CLASS (EVENT LISTENERS)
# ---------------------------------------------------------
class LoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="log_setup", description="Configure the advanced server logging system")
    @app_commands.default_permissions(administrator=True)
    async def log_setup(self, interaction: discord.Interaction):
        config = get_log_config(interaction.guild.id)
        embed = discord.Embed(
            title="⚙️ Ultimate Server Logger",
            description="Track everything happening in your server with extreme detail.\nUse the buttons below to configure.",
            color=discord.Color.from_str("#2b2d31")
        )
        embed.add_field(name="System Status", value="✅ Enabled" if config['is_enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{config['channel_id']}>" if config['channel_id'] else "Not Set", inline=True)
        
        await interaction.response.send_message(embed=embed, view=LogDashboardView(interaction.guild.id), ephemeral=True)

    # --- HELPER: SEND LOGS ---
    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        config = get_log_config(guild.id)
        if not config['is_enabled'] or not config['channel_id']: return
        try:
            channel = guild.get_channel(int(config['channel_id']))
            if channel:
                embed.timestamp = datetime.now()
                await channel.send(embed=embed)
        except: pass

    # --- HELPER: FETCH AUDIT LOG EXECUTOR ---
    async def get_executor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        try:
            await asyncio.sleep(0.5) # Give Discord API time to update audit logs
            async for entry in guild.audit_logs(action=action, limit=5):
                if entry.target.id == target_id:
                    return entry.user
        except: pass
        return None

    # 1. MESSAGE DELETED (Detailed)
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot: return
        embed = discord.Embed(description=f"**Message sent by {message.author.mention} deleted in {message.channel.mention}**", color=discord.Color.red())
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        
        content = message.content if message.content else "*(Embed/Attachment or Empty)*"
        embed.add_field(name="Message Content", value=f"```\n{content[:1015]}\n```", inline=False)
        embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
        await self.send_log(message.guild, embed)

    # 2. MESSAGE EDITED (Detailed)
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content: return
        embed = discord.Embed(description=f"**Message edited in {before.channel.mention}** [Jump to Message]({after.jump_url})", color=discord.Color.from_str("#E67E22"))
        embed.set_author(name=before.author.display_name, icon_url=before.author.display_avatar.url)
        
        old_content = before.content if before.content else "*(Empty)*"
        new_content = after.content if after.content else "*(Empty)*"
        
        embed.add_field(name="Old Message", value=f"```\n{old_content[:1015]}\n```", inline=False)
        embed.add_field(name="New Message", value=f"```\n{new_content[:1015]}\n```", inline=False)
        embed.set_footer(text=f"Author ID: {before.author.id}")
        await self.send_log(before.guild, embed)

    # 3. CHANNEL CREATED (Detailed with Audit Log)
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        executor = await self.get_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        
        embed = discord.Embed(title="📁 Channel Created", color=discord.Color.green())
        if executor:
            embed.set_author(name=executor.display_name, icon_url=executor.display_avatar.url)
            embed.add_field(name="Created By", value=executor.mention, inline=False)
        else:
            embed.set_author(name=channel.guild.name, icon_url=channel.guild.icon.url if channel.guild.icon else None)

        embed.add_field(name="Channel Info", value=f"**Name:** {channel.mention}\n**Type:** {str(channel.type).capitalize()}\n**Category:** {channel.category.name if channel.category else 'None'}", inline=False)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await self.send_log(channel.guild, embed)

    # 4. CHANNEL DELETED (Detailed with Audit Log)
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        executor = await self.get_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        
        embed = discord.Embed(title="🗑️ Channel Deleted", color=discord.Color.red())
        if executor:
            embed.set_author(name=executor.display_name, icon_url=executor.display_avatar.url)
            embed.add_field(name="Deleted By", value=executor.mention, inline=False)
        
        embed.add_field(name="Channel Info", value=f"**Name:** #{channel.name}\n**Type:** {str(channel.type).capitalize()}\n**Category:** {channel.category.name if channel.category else 'None'}", inline=False)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await self.send_log(channel.guild, embed)

    # 5. ROLE CREATED (Detailed)
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        executor = await self.get_executor(role.guild, discord.AuditLogAction.role_create, role.id)
        
        embed = discord.Embed(title="🛡️ Role Created", color=discord.Color.green())
        if executor:
            embed.set_author(name=executor.display_name, icon_url=executor.display_avatar.url)
            embed.add_field(name="Created By", value=executor.mention, inline=False)

        embed.add_field(name="Role Info", value=f"**Role:** {role.mention}\n**Hex Color:** {str(role.color).upper()}\n**Hoisted:** {'Yes' if role.hoist else 'No'}", inline=False)
        embed.set_footer(text=f"Role ID: {role.id}")
        await self.send_log(role.guild, embed)

    # 6. ROLE DELETED (Detailed)
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        executor = await self.get_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
        
        embed = discord.Embed(title="🔥 Role Deleted", color=discord.Color.red())
        if executor:
            embed.set_author(name=executor.display_name, icon_url=executor.display_avatar.url)
            embed.add_field(name="Deleted By", value=executor.mention, inline=False)

        embed.add_field(name="Role Info", value=f"**Name:** @{role.name}\n**Hex Color:** {str(role.color).upper()}", inline=False)
        embed.set_footer(text=f"Role ID: {role.id}")
        await self.send_log(role.guild, embed)

    # 7. VOICE CHANNEL UPDATES (Detailed)
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        embed = discord.Embed()
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        
        if before.channel is None and after.channel is not None:
            embed.title = "🎙️ Joined Voice Channel"
            embed.color = discord.Color.from_str("#3BA55C")
            embed.description = f"**{member.mention}** joined {after.channel.mention}"
        elif before.channel is not None and after.channel is None:
            embed.title = "🔇 Left Voice Channel"
            embed.color = discord.Color.from_str("#ED4245")
            embed.description = f"**{member.mention}** left {before.channel.mention}"
        elif before.channel != after.channel:
            embed.title = "🔀 Switched Voice Channel"
            embed.color = discord.Color.from_str("#5865F2")
            embed.description = f"**{member.mention}** switched voice channels:\n**From:** {before.channel.mention}\n**To:** {after.channel.mention}"
        else:
            return 
        
        embed.set_footer(text=f"User ID: {member.id}")
        await self.send_log(member.guild, embed)

    # 8. MEMBER NICKNAME / ROLE UPDATES
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            embed = discord.Embed(title="👤 Nickname Changed", color=discord.Color.from_str("#FEE75C"))
            embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
            embed.add_field(name="Old Nickname", value=f"`{before.nick if before.nick else before.name}`", inline=True)
            embed.add_field(name="New Nickname", value=f"`{after.nick if after.nick else after.name}`", inline=True)
            embed.set_footer(text=f"User ID: {after.id}")
            await self.send_log(after.guild, embed)
            
        elif before.roles != after.roles:
            added_roles = [role.mention for role in after.roles if role not in before.roles]
            removed_roles = [role.mention for role in before.roles if role not in after.roles]
            
            if added_roles or removed_roles:
                embed = discord.Embed(title="🏷️ Roles Updated", color=discord.Color.from_str("#1ABC9C"))
                embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                embed.description = f"Roles for **{after.mention}** were updated."
                if added_roles: embed.add_field(name="✅ Added Roles", value=" ".join(added_roles), inline=False)
                if removed_roles: embed.add_field(name="❌ Removed Roles", value=" ".join(removed_roles), inline=False)
                embed.set_footer(text=f"User ID: {after.id}")
                await self.send_log(after.guild, embed)

async def setup(bot):
    await bot.add_cog(LoggerCog(bot))
