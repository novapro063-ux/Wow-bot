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
        description="Add multiple emojis at once via custom emojis, URLs, or attachments."
    )
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def addemojis(self, ctx: commands.Context, *, text_input: str = None, attachment: discord.Attachment = None):
        await ctx.defer()
        
        tasks = [] # এখানে আমরা (name, url) এর লিস্ট সেভ করব
        
        # ১. স্লাশ কমান্ডের অ্যাটাচমেন্ট বা প্রিফিক্স কমান্ডের একাধিক অ্যাটাচমেন্ট চেক করা
        all_attachments = ctx.message.attachments if ctx.message else []
        if attachment and attachment not in all_attachments:
            all_attachments.append(attachment)

        for att in all_attachments:
            if att.content_type and att.content_type.startswith("image/"):
                name = att.filename.split('.')[0]
                tasks.append((name, att.url))
                
        # ২. টেক্সট ইনপুট থেকে সব কাস্টম ইমোজি এবং লিংক বের করা
        if text_input:
            # কাস্টম ইমোজি (<:name:id> বা <a:name:id>) এক্সট্র্যাক্ট করা
            custom_emojis = re.finditer(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>', text_input)
            for match in custom_emojis:
                is_animated = bool(match.group(1))
                name = match.group(2)
                emoji_id = match.group(3)
                ext = "gif" if is_animated else "png"
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
                tasks.append((name, url))
                
            # লিংক (URL) এক্সট্র্যাক্ট করা
            urls = re.finditer(r'https?://[^\s<>"]+', text_input)
            for i, match in enumerate(urls):
                url = match.group(0)
                tasks.append((f"custom_emoji_{i+1}", url))

        # যদি কোনো ইমোজি, লিংক বা ছবি না পাওয়া যায়
        if not tasks:
            return await ctx.send("⚠️ **Usage:** Please provide valid emojis, image URLs, or attach images.")
            
        # ডিসকর্ডের রেট-লিমিট থেকে বাঁচতে একবারে সর্বোচ্চ ২০টি ইমোজি সেট করা হলো
        if len(tasks) > 20:
             return await ctx.send("❌ You can only add up to **20 emojis** at once to prevent rate limits.")

        added_emojis = []
        failed_count = 0
        
        # ৩. লুপ চালিয়ে এক এক করে সব ইমোজি সার্ভারে অ্যাড করা
        async with aiohttp.ClientSession() as session:
            for name, url in tasks:
                # নাম ফিক্স করা (স্পেশাল ক্যারেক্টার বাদ দিয়ে সর্বোচ্চ ৩২ অক্ষর)
                clean_name = re.sub(r'[^a-zA-Z0-9\_]', '', name)[:32]
                if not clean_name:
                    clean_name = "emoji"
                
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                            new_emoji = await ctx.guild.create_custom_emoji(name=clean_name, image=image_bytes)
                            added_emojis.append(f"<{'a' if new_emoji.animated else ''}:{new_emoji.name}:{new_emoji.id}>")
                        else:
                            failed_count += 1
                except Exception:
                    failed_count += 1

        # ৪. ফাইনাল রেজাল্ট পাঠানো
        if added_emojis:
            result_msg = f"✅ **Success!** Added {len(added_emojis)} emojis:\n{' '.join(added_emojis)}"
            if failed_count > 0:
                result_msg += f"\n⚠️ Failed to add {failed_count} emojis (File too large or invalid link)."
            await ctx.send(result_msg)
        else:
            await ctx.send("❌ **Error:** Failed to add any emojis. Please check your URLs or image sizes (Max 256KB).")

    # পারমিশন এরর হ্যান্ডলার (আগের সমাধানের মতো)
    @addemojis.error
    async def addemojis_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ **Error:** You don't have the `Manage Emojis and Stickers` permission.", ephemeral=True)
        else:
            raise error

async def setup(bot):
    await bot.add_cog(EmojiManager(bot))
    
