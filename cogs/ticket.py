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

def ensure_guild_data(guild_id: str):
    config = load_config()
    changed = False 
    
    if guild_id not in config:
        config[guild_id] = {}
        changed = True

    if "ticket_count" not in config[guild_id]:
        config[guild_id]["ticket_count"] = 0
        changed = True

    if "select_panel" not in config[guild_id]:
        config[guild_id]["select_panel"] = {
            "title": "🎫 Support Panel (Select Menu)",
            "description": "Please select a category below.",
            "image": "",
            "categories": [],
            "staff_roles": [],
            "log_channel_id": None,
            "target_channel_id": None
        }
        changed = True

    if "button_panels" not in config[guild_id]:
        config[guild_id]["button_panels"] = {}
        changed = True

    for i in range(1, 6):
        if str(i) not in config[guild_id]["button_panels"]:
            config[guild_id]["button_panels"][str(i)] = {
                "title": f"🔘 Support Panel (Buttons) - {i}",
                "description": "Click a button to open a ticket.",
                "image": "",
                "buttons": [],
                "staff_roles": [],
                "log_channel_id": None,
                "target_channel_id": None
            }
            changed = True
            
    if changed:
        save_config(config)
        
    return config

# ================= 1. TICKET CREATION LOGIC =================
async def create_ticket_channel(interaction: discord.Interaction, label: str, emoji: str, target_cat_id: int, staff_roles: list, reason: str):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild.id)
    config = load_config()
    
    target_discord_category = interaction.guild.get_channel(target_cat_id) if target_cat_id else interaction.channel.category

    if target_discord_category:
        for channel in target_discord_category.text_channels:
            if interaction.user.name.lower() in channel.name.lower():
                return await interaction.followup.send(f"❌ You already have an open ticket in this category: {channel.mention}", ephemeral=True)
    
    count = config[guild_id].get("ticket_count", 0) + 1
    config[guild_id]["ticket_count"] = count
    save_config(config)

    ch_name = f"ticket-{interaction.user.name}-{count:04d}"
    
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, attach_files=True),
        interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }

    staff_mentions = []
    for role_id in staff_roles:
        role = interaction.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
            staff_mentions.append(role.mention)

    try:
        channel = await interaction.guild.create_text_channel(name=ch_name, overwrites=overwrites, category=target_discord_category)
        embed = discord.Embed(
            title=f"{emoji} {label} Ticket",
            description=f"Hello {interaction.user.mention}!\nWelcome to your ticket.\n\n**Staff:** {' '.join(staff_mentions)}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
        embed.set_footer(text="Staff: Use the buttons below to manage this ticket.")
        
        await channel.send(content=f"{interaction.user.mention} {' '.join(staff_mentions)}", embed=embed, view=TicketActiveView())
        await interaction.followup.send(f"✅ Ticket Created: {channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ Error: Missing permissions to create channels. Make sure I have 'Manage Channels' permission.", ephemeral=True)

class ReasonModal(Modal):
    def __init__(self, label: str, emoji: str, target_cat_id: int, staff_roles: list):
        super().__init__(title=f"📝 Ticket Reason: {label}")
        self.label_str = label
        self.emoji_str = emoji
        self.target_cat_id = target_cat_id
        self.staff_roles = staff_roles

        self.reason = TextInput(
            label="Why are you opening this ticket?",
            style=discord.TextStyle.paragraph,
            placeholder="Describe your issue shortly...",
            required=True,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket_channel(interaction, self.label_str, self.emoji_str, self.target_cat_id, self.staff_roles, self.reason.value)

class TicketPanelView(View):
    def __init__(self, panel_type: str, panel_data: dict):
        super().__init__(timeout=None)
        staff_roles = panel_data.get("staff_roles", [])
        
        if panel_type == "select":
            categories = panel_data.get("categories", [])
            if not categories: return
            options = [discord.SelectOption(label=c["label"], emoji=c["emoji"], description=c["desc"], value=str(i)) for i, c in enumerate(categories)]
            select = Select(placeholder="👇 Select Support Category...", min_values=1, max_values=1, options=options, custom_id="main_ticket_select")
            async def select_callback(interaction: discord.Interaction):
                idx = int(select.values[0])
                cat = categories[idx]
                await interaction.response.send_modal(ReasonModal(cat["label"], cat["emoji"], cat["category_id"], staff_roles))
            select.callback = select_callback
            self.add_item(select)
            
        elif panel_type == "button":
            buttons = panel_data.get("buttons", [])
            for i, btn_data in enumerate(buttons):
                btn = Button(label=btn_data["label"], emoji=btn_data["emoji"], style=discord.ButtonStyle.primary, custom_id=f"btn_panel_{i}_{btn_data['label']}")
                async def btn_callback(interaction: discord.Interaction, bd=btn_data):
                    await interaction.response.send_modal(ReasonModal(bd["label"], bd["emoji"], bd.get("category_id"), staff_roles))
                btn.callback = btn_callback
                self.add_item(btn)

# ================= 2. ACTIVE TICKET CONTROLS =================
class RenameTicketModal(Modal, title="✏️ Rename Ticket"):
    new_name = TextInput(label="New Channel Name", style=discord.TextStyle.short, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.channel.edit(name=self.new_name.value.replace(" ", "-"))
            await interaction.followup.send(f"✅ Ticket renamed to `{self.new_name.value}`.", ephemeral=False)
        except:
            await interaction.followup.send("❌ Missing permissions.", ephemeral=True)

class TicketConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=60)
    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger)
    async def btn_yes(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔒 Generating transcript & closing ticket in 5 seconds...", ephemeral=False)
        for child in self.children: child.disabled = True
        await interaction.message.edit(view=self)
        
        transcript = f"--- Ticket: {interaction.channel.name} ---\n\n"
        async for msg in interaction.channel.history(limit=500, oldest_first=True):
            transcript += f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.author.name}: {msg.clean_content}\n"
        
        file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"{interaction.channel.name}.txt")
        
        config = load_config()
        guild_id = str(interaction.guild.id)
        log_id = config.get(guild_id, {}).get("select_panel", {}).get("log_channel_id")
        if not log_id:
            for p_id, p_data in config.get(guild_id, {}).get("button_panels", {}).items():
                if p_data.get("log_channel_id"):
                    log_id = p_data["log_channel_id"]; break
                    
        if log_id:
            try:
                log_ch = interaction.guild.get_channel(int(log_id))
                embed = discord.Embed(title="📜 Ticket Closed", description=f"Name: {interaction.channel.name}\nClosed By: {interaction.user.mention}", color=discord.Color.red())
                await log_ch.send(embed=embed, file=file)
            except: pass
            
        await asyncio.sleep(5)
        try: await interaction.channel.delete()
        except: pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def btn_no(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()

class TicketActiveView(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="active_close")
    async def close_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Are you sure you want to close this ticket?", view=TicketConfirmCloseView(), ephemeral=False)
    @discord.ui.button(label="🙋‍♂️ Claim", style=discord.ButtonStyle.success, custom_id="active_claim")
    async def claim_btn(self, interaction: discord.Interaction, button: Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"✅ **Claimed by {interaction.user.mention}.**")
    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.secondary, custom_id="active_rename")
    async def rename_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RenameTicketModal())

# ================= 3. DASHBOARD CONFIGURATION LOGIC =================
class SelectTargetCategoryView(View):
    def __init__(self, label_data: dict):
        super().__init__(timeout=120)
        self.label_data = label_data
    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.category], placeholder="📂 Mandatory: Select target category")
    async def select_category(self, interaction: discord.Interaction, select: ChannelSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        new_cat = {"label": self.label_data["label"], "emoji": self.label_data["emoji"], "desc": self.label_data["desc"], "category_id": select.values[0].id}
        config[guild_id]["select_panel"]["categories"].append(new_cat)
        save_config(config)
        await interaction.response.edit_message(content=f"✅ Select Option added and linked to **{select.values[0].name}**!", view=None)

class OptionalTargetCategoryView(View):
    def __init__(self, panel_id: str, label_data: dict):
        super().__init__(timeout=120)
        self.panel_id = panel_id
        self.label_data = label_data
    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.category], placeholder="📂 Optional: Select target category")
    async def select_category(self, interaction: discord.Interaction, select: ChannelSelect):
        self._save_button(str(interaction.guild.id), select.values[0].id)
        await interaction.response.edit_message(content=f"✅ Button added and linked to **{select.values[0].name}**!", view=None)
    @discord.ui.button(label="Skip (Use Default Category)", style=discord.ButtonStyle.secondary, row=1)
    async def skip_btn(self, interaction: discord.Interaction, button: Button):
        self._save_button(str(interaction.guild.id), None)
        await interaction.response.edit_message(content=f"✅ Button added! (Tickets will open in the default category)", view=None)
    def _save_button(self, guild_id, cat_id):
        config = load_config()
        new_btn = {"label": self.label_data["label"], "emoji": self.label_data["emoji"], "category_id": cat_id}
        config[guild_id]["button_panels"][self.panel_id]["buttons"].append(new_btn)
        save_config(config)

class SetupCategoryModal(Modal):
    def __init__(self, panel_type: str, panel_id: str = None):
        super().__init__(title="📂 Setup Ticket Option")
        self.panel_type = panel_type
        self.panel_id = panel_id
        self.name = TextInput(label="Name (e.g. Support)", required=True)
        self.emoji = TextInput(label="Emoji", max_length=2, required=True)
        self.desc = TextInput(label="Description", required=False) if panel_type == "select" else None
        
        self.add_item(self.name); self.add_item(self.emoji)
        if self.desc: self.add_item(self.desc)

    async def on_submit(self, interaction: discord.Interaction):
        label_data = {"label": self.name.value, "emoji": self.emoji.value, "desc": self.desc.value if self.desc else ""}
        if self.panel_type == "select":
            await interaction.response.send_message("⚙️ **Step 2:** Select which Discord Category these tickets should open in:", view=SelectTargetCategoryView(label_data), ephemeral=True)
        else:
            await interaction.response.send_message("⚙️ **Step 2 (Optional):** Select a specific category, or skip to use default.", view=OptionalTargetCategoryView(self.panel_id, label_data), ephemeral=True)

class ContentModal(Modal, title="📝 Edit Panel Text & GIF"):
    def __init__(self, panel_type: str, current_data: dict, panel_id: str = None):
        super().__init__()
        self.panel_type = panel_type
        self.panel_id = panel_id
        self.title_input = TextInput(label="Title", default=current_data.get("title", ""), required=True)
        self.desc_input = TextInput(label="Description", style=discord.TextStyle.paragraph, default=current_data.get("description", ""), required=True)
        self.image_input = TextInput(label="GIF / Image URL (Optional)", default=current_data.get("image", ""), required=False)
        
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        config = load_config()
        guild_id = str(interaction.guild.id)
        target = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        
        target["title"] = self.title_input.value
        target["description"] = self.desc_input.value
        target["image"] = self.image_input.value.strip()
        save_config(config)
        await interaction.response.send_message(f"✅ Text & GIF Updated!", ephemeral=True)

class PanelEditView(View):
    def __init__(self, panel_type: str, panel_id: str = None):
        super().__init__(timeout=None)
        self.panel_type = panel_type
        self.panel_id = panel_id

    @discord.ui.button(label="📝 Edit Text & GIF", style=discord.ButtonStyle.primary, row=0)
    async def edit_text(self, interaction: discord.Interaction, button: Button):
        config = load_config()
        guild_id = str(interaction.guild.id)
        current_data = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        await interaction.response.send_modal(ContentModal(self.panel_type, current_data, self.panel_id))

    @discord.ui.button(label="➕ Add Category/Button", style=discord.ButtonStyle.primary, row=0)
    async def add_item_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SetupCategoryModal(self.panel_type, self.panel_id))

    @discord.ui.button(label="🚀 Send Panel", style=discord.ButtonStyle.success, row=0)
    async def send_panel_btn(self, interaction: discord.Interaction, button: Button):
        config = load_config()
        guild_id = str(interaction.guild.id)
        panel_data = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        
        target_id = panel_data.get("target_channel_id")
        target_channel = interaction.guild.get_channel(target_id) if target_id else interaction.channel
        if not target_channel: target_channel = interaction.channel
            
        embed = discord.Embed(
            title=panel_data.get("title", "Ticket Support"),
            description=panel_data.get("description", "Choose an option below."),
            color=discord.Color.blurple()
        )
        
        image_url = panel_data.get("image", "")
        if image_url and image_url.startswith("http"):
            embed.set_image(url=image_url)
            
        view = TicketPanelView(self.panel_type, panel_data)
        try:
            await target_channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Successfully sent the ticket panel to {target_channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Missing permissions to send messages in {target_channel.mention}.", ephemeral=True)

    @discord.ui.select(cls=RoleSelect, placeholder="🛡️ Add Staff Role", max_values=1, row=1)
    async def select_role(self, interaction: discord.Interaction, select: RoleSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        target = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        target["staff_roles"].append(select.values[0].id)
        save_config(config)
        await interaction.response.send_message(f"✅ Added Staff Role.", ephemeral=True)

    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="📜 Set Log Channel", row=2)
    async def select_log(self, interaction: discord.Interaction, select: ChannelSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        target = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        target["log_channel_id"] = select.values[0].id
        save_config(config)
        await interaction.response.send_message(f"✅ Log channel set.", ephemeral=True)

    @discord.ui.select(cls=ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="📍 Set Target Channel (Optional)", row=3)
    async def select_target(self, interaction: discord.Interaction, select: ChannelSelect):
        config = load_config()
        guild_id = str(interaction.guild.id)
        target = config[guild_id]["select_panel"] if self.panel_type == "select" else config[guild_id]["button_panels"][self.panel_id]
        target["target_channel_id"] = select.values[0].id
        save_config(config)
        await interaction.response.send_message(f"✅ Target channel set to {select.values[0].mention}. Now click '🚀 Send Panel' to deploy."
