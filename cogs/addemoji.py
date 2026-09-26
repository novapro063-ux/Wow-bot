import discord
from discord.ext import commands
import aiohttp
import re

class EmojiManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="addemojis", 
        aliases=["steal", "addemoji", "am"],
        description="Add emojis via custom emoji, URL, or image attachment."
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def addemojis(self, ctx: commands.Context, *, emoji_url: str = None, attachment: discord.Attachment = None):
        await ctx.defer()
        
        tasks = []
        
        # 1. Check for attachments or uploaded images
        all_attachments = ctx.message.attachments if ctx.message else []
        if attachment and attachment not in all_attachments:
            all_attachments.append(attachment)

        for att in all_attachments:
            if att.content_type and att.content_type.startswith("image/"):
                tasks.append((att.filename.split('.')[0], att.url))
                
        # 2. Extract custom emojis or links from emoji_url input
        if emoji_url:
            # Find custom emojis (<:name:id> or <a:name:id>)
            custom_emojis = re.finditer(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>', emoji_url)
            for match in custom_emojis:
                is_animated = bool(match.group(1))
                name = match.group(2)
                emoji_id = match.group(3)
                ext = "gif" if is_animated else "png"
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
                tasks.append((name, url))
                
            # Find standard URLs
            urls = re.finditer(r'https?://[^\s<>"]+', emoji_url)
            for i, match in enumerate(urls):
                if "cdn.discordapp.com/emojis" not in match.group(0): # Prevent double counting
                    tasks.append((f"emoji_{i+1}", match.group(0)))

        # If no valid input is provided
        if not tasks:
            return await ctx.send("⚠️ **Usage:** Please use `/addemojis emoji_url: <emoji/link>` or upload an image.")
            
        # Limit to 10 emojis at once to prevent glitches or rate limits
        if len(tasks) > 10:
             return await ctx.send("❌ You can only add up to **10 emojis** at once.")

        added_emojis = []
        
        # 3. Add the emojis to the server
        async with aiohttp.ClientSession() as session:
            for name, url in tasks:
                clean_name = re.sub(r'[^a-zA-Z0-9\_]', '', name)[:32]
                if not clean_name:
                    clean_name = "custom_emoji"
                
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                            new_emoji = await ctx.guild.create_custom_emoji(name=clean_name, image=image_bytes)
                            added_emojis.append(f"<{'a' if new_emoji.animated else ''}:{new_emoji.name}:{new_emoji.id}>")
                except Exception:
                    continue # Skip to the next one if an error occurs with a specific emoji

        # 4. Send the final result
        if added_emojis:
            await ctx.send(f"✅ **Success! Added:** {' '.join(added_emojis)}")
        else:
            await ctx.send("❌ **Error:** Failed to add any emojis. Please check if the links are valid and the image size is under 256KB.")

    # Error handler for missing permissions
    @addemojis.error
    async def addemojis_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ **Error:** You need the `Manage Emojis and Stickers` permission to use this command.", ephemeral=True)
        else:
            raise error

async def setup(bot):
    await bot.add_cog(EmojiManager(bot))
