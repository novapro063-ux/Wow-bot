import net.dv8tion.jda.api.EmbedBuilder;
import net.dv8tion.jda.api.entities.Guild;
import net.dv8tion.jda.api.entities.Member;
import net.dv8tion.jda.api.entities.Role;
import net.dv8tion.jda.api.entities.channel.concrete.TextChannel;
import net.dv8tion.jda.api.events.guild.member.GuildMemberJoinEvent;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.ButtonInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.EntitySelectInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.StringSelectInteractionEvent;
import net.dv8tion.jda.api.events.interaction.ModalInteractionEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.interactions.components.ActionRow;
import net.dv8tion.jda.api.interactions.components.buttons.Button;
import net.dv8tion.jda.api.interactions.components.selections.EntitySelectMenu;
import net.dv8tion.jda.api.interactions.components.selections.StringSelectMenu;
import net.dv8tion.jda.api.interactions.components.text.TextInput;
import net.dv8tion.jda.api.interactions.components.text.TextInputStyle;
import net.dv8tion.jda.api.interactions.modals.Modal;
import net.dv8tion.jda.api.utils.messages.MessageEditBuilder;
import net.dv8tion.jda.api.utils.messages.MessageEditData;

import java.awt.Color;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

public class WelcomeCog extends ListenerAdapter {

    // ---------------------------------------------------------
    // DATABASE (In-Memory Database for Configurations)
    // ---------------------------------------------------------
    private static final HashMap<String, ServerConfig> serverConfigs = new HashMap<>();

    private static class ServerConfig {
        boolean isEnabled = false;
        String welcomeChannelId = null;
        
        // Message & Visuals
        String displayMode = "BOTH"; // BOTH, IMAGE_ONLY, TEXT_ONLY
        String welcomeTitle = "**Welcome to {server_name}!**";
        String welcomeMessage = "Hey {user_mention}, you are lucky member **#{member_count}**!\n\n**To learn more, don't forget to check out the channels above.**";
        String bgImageUrl = "https://cdn.discordapp.com/attachments/1509733741302382670/1545129390063616010/tenor.gif?ex=6a9b0561&is=6a99b3e1&hm=78d4c8db38a5523aa3eba51b1f350c1d68a010313875874e31ded09a37f23e63&";
        String accentColor = "#5865F2"; 
        
        // Buttons
        LinkedHashMap<String, String> embedLinks = new LinkedHashMap<>();
        
        // Advanced Features
        boolean pingEnabled = false;
        String pingMessage = "Welcome {user_mention}!";
        int pingTimer = 3;

        String autoRoleId = null;
        boolean dmEnabled = false;
        String dmMessage = "Hello {user_name}, welcome to {server_name}! Please read the rules and enjoy your stay.";
    }

    private ServerConfig getConfig(String guildId) {
        return serverConfigs.computeIfAbsent(guildId, k -> new ServerConfig());
    }

    // ---------------------------------------------------------
    // 1. DASHBOARD GENERATOR (Dynamic UI)
    // ---------------------------------------------------------
    private MessageEditData getDashboard(String guildId) {
        ServerConfig config = getConfig(guildId);
        
        EmbedBuilder embed = new EmbedBuilder();
        embed.setTitle("⚙️ Ultimate Welcome Configuration");
        embed.setDescription("Manage all welcome features for this server using the panel below.\n*(Only Admins can use this dashboard)*");
        embed.setColor(Color.decode("#2b2d31"));

        // Dynamic Toggle Button
        Button toggleBtn = config.isEnabled 
            ? Button.danger("btn_toggle", "❌ Disable") 
            : Button.success("btn_toggle", "✅ Enable");

        ActionRow row1 = ActionRow.of(
            Button.success("btn_set_channel", "📢 Set Channel"),
            toggleBtn,
            Button.secondary("btn_test", "🧪 Test Welcome"),
            Button.secondary("btn_view_config", "👁️ View Config")
        );

        ActionRow row2 = ActionRow.of(
            Button.primary("btn_edit_msg", "✏️ Edit Message"),
            Button.primary("btn_display_mode", "🖥️ Display Mode"),
            Button.primary("btn_bg", "🖼️ Background"),
            Button.secondary("btn_placeholders", "📋 Placeholders")
        );

        ActionRow row3 = ActionRow.of(
            Button.success("btn_add_link", "➕ Add Link"),
            Button.secondary("btn_view_links", "🔗 View Links"),
            Button.primary("btn_accent", "🎨 Accent Color"),
            Button.danger("btn_reset", "🔄 Reset All")
        );

        ActionRow row4 = ActionRow.of(
            Button.success("btn_auto_role", "🎭 Set Auto-Role"),
            Button.primary("btn_dm", "✉️ DM Welcome"),
            Button.primary("btn_ping", "📌 Ping & Delete")
        );

        return new MessageEditBuilder().setEmbeds(embed.build()).setComponents(row1, row2, row3, row4).build();
    }

    // ---------------------------------------------------------
    // 2. SLASH COMMAND (Triggers Dashboard)
    // ---------------------------------------------------------
    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            MessageEditData dashboard = getDashboard(event.getGuild().getId());
            event.replyEmbeds(dashboard.getEmbeds()).setComponents(dashboard.getComponents()).setEphemeral(true).queue();
        }
    }

    // ---------------------------------------------------------
    // 3. BUTTON CLICKS HANDLER (Smooth Ephemeral Navigation)
    // ---------------------------------------------------------
    @Override
    public void onButtonInteraction(ButtonInteractionEvent event) {
        String guildId = event.getGuild().getId();
        ServerConfig config = getConfig(guildId);
        Button backBtn = Button.danger("btn_back_home", "🔙 Back to Dashboard");

        switch (event.getComponentId()) {
            
            // --- IN-MESSAGE MENU NAVIGATION ---
            case "btn_back_home":
                event.editMessage(getDashboard(guildId)).queue();
                break;

            case "btn_toggle":
                config.isEnabled = !config.isEnabled;
                event.editMessage(getDashboard(guildId)).queue();
                break;

            case "btn_set_channel":
                EntitySelectMenu channelMenu = EntitySelectMenu.create("menu_set_channel", EntitySelectMenu.SelectTarget.CHANNEL)
                    .setPlaceholder("Select a channel for welcome messages").build();
                event.editComponents(ActionRow.of(channelMenu), ActionRow.of(backBtn)).queue();
                break;

            case "btn_auto_role":
                EntitySelectMenu roleMenu = EntitySelectMenu.create("menu_auto_role", EntitySelectMenu.SelectTarget.ROLE)
                    .setPlaceholder("Select a role to give automatically").build();
                event.editComponents(ActionRow.of(roleMenu), ActionRow.of(backBtn)).queue();
                break;

            case "btn_display_mode":
                StringSelectMenu displayMenu = StringSelectMenu.create("menu_display")
                    .setPlaceholder("Select Display Mode")
                    .addOption("🖼️ Both (Image + Text)", "BOTH")
                    .addOption("📷 Image Only", "IMAGE_ONLY")
                    .addOption("📝 Text Only", "TEXT_ONLY")
                    .build();
                event.editComponents(ActionRow.of(displayMenu), ActionRow.of(backBtn)).queue();
                break;

            case "btn_view_config":
                EmbedBuilder confEmbed = new EmbedBuilder();
                confEmbed.setTitle("📊 Current Server Configuration");
                confEmbed.addField("Status", config.isEnabled ? "✅ Enabled" : "❌ Disabled", true);
                confEmbed.addField("Channel", config.welcomeChannelId != null ? "<#" + config.welcomeChannelId + ">" : "Not Set", true);
                confEmbed.addField("Display Mode", config.displayMode, true);
                confEmbed.addField("Auto-Role", config.autoRoleId != null ? "<@&" + config.autoRoleId + ">" : "None", true);
                confEmbed.addField("Accent Color", config.accentColor, true);
                confEmbed.addField("Ping & Delete", config.pingEnabled ? "Enabled (" + config.pingTimer + "s)" : "Disabled", true);
                confEmbed.addField("DM Welcome", config.dmEnabled ? "✅ Enabled" : "❌ Disabled", false);
                confEmbed.addField("Embed Buttons", config.embedLinks.size() + "/5 Configured", false);
                confEmbed.setColor(Color.decode(config.accentColor));
                event.editMessageEmbeds(confEmbed.build()).setComponents(ActionRow.of(backBtn)).queue();
                break;

            case "btn_placeholders":
                EmbedBuilder phEmbed = new EmbedBuilder();
                phEmbed.setTitle("📋 Available Placeholders");
                phEmbed.setDescription("Use these tags in your welcome message:\n\n" +
                    "`{display_name}` - User's display name\n" +
                    "`{user_name}` - User's username\n" +
                    "`{user_mention}` - Pings the user\n" +
                    "`{server_name}` - Server's name\n" +
                    "`{member_count}` - Total member count\n" +
                    "`{member_count_ordinal}` - e.g. 150th\n" +
                    "`{join_date}` - Time they joined\n" +
                    "`{creation_date}` - Account creation date");
                phEmbed.setColor(Color.decode("#2b2d31"));
                event.editMessageEmbeds(phEmbed.build()).setComponents(ActionRow.of(backBtn)).queue();
                break;

            case "btn_test":
                if (config.welcomeChannelId == null) {
                    event.reply("⚠️ Please set a welcome channel first!").setEphemeral(true).queue();
                    return;
                }
                event.reply("✅ Sending a test welcome message to <#" + config.welcomeChannelId + ">").setEphemeral(true).queue();
                executeWelcome(event.getGuild(), event.getMember(), config, true);
                break;

            case "btn_reset":
                serverConfigs.remove(guildId);
                event.editMessage(getDashboard(guildId)).queue();
                break;

            // --- MODAL POP-UPS (Forms) ---
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
                TextInput bgInput = TextInput.create("input_bg", "Background URL (GIF/PNG)", TextInputStyle.SHORT)
                    .setValue(config.bgImageUrl).setPlaceholder("Paste image/gif link here").setRequired(true).build();
                Modal bgModal = Modal.create("modal_bg", "Background Image Settings")
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
                Modal linkModal = Modal.create("modal_add_link", "Add Welcome Button")
                    .addActionRows(ActionRow.of(labelInput), ActionRow.of(urlInput)).build();
                event.replyModal(linkModal).queue();
                break;

            case "btn_view_links":
                StringBuilder linksStr = new StringBuilder();
                if (config.embedLinks.isEmpty()) linksStr.append("No buttons configured.");
                else config.embedLinks.forEach((k, v) -> linksStr.append("**").append(k).append("** : `").append(v).append("`\n"));
                EmbedBuilder linkEmbed = new EmbedBuilder().setTitle("🔗 Configured Buttons").setDescription(linksStr.toString()).setColor(Color.decode("#2b2d31"));
                event.editMessageEmbeds(linkEmbed.build()).setComponents(ActionRow.of(backBtn)).queue();
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
                TextInput pingMsgStr = TextInput.create("input_ping_msg", "Ping Message", TextInputStyle.SHORT)
                    .setValue(config.pingMessage).setRequired(true).build();
                TextInput pingTimer = TextInput.create("input_ping_timer", "Delete After (Seconds, 1-300)", TextInputStyle.SHORT)
                    .setValue(String.valueOf(config.pingTimer)).setRequired(true).build();
                Modal pingModal = Modal.create("modal_ping", "Ping & Delete Settings")
                    .addActionRows(ActionRow.of(pingStatus), ActionRow.of(pingMsgStr), ActionRow.of(pingTimer)).build();
                event.replyModal(pingModal).queue();
                break;
        }
    }

    // ---------------------------------------------------------
    // 4. SELECT MENUS HANDLER (Dropdown Interactions)
    // ---------------------------------------------------------
    @Override
    public void onEntitySelectInteraction(EntitySelectInteractionEvent event) {
        ServerConfig config = getConfig(event.getGuild().getId());

        if (event.getComponentId().equals("menu_set_channel")) {
            config.welcomeChannelId = event.getValues().get(0).getId();
            config.isEnabled = true;
            event.editMessage(getDashboard(event.getGuild().getId())).queue();
            event.getHook().sendMessage("✅ Channel set to <#" + config.welcomeChannelId + ">").setEphemeral(true).queue();
        } 
        else if (event.getComponentId().equals("menu_auto_role")) {
            config.autoRoleId = event.getValues().get(0).getId();
            event.editMessage(getDashboard(event.getGuild().getId())).queue();
            event.getHook().sendMessage("✅ Auto-Role set!").setEphemeral(true).queue();
        }
    }

    @Override
    public void onStringSelectInteraction(StringSelectInteractionEvent event) {
        if (event.getComponentId().equals("menu_display")) {
            ServerConfig config = getConfig(event.getGuild().getId());
            config.displayMode = event.getValues().get(0);
            event.editMessage(getDashboard(event.getGuild().getId())).queue();
            event.getHook().sendMessage("✅ Display mode updated to: " + config.displayMode).setEphemeral(true).queue();
        }
    }

    // ---------------------------------------------------------
    // 5. MODALS HANDLER (Saving User Inputs)
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
                event.reply("✅ Background image URL updated!").setEphemeral(true).queue();
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
    // 6. MEMBER JOIN EVENT & CORE WELCOME SENDER
    // ---------------------------------------------------------
   @Override
    public void onGuildMemberJoin(GuildMemberJoinEvent event) {
        Guild guild = event.getGuild();
        ServerConfig config = getConfig(guild.getId());
        if (!config.isEnabled || config.welcomeChannelId == null) return;
        executeWelcome(guild, event.getMember(), config, false);
    }

    private void executeWelcome(Guild guild, Member member, ServerConfig config, boolean isTest) {
        TextChannel channel = guild.getTextChannelById(config.welcomeChannelId);
        if (channel == null) return;

        // 1. Auto-Role
        if (!isTest && config.autoRoleId != null) {
            Role role = guild.getRoleById(config.autoRoleId);
            if (role != null && guild.getSelfMember().canInteract(role)) {
                guild.addRoleToMember(member, role).queue(null, err -> {});
            }
        }

        // 2. DM Welcome
        if (!isTest && config.dmEnabled) {
            String finalDm = formatPlaceholders(config.dmMessage, member, guild);
            member.getUser().openPrivateChannel().queue(
                pc -> pc.sendMessage(finalDm).queue(null, err -> {}), 
                err -> {} 
            );
        }

        // 3. Ping & Delete
        if (config.pingEnabled) {
            String pMsg = formatPlaceholders(config.pingMessage, member, guild);
            channel.sendMessage(pMsg).queue(msg -> {
                msg.delete().queueAfter(config.pingTimer, TimeUnit.SECONDS, null, err -> {});
            });
        }

        // 4. Build Embed based on Display Mode
        EmbedBuilder welcomeEmbed = new EmbedBuilder();
        
        if (config.displayMode.equals("BOTH") || config.displayMode.equals("TEXT_ONLY")) {
            welcomeEmbed.setAuthor(formatPlaceholders(config.welcomeTitle, member, guild), null, guild.getIconUrl());
            welcomeEmbed.setDescription(formatPlaceholders(config.welcomeMessage, member, guild));
            welcomeEmbed.setThumbnail(member.getUser().getEffectiveAvatarUrl());
            welcomeEmbed.setFooter("User ID: " + member.getId() + " • Member #" + guild.getMemberCount());
        }

        if (config.displayMode.equals("BOTH") || config.displayMode.equals("IMAGE_ONLY")) {
            welcomeEmbed.setImage(config.bgImageUrl);
        }

        try { welcomeEmbed.setColor(Color.decode(config.accentColor)); } 
        catch (Exception e) { welcomeEmbed.setColor(Color.decode("#5865F2")); }

        // 5. Attach Buttons & Send
        if (!config.embedLinks.isEmpty() && !config.displayMode.equals("IMAGE_ONLY")) {
            Button[] buttons = new Button[config.embedLinks.size()];
            int i = 0;
            for (Map.Entry<String, String> entry : config.embedLinks.entrySet()) {
                buttons[i++] = Button.link(entry.getValue(), entry.getKey());
            }
            channel.sendMessageEmbeds(welcomeEmbed.build()).setComponents(ActionRow.of(buttons)).queue();
        } else {
            channel.sendMessageEmbeds(welcomeEmbed.build()).queue();
        }
    }

    // ---------------------------------------------------------
    // 7. PLACEHOLDER FORMATTER
    // ---------------------------------------------------------
    private String formatPlaceholders(String text, Member member, Guild guild) {
        if (text == null) return "";
        long joinUnix = member.getTimeJoined().toEpochSecond();
        long createUnix = member.getTimeCreated().toEpochSecond();
        int count = guild.getMemberCount();
        String ordinal = count + (count % 10 == 1 && count != 11 ? "st" : count % 10 == 2 && count != 12 ? "nd" : count % 10 == 3 && count != 13 ? "rd" : "th");

        return text.replace("{display_name}", member.getEffectiveName())
            .replace("{user_name}", member.getUser().getName())
            .replace("{user_mention}", member.getAsMention())
            .replace("{user_id}", member.getId())
            .replace("{server_name}", guild.getName())
            .replace("{member_count}", String.valueOf(count))
            .replace("{member_count_ordinal}", ordinal)
            .replace("{join_date}", "<t:" + joinUnix + ":F>")
            .replace("{creation_date}", "<t:" + createUnix + ":R>");
    }
                     }
