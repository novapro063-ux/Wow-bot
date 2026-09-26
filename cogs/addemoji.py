import discord
from discord.ext import commands
import aiohttp
import re

class EmojiManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # @commands.command এর বদলে @commands.hybrid_command ব্যবহার করা হয়েছে
    @commands.hybrid_command(
        name="addemoji", 
        aliases=["steal", "emojiadd"],
        description="Add a new emoji via URL, custom emoji, or image attachment."
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def addemoji(self, ctx: commands.Context, emoji_or_url: str = None, custom_name: str = None, image: discord.Attachment = None):
        # স্লাশ কমান্ডে ইন্টারনেট থেকে ছবি ডাউনলোডের সময় যাতে "Interaction Failed" না আসে, তাই defer করা হলো
        await ctx.defer()
        
        url = None
        name = None
        
        # ১. স্লাশ কমান্ডের অ্যাটাচমেন্ট (image) অথবা প্রিফিক্স কমান্ডের অ্যাটাচমেন্ট চেক করা হচ্ছে
        actual_attachment = image or (ctx.message.attachments[0] if ctx.message and ctx.message.attachments else None)

        if actual_attachment:
            url = actual_attachment.url
            # যদি ইউজার প্রিফিক্স কমান্ডে ছবির সাথে ক্যাপশন দেয়, তবে সেটি নাম হিসেবে কাউন্ট হবে
            name = custom_name or emoji_or_url or actual_attachment.filename.split('.')[0]
        
        # ২. টেক্সট, লিংক বা অন্য সার্ভারের ইমোজি চেক
        elif emoji_or_url:
            custom_emoji_match = re.match(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>', emoji_or_url)
            
            if custom_emoji_match:
                is_animated = bool(custom_emoji_match.group(1))
                name = custom_name or custom_emoji_match.group(2)
                emoji_id = custom_emoji_match.group(3)
                ext = "gif" if is_animated else "png"
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
            
            elif emoji_or_url.startswith("http"):
                url = emoji_or_url
                name = custom_name or "new_emoji"
            
            else:
                return await ctx.send("❌ **Error:** Please provide a valid Emoji, Image URL, or attach an image.")
        else:
            return await ctx.send("⚠️ **Usage:** Use `/addemoji` or `.addemoji <emoji/url/image> [name]`")
            
        # নাম ফিক্স করা হচ্ছে (স্পেশাল ক্যারেক্টার বাদ দিয়ে সর্বোচ্চ ৩২ অক্ষর)
        name = re.sub(r'[^a-zA-Z0-9\_]', '', name)[:32] if name else "custom_emoji"
        if not name:
            name = "custom_emoji"

        try:
            # ছবি ডাউনলোড
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return await ctx.send("❌ **Error:** Failed to download the image from the provided source.")
                    
                    image_bytes = await response.read()
                    
            # সার্ভারে ইমোজি অ্যাড করা
            new_emoji = await ctx.guild.create_custom_emoji(name=name, image=image_bytes)
            await ctx.send(f"✅ **Success!** Emoji added: <{'a' if new_emoji.animated else ''}:{new_emoji.name}:{new_emoji.id}> (`:{new_emoji.name}:`)")
            
        except discord.Forbidden:
            await ctx.send("❌ **Error:** I don't have the `Manage Emojis` permission in this server.")
        except discord.HTTPException as e:
            if e.code == 50035: 
                await ctx.send("❌ **Error:** Image file is too large! Discord's maximum emoji size is 256 KB.")
            else:
                await ctx.send(f"❌ **Failed to add emoji.** (Error: {e.text})")
        except Exception as e:
            await ctx.send(f"❌ **An unexpected error occurred:** {str(e)[:100]}")

async def setup(bot):
    await bot.add_cog(EmojiManager(bot))
  
