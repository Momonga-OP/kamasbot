import logging
from datetime import datetime
import os
import aiohttp
from io import BytesIO
import re
from discord import utils

logger = logging.getLogger(__name__)

def parse_kamas_amount(amount_str):
    """Parse kamas amount from string format to numeric value."""
    amount_str = amount_str.replace(" ", "").upper()
    if "M" in amount_str:
        try:
            num_part = amount_str.replace("M", "")
            num_part = num_part.replace(",", ".")
            return float(num_part) * 1000000
        except ValueError:
            return None
    elif "K" in amount_str:
        try:
            num_part = amount_str.replace("K", "")
            num_part = num_part.replace(",", ".")
            return float(num_part) * 1000
        except ValueError:
            return None
    else:
        try:
            return float(amount_str.replace(",", "."))
        except ValueError:
            return None

def format_kamas_amount(amount_num):
    """Format numeric kamas amount to string representation."""
    if amount_num >= 1000000:
        if amount_num % 1000000 == 0:
            return f"{int(amount_num / 1000000)}M"
        else:
            return f"{amount_num / 1000000:.2f}M"
    elif amount_num >= 1000:
        if amount_num % 1000 == 0:
            return f"{int(amount_num / 1000)}K"
        else:
            return f"{amount_num / 1000:.2f}K"
    else:
        return str(int(amount_num) if amount_num.is_integer() else amount_num)

async def fetch_kamas_logo():
    """Fetch the kamas logo from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(KAMAS_LOGO_URL) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logger.warning(f"Could not fetch Kamas logo: {e}")
    return None

async def store_verification_data(interaction, user_id, verification_data):
    """Store verification data in the verified sellers channel."""
    try:
        channel = interaction.client.get_channel(VERIFIED_DATA_CHANNEL_ID)
        if not channel:
            channel = await interaction.client.fetch_channel(VERIFIED_DATA_CHANNEL_ID)
            
        file_content = f"""Verified Seller Information:
User ID: {user_id}
Username: {verification_data['username']}
Social Platform: {verification_data['social_platform']}
Social Handle: {verification_data['social_handle']}
Trading Experience: {verification_data['trading_experience']}
Additional Info: {verification_data['additional_info']}
Application Date: {verification_data['application_date']}
Verified Date: {verification_data['verified_date']}
Verified By: {verification_data['verified_by']}"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"verified_seller_{user_id}_{timestamp}.txt"
        
        await channel.send(
            f"New verified seller: <@{user_id}>",
            file=discord.File(BytesIO(file_content.encode()), filename=filename)
        )
        
        guild = interaction.guild
        verified_role = await get_verified_role(guild)
        member = await guild.fetch_member(int(user_id))
        if member:
            await member.add_roles(verified_role)
            
        return True
        
    except Exception as e:
        logger.exception(f"Error storing verification data: {e}")
        return False

async def get_verified_role(guild):
    """Get or create the verified seller role."""
    verified_role = discord.utils.get(guild.roles, name="Verified Seller")
    if not verified_role:
        verified_role = await guild.create_role(
            name="Verified Seller",
            color=discord.Color.gold(),
            mentionable=True
        )
    return verified_role

async def is_verified_seller(user_id, guild):
    """Check if a user is a verified seller."""
    verified_role = discord.utils.get(guild.roles, name="Verified Seller")
    if not verified_role:
        return False
    
    member = await guild.fetch_member(int(user_id))
    if not member:
        return False
    
    return verified_role in member.roles

async def get_seller_profile(user_id, guild):
    """Get seller profile data from Discord channel."""
    try:
        channel = guild.get_channel(VERIFIED_DATA_CHANNEL_ID)
        if not channel:
            return {}
            
        async for message in channel.history(limit=1000):
            if message.attachments:
                for attachment in message.attachments:
                    if str(attachment.id) == str(user_id):
                        file_content = await attachment.read()
                        text = file_content.decode('utf-8')
                        profile = {}
                        lines = text.split('\n')
                        for line in lines:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                profile[key.strip()] = value.strip()
                        return profile
        return {}
    except Exception as e:
        logger.exception(f"Error getting seller profile: {e}")
        return {}
