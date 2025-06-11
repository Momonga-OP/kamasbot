import discord
from discord.ext import commands
import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
intents.messages = True
intents.guilds = True

# Ensure privileged intents are explicitly enabled
intents.message_content = True  # This is a privileged intent
intents.members = True  # This is a privileged intent

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

@bot.event
async def on_ready():
    try:
        logger.info(f'Bot is ready! Logged in as {bot.user}')
        
        # Load cogs
        await bot.add_cog(PanelCog(bot))
        await bot.add_cog(TicketsCog(bot))
        
        # Sync app commands
        await bot.tree.sync()
        logger.info('Application commands synced')
    except discord.Forbidden as e:
        logger.error(f'Permission error: {e}')
        raise
    except discord.NotFound as e:
        logger.error(f'Channel or role not found: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error during startup: {e}')
        raise

if __name__ == '__main__':
    bot.run(os.environ['DISCORD_TOKEN'])
