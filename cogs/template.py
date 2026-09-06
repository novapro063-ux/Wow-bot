import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import time

# ---------------------------------------------------------
# DATABASE & FILE SYSTEM (Global Structure)
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
    data = load_templates()
    user_id = str(user.id)
    
    private_count = sum(1 for t in data.values() if t.get("owner_id") == user_id and not t.get("is_public"))
    public_count = sum(1 for t in data.values() if t.get("is_public"))

    embed = discord.Embed(
        title="⚙️ Global Server Template Manager",
        description="Welcome to the Ultimate Server Cloner!\n\n"
                    "🔒 **Private:** Only you can see and use these.\n"
                    "🌍 **Public:** Shared with everyone across all servers.\n"
                    "💥 **Load:** Preview and overwrite a server with a template.",
        color=discord.Color.from_str("#2b2d31")
    )
    
    embed.add_field(name="🔒 Your Private Templates", value=f"**{private_count}** saved", inline=True)
    embed.add_field(name="🌍 Global Public Templates", value=f"**{public_count}** available", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed

def get_preview_embed(template_data):
    roles = template_data.get("roles", [])
    top_roles = ", ".join([r["name"] for r in roles[:5]]) + ("..." if len(roles) > 5 else "")
    
    preview_text = f"👑 **Top Roles:** {top_roles}\n\n"
    
    cats = template_data.get("categories", [])
    total_ch = sum(len(c["channels"]) for c in cats) + len(template_data.get("uncategorized", []))
    
    for cat in cats[:5]: 
        preview_text += f"📁 **{cat['name']}**\n"
        ch_list = cat["channels"]
        for i, ch in enumerate(ch_list[:3]): 
            symbol = "┗" if i == len(ch_list)-1 and len(ch_list) <= 3 else "┣"
            icon = "🔊" if ch["type"] == "voice" else "💬"
            preview_text += f" {symbol} {icon} {ch['name']}\n"
        if len(ch_list) > 3:
            preview_text += f" ┗ *... and {len(ch_list)-3} more channels*\n"
        preview_text += "\n"
        
    if len(cats) > 5:
        preview_text += f"📁 *... and {len(cats)-5} more categories*\n\n"

    status = "🌍 PUBLIC" if template_data.get("is_public") else "🔒 PRIVATE"
    
    embed = discord.Embed(
        title=f"🔍 Preview: {template_data['name']} [{status}]",
        description=f"*{template_data.get('description', 'No description')}*\n\n{preview_text}",
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Total: {len(roles)} Roles | {total_ch} Channels | Saved on <t:{template_data['created_at']}:d>")
    return embed

# ---------------------------------------------------------
# MODALS (Forms)
# ---------------------------------------------------------
class SaveTemplateModal(discord.ui.Modal):
    t_name = discord.ui.TextInput(label="Template Name (Empty for Server Name)", style=discord.TextStyle.short, required=False)
    t_desc = discord.ui.TextInput(label="Short Description", style=discord.TextStyle.short, required=False, max_length=100)

    def __init__(self, is_public: bool):
        super().__init__(title="🌍 Save Public Template" if is_public else "🔒 Save Private Template")
        self.is_public = is_public

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        template = {
            "name": self.t_name.value.strip() or guild.name,
            "description": self.t_desc.value.strip() or "No description provided.",
            "created_at": int(time.time()),
            "owner_id": str(interaction.user.id),
            "is_public": self.is_public,
            "roles": [],
            "categories": [],
            "uncategorized": []
        }

        for r in reversed(guild.roles):
            if r.is_default() or r.is_bot_managed() or r.is_integration(): continue
            template["roles"].append({
                "name": r.name,
                "color": r.color.value,
                "permissions": r.permissions.value,
                "hoist": r.hoist,
                "mentionable": r.mentionable
            })

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

        data = load_templates()
        template_id = str(int(time.time()))
        data[template_id] = template
        save_templates(data)

        status_msg = "🌍 **PUBLIC** Vault (Everyone can use it)" if self.is_public else "🔒 **PRIVATE** Vault (Only you can use it)"
        await interaction.followup.send(f"✅ Template **{template['name']}** saved to {status_msg}!", ephemeral=True)


class ConfirmNukeModal(discord.ui.Modal, title="⚠️ DANGER: CONFIRM WIPE"):
    confirm = discord.ui.TextInput(label="Type 'CONFIRM' to wipe server & paste", style=discord.TextStyle.short, placeholder="CONFIRM", required=True)

    def __init__(self, template_data):
        super().__init__()
        self.template_data = template_data

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value != "CONFIRM":
            await interaction.response.send_message("❌ Cancelled. You did not type 'CONFIRM'.", ephemeral=True)
            return
        
        await interaction.response.send_message("⚠️ **INITIATING SERVER WIPE & REBUILD...** Please wait...", ephemeral=True)
        asyncio.create_task(rebuild_server(interaction.guild, self.template_data, interaction.user))


# ---------------------------------------------------------
# CORE LOGIC: WIPE & BUILD (Anti-Ban Safe)
# ---------------------------------------------------------
async def rebuild_server(guild, template, user):
    try:
        log_channel = await guild.create_text_channel("build-logs")
        await log_channel.send(f"🛠️ Starting Server Wipe & Clone requested by {user.mention}...")

        await log_channel.send("🧹 Wiping channels...")
        for ch in guild.channels:
            if ch.id != log_channel.id:
                try: 
                    await ch.delete()
                    await asyncio.sleep(0.3) 
                except: pass

        await log_channel.send("🧹 Wiping roles...")
        for r in guild.roles:
            if not r.is_default() and not r.is_bot_managed() and r < guild.me.top_role:
                try: 
                    await r.delete()
                    await asyncio.sleep(0.3)
                except: pass

        await log_channel.send("✨ Creating new roles...")
        for r_data in reversed(template["roles"]): 
            try:
                await guild.create_role(
                    name=r_data["name"], 
                    color=discord.Color(r_data["color"]), 
                    permissions=discord.Permissions(r_data["permissions"]),
                    hoist=r_data["hoist"],
                    mentionable=r_data["mentionable"]
                )
                await asyncio.sleep(0.3)
            except: pass

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

        await log_channel.send(f"✅ **TEMPLATE LOADED SUCCESSFULLY!** {user.mention}")
    except Exception as e:
        print(f"Error during rebuild: {e}")


# ---------------------------------------------------------
# INTERACTIVE VIEWS (Select Menus & Buttons)
# ---------------------------------------------------------
class TemplatePreviewView(discord.ui.View):
    def __init__(self, template_id, template_data, user_id):
        super().__init__(timeout=None)
        self.template_id = template_id
        self.template_data = template_data
        self.user_id = user_id

        # Delete button is ONLY visible if the user is the creator (Owner)
        if template_data.get("owner_id") == str(user_id):
            del_btn = discord.ui.Button(label="Delete Template", style=discord.ButtonStyle.secondary, emoji="🗑️", row=0)
            del_btn.callback = self.delete_template
            self.add_item(del_btn)

    @discord.ui.button(label="⚠️ Overwrite Server", style=discord.ButtonStyle.danger, emoji="💥", row=0)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfirmNukeModal(self.template_data))

    @discord.ui.button(label="🔙 Back", style=discord.ButtonStyle.primary, row=0)
    async def btn_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_dashboard_embed(interaction.user), view=TemplateDashboardView(interaction.user.id))

    async def delete_template(self, interaction: discord.Interaction):
        data = load_templates()
        if self.template_id in data:
            del data[self.template_id]
            save_templates(data)
            await interaction.response.send_message("🗑️ Template successfully deleted!", ephemeral=True)
            await interaction.message.edit(embed=get_dashboard_embed(interaction.user), view=TemplateDashboardView(interaction.user.id))


class TemplateSelect(discord.ui.Select):
    def __init__(self, user_id, is_public_menu=False):
        self.is_public_menu = is_public_menu
        data = load_templates()
        options = []
        
        for t_id, t_info in data.items():
            if len(options) >= 25: break
            
            # Condition for Public vs Private menu
            if is_public_menu and t_info.get("is_public"):
                options.append(discord.SelectOption(label=t_info["name"], description=t_info["description"][:50], value=t_id, emoji="🌍"))
            elif not is_public_menu and t_info.get("owner_id") == str(user_id) and not t_info.get("is_public"):
                options.append(discord.SelectOption(label=t_info["name"], description=t_info["description"][:50], value=t_id, emoji="🔒"))
                
        if not options:
            options.append(discord.SelectOption(label="No templates found", value="none"))
            
        placeholder = "🌍 Select a Global Public Template..." if is_public_menu else "🔒 Select your Private Template..."
        super().__init__(placeholder=placeholder, options=options, row=1 if is_public_menu else 0)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
            
        data = load_templates()
        template_id = self.values[0]
        template_data = data.get(template_id)
        
        if template_data:
            await interaction.response.edit_message(embed=get_preview_embed(template_data), view=TemplatePreviewView(template_id, template_data, interaction.user.id))


class TemplateDashboardView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        # Dropdowns
        self.add_item(TemplateSelect(user_id, is_public_menu=False))
        self.add_item(TemplateSelect(user_id, is_public_menu=True))

    @discord.ui.button(label="Save Private", style=discord.ButtonStyle.secondary, emoji="🔒", row=2)
    async def btn_private(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SaveTemplateModal(is_public=False))

    @discord.ui.button(label="Save Public", style=discord.ButtonStyle.success, emoji="🌍", row=2)
    async def btn_public(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SaveTemplateModal(is_public=True))


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------
class TemplateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="template_manager", description="Copy or load full server templates (Public & Private)")
    @app_commands.default_permissions(administrator=True)
    async def template_manager(self, interaction: discord.Interaction):
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
    
