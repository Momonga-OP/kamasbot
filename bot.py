import discord
from discord.ext import commands
import logging
import os
import sys

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.panel import PanelCog
from cogs.tickets import TicketsCog

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

@bot.event
async def on_ready():
    logger.info(f'Bot is ready! Logged in as {bot.user}')
    
    # Load cogs
    await bot.add_cog(PanelCog(bot))
    await bot.add_cog(TicketsCog(bot))
    
    # Sync app commands
    try:
        await bot.tree.sync()
        logger.info('Application commands synced')
    except Exception as e:
        logger.error(f'Error syncing commands: {e}')

if __name__ == '__main__':
    bot.run(os.environ['DISCORD_TOKEN'])
