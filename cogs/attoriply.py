import discord
from discord.ext import commands
import json
import os
import asyncio
import re
from datetime import datetime

DATA_FILE = 'commands_data.json'
IMAGE_DIR = 'saved_images' # Local folder for permanent images

# Create folder if it doesn't exist
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Regex to extract links
URL_REGEX = re.compile(r'(https?://\S+)')

# Function to load and save data
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Dashboard Button System
class DashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="➕ Add New Command", style=discord.ButtonStyle.success)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📝 **Please type the trigger word** (e.g., rex).\n*You have 60 seconds.*", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            trigger_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            trigger = trigger_msg.content.lower()
            
            await interaction.followup.send("🖼️ **Now, send the reply!**\nYou can send text, a **link**, or directly **upload an image/GIF** here.", ephemeral=True)
            
            reply_msg = await self.bot.wait_for('message', check=check, timeout=120.0)
            
            reply_text = reply_msg.content
            image_url = None
            
            # 1. Handle Direct Image Upload (Permanent Save)
            if reply_msg.attachments:
                attachment = reply_msg.attachments[0]
                ext = attachment.filename.split('.')[-1]
                local_path = os.path.join(IMAGE_DIR, f"{trigger}.{ext}")
                
                await attachment.save(local_path)
                image_url = local_path 
                
            # 2. Handle Links in Text
            else:
                match = URL_REGEX.search(reply_text)
                if match:
                    image_url = match.group(0)
                    reply_text = reply_text.replace(image_url, '').strip() 
            
            # Save data
            data = load_data()
            data[trigger] = {
                "text": reply_text,
                "image": image_url
            }
            save_data(data)
            
            await interaction.followup.send(f"✅ **Successfully saved!**\n**Trigger:** `{trigger}`", ephemeral=True)
            
            await trigger_msg.delete()
            await reply_msg.delete()
            
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Time's up! Please try again from the dashboard.", ephemeral=True)

    @discord.ui.button(label="🗑️ Delete Command", style=discord.ButtonStyle.danger)
    async def del_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🗑️ **Type the trigger word you want to delete:**", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
            
        try:
            del_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            trigger = del_msg.content.lower()
            
            data = load_data()
            if trigger in data:
                # Delete local image if exists
                saved_image = data[trigger].get("image")
                if saved_image and not saved_image.startswith("http"):
                    if os.path.exists(saved_image):
                        os.remove(saved_image)
                
                del data[trigger]
                save_data(data)
                await interaction.followup.send(f"✅ `{trigger}` has been successfully deleted.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ No command found with this trigger.", ephemeral=True)
                
            await del_msg.delete()
                
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Time's up!", ephemeral=True)

# Main Cog Class
class AutoReplyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. Dashboard Command with ALIASES ('dash', 'db')
    @commands.command(name="dashboard", aliases=["dash", "db"], help="Open the Auto-Reply Dashboard")
    @commands.has_permissions(administrator=True)
    async def dashboard(self, ctx: commands.Context):
        embed = discord.Embed(
            title="⚙️ Auto-Reply Management", 
            description="Manage your custom auto-replies below.\nYou can set text, links, or directly upload images/GIFs.", 
            color=discord.Color.dark_theme()
        )
        await ctx.send(embed=embed, view=DashboardView(self.bot))

    # 2. Help Command
    @commands.command(name="help", help="List all available auto-reply commands")
    async def help_command(self, ctx: commands.Context):
        data = load_data()
        
        if not data:
            embed = discord.Embed(
                title="📜 Custom Commands List", 
                description="*No custom commands have been created yet.*", 
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        cmd_list = [f"• `{trigger}`" for trigger in data.keys()]
        description = "\n".join(cmd_list)[:4000]

        embed = discord.Embed(
            title="📜 Available Custom Commands",
            description=f"Here are the auto-reply triggers you can use in this server:\n\n{description}",
            color=discord.Color.teal()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Total Commands: {len(data)}")
        
        await ctx.send(embed=embed)

    # 3. Auto-Reply Event
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        data = load_data()
        content = message.content.lower()

        if content in data:
            reply_data = data[content]
            text = reply_data.get("text", "")
            image_url = reply_data.get("image", None)

            embed = discord.Embed(
                title=content.title(),
                description=text if text else None,
                color=discord.Color.teal()
            )
            
            file_to_send = None
            
            if image_url:
                if image_url.startswith("http"):
                    embed.set_image(url=image_url)
                else:
                    if os.path.exists(image_url):
                        filename = os.path.basename(image_url)
                        file_to_send = discord.File(image_url, filename=filename)
                        embed.set_image(url=f"attachment://{filename}")

            footer_text = f"{message.author.display_name} | {datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
            avatar_url = message.author.display_avatar.url if message.author.display_avatar else None
            embed.set_footer(text=footer_text, icon_url=avatar_url)

            if file_to_send:
                await message.channel.send(file=file_to_send, embed=embed)
            else:
                await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoReplyCog(bot))
          
