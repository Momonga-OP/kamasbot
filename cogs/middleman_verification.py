"""Middleman verification system for the Kamas bot."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import asyncio
from io import BytesIO
from datetime import datetime

from utils.utils import get_escrow_transactions, assign_middleman_badge
from config import (
    MIDDLEMAN_APPLICATION_CHANNEL_ID,
    MIN_ESCROWS_FOR_APPLICATION,
    MIN_SUCCESS_RATE_FOR_APPLICATION,
    VERIFICATION_INTERVIEW_CHANNEL_ID,
    MIDDLEMAN_BADGES,
    MIDDLEMAN_REMINDERS_CHANNEL_ID,
    GUIDELINE_REMINDER_FREQ_DAYS
)

logger = logging.getLogger(__name__)

class MiddlemanVerificationCog(commands.Cog):
    """Handles middleman verification and applications."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.send_guideline_reminders())

    async def send_guideline_reminders(self):
        """Send weekly guideline reminders to middlemen."""
        await self.bot.wait_until_ready()
        
        from config import MIDDLEMAN_REMINDERS_CHANNEL_ID, GUIDELINE_REMINDER_FREQ_DAYS
        
        while not self.bot.is_closed():
            try:
                try:
                    channel = self.bot.get_channel(MIDDLEMAN_REMINDERS_CHANNEL_ID)
                    if not channel:
                        channel = await self.bot.fetch_channel(MIDDLEMAN_REMINDERS_CHANNEL_ID)
                    if channel is None:
                        raise ValueError("Middleman reminders channel not found")
                except Exception as e:
                    logger.error(f"Failed to fetch middleman reminders channel: {e}")
                    await asyncio.sleep(3600)
                    continue
                
                reminder = (
                    "🔔 **Weekly Middleman Reminder** 🔔\n\n"
                    "Please review our guidelines:\n"
                    "1. Always verify both parties\n"
                    "2. Document every step\n"
                    "3. Escalate disputes promptly\n"
                    "4. Maintain professional conduct\n\n"
                    "See #middleman-guidelines for details"
                )
                
                await channel.send(reminder)
                await asyncio.sleep(GUIDELINE_REMINDER_FREQ_DAYS * 86400)
            except Exception as e:
                logger.error(f"Guideline reminder failed: {e}")
                await asyncio.sleep(3600)  # Retry after 1 hour on error

    @app_commands.command(name="apply_middleman", description="Apply to become a verified middleman")
    async def apply_middleman(self, interaction: discord.Interaction):
        """Handle middleman applications."""
        from utils.utils import get_escrow_transactions
        await interaction.response.defer(ephemeral=True)
        
        # Check qualifications
        escrows = await get_escrow_transactions(interaction.guild)
        user_escrows = [e for e in escrows if e['middleman_id'] == interaction.user.id]
        
        if not user_escrows:
            return await interaction.followup.send(
                "You need experience as a middleman to apply. Ask to be assigned as a middleman in some escrows first.",
                ephemeral=True
            )
            
        completed = sum(1 for e in user_escrows if e['status'] == 'completed')
        success_rate = (completed / len(user_escrows)) * 100
        
        if len(user_escrows) < MIN_ESCROWS_FOR_APPLICATION or \
           success_rate < MIN_SUCCESS_RATE_FOR_APPLICATION:
            return await interaction.followup.send(
                f"Requirements: {MIN_ESCROWS_FOR_APPLICATION}+ escrows with {MIN_SUCCESS_RATE_FOR_APPLICATION}%+ success rate\n"
                f"Your stats: {len(user_escrows)} escrows, {success_rate:.1f}% success rate",
                ephemeral=True
            )
        
        # Create application
        channel = interaction.guild.get_channel(MIDDLEMAN_APPLICATION_CHANNEL_ID)
        if not channel:
            channel = await interaction.guild.fetch_channel(MIDDLEMAN_APPLICATION_CHANNEL_ID)
        
        embed = discord.Embed(
            title=f"Middleman Application: {interaction.user.display_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Escrows Completed", value=str(len(user_escrows)))
        embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="View Profile",
            url=f"https://discordapp.com/users/{interaction.user.id}"
        ))
        
        await channel.send(
            content=f"Middleman application from {interaction.user.mention}",
            embed=embed,
            view=view
        )
        
        await interaction.followup.send(
            "Your application has been submitted! A moderator will review it soon.",
            ephemeral=True
        )

async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(MiddlemanVerificationCog(bot))
