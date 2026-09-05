import discord
from discord.ext import commands
from discord import app_commands

# ---------------------------------------------------------
# DATABASE (In-Memory Configuration)
# ---------------------------------------------------------
server_configs = {}

def get_config(guild_id: int):
    if guild_id not in server_configs:
        server_configs[guild_id] = {
            "is_enabled": False,
            "channel_id": None,
            "auto_role_id": None,
            
            "display_mode": "BOTH",
            "welcome_title": "**Welcome to {server_name}!**",
            "welcome_msg": "Hey {user_mention}, you are lucky member **#{member_count}**!\n\n**To learn more, check out the channels above.**",
            "bg_url": "https://cdn.discordapp.com/attachments/1509733741302382670/1545129390063616010/tenor.gif?ex=6a9b0561&is=6a99b3e1&hm=78d4c8db38a5523aa3eba51b1f350c1d68a010313875874e31ded09a37f23e63&",
            "accent_color": "#5865F2", # Blurple default
            
            "links": {}, 
            
            "dm_enabled": False,
            "dm_msg": "Hello {user_name}, welcome to {server_name}! Please read the rules.",
            
            "ping_enabled": False,
            "ping_channel_id": None,
            "ping_msg": "Welcome {user_mention}!",
            "ping_timer": 3,
        }
    return server_configs[guild_id]

# ---------------------------------------------------------
# EMBED GENERATORS (For Live Dashboard Updates)
# ---------------------------------------------------------
def get_core_embed(config):
    embed = discord.Embed(title="⚙️ 1. Core Settings", color=discord.Color.from_str("#2b2d31"))
    embed.add_field(name="System Status", value="✅ Enabled" if config['is_enabled'] else "❌ Disabled")
    embed.add_field(name="Welcome Channel", value=f"<#{config['channel_id']}>" if config['channel_id'] else "Not Set")
    embed.add_field(name="Auto-Role", value=f"<@&{config['auto_role_id']}>" if config['auto_role_id'] else "Not Set")
    return embed

def get_design_embed(config):
    embed = discord.Embed(title="🎨 2. Design & Aesthetics", color=discord.Color.from_str("#2b2d31"))
    embed.add_field(name="Display Mode", value=config['display_mode'])
    embed.add_field(name="Accent Color", value=config['accent_color'])
    embed.add_field(name="Background", value="Custom URL Set" if config['bg_url'] else "Default")
    return embed

def get_advanced_embed(config):
    embed = discord.Embed(title="🛠️ 3. Advanced Extra", color=discord.Color.from_str("#2b2d31"))
    embed.add_field(name="Ping Channel", value=f"<#{config['ping_channel_id']}>" if config['ping_channel_id'] else "Not Set")
    embed.add_field(name="Ping System", value=f"Enabled ({config['ping_timer']}s)" if config['ping_enabled'] else "Disabled")
    embed.add_field(name="DM Welcome", value="✅ Enabled" if config['dm_enabled'] else "❌ Disabled")
    embed.add_field(name="Link Buttons", value=f"{len(config['links'])}/5 Configured")
    return embed

# ---------------------------------------------------------
# SELECTION MENUS (Channel, Role, Color)
# ---------------------------------------------------------
class ChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int, is_ping: bool = False):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.is_ping = is_ping

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a Text Channel", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_config(self.guild_id)
        if self.is_ping:
            config['ping_channel_id'] = str(select.values[0].id)
            await interaction.response.edit_message(embed=get_advanced_embed(config), view=AdvancedView(self.guild_id))
            await interaction.followup.send(f"✅ Ping Channel set to <#{config['ping_channel_id']}>!", ephemeral=True)
        else:
            config['channel_id'] = str(select.values[0].id)
            config['is_enabled'] = True
            await interaction.response.edit_message(embed=get_core_embed(config), view=CoreView(self.guild_id))
            await interaction.followup.send(f"✅ Welcome Channel set to <#{config['channel_id']}>!", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select an Auto-Role", row=0)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        config = get_config(self.guild_id)
        config['auto_role_id'] = str(select.values[0].id)
        await interaction.response.edit_message(embed=get_core_embed(config), view=CoreView(self.guild_id))
        await interaction.followup.send(f"✅ Auto-Role set to <@&{config['auto_role_id']}>!", ephemeral=True)

class ColorSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(
        placeholder="Choose an Accent Color",
        options=[
            discord.SelectOption(label="Blurple (Default)", value="#5865F2", emoji="🟣"),
            discord.SelectOption(label="Red", value="#FF0000", emoji="🔴"),
            discord.SelectOption(label="Green", value="#00FF00", emoji="🟢"),
            discord.SelectOption(label="Blue", value="#0000FF", emoji="🔵"),
            discord.SelectOption(label="Yellow", value="#FFFF00", emoji="🟡"),
            discord.SelectOption(label="White", value="#FFFFFF", emoji="⚪"),
            discord.SelectOption(label="Black", value="#000000", emoji="⚫")
        ],
        row=0
    )
    async def select_color(self, interaction: discord.Interaction, select: discord.ui.Select):
        config = get_config(self.guild_id)
        config['accent_color'] = select.values[0]
        await interaction.response.edit_message(embed=get_design_embed(config), view=DesignView(self.guild_id))
        await interaction.followup.send(f"✅ Accent Color set to {select.values[0]}!", ephemeral=True)


# ---------------------------------------------------------
# MODALS (Forms)
# ---------------------------------------------------------
class TextAndModeModal(discord.ui.Modal, title="✏️ Edit Text & Mode"):
    display_mode = discord.ui.TextInput(label="Mode (BOTH, IMAGE_ONLY, TEXT_ONLY)", style=discord.TextStyle.short, required=True)
    msg_title = discord.ui.TextInput(label="Welcome Title", style=discord.TextStyle.short, required=True)
    msg_desc = discord.ui.TextInput(label="Welcome Message", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.display_mode.default = config['display_mode']
        self.msg_title.default = config['welcome_title']
        self.msg_desc.default = config['welcome_msg']

    async def on_submit(self, interaction: discord.Interaction):
        mode = self.display_mode.value.strip().upper()
        if mode not in ["BOTH", "IMAGE_ONLY", "TEXT_ONLY"]: mode = "BOTH"
        self.config['display_mode'] = mode
        self.config['welcome_title'] = self.msg_title.value
        self.config['welcome_msg'] = self.msg_desc.value
        await interaction.response.edit_message(embed=get_design_embed(self.config), view=DesignView(interaction.guild.id))
        await interaction.followup.send("✅ Text & Display Mode updated!", ephemeral=True)

class BackgroundModal(discord.ui.Modal, title="🖼️ Set Background Image"):
    bg_url = discord.ui.TextInput(label="Image/GIF URL", style=discord.TextStyle.short, required=True)
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.bg_url.default = config['bg_url']
    async def on_submit(self, interaction: discord.Interaction):
        self.config['bg_url'] = self.bg_url.value
        await interaction.response.edit_message(embed=get_design_embed(self.config), view=DesignView(interaction.guild.id))
        await interaction.followup.send("✅ Background updated!", ephemeral=True)

class PingSettingsModal(discord.ui.Modal, title="⏱️ Ping Settings"):
    ping_status = discord.ui.TextInput(label="Enable Ping? (yes/no)", style=discord.TextStyle.short, required=True)
    ping_msg = discord.ui.TextInput(label="Ping Message (Use {user_mention})", style=discord.TextStyle.short, required=True)
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
        await interaction.response.edit_message(embed=get_advanced_embed(self.config), view=AdvancedView(interaction.guild.id))
        await interaction.followup.send("✅ Ping settings updated!", ephemeral=True)

class DMModal(discord.ui.Modal, title="✉️ DM Welcome"):
    dm_status = discord.ui.TextInput(label="Enable DM? (yes/no)", style=discord.TextStyle.short, required=True)
    dm_msg = discord.ui.TextInput(label="DM Message", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.dm_status.default = "yes" if config['dm_enabled'] else "no"
        self.dm_msg.default = config['dm_msg']
    async def on_submit(self, interaction: discord.Interaction):
        self.config['dm_enabled'] = self.dm_status.value.strip().lower() == "yes"
        self.config['dm_msg'] = self.dm_msg.value
        await interaction.response.edit_message(embed=get_advanced_embed(self.config), view=AdvancedView(interaction.guild.id))
        await interaction.followup.send("✅ DM settings updated!", ephemeral=True)

class LinkModal(discord.ui.Modal, title="🔗 Manage Link Buttons"):
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
        
        await interaction.response.edit_message(embed=get_advanced_embed(self.config), view=AdvancedView(interaction.guild.id))
        await interaction.followup.send("✅ Links updated successfully!", ephemeral=True)


# ---------------------------------------------------------
# THE 3 MAIN DASHBOARD VIEWS
# ---------------------------------------------------------

# VIEW 1: Core Settings (4 Buttons)
class CoreView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_config(guild_id)
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable"
            self.btn_toggle.style = discord.ButtonStyle.success

    @discord.ui.button(label="📢 Set Channel", style=discord.ButtonStyle.success)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=ChannelSelectView(self.guild_id, is_ping=False))

    @discord.ui.button(label="🎭 Auto-Role", style=discord.ButtonStyle.success)
    async def btn_auto_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=RoleSelectView(self.guild_id))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle")
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        await interaction.response.edit_message(embed=get_core_embed(config), view=CoreView(self.guild_id))

    @discord.ui.button(label="🧪 Test Welcome", style=discord.ButtonStyle.secondary)
    async def btn_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id)
        if not config['channel_id']:
            await interaction.response.send_message("⚠️ Set a welcome channel first!", ephemeral=True)
            return
        await interaction.response.send_message("✅ Testing welcome message...", ephemeral=True)
        await interaction.client.get_cog("WelcomeCog").execute_welcome(interaction.guild, interaction.user, config, is_test=True)


# VIEW 2: Design & Aesthetics (4 Buttons)
class DesignView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="✏️ Edit Text & Mode", style=discord.ButtonStyle.primary)
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TextAndModeModal(get_config(self.guild_id)))

    @discord.ui.button(label="🖼️ Background", style=discord.ButtonStyle.primary)
    async def btn_bg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BackgroundModal(get_config(self.guild_id)))

    @discord.ui.button(label="🎨 Accent Color", style=discord.ButtonStyle.primary)
    async def btn_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=ColorSelectView(self.guild_id))

    @discord.ui.button(label="📋 Placeholders", style=discord.ButtonStyle.secondary)
    async def btn_placeholders(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Available Placeholders",
            description=(
                "`{display_name}` - Display name\n"
                "`{user_name}` - Username (no tag)\n"
                "`{user_mention}` - Pings user\n"
                "`{user_id}` - User's ID\n\n"
                "`{server_name}` - Server's name\n"
                "`{server_id}` - Server's ID\n"
                "`{member_count}` - Total count (e.g. 150)\n"
                "`{member_count_ordinal}` - e.g. 150th\n\n"
                "`{join_date}` - Time joined\n"
                "`{creation_date}` - Account created"
            ),
            color=discord.Color.from_str("#2b2d31")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# VIEW 3: Advanced Extra (4 Buttons)
class AdvancedView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="🔗 Manage Links", style=discord.ButtonStyle.secondary)
    async def btn_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkModal(get_config(self.guild_id)))

    @discord.ui.button(label="✉️ DM Welcome", style=discord.ButtonStyle.primary)
    async def btn_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DMModal(get_config(self.guild_id)))

    @discord.ui.button(label="📌 Ping Channel", style=discord.ButtonStyle.primary)
    async def btn_ping_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=ChannelSelectView(self.guild_id, is_ping=True))

    @discord.ui.button(label="⏱️ Ping Settings", style=discord.ButtonStyle.primary)
    async def btn_ping_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PingSettingsModal(get_config(self.guild_id)))


# ---------------------------------------------------------
# MAIN COG CLASS
# ---------------------------------------------------------
class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="welcome_setup", description="Open the ultimate welcome setup dashboard (3 Pages)")
    @app_commands.default_permissions(administrator=True)
    async def welcome_setup(self, interaction: discord.Interaction):
        config = get_config(interaction.guild.id)
        
        # Send 1st Message (Core)
        await interaction.response.send_message(embed=get_core_embed(config), view=CoreView(interaction.guild.id), ephemeral=True)
        # Send 2nd Message (Design)
        await interaction.followup.send(embed=get_design_embed(config), view=DesignView(interaction.guild.id), ephemeral=True)
        # Send 3rd Message (Advanced)
        await interaction.followup.send(embed=get_advanced_embed(config), view=AdvancedView(interaction.guild.id), ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        config = get_config(guild.id)
        if not config['is_enabled'] or not config['channel_id']: return
        await self.execute_welcome(guild, member, config, is_test=False)

    async def execute_welcome(self, guild: discord.Guild, member: discord.Member, config: dict, is_test: bool):
        try: welcome_channel = guild.get_channel(int(config['channel_id']))
        except: return
        if not welcome_channel: return

        # 1. Auto-Role
        if not is_test and config['auto_role_id']:
            try:
                role = guild.get_role(int(config['auto_role_id']))
                if role: await member.add_roles(role)
            except: pass

        # 2. DM Welcome
        if not is_test and config['dm_enabled']:
            dm_text = self.format_placeholders(config['dm_msg'], member, guild)
            try: await member.send(dm_text)
            except: pass

        # 3. Separate Ping System
        if config['ping_enabled'] and config['ping_channel_id']:
            try:
                ping_channel = guild.get_channel(int(config['ping_channel_id']))
                if ping_channel:
                    p_msg = self.format_placeholders(config['ping_msg'], member, guild)
                    await ping_channel.send(p_msg, delete_after=config['ping_timer'])
            except: pass

        # 4. Build Embed
        embed = discord.Embed()
        mode = config['display_mode']

        if mode in ["BOTH", "TEXT_ONLY"]:
            embed.set_author(name=self.format_placeholders(config['welcome_title'], member, guild), icon_url=guild.icon.url if guild.icon else None)
            embed.description = self.format_placeholders(config['welcome_msg'], member, guild)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"User ID: {member.id} • Member #{guild.member_count}")

        if mode in ["BOTH", "IMAGE_ONLY"]:
            embed.set_image(url=config['bg_url'])

        try: embed.color = discord.Color.from_str(config['accent_color'])
        except: embed.color = discord.Color.blurple()

        # 5. Buttons (Links)
        view = discord.ui.View()
        if config['links'] and mode != "IMAGE_ONLY":
            for label, url in config['links'].items():
                view.add_item(discord.ui.Button(label=label, url=url))

        # Send
        try:
            if len(view.children) > 0: await welcome_channel.send(embed=embed, view=view)
            else: await welcome_channel.send(embed=embed)
        except Exception as e: print(f"Failed to send welcome message: {e}")

    def format_placeholders(self, text: str, member: discord.Member, guild: discord.Guild) -> str:
        if not text: return ""
        join_unix = int(member.joined_at.timestamp()) if member.joined_at else 0
        create_unix = int(member.created_at.timestamp()) if member.created_at else 0
        count = guild.member_count
        ordinal = f"{count}" + ("st" if count % 10 == 1 and count != 11 else "nd" if count % 10 == 2 and count != 12 else "rd" if count % 10 == 3 and count != 13 else "th")

        return text.replace("{display_name}", member.display_name)\
                   .replace("{user_name}", member.name)\
                   .replace("{user_mention}", member.mention)\
                   .replace("{user_id}", str(member.id))\
                   .replace("{server_name}", guild.name)\
                   .replace("{server_id}", str(guild.id))\
                   .replace("{member_count}", str(count))\
                   .replace("{member_count_ordinal}", ordinal)\
                   .replace("{join_date}", f"<t:{join_unix}:F>")\
                   .replace("{creation_date}", f"<t:{create_unix}:R>")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
