import discord
from discord.ext import commands
from discord import app_commands

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="announce_winner", description="Manually announce winners for a stuck or offline giveaway.")
    @app_commands.default_permissions(administrator=True)
    async def announce_winner(
        self,
        interaction: discord.Interaction,
        prize: str,
        winner1: discord.Member,
        winner2: discord.Member,
        message_id: str
    ):
        # Ephemeral defer so the command itself stays hidden from normal users
        await interaction.response.defer(ephemeral=True)

        # Create the winning embed
        embed = discord.Embed(
            title="🎉 Giveaway Ended! 🎉",
            description=f"**Prize:** {prize}\n**Winners:** {winner1.mention}, {winner2.mention}\n**Hosted by:** {interaction.user.mention}",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Ultimate Giveaway System")

        content_msg = f"Congratulations {winner1.mention} and {winner2.mention}! You won the **{prize}**!"

        try:
            # Try to fetch the original giveaway message to reply directly to it
            original_msg = await interaction.channel.fetch_message(int(message_id))
            await original_msg.reply(content=content_msg, embed=embed)
            await interaction.followup.send("✅ Winners announced successfully via reply!")
        except Exception:
            # If message ID is wrong or from another channel, just send it normally in the current channel
            await interaction.channel.send(content=content_msg, embed=embed)
            await interaction.followup.send("✅ Winners announced in the channel (Note: Could not find the original message ID).")

async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))
  
