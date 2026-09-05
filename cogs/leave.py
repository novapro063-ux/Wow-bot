import discord
from discord.ext import commands
from discord import app_commands

# ---------------------------------------------------------
# DATABASE (In-Memory Configuration for Leave)
# ---------------------------------------------------------
leave_configs = {}

def get_leave_config(guild_id: int):
    if guild_id not in leave_configs:
        leave_configs[guild_id] = {
            "is_enabled": False,
            "channel_id": None,
            
            "display_mode": "BOTH",
            "leave_title": "**Goodbye, {user_name}!**",
            "leave_msg": "We are sad to see you go, {user_name}.\n\nWe are now down to **{member_count}** members.",
            "bg_url": "https://cdn.discordapp.com/attachments/1509733741302382670/1545129390063616010/tenor.gif?ex=6a9b0561&is=6a99b3e1&hm=78d4c8db38a5523aa3eba51b1f350c1d68a010313875874e31ded09a37f23e63&",
            "accent_color": "#ED4245", # Red default for leave
            
            "links": {}, 
            
            "ping_enabled": False,
            "ping_channel_id": None,
            "ping_msg": "{user_name} just left the server.",
            "ping_timer": 3,
        }
    return leave_configs[guild_id]

# ---------------------------------------------------------
# SINGLE COMPACT EMBED GENERATOR
# ---------------------------------------------------------
def get_leave_dashboard_embed(config):
    try: color = discord.Color.from_str(config['accent_color'])
    except: color = discord.Color.red()
        
    embed = discord.Embed(title="⚙️ Leave Setup Dashboard", color=color)
    
    # Core Summary
    status = "✅ On" if config['is_enabled'] else "❌ Off"
    ch = f"<#{config['channel_id']}>" if config['channel_id'] else "None"
    embed.add_field(name="📌 Core Setup", value=f"**Status:** {status}\n**Channel:** {ch}", inline=True)
    
    # Design Summary
    mode = config['display_mode']
    bg_stat = "Custom" if config['bg_url'] else "Default"
    embed.add_field(name="🎨 Aesthetics", value=f"**Mode:** {mode}\n**Color:** {config['accent_color']}\n**Image:** {bg_stat}", inline=True)
    
    # Advanced Summary
    ping_ch = f"<#{config['ping_channel_id']}>" if config['ping_channel_id'] else "None"
    ping_stat = f"On ({config['ping_timer']}s)" if config['ping_enabled'] else "Off"
    embed.add_field(name="🛠️ Advanced", value=f"**Links:** {len(config['links'])}/5\n**Ping Ch:** {ping_ch}\n**Ping System:** {ping_stat}", inline=False)
    
    return embed


# ---------------------------------------------------------
# SELECTION MENUS (Channel, Color)
# ---------------------------------------------------------
class LeaveChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, is_ping: bool = False):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.is_ping = is_ping

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a Text Channel", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_leave_config(self.guild_id)
        if self.is_ping:
            config['ping_channel_id'] = str(select.values[0].id)
            await interaction.response.edit_message(embed=get_leave_dashboard_embed(config), view=LeaveDashboardView(self.guild_id))
            await interaction.followup.send(f"✅ Leave Ping Channel set to <#{config['ping_channel_id']}>!", ephemeral=True)
        else:
            config['channel_id'] = str(select.values[0].id)
            config['is_enabled'] = True
            await interaction.response.edit_message(embed=get_leave_dashboard_embed(config), view=LeaveDashboardView(self.guild_id))
            await interaction.followup.send(f"✅ Leave Channel set to <#{config['channel_id']}>!", ephemeral=True)

    @discord.ui.button(label="🔙 Back to Dashboard", style=discord.ButtonStyle.danger, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(get_leave_config(self.guild_id)), view=LeaveDashboardView(self.guild_id))


class LeaveColorSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="Choose an Accent Color",
        options=[
            discord.SelectOption(label="Red (Default)", value="#ED4245", emoji="🔴"),
            discord.SelectOption(label="Blurple", value="#5865F2", emoji="🟣"),
            discord.SelectOption(label="Green", value="#00FF00", emoji="🟢"),
            discord.SelectOption(label="Blue", value="#0000FF", emoji="🔵"),
            discord.SelectOption(label="Yellow", value="#FFFF00", emoji="🟡"),
            discord.SelectOption(label="White", value="#FFFFFF", emoji="⚪"),
            discord.SelectOption(label="Black", value="#000000", emoji="⚫")
        ],
        row=0
    )
    async def select_color(self, interaction: discord.Interaction, select: discord.ui.Select):
        config = get_leave_config(self.guild_id)
        config['accent_color'] = select.values[0]
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(config), view=LeaveDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Accent Color set to {select.values[0]}!", ephemeral=True)

    @discord.ui.button(label="🔙 Back to Dashboard", style=discord.ButtonStyle.danger, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(get_leave_config(self.guild_id)), view=LeaveDashboardView(self.guild_id))


# ---------------------------------------------------------
# MODALS (Forms)
# ---------------------------------------------------------
class LeaveTextAndModeModal(discord.ui.Modal, title="✏️ Edit Text & Mode"):
    display_mode = discord.ui.TextInput(label="Mode (BOTH, IMAGE_ONLY, TEXT_ONLY)", style=discord.TextStyle.short, required=True)
    msg_title = discord.ui.TextInput(label="Leave Title", style=discord.TextStyle.short, required=True)
    msg_desc = discord.ui.TextInput(label="Leave Message", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.display_mode.default = config['display_mode']
        self.msg_title.default = config['leave_title']
        self.msg_desc.default = config['leave_msg']

    async def on_submit(self, interaction: discord.Interaction):
        mode = self.display_mode.value.strip().upper()
        if mode not in ["BOTH", "IMAGE_ONLY", "TEXT_ONLY"]: mode = "BOTH"
        self.config['display_mode'] = mode
        self.config['leave_title'] = self.msg_title.value
        self.config['leave_msg'] = self.msg_desc.value
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(self.config), view=LeaveDashboardView(interaction.guild.id))
        await interaction.followup.send("✅ Text & Display Mode updated!", ephemeral=True)

class LeaveBackgroundModal(discord.ui.Modal, title="🖼️ Set Background Image"):
    bg_url = discord.ui.TextInput(label="Image/GIF URL", style=discord.TextStyle.short, required=True)
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.bg_url.default = config['bg_url']
    async def on_submit(self, interaction: discord.Interaction):
        self.config['bg_url'] = self.bg_url.value
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(self.config), view=LeaveDashboardView(interaction.guild.id))
        await interaction.followup.send("✅ Background updated!", ephemeral=True)

class LeavePingSettingsModal(discord.ui.Modal, title="⏱️ Ping Settings"):
    ping_status = discord.ui.TextInput(label="Enable Ping? (yes/no)", style=discord.TextStyle.short, required=True)
    ping_msg = discord.ui.TextInput(label="Ping Message", style=discord.TextStyle.short, required=True)
    ping_timer = discord.ui.TextInput(label="Delete After (Seconds)", style=discord.TextStyle.short, required=True)
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.ping_status.default = "yes" if config['ping_enabled'] else "no"
        self.ping_msg.default = config['ping_msg']
        self.ping_timer.default = str(config['ping_timer'])
    async def on_submit(self, interaction: discord.Interaction):
        self.config['ping_enabled'] = self.ping_status.value.strip().lower() == "yes"
        self.config['ping_msg'] = self.ping_msg.value
        try: self.config['ping_timer'] = int(self.ping_timer.value)
        except: self.config['ping_timer'] = 3
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(self.config), view=LeaveDashboardView(interaction.guild.id))
        await interaction.followup.send("✅ Ping settings updated!", ephemeral=True)

class LeaveLinkModal(discord.ui.Modal, title="🔗 Manage Link Buttons"):
    label_input = discord.ui.TextInput(label="Button Label (Exact Name)", style=discord.TextStyle.short, required=True)
    url_input = discord.ui.TextInput(label="URL (Leave blank to remove)", style=discord.TextStyle.short, required=False)
    def __init__(self, config):
        super().__init__()
        self.config = config
    async def on_submit(self, interaction: discord.Interaction):
        label = self.label_input.value.strip()
        url = self.url_input.value.strip()
        if not url:
            if label in self.config['links']:
                del self.config['links'][label]
            else:
                await interaction.response.send_message(f"⚠️ Button **{label}** not found.", ephemeral=True)
                return
        else:
            if len(self.config['links']) >= 5 and label not in self.config['links']:
                await interaction.response.send_message("⚠️ Max 5 buttons allowed!", ephemeral=True)
                return
            if not url.startswith("http"): url = "https://" + url
            self.config['links'][label] = url
        
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(self.config), view=LeaveDashboardView(interaction.guild.id))
        await interaction.followup.send("✅ Links updated successfully!", ephemeral=True)


# ---------------------------------------------------------
# SINGLE DASHBOARD VIEW (Compact Setup)
# ---------------------------------------------------------
class LeaveDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_leave_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable"
            self.btn_toggle.style = discord.ButtonStyle.success

    # --- ROW 0: Core Settings ---
    @discord.ui.button(label="📢 Set Channel", style=discord.ButtonStyle.success, row=0)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=LeaveChannelSelectView(self.guild_id, is_ping=False))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_leave_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        await interaction.response.edit_message(embed=get_leave_dashboard_embed(config), view=LeaveDashboardView(self.guild_id))

    @discord.ui.button(label="🧪 Test", style=discord.ButtonStyle.secondary, row=0)
    async def btn_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_leave_config(self.guild_id)
        if not config['channel_id']:
            await interaction.response.send_message("⚠️ Set a leave channel first!", ephemeral=True)
            return
        await interaction.response.send_message("✅ Testing leave message...", ephemeral=True)
        await interaction.client.get_cog("LeaveCog").execute_leave(interaction.guild, interaction.user, config)

    # --- ROW 1: Design Settings ---
    @discord.ui.button(label="✏️ Text/Mode", style=discord.ButtonStyle.primary, row=1)
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LeaveTextAndModeModal(get_leave_config(self.guild_id)))

    @discord.ui.button(label="🖼️ Background", style=discord.ButtonStyle.primary, row=1)
    async def btn_bg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LeaveBackgroundModal(get_leave_config(self.guild_id)))

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.primary, row=1)
    async def btn_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=LeaveColorSelectView(self.guild_id))

    @discord.ui.button(label="📋 Tags", style=discord.ButtonStyle.secondary, row=1)
    async def btn_placeholders(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Leave Placeholders",
            description=(
                "`{display_name}` - Display name\n"
                "`{user_name}` - Username (Safest for leaves)\n"
                "`{user_mention}` - Might not resolve if they left entirely\n"
                "`{user_id}` - User's ID\n\n"
                "`{server_name}` - Server's name\n"
                "`{member_count}` - Total count after leaving\n"
            ),
            color=discord.Color.from_str("#2b2d31")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ROW 2: Advanced Settings ---
    @discord.ui.button(label="🔗 Links", style=discord.ButtonStyle.secondary, row=2)
    async def btn_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LeaveLinkModal(get_leave_config(self.guild_id)))

    @discord.ui.button(label="📌 Ping Ch.", style=discord.ButtonStyle.primary, row=2)
    async def btn_ping_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=LeaveChannelSelectView(self.guild_id, is_ping=True))

    @discord.ui.button(label="⏱️ Ping Setup", style=discord.ButtonStyle.primary, row=2)
    async def btn_ping_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LeavePingSettingsModal(get_leave_config(self.guild_id)))


# ---------------------------------------------------------
# MAIN COG CLASS
# ---------------------------------------------------------
class LeaveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leave_setup", description="Open the compact leave setup dashboard")
    @app_commands.default_permissions(administrator=True)
    async def leave_setup(self, interaction: discord.Interaction):
        config = get_leave_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_leave_dashboard_embed(config), view=LeaveDashboardView(interaction.guild.id), ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        config = get_leave_config(guild.id)
        if not config['is_enabled'] or not config['channel_id']: return
        await self.execute_leave(guild, member, config)

    async def execute_leave(self, guild: discord.Guild, member: discord.Member, config: dict):
        try: leave_channel = guild.get_channel(int(config['channel_id']))
        except: return
        if not leave_channel: return

        # 1. Separate Ping System
        if config['ping_enabled'] and config['ping_channel_id']:
            try:
                ping_channel = guild.get_channel(int(config['ping_channel_id']))
                if ping_channel:
                    p_msg = self.format_placeholders(config['ping_msg'], member, guild)
                    await ping_channel.send(p_msg, delete_after=config['ping_timer'])
            except: pass

        # 2. Build Embed
        embed = discord.Embed()
        mode = config['display_mode']

        if mode in ["BOTH", "TEXT_ONLY"]:
            embed.set_author(name=self.format_placeholders(config['leave_title'], member, guild), icon_url=guild.icon.url if guild.icon else None)
            embed.description = self.format_placeholders(config['leave_msg'], member, guild)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"User ID: {member.id} • Member #{guild.member_count}")

        if mode in ["BOTH", "IMAGE_ONLY"]:
            embed.set_image(url=config['bg_url'])

        try: embed.color = discord.Color.from_str(config['accent_color'])
        except: embed.color = discord.Color.red()

        # 3. Buttons (Links)
        view = discord.ui.View()
        if config['links'] and mode != "IMAGE_ONLY":
            for label, url in config['links'].items():
                view.add_item(discord.ui.Button(label=label, url=url))

        # Send
        try:
            if len(view.children) > 0: await leave_channel.send(embed=embed, view=view)
            else: await leave_channel.send(embed=embed)
        except Exception as e: print(f"Failed to send leave message: {e}")

    def format_placeholders(self, text: str, member: discord.Member, guild: discord.Guild) -> str:
        if not text: return ""
        count = guild.member_count
        return text.replace("{display_name}", member.display_name)\
                   .replace("{user_name}", member.name)\
                   .replace("{user_mention}", member.mention)\
                   .replace("{user_id}", str(member.id))\
                   .replace("{server_name}", guild.name)\
                   .replace("{member_count}", str(count))

async def setup(bot):
    await bot.add_cog(LeaveCog(bot))
          
