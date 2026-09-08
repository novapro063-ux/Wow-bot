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
# DASHBOARD UI CLASSES (For /invite_setup)
# ---------------------------------------------------------
class TrackerChannelSelect(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a channel for Invite Logs", row=0)
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        g_data = get_guild_data(self.guild_id)
        g_data["config"]["channel_id"] = str(select.values[0].id)
        g_data["config"]["is_enabled"] = True
        save_guild_data(self.guild_id, g_data)
        
        embed = discord.Embed(title="🔗 Invite Tracker Settings", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="Status", value="✅ Enabled", inline=True)
        embed.add_field(name="Log Channel", value=f"<#{select.values[0].id}>", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=TrackerDashboardView(self.guild_id))
        await interaction.followup.send(f"✅ Invite Log Channel set to <#{select.values[0].id}>!", ephemeral=True)

class TrackerDashboardView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        g_data = get_guild_data(guild_id)
        
        if g_data["config"]["is_enabled"]:
            self.btn_toggle.label = "❌ Disable Logs"
            self.btn_toggle.style = discord.ButtonStyle.danger
        else:
            self.btn_toggle.label = "✅ Enable Logs"
            self.btn_toggle.style = discord.ButtonStyle.success

    @discord.ui.button(label="📢 Set Log Channel", style=discord.ButtonStyle.primary, row=0)
    async def btn_set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=TrackerChannelSelect(self.guild_id))

    @discord.ui.button(label="Toggle", custom_id="btn_toggle", row=0)
    async def btn_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        g_data = get_guild_data(self.guild_id)
        g_data["config"]["is_enabled"] = not g_data["config"]["is_enabled"]
        save_guild_data(self.guild_id, g_data)
        
        embed = discord.Embed(title="🔗 Invite Tracker Settings", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="Status", value="✅ Enabled" if g_data["config"]["is_enabled"] else "❌ Disabled", inline=True)
        ch_id = g_data["config"]["channel_id"]
        embed.add_field(name="Log Channel", value=f"<#{ch_id}>" if ch_id else "Not Set", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=TrackerDashboardView(self.guild_id))


# ---------------------------------------------------------
# PAGINATION CLASS (For /invited list)
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
        self.total_pages = max(1, math.ceil(len(data) / self.items_per_page))
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

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        inviter = None
        used_invite = None

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
        
        if inviter:
            g_data, inviter_id = get_user_data(guild.id, inviter.id)
            _, joined_id = get_user_data(guild.id, member.id)

            inc_field = "regular"
            if member.bot: inc_field = "bots"
            elif (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days < 1: inc_field = "fake"
            
            entry_data = {
                "name": member.name,
                "id": str(member.id),
                "date": datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p"),
                "status": "New Join"
            }

            g_data["users"][inviter_id][inc_field] += 1
            g_data["users"][inviter_id]["history"].insert(0, entry_data)
            g_data["users"][joined_id]["invited_by"] = inviter_id
            g_data["users"][joined_id]["join_date"] = entry_data["date"]
            
            save_guild_data(guild.id, g_data)

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

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        g_data, member_id = get_user_data(member.guild.id, member.id)
        
        inviter_id = g_data["users"][member_id].get("invited_by")
        if inviter_id and inviter_id in g_data["users"]:
            g_data["users"][inviter_id]["leave"] += 1
            for history_entry in g_data["users"][inviter_id]["history"]:
                if history_entry["id"] == str(member.id):
                    history_entry["status"] = "Left"
                    break
            save_guild_data(member.guild.id, g_data)

            if g_data["config"]["is_enabled"] and g_data["config"]["channel_id"]:
                try:
                    ch = member.guild.get_channel(int(g_data["config"]["channel_id"]))
                    stats = g_data["users"][inviter_id]
                    net = max(0, (stats["regular"] + stats["bonus"]) - (stats["fake"] + stats["leave"]))
                    embed = discord.Embed(description=f"📤 {member.mention} left.", color=discord.Color.red())
                    embed.add_field(name="Invited By", value=f"<@{inviter_id}> (`{net}` invites left)", inline=False)
                    await ch.send(embed=embed)
                except: pass

    # ================= 🛠️ COMMANDS =================

    @app_commands.command(name="invite_setup", description="⚙️ Configure the invite tracker dashboard")
    @app_commands.default_permissions(administrator=True)
    async def invite_setup(self, interaction: discord.Interaction):
        g_data = get_guild_data(interaction.guild.id)
        embed = discord.Embed(title="🔗 Invite Tracker Settings", description="Set up a channel to log who invited who.", color=discord.Color.from_str("#2b2d31"))
        embed.add_field(name="Status", value="✅ Enabled" if g_data["config"]["is_enabled"] else "❌ Disabled", inline=True)
        ch_id = g_data["config"]["channel_id"]
        embed.add_field(name="Log Channel", value=f"<#{ch_id}>" if ch_id else "Not Set", inline=True)
        await interaction.response.send_message(embed=embed, view=TrackerDashboardView(interaction.guild.id), ephemeral=True)

    @commands.hybrid_command(name="sync_invites", description="🔄 Sync your past 12+ invites from Discord to Database")
    @commands.has_permissions(administrator=True)
    async def sync_invites(self, ctx):
        await ctx.defer()
        g_data = get_guild_data(ctx.guild.id)
        try:
            invites = await ctx.guild.invites()
            total_synced = 0
            
            user_uses = {}
            for inv in invites:
                if inv.inviter and inv.uses > 0:
                    uid = str(inv.inviter.id)
                    user_uses[uid] = user_uses.get(uid, 0) + inv.uses
                    
            for uid, uses in user_uses.items():
                if uid not in g_data["users"]:
                    g_data["users"][uid] = {"regular": 0, "fake": 0, "leave": 0, "bonus": 0, "bots": 0, "history": [], "invited_by": None, "join_date": None}
                g_data["users"][uid]["regular"] = uses
                total_synced += uses
                
            save_guild_data(ctx.guild.id, g_data)
            await ctx.send(embed=discord.Embed(description=f"✅ Successfully synced **{total_synced}** past invites from Discord links!", color=discord.Color.green()))
        except Exception as e:
            await ctx.send(f"❌ Failed to sync: {e}")

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
        await ctx.send(embed=embed)

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
            embed.description = f"👤 **Member:** {target.mention}\n❓ **Invited By:** Unknown\n⚠️ *Joined via Vanity URL or before tracking started.*"
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addinvite", description="🎁 Add bonus invites")
    @commands.has_permissions(administrator=True)
    async def addinvite(self, ctx, member: discord.Member, amount: int):
        g_data, user_id = get_user_data(ctx.guild.id, member.id)
        g_data["users"][user_id]["bonus"] += amount
        save_guild_data(ctx.guild.id, g_data)
        
        embed = discord.Embed(description=f"<:Star:1472268505238863945> Added **{amount}** bonus invites to {member.mention}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="removeinvite", description="🗑️ Remove bonus invites")
    @commands.has_permissions(administrator=True)
    async def removeinvite(self, ctx, member: discord.Member, amount: int):
        g_data, user_id = get_user_data(ctx.guild.id, member.id)
        g_data["users"][user_id]["bonus"] -= amount
        save_guild_data(ctx.guild.id, g_data)
        
        embed = discord.Embed(description=f"<:dot:1472268394391670855> Removed **{amount}** bonus invites from {member.mention}", color=discord.Color.orange())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearinvite", description="⚠️ Clear ALL invite data for a user")
    @commands.has_permissions(administrator=True)
    async def clearinvite(self, ctx, member: discord.Member):
        g_data = get_guild_data(ctx.guild.id)
        user_id = str(member.id)
        if user_id in g_data["users"]:
            del g_data["users"][user_id]
            save_guild_data(ctx.guild.id, g_data)
            await ctx.send(embed=discord.Embed(description=f"<:dot:1472268394391670855> **Success:** All invite data for {member.mention} has been wiped!", color=discord.Color.red()))
        else:
            await ctx.send(embed=discord.Embed(description="❌ This user already has 0 invites.", color=discord.Color.red()))

    @commands.hybrid_command(name="resetallinvite", description="⚠️ Wipe all invite data for the entire server")
    @commands.has_permissions(administrator=True)
    async def resetallinvite(self, ctx):
        g_data = get_guild_data(ctx.guild.id)
        g_data["users"] = {}
        save_guild_data(ctx.guild.id, g_data)
        await ctx.send(embed=discord.Embed(description="<:dot:1472268394391670855> All invite counts and history for this server have been reset!", color=discord.Color.red()))

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
    
