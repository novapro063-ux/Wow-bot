import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import time
import random
import re

# ---------------------------------------------------------
# DATABASE & EMOJIS
# ---------------------------------------------------------
DB_FILE = "giveaways.json"

# Your Custom Emojis
JOIN_EMOJI = discord.PartialEmoji.from_str("<a:Giveaway2:1470530788322705599>")
GIFT_EMOJI = "<a:gift:1470830259329826826>"
DECO_EMOJI = "<a:emoji_53:1429365638673072300>"

def load_giveaways():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_giveaways(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

# Convert duration string (e.g., "1d", "5h", "30m") to seconds
def parse_time(time_str: str) -> int:
    time_str = time_str.lower().replace(" ", "")
    regex = re.compile(r'((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?')
    parts = regex.match(time_str)
    if not parts: return 0
    parts = parts.groupdict()
    return int(parts.get('days') or 0)*86400 + int(parts.get('hours') or 0)*3600 + int(parts.get('minutes') or 0)*60 + int(parts.get('seconds') or 0)


# ---------------------------------------------------------
# CORE EMBED GENERATOR
# ---------------------------------------------------------
def create_giveaway_embed(prize, end_time, winners, host: discord.Member, image_url=None, ended=False):
    embed = discord.Embed(title=f"{GIFT_EMOJI} **{prize}** {GIFT_EMOJI}", color=discord.Color.from_str("#5865F2") if not ended else discord.Color.red())
    if ended:
        embed.description = f"**Giveaway Ended!** {DECO_EMOJI}\n\n**Hosted by:** {host.mention}"
    else:
        embed.description = (
            f"**Ends:** <t:{end_time}:R> (<t:{end_time}:f>)\n"
            f"**Hosted by:** {host.mention}\n"
            f"**Winners:** {winners}\n\n"
            f"👇 **React with {JOIN_EMOJI} to enter!**"
        )
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text="Ultimate Giveaway System")
    return embed

def get_dashboard_embed(selected_gw=None):
    embed = discord.Embed(title=f"{DECO_EMOJI} Giveaway Control Panel", color=discord.Color.from_str("#2b2d31"))
    embed.description = "Use the buttons below to create or manage your giveaways live!"
    if selected_gw:
        embed.add_field(name="🎯 Currently Managing:", value=f"**Prize:** {selected_gw['prize']}\n**Status:** {'Ended' if selected_gw['is_ended'] else 'Active'}", inline=False)
    else:
        embed.add_field(name="🎯 Currently Managing:", value="`None Selected` (Select from the menu below)", inline=False)
    return embed


# ---------------------------------------------------------
# MODALS (Live Forms)
# ---------------------------------------------------------
class CreateGiveawayModal(discord.ui.Modal, title="🚀 Create New Giveaway"):
    prize = discord.ui.TextInput(label="Prize", style=discord.TextStyle.short, placeholder="e.g. 1 Month Nitro", required=True)
    duration = discord.ui.TextInput(label="Duration (e.g. 1d, 5h, 30m)", style=discord.TextStyle.short, placeholder="1h", required=True)
    winners = discord.ui.TextInput(label="Number of Winners", style=discord.TextStyle.short, default="1", required=True)
    channel_id = discord.ui.TextInput(label="Channel ID", style=discord.TextStyle.short, placeholder="Leave empty for current channel", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        time_seconds = parse_time(self.duration.value)
        if time_seconds <= 0:
            await interaction.response.send_message("❌ Invalid duration format!", ephemeral=True)
            return
            
        try: w_count = int(self.winners.value)
        except: w_count = 1

        ch_id = int(self.channel_id.value.strip()) if self.channel_id.value.strip() else interaction.channel.id
        channel = interaction.guild.get_channel(ch_id)
        if not channel:
            await interaction.response.send_message("❌ Invalid Channel ID!", ephemeral=True)
            return

        end_time = int(time.time()) + time_seconds
        embed = create_giveaway_embed(self.prize.value, end_time, w_count, interaction.user)
        msg = await channel.send(embed=embed)
        await msg.add_reaction(JOIN_EMOJI)

        data = load_giveaways()
        gw_id = str(msg.id)
        data[gw_id] = {
            "guild_id": interaction.guild.id,
            "channel_id": channel.id,
            "host_id": interaction.user.id,
            "prize": self.prize.value,
            "winners": w_count,
            "end_time": end_time,
            "image_url": None,
            "is_ended": False
        }
        save_giveaways(data)
        await interaction.response.edit_message(embed=get_dashboard_embed(data[gw_id]), view=DashboardView(interaction.guild, gw_id))
        await interaction.followup.send(f"✅ Giveaway started in <#{channel.id}>!", ephemeral=True)


class EditInfoModal(discord.ui.Modal, title="✏️ Edit Prize & Winners"):
    prize = discord.ui.TextInput(label="New Prize", style=discord.TextStyle.short, required=True)
    winners = discord.ui.TextInput(label="New Winner Count", style=discord.TextStyle.short, required=True)

    def __init__(self, gw_id, current_prize, current_winners):
        super().__init__()
        self.gw_id = gw_id
        self.prize.default = current_prize
        self.winners.default = str(current_winners)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_giveaways()
        if self.gw_id not in data: return
        data[self.gw_id]["prize"] = self.prize.value
        try: data[self.gw_id]["winners"] = int(self.winners.value)
        except: pass
        
        save_giveaways(data)
        await update_live_message(interaction, self.gw_id, data[self.gw_id])


class EditImageModal(discord.ui.Modal, title="🖼️ Set Image/GIF"):
    img_url = discord.ui.TextInput(label="Image/GIF URL (Leave blank to remove)", style=discord.TextStyle.short, required=False)
    def __init__(self, gw_id, current_img):
        super().__init__()
        self.gw_id = gw_id
        self.img_url.default = current_img if current_img else ""

    async def on_submit(self, interaction: discord.Interaction):
        data = load_giveaways()
        if self.gw_id not in data: return
        data[self.gw_id]["image_url"] = self.img_url.value if self.img_url.value else None
        save_giveaways(data)
        await update_live_message(interaction, self.gw_id, data[self.gw_id])


async def update_live_message(interaction, gw_id, gw_data):
    try:
        channel = interaction.guild.get_channel(gw_data["channel_id"])
        msg = await channel.fetch_message(int(gw_id))
        host = interaction.guild.get_member(gw_data["host_id"]) or interaction.user
        embed = create_giveaway_embed(gw_data["prize"], gw_data["end_time"], gw_data["winners"], host, gw_data["image_url"], gw_data["is_ended"])
        await msg.edit(embed=embed)
    except Exception as e:
        print(f"Failed to edit giveaway live: {e}")
    
    await interaction.response.edit_message(embed=get_dashboard_embed(gw_data), view=DashboardView(interaction.guild, gw_id))
    await interaction.followup.send("✅ Live giveaway updated successfully!", ephemeral=True)


# ---------------------------------------------------------
# DASHBOARD CONTROLS (Buttons & Select Menu)
# ---------------------------------------------------------
class GiveawaySelect(discord.ui.Select):
    def __init__(self, guild):
        data = load_giveaways()
        options = []
        for gw_id, info in data.items():
            if info["guild_id"] == guild.id and not info["is_ended"]:
                # Limit to 25 active giveaways for menu
                if len(options) >= 25: break
                options.append(discord.SelectOption(label=info["prize"], description=f"ID: {gw_id}", value=gw_id, emoji="🎁"))
        
        if not options:
            options.append(discord.SelectOption(label="No active giveaways", value="none"))
            
        super().__init__(placeholder="🎯 Select an active giveaway to manage...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        gw_id = self.values[0]
        data = load_giveaways()
        await interaction.response.edit_message(embed=get_dashboard_embed(data.get(gw_id)), view=DashboardView(interaction.guild, gw_id))


class DashboardView(discord.ui.View):
    def __init__(self, guild, selected_gw_id=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.selected_gw_id = selected_gw_id
        self.add_item(GiveawaySelect(guild))

    @discord.ui.button(label="🚀 Create New", style=discord.ButtonStyle.success, row=1)
    async def btn_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateGiveawayModal())

    @discord.ui.button(label="✏️ Edit Info", style=discord.ButtonStyle.primary, row=1)
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_gw_id:
            await interaction.response.send_message("⚠️ Please select a giveaway from the menu first!", ephemeral=True)
            return
        data = load_giveaways().get(self.selected_gw_id)
        if data: await interaction.response.send_modal(EditInfoModal(self.selected_gw_id, data["prize"], data["winners"]))

    @discord.ui.button(label="🖼️ Set Image/GIF", style=discord.ButtonStyle.primary, row=1)
    async def btn_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_gw_id:
            await interaction.response.send_message("⚠️ Please select a giveaway from the menu first!", ephemeral=True)
            return
        data = load_giveaways().get(self.selected_gw_id)
        if data: await interaction.response.send_modal(EditImageModal(self.selected_gw_id, data["image_url"]))

    @discord.ui.button(label="🛑 End Now / Reroll", style=discord.ButtonStyle.danger, row=2)
    async def btn_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_gw_id:
            await interaction.response.send_message("⚠️ Please select a giveaway from the menu first!", ephemeral=True)
            return
        
        await interaction.response.send_message("🎲 Processing winners...", ephemeral=True)
        cog = interaction.client.get_cog("GiveawayCog")
        await cog.end_giveaway(self.guild, self.selected_gw_id)


# ---------------------------------------------------------
# MAIN COG & BACKGROUND TASKS
# ---------------------------------------------------------
class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giveaway_checker.start()

    def cog_unload(self):
        self.giveaway_checker.cancel()

    @app_commands.command(name="gstart", description="Open the live Giveaway control panel")
    @app_commands.default_permissions(administrator=True)
    async def gstart(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=get_dashboard_embed(), view=DashboardView(interaction.guild), ephemeral=True)

    @tasks.loop(seconds=15)
    async def giveaway_checker(self):
        data = load_giveaways()
        current_time = int(time.time())
        updated = False

        for gw_id, info in list(data.items()):
            if not info["is_ended"] and current_time >= info["end_time"]:
                guild = self.bot.get_guild(info["guild_id"])
                if guild:
                    await self.end_giveaway(guild, gw_id)
                    updated = True
        if updated:
            save_giveaways(load_giveaways()) # Ensure it's saved in loop

    @giveaway_checker.before_loop
    async def before_checker(self):
        await self.bot.wait_until_ready()

    async def end_giveaway(self, guild, gw_id):
        data = load_giveaways()
        if gw_id not in data: return
        gw = data[gw_id]
        
        try:
            channel = guild.get_channel(gw["channel_id"])
            if not channel: return
            msg = await channel.fetch_message(int(gw_id))
            
            # Find the correct reaction users
            users = []
            for reaction in msg.reactions:
                # Support for Custom Emojis comparison
                if str(reaction.emoji) == str(JOIN_EMOJI) or getattr(reaction.emoji, "id", None) == JOIN_EMOJI.id:
                    async for user in reaction.users():
                        if not user.bot:
                            users.append(user)
                    break
            
            # Edit Embed to Ended
            host = guild.get_member(gw["host_id"])
            embed = create_giveaway_embed(gw["prize"], gw["end_time"], gw["winners"], host, gw["image_url"], ended=True)
            await msg.edit(embed=embed)

            # Pick Winners
            if len(users) == 0:
                await channel.send(f"❌ No one joined the giveaway for **{gw['prize']}**!")
            else:
                winner_count = min(gw["winners"], len(users))
                winners = random.sample(users, winner_count)
                mentions = ", ".join(w.mention for w in winners)
                
                win_embed = discord.Embed(
                    title=f"{DECO_EMOJI} Giveaway Winner! {DECO_EMOJI}",
                    description=f"Congratulations {mentions}!\nYou have won: **{gw['prize']}**!\n\n[↗️ Jump to Giveaway]({msg.jump_url})",
                    color=discord.Color.green()
                )
                await channel.send(content=f"🎉 {mentions}", embed=win_embed)
            
            # Update Database
            gw["is_ended"] = True
            save_giveaways(data)
            
        except Exception as e:
            print(f"Error ending giveaway {gw_id}: {e}")

async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
  
