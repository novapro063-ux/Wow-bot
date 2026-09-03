import com.sun.net.httpserver.HttpServer;
import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;
import net.dv8tion.jda.api.entities.Activity;
import net.dv8tion.jda.api.interactions.commands.build.Commands;
import net.dv8tion.jda.api.requests.GatewayIntent;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;

public class DiscordBot {

    public static void main(String[] args) {
        // রেন্ডার বা সিস্টেম থেকে টোকেন নেওয়া
        String token = System.getenv("TOKEN"); 
        
        if (token == null) {
            System.out.println("❌ ERROR: Bot Token missing! Please set TOKEN in environment variables.");
            return;
        }

        try {
            // রেন্ডারের জন্য ডামি সার্ভার স্টার্ট করা
            startDummyServer();

            // বট ইনিশিয়ালাইজ করা এবং Cogs (WelcomeCog) অ্যাড করা
            JDA jda = JDABuilder.createLight(token)
                .enableIntents(GatewayIntent.GUILD_MESSAGES, GatewayIntent.MESSAGE_CONTENT)
                .setActivity(Activity.playing("Server Management"))
                .addEventListeners(new WelcomeCog()) // এখানে আপনার Cog কানেক্ট করা হয়েছে
                .build();

            // বটের কমান্ড গ্লোবালি রেজিস্টার করা
            jda.updateCommands().addCommands(
                Commands.slash("welcome_setup", "ওয়েলকাম সিস্টেম সেটআপ করার ড্যাশবোর্ড খুলুন")
            ).queue();
            
            System.out.println("✅ বট সফলভাবে চালু হয়েছে এবং Cogs লোড হয়েছে!");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // রেন্ডারের পোর্ট বাইন্ডিং এরর এড়ানোর জন্য ছোট ওয়েব সার্ভার
    private static void startDummyServer() throws IOException {
        String portStr = System.getenv("PORT");
        int port = (portStr != null) ? Integer.parseInt(portStr) : 8080;
        
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", exchange -> {
            String response = "Discord Bot is Online and Running on Render!";
            exchange.sendResponseHeaders(200, response.length());
            OutputStream os = exchange.getResponseBody();
            os.write(response.getBytes());
            os.close();
        });
        server.start();
        System.out.println("🌐 Web Server started on port: " + port);
    }
}
