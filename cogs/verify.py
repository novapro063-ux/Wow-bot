import discord
from discord.ext import commands
import sqlite3
import random

# ==========================================
# DATABASE SETUP (Advanced Multi-Panel)
# ==========================================
class VerifyDB:
    def __init__(self):
        self.conn = sqlite3.connect("verification_data.db")
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS verify_panels 
                               (guild_id INTEGER, panel_id INTEGER, role_id INTEGER, 
                                log_channel_id INTEGER, target_channel_id INTEGER, 
                                panel_message TEXT, panel_gif TEXT, button_text TEXT,
                                PRIMARY KEY (guild_id, panel_id))''')
        self.conn.commit()

    def update_field(self, guild_id: int, panel_id: int, field: str, value):
        self.cursor.execute("SELECT guild_id FROM verify_panels WHERE guild_id = ? AND panel_id = ?", (guild_id, panel_id))
        if self.cursor.fetchone():
            self.cursor.execute(f"UPDATE verify_panels SET {field} = ? WHERE guild_id = ? AND panel_id = ?", (value, guild_id, panel_id))
        else:
            self.cursor.execute(f"INSERT INTO verify_panels (guild_id, panel_id, {field}) VALUES (?, ?, ?)", (guild_id, panel_id, value))
        self.conn.commit()

    def update_panel_details(self, guild_id: int, panel_id: int, message: str, gif: str, btn_text: str):
        self.cursor.execute("SELECT guild_id FROM verify_panels WHERE guild_id = ? AND panel_id = ?", (guild_id, panel_id))
        if self.cursor.fetchone():
            self.cursor.execute("UPDATE verify_panels SET panel_message = ?, panel_gif = ?, button_text = ? WHERE guild_id = ? AND panel_id = ?", 
                                (message, gif, btn_text, guild_id, panel_id))
        else:
            self.cursor.execute("INSERT INTO verify_panels (guild_id, panel_id, panel_message, panel_gif, button_text) VALUES (?, ?, ?, ?, ?)", 
                                (guild_id, panel_id, message, gif, btn_text))
        self.conn.commit()

    def get_config(self, guild_id: int, panel_id: int):
        self.cursor.execute("SELECT * FROM verify_panels WHERE guild_id = ? AND panel_id = ?", (guild_id, panel_id))
        return self.cursor.fetchone()

db = VerifyDB()


# ==========================================
# USER VERIFICATION (MODALS & BUTTONS)
# ==========================================
class VerifyCaptchaModal(discord.ui.Modal):
    def __init__(self, num1, num2, role_id, log_channel_id):
        super().__init__(title="🤖 Anti-Bot Verification")
        self.num1 = num1
        self.num2 = num2
        self.role_id = role_id
        self.log_channel_id = log_channel_id

        self.answer = discord.ui.TextInput(
            label=f"What is {num1} + {num2}?",
            placeholder="Type your answer here...",
            required=True,
            max_length=3
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        correct_answer = self.num1 + self.num2
        
        if not self.answer.value.isdigit() or int(self.answer.value) != correct_answer:
            return await interaction.response.send_message("❌ Incorrect answer! Please try again.", ephemeral=True)

        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ Role is missing. Contact an admin.", ephemeral=True)

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You have been successfully verified!", ephemeral=True)

            if self.log_channel_id:
                log_channel = interaction.guild.get_channel(self.log_channel_id)
                if log_channel:
                    embed = discord.Embed(title="✅ User Verified", description=f"{interaction.user.mention} passed the captcha.", color=discord.Color.green())
                    await log_channel.send(embed=embed)
                    
        except discord.Forbidden:
            await interaction.response.send_message("❌ Error: The bot does not have permission to manage this role.", ephemeral=True)

class VerifyPanelView(discord.ui.View):
    def __init__(self, panel_id: int, btn_text: str = "✅ Click to Verify"):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        
        btn = discord.ui.Button(
            label=btn_text, 
            style=discord.ButtonStyle.success, 
            custom_id=f"persistent_verify_btn_{panel_id}"
        )
        btn.callback = self.verify_callback
        self.add_item(btn)

    async def verify_callback(self, interaction: discord.Interaction):
        config = db.get_config(interaction.guild.id, self.panel_id)
        
        if not config or not config[2]:
            return await interaction.response.send_message("❌ This verification panel is not fully setup yet.", ephemeral=True)

        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        
        await interaction.response.send_modal(VerifyCaptchaModal(num1, num2, config[2], config[3]))


# ==========================================
# ADMIN DASHBOARD VIEWS & MODALS
# ==========================================
class EditPanelModal(discord.ui.Modal):
    def __init__(self, panel_id, current_msg, current_gif, current_btn):
        super().__init__(title=f"📝 Edit Panel {panel_id} Details")
        self.panel_id = panel_id
        
        self.panel_msg = discord.ui.TextInput(
            label="Panel Message", style=discord.TextStyle.paragraph, 
            default=current_msg if current_msg else "Welcome to the server!\nClick the button below to verify.",
            required=True, max_length=2000
        )
        self.btn_text = discord.ui.TextInput(
            label="Button Text", 
            default=current_btn if current_btn else "✅ Click to Verify",
            required=True, max_length=50
        )
        self.panel_gif = discord.ui.TextInput(
            label="GIF / Image URL (Optional)", default=current_gif if current_gif else "", required=False
        )
        
        self.add_item(self.panel_msg)
        self.add_item(self.btn_text)
        self.add_item(self.panel_gif)

    async def on_submit(self, interaction: discord.Interaction):
        db.update_panel_details(interaction.guild.id, self.panel_id, self.panel_msg.value.strip(), self.panel_gif.value.strip(), self.btn_text.value.strip())
        await interaction.response.send_message(f"✅ Panel {self.panel_id} details updated! Click **Send Panel** to apply changes.", ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self, panel_id: int):
        super().__init__(timeout=None)
        self.panel_id = panel_id

        # 1. Role Select
        role_select = discord.ui.RoleSelect(placeholder=f"1️⃣ Select Verified Role...", row=0)
        async def role_callback(interaction: discord.Interaction):
            db.update_field(interaction.guild.id, self.panel_id, "role_id", role_select.values[0].id)
            await interaction.response.send_message(f"✅ Role for Panel {self.panel_id} set!", ephemeral=True)
        role_select.callback = role_callback
        self.add_item(role_select)

        # 2. Target Channel Select
        target_select = discord.ui.ChannelSelect(placeholder=f"2️⃣ Select Target Channel...", channel_types=[discord.ChannelType.text], row=1)
        async def target_callback(interaction: discord.Interaction):
            db.update_field(interaction.guild.id, self.panel_id, "target_channel_id", target_select.values[0].id)
            await interaction.response.send_message(f"✅ Target Channel set to {target_select.values[0].mention}!", ephemeral=True)
        target_select.callback = target_callback
        self.add_item(target_select)

        # 3. Log Channel Select
        log_select = discord.ui.ChannelSelect(placeholder=f"3️⃣ Select Log Channel (Optional)...", channel_types=[discord.ChannelType.text], row=2)
        async def log_callback(interaction: discord.Interaction):
            db.update_field(interaction.guild.id, self.panel_id, "log_channel_id", log_select.values[0].id)
            await interaction.response.send_message(f"✅ Log Channel set!", ephemeral=True)
        log_select.callback = log_callback
        self.add_item(log_select)

        # 4. Hide Channels (Multi-Select Menu)
        hide_select = discord.ui.ChannelSelect(
            placeholder=f"4️⃣ Select Channels to Hide (Max 25 at once)", 
            channel_types=[discord.ChannelType.text, discord.ChannelType.voice, discord.ChannelType.forum],
            min_values=1, max_values=25, row=3
        )
        async def hide_callback(interaction: discord.Interaction):
            config = db.get_config(interaction.guild.id, self.panel_id)
            if not config or not config[2]:
                return await interaction.response.send_message("❌ Please set the **Verified Role** (Step 1) before hiding channels!", ephemeral=True)

            role = interaction.guild.get_role(config[2])
            if not role:
                return await interaction.response.send_message("❌ The verified role was deleted. Please set it again.", ephemeral=True)

            # Defer ব্যবহার করা হচ্ছে কারণ অনেক চ্যানেল আপডেট হতে সময় লাগতে পারে
            await interaction.response.defer(ephemeral=True)

            success_count = 0
            for channel in hide_select.values:
                try:
                    # Unverified (@everyone) দের জন্য হাইড করা হচ্ছে
                    await channel.set_permissions(interaction.guild.default_role, view_channel=False)
                    # Verified Role এর জন্য ওপেন করা হচ্ছে
                    await channel.set_permissions(role, view_channel=True)
                    success_count += 1
                except discord.Forbidden:
                    pass

            await interaction.followup.send(f"✅ **{success_count}** টি চ্যানেল হাইড করা হয়েছে! এখন আনভেরিফাইড ইউজাররা এগুলো দেখতে পারবে না।\n*(আপনি চাইলে আবার মেনু ওপেন করে আরও চ্যানেল সিলেক্ট করতে পারেন)*", ephemeral=True)
        hide_select.callback = hide_callback
        self.add_item(hide_select)

    @discord.ui.button(label="📝 Edit Text & Button", style=discord.ButtonStyle.secondary, row=4)
    async def edit_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = db.get_config(interaction.guild.id, self.panel_id)
        current_msg = config[5] if config else None
        current_gif = config[6] if config else None
        current_btn = config[7] if config else None
        await interaction.response.send_modal(EditPanelModal(self.panel_id, current_msg, current_gif, current_btn))

    @discord.ui.button(label="🚀 Send This Panel", style=discord.ButtonStyle.primary, row=4)
    async def send_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = db.get_config(interaction.guild.id, self.panel_id)
        
        if not config or not config[2]:
            return await interaction.response.send_message("❌ Please set the **Verified Role** first!", ephemeral=True)

        target_channel_id = config[4]
        target_channel = interaction.guild.get_channel(target_channel_id) if target_channel_id else interaction.channel

        if not target_channel:
            return await interaction.response.send_message("❌ Target channel not found or you don't have access.", ephemeral=True)

        msg = config[5] if config and config[5] else "Welcome to the server!\nClick the button below to verify."
        gif = config[6] if config and config[6] else None
        btn_text = config[7] if config and config[7] else "✅ Click to Verify"

        embed = discord.Embed(title=f"🔒 Server Verification", description=msg, color=discord.Color.blurple())
        
        if gif and gif.startswith("http"): embed.set_image(url=gif)
        elif interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
        
        try:
            await target_channel.send(embed=embed, view=VerifyPanelView(self.panel_id, btn_text))
            await interaction.response.send_message(f"✅ Panel successfully sent to {target_channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Bot is missing permissions to send messages in {target_channel.mention}.", ephemeral=True)

    @discord.ui.button(label="🔙 Back", style=discord.ButtonStyle.danger, row=4)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="⚙️ Verification Master Dashboard", description="Choose a Panel (1 to 5) from the dropdown below to configure it.", color=discord.Color.dark_theme())
        await interaction.response.edit_message(embed=embed, view=MainDashboardView())


class MainDashboardSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=f"Panel {i}", value=str(i), description=f"Configure Verification Panel {i}") for i in range(1, 6)]
        super().__init__(placeholder="Select a Verification Panel to configure...", options=options)
        
    async def callback(self, interaction: discord.Interaction):
        panel_id = int(self.values[0])
        embed = discord.Embed(
            title=f"⚙️ Configuring Panel {panel_id}", 
            description="**Step 1:** Select the Verified Role.\n**Step 2:** Select Target & Log Channels.\n**Step 3:** Use **Step 4** to hide specific channels from unverified users.\n**Step 4:** Edit panel details and click **Send**.", 
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=DashboardView(panel_id))


class MainDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainDashboardSelect())


# ==========================================
# MAIN COG
# ==========================================
class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for i in range(1, 6):
            self.bot.add_view(VerifyPanelView(panel_id=i))

    @commands.hybrid_command(name="verify_dashboard", aliases=["vdash"], description="Admin Only: Setup Advanced Multi-Verification System")
    @commands.has_permissions(administrator=True)
    async def verify_dashboard(self, ctx: commands.Context):
        embed = discord.Embed(
            title="⚙️ Verification Master Dashboard", 
            description="Welcome to the Advanced Verification System!\n\nUse the dropdown below to select which Panel (1 to 5) you want to configure.", 
            color=discord.Color.dark_theme()
        )
        await ctx.send(embed=embed, view=MainDashboardView(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(VerificationCog(bot))
  
