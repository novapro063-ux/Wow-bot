import discord
from discord.ext import commands
import os
import threading
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------------------------------------------------
# WEB SERVER FOR RENDER (Keeps the bot alive safely)
# ---------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is Online and Running smoothly on Render!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    # Using waitress instead of Flask's default dev server to remove warnings
    from waitress import serve
    serve(app, host='0.0.0.0', port=port)

# ---------------------------------------------------------
# BOT SETUP & COG LOADER
# ---------------------------------------------------------
class UltimateBot(commands.Bot):
    def __init__(self):
        # Enabling all intents (Important for Member Join event)
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        # Automatically load all files inside the 'cogs' folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"✅ Loaded Cog: {filename}")
        
        # Sync slash commands globally
        await self.tree.sync()
        print("✅ Slash commands synchronized globally!")

    async def on_ready(self):
        print(f"✅ Logged in successfully as {self.user}!")
        await self.change_presence(activity=discord.Game(name="Server Management"))


if __name__ == "__main__":
    # Start the web server in a background thread
    threading.Thread(target=run_server, daemon=True).start()
    
    # Start the Discord Bot
    token = os.environ.get("TOKEN")
    if not token:
        print("❌ ERROR: Bot Token is missing in environment variables.")
    else:
        bot = UltimateBot()
        bot.run(token)
        
