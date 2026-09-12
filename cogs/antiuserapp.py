import discord
from discord.ext import commands
from discord import app_commands
import time
import datetime
import json
import os

# ---------------------------------------------------------
# DEVELOPER / SUPER ADMIN ID
# ---------------------------------------------------------
MY_USER_ID = 1313370345851457569

# ---------------------------------------------------------
# JSON DATABASE SETUP
# ---------------------------------------------------------
DATA_FILE = "anti_external_configs.json"

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

def get_ext_config(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "is_enabled": False,
            "max_strikes": 3,
            "timeout_mins": 10
        }
        save_data(data)
    return data[g_id]

def save_ext_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

# ---------------------------------------------------------
# IN-MEMORY STRIKE TRACKER
# ---------------------------------------------------------
external_strikes = {}

def add_strike(guild_id: int, user_id: int, time_window: int = 60) -> int:
    current_time = time.time()
    if guild_id not in external_strikes: external_strikes[guild_id] = {}
    if user_id not in external_strikes[guild_id]: external_strikes[guild_id][user_id] = []
        
    external_strikes[guild_id][user_id] = [t for t in external_strikes[guild_id][user_id] if current_time - t <= time_window]
    external_strikes[guild_id][user_id].append(current_time)
    return len(external_strikes[guild_id][user_id])

def clear_strikes(guild_id: int, user_id: int):
    if guild_id in external_strikes and user_id in external_strikes[guild_id]:
        external_strikes[guild_id][user_id] = []

# ---------------------------------------------------------
# DASHBOARD EMBED
# ---------------------------------------------------------
def get_ext_embed(config):
    embed = discord.Embed(title="🛡️ Anti-External App Security", color=discord.Color.from_str("#2b2d31"))
    status = "✅ Active" if config['is_enabled'] else "❌ Disabled"
    embed.add_field(name="📌 Status", value=status, inline=False)
    embed.add_field(name="⚖️ Punishment", value=f"**Action:** {config['timeout_mins']} Mins Timeout\n**Limit:** {config['max_strikes']} Warnings / 60s", inline=False)
    embed.set_footer(text="Blocks users from using external bots/apps in the server.")
    return embed

# ---------------------------------------------------------
# DASHBOARD VIEW
# ---------------------------------------------------------
class AntiExternalView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        config = get_ext_config(guild_id)
        
        if config['is_enabled']:
            self.btn_toggle.label = "❌ Disable"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable"
            self.btn_toggle.style = discord.ButtonStyle.success

    @discord.ui.button(label="Toggle", custom_id="btn_ext_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_ext_config(self.guild_id)
        config['is_enabled'] = not config['is_enabled']
        save_ext_config(self.guild_id, config)
        await interaction.response.edit_message(embed=get_ext_embed(config), view=AntiExternalView(self.guild_id))

# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------
class AntiExternalBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="external_setup", description="Open Anti-External App Security Dashboard")
    @app_commands.default_permissions(administrator=True)
    async def external_setup(self, interaction: discord.Interaction):
        # Only Server Owner AND Developer (You) can configure this
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.response.send_message("❌ Only the Server Owner or Developer can use this!", ephemeral=True)
            return
            
        config = get_ext_config(interaction.guild.id)
        await interaction.response.send_message(embed=get_ext_embed(config), view=AntiExternalView(interaction.guild.id), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.id == self.bot.user.id: return
        
        # Check if the system is enabled in this server
        config = get_ext_config(message.guild.id)
        if not config['is_enabled']: return

        if message.author.bot:
            is_member = message.guild.get_member(message.author.id)
            
            if is_member is None and message.interaction is not None:
                user = message.interaction.user
                
                # Bypasses: Server Owner & Bot Developer (You)
                if user.id == message.guild.owner_id or user.id == MY_USER_ID:
                    return

                try:
                    await message.delete()
                    
                    strikes = add_strike(message.guild.id, user.id, time_window=60)
                    
                    if strikes >= config['max_strikes']:
                        clear_strikes(message.guild.id, user.id)
                        try:
                            member = message.guild.get_member(user.id)
                            if member:
                                timeout_duration = datetime.timedelta(minutes=config['timeout_mins'])
                                await member.timeout(timeout_duration, reason="Repeated External Bot Spam")
                                alert = await message.channel.send(f"🔇 {user.mention} has been **muted for {config['timeout_mins']} minutes** for repeatedly using external bots!")
                                await alert.delete(delay=10)
                        except discord.Forbidden:
                            pass 
                    else:
                        warn_msg = await message.channel.send(f"⚠️ {user.mention}, **Warning ({strikes}/{config['max_strikes']}):** You cannot use external bot commands here!", delete_after=7)
                except discord.Forbidden:
                    pass

async def setup(bot):
    await bot.add_cog(AntiExternalBot(bot))
  
