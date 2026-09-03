import net.dv8tion.jda.api.EmbedBuilder;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.ButtonInteractionEvent;
import net.dv8tion.jda.api.events.interaction.component.StringSelectInteractionEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.interactions.components.ActionRow;
import net.dv8tion.jda.api.interactions.components.buttons.Button;
import net.dv8tion.jda.api.interactions.components.selections.StringSelectMenu;

import java.awt.Color;

public class WelcomeCog extends ListenerAdapter {

    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            
            EmbedBuilder embed = new EmbedBuilder();
            embed.setTitle("👋 Welcome Setup Dashboard");
            embed.setDescription("Use the buttons and menu below to configure the welcome system for this server.\n*(Admin only)*");
            embed.setColor(Color.decode("#2b2d31"));

            Button btnEnable = Button.success("btn_welcome_on", "✅ Enable Welcome");
            Button btnDisable = Button.danger("btn_welcome_off", "❌ Disable Welcome");

            StringSelectMenu menu = StringSelectMenu.create("menu_welcome")
                .setPlaceholder("⚙️ Select other settings")
                .addOption("Set Welcome Channel", "opt_channel", "Where should new members be greeted?")
                .addOption("Set Custom Message", "opt_message", "Change the welcome greeting text")
                .build();

            // ephemeral = true মানে শুধু আপনি এই প্যানেলটি দেখতে পাবেন
            event.replyEmbeds(embed.build())
                .setComponents(
                    ActionRow.of(btnEnable, btnDisable),
                    ActionRow.of(menu)
                )
                .setEphemeral(true)
                .queue();
        }
    }

    @Override
    public void onButtonInteraction(ButtonInteractionEvent event) {
        if (event.getComponentId().equals("btn_welcome_on")) {
            event.reply("✅ The welcome system has been **enabled** for this server!").setEphemeral(true).queue();
        } else if (event.getComponentId().equals("btn_welcome_off")) {
            event.reply("❌ The welcome system has been **disabled**.").setEphemeral(true).queue();
        }
    }

    @Override
    public void onStringSelectInteraction(StringSelectInteractionEvent event) {
        if (event.getComponentId().equals("menu_welcome")) {
            String selectedValue = event.getValues().get(0);

            if (selectedValue.equals("opt_channel")) {
                event.reply("📢 Please mention the channel where you want the welcome messages to be sent.").setEphemeral(true).queue();
            } else if (selectedValue.equals("opt_message")) {
                event.reply("📝 The pop-up modal to type a custom welcome message will be added soon!").setEphemeral(true).queue();
            }
        }
    }
}
