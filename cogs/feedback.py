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
# 3. FEEDBACK MODAL (Form for Description)
# ---------------------------------------------------------
class FeedbackModal(discord.ui.Modal):
    def __init__(self, stars: int):
        # ડায়নামিক টাইটেল (যাতে ইউজার দেখতে পারে সে কত স্টার সিলেক্ট করেছে)
        super().__init__(title=f"📝 Submit {stars}-Star Feedback")
        self.stars = stars
        
        self.description = discord.ui.TextInput(
            label="Feedback Description",
            style=discord.TextStyle.paragraph,
            placeholder="Write your feedback, suggestions, or issues here...",
            required=True,
            max_length=2000
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        config = get_feedback_config(guild.id)
        
        stars_str = "⭐" * self.stars + "☆" * (5 - self.stars)
        
        # ডায়নামিক কালার (রেটিং অনুযায়ী কালার চেঞ্জ হবে)
        colors = {
            5: discord.Color.gold(),
            4: discord.Color.green(),
            3: discord.Color.from_str("#FEE75C"), # Yellow
            2: discord.Color.orange(),
            1: discord.Color.red()
        }
        embed_color = colors.get(self.stars, discord.Color.blurple())

        # 1. Send Premium Log to Admin Channel
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            try:
                log_channel = guild.get_channel(int(log_channel_id))
                if log_channel:
                    embed = discord.Embed(
                        title="🌟 New Server Feedback Received!",
                        description=f"**Feedback:**\n```\n{self.description.value}\n```",
                        color=embed_color,
                        timestamp=datetime.datetime.now()
                    )
                    embed.set_author(name=f"{interaction.user.display_name} ({interaction.user.name})", icon_url=interaction.user.display_avatar.url)
                    embed.add_field(name="Given Rating", value=f"**{self.stars}/5** {stars_str}", inline=False)
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.set_footer(text=f"User ID: {interaction.user.id}")
                    await log_channel.send(embed=embed)
            except Exception as e:
                print(f"Feedback Log Error: {e}")

        # 2. Give Reward Role
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

        # 3. Reply to User
        msg = f"✅ Thank you for your valuable feedback! You rated us **{self.stars} Stars**."
        if role_given:
            msg += f"\n🎉 As a reward, you have received the <@&{role_id}> role!"
            
        await interaction.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------
# 2. USER PANEL VIEW (Selection Menu for Stars)
# ---------------------------------------------------------
class FeedbackPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="persistent_feedback_star_select",
        placeholder="⭐ Select your rating to start...",
        options=[
            discord.SelectOption(label="5 Stars - Excellent!", value="5", emoji="🌟"),
            discord.SelectOption(label="4 Stars - Very Good", value="4", emoji="⭐"),
            discord.SelectOption(label="3 Stars - Good", value="3", emoji="👍"),
            discord.SelectOption(label="2 Stars - Fair", value="2", emoji="😕"),
            discord.SelectOption(label="1 Star - Poor", value="1", emoji="😞"),
        ]
    )
    async def select_rating(self, interaction: discord.Interaction, select: discord.ui.Select):
        # Selection মেনু থেকে কত স্টার সিলেক্ট করেছে সেটা নিয়ে Modal ওপেন হবে
        stars = int(select.values[0])
        await interaction.response.send_modal(FeedbackModal(stars=stars))


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
        # রিস্টার্টের পরেও যাতে Selection Menu কাজ করে তার জন্য
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
            description="Help us improve the server by sharing your thoughts.\n**Please select a rating below to submit your feedback.**",
            color=discord.Color.from_str("#2b2d31")
        )
        if config.get('reward_role_id'):
            panel_embed.description += f"\n\n🎁 **Bonus:** Submit your feedback to receive the <@&{config['reward_role_id']}> role!"
            
        await interaction.channel.send(embed=panel_embed, view=FeedbackPanelView())
        await interaction.response.send_message("✅ Feedback panel successfully sent to this channel!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(FeedbackCog(bot))
