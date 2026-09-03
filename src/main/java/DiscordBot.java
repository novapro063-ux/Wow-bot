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
        String token = System.getenv("TOKEN"); 
        
        if (token == null) {
            System.out.println("❌ ERROR: Bot Token missing! Please set TOKEN in environment variables.");
            return;
        }

        try {
            startDummyServer();

            JDA jda = JDABuilder.createLight(token)
                .enableIntents(GatewayIntent.GUILD_MESSAGES, GatewayIntent.MESSAGE_CONTENT)
                .setActivity(Activity.playing("Server Management"))
                .addEventListeners(new WelcomeCog()) 
                .build();

            // Command registration
            jda.updateCommands().addCommands(
                Commands.slash("welcome_setup", "Open the welcome setup dashboard")
            ).queue();
            
            System.out.println("✅ Bot is online and Cogs are loaded!");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

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
