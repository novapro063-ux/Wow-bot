import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import io
import datetime

# ---------------------------------------------------------
# DEVELOPER / SUPER ADMIN ID
# ---------------------------------------------------------
MY_USER_ID = 1313370345851457569

# ---------------------------------------------------------
# JSON DATABASE SETUP FOR TICKETS
# ---------------------------------------------------------
DATA_FILE = "ticket_configs.json"

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

def get_ticket_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "is_enabled": False,
            "category_id": None,
            "support_role_id": None,
            "log_channel_id": None,
            "panel_title": "🎫 Contact Support",
            "panel_desc": "Click the button below to open a ticket and speak with our support team.",
            "panel_color": "#5865F2"
        }
        save_data(data)
    return data[g_id]

def save_ticket_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

# ---------------------------------------------------------
# EMBED GENERATOR FOR SETUP DASHBOARD
# ---------------------------------------------------------
def get_setup_embed(config):
    try: color = discord.Color.from_str(config['panel_color'])
    except: color = discord.Color.blurple()
        
    embed = discord.Embed(title="⚙️ Ultimate Ticket Setup", color=color)
    
    status = "✅ Active" if config['is_enabled'] else "❌ Disabled"
    cat = f"<#{config['category_id']}>" if config['category_id'] else "None"
    role = f"<@&{config['support_role_id']}>" if config['support_role_id'] else "None"
    log_ch = f"<#{config['log_channel_id']}>" if config['log_channel_id'] else "None"
    
    embed.add_field(name="📌 Routing Setup", value=f"**Status:** {status}\n**Category:** {cat}\n**Support Role:** {role}\n**Log Channel:** {log_ch}", inline=False)
    embed.add_field(name="🎨 Panel Design", value=f"**Title:** {config['panel_title']}\n**Color:** {config['panel_color']}", inline=False)
    
    return embed


# ---------------------------------------------------------
# PERSISTENT VIEWS (For Users & Tickets)
# ---------------------------------------------------------
class TicketActiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds... Generating transcript...", ephemeral=False)
        
        # Transcript Generation
        messages = [message async for message in interaction.channel.history(limit=200, oldest_first=True)]
        transcript = f"--- Transcript for {interaction.channel.name} ---\n\n"
        for msg in messages:
            time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript += f"[{time_str}] {msg.author.name}: {msg.clean_content}\n"
            
        transcript_file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"{interaction.channel.name}_log.txt")
        
        # Send to Log Channel
        config = get_ticket_config(interaction.guild.id)
        if config['log_channel_id']:
            try:
                log_channel = interaction.guild.get_channel(int(config['log_channel_id']))
                if log_channel:
                    log_embed = discord.Embed(title="📜 Ticket Closed", description=f"**Ticket:** {interaction.channel.name}\n**Closed by:** {interaction.user.mention}", color=discord.Color.red())
                    await log_channel.send(embed=log_embed, file=transcript_file)
            except: pass
            
        # Delete Channel
        import asyncio
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except: pass

    @discord.ui.button(label="🙋‍♂️ Claim Ticket", style=discord.ButtonStyle.success, custom_id="ticket_claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_ticket_config(interaction.guild.id)
        # Verify if user has support role
        if config['support_role_id'] and str(config['support_role_id']) not in [str(r.id) for r in interaction.user.roles] and interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.response.send_message("❌ Only support staff can claim tickets!", ephemeral=True)
            return
            
        embed = discord.Embed(description=f"✅ **This ticket has been claimed by {interaction.user.mention}.** They will assist you shortly.", color=discord.Color.green())
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=embed)


class TicketReasonModal(discord.ui.Modal, title="🎫 Create a Ticket"):
    reason = discord.ui.TextInput(label="Reason for ticket", style=discord.TextStyle.paragraph, placeholder="Explain your issue briefly...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        config = get_ticket_config(interaction.guild.id)
        guild = interaction.guild
        
        if not config['is_enabled'] or not config['category_id']:
            await interaction.response.send_message("❌ Ticket system is not fully setup yet!", ephemeral=True)
            return
            
        category = guild.get_channel(int(config['category_id']))
        support_role = guild.get_role(int(config['support_role_id'])) if config['support_role_id'] else None
        
        if not category:
            await interaction.response.send_message("❌ Ticket category not found. Please contact admin.", ephemeral=True)
            return
            
        # Set Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            
        # Create Channel
        ticket_name = f"ticket-{interaction.user.name}"
        try:
            ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)
            
            # Send Welcome Message inside ticket
            embed = discord.Embed(title="🎫 Ticket Opened", description=f"Hello {interaction.user.mention},\n\nOur support team will be with you shortly.\n**Reason:** {self.reason.value}", color=discord.Color.blue())
            ping_msg = f"{interaction.user.mention}"
            if support_role: ping_msg += f" <@&{support_role.id}>"
            
            await ticket_channel.send(content=ping_msg, embed=embed, view=TicketActiveView())
            await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create ticket: {e}", ephemeral=True)

class CreateTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="panel_create_ticket")
    async def btn_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketReasonModal())


# ---------------------------------------------------------
# SETUP DASHBOARD MENUS
# ---------------------------------------------------------
class CategorySelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.category], placeholder="Select Ticket Category", row=0)
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_ticket_config(self.guild_id)
        config['category_id'] = str(select.values[0].id)
        save_ticket_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_setup_embed(config), view=TicketDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Category set to {select.values[0].name}!", ephemeral=True)

class RoleSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select Support Role", row=0)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        config = get_ticket_config(self.guild_id)
        config['support_role_id'] = str(select.values[0].id)
        save_ticket_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_setup_embed(config), view=TicketDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Support Role set!", ephemeral=True)

class LogChannelSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select Log Channel", row=0)
    async def select_log(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_ticket_config(self.guild_id)
        config['log_channel_id'] = str(select.values[0].id)
        save_ticket_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_setup_embed(config), view=TicketDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Log Channel set!", ephemeral=True)

class PanelDesignModal(discord.ui.Modal, title="🎨 Design Ticket Panel"):
    p_title = discord.ui.TextInput(label="Panel Title", style=discord.TextStyle.short)
    p_desc = discord.ui.TextInput(label="Panel Description", style=discord.TextStyle.paragraph)
    p_color = discord.ui.TextInput(label="Embed Color (Hex)", style=discord.TextStyle.short)

    def __init__(self, guild_id: int, config: dict):
        super().__init__()
        self.guild_id = guild_id
        self.config = config
        self.p_title.default = config['panel_title']
        self.p_desc.default = config['panel_desc']
        self.p_color.default = config['panel_color']

    async def on_submit(self, interaction: discord.Interaction):
        self.config['panel_title'] = self.p_title.value
        self.config['panel_desc'] = self.p_desc.value
        self.config['panel_color'] = self.p_color.value
        save_ticket_config(self.guild_id, self.config)
        await interaction.response.edit_message(embed=get_setup_embed(self.config), view=TicketDashboardView(self.guild_id))
        await interaction.followup.send("✅ Panel Design updated!", ephemeral=True)

# ---------------------------------------------------------
# MAIN SETUP DASHBOARD VIEW
# ---------------------------------------------------------
class TicketDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_ticket_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable"
            self.btn_toggle.style = discord.ButtonStyle.success

    # ROW 0
    @discord.ui.button(label="📁 Set Category", style=discord.ButtonStyle.primary, row=0)
    async def btn_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=CategorySelectView(self.guild_id))

    @discord.ui.button(label="🎭 Support Role", style=discord.ButtonStyle.primary, row=0)
    async def btn_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=RoleSelectView(self.guild_id))

    @discord.ui.button(label="📢 Log Channel", style=discord.ButtonStyle.primary, row=0)
    async def btn_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=LogChannelSelectView(self.guild_id))

    # ROW 1
    @discord.ui.button(label="🎨 Design Panel", style=discord.ButtonStyle.secondary, row=1)
    async def btn_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PanelDesignModal(self.guild_id, get_ticket_config(self.guild_id)))

    @discord.ui.button(label="📤 Send Panel Here", style=discord.ButtonStyle.success, row=1)
    async def btn_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_ticket_config(self.guild_id)
        if not config['category_id']:
            await interaction.response.send_message("⚠️ Please set a Category first!", ephemeral=True)
            return
        
        try: color = discord.Color.from_str(config['panel_color'])
        except: color = discord.Color.blurple()
            
        embed = discord.Embed(title=config['panel_title'], description=config['panel_desc'], color=color)
        await interaction.channel.send(embed=embed, view=CreateTicketView())
        await interaction.response.send_message("✅ Ticket Panel sent successfully!", ephemeral=True)

    @discord.ui.button(label="Toggle", custom_id="btn_ticket_toggle", row=1)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_ticket_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_ticket_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_setup_embed(config), view=TicketDashboardView(self.guild_id))


# ---------------------------------------------------------
# MAIN COG LOGIC
# ---------------------------------------------------------
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views so buttons work after restart
        self.bot.add_view(CreateTicketView())
        self.bot.add_view(TicketActiveView())

    @app_commands.command(name="ticket_setup", description="Open the Ultimate Ticket Setup Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        # Only Server Owner AND Developer (You)
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.response.send_message("❌ Only the Server Owner or Bot Developer can configure Tickets!", ephemeral=True)
            return
            
        config = get_ticket_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_setup_embed(config), view=TicketDashboardView(interaction.guild.id), ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
  
