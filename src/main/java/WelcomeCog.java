import net.dv8tion.jda.api.EmbedBuilder;
import net.dv8tion.jda.api.entities.Guild;
import net.dv8tion.jda.api.entities.Member;
import net.dv8tion.jda.api.entities.Role;
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
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

public class WelcomeCog extends ListenerAdapter {

    // ---------------------------------------------------------
    // DATABASE (In-Memory for now, replace with SQL/Mongo later)
    // ---------------------------------------------------------
    private static final HashMap<String, ServerConfig> serverConfigs = new HashMap<>();

    private static class ServerConfig {
        boolean isEnabled = false;
        String welcomeChannelId = null;
        
        // Customization
        String welcomeTitle = "Welcome to {server_name}!";
        String welcomeMessage = "Hey {user_mention}, you are lucky member **#{member_count}**!\n\n**To learn more, don't forget to check out the channels above.**";
        String bgImageUrl = "https://cdn.discordapp.com/attachments/1509733741302382670/1545129390063616010/tenor.gif?ex=6a9b0561&is=6a99b3e1&hm=78d4c8db38a5523aa3eba51b1f350c1d68a010313875874e31ded09a37f23e63&";
        String accentColor = "#5865F2"; 
        
        // Extra Features (Buttons on Welcome Message)
        LinkedHashMap<String, String> embedLinks = new LinkedHashMap<>(); // Label -> URL
        
        // Advanced / Ping Settings
        boolean pingEnabled = false;
        String pingMessage = "Welcome {user_mention}!";
        int pingTimer = 3;

        // NEW: Auto-Role & Direct Message Welcome
        String autoRoleId = null;
        boolean dmEnabled = false;
        String dmMessage = "Hello {user_name}, welcome to {server_name}! Please read the rules and enjoy your stay.";
    }

    private ServerConfig getConfig(String guildId) {
        return serverConfigs.computeIfAbsent(guildId, k -> new ServerConfig());
    }

    // ---------------------------------------------------------
    // 1. SLASH COMMAND: SETUP DASHBOARD
    // ---------------------------------------------------------
    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            
            EmbedBuilder embed = new EmbedBuilder();
            embed.setTitle("⚙️ Ultimate Welcome Configuration");
            embed.setDescription("Manage all welcome features for this server using the panel below.\n*(Only Admins can use this dashboard)*");
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

            // Row 3: Extra Features (Links & Colors)
            ActionRow row3 = ActionRow.of(
                Button.success("btn_add_link", "➕ Add Link"),
                Button.danger("btn_remove_link", "➖ Remove Link"),
                Button.secondary("btn_view_links", "🔗 View Links"),
                Button.primary("btn_accent", "🎨 Accent Color")
            );

            // Row 4: Advanced Aesthetic & Ping
            ActionRow row4 = ActionRow.of(
                Button.primary("btn_font_color", "🎨 Font Color"),
                Button.primary("btn_border", "⬜ Border Settings"),
                Button.danger("btn_disable_anim", "🎬 Disable Animation"),
                Button.primary("btn_ping", "📌 Ping & Delete")
            );

            // Row 5: NEW Powerful Features & Support
            ActionRow row5 = ActionRow.of(
                Button.success("btn_auto_role", "🎭 Set Auto-Role"),
                Button.primary("btn_dm", "✉️ Setup DM Welcome"),
                Button.link("https://discord.com", "💬 Support Server")
            );

            event.replyEmbeds(embed.build())
                .setComponents(row1, row2, row3, row4, row5)
                .setEphemeral(true)
                .queue();
        }
    }

    // ---------------------------------------------------------
    // 2. BUTTON CLICKS HANDLER
    // ---------------------------------------------------------
    @Override
    public void onButtonInteraction(ButtonInteractionEvent event) {
        String guildId = event.getGuild().getId();
        ServerConfig config = getConfig(guildId);

        switch (event.getComponentId()) {
            case "btn_set_channel":
                EntitySelectMenu channelMenu = EntitySelectMenu.create("menu_set_channel", EntitySelectMenu.SelectTarget.CHANNEL)
                    .setPlaceholder("Select a channel for welcome messages")
                    .build();
                event.reply("Please select the welcome channel below:")
                    .addActionRow(channelMenu).setEphemeral(true).queue();
                break;

            case "btn_auto_role":
                EntitySelectMenu roleMenu = EntitySelectMenu.create("menu_auto_role", EntitySelectMenu.SelectTarget.ROLE)
                    .setPlaceholder("Select a role to give automatically to new members")
                    .build();
                event.reply("Please select the Auto-Role below:")
                    .addActionRow(roleMenu).setEphemeral(true).queue();
                break;

            case "btn_disable":
                config.isEnabled = false;
                event.reply("❌ Welcome system has been **disabled**.").setEphemeral(true).queue();
                break;

            case "btn_view_config":
                EmbedBuilder confEmbed = new EmbedBuilder();
                confEmbed.setTitle("📊 Current Server Configuration");
                confEmbed.addField("Status", config.isEnabled ? "✅ Enabled" : "❌ Disabled", true);
                confEmbed.addField("Channel", config.welcomeChannelId != null ? "<#" + config.welcomeChannelId + ">" : "Not Set", true);
                confEmbed.addField("Auto-Role", config.autoRoleId != null ? "<@&" + config.autoRoleId + ">" : "None", true);
                confEmbed.addField("Accent Color", config.accentColor, true);
                confEmbed.addField("Ping & Delete", config.pingEnabled ? "Enabled (" + config.pingTimer + "s)" : "Disabled", true);
                confEmbed.addField("DM Welcome", config.dmEnabled ? "✅ Enabled" : "❌ Disabled", true);
                confEmbed.addField("Embed Buttons", config.embedLinks.size() + " buttons added", false);
                confEmbed.setColor(Color.decode(config.accentColor));
                event.replyEmbeds(confEmbed.build()).setEphemeral(true).queue();
                break;

            case "btn_edit_msg":
                TextInput titleInput = TextInput.create("input_title", "Welcome Title", TextInputStyle.SHORT)
                    .setValue(config.welcomeTitle).setRequired(true).build();
                TextInput msgInput = TextInput.create("input_msg", "Welcome Message", TextInputStyle.PARAGRAPH)
                    .setValue(config.welcomeMessage).setRequired(true).build();
                
                Modal msgModal = Modal.create("modal_edit_msg", "Edit Welcome Message")
                    .addActionRows(ActionRow.of(titleInput), ActionRow.of(msgInput)).build();
                event.replyModal(msgModal).queue();
                break;

            case "btn_bg":
                TextInput bgInput = TextInput.create("input_bg", "Background Image URL (GIF/PNG/JPG)", TextInputStyle.SHORT)
                    .setValue(config.bgImageUrl).setRequired(true).build();
                Modal bgModal = Modal.create("modal_bg", "Set Background Image")
                    .addActionRows(ActionRow.of(bgInput)).build();
                event.replyModal(bgModal).queue();
                break;

            case "btn_accent":
                TextInput colorInput = TextInput.create("input_color", "Accent Color (Hex Code)", TextInputStyle.SHORT)
                    .setValue(config.accentColor).setPlaceholder("#5865F2").setRequired(true).build();
                Modal colorModal = Modal.create("modal_color", "Set Accent Color")
                    .addActionRows(ActionRow.of(colorInput)).build();
                event.replyModal(colorModal).queue();
                break;

            case "btn_add_link":
                if (config.embedLinks.size() >= 5) {
                    event.reply("⚠️ You can only add up to 5 buttons!").setEphemeral(true).queue();
                    return;
                }
                TextInput labelInput = TextInput.create("input_label", "Button Label (e.g. Rules)", TextInputStyle.SHORT).setRequired(true).build();
                TextInput urlInput = TextInput.create("input_url", "Button URL (https://...)", TextInputStyle.SHORT).setRequired(true).build();
                Modal linkModal = Modal.create("modal_add_link", "Add Welcome Button Link")
                    .addActionRows(ActionRow.of(labelInput), ActionRow.of(urlInput)).build();
                event.replyModal(linkModal).queue();
                break;

            case "btn_remove_link":
                TextInput removeLabel = TextInput.create("input_remove_label", "Exact Button Label to Remove", TextInputStyle.SHORT).setRequired(true).build();
                Modal removeModal = Modal.create("modal_remove_link", "Remove Welcome Button")
                    .addActionRows(ActionRow.of(removeLabel)).build();
                event.replyModal(removeModal).queue();
                break;

            case "btn_view_links":
                StringBuilder linksStr = new StringBuilder();
                if (config.embedLinks.isEmpty()) linksStr.append("No buttons added yet.");
                else config.embedLinks.forEach((k, v) -> linksStr.append("**").append(k).append("** : `").append(v).append("`\n"));
                event.reply("🔗 **Current Welcome Buttons:**\n" + linksStr.toString()).setEphemeral(true).queue();
                break;

            case "btn_dm":
                TextInput dmStatus = TextInput.create("input_dm_status", "Enable DM Welcome? (yes/no)", TextInputStyle.SHORT)
                    .setValue(config.dmEnabled ? "yes" : "no").setRequired(true).build();
                TextInput dmMsg = TextInput.create("input_dm_msg", "DM Message", TextInputStyle.PARAGRAPH)
                    .setValue(config.dmMessage).setRequired(true).build();
                Modal dmModal = Modal.create("modal_dm", "Direct Message Settings")
                    .addActionRows(ActionRow.of(dmStatus), ActionRow.of(dmMsg)).build();
                event.replyModal(dmModal).queue();
                break;

            case "btn_ping":
                TextInput pingStatus = TextInput.create("input_ping_status", "Enable Ping? (yes/no)", TextInputStyle.SHORT)
                    .setValue(config.pingEnabled ? "yes" : "no").setRequired(true).build();
                TextInput pingMsg = TextInput.create("input_ping_msg", "Ping Message (must contain {user_mention})", TextInputStyle.SHORT)
                    .setValue(config.pingMessage).setRequired(true).build();
                TextInput pingTimer = TextInput.create("input_ping_timer", "Delete After (Seconds, 1-300)", TextInputStyle.SHORT)
                    .setValue(String.valueOf(config.pingTimer)).setRequired(true).build();

                Modal pingModal = Modal.create("modal_ping", "Ping & Delete Settings")
                    .addActionRows(ActionRow.of(pingStatus), ActionRow.of(pingMsg), ActionRow.of(pingTimer)).build();
                event.replyModal(pingModal).queue();
                break;

            case "btn_reset":
                serverConfigs.remove(guildId); 
                event.reply("✅ All welcome configurations have been reset to default.").setEphemeral(true).queue();
                break;

            case "btn_font_color":
            case "btn_border":
            case "btn_disable_anim":
                event.reply("🖼️ Custom Image Canvas settings (Font, Border, Animation) are reserved for Image Welcome generation. Currently using Embed mode!").setEphemeral(true).queue();
                break;

            case "btn_placeholders":
                EmbedBuilder phEmbed = new EmbedBuilder();
                phEmbed.setTitle("📋 Huge List of Available Placeholders");
                phEmbed.setDescription("You can use these powerful placeholders in your welcome message & DM:\n\n" +
                    "**User Placeholders:**\n" +
                    "`{display_name}` - User's display name\n" +
                    "`{user_name}` - User's username (without #)\n" +
                    "`{user_mention}` or `{user}` - Pings the user\n" +
                    "`{user_id}` - The user's ID number\n\n" +
                    "**Server Placeholders:**\n" +
                    "`{server_name}` or `{server}` - Server's name\n" +
                    "`{server_id}` - Server's ID number\n" +
                    "`{member_count}` - Total member count (e.g. 150)\n" +
                    "`{member_count_ordinal}` - Ordinal count (e.g. 150th)\n\n" +
                    "**Date Placeholders (Auto-formats to user timezone):**\n" +
                    "`{join_date}` - Time they joined the server\n" +
                    "`{creation_date}` - Time they created their account");
                phEmbed.setColor(Color.decode("#2b2d31"));
                event.replyEmbeds(phEmbed.build()).setEphemeral(true).queue();
                break;

            case "btn_test":
                if (config.welcomeChannelId == null) {
                    event.reply("⚠️ Please set a welcome channel first!").setEphemeral(true).queue();
                    return;
                }
                event.reply("✅ Sending a test welcome message to <#" + config.welcomeChannelId + ">").setEphemeral(true).queue();
                executeWelcome(event.getGuild(), event.getMember(), config, true);
                break;
        }
    }

    // ---------------------------------------------------------
    // 3. SELECT MENUS HANDLER (Channel & Roles)
    // ---------------------------------------------------------
    @Override
    public void onEntitySelectInteraction(EntitySelectInteractionEvent event) {
        ServerConfig config = getConfig(event.getGuild().getId());

        if (event.getComponentId().equals("menu_set_channel")) {
            config.welcomeChannelId = event.getValues().get(0).getId();
            config.isEnabled = true;
            event.reply("✅ Welcome channel successfully set to <#" + config.welcomeChannelId + ">!").setEphemeral(true).queue();
        } 
        else if (event.getComponentId().equals("menu_auto_role")) {
            config.autoRoleId = event.getValues().get(0).getId();
            event.reply("✅ Auto-Role successfully set to <@&" + config.autoRoleId + ">!").setEphemeral(true).queue();
        }
    }

    // ---------------------------------------------------------
    // 4. MODALS HANDLER (Saving Inputs)
    // ---------------------------------------------------------
    @Override
    public void onModalInteraction(ModalInteractionEvent event) {
        ServerConfig config = getConfig(event.getGuild().getId());

        switch (event.getModalId()) {
            case "modal_edit_msg":
                config.welcomeTitle = event.getValue("input_title").getAsString();
                config.welcomeMessage = event.getValue("input_msg").getAsString();
                event.reply("✅ Welcome message updated!").setEphemeral(true).queue();
                break;
            case "modal_bg":
                config.bgImageUrl = event.getValue("input_bg").getAsString();
                event.reply("✅ Background image updated!").setEphemeral(true).queue();
                break;
            case "modal_color":
                config.accentColor = event.getValue("input_color").getAsString();
                event.reply("✅ Accent color updated!").setEphemeral(true).queue();
                break;
            case "modal_add_link":
                String label = event.getValue("input_label").getAsString();
                String url = event.getValue("input_url").getAsString();
                if (!url.startsWith("http")) url = "https://" + url;
                config.embedLinks.put(label, url);
                event.reply("✅ Link Button added: **" + label + "**").setEphemeral(true).queue();
                break;
            case "modal_remove_link":
                String removeL = event.getValue("input_remove_label").getAsString();
                if (config.embedLinks.remove(removeL) != null) {
                    event.reply("✅ Link Button removed: **" + removeL + "**").setEphemeral(true).queue();
                } else {
                    event.reply("⚠️ Could not find a button with that exact label.").setEphemeral(true).queue();
                }
                break;
            case "modal_dm":
                config.dmEnabled = event.getValue("input_dm_status").getAsString().equalsIgnoreCase("yes");
                config.dmMessage = event.getValue("input_dm_msg").getAsString();
                event.reply("✅ DM Welcome settings updated!").setEphemeral(true).queue();
                break;
            case "modal_ping":
                config.pingEnabled = event.getValue("input_ping_status").getAsString().equalsIgnoreCase("yes");
                config.pingMessage = event.getValue("input_ping_msg").getAsString();
                try {
                    config.pingTimer = Integer.parseInt(event.getValue("input_ping_timer").getAsString());
                } catch (Exception e) { config.pingTimer = 3; }
                event.reply("✅ Ping & Delete settings updated!").setEphemeral(true).queue();
                break;
        }
    }

    // ---------------------------------------------------------
    // 5. SERVER DETECTION: ACTUAL MEMBER JOIN EVENT
    // ---------------------------------------------------------
    @Override
    public void onGuildMemberJoin(GuildMemberJoinEvent event) {
        Guild guild = event.getGuild();
        ServerConfig config = getConfig(guild.getId());
        
        if (!config.isEnabled || config.welcomeChannelId == null) return;
        executeWelcome(guild, event.getMember(), config, false);
    }

    // ---------------------------------------------------------
    // CORE FUNCTION: Replace placeholders, Send Embed, DM, Role
    // ---------------------------------------------------------
    private void executeWelcome(Guild guild, Member member, ServerConfig config, boolean isTest) {
        TextChannel channel = guild.getTextChannelById(config.welcomeChannelId);
        if (channel == null) return;

        // Auto-Role (Only on real join, not test)
        if (!isTest && config.autoRoleId != null) {
            Role role = guild.getRoleById(config.autoRoleId);
            if (role != null && guild.getSelfMember().canInteract(role)) {
                guild.addRoleToMember(member, role).queue(null, err -> {});
            }
        }

        // Direct Message Welcome (Only on real join)
        if (!isTest && config.dmEnabled) {
            String finalDm = formatPlaceholders(config.dmMessage, member, guild);
            member.getUser().openPrivateChannel().queue(
                pc -> pc.sendMessage(finalDm).queue(null, err -> {}), 
                err -> {} // Ignore if user has DMs closed
            );
        }

        // Ping & Delete
        if (config.pingEnabled) {
            String pMsg = formatPlaceholders(config.pingMessage, member, guild);
            channel.sendMessage(pMsg).queue(msg -> {
                msg.delete().queueAfter(config.pingTimer, TimeUnit.SECONDS, null, err -> {});
            });
        }

        // Build Stylish Embed
        String formattedTitle = formatPlaceholders(config.welcomeTitle, member, guild);
        String formattedMsg = formatPlaceholders(config.welcomeMessage, member, guild);

        EmbedBuilder welcomeEmbed = new EmbedBuilder();
        welcomeEmbed.setAuthor(formattedTitle, null, guild.getIconUrl());
        welcomeEmbed.setDescription(formattedMsg);
        welcomeEmbed.setImage(config.bgImageUrl); // Uses custom GIF/Image
        welcomeEmbed.setThumbnail(member.getUser().getEffectiveAvatarUrl());
        
        try {
            welcomeEmbed.setColor(Color.decode(config.accentColor));
        } catch (Exception e) {
            welcomeEmbed.setColor(Color.decode("#5865F2"));
        }
        
        welcomeEmbed.setFooter("User Identity: " + member.getId() + " • Member #" + guild.getMemberCount());

        // Attach Custom Button Links
        if (!config.embedLinks.isEmpty()) {
            ActionRow buttonRow = buildLinkButtons(config.embedLinks);
            channel.sendMessageEmbeds(welcomeEmbed.build()).setComponents(buttonRow).queue();
        } else {
            channel.sendMessageEmbeds(welcomeEmbed.build()).queue();
        }
    }

    // Helper: Placeholder Replacer
    private String formatPlaceholders(String text, Member member, Guild guild) {
        if (text == null) return "";
        
        long joinUnix = member.getTimeJoined().toEpochSecond();
        long createUnix = member.getTimeCreated().toEpochSecond();
        
        int count = guild.getMemberCount();
        String ordinal = count + (count % 10 == 1 && count != 11 ? "st" : count % 10 == 2 && count != 12 ? "nd" : count % 10 == 3 && count != 13 ? "rd" : "th");

        return text
            .replace("{display_name}", member.getEffectiveName())
            .replace("{user_name}", member.getUser().getName())
            .replace("{user_mention}", member.getAsMention())
            .replace("{user}", member.getAsMention())
            .replace("{user_id}", member.getId())
            .replace("{server_name}", guild.getName())
            .replace("{server}", guild.getName())
            .replace("{server_id}", guild.getId())
            .replace("{member_count}", String.valueOf(count))
            .replace("{member_count_ordinal}", ordinal)
            .replace("{join_date}", "<t:" + joinUnix + ":F>")
            .replace("{creation_date}", "<t:" + createUnix + ":R>");
    }

    // Helper: Build ActionRow from Links map
    private ActionRow buildLinkButtons(LinkedHashMap<String, String> links) {
        Button[] buttons = new Button[links.size()];
        int i = 0;
        for (Map.Entry<String, String> entry : links.entrySet()) {
            buttons[i++] = Button.link(entry.getValue(), entry.getKey());
        }
        return ActionRow.of(buttons);
    }
}
