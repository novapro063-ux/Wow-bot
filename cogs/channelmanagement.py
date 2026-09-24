import discord
from discord.ext import commands
from discord import app_commands
import typing

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
# DYNAMIC EMBED GENERATOR (Multi-Support)
# ---------------------------------------------------------
def get_manager_embed(channels: list[discord.abc.GuildChannel] = None, roles: list[discord.Role] = None):
    embed = discord.Embed(title="🎛️ Ultimate Channel Permission Manager", color=discord.Color.from_str("#2b2d31"))
    
    if not channels or not roles:
        embed.description = (
            "👇 **Please select Channels and Roles from the dropdowns below to edit permissions.**\n"
            "*(Tip: Since Discord shows max 25 items, simply **TYPE** the name in the dropdown to search for hidden channels/roles!)*\n"
            "*(Use the 🌍 button to quickly select the `@everyone` role)*"
        )
        return embed

    ch_mentions = ", ".join([ch.mention for ch in channels])
    r_mentions = ", ".join([r.mention for r in roles])
    
    embed.description = f"**Target Channels ({len(channels)}):** {ch_mentions}\n**Target Roles ({len(roles)}):** {r_mentions}"
    
    embed.add_field(
        name="📝 Ready to Apply", 
        value="Select permissions from the dropdowns below, then click **Allow**, **Deny**, or **Default** to apply them to all selected channels and roles at once.", 
        inline=False
    )
    
    embed.set_footer(text="⬜ Default (Inherit) | ✅ Allow | ❌ Deny")
    return embed


# ---------------------------------------------------------
# MAIN INTERACTIVE VIEW (Multi-Select Support)
# ---------------------------------------------------------
class ChannelManagerView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.target_channels = []
        self.target_roles = []
        self.selected_text_perms = []
        self.selected_voice_perms = []
        self.update_action_buttons()

    def update_action_buttons(self):
        is_ready = bool(self.target_channels and self.target_roles)
        has_perms = len(self.selected_text_perms) > 0 or len(self.selected_voice_perms) > 0

        for child in self.children:
            custom_id = getattr(child, "custom_id", "")
            if custom_id in ["sel_text", "sel_voice"]:
                child.disabled = not is_ready
            elif custom_id in ["btn_allow", "btn_deny", "btn_reset"]:
                child.disabled = not (is_ready and has_perms)

    # ROW 0: Channel Selection (Updated with explicit channel_types to show EVERYTHING)
    @discord.ui.select(
        cls=discord.ui.ChannelSelect, 
        placeholder="1️⃣ Select Channels (Type name to search...)", 
        min_values=1, 
        max_values=25, 
        custom_id="sel_chan", 
        row=0,
        channel_types=[
            discord.ChannelType.text, 
            discord.ChannelType.voice, 
            discord.ChannelType.category, 
            discord.ChannelType.news, 
            discord.ChannelType.forum, 
            discord.ChannelType.stage_voice
        ]
    )
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.target_channels = [self.guild.get_channel(ch.id) for ch in select.values if self.guild.get_channel(ch.id)]
        
        if not self.target_channels:
            return await interaction.response.send_message("❌ Error: Could not resolve channels.", ephemeral=True)
            
        self.update_action_buttons()
        await interaction.response.edit_message(embed=get_manager_embed(self.target_channels, self.target_roles), view=self)

    # ROW 1: Role Selection
    @discord.ui.select(
        cls=discord.ui.RoleSelect, 
        placeholder="2️⃣ Select Roles (Type name to search...)", 
        min_values=1, 
        max_values=25, 
        custom_id="sel_role", 
        row=1
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.target_roles = [self.guild.get_role(r.id) for r in select.values if self.guild.get_role(r.id)]
        
        if not self.target_roles:
            return await interaction.response.send_message("❌ Error: Could not resolve roles.", ephemeral=True)
            
        self.update_action_buttons()
        await interaction.response.edit_message(embed=get_manager_embed(self.target_channels, self.target_roles), view=self)

    # ROW 2: Text Permissions
    @discord.ui.select(placeholder="📝 Select Text & General Perms", options=TEXT_GENERAL_PERMS, min_values=1, max_values=len(TEXT_GENERAL_PERMS), custom_id="sel_text", row=2)
    async def text_perm_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_text_perms = select.values
        self.update_action_buttons()
        await interaction.response.edit_message(view=self)

    # ROW 3: Voice Permissions
    @discord.ui.select(placeholder="🎙️ Select Voice & Event Perms", options=VOICE_EVENT_PERMS, min_values=1, max_values=len(VOICE_EVENT_PERMS), custom_id="sel_voice", row=3)
    async def voice_perm_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_voice_perms = select.values
        self.update_action_buttons()
        await interaction.response.edit_message(view=self)

    # ROW 4: Action Buttons
    @discord.ui.button(label="@everyone", style=discord.ButtonStyle.primary, emoji="🌍", custom_id="btn_everyone", row=4)
    async def btn_everyone(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_channels:
            return await interaction.response.send_message("❌ Please select Channels first from the top dropdown!", ephemeral=True)
        
        self.target_roles = [self.guild.default_role]
        self.update_action_buttons()
        await interaction.response.edit_message(embed=get_manager_embed(self.target_channels, self.target_roles), view=self)

    async def apply_permissions(self, interaction: discord.Interaction, perm_value: typing.Optional[bool], action_name: str):
        all_selected_perms = self.selected_text_perms + self.selected_voice_perms
        if not self.target_channels or not self.target_roles or not all_selected_perms:
            return
            
        await interaction.response.defer(ephemeral=True) 

        success_count = 0
        error_count = 0

        for channel in self.target_channels:
            for role in self.target_roles:
                try:
                    overwrite = channel.overwrites_for(role)
                    kwargs = {perm: perm_value for perm in all_selected_perms}
                    overwrite.update(**kwargs)
                    
                    await channel.set_permissions(role, overwrite=overwrite, reason=f"Advanced Manager by {interaction.user}")
                    success_count += 1
                except discord.Forbidden:
                    error_count += 1
                except Exception:
                    error_count += 1
            
        self.selected_text_perms = []
        self.selected_voice_perms = []
        self.update_action_buttons()
        
        await interaction.edit_original_response(embed=get_manager_embed(self.target_channels, self.target_roles), view=self)
        
        msg = f"✅ Successfully set **{len(all_selected_perms)}** permissions to **{action_name}** for **{len(self.target_roles)}** role(s) in **{len(self.target_channels)}** channel(s)!"
        if error_count > 0:
            msg += f"\n⚠️ Encountered permission errors on **{error_count}** update attempts. Make sure my bot's role is higher than the roles you are editing."
            
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="Allow", style=discord.ButtonStyle.success, emoji="✅", custom_id="btn_allow", row=4)
    async def btn_allow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_permissions(interaction, True, "ALLOWED")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌", custom_id="btn_deny", row=4)
    async def btn_deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.apply_permissions(interaction, False, "DENIED")

    @discord.ui.button(label="Default", style=discord.ButtonStyle.secondary, emoji="⬜", custom_id="btn_reset", row=4)
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
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command must be used inside a server.", ephemeral=True)

        await interaction.response.send_message(embed=get_manager_embed(), view=ChannelManagerView(interaction.guild), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ChannelManagerCog(bot))
                       
