import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select, ChannelSelect
import json
import os
import datetime

# ==========================================
# DATABASE SETUP (JSON)
# ==========================================
DATA_FILE = "request_data.json"

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

def ensure_guild_data(guild_id: str):
    data = load_data()
    changed = False
    
    if guild_id not in data:
        data[guild_id] = {}
        changed = True

    if "panel" not in data[guild_id]:
        data[guild_id]["panel"] = {
            "title": "📝 Server Request Panel",
            "desc": "Click the button below to submit your request or suggestion.",
            "image": "",
            "btn_text": "Submit Request",
            "btn_emoji": "📩"
        }
        changed = True
        
    if "fields" not in data[guild_id]:
        data[guild_id]["fields"] = [
            {"label": "What is your request?", "placeholder": "Describe your request in detail...", "required": True},
            {}, {}, {}, {} 
        ]
        changed = True

    if "log_channel_id" not in data[guild_id]:
        data[guild_id]["log_channel_id"] = None
        changed = True

    if "target_channel_id" not in data[guild_id]:
        data[guild_id]["target_channel_id"] = None
        changed = True
        
    if changed:
        save_data(data)
    return data

# ==========================================
# 1. USER FACING VIEWS (Panel & Modal)
# ==========================================
class DynamicRequestModal(Modal):
    def __init__(self, guild_id: str):
        data = load_data().get(guild_id, {})
        panel_title = data.get("panel", {}).get("title", "Submit Request")[:45]
        super().__init__(title=panel_title)
        
        self.guild_id = guild_id
        self.fields_data = data.get("fields", [])
        self.inputs = []
        
        valid_fields = [f for f in self.fields_data if f.get("label")]
        
        if not valid_fields:
            ti = TextInput(label="Your Request", style=discord.TextStyle.paragraph, required=True)
            self.add_item(ti)
            self.inputs.append(ti)
        else:
            for f in valid_fields:
                ti = TextInput(
                    label=f["label"][:45], 
                    placeholder=f.get("placeholder", "")[:100], 
                    required=f.get("required", True),
                    style=discord.TextStyle.paragraph
                )
                self.add_item(ti)
                self.inputs.append(ti)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data().get(self.guild_id, {})
        log_channel_id = data.get("log_channel_id")
        
        if not log_channel_id:
            return await interaction.response.send_message("❌ The admins haven't set a log channel for requests yet!", ephemeral=True)
            
        log_channel = interaction.guild.get_channel(log_channel_id)
        if not log_channel:
            return await interaction.response.send_message("❌ Request log channel is missing or deleted. Contact admins.", ephemeral=True)
            
        embed = discord.Embed(
            title="📩 New Request Received",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        
        for text_input in self.inputs:
            val = text_input.value if text_input.value else "N/A"
            embed.add_field(name=text_input.label, value=f"```{val[:1000]}```", inline=False)
            
        try:
            await log_channel.send(embed=embed)
            await interaction.response.send_message("✅ Your request has been submitted successfully!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot doesn't have permission to send messages in the log channel.", ephemeral=True)

class RequestPanelView(View):
    def __init__(self, btn_text: str, btn_emoji: str):
        super().__init__(timeout=None)
        btn = Button(
            label=btn_text if btn_text else "Submit Request", 
            emoji=btn_emoji if btn_emoji else "📩", 
            style=discord.ButtonStyle.primary, 
            custom_id="persistent_request_btn"
        )
        async def btn_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(DynamicRequestModal(str(interaction.guild.id)))
        btn.callback = btn_callback
        self.add_item(btn)

# ==========================================
# 2. ADMIN DASHBOARD MODALS & VIEWS
# ==========================================
class EditPanelModal(Modal):
    def __init__(self, current_data: dict):
        super().__init__(title="📝 Edit Request Panel")
        self.title_input = TextInput(label="Panel Title", default=current_data.get("title", ""), required=True)
        self.desc_input = TextInput(label="Panel Description", style=discord.TextStyle.paragraph, default=current_data.get("desc", ""), required=True)
        self.btn_text = TextInput(label="Button Text", default=current_data.get("btn_text", "Submit Request"), required=True, max_length=80)
        self.btn_emoji = TextInput(label="Button Emoji", default=current_data.get("btn_emoji", "📩"), required=False, max_length=5)
        self.image_url = TextInput(label="GIF / Image URL (Optional)", default=current_data.get("image", ""), required=False)

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.btn_text)
        self.add_item(self.btn_emoji)
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        guild_id = str(interaction.guild.id)
        
        data[guild_id]["panel"]["title"] = self.title_input.value
        data[guild_id]["panel"]["desc"] = self.desc_input.value
        data[guild_id]["panel"]["btn_text"] = self.btn_text.value
        data[guild_id]["panel"]["btn_emoji"] = self.btn_emoji.value
        data[guild_id]["panel"]["image"] = self.image_url.value.strip()
        
        save_data(data)
        await interaction.response.send_message("✅ Panel details & GIF updated successfully!", ephemeral=True)

class EditFieldModal(Modal):
    def __init__(self, field_index: int, current_field_data: dict):
        super().__init__(title=f"⚙️ Edit Form Field {field_index + 1}")
        self.field_index = field_index
        
        self.label_input = TextInput(
            label="Question / Field Title (Leave empty to remove)", 
            placeholder="e.g. What is your Minecraft IGN?", 
            default=current_field_data.get("label", ""), 
            required=False,
            max_length=45
        )
        self.placeholder_input = TextInput(
            label="Placeholder (Optional)", 
            placeholder="e.g. Type your name here...", 
            default=current_field_data.get("placeholder", ""), 
            required=False,
            max_length=100
        )
        self.required_input = TextInput(
            label="Is it required? (Type 'yes' or 'no')", 
            default="yes" if current_field_data.get("required", True) else "no", 
            required=True,
            max_length=3
        )
        
        self.add_item(self.label_input)
        self.add_item(self.placeholder_input)
        self.add_item(self.required_input)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        guild_id = str(interaction.guild.id)
        is_req = self.required_input.value.strip().lower() == "yes"
        
        if not self.label_input.value.strip():
            data[guild_id]["fields"][self.field_index] = {}
            msg = f"🗑️ Field {self.field_index + 1} has been removed/cleared."
        else:
            data[guild_id]["fields"][self.field_index] = {
                "label": self.label_input.value.strip(),
                "placeholder": self.placeholder_input.value.strip(),
                "required": is_req
            }
            msg = f"✅ Field {self.field_index + 1} updated successfully!"
            
        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

class DashboardView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # 1. Edit Panel
        btn_edit = Button(label="📝 Edit Panel Text & GIF", style=discord.ButtonStyle.primary, row=0)
        async def edit_panel_callback(interaction: discord.Interaction):
            data = ensure_guild_data(str(interaction.guild.id))
            await interaction.response.send_modal(EditPanelModal(data["panel"]))
        btn_edit.callback = edit_panel_callback
        self.add_item(btn_edit)
        
        # 2. Send Panel (With Defer to stop timeout)
        btn_send = Button(label="🚀 Send Panel", style=discord.ButtonStyle.success, row=0)
        async def send_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True) # Tells Discord to wait (stops timeout)
            
            data = load_data().get(str(interaction.guild.id), {})
            panel_data = data.get("panel", {})
            target_id = data.get("target_channel_id")
            
            target = interaction.guild.get_channel(target_id) if target_id else interaction.channel
            if not target: target = interaction.channel
            
            embed = discord.Embed(
                title=panel_data.get("title", "Server Request"),
                description=panel_data.get("desc", "Click to submit."),
                color=discord.Color.blurple()
            )
            
            image_url = panel_data.get("image", "")
            if image_url and image_url.startswith("http"):
                embed.set_image(url=image_url)
            
            view = RequestPanelView(panel_data.get("btn_text"), panel_data.get("btn_emoji"))
            
            try:
                await target.send(embed=embed, view=view)
                await interaction.followup.send(f"✅ Request Panel successfully sent to {target.mention}!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Missing permissions to send messages in {target.mention}.", ephemeral=True)
        btn_send.callback = send_callback
        self.add_item(btn_send)

        # 3. Setup Questions Modal
        options = [discord.SelectOption(label=f"Edit Form Question {i+1}", value=str(i), emoji="⚙️") for i in range(5)]
        field_select = Select(placeholder="⚙️ Setup Modal Questions (Max 5)...", options=options, row=1)
        async def field_select_callback(interaction: discord.Interaction):
            idx = int(field_select.values[0])
            data = ensure_guild_data(str(interaction.guild.id))
            current_field = data["fields"][idx]
            await interaction.response.send_modal(EditFieldModal(idx, current_field))
        field_select.callback = field_select_callback
        self.add_item(field_select)

        # 4. Select Log Channel (With Defer)
        log_select = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="📜 Select Log Channel (Where requests go)", row=2)
        async def log_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            data = load_data()
            data[str(interaction.guild.id)]["log_channel_id"] = log_select.values[0].id
            save_data(data)
            await interaction.followup.send(f"✅ Request Log Channel set to {log_select.values[0].mention}", ephemeral=True)
        log_select.callback = log_callback
        self.add_item(log_select)

        # 5. Select Target Channel (With Defer)
        target_select = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="📍 Set Target Channel (Optional)", row=3)
        async def target_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            data = load_data()
            data[str(interaction.guild.id)]["target_channel_id"] = target_select.values[0].id
            save_data(data)
            await interaction.followup.send(f"✅ Target channel set to {target_select.values[0].mention}. Now click '🚀 Send Panel' to deploy.", ephemeral=True)
        target_select.callback = target_callback
        self.add_item(target_select)


# ==========================================
# 3. MAIN COG
# ==========================================
class RequestSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(RequestPanelView("Submit", "📩"))

    @app_commands.command(name="request_dashboard", description="🛠️ Configure the Advanced Request System")
    @app_commands.checks.has_permissions(administrator=True)
    async def request_dashboard(self, interaction: discord.Interaction):
        ensure_guild_data(str(interaction.guild.id))
        embed = discord.Embed(
            title="⚙️ Advanced Request Master Dashboard",
            description=(
                "Welcome to the Request System Setup!\n\n"
                "**1. Edit Panel Text & GIF:** Change the message, button, and image.\n"
                "**2. Setup Questions:** Use the dropdown to set up to 5 questions users have to answer.\n"
                "**3. Log Channel:** Select where the submitted requests will be posted.\n"
                "**4. Target Channel:** Optional. Select where to send the panel, then click **Send Panel**."
            ),
            color=discord.Color.dark_teal()
        )
        await interaction.response.send_message(embed=embed, view=DashboardView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(RequestSystemCog(bot))
            
