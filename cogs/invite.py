import discord
from discord.ext import commands
from discord import app_commands
import datetime
import math
import asyncio
from utils import get_theme_color
from database import Database

# ================= 🔘 বাটন ক্লাস (Pagination View) =================
class InvitePaginationView(discord.ui.View):
    def __init__(self, data, title, author, member_checked, guild_id):
        super().__init__(timeout=60)
        self.data = data
        self.title = title
        self.author = author
        self.member_checked = member_checked
        self.guild_id = guild_id
        self.current_page = 1
        self.items_per_page = 10
        self.total_pages = math.ceil(len(data) / self.items_per_page) if data else 1

    def create_embed(self):
        start = (self.current_page - 1) * self.items_per_page
        end = start + self.items_per_page
        current_data = self.data[start:end]

        embed = discord.Embed(
            title=self.title,
            color=get_theme_color(self.guild_id),
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=self.member_checked.display_avatar.url)

        description = ""
        for i, entry in enumerate(current_data, start=start + 1):
            status = entry.get('status', 'New Join')
            status_icon = "🔄" if status == "Rejoined" else "❌" if "Left" in status else "🆕"
            date_str = entry.get('date', 'Unknown Date')
            
            description += (
                f"**{i}. {entry['name']}**\n"
                f"├─ ID: `{entry['id']}`\n"
                f"├─ Date: `{date_str}`\n"
                f"└─ Status: **{status}** {status_icon}\n\n"
            )
        
        embed.description = description or "❌ No invites found."
        embed.set_footer(text=f"Page {self.current_page} of {self.total_pages} • Total: {len(self.data)}")
        return embed

    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 1)
        self.next_button.disabled = (self.current_page == self.total_pages)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ This menu is not for you!", ephemeral=True)
            return False
        return True

# ================= ⚙️ মেইন ইনভাইট ট্র্যাকার ক্লাস =================
class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {} # Cache: {guild_id: {invite_code: uses}}

    async def update_invite_cache(self, guild):
        """সার্ভারের ইনভাইটগুলো সঠিকভাবে ক্যাশ করার ফাংশন"""
        try:
            invites = await guild.invites()
            self.invites[guild.id] = {invite.code: invite.uses for invite in invites}
            
            # Vanity URL Support
            if 'VANITY_URL' in guild.features:
                vanity = await guild.vanity_invite()
                if vanity:
                    self.invites[guild.id][vanity.code] = vanity.uses
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.update_invite_cache(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.update_invite_cache(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild:
            await self.update_invite_cache(invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild:
            await self.update_invite_cache(invite.guild)

    # ================= 📥 জয়েন ট্র্যাকিং (100% Accurate Logic) =================
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        inviter = None
        
        if member.bot:
            try:
                await asyncio.sleep(1) # Audit log আপডেট হওয়ার জন্য সামান্য অপেক্ষা
                async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=5):
                    if entry.target.id == member.id:
                        inviter = entry.user
                        break
            except: pass
        else:
            old_invites = self.invites.get(guild.id, {})
            try:
                new_invites = await guild.invites()
                if 'VANITY_URL' in guild.features:
                    vanity = await guild.vanity_invite()
                    if vanity: new_invites.append(vanity)
            except discord.Forbidden:
                return

            for invite in new_invites:
                old_uses = old_invites.get(invite.code, 0)
                if invite.uses > old_uses:
                    inviter = invite.inviter
                    break
            
            await self.update_invite_cache(guild)
        
        if inviter:
            col = Database.get_collection("invites")
            gid, inviter_id = str(guild.id), str(inviter.id)

            inc_field = "regular"
            if member.bot:
                inc_field = "bots"
            elif (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days < 1:
                inc_field = "fake"
            
            # ডাটাবেসে চেক করা ইউজার আগে জয়েন করেছিল কিনা
            existing_user = col.find_one({"guild_id": gid, "user_id": str(member.id)})
            join_status = "Rejoined" if existing_user else "New Join"

            entry_data = {
                "name": member.name,
                "id": member.id,
                "date": datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                "status": join_status
            }

            col.update_one(
                {"guild_id": gid, "user_id": inviter_id},
                {
                    "$inc": {inc_field: 1},
                    "$push": {"history": {"$each": [entry_data], "$position": 0}},
                    "$setOnInsert": {"bonus": 0, "leave": 0}
                },
                upsert=True
            )

            col.update_one(
                {"guild_id": gid, "user_id": str(member.id)},
                {"$set": {"invited_by": inviter_id, "invited_by_name": inviter.name, "join_date": entry_data["date"]}},
                upsert=True
            )

    # ================= 🚪 লিভ ট্র্যাকিং =================
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        col = Database.get_collection("invites")
        gid = str(member.guild.id)
        
        member_data = col.find_one({"guild_id": gid, "user_id": str(member.id)})
        if member_data and "invited_by" in member_data:
            inviter_id = member_data["invited_by"]
            
            # লিভ কাউন্ট বাড়ানো এবং হিস্টরিতে স্ট্যাটাস 'Left' সেট করা
            col.update_one(
                {"guild_id": gid, "user_id": inviter_id, "history.id": member.id},
                {
                    "$inc": {"leave": 1},
                    "$set": {"history.$.status": "Left"}
                }
            )

    # ================= 📊 ১. INVITE STATS (Slash Only) =================
    @app_commands.command(name="invite", description="📊 View your or someone else's invite stats")
    @app_commands.describe(member="Select a user to check")
    async def invite(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        col = Database.get_collection("invites")
        
        data = col.find_one({"guild_id": str(interaction.guild.id), "user_id": str(member.id)}) or {}

        reg = data.get("regular", 0)
        fake = data.get("fake", 0)
        leave = data.get("leave", 0)
        bonus = data.get("bonus", 0)
        bots = data.get("bots", 0)

        total = max(0, (reg + bonus) - (fake + leave))

        embed = discord.Embed(color=get_theme_color(interaction.guild.id))
        embed.set_author(name=f"{member.name}'s Invites", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.description = (
            f"<:Star:1472268505238863945> **Total Invites:** `{total}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<:dot:1472268394391670855> **Join:** `{reg}`\n"
            f"<:dot:1472268394391670855> **Leave:** `{leave}`\n"
            f"<:dot:1472268394391670855> **Fake:** `{fake}`\n"
            f"<:dot:1472268394391670855> **Bonus:** `{bonus}`\n"
            f"<:dot:1472268394391670855> **Bots:** `{bots}`"
        )
        await interaction.response.send_message(embed=embed)

    # ================= 📜 ২. INVITED LIST (Slash Only) =================
    @app_commands.command(name="invited", description="📜 See the list of members someone has invited")
    @app_commands.describe(member="Select a user to check")
    async def invited(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        col = Database.get_collection("invites")
        
        data = col.find_one({"guild_id": str(interaction.guild.id), "user_id": str(target.id)})
        history = data.get("history", []) if data else []

        if not history:
            await interaction.response.send_message(embed=discord.Embed(description=f"❌ **{target.name}** has not invited anyone yet.", color=discord.Color.red()))
            return

        view = InvitePaginationView(data=history, title=f"📜 Invited by: {target.name}", author=interaction.user, member_checked=target, guild_id=interaction.guild.id)
        view.update_buttons()
        await interaction.response.send_message(embed=view.create_embed(), view=view)

    # ================= 🕵️ ৩. INVITER (CHECK SOURCE) (Slash Only) =================
    @app_commands.command(name="inviter", description="🕵️ Check who invited a specific member")
    @app_commands.describe(member="Select a user to check")
    async def inviter(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        col = Database.get_collection("invites")
        
        data = col.find_one({"guild_id": str(interaction.guild.id), "user_id": str(target.id)})
        
        embed = discord.Embed(title="Invite Source", color=get_theme_color(interaction.guild.id))
        embed.set_thumbnail(url=target.display_avatar.url)

        if data and "invited_by" in data:
            inviter_id = data.get("invited_by")
            date = data.get("join_date", "Unknown")
            embed.description = f"👤 **Member:** {target.mention}\n📨 **Invited By:** <@{inviter_id}> (`{inviter_id}`)\n📅 **Date:** `{date}`"
        else:
            embed.description = f"👤 **Member:** {target.mention}\n❓ **Invited By:** Unknown\n⚠️ *Tracking started recently or joined via unknown link.*"

        await interaction.response.send_message(embed=embed)

    # ================= 🎁 ৪. ADD INVITE (BONUS) (Slash Only) =================
    @app_commands.command(name="addinvite", description="🎁 Add bonus invites to a user (Admin Only)")
    @app_commands.describe(member="Select a user", amount="Number of invites to add")
    @app_commands.default_permissions(administrator=True)
    async def addinvite(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        col = Database.get_collection("invites")
        col.update_one(
            {"guild_id": str(interaction.guild.id), "user_id": str(member.id)},
            {"$inc": {"bonus": amount}},
            upsert=True
        )
        
        embed = discord.Embed(description=f"<:Star:1472268505238863945> Added **{amount}** bonus invites to {member.mention}", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # ================= 🗑️ ৫. REMOVE INVITE (Slash Only) =================
    @app_commands.command(name="removeinvite", description="🗑️ Remove bonus invites from a user (Admin Only)")
    @app_commands.describe(member="Select a user", amount="Number of invites to remove")
    @app_commands.default_permissions(administrator=True)
    async def removeinvite(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        col = Database.get_collection("invites")
        col.update_one(
            {"guild_id": str(interaction.guild.id), "user_id": str(member.id)},
            {"$inc": {"bonus": -amount}},
            upsert=True
        )
        embed = discord.Embed(description=f"<:dot:1472268394391670855> Removed **{amount}** bonus invites from {member.mention}", color=discord.Color.orange())
        await interaction.response.send_message(embed=embed)

    # ================= 🧹 ৬. CLEAR INVITE (USER RESET) (Slash Only) =================
    @app_commands.command(name="clearinvite", description="⚠️ Clear all invite data for a specific user (Admin Only)")
    @app_commands.describe(member="Select a user to wipe")
    @app_commands.default_permissions(administrator=True)
    async def clearinvite(self, interaction: discord.Interaction, member: discord.Member):
        col = Database.get_collection("invites")
        result = col.delete_one({"guild_id": str(interaction.guild.id), "user_id": str(member.id)})
            
        if result.deleted_count > 0:
            embed = discord.Embed(description=f"<:dot:1472268394391670855> **Success:** All invite data for {member.mention} has been wiped!", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=discord.Embed(description="❌ This user already has 0 invites.", color=discord.Color.red()), ephemeral=True)

    # ================= ⚠️ ৭. RESET ALL (SERVER RESET) (Slash Only) =================
    @app_commands.command(name="resetallinvite", description="⚠️ Reset all invite stats for this entire server (Admin Only)")
    @app_commands.default_permissions(administrator=True)
    async def resetallinvite(self, interaction: discord.Interaction):
        col = Database.get_collection("invites")
        col.delete_many({"guild_id": str(interaction.guild.id)})
        
        embed = discord.Embed(description="<:dot:1472268394391670855> All invite counts and history for this server have been permanently reset!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
