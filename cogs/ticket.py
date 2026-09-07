import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select, RoleSelect, ChannelSelect
import datetime
import json
import os
import io
import asyncio

# ---------------------------------------------------------
# DEVELOPER / SUPER ADMIN ID
# ---------------------------------------------------------
MY_USER_ID = 1313370345851457569

# ---------------------------------------------------------
# JSON DATABASE (Config Functions)
# ---------------------------------------------------------
DATA_FILE = "ticket_configs.json"

def load_config():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_config(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ================= 1. MODALS (এডিটিং ফর্ম) =================

class ContentModal(Modal, title="📝 Edit Panel Text"):
    title_input = TextInput(label="Title", placeholder="Support Panel", required=True)
    desc_input = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Select a category below...", required=True)
    footer_input = TextInput(label="Footer", placeholder="Powered by Support Bot", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {}
        
        config[guild_id]["ticket_config"]["title"] = self.title_input.value
        config[guild_id]["ticket_config"]["description"] = self.desc_input.value
        config[guild_id]["ticket_config"]["footer"] = self.footer_input.value
        save_config(config)
        await interaction.response.send_message("✅ **Text Updated!** Use `/ticket_set` to see changes.", ephemeral=True)

class VisualModal(Modal, title="🎨 Edit Visuals"):
    image_url = TextInput(label="Main GIF/Image URL", placeholder="https://...", required=False)
    thumb_url = TextInput(label="Thumbnail URL", placeholder="https://...", required=False)
    color_hex = TextInput(label="Color (Hex)", placeholder="#00ff00", max_length=7, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {}
        
        if self.image_url.value: config[guild_id]["ticket_config"]["image"] = self.image_url.value
        if self.thumb_url.value: config[guild_id]["ticket_config"]["thumbnail"] = self.thumb_url.value
        if self.color_hex.value: config[guild_id]["ticket_config"]["color"] = self.color_hex.value
        save_config(config)
        await interaction.response.send_message("✅ **Visuals Updated!** Use `/ticket_set` to see changes.", ephemeral=True)

class CategoryModal(Modal, title="📂 Add New Category"):
    name = TextInput(label="Name", placeholder="Donation", required=True)
    emoji = TextInput(label="Emoji", placeholder="💰", max_length=2, required=True)
    desc = TextInput(label="Description", placeholder="For donations...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {}
        if "categories" not in config[guild_id]["ticket_config"]: config[guild_id]["ticket_config"]["categories"] = []

        new_cat = {"label": self.name.value, "emoji": self.emoji.value, "description": self.desc.value, "value": self.name.value}
        config[guild_id]["ticket_config"]["categories"].append(new_cat)
        save_config(config)
        await interaction.response.send_message(f"✅ Added Category: **{self.name.value}**", ephemeral=True)


# ================= 2. ACTIVE TICKET LOGIC (The Advanced Features) =================

class RenameTicketModal(Modal, title="✏️ Rename Ticket"):
    new_name = TextInput(label="New Channel Name", style=discord.TextStyle.short, placeholder="e.g. solved-username", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            old_name = interaction.channel.name
            await interaction.channel.edit(name=self.new_name.value.replace(" ", "-"))
            await interaction.followup.send(f"✅ Ticket renamed from `{old_name}` to `{self.new_name.value}`.", ephemeral=False)
        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to rename channel.", ephemeral=True)

class TicketConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger, custom_id="confirm_close_yes")
    async def btn_yes(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔒 Generating transcript and closing ticket in 5 seconds...", ephemeral=False)
        for child in self.children: child.disabled = True
        await interaction.message.edit(view=self)
        
        # Transcript Generation
        messages = [message async for message in interaction.channel.history(limit=500, oldest_first=True)]
        transcript = f"--- Ticket Transcript: {interaction.channel.name} ---\n--- Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n\n"
        for msg in messages:
            time_str = msg.created_at.strftime("%H:%M:%S")
            transcript += f"[{time_str}] {msg.author.name}: {msg.clean_content}\n"
            
        transcript_file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"{interaction.channel.name}_log.txt")
        
        # Route to Log Channel
        config = load_config()
        guild_id = str(interaction.guild.id)
        log_id = config.get(guild_id, {}).get("ticket_config", {}).get("log_channel_id")
        
        if log_id:
            try:
                log_channel = interaction.guild.get_channel(int(log_id))
                if log_channel:
                    embed = discord.Embed(title="📜 Ticket Closed & Logged", color=discord.Color.red())
                    embed.add_field(name="Ticket Name", value=interaction.channel.name, inline=True)
                    embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                    await log_channel.send(embed=embed, file=transcript_file)
            except: pass
            
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except: pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="confirm_close_no")
    async def btn_no(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()


class TicketActiveView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def is_staff(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        if interaction.user.id == interaction.guild.owner_id or interaction.user.id == MY_USER_ID:
            return True
        staff_ids = config.get(guild_id, {}).get("ticket_config", {}).get("staff_roles", [])
        return any(str(r.id) in map(str, staff_ids) for r in interaction.user.roles)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👥 Add / Remove User", custom_id="ticket_user_manage", row=0)
    async def manage_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        await interaction.response.defer(ephemeral=True)
        if not self.is_staff(interaction):
            await interaction.followup.send("❌ Only support staff can add or remove users!", ephemeral=True)
            return

        target_user = select.values[0]
        overwrite = interaction.channel.overwrites_for(target_user)
        
        if overwrite.read_messages is True:
            overwrite.read_messages = False
            overwrite.send_messages = False
            await interaction.channel.set_permissions(target_user, overwrite=overwrite)
            await interaction.followup.send(f"➖ {target_user.mention} removed from the ticket.", ephemeral=False)
        else:
            overwrite.read_messages = True
            overwrite.send_messages = True
            await interaction.channel.set_permissions(target_user, overwrite=overwrite)
            await interaction.followup.send(f"➕ {target_user.mention} added to the ticket.", ephemeral=False)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn", row=1)
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("⚠️ Are you sure you want to close this ticket?", view=TicketConfirmCloseView(), ephemeral=False)

    @discord.ui.button(label="🙋‍♂️ Claim", style=discord.ButtonStyle.success, custom_id="ticket_claim_btn", row=1)
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        if not self.is_staff(interaction):
            await interaction.response.send_message("❌ Only support staff can claim tickets!", ephemeral=True)
            return
        embed = discord.Embed(description=f"✅ **This ticket has been claimed by {interaction.user.mention}.**", color=discord.Color.green())
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=embed)

    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.secondary, custom_id="ticket_rename_btn", row=1)
    async def rename_ticket(self, interaction: discord.Interaction, button: Button):
        if not self.is_staff(interaction):
            await interaction.response.send_message("❌ Only support staff can rename tickets!", ephemeral=True)
            return
        await interaction.response.send_modal(RenameTicketModal())


# ================= 3. TICKET CREATION LOGIC =================

class TicketSelect(Select):
    def __init__(self, categories):
        options = []
        for cat in categories:
            options.append(discord.SelectOption(
                label=cat["label"], emoji=cat["emoji"], description=cat["description"], value=cat["value"]
            ))
        super().__init__(placeholder="👇 Select Support Category...", min_values=1, max_values=1, options=options, custom_id="ticket_dropdown")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category_name = self.values[0]
        guild = interaction.guild
        guild_id = str(guild.id)
        config = load_config()
        
        # ADVANCED: Anti-Spam Check (1 ticket per user)
        cat_id = config.get(guild_id, {}).get("ticket_config", {}).get("category_id")
        category_channel = guild.get_channel(cat_id) if cat_id else None
        
        if category_channel:
            for channel in category_channel.text_channels:
                if interaction.user.name.lower() in channel.name.lower():
                    await interaction.followup.send(f"❌ You already have an open ticket: {channel.mention}. Please close it first.", ephemeral=True)
                    return
        
        # Ticket Count Logic
        count = config[guild_id].get("ticket_count", 0) + 1
        config[guild_id]["ticket_count"] = count
        save_config(config)

        # Channel Name & Perms
        ch_name = f"ticket-{interaction.user.name}-{count:04d}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        # Add Staff Roles
        staff_ids = config[guild_id].get("ticket_config", {}).get("staff_roles", [])
        staff_mentions = []
        for role_id in staff_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
                staff_mentions.append(role.mention)

        try:
            channel = await guild.create_text_channel(name=ch_name, overwrites=overwrites, category=category_channel)
            
            embed = discord.Embed(
                title=f"🎫 {category_name} Support",
                description=f"Hello {interaction.user.mention}!\nWelcome to your **{category_name}** ticket.\n\n**Staff:** {' '.join(staff_mentions)}\nPlease describe your issue.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text="Staff: Use the menu below to manage this ticket.")
            
            await channel.send(content=f"{interaction.user.mention} {' '.join(staff_mentions)}", embed=embed, view=TicketActiveView())
            await interaction.followup.send(f"✅ Ticket Created: {channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: Ensure the bot has 'Manage Channels' permission.", ephemeral=True)

class TicketPanelView(View):
    def __init__(self, categories):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(categories))


# ================= 4. DASHBOARD VIEW (Admin) =================

class DashboardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Edit Text", style=discord.ButtonStyle.primary, row=0)
    async def edit_text(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ContentModal())

    @discord.ui.button(label="🎨 Edit Visuals", style=discord.ButtonStyle.secondary, row=0)
    async def edit_visuals(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VisualModal())

    @discord.ui.button(label="📂 Add Category", style=discord.ButtonStyle.success, row=1)
    async def add_cat(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CategoryModal())

    @discord.ui.button(label="♻️ Reset Defaults", style=discord.ButtonStyle.danger, row=1)
    async def reset_config(self, interaction: discord.Interaction, button: Button):
        config = load_config()
        guild_id = str(interaction.guild.id)
        if guild_id not in config: config[guild_id] = {}
        
        config[guild_id]["ticket_config"] = {} # Full Reset
        save_config(config)
        await interaction.response.send_message("🗑️ **Config Reset!** Now using Default Normal Panel.", ephemeral=True)

    @discord.ui.select(cls=RoleSelect, placeholder="🛡️ Add Staff Role", min_values=1, max_values=1, row=2)
    async def select_role(self, interaction: discord.Interaction, select: RoleSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {"staff_roles": []}
        if "staff_roles" not in config[guild_id]["ticket_config"]: config[guild_id]["ticket_config"]["staff_roles"] = []
        
        config[guild_id]["ticket_config"]["staff_roles"].append(select.values[0].id)
        save_config(config)
        await interaction.response.send_message(f"✅ Added Staff Role: **{select.values[0].name}**", ephemeral=True)

    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.category], placeholder="📂 Set Ticket Category", row=3)
    async def select_channel_cat(self, interaction: discord.Interaction, select: ChannelSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {}
        
        config[guild_id]["ticket_config"]["category_id"] = select.values[0].id
        save_config(config)
        await interaction.response.send_message(f"✅ Tickets will open in: **{select.values[0].name}**", ephemeral=True)

    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="📜 Set Transcript Log Channel", row=4)
    async def select_log_channel(self, interaction: discord.Interaction, select: ChannelSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_config" not in config[guild_id]: config[guild_id]["ticket_config"] = {}
        
        config[guild_id]["ticket_config"]["log_channel_id"] = select.values[0].id
        save_config(config)
        await interaction.response.send_message(f"✅ Closed tickets will be logged in: **{select.values[0].name}**", ephemeral=True)


# ================= 5. MAIN COMMANDS =================

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views
        self.bot.add_view(TicketActiveView())
        # To make the dropdown panel persistent, we would need its specific categories. 
        # For full persistency, it's usually managed dynamically in a real DB, but this works fine for active ones.

    @app_commands.command(name="ticket_dashboard", description="🛠️ Configure Ticket System (Advanced)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_dashboard(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.response.send_message("❌ Only the Server Owner or Bot Developer can configure Tickets!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🎛️ Ultimate Ticket Master Dashboard",
            description="Use the buttons below to customize your ticket panel.\n\n**Advanced Features Active:**\n• Anti-Spam (1 Ticket/User)\n• Live Transcripts (.txt)\n• In-Ticket Tools (Add/Remove, Claim, Rename)\n\nOnce done, use `/ticket_set` to launch it.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=DashboardView(), ephemeral=True)

    @app_commands.command(name="ticket_set", description="🚀 Launch the Ticket Panel in a channel")
    @app_commands.describe(channel="Where to send the panel? (Default: Current Channel)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_set(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        config = load_config()
        guild_id = str(interaction.guild.id)
        
        tc = config.get(guild_id, {}).get("ticket_config", {})

        title = tc.get("title", "🎫 Support Panel")
        desc = tc.get("description", "Please select a category below to open a ticket.")
        footer = tc.get("footer", "Powered by Advanced Bot")
        image = tc.get("image", "https://media.tenor.com/7b2e6X2s-38AAAAC/discord-ticket.gif")
        thumb = tc.get("thumbnail", "https://cdn-icons-png.flaticon.com/512/4542/4542173.png")
        color_str = tc.get("color", "#5865F2").replace("#", "")
        try: color = int(color_str, 16)
        except: color = 0x5865F2

        categories = tc.get("categories", [])
        if not categories:
            categories = [
                {"label": "Help & Support", "emoji": "❓", "description": "General questions", "value": "Help"},
                {"label": "Report User", "emoji": "⚠️", "description": "Report a member", "value": "Report"}
            ]

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_image(url=image)
        embed.set_thumbnail(url=thumb)
        embed.set_footer(text=footer)

        try:
            await target_channel.send(embed=embed, view=TicketPanelView(categories))
            await interaction.response.send_message(f"✅ Advanced Ticket Panel sent to {target_channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send panel: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
