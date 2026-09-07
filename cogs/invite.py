import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import math
import asyncio

# ---------------------------------------------------------
# JSON DATABASE SETUP FOR INVITE TRACKER
# ---------------------------------------------------------
DATA_FILE = "invite_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f: json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        try: return json.load(f)
        except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

def get_guild_data(guild_id: int):
    data = load_data()
    g_id = str(guild_id)
    if g_id not in data:
        data[g_id] = {
            "config": {"channel_id": None, "is_enabled": False},
            "users": {} 
            # user_id: { regular: 0, fake: 0, leave: 0, bonus: 0, bots: 0, history: [], invited_by: None, join_date: None }
        }
        save_data(data)
    return data[g_id]

def save_guild_data(guild_id: int, guild_data: dict):
    data = load_data()
    data[str(guild_id)] = guild_data
    save_data(data)

def get_user_data(guild_id: int, user_id: int):
    g_data = get_guild_data(guild_id)
    u_id = str(user_id)
    if u_id not in g_data["users"]:
        g_data["users"][u_id] = {
            "regular": 0, "fake": 0, "leave": 0, "bonus": 0, "bots": 0,
            "history": [], "invited_by": None, "join_date": None
        }
    return g_data, u_id

# ---------------------------------------------------------
# BUTTON CLASS (Pagination View for /invited)
# ---------------------------------------------------------
class InvitePaginationView(discord.ui.View):
    def __init__(self, data, title, author, member_checked):
        super().__init__(timeout=60)
        self.data = data
        self.title = title
        self.author = author
        self.member_checked = member_checked
        self.current_page = 1
        self.items_per_page = 10
        self.total_pages = math.ceil(len(data) / self.items_per_page)
        self.update_buttons()

    def create_embed(self):
        start = (self.current_page - 1) * self.items_per_page
        end = start + self.items_per_page
        current_data = self.data[start:end]

        embed = discord.Embed(title=self.title, color=discord.Color.from_str("#2b2d31"), timestamp=datetime.datetime.now())
        embed.set_thumbnail(url=self.member_checked.display_avatar.url)

        description = ""
        for i, entry in enumerate(current_data, start=start + 1):
            status_icon = "🔄" if entry.get('status') == "Rejoined" else "🆕"
            if entry.get('status') == "Left": status_icon = "❌"
            
            description += (
                f"**{i}. {entry['name']}**\n"
                f"├─ ID: `{entry['id']}`\n"
                f"├─ Date: `{entry.get('date', 'Unknown')}`\n"
                f"└─ Status: **{entry.get('status', 'New Join')}** {status_icon}\n\n"
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


# ---------------------------------------------------------
# MAIN TRACKER COG
# ---------------------------------------------------------
class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites_cache = {}

    async def cog_load(self):
        """বট চালু হলে সমস্ত সার্ভারের ইনভাইট ক্যাশ করবে (100% Accuracy)"""
        for guild in self.bot.guilds:
            try: self.invites_cache[guild.id] = await guild.invites()
            except: pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        try: self.invites_cache[invite.guild.id] = await invite.guild.invites()
        except: pass

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        try: self.invites_cache[invite.guild.id] = await invite.guild.invites()
        except: pass

    # ================= 📥 JOIN TRACKING =================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        inviter = None
        used_invite = None

        # ১. ইনভাইটার খোঁজা (Bot & Human)
        if member.bot:
            try:
                await asyncio.sleep(0.5)
                async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=5):
                    if entry.target.id == member.id:
                        inviter = entry.user
                        break
            except: pass
        else:
            invites_before = self.invites_cache.get(guild.id, [])
            try:
                invites_after = await guild.invites()
                self.invites_cache[guild.id] = invites_after
                for i_before in invites_before:
                    for i_after in invites_after:
                        if i_before.code == i_after.code and i_after.uses > i_before.uses:
                            inviter = i_after.inviter
                            used_invite = i_after
                            break
            except: pass
        
        # ২. ডাটাবেসে সেভ করা
        if inviter:
            g_data, inviter_id = get_user_data(guild.id, inviter.id)
            _, joined_id = get_user_data(guild.id, member.id)

            # টাইপ নির্ধারণ (Regular, Fake, Bot)
            inc_field = "regular"
            if member.bot: inc_field = "bots"
            elif (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days < 1: inc_field = "fake"
            
            entry_data = {
                "name": member.name,
                "id": str(member.id),
                "date": datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                "status": "New Join"
            }

            # আপডেট Inviter
            g_data["users"][inviter_id][inc_field] += 1
            g_data["users"][inviter_id]["history"].insert(0, entry_data)

            # আপডেট Joined Member
            g_data["users"][joined_id]["invited_by"] = inviter_id
            g_data["users"][joined_id]["join_date"] = entry_data["date"]
            
            save_guild_data(guild.id, g_data)

            # Dashboard Log
            if g_data["config"]["is_enabled"] and g_data["config"]["channel_id"]:
                try:
                    ch = guild.get_channel(int(g_data["config"]["channel_id"]))
                    stats = g_data["users"][inviter_id]
                    net = max(0, (stats["regular"] + stats["bonus"]) - (stats["fake"] + stats["leave"]))
                    
                    embed = discord.Embed(description=f"📥 {member.mention} joined!", color=discord.Color.green())
                    embed.add_field(name="Invited By", value=f"{inviter.mention} (`{net}` invites)", inline=True)
                    if used_invite: embed.add_field(name="Code", value=f"`{used_invite.code}`", inline=True)
                    if inc_field == "fake": embed.add_field(name="⚠️ Warning", value="Account is less than 1 day old (Fake).", inline=False)
                    await ch.send(embed=embed)
                except: pass

    # ================= 📤 LEAVE TRACKING (100% Accurate) =================
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        g_data, member_id = get_user_data(member.guild.id, member.id)
        
        inviter_id = g_data["users"][member_id].get("invited_by")
        if inviter_id and inviter_id in g_data["users"]:
            # লিভ কাউন্ট প্লাস করা
            g_data["users"][inviter_id]["leave"] += 1
            
            # হিস্ট্রিতে স্ট্যাটাস 'Left' করে দেওয়া
            for history_entry in g_data["users"][inviter_id]["history"]:
                if history_entry["id"] == str(member.id):
                    history_entry["status"] = "Left"
                    break
            
            save_guild_data(member.guild.id, g_data)

            # Dashboard Log
            if g_data["config"]["is_enabled"] and g_data["config"]["channel_id"]:
                try:
                    ch = member.guild.get_channel(int(g_data["config"]["channel_id"]))
                    stats = g_data["users"][inviter_id]
                    net = max(0, (stats["regular"] + stats["bonus"]) - (stats["fake"] + stats["leave"]))
                    embed = discord.Embed(description=f"📤 {member.mention} left.", color=discord.Color.red())
                    embed.add_field(name="Invited By", value=f"<@{inviter_id}> (`{net}` invites left)", inline=False)
                    await ch.send(embed=embed)
                except: pass

    # ================= 📊 1. INVITE STATS =================
    @commands.hybrid_command(name="invite", aliases=["i"], description="📊 View invite stats")
    @app_commands.describe(member="User to check")
    async def invite(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        g_data, user_id = get_user_data(ctx.guild.id, member.id)
        data = g_data["users"][user_id]

        reg, fake, leave, bonus, bots = data["regular"], data["fake"], data["leave"], data["bonus"], data["bots"]
        total = max(0, (reg + bonus) - (fake + leave))

        embed = discord.Embed(color=discord.Color.from_str("#2b2d31"))
        embed.set_author(name=f"{member.name}", icon_url=member.display_avatar.url)
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
        embed.set_footer(text="Funny Bot Security", icon_url=self.bot.user.display_avatar.url if self.bot.user else None)
        await ctx.send(embed=embed)

    # ================= 📜 2. INVITED LIST =================
    @commands.hybrid_command(name="invited", aliases=["invites", "list", "il"], description="📜 See invited list")
    @app_commands.describe(member="User to check")
    async def invited(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        g_data, user_id = get_user_data(ctx.guild.id, target.id)
        history = g_data["users"][user_id].get("history", [])

        if not history:
            await ctx.send(embed=discord.Embed(description=f"❌ **{target.name}** has not invited anyone yet.", color=discord.Color.red()))
            return

        view = InvitePaginationView(data=history, title=f"📜 Invited by: {target.name}", author=ctx.author, member_checked=target)
        await ctx.send(embed=view.create_embed(), view=view)

    # ================= 🕵️ 3. INVITER (CHECK SOURCE) =================
    @commands.hybrid_command(name="inviter", aliases=["who", "check"], description="🕵️ Check inviter")
    @app_commands.describe(member="User to check")
    async def inviter(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        g_data, user_id = get_user_data(ctx.guild.id, target.id)
        
        embed = discord.Embed(title="Invite Source", color=discord.Color.from_str("#2b2d31"))
        embed.set_thumbnail(url=target.display_avatar.url)

        inviter_id = g_data["users"][user_id].get("invited_by")
        if inviter_id:
            date = g_data["users"][user_id].get("join_date", "Unknown")
            embed.description = f"👤 **Member:** {target.mention}\n📨 **Invited By:** <@{inviter_id}> (`{inviter_id}`)\n📅 **Date:** `{date}`"
        else:
            embed.description = f"👤 **Member:** {target.mention}\n❓ **Invited By:** Unknown\n⚠️ *Tracking started recently or Vanity URL used.*"

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ================= 🎁 4. ADD INVITE =================
    @commands.hybrid_command(name="addinvite", description="🎁 Add bonus invites")
    @commands.has_permissions(administrator=True)
    async def addinvite(self, ctx, member: discord.Member, amount: int):
        g_data, user_id = get_user_data(ctx.guild.id, member.id)
        g_data["users"][user_id]["bonus"] += amount
        save_guild_data(ctx.guild.id, g_data)
        
        embed = discord.Embed(description=f"<:Star:1472268505238863945> Added **{amount}** bonus invites to {member.mention}", color=discord.Color.green())
        embed.set_author(name=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ================= 🗑️ 5. REMOVE INVITE =================
    @commands.hybrid_command(name="removeinvite", description="🗑️ Remove bonus invites")
    @commands.has_permissions(administrator=True)
    async def removeinvite(self, ctx, member: discord.Member, amount: int):
        g_data, user_id = get_user_data(ctx.guild.id, member.id)
        g_data["users"][user_id]["bonus"] -= amount
        save_guild_data(ctx.guild.id, g_data)
        
        embed = discord.Embed(description=f"<:dot:1472268394391670855> Removed **{amount}** bonus invites from {member.mention}", color=discord.Color.orange())
        embed.set_author(name=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ================= 🧹 6. CLEAR INVITE =================
    @commands.hybrid_command(name="clearinvite", aliases=["ci"], description="⚠️ Clear ALL invite data for a user")
    @commands.has_permissions(administrator=True)
    async def clearinvite(self, ctx, member: discord.Member):
        g_data = get_guild_data(ctx.guild.id)
        user_id = str(member.id)
        
        if user_id in g_data["users"]:
            del g_data["users"][user_id]
            save_guild_data(ctx.guild.id, g_data)
            embed = discord.Embed(description=f"<:dot:1472268394391670855> **Success:** All invite data for {member.mention} has been wiped!", color=discord.Color.red())
        else:
            embed = discord.Embed(description="❌ This user already has 0 invites.", color=discord.Color.red())
            
        embed.set_author(name=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    # ================= ⚠️ 7. RESET ALL =================
    @commands.hybrid_command(name="resetallinvite", description="⚠️ Wipe all invite data for the entire server")
    @commands.has_permissions(administrator=True)
    async def resetallinvite(self, ctx):
        g_data = get_guild_data(ctx.guild.id)
        g_data["users"] = {}
        save_guild_data(ctx.guild.id, g_data)
        
        embed = discord.Embed(description="<:dot:1472268394391670855> All invite counts and history for this server have been reset!", color=discord.Color.red())
        embed.set_author(name=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
