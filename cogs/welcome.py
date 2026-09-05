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
            "display_mode": "BOTH",
            "welcome_title": "**Welcome to {server_name}!**",
            "welcome_msg": "Hey {user_mention}, you are lucky member **#{member_count}**!\n\n**To learn more, don't forget to check out the channels above.**",
            "bg_url": "https://cdn.discordapp.com/attachments/1509733741302382670/1545129390063616010/tenor.gif?ex=6a9b0561&is=6a99b3e1&hm=78d4c8db38a5523aa3eba51b1f350c1d68a010313875874e31ded09a37f23e63&",
            "accent_color": "#5865F2",
            "links": {}, 
            "ping_enabled": False,
            "ping_msg": "Welcome {user_mention}!",
            "ping_timer": 3,
            "auto_role_id": None,
            "dm_enabled": False,
            "dm_msg": "Hello {user_name}, welcome to {server_name}! Please read the rules and enjoy your stay."
        }
    return server_configs[guild_id]


# ---------------------------------------------------------
# SELECTION MENU VIEWS (Edits Current Message)
# ---------------------------------------------------------
class ChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a channel for welcome messages", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_config(self.guild_id)
        config['channel_id'] = str(select.values[0].id)
        config['is_enabled'] = True
        # Return to Dashboard
        await interaction.response.edit_message(view=DashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Welcome channel successfully set to <#{config['channel_id']}>!", ephemeral=True)

    @discord.ui.button(label="🔙 Back to Dashboard", style=discord.ButtonStyle.danger, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=DashboardView(self.guild_id))


class RoleSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select an Auto-Role for new members", row=0)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        config = get_config(self.guild_id)
        config['auto_role_id'] = str(select.values[0].id)
        # Return to Dashboard
        await interaction.response.edit_message(view=DashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Auto-Role successfully set to <@&{config['auto_role_id']}>!", ephemeral=True)

    @discord.ui.button(label="🔙 Back to Dashboard", style=discord.ButtonStyle.danger, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=DashboardView(self.guild_id))


# ---------------------------------------------------------
# MODALS (For Text Inputs)
# ---------------------------------------------------------
class DesignModal(discord.ui.Modal, title="🎨 Design Welcome Embed"):
    msg_title = discord.ui.TextInput(label="Welcome Title", style=discord.TextStyle.short, required=True)
    msg_desc = discord.ui.TextInput(label="Welcome Message", style=discord.TextStyle.paragraph, required=True)
    display_mode = discord.ui.TextInput(label="Mode (BOTH, IMAGE_ONLY, TEXT_ONLY)", style=discord.TextStyle.short, required=True)
    bg_url = discord.ui.TextInput(label="Background Image (URL)", style=discord.TextStyle.short, required=True)
    accent_color = discord.ui.TextInput(label="Accent Color (Hex)", style=discord.TextStyle.short, required=True)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.msg_title.default = config['welcome_title']
        self.msg_desc.default = config['welcome_msg']
        self.display_mode.default = config['display_mode']
        self.bg_url.default = config['bg_url']
        self.accent_color.default = config['accent_color']

    async def on_submit(self, interaction: discord.Interaction):
        mode = self.display_mode.value.strip().upper()
        if mode not in ["BOTH", "IMAGE_ONLY", "TEXT_ONLY"]: mode = "BOTH"
            
        self.config['welcome_title'] = self.msg_title.value
        self.config['welcome_msg'] = self.msg_desc.value
        self.config['display_mode'] = mode
        self.config['bg_url'] = self.bg_url.value
        self.config['accent_color'] = self.accent_color.value
        await interaction.response.send_message("✅ Welcome design updated perfectly!", ephemeral=True)


class AdvancedModal(discord.ui.Modal, title="🛠️ Advanced Features"):
    dm_status = discord.ui.TextInput(label="Enable DM Welcome? (yes/no)", style=discord.TextStyle.short, required=True)
    dm_msg = discord.ui.TextInput(label="DM Message", style=discord.TextStyle.paragraph, required=True)
    ping_status = discord.ui.TextInput(label="Enable Ping & Delete? (yes/no)", style=discord.TextStyle.short, required=True)
    ping_msg = discord.ui.TextInput(label="Ping Message", style=discord.TextStyle.short, required=True)
    ping_timer = discord.ui.TextInput(label="Delete Ping After (Seconds)", style=discord.TextStyle.short, required=True)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.dm_status.default = "yes" if config['dm_enabled'] else "no"
        self.dm_msg.default = config['dm_msg']
        self.ping_status.default = "yes" if config['ping_enabled'] else "no"
        self.ping_msg.default = config['ping_msg']
        self.ping_timer.default = str(config['ping_timer'])

    async def on_submit(self, interaction: discord.Interaction):
        self.config['dm_enabled'] = self.dm_status.value.strip().lower() == "yes"
        self.config['dm_msg'] = self.dm_msg.value
        self.config['ping_enabled'] = self.ping_status.value.strip().lower() == "yes"
        self.config['ping_msg'] = self.ping_msg.value
        try: self.config['ping_timer'] = int(self.ping_timer.value)
        except: self.config['ping_timer'] = 3
        await interaction.response.send_message("✅ Advanced features updated successfully!", ephemeral=True)


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
                await interaction.response.send_message(f"🗑️ Removed button: **{label}**", ephemeral=True)
            else:
                await interaction.response.send_message(f"⚠️ Could not find a button named **{label}** to remove.", ephemeral=True)
        else:
            if len(self.config['links']) >= 5 and label not in self.config['links']:
                await interaction.response.send_message("⚠️ You can only have a maximum of 5 buttons!", ephemeral=True)
                return
            if not url.startswith("http"): url = "https://" + url
            self.config['links'][label] = url
            await interaction.response.send_message(f"✅ Button **{label}** configured successfully!", ephemeral=True)


# ---------------------------------------------------------
# CLEAN & COMPACT DASHBOARD UI 
# ---------------------------------------------------------
class DashboardView(discord.ui.View):
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

    # --- ROW 0 : Basic Selections & Toggle ---
    @discord.ui.button(label="📢 Set Channel", style=discord.ButtonStyle.success, row=0)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=ChannelSelectView(self.guild_id))

    @discord.ui.button(label="🎭 Set Auto-Role", style=discord.ButtonStyle.success, row=0)
    async def btn_auto_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=RoleSelectView(self.guild_id))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        await interaction.response.edit_message(view=DashboardView(self.guild_id))

    # --- ROW 1 : Design & Advanced ---
    @discord.ui.button(label="🎨 Design Welcome", style=discord.ButtonStyle.primary, row=1)
    async def btn_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DesignModal(get_config(self.guild_id)))

    @discord.ui.button(label="🛠️ Advanced Features", style=discord.ButtonStyle.primary, row=1)
    async def btn_advanced(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdvancedModal(get_config(self.guild_id)))

    @discord.ui.button(label="🔗 Manage Links", style=discord.ButtonStyle.secondary, row=1)
    async def btn_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkModal(get_config(self.guild_id)))

    # --- ROW 2 : Utilities ---
    @discord.ui.button(label="🧪 Test Welcome", style=discord.ButtonStyle.secondary, row=2)
    async def btn_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id)
        if not config['channel_id']:
            await interaction.response.send_message("⚠️ Please configure 'Set Channel' first!", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ Sending a test welcome message...", ephemeral=True)
        cog = interaction.client.get_cog("WelcomeCog")
        await cog.execute_welcome(interaction.guild, interaction.user, config, is_test=True)

    @discord.ui.button(label="📊 View Config", style=discord.ButtonStyle.secondary, row=2)
    async def btn_view_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config(self.guild_id)
        embed = discord.Embed(title="📊 Dashboard Configuration", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="System Status", value="✅ Enabled" if config['is_enabled'] else "❌ Disabled")
        embed.add_field(name="Channel ID", value=f"<#{config['channel_id']}>" if config['channel_id'] else "None")
        embed.add_field(name="Auto-Role ID", value=f"<@&{config['auto_role_id']}>" if config['auto_role_id'] else "None")
        embed.add_field(name="Display Mode", value=config['display_mode'])
        embed.add_field(name="DM Enabled", value="Yes" if config['dm_enabled'] else "No")
        embed.add_field(name="Ping Enabled", value="Yes" if config['ping_enabled'] else "No")
        
        links = "\n".join([f"**{k}**" for k in config['links'].keys()]) if config['links'] else "0 Links"
        embed.add_field(name="Active Buttons", value=links, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📋 Placeholders", style=discord.ButtonStyle.secondary, row=2)
    async def btn_placeholders(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Available Placeholders",
            description=(
                "`{display_name}` - Display name\n"
                "`{user_name}` - Username\n"
                "`{user_mention}` - Pings the user\n"
                "`{server_name}` - Server's name\n"
                "`{member_count}` - Total member count\n"
                "`{join_date}` - Time joined"
            ),
            color=discord.Color.from_str("#2b2d31")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------
# MAIN COG CLASS
# ---------------------------------------------------------
class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="welcome_setup", description="Open the user-friendly welcome dashboard")
    @app_commands.default_permissions(administrator=True)
    async def welcome_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Ultimate Welcome System",
            description="Use the compact buttons below to fully configure the welcome system.\n\n"
                        "🔹 **Set Channel:** Where to send welcome messages\n"
                        "🔹 **Set Auto-Role:** Role given on join\n"
                        "🔹 **Design Welcome:** Message, Color & BG\n"
                        "🔹 **Advanced:** DM & Ping Settings\n"
                        "🔹 **Manage Links:** Add or Remove buttons",
            color=discord.Color.from_str("#2b2d31")
        )
        await interaction.response.send_message(embed=embed, view=DashboardView(interaction.guild.id), ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        config = get_config(guild.id)
        if not config['is_enabled'] or not config['channel_id']:
            return
        await self.execute_welcome(guild, member, config, is_test=False)

    async def execute_welcome(self, guild: discord.Guild, member: discord.Member, config: dict, is_test: bool):
        try:
            channel = guild.get_channel(int(config['channel_id']))
        except:
            return
        if not channel: return

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

        # 3. Ping & Delete
        if config['ping_enabled']:
            p_msg = self.format_placeholders(config['ping_msg'], member, guild)
            try: await channel.send(p_msg, delete_after=config['ping_timer'])
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
            if len(view.children) > 0: await channel.send(embed=embed, view=view)
            else: await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send welcome message: {e}")

    def format_placeholders(self, text: str, member: discord.Member, guild: discord.Guild) -> str:
        if not text: return ""
        join_unix = int(member.joined_at.timestamp()) if member.joined_at else 0
        return text.replace("{display_name}", member.display_name)\
                   .replace("{user_name}", member.name)\
                   .replace("{user_mention}", member.mention)\
                   .replace("{user_id}", str(member.id))\
                   .replace("{server_name}", guild.name)\
                   .replace("{member_count}", str(guild.member_count))\
                   .replace("{join_date}", f"<t:{join_unix}:F>")

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
    
