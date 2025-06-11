import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import os
import logging

from ..utils.constants import PANEL_CHANNEL_ID
from ..utils.utils import fetch_kamas_logo

logger = logging.getLogger(__name__)

class KamasView(ui.View):
    """View containing the Buy, Sell, and Verification buttons."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="BUY KAMAS", style=discord.ButtonStyle.primary, custom_id="buy_kamas", emoji="💰")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KamasModal("BUY"))
    
    @discord.ui.button(label="SELL KAMAS", style=discord.ButtonStyle.success, custom_id="sell_kamas", emoji="💎")
    async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KamasModal("SELL"))
    
    @discord.ui.button(label="BECOME VERIFIED SELLER", style=discord.ButtonStyle.secondary, custom_id="verify_seller", emoji="🏆")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerificationModal())

class CurrencySelect(ui.Select):
    """Dropdown menu for selecting currency."""
    
    def __init__(self):
        options = [
            discord.SelectOption(label="Euro (€)", value="EUR", emoji="💶"),
            discord.SelectOption(label="US Dollar ($)", value="USD", emoji="💵")
        ]
        super().__init__(placeholder="Select currency", min_values=1, max_values=1, options=options, custom_id="currency_select")

class PanelCog(commands.Cog):
    """Cog for managing the main panel interface."""
    
    def __init__(self, bot):
        self.bot = bot
        self.panel_message = None
        self.bot.loop.create_task(self.setup_panel())
    
    async def setup_panel(self):
        await self.bot.wait_until_ready()
        try:
            panel_channel = self.bot.get_channel(PANEL_CHANNEL_ID)
            if not panel_channel:
                panel_channel = await self.bot.fetch_channel(PANEL_CHANNEL_ID)
            
            panel_message_id = None
            panel_file_path = "kamas_panel_id.txt"
            if os.path.exists(panel_file_path):
                with open(panel_file_path, "r") as f:
                    try:
                        panel_message_id = int(f.read().strip())
                    except (ValueError, IOError):
                        logger.warning("Could not read panel message ID from file")
            
            existing_message = None
            if panel_message_id:
                try:
                    existing_message = await panel_channel.fetch_message(panel_message_id)
                    logger.info(f"Found existing kamas panel message: {panel_message_id}")
                except discord.NotFound:
                    logger.info("Stored kamas panel message not found, creating new one")
                except Exception as e:
                    logger.exception(f"Error fetching kamas panel message: {e}")
            
            kamas_logo = await fetch_kamas_logo()
            
            embed = discord.Embed(
                title=" AFL Wall Street - Kamas Trading ",
                description=(
                    "**Secure & Reliable Kamas Trading Platform**\n\n"
                    "Looking to buy or sell kamas safely? AFL Wall Street facilitates secure meetings "
                    "between buyers and sellers within the AFL alliance.\n\n"
                    "AFL Wall Street is dedicated to providing a secure platform for kamas trading "
                    "among AFL members.\n\n"
                    "**Please provide the following information:**\n"
                    "• Amount of kamas you're buying/selling\n"
                    "• Your price per million kamas\n"
                    "• Select your currency (€ or $)\n"
                    "• Your preferred payment method\n"
                    "• Contact information"
                ),
                color=discord.Color.gold()
            )
            
            if kamas_logo:
                embed.set_thumbnail(url=KAMAS_LOGO_URL)
            
            embed.add_field(name="📈 Attractive Rates & Safe Transactions", value="\u200b", inline=False)
            embed.add_field(name="🔒 Secure & Private Communications", value="\u200b", inline=False)
            embed.add_field(name="👥 Trusted Intermediary Service", value="\u200b", inline=False)
            
            embed.add_field(
                name="How It Works",
                value=(
                    "1. Click one of the buttons below and fill out the form\n"
                    "2. Select your preferred currency (€ or $)\n"
                    "3. A listing will be created in our transactions channel\n"
                    "4. Interested parties can use the private discussion button\n"
                    "5. Complete your transaction safely through our secure system\n"
                    "6. Close the thread when your transaction is complete"
                ),
                inline=False
            )
            
            embed.set_footer(text="AFL Wall Street - Making transactions secure since Today we are just Testing this Idea")
            
            view = KamasView()
            
            if existing_message:
                await existing_message.edit(embed=embed, view=view)
                self.panel_message = existing_message
                logger.info(f"Updated existing kamas panel message: {existing_message.id}")
            else:
                self.panel_message = await panel_channel.send(embed=embed, view=view)
                with open(panel_file_path, "w") as f:
                    f.write(str(self.panel_message.id))
                logger.info(f"Created new kamas panel message: {self.panel_message.id}")
                
        except Exception as e:
            logger.exception(f"Error setting up kamas panel: {e}")
    
    @app_commands.command(name="wallstreet_reset", description="Reset the AFL Wall Street kamas trading panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_panel(self, interaction: discord.Interaction):
        try:
            panel_file_path = "kamas_panel_id.txt"
            if os.path.exists(panel_file_path):
                os.remove(panel_file_path)
            await self.setup_panel()
            await interaction.response.send_message("AFL Wall Street trading panel has been reset!", ephemeral=True)
        except Exception as e:
            logger.exception(f"Error resetting AFL Wall Street panel: {e}")
            await interaction.response.send_message("Error resetting the panel.", ephemeral=True)
