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

    // ১. স্ল্যাশ কমান্ড রান হলে ড্যাশবোর্ড পাঠানো
    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            
            EmbedBuilder embed = new EmbedBuilder();
            embed.setTitle("👋 ওয়েলকাম সেটআপ ড্যাশবোর্ড");
            embed.setDescription("নিচের বাটন এবং মেনু ব্যবহার করে সার্ভারের ওয়েলকাম সিস্টেম ম্যানেজ করুন।");
            embed.setColor(Color.decode("#2b2d31"));

            Button btnEnable = Button.success("btn_welcome_on", "✅ Enable Welcome");
            Button btnDisable = Button.danger("btn_welcome_off", "❌ Disable Welcome");

            StringSelectMenu menu = StringSelectMenu.create("menu_welcome")
                .setPlaceholder("⚙️ অন্যান্য সেটিংস নির্বাচন করুন")
                .addOption("ওয়েলকাম চ্যানেল সেট করুন", "opt_channel", "নতুন মেম্বারদের কোথায় স্বাগতম জানানো হবে")
                .addOption("কাস্টম মেসেজ সেট করুন", "opt_message", "স্বাগতম জানানোর টেক্সট পরিবর্তন করুন")
                .build();

            event.replyEmbeds(embed.build())
                .setComponents(
                    ActionRow.of(btnEnable, btnDisable),
                    ActionRow.of(menu)
                )
                .setEphemeral(true) // শুধুমাত্র যে কমান্ড দিয়েছে সে দেখবে
                .queue();
        }
    }

    // ২. বাটন ক্লিক হ্যান্ডেল করা
    @Override
    public void onButtonInteraction(ButtonInteractionEvent event) {
        if (event.getComponentId().equals("btn_welcome_on")) {
            event.reply("✅ সার্ভারে ওয়েলকাম সিস্টেম চালু করা হয়েছে!").setEphemeral(true).queue();
        } else if (event.getComponentId().equals("btn_welcome_off")) {
            event.reply("❌ ওয়েলকাম সিস্টেম বন্ধ করা হয়েছে।").setEphemeral(true).queue();
        }
    }

    // ৩. সিলেকশন মেনু হ্যান্ডেল করা
    @Override
    public void onStringSelectInteraction(StringSelectInteractionEvent event) {
        if (event.getComponentId().equals("menu_welcome")) {
            String selectedValue = event.getValues().get(0);

            if (selectedValue.equals("opt_channel")) {
                event.reply("📢 দয়া করে যে চ্যানেলে ওয়েলকাম মেসেজ পাঠাতে চান, সেটি মেনশন করুন।").setEphemeral(true).queue();
            } else if (selectedValue.equals("opt_message")) {
                event.reply("📝 নতুন ওয়েলকাম মেসেজ টাইপ করার পপ-আপ সিস্টেম শীঘ্রই আসছে!").setEphemeral(true).queue();
            }
        }
    }
}

