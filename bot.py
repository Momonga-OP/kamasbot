import discord
from discord.ext import commands
import logging
import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cogs.panel import PanelCog
from cogs.tickets import TicketsCog
from cogs.verification import VerificationCog

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Validate environment variables
required_env_vars = ['DISCORD_TOKEN', 'PANEL_CHANNEL_ID', 'TICKET_CHANNEL_ID', 'VERIFIED_DATA_CHANNEL_ID', 'SERVER_ID']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    sys.exit(1)

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
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info(f'Guilds: {len(bot.guilds)}')
    
    # Load cogs
    try:
        await bot.add_cog(PanelCog(bot))
        logger.info('PanelCog loaded successfully')
    except Exception as e:
        logger.error(f'Error loading PanelCog: {e}')
    
    try:
        await bot.add_cog(TicketsCog(bot))
        logger.info('TicketsCog loaded successfully')
    except Exception as e:
        logger.error(f'Error loading TicketsCog: {e}')
    
    try:
        await bot.add_cog(VerificationCog(bot))
        logger.info('VerificationCog loaded successfully')
    except Exception as e:
        logger.error(f'Error loading VerificationCog: {e}')
    
    # Sync app commands
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} application commands')
    except Exception as e:
        logger.error(f'Error syncing commands: {e}')

@bot.event
async def on_error(event, *args, **kwargs):
    logger.exception(f'An error occurred in event {event}')

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'Command error in {ctx.command}: {error}')

if __name__ == '__main__':
    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logger.exception(f'Failed to start bot: {e}')
        sys.exit(1)
