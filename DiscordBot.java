import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;
import net.dv8tion.jda.api.entities.Activity;
import net.dv8tion.jda.api.events.interaction.command.SlashCommandInteractionEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.interactions.commands.build.Commands;
import net.dv8tion.jda.api.EmbedBuilder;
import com.sun.net.httpserver.HttpServer;

import java.awt.Color;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;

public class DiscordBot extends ListenerAdapter {

    public static void main(String[] args) {
        // Render থেকে টোকেন নেওয়া হবে
        String token = System.getenv("TOKEN"); 
        
        if (token == null) {
            System.out.println("❌ ERROR: Bot Token is missing in environment variables!");
            return;
        }

        try {
            // ডামি ওয়েব সার্ভার তৈরি (Render এর Port Binding এর জন্য)
            startDummyServer();

            // বট স্টার্ট করা
            JDA jda = JDABuilder.createLight(token)
                .addEventListeners(new DiscordBot())
                .setActivity(Activity.playing("Server Management"))
                .build();

            // স্ল্যাশ কমান্ড রেজিস্টার
            jda.updateCommands().addCommands(
                Commands.slash("welcome_setup", "ওয়েলকাম সিস্টেম সেটআপ করার ড্যাশবোর্ড খুলুন")
            ).queue();
            
            System.out.println("✅ বট সফলভাবে চালু হয়েছে!");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // Render এর জন্য ডামি ওয়েব সার্ভার
    private static void startDummyServer() throws IOException {
        String portStr = System.getenv("PORT");
        int port = (portStr != null) ? Integer.parseInt(portStr) : 8080;
        
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", exchange -> {
            String response = "Discord Bot is Running Perfectly!";
            exchange.sendResponseHeaders(200, response.length());
            OutputStream os = exchange.getResponseBody();
            os.write(response.getBytes());
            os.close();
        });
        server.start();
        System.out.println("🌐 Dummy Web Server started on port: " + port);
    }

    @Override
    public void onSlashCommandInteraction(SlashCommandInteractionEvent event) {
        if (event.getName().equals("welcome_setup")) {
            EmbedBuilder embed = new EmbedBuilder();
            embed.setTitle("👋 ওয়েলকাম সেটআপ ড্যাশবোর্ড");
            embed.setDescription("এই ড্যাশবোর্ডটি রেন্ডার থেকে হোস্ট করা হচ্ছে।");
            embed.setColor(Color.decode("#2b2d31"));
            
            event.replyEmbeds(embed.build()).setEphemeral(true).queue();
        }
    }
}

