import discord
from discord.ext import commands
from discord import app_commands
import typing

# ---------------------------------------------------------
# DEVELOPER / SUPER ADMIN ID
# ---------------------------------------------------------
MY_USER_ID = 1313370345851457569

# ---------------------------------------------------------
# ALL 35 PERMISSIONS SPLIT INTO TWO MENUS
# ---------------------------------------------------------
TEXT_GENERAL_PERMS = [
    discord.SelectOption(label="View Channel", value="view_channel", emoji="👁️"),
    discord.SelectOption(label="Manage Channel", value="manage_channels", emoji="⚙️"),
    discord.SelectOption(label="Manage Permissions", value="manage_roles", emoji="🔐"),
    discord.SelectOption(label="Manage Webhooks", value="manage_webhooks", emoji="🪝"),
    discord.SelectOption(label="Create Invite", value="create_instant_invite", emoji="📨"),
    discord.SelectOption(label="Send Messages", value="send_messages", emoji="💬"),
    discord.SelectOption(label="Embed Links", value="embed_links", emoji="🔗"),
    discord.SelectOption(label="Attach Files", value="attach_files", emoji="📁"),
    discord.SelectOption(label="Add Reactions", value="add_reactions", emoji="👍"),
    discord.SelectOption(label="Use External Emojis", value="use_external_emojis", emoji="😀"),
    discord.SelectOption(label="Use External Stickers", value="use_external_stickers", emoji="🖼️"),
    discord.SelectOption(label="Mention @everyone", value="mention_everyone", emoji="📢"),
    discord.SelectOption(label="Manage Messages", value="manage_messages", emoji="🗑️"),
    discord.SelectOption(label="Read Message History", value="read_message_history", emoji="📜"),
    discord.SelectOption(label="Send TTS Messages", value="send_tts_messages", emoji="🗣️"),
    discord.SelectOption(label="Use Slash Commands", value="use_application_commands", emoji="🤖"),
    discord.SelectOption(label="Send Msg in Threads", value="send_messages_in_threads", emoji="🧵"),
    discord.SelectOption(label="Create Public Threads", value="create_public_threads", emoji="🔓"),
    discord.SelectOption(label="Create Private Threads", value="create_private_threads", emoji="🔒"),
    discord.SelectOption(label="Manage Threads", value="manage_threads", emoji="🧶")
]

VOICE_EVENT_PERMS = [
    discord.SelectOption(label="Connect", value="connect", emoji="🔈"),
    discord.SelectOption(label="Speak", value="speak", emoji="🎙️"),
    discord.SelectOption(label="Video / Stream", value="stream", emoji="🎥"),
    discord.SelectOption(label="Use Voice Activity", value="use_voice_activation", emoji="🗣️"),
    discord.SelectOption(label="Priority Speaker", value="priority_speaker", emoji="⭐"),
    discord.SelectOption(label="Mute Members", value="mute_members", emoji="🔇"),
    discord.SelectOption(label="Deafen Members", value="deafen_members", emoji="🔕"),
    discord.SelectOption(label="Move Members", value="move_members", emoji="➡️"),
    discord.SelectOption(label="Send Voice Messages", value="send_voice_messages", emoji="🎤"),
    discord.SelectOption(label="Use Soundboard", value="use_soundboard", emoji="🎵"),
    discord.SelectOption(label="Use External Sounds", value="use_external_sounds", emoji="🎶"),
    discord.SelectOption(label="Use Activities", value="use_embedded_activities", emoji="🚀"),
    discord.SelectOption(label="Request to Speak", value="request_to_speak", emoji="✋"),
    discord.SelectOption(label="Create Events", value="create_events", emoji="📅"),
    discord.SelectOption(label="Manage Events", value="manage_events", emoji="🛠️")
]

# ---------------------------------------------------------
# DYNAMIC EMBED GENERATOR
# ---------------------------------------------------------
def get_manager_embed(channel: discord.abc.GuildChannel = None, role: discord.Role = None):
    embed = discord.Embed(title="🎛️ Ultimate Channel Permission Manager", color=discord.Color.from_str("#2b2d31"))
    
    if not channel or not role:
        embed.description = "👇 **Please select a Channel and a Role from the dropdowns below to view and edit permissions.**\n*(Tip: Use the 🌍 button for `@everyone` role)*"
        return embed

    embed.description = f"**Target Channel:** {channel.mention}\n**Target Role:** {role.mention}"
    
    # Get current permissions
    overwrite = channel.overwrites_for(role)
    
    # Text Permissions Column
    text_str = ""
    for p in TEXT_GENERAL_PERMS:
        val = getattr(overwrite, p.value, None)
        icon = "✅" if val is True else "❌" if val is False else "⬜"
        text_str += f"{icon} {p.label}\n"
        
    # Voice Permissions Column
    voice_str = ""
    for p in VOICE_EVENT_PERMS:
        val = getattr(overwrite, p.value, None)
        icon = "✅" if val is True else "❌" if val is False else "⬜"
        voice_str += f"{icon} {p.label}\n"
    
    embed.add_field(name="📝 Text & General", value=text_str, inline=True)
    embed.add_field(name="🎙️ Voice & Events", value=voice_str, inline=True)
    
    embed.set_footer(text="⬜ Default (Inherit) | ✅ Allow | ❌ Deny")
    return embed


# ---------------------------------------------------------
# MAIN INTERACTIVE VIEW
# ---------------------------------------------------------
class ChannelManagerView(discord.ui.View):
    def __init__(self, guild: discord.Guild, target_channel=None, target_role=None):
        super().__init__(timeout=None)
        self.guild = guild
        self.target_channel = target_channel
        self.target_role = target_role
        self.selected_text_perms = []
        self.selected_voice_perms = []
        
        is_ready = bool(self.target_channel and self.target_role)
        self.text_perm_select.disabled = not is_ready
        self.voice_perm_select.disabled = not is_ready
        self.btn_allow.disabled = True
        self.btn_deny.disabled = True
        self.btn_reset.disabled = True

    def update_action_buttons(self):
        has_perms = len(self.selected_text_perms) > 0 or len(self.selected_voice_perms) > 0
        self.btn_allow.disabled = not has_perms
        self.btn_deny.disabled = not has_perms
        self.btn_reset.disabled = not has_perms

    # ROW 0
    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="1️⃣ Select a Channel (Voice or Text)", row=0)
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True) # Anti-Timeout
        self.target_channel = select.values[0]
        new_view = ChannelManagerView(self.guild, self.target_channel, self.target_role)
        await interaction.edit_original_response(embed=get_manager_embed(self.target_channel, self.target_role), view=new_view)

    # ROW 1
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="2️⃣ Select a Specific Role (Skip if @everyone)", row=1)
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await interaction.response.defer(ephemeral=True) # Anti-Timeout
        self.target_role = select.values[0]
        new_view = ChannelManagerView(self.guild, self.target_channel, self.target_role)
        await interaction.edit_original_response(embed=get_manager_embed(self.target_channel, self.target_role), view=new_view)

    # ROW 2
    @discord.ui.select(placeholder="📝 Select Text & General Perms", options=TEXT_GENERAL_PERMS, min_values=1, max_values=len(TEXT_GENERAL_PERMS), row=2)
    async def text_perm_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)
        self.selected_text_perms = select.values
        self.update_action_buttons()
        await interaction.edit_original_response(view=self)

    # ROW 3
    @discord.ui.select(placeholder="🎙️ Select Voice & Event Perms", options=VOICE_EVENT_PERMS, min_values=1, max_values=len(VOICE_EVENT_PERMS), row=3)
    async def voice_perm_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)
        self.selected_voice_perms = select.values
        self.update_action_buttons()
        await interaction.edit_original_response(view=self)

    # ROW 4 Action Buttons
    @discord.ui.button(label="@everyone", style=discord.ButtonStyle.primary, emoji="🌍", row=4)
    async def btn_everyone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_channel:
            await interaction.response.send_message("❌ Please select a Channel first from the top dropdown!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        self.target_role = self.guild.default_role
        new_view = ChannelManagerView(self.guild, self.target_channel, self.target_role)
        await interaction.edit_original_response(embed=get_manager_embed(self.target_channel, self.target_role), view=new_view)

    async def apply_permissions(self, interaction: discord.Interaction, perm_value: typing.Optional[bool], action_name: str):
        await interaction.response.defer(ephemeral=True) # Heavy operation, preventing timeout
        all_selected_perms = self.selected_text_perms + self.selected_voice_perms
        if not self.target_channel or not self.target_role or not all_selected_perms:
            return
            
        try:
            overwrite = self.target_channel.overwrites_for(self.target_role)
            kwargs = {perm: perm_value for perm in all_selected_perms}
            overwrite.update(**kwargs)
            
            await self.target_channel.set_permissions(self.target_role, overwrite=overwrite, reason=f"Advanced Manager by {interaction.user}")
            
            new_view = ChannelManagerView(self.guild, self.target_channel, self.target_role)
            await interaction.edit_original_response(embed=get_manager_embed(self.target_channel, self.target_role), view=new_view)
            await interaction.followup.send(f"✅ Successfully set **{len(kwargs)}** permissions to **{action_name}** for {self.target_role.mention}!", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I am missing permissions! Please move my bot role higher.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Allow", style=discord.ButtonStyle.success, emoji="✅", row=4)
    async def btn_allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_permissions(interaction, True, "ALLOWED")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌", row=4)
    async def btn_deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_permissions(interaction, False, "DENIED")

    @discord.ui.button(label="Default", style=discord.ButtonStyle.secondary, emoji="⬜", row=4)
    async def btn_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_permissions(interaction, None, "DEFAULT")


# ---------------------------------------------------------
# MAIN COG
# ---------------------------------------------------------
class ChannelManagerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="channel_manager", description="Open the Ultimate Channel Permission Manager")
    @app_commands.default_permissions(administrator=True)
    async def channel_manager(self, interaction: discord.Interaction):
        # 1. Anti-Timeout lock
        await interaction.response.defer(ephemeral=True)
        
        # 2. Prevent DM Crash
        if not interaction.guild:
            await interaction.followup.send("❌ This command must be used inside a server.")
            return

        # 3. Super Admin Check
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != MY_USER_ID:
            await interaction.followup.send("❌ Only the Server Owner or Bot Developer can use the Channel Manager!")
            return
            
        # 4. Safely deploy dashboard
        await interaction.followup.send(embed=get_manager_embed(), view=ChannelManagerView(interaction.guild))

async def setup(bot):
    await bot.add_cog(ChannelManagerCog(bot))
    
