import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime

# ---------------------------------------------------------
# JSON DATABASE SETUP FOR FEEDBACK
# ---------------------------------------------------------
DATA_FILE = "feedback_configs.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

def get_feedback_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "log_channel_id": None,
            "reward_role_id": None
        }
        save_data(data)
    return data[g_id]

def save_feedback_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)


# ---------------------------------------------------------
# 3. FEEDBACK MODAL (Form for Users)
# ---------------------------------------------------------
class FeedbackModal(discord.ui.Modal, title="📝 Submit Your Feedback"):
    rating = discord.ui.TextInput(
        label="Rating (1 to 5 Stars)", 
        style=discord.TextStyle.short, 
        placeholder="Enter a number between 1 and 5...", 
        max_length=1, 
        required=True
    )
    description = discord.ui.TextInput(
        label="Feedback Description", 
        style=discord.TextStyle.paragraph, 
        placeholder="Write your feedback or suggestions here...", 
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = get_feedback_config(guild.id)
        
        # 1. Rating Check
        try:
            star_count = int(self.rating.value.strip())
            star_count = max(1, min(star_count, 5)) 
        except:
            star_count = 5 
            
        stars_str = "⭐" * star_count + "☆" * (5 - star_count)

        # 2. Send Log to Admin Channel
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            try:
                log_channel = guild.get_channel(int(log_channel_id))
                if log_channel:
                    embed = discord.Embed(
                        title="🌟 New Server Feedback",
                        color=discord.Color.gold(),
                        timestamp=datetime.datetime.now()
                    )
                    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                    embed.add_field(name="Rating", value=stars_str, inline=False)
                    embed.add_field(name="Feedback", value=self.description.value, inline=False)
                    embed.set_footer(text=f"User ID: {interaction.user.id}")
                    await log_channel.send(embed=embed)
            except Exception as e:
                print(f"Feedback Log Error: {e}")

        # 3. Give Reward Role
        role_id = config.get("reward_role_id")
        role_given = False
        if role_id:
            try:
                role = guild.get_role(int(role_id))
                if role and guild.me.top_role > role:
                    await interaction.user.add_roles(role)
                    role_given = True
            except:
                pass

        # 4. Reply to User
        msg = f"✅ Thank you for your feedback! You gave us **{star_count} Stars**."
        if role_given:
            msg += f"\n🎉 As a reward, you have received the <@&{role_id}> role!"
            
        await interaction.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------
# 2. USER PANEL VIEW (Persistent Button)
# ---------------------------------------------------------
class FeedbackPanelView(discord.ui.View):
    def __init__(self):
        # timeout=None keeps the button working even after bot restarts
        super().__init__(timeout=None)

    @discord.ui.button(label="📝 Give Feedback", style=discord.ButtonStyle.success, custom_id="btn_give_feedback")
    async def btn_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())


# ---------------------------------------------------------
# 1. SETUP DASHBOARD VIEWS (For Admins)
# ---------------------------------------------------------
class FeedbackChannelSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select Channel for Feedback Logs", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        config = get_feedback_config(self.guild_id)
        config['log_channel_id'] = str(select.values[0].id)
        save_feedback_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_dashboard_embed(config), view=FeedbackDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Feedback Log Channel set to <#{config['log_channel_id']}>!", ephemeral=True)

class FeedbackRoleSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Select Reward Role for Feedback", row=0)
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        config = get_feedback_config(self.guild_id)
        config['reward_role_id'] = str(select.values[0].id)
        save_feedback_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_dashboard_embed(config), view=FeedbackDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Reward Role set to <@&{config['reward_role_id']}>!", ephemeral=True)

def get_dashboard_embed(config):
    embed = discord.Embed(title="⚙️ Feedback System Setup", description="Configure where feedbacks go and what role users get.", color=discord.Color.from_str("#2b2d31"))
    ch = f"<#{config['log_channel_id']}>" if config.get('log_channel_id') else "Not Set"
    rl = f"<@&{config['reward_role_id']}>" if config.get('reward_role_id') else "Not Set"
    embed.add_field(name="📢 Log Channel", value=ch, inline=True)
    embed.add_field(name="🎭 Reward Role", value=rl, inline=True)
    return embed

class FeedbackDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="📢 Set Log Channel", style=discord.ButtonStyle.primary, row=0)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=FeedbackChannelSelect(self.guild_id))

    @discord.ui.button(label="🎭 Set Reward Role", style=discord.ButtonStyle.primary, row=0)
    async def btn_set_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=FeedbackRoleSelect(self.guild_id))


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------
class FeedbackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register the persistent view so the "Give Feedback" button works after restarts
        self.bot.add_view(FeedbackPanelView())

    @app_commands.command(name="feedback_setup", description="⚙️ Open the Feedback System Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def feedback_setup(self, interaction: discord.Interaction):
        config = get_feedback_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_dashboard_embed(config), view=FeedbackDashboardView(interaction.guild.id), ephemeral=True)

    @app_commands.command(name="send_feedback_panel", description="🚀 Send the Feedback Panel to the current channel")
    @app_commands.default_permissions(administrator=True)
    async def send_feedback_panel(self, interaction: discord.Interaction):
        config = get_feedback_config(interaction.guild.id)
        
        if not config.get('log_channel_id'):
            await interaction.response.send_message("⚠️ Please set a Feedback Log Channel first using `/feedback_setup`!", ephemeral=True)
            return

        panel_embed = discord.Embed(
            title="🌟 We Value Your Feedback!",
            description="Help us improve the server by sharing your thoughts.\nClick the button below to submit your feedback and rating.",
            color=discord.Color.from_str("#2b2d31")
        )
        if config.get('reward_role_id'):
            panel_embed.description += f"\n\n🎁 **Bonus:** Submit your feedback to receive the <@&{config['reward_role_id']}> role!"
            
        await interaction.channel.send(embed=panel_embed, view=FeedbackPanelView())
        await interaction.response.send_message("✅ Feedback panel successfully sent to this channel!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(FeedbackCog(bot))
                           
