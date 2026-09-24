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
        data[guild_id] = {"panels": {}}
        changed = True
        
    if "panels" not in data[guild_id]:
        data[guild_id]["panels"] = {}
        changed = True

    # ৫টি আলাদা প্যানেল জেনারেট করা হচ্ছে
    for i in range(1, 6):
        pid = str(i)
        if pid not in data[guild_id]["panels"]:
            data[guild_id]["panels"][pid] = {
                "title": f"📝 Request Panel {pid}",
                "desc": "Click the button below to submit your request.",
                "image": "",
                "btn_text": "Submit Request",
                "btn_emoji": "📩",
                "log_channel_id": None,
                "target_channel_id": None,
                "fields": [
                    {"label": "What is your request?", "placeholder": "Describe your request in detail...", "required": True},
                    {}, {}, {}, {} # Max 5 fields
                ]
            }
            changed = True
            
    if changed:
        save_data(data)
    return data

# ==========================================
# 1. USER FACING VIEWS (Panel & Modal)
# ==========================================
class DynamicRequestModal(Modal):
    def __init__(self, guild_id: str, panel_id: str):
        data = load_data().get(guild_id, {}).get("panels", {}).get(panel_id, {})
        panel_title = data.get("title", "Submit Request")[:45]
        super().__init__(title=panel_title)
        
        self.guild_id = guild_id
        self.panel_id = panel_id
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
        data = load_data().get(self.guild_id, {}).get("panels", {}).get(self.panel_id, {})
        log_channel_id = data.get("log_channel_id")
        
        if not log_channel_id:
            return await interaction.response.send_message("❌ The admins haven't set a log channel for this panel yet!", ephemeral=True)
            
        log_channel = interaction.guild.get_channel(log_channel_id)
        if not log_channel:
            return await interaction.response.send_message("❌ Request log channel is missing or deleted.", ephemeral=True)
            
        embed = discord.Embed(
            title=f"📩 New Request (Panel {self.panel_id})",
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
    def __init__(self, panel_id: str, btn_text: str = "Submit", btn_emoji: str = "📩"):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        
        btn = Button(
            label=btn_text, 
            emoji=btn_emoji, 
            style=discord.ButtonStyle.primary, 
            custom_id=f"req_panel_btn_{panel_id}" # পার্মানেন্ট আইডি
        )
        btn.callback = self.btn_callback
        self.add_item(btn)
        
    async def btn_callback(self, interaction: discord.Interaction):
        # Modal কল করার আগে defer করা যায় না, তাই সরাসরি send_modal করতে হবে
        await interaction.response.send_modal(DynamicRequestModal(str(interaction.guild.id), self.panel_id))

# ==========================================
# 2. ADMIN DASHBOARD MODALS & VIEWS
# ==========================================
class EditPanelModal(Modal):
    def __init__(self, panel_id: str, current_data: dict):
        super().__init__(title=f"📝 Edit Request Panel {panel_id}")
        self.panel_id = panel_id
        
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
        
        data[guild_id]["panels"][self.panel_id]["title"] = self.title_input.value
        data[guild_id]["panels"][self.panel_id]["desc"] = self.desc_input.value
        data[guild_id]["panels"][self.panel_id]["btn_text"] = self.btn_text.value
        data[guild_id]["panels"][self.panel_id]["btn_emoji"] = self.btn_emoji.value
        data[guild_id]["panels"][self.panel_id]["image"] = self.image_url.value.strip()
        
        save_data(data)
        await interaction.response.send_message(f"✅ Panel {self.panel_id} details & GIF updated successfully!", ephemeral=True)

class EditFieldModal(Modal):
    def __init__(self, panel_id: str, field_index: int, current_field_data: dict):
        super().__init__(title=f"⚙️ Edit Field {field_index + 1} (Panel {panel_id})")
        self.panel_id = panel_id
        self.field_index = field_index
        
        self.label_input = TextInput(label="Question (Leave empty to remove)", default=current_field_data.get("label", ""), required=False, max_length=45)
        self.placeholder_input = TextInput(label="Placeholder (Optional)", default=current_field_data.get("placeholder", ""), required=False, max_length=100)
        self.required_input = TextInput(label="Is it required? (Type 'yes' or 'no')", default="yes" if current_field_data.get("required", True) else "no", required=True, max_length=3)
        
        self.add_item(self.label_input)
        self.add_item(self.placeholder_input)
        self.add_item(self.required_input)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        guild_id = str(interaction.guild.id)
        is_req = self.required_input.value.strip().lower() == "yes"
        
        if not self.label_input.value.strip():
            data[guild_id]["panels"][self.panel_id]["fields"][self.field_index] = {}
            msg = f"🗑️ Field {self.field_index + 1} removed from Panel {self.panel_id}."
        else:
            data[guild_id]["panels"][self.panel_id]["fields"][self.field_index] = {
                "label": self.label_input.value.strip(),
                "placeholder": self.placeholder_input.value.strip(),
                "required": is_req
            }
            msg = f"✅ Field {self.field_index + 1} updated on Panel {self.panel_id}!"
            
        save_data(data)
        await interaction.response.send_message(msg, ephemeral=True)

# ----------------- PANEL SPECIFIC DASHBOARD -----------------
class PanelEditView(View):
    def __init__(self, panel_id: str):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        
        # 1. Edit Panel Data
        btn_edit = Button(label="📝 Edit Panel Text & GIF", style=discord.ButtonStyle.primary, row=0)
        async def edit_panel_callback(interaction: discord.Interaction):
            data = ensure_guild_data(str(interaction.guild.id))
            panel_data = data["panels"][self.panel_id]
            await interaction.response.send_modal(EditPanelModal(self.panel_id, panel_data))
        btn_edit.callback = edit_panel_callback
        self.add_item(btn_edit)
        
        # 2. Send Panel (With Timeout Fix)
        btn_send = Button(label="🚀 Send Panel", style=discord.ButtonStyle.success, row=0)
        async def send_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True) # টাইমআউট ঠেকানোর জন্য defer
            
            data = load_data().get(str(interaction.guild.id), {}).get("panels", {}).get(self.panel_id, {})
            target_id = data.get("target_channel_id")
            
            target = interaction.guild.get_channel(target_id) if target_id else interaction.channel
            if not target: target = interaction.channel
            
            embed = discord.Embed(
                title=data.get("title", f"Request Panel {self.panel_id}"),
                description=data.get("desc", "Click to submit."),
                color=discord.Color.blurple()
            )
            
            img = data.get("image", "")
            if img and img.startswith("http"):
                embed.set_image(url=img)
            
            view = RequestPanelView(self.panel_id, data.get("btn_text", "Submit"), data.get("btn_emoji", "📩"))
            
            try:
                await target.send(embed=embed, view=view)
                await interaction.followup.send(f"✅ Panel {self.panel_id} successfully sent to {target.mention}!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Missing permissions to send messages in {target.mention}.", ephemeral=True)
        btn_send.callback = send_callback
        self.add_item(btn_send)

        # 3. Back Button
        btn_back = Button(label="🔙 Back", style=discord.ButtonStyle.danger, row=0)
        async def back_callback(interaction: discord.Interaction):
            embed = discord.Embed(title="⚙️ Advanced Request Master Dashboard", description="Select a Panel from 1 to 5 to configure it.", color=discord.Color.dark_teal())
            await interaction.response.edit_message(embed=embed, view=MasterDashboardView())
        btn_back.callback = back_callback
        self.add_item(btn_back)

        # 4. Setup Questions Modal
        options = [discord.SelectOption(label=f"Edit Form Question {i+1}", value=str(i), emoji="⚙️") for i in range(5)]
        field_select = Select(placeholder="⚙️ Setup Modal Questions (Max 5)...", options=options, row=1)
        async def field_select_callback(interaction: discord.Interaction):
            idx = int(field_select.values[0])
            data = ensure_guild_data(str(interaction.guild.id))
            current_field = data["panels"][self.panel_id]["fields"][idx]
            await interaction.response.send_modal(EditFieldModal(self.panel_id, idx, current_field))
        field_select.callback = field_select_callback
        self.add_item(field_select)

        # 5. Log Channel (With Timeout Fix)
        log_select = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="📜 Select Log Channel (Where requests go)", row=2)
        async def log_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            data = load_data()
            data[str(interaction.guild.id)]["panels"][self.panel_id]["log_channel_id"] = log_select.values[0].id
            save_data(data)
            await interaction.followup.send(f"✅ Log Channel for Panel {self.panel_id} set to {log_select.values[0].mention}", ephemeral=True)
        log_select.callback = log_callback
        self.add_item(log_select)

        # 6. Target Channel (With Timeout Fix)
        target_select = ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="📍 Set Target Channel (Optional)", row=3)
        async def target_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            data = load_data()
            data[str(interaction.guild.id)]["panels"][self.panel_id]["target_channel_id"] = target_select.values[0].id
            save_data(data)
            await interaction.followup.send(f"✅ Target channel for Panel {self.panel_id} set. Click '🚀 Send Panel' to deploy.", ephemeral=True)
        target_select.callback = target_callback
        self.add_item(target_select)

# ----------------- MASTER DASHBOARD -----------------
class MasterDashboardView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        options = [discord.SelectOption(label=f"Request Panel {i}", value=str(i), description=f"Configure settings for Panel {i}") for i in range(1, 6)]
        select = Select(placeholder="🎛️ Select a Request Panel to Configure...", options=options)
        
        async def panel_select_callback(interaction: discord.Interaction):
            panel_id = select.values[0]
            ensure_guild_data(str(interaction.guild.id))
            embed = discord.Embed(
                title=f"⚙️ Configuring Request Panel {panel_id}", 
                description="Setup your questions, edit panel text, and choose where to send it.", 
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=PanelEditView(panel_id))
            
        select.callback = panel_select_callback
        self.add_item(select)


# ==========================================
# 3. MAIN COG
# ==========================================
class RequestSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # রিস্টার্ট হলেও যাতে ১ থেকে ৫ পর্যন্ত সব প্যানেলের বাটন কাজ করে, তার জন্য ভিউ রেজিস্টার করা হচ্ছে
        for i in range(1, 6):
            self.bot.add_view(RequestPanelView(str(i)))

    @app_commands.command(name="request_dashboard", description="🛠️ Configure the Multi-Panel Request System")
    @app_commands.checks.has_permissions(administrator=True)
    async def request_dashboard(self, interaction: discord.Interaction):
        ensure_guild_data(str(interaction.guild.id))
        embed = discord.Embed(
            title="⚙️ Advanced Request Master Dashboard",
            description=(
                "Welcome to the Multi-Panel Request System Setup!\n\n"
                "Use the dropdown below to select **Panel 1 to 5**.\n"
                "After selecting a panel, you can set its own specific text, GIF, questions, and channels."
            ),
            color=discord.Color.dark_teal()
        )
        await interaction.response.send_message(embed=embed, view=MasterDashboardView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(RequestSystemCog(bot))
    
