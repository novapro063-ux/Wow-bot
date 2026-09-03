import net.dv8tion.jda.api.EmbedBuilder;
import net.dv8tion.jda.api.entities.Guild;
import net.dv8tion.jda.api.entities.Member;
import net.dv8tion.jda.api.entities.channel.concrete.TextChannel;
import net.dv8tion.jda.api.events.guild.member.GuildMemberJoinEvent;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.ButtonInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.EntitySelectInteractionEvent;
import net.dv8tion.jda.api.events.interaction.ModalInteractionEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.interactions.components.ActionRow;
import net.dv8tion.jda.api.interactions.components.buttons.Button;
import net.dv8tion.jda.api.interactions.components.selections.EntitySelectMenu;
import net.dv8tion.jda.api.interactions.components.text.TextInput;
import net.dv8tion.jda.api.interactions.components.text.TextInputStyle;
import net.dv8tion.jda.api.interactions.modals.Modal;

import java.awt.Color;
import java.util.HashMap;

public class WelcomeCog extends ListenerAdapter {

    // Server Detection System: Saves unique configurations for each Guild ID
    private static final HashMap<String, ServerConfig> serverConfigs = new HashMap<>();

    // Internal Data Class for Server Configs
    private static class ServerConfig {
        String welcomeChannelId = null;
        String welcomeTitle = "**Welcome to {server_name}!**";
        String welcomeMessage = "Hello {user_mention}, thanks for joining!";
        boolean isEnabled = false;
    }

    // Helper method to get or create a config for a specific server
    private ServerConfig getConfig(String guildId) {
        return serverConfigs.computeIfAbsent(guildId, k -> new ServerConfig());
    }

    // 1. SLASH COMMAND: Opens the Advanced Dashboard
    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            
            EmbedBuilder embed = new EmbedBuilder();
            embed.setTitle("⚙️ Welcome Bot Configuration");
            embed.setDescription("Manage the welcome system for this server using the panel below.");
            embed.setColor(Color.decode("#2b2d31"));

            // Row 1: Basic Setup
            ActionRow row1 = ActionRow.of(
                Button.success("btn_set_channel", "📢 Set Channel"),
                Button.danger("btn_disable", "🔄 Disable"),
                Button.secondary("btn_test", "🧪 Test Welcome"),
                Button.secondary("btn_view_config", "👁️ View Config")
            );

            // Row 2: Customization
            ActionRow row2 = ActionRow.of(
                Button.primary("btn_edit_msg", "✏️ Edit Message"),
                Button.primary("btn_bg", "🖼️ Background"),
                Button.secondary("btn_placeholders", "📋 View Placeholders"),
                Button.danger("btn_reset", "🔄 Reset All")
            );

            // Row 3: Extra
            ActionRow row3 = ActionRow.of(
                Button.success("btn_add_link", "➕ Add Link"),
                Button.danger("btn_remove_link", "➖ Remove Link"),
                Button.secondary("btn_view_links", "🔗 View Links"),
                Button.primary("btn_accent", "🎨 Accent Color")
            );

            // Row 4: Advanced Settings
            ActionRow row4 = ActionRow.of(
                Button.primary("btn_font_color", "🎨 Font Color"),
                Button.primary("btn_border", "⬜ Border Settings"),
                Button.danger("btn_disable_anim", "🎬 Disable Animation"),
                Button.primary("btn_ping", "📌 Ping & Delete")
            );

            // Row 5: Support
            ActionRow row5 = ActionRow.of(
                Button.link("https://discord.com", "💬 Support Server")
            );

            event.replyEmbeds(embed.build())
                .setComponents(row1, row2, row3, row4, row5)
                .setEphemeral(true)
                .queue();
        }
    }

    // 2. BUTTON CLICKS HANDLER
    @Override
    public void onButtonInteraction(ButtonInteractionEvent event) {
        String guildId = event.getGuild().getId();
        ServerConfig config = getConfig(guildId);

        switch (event.getComponentId()) {
            case "btn_set_channel":
                // Creates a Channel Select Menu
                EntitySelectMenu channelMenu = EntitySelectMenu.create("menu_set_channel", EntitySelectMenu.SelectTarget.CHANNEL)
                    .setPlaceholder("Select a channel for welcome messages")
                    .build();
                event.reply("Please select the welcome channel below:")
                    .addActionRow(channelMenu)
                    .setEphemeral(true)
                    .queue();
                break;

            case "btn_disable":
                config.isEnabled = false;
                event.reply("❌ Welcome system has been disabled for this server.").setEphemeral(true).queue();
                break;

            case "btn_edit_msg":
                // Creates a Modal for editing message
                TextInput titleInput = TextInput.create("input_title", "Welcome Title", TextInputStyle.SHORT)
                    .setValue(config.welcomeTitle)
                    .setRequired(true)
                    .build();

                TextInput msgInput = TextInput.create("input_msg", "Welcome Message", TextInputStyle.PARAGRAPH)
                    .setValue(config.welcomeMessage)
                    .setRequired(true)
                    .build();

                Modal modal = Modal.create("modal_edit_msg", "Edit Welcome Message")
                    .addActionRows(ActionRow.of(titleInput), ActionRow.of(msgInput))
                    .build();

                event.replyModal(modal).queue();
                break;

            case "btn_placeholders":
                // Shows available placeholders
                EmbedBuilder phEmbed = new EmbedBuilder();
                phEmbed.setTitle("📋 Available Placeholders");
                phEmbed.setDescription("You can use these placeholders in your welcome message:\n\n" +
                    "**User Placeholders:**\n" +
                    "`{display_name}` - User's display name\n" +
                    "`{user_name}` - User's username\n" +
                    "`{user_mention}` - Mentions the user\n\n" +
                    "**Server Placeholders:**\n" +
                    "`{server_name}` - Server's name\n" +
                    "`{member_count}` - Total member count");
                phEmbed.setColor(Color.decode("#2b2d31"));
                event.replyEmbeds(phEmbed.build()).setEphemeral(true).queue();
                break;

            case "btn_test":
                if (config.welcomeChannelId == null) {
                    event.reply("⚠️ Please set a welcome channel first!").setEphemeral(true).queue();
                    return;
                }
                event.reply("✅ Sending a test welcome message to <#" + config.welcomeChannelId + ">").setEphemeral(true).queue();
                sendWelcomeMessage(event.getGuild(), event.getMember(), config);
                break;

            default:
                event.reply("🛠️ This feature is currently under development!").setEphemeral(true).queue();
                break;
        }
    }

    // 3. ENTITY SELECT MENU HANDLER (For Channel Selection)
    @Override
    public void onEntitySelectInteraction(EntitySelectInteractionEvent event) {
        if (event.getComponentId().equals("menu_set_channel")) {
            String selectedChannelId = event.getValues().get(0).getId();
            ServerConfig config = getConfig(event.getGuild().getId());
            
            config.welcomeChannelId = selectedChannelId;
            config.isEnabled = true;
            
            event.reply("✅ Welcome channel successfully set to <#" + selectedChannelId + ">!").setEphemeral(true).queue();
        }
    }

    // 4. MODAL SUBMIT HANDLER (For Saving the Custom Message)
    @Override
    public void onModalInteraction(ModalInteractionEvent event) {
        if (event.getModalId().equals("modal_edit_msg")) {
            String newTitle = event.getValue("input_title").getAsString();
            String newMsg = event.getValue("input_msg").getAsString();

            ServerConfig config = getConfig(event.getGuild().getId());
            config.welcomeTitle = newTitle;
            config.welcomeMessage = newMsg;

            event.reply("✅ Welcome message has been successfully updated!").setEphemeral(true).queue();
        }
    }

    // 5. SERVER DETECTION: MEMBER JOIN EVENT
    @Override
    public void onGuildMemberJoin(GuildMemberJoinEvent event) {
        Guild guild = event.getGuild();
        ServerConfig config = getConfig(guild.getId());

        // Check if welcome system is enabled and channel is set for THIS specific server
        if (!config.isEnabled || config.welcomeChannelId == null) return;

        sendWelcomeMessage(guild, event.getMember(), config);
    }

    // Core function to replace placeholders and send the message
    private void sendWelcomeMessage(Guild guild, Member member, ServerConfig config) {
        TextChannel channel = guild.getTextChannelById(config.welcomeChannelId);
        if (channel == null) return;

        // Replace Placeholders
        String formattedTitle = config.welcomeTitle
            .replace("{server_name}", guild.getName())
            .replace("{user_mention}", member.getAsMention())
            .replace("{display_name}", member.getEffectiveName())
            .replace("{user_name}", member.getUser().getName())
            .replace("{member_count}", String.valueOf(guild.getMemberCount()));

        String formattedMsg = config.welcomeMessage
            .replace("{server_name}", guild.getName())
            .replace("{user_mention}", member.getAsMention())
            .replace("{display_name}", member.getEffectiveName())
            .replace("{user_name}", member.getUser().getName())
            .replace("{member_count}", String.valueOf(guild.getMemberCount()));

        EmbedBuilder welcomeEmbed = new EmbedBuilder();
        welcomeEmbed.setTitle(formattedTitle);
        welcomeEmbed.setDescription(formattedMsg);
        welcomeEmbed.setColor(Color.decode("#2b2d31"));
        welcomeEmbed.setThumbnail(member.getUser().getEffectiveAvatarUrl());

        channel.sendMessageEmbeds(welcomeEmbed.build()).queue();
    }
}
