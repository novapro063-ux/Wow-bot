import discord
from discord.ext import commands
from discord import app_commands

# আপনার দেওয়া ডেকোরেশন ইমোজি
DECO_EMOJI = "<a:emoji_53:1429365638673072300>"

class ManualGiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="manual_winner", description="Manually announce giveaway winners if the bot went offline")
    @app_commands.default_permissions(administrator=True)
    async def manual_winner(self, interaction: discord.Interaction, prize: str, winner_1: discord.Member, winner_2: discord.Member = None, message_link: str = None):
        
        # উইনারদের লিস্ট তৈরি করা
        winners = [winner_1]
        if winner_2:
            winners.append(winner_2)
            
        mentions = ", ".join(w.mention for w in winners)
        
        # মেসেজ ডেসক্রিপশন তৈরি করা
        desc = f"Congratulations {mentions}!\nYou have won: **{prize}**!"
        if message_link:
            desc += f"\n\n[↗️ Jump to Giveaway]({message_link})"
            
        # একদম আসল উইনিং মেসেজের মতো হুবহু এম্বেড তৈরি করা
        win_embed = discord.Embed(
            title=f"{DECO_EMOJI} Giveaway Winner! {DECO_EMOJI}",
            description=desc,
            color=discord.Color.green()
        )
        
        # মেসেজ পাঠানো (যাতে সবাইকে পিং করা হয়)
        await interaction.response.send_message(content=f"🎉 {mentions}", embed=win_embed)

async def setup(bot):
    await bot.add_cog(ManualGiveawayCog(bot))
    
