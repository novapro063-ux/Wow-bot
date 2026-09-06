import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import time

# ---------------------------------------------------------
# DATABASE & FILE SYSTEM
# ---------------------------------------------------------
DB_FILE = "templates.json"

def load_templates():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_templates(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

# ---------------------------------------------------------
# UI EMBEDS
# ---------------------------------------------------------
def get_dashboard_embed(user: discord.User):
    embed = discord.Embed(
        title="⚙️ Server Template Manager",
        description="Welcome to the Ultimate Server Cloner!\n\n"
                    "📥 **Copy:** Clone this current server design.\n"
                    "🚀 **Load:** View & paste your saved templates.\n"
                    "🔒 *Your templates are private to your User ID.*",
        color=discord.Color.from_str("#2b2d31")
    )
    data = load_templates()
    user_id = str(user.id)
    user_templates = data.get(user_id, {})
    embed.add_field(name="📁 Your Saved Templates", value=f"**{len(user_templates)}** templates available.")
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed

def get_preview_embed(template_data):
    # Top roles
    roles = template_data.get("roles", [])
    top_roles = ", ".join([r["name"] for r in roles[:5]]) + ("..." if len(roles) > 5 else "")
    
    # Categories and Channels string builder
    preview_text = f"👑 **Top Roles:** {top_roles}\n\n"
    
    cats = template_data.get("categories", [])
    total_ch = sum(len(c["channels"]) for c in cats) + len(template_data.get("uncategorized", []))
    
    # Build tree
    for cat in cats[:5]: # Show max 5 categories in preview
        preview_text += f"📁 **{cat['name']}**\n"
        ch_list = cat["channels"]
        for i, ch in enumerate(ch_list[:3]): # Show max 3 channels per category
            symbol = "┗" if i == len(ch_list)-1 and len(ch_list) <= 3 else "┣"
            icon = "🔊" if ch["type"] == "voice" else "💬"
            preview_text += f" {symbol} {icon} {ch['name']}\n"
        if len(ch_list) > 3:
            preview_text += f" ┗ *... and {len(ch_list)-3} more channels*\n"
        preview_text += "\n"
        
    if len(cats) > 5:
        preview_text += f"📁 *... and {len(cats)-5} more categories*\n\n"

    embed = discord.Embed(
        title=f"🔍 Template Overview: {template_data['name']}",
        description=f"*{template_data.get('description', 'No description')}*\n\n{preview_text}",
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Total: {len(roles)} Roles | {total_ch} Channels | Saved on <t:{template_data['created_at']}:d>")
    return embed

# ---------------------------------------------------------
# MODALS (Forms)
# ---------------------------------------------------------
class SaveTemplateModal(discord.ui.Modal, title="📥 Copy Server Design"):
    t_name = discord.ui.TextInput(label="Template Name (Leave empty for Server Name)", style=discord.TextStyle.short, required=False)
    t_desc = discord.ui.TextInput(label="Short Description", style=discord.TextStyle.short, required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        # Gathering Server Data
        template = {
            "name": self.t_name.value.strip() or guild.name,
            "description": self.t_desc.value.strip() or "No description provided.",
            "created_at": int(time.time()),
            "roles": [],
            "categories": [],
            "uncategorized": []
        }

        # Backup Roles (Excluding everyone, bot roles, integrations)
        for r in reversed(guild.roles):
            if r.is_default() or r.is_bot_managed() or r.is_integration(): continue
            template["roles"].append({
                "name": r.name,
                "color": r.color.value,
                "permissions": r.permissions.value,
                "hoist": r.hoist,
                "mentionable": r.mentionable
            })

        # Backup Categories and Channels
        for cat in guild.categories:
            cat_data = {"name": cat.name, "channels": []}
            for ch in cat.channels:
                ch_data = {"name": ch.name, "type": str(ch.type)}
                if isinstance(ch, discord.TextChannel):
                    ch_data.update({"topic": ch.topic, "nsfw": ch.nsfw})
                elif isinstance(ch, discord.VoiceChannel):
                    ch_data.update({"bitrate": ch.bitrate, "user_limit": ch.user_limit})
                cat_data["channels"].append(ch_data)
            template["categories"].append(cat_data)

        # Save to DB
        data = load_templates()
        user_id = str(interaction.user.id)
        if user_id not in data: data[user_id] = {}
        
        template_id = str(int(time.time()))
        data[user_id][template_id] = template
        save_templates(data)

        await interaction.followup.send(f"✅ Template **{template['name']}** has been successfully saved to your vault!", ephemeral=True)


class ConfirmNukeModal(discord.ui.Modal, title="⚠️ DANGER: CONFIRM WIPE"):
    confirm = discord.ui.TextInput(label="Type 'CONFIRM' to wipe server & paste", style=discord.TextStyle.short, placeholder="CONFIRM", required=True)

    def __init__(self, template_data):
        super().__init__()
        self.template_data = template_data

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value != "CONFIRM":
            await interaction.response.send_message("❌ Cancelled. You did not type 'CONFIRM'.", ephemeral=True)
            return
        
        await interaction.response.send_message("⚠️ **INITIATING SERVER WIPE & REBUILD...** Please wait, this might take a few minutes.", ephemeral=True)
        
        # Start Background Process
        asyncio.create_task(rebuild_server(interaction.guild, self.template_data, interaction.user))


# ---------------------------------------------------------
# CORE LOGIC: WIPE & BUILD (Anti-Ban Safe)
# ---------------------------------------------------------
async def rebuild_server(guild, template, user):
    try:
        # 1. Create a safe temporary channel for logs
        log_channel = await guild.create_text_channel("build-logs")
        await log_channel.send(f"🛠️ Starting Server Wipe & Clone requested by {user.mention}...")

        # 2. Delete all existing channels (except log)
        await log_channel.send("🧹 Wiping channels...")
        for ch in guild.channels:
            if ch.id != log_channel.id:
                try: 
                    await ch.delete()
                    await asyncio.sleep(0.3) # Rate limit protection
                except: pass

        # 3. Delete all roles (that bot can touch)
        await log_channel.send("🧹 Wiping roles...")
        for r in guild.roles:
            if not r.is_default() and not r.is_bot_managed() and r < guild.me.top_role:
                try: 
                    await r.delete()
                    await asyncio.sleep(0.3)
                except: pass

        # 4. Create Roles
        await log_channel.send("✨ Creating new roles...")
        role_mapping = {} # Store new roles if needed for permissions later
        for r_data in reversed(template["roles"]): # Reverse to maintain order from bottom up
            try:
                new_role = await guild.create_role(
                    name=r_data["name"], 
                    color=discord.Color(r_data["color"]), 
                    permissions=discord.Permissions(r_data["permissions"]),
                    hoist=r_data["hoist"],
                    mentionable=r_data["mentionable"]
                )
                role_mapping[r_data["name"]] = new_role
                await asyncio.sleep(0.3)
            except: pass

        # 5. Create Categories & Channels
        await log_channel.send("📁 Creating categories and channels...")
        for cat_data in template["categories"]:
            try:
                cat = await guild.create_category(name=cat_data["name"])
                await asyncio.sleep(0.3)
                for ch_data in cat_data["channels"]:
                    try:
                        if ch_data["type"] == "text":
                            await cat.create_text_channel(name=ch_data["name"], topic=ch_data.get("topic"), nsfw=ch_data.get("nsfw", False))
                        elif ch_data["type"] == "voice":
                            await cat.create_voice_channel(name=ch_data["name"], bitrate=ch_data.get("bitrate", 64000), user_limit=ch_data.get("user_limit", 0))
                        await asyncio.sleep(0.3)
                    except: pass
            except: pass

        # Finish
        await log_channel.send(f"✅ **TEMPLATE LOADED SUCCESSFULLY!** {user.mention}")
    
    except Exception as e:
        print(f"Error during rebuild: {e}")


# ---------------------------------------------------------
# INTERACTIVE VIEWS (Select Menus & Buttons)
# ---------------------------------------------------------
class TemplatePreviewView(discord.ui.View):
    def __init__(self, template_data):
        super().__init__(timeout=None)
        self.template_data = template_data

    @discord.ui.button(label="⚠️ Confirm & Overwrite Server", style=discord.ButtonStyle.danger, emoji="💥", row=0)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfirmNukeModal(self.template_data))

    @discord.ui.button(label="🔙 Back to Templates", style=discord.ButtonStyle.secondary, row=1)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_dashboard_embed(interaction.user), view=TemplateDashboardView(interaction.user.id))


class LoadTemplateSelect(discord.ui.Select):
    def __init__(self, user_id):
        data = load_templates()
        user_templates = data.get(str(user_id), {})
        
        options = []
        for t_id, t_info in user_templates.items():
            if len(options) >= 25: break
            options.append(discord.SelectOption(label=t_info["name"], description=t_info["description"][:50], value=t_id, emoji="📁"))
            
        if not options:
            options.append(discord.SelectOption(label="No templates found", value="none"))
            
        super().__init__(placeholder="🚀 Select a template to preview...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
            
        data = load_templates()
        user_id = str(interaction.user.id)
        template_data = data.get(user_id, {}).get(self.values[0])
        
        if template_data:
            await interaction.response.edit_message(embed=get_preview_embed(template_data), view=TemplatePreviewView(template_data))


class TemplateDashboardView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.add_item(LoadTemplateSelect(user_id))

    @discord.ui.button(label="📥 Copy Current Server", style=discord.ButtonStyle.success, emoji="📋", row=1)
    async def btn_copy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SaveTemplateModal())


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------
class TemplateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="template_manager", description="Copy or load full server templates (Roles, Channels, Categories)")
    @app_commands.default_permissions(administrator=True)
    async def template_manager(self, interaction: discord.Interaction):
        # Admin check
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an Administrator to use this!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            embed=get_dashboard_embed(interaction.user), 
            view=TemplateDashboardView(interaction.user.id), 
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(TemplateCog(bot))
          
