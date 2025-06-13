"""Main bot file using config.py."""
import discord
from discord.ext import commands
import logging
from pathlib import Path

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/kamasbot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True
intents.guilds = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

@bot.event
async def on_ready():
    logger.info(f'Bot is ready! Logged in as {bot.user}')
    
    # Load cogs
    from cogs.panel import PanelCog
    from cogs.tickets import TicketsCog
    from cogs.verification import VerificationCog
    from cogs.middleman_verification import MiddlemanVerificationCog
    from cogs.verification import VerificationCog
    
    await bot.add_cog(PanelCog(bot))
    await bot.add_cog(TicketsCog(bot))
    await bot.add_cog(VerificationCog(bot))
    await bot.add_cog(MiddlemanVerificationCog(bot))
    
    # Sync commands
    await bot.tree.sync()
    logger.info('Application commands synced')

if __name__ == '__main__':
    from config import DISCORD_TOKEN, SERVER_ID
    bot.run(DISCORD_TOKEN)
