import logging
import aiohttp
import os
import re
import json
import time
from io import BytesIO
from datetime import datetime
from discord import utils

from config import (
    KAMAS_LOGO_URL, VERIFIED_DATA_CHANNEL_ID,
    REPUTATION_CHANNEL_ID, BADGES_CHANNEL_ID,
    ARCHIVE_CHANNEL_ID, BADGE_COLORS
)

logger = logging.getLogger(__name__)

# Rate limiting decorator
def rate_limited(window_seconds=60, max_requests=5):
    def decorator(func):
        calls = []
        
        @utils.wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [call for call in calls if call > now - window_seconds]
            
            if len(calls) >= max_requests:
                raise commands.CommandError(
                    f"Too many requests. Please wait {window_seconds} seconds."
                )
                
            calls.append(now)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Enhanced input validation
def validate_kamas_amount(amount_str):
    if not isinstance(amount_str, str):
        return False
        
    amount_str = amount_str.replace(" ", "").upper()
    pattern = r'^\d+(\.\d+)?[MK]?$'
    return bool(re.fullmatch(pattern, amount_str))

def parse_kamas_amount(amount_str):
    """Parse kamas amount from string format to numeric value."""
    if not validate_kamas_amount(amount_str):
        raise ValueError("Invalid kamas amount format")
        
    amount_str = amount_str.replace(" ", "").upper()
    try:
        if "M" in amount_str:
            return float(amount_str.replace("M", "").replace(",", ".")) * 1000000
        elif "K" in amount_str:
            return float(amount_str.replace("K", "").replace(",", ".")) * 1000
        else:
            return float(amount_str.replace(",", "."))
    except ValueError as e:
        logger.error(f"Kamas amount parsing failed: {e}")
        raise

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
            async with session.get(KAMAS_LOGO_URL) as response:
                if response.status == 200:
                    return BytesIO(await response.read())
                return None
    except Exception as e:
        logger.warning(f"Error fetching Kamas logo: {e}")
        return None

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data using SHA-256."""
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()

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

async def update_reputation(interaction: discord.Interaction, seller_id: int, positive: bool):
    """Update seller reputation using reaction-based tracking in a text file."""
    try:
        channel = interaction.client.get_channel(REPUTATION_CHANNEL_ID)
        if not channel:
            channel = await interaction.client.fetch_channel(REPUTATION_CHANNEL_ID)
        
        # Create/update reputation file
        filename = f"reputation_{seller_id}.txt"
        content = f"{datetime.now().isoformat()},{'positive' if positive else 'negative'}"
        
        await channel.send(
            f"Reputation update for <@{seller_id}>",
            file=discord.File(BytesIO(content.encode()), filename=filename)
        )
        return True
    except Exception as e:
        logger.error(f"Reputation update failed: {e}")
        return False

async def calculate_reputation(seller_id: int, guild: discord.Guild):
    """Calculate reputation score from stored files."""
    try:
        channel = guild.get_channel(REPUTATION_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(REPUTATION_CHANNEL_ID)
        
        positive = 0
        negative = 0
        
        async for message in channel.history(limit=1000):
            if message.attachments:
                for attachment in message.attachments:
                    if str(seller_id) in attachment.filename:
                        file_content = await attachment.read()
                        _, rep_type = file_content.decode().strip().split(',')
                        if rep_type == 'positive':
                            positive += 1
                        else:
                            negative += 1
        
        return {
            'score': positive - negative,
            'total': positive + negative,
            'positive': positive,
            'negative': negative
        }
    except Exception as e:
        logger.error(f"Reputation calculation failed: {e}")
        return None

async def update_seller_badges(user_id: int, guild: discord.Guild):
    """Update seller badges based on transaction count."""
    try:
        rep = await calculate_reputation(user_id, guild)
        if not rep:
            return
            
        member = await guild.fetch_member(user_id)
        if not member:
            return
            
        # Remove existing badge roles
        for role in member.roles:
            if role.name in ["Bronze Seller", "Silver Seller", "Gold Seller"]:
                await member.remove_roles(role)
        
        # Assign new badges
        if rep['positive'] >= 100:
            role = await get_or_create_role(guild, "Gold Seller", BADGE_COLORS["GOLD"])
        elif rep['positive'] >= 50:
            role = await get_or_create_role(guild, "Silver Seller", BADGE_COLORS["SILVER"])
        elif rep['positive'] >= 10:
            role = await get_or_create_role(guild, "Bronze Seller", BADGE_COLORS["BRONZE"])
        else:
            return
            
        await member.add_roles(role)
        return role.name
        
    except Exception as e:
        logger.error(f"Badge update failed: {e}")
        return None

async def get_or_create_role(guild, name, color):
    """Get or create a badge role."""
    role = discord.utils.get(guild.roles, name=name)
    if not role:
        role = await guild.create_role(name=name, color=discord.Color(color))
    return role

async def archive_transaction(message: discord.Message):
    """Move a transaction to the archive channel."""
    try:
        archive_channel = message.guild.get_channel(ARCHIVE_CHANNEL_ID)
        if not archive_channel:
            archive_channel = await message.guild.fetch_channel(ARCHIVE_CHANNEL_ID)
        
        # Create archive file
        content = f"Transaction from {message.created_at}\n"
        content += f"Original URL: {message.jump_url}\n\n"
        
        # Add embed data if exists
        if message.embeds:
            embed = message.embeds[0]
            content += f"Title: {embed.title}\n"
            content += f"Description: {embed.description}\n"
            for field in embed.fields:
                content += f"{field.name}: {field.value}\n"
        
        # Add attachments if any
        if message.attachments:
            content += "\nAttachments:\n"
            for att in message.attachments:
                content += f"- {att.filename}: {att.url}\n"
        
        # Send to archive
        filename = f"txn_{message.id}.txt"
        await archive_channel.send(
            f"Archived transaction from {message.author.mention}",
            file=discord.File(BytesIO(content.encode()), filename=filename)
        )
        
        # Delete original if successful
        await message.delete()
        return True
        
    except Exception as e:
        logger.error(f"Archive failed: {e}")
        return False

async def search_archives(guild: discord.Guild, query: str):
    """Search archived transactions."""
    try:
        channel = guild.get_channel(ARCHIVE_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(ARCHIVE_CHANNEL_ID)
        
        results = []
        async for message in channel.history(limit=1000):
            if message.attachments:
                for att in message.attachments:
                    if query.lower() in att.filename.lower():
                        results.append({
                            "url": message.jump_url,
                            "date": message.created_at,
                            "filename": att.filename
                        })
        return results
    except Exception as e:
        logger.error(f"Archive search failed: {e}")
        return []

async def collect_market_data(guild: discord.Guild):
    """Collect trading data from archive channel."""
    try:
        from config import ARCHIVE_CHANNEL_ID
        channel = guild.get_channel(ARCHIVE_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(ARCHIVE_CHANNEL_ID)
        
        data = {
            'total_transactions': 0,
            'total_kamas': 0,
            'payment_methods': {},
            'daily_volume': {},
            'seller_stats': {},
            'price_ranges': {},  # New: Track kamas price ranges
            'transaction_times': [],  # New: Track time of day
            'new_sellers': set()  # New: Track new sellers
        }
        
        # Get seller list from previous week for new seller detection
        prev_sellers = set()
        async for old_msg in channel.history(after=datetime.now()-timedelta(days=14), limit=500):
            if old_msg.attachments and old_msg.created_at < datetime.now()-timedelta(days=7):
                for att in old_msg.attachments:
                    if 'txn_' in att.filename:
                        prev_sellers.add(old_msg.author.id)
        
        async for message in channel.history(limit=1000):
            if message.attachments:
                data['total_transactions'] += 1
                data['transaction_times'].append(message.created_at.hour)
                
                # Parse transaction details from filename
                for att in message.attachments:
                    if 'txn_' in att.filename:
                        parts = att.filename.split('_')
                        if len(parts) >= 4:  # txn_ID_KAMAS_PAYMENTMETHOD
                            try:
                                kamas = int(parts[2])
                                method = parts[3].split('.')[0]
                                date = message.created_at.date()
                                
                                # Track price ranges
                                price_range = f"{(kamas // 1000) * 1000}-{(kamas // 1000 + 1) * 1000}"
                                data['price_ranges'][price_range] = data['price_ranges'].get(price_range, 0) + 1
                                
                                # Track new sellers
                                if message.author.id not in prev_sellers:
                                    data['new_sellers'].add(message.author.id)
                                
                                # Existing tracking
                                data['total_kamas'] += kamas
                                data['payment_methods'][method] = data['payment_methods'].get(method, 0) + 1
                                data['daily_volume'][str(date)] = data['daily_volume'].get(str(date), 0) + kamas
                                
                                seller = message.author.id
                                data['seller_stats'][seller] = data['seller_stats'].get(seller, {'count': 0, 'volume': 0})
                                data['seller_stats'][seller]['count'] += 1
                                data['seller_stats'][seller]['volume'] += kamas
                                
                            except (ValueError, IndexError):
                                continue
        
        # Calculate additional metrics
        data['avg_kamas_per_txn'] = data['total_kamas'] / data['total_transactions'] if data['total_transactions'] else 0
        data['busiest_hour'] = max(set(data['transaction_times']), key=data['transaction_times'].count) if data['transaction_times'] else None
        data['new_sellers_count'] = len(data['new_sellers'])
        
        return data
    except Exception as e:
        logger.error(f"Market data collection failed: {e}")
        return None

async def generate_market_report(guild: discord.Guild):
    """Generate weekly market report."""
    try:
        from config import STATS_CHANNEL_ID
        data = await collect_market_data(guild)
        if not data:
            return False
            
        # Generate report embed
        embed = discord.Embed(
            title="Weekly Market Report",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Main stats
        embed.add_field(
            name="Transaction Volume",
            value=f"{data['total_transactions']} transactions\n{data['total_kamas']:,} kamas total\nAvg: {data['avg_kamas_per_txn']:,.0f} kamas/txn",
            inline=False
        )
        
        # New sellers
        embed.add_field(
            name="New Sellers",
            value=f"{data['new_sellers_count']} new sellers this week",
            inline=True
        )
        
        # Busiest hour
        if data['busiest_hour']:
            embed.add_field(
                name="Peak Hours",
                value=f"{data['busiest_hour']}:00-{data['busiest_hour']+1}:00",
                inline=True
            )
        
        # Top payment methods
        top_methods = sorted(
            data['payment_methods'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        embed.add_field(
            name="Top Payment Methods",
            value="\n".join(f"{m}: {c}" for m, c in top_methods),
            inline=True
        )
        
        # Price ranges
        top_ranges = sorted(
            data['price_ranges'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        embed.add_field(
            name="Popular Price Ranges",
            value="\n".join(f"{r}: {c}" for r, c in top_ranges),
            inline=True
        )
        
        # Top sellers
        top_sellers = sorted(
            [(k, v['volume']) for k, v in data['seller_stats'].items()],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        embed.add_field(
            name="Top Sellers by Volume",
            value="\n".join(f"<@{s[0]}>: {s[1]:,} kamas" for s in top_sellers),
            inline=True
        )
        
        # Send to stats channel
        channel = guild.get_channel(STATS_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(STATS_CHANNEL_ID)
            
        await channel.send(embed=embed)
        return True
        
    except Exception as e:
        logger.error(f"Market report generation failed: {e}")
        return False

async def create_escrow(buyer: discord.Member, seller: discord.Member, middleman: discord.Member, amount: int):
    """Create an escrow transaction file."""
    try:
        from config import ESCROW_CHANNEL_ID, ESCROW_FEE_PERCENT
        fee = int(amount * (ESCROW_FEE_PERCENT / 100))
        
        escrow_data = {
            "buyer": buyer.id,
            "seller": seller.id,
            "middleman": middleman.id,
            "amount": amount,
            "fee": fee,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Store in escrow channel
        channel = buyer.guild.get_channel(ESCROW_CHANNEL_ID)
        if not channel:
            channel = await buyer.guild.fetch_channel(ESCROW_CHANNEL_ID)
            
        filename = f"escrow_{buyer.id}_{seller.id}_{int(datetime.now().timestamp())}.json"
        await channel.send(
            f"New escrow created for {amount} kamas",
            file=discord.File(BytesIO(json.dumps(escrow_data).encode()), filename=filename)
        )
        
        return True
    except Exception as e:
        logger.error(f"Escrow creation failed: {e}")
        return False

async def get_escrow_transactions(guild: discord.Guild):
    """Retrieve all active escrow transactions."""
    try:
        from config import ESCROW_CHANNEL_ID
        channel = guild.get_channel(ESCROW_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(ESCROW_CHANNEL_ID)
            
        escrows = []
        async for message in channel.history(limit=200):
            if message.attachments:
                for att in message.attachments:
                    if att.filename.startswith('escrow_'):
                        content = await att.read()
                        escrows.append(json.loads(content.decode()))
        return escrows
    except Exception as e:
        logger.error(f"Escrow retrieval failed: {e}")
        return []

async def load_translations(guild: discord.Guild):
    """Load all translations from the translations channel."""
    try:
        from config import TRANSLATIONS_CHANNEL_ID
        channel = guild.get_channel(TRANSLATIONS_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(TRANSLATIONS_CHANNEL_ID)
        
        translations = {}
        async for message in channel.history(limit=200):
            if message.attachments and message.attachments[0].filename.endswith('.json'):
                lang = message.attachments[0].filename.split('.')[0]
                content = await message.attachments[0].read()
                translations[lang] = json.loads(content.decode())
        
        return translations
    except Exception as e:
        logger.error(f"Translation loading failed: {e}")
        return {}

async def set_user_language(user_id: int, language: str, guild: discord.Guild):
    """Store a user's language preference."""
    try:
        from config import VERIFIED_DATA_CHANNEL_ID, SUPPORTED_LANGUAGES
        
        if language not in SUPPORTED_LANGUAGES:
            return False
            
        channel = guild.get_channel(VERIFIED_DATA_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(VERIFIED_DATA_CHANNEL_ID)
            
        # Create/update language file
        filename = f"lang_{user_id}.txt"
        content = language
        
        # Check if existing file exists
        async for message in channel.history(limit=200):
            if message.attachments and message.attachments[0].filename == filename:
                await message.edit(
                    attachments=[discord.File(BytesIO(content.encode()), filename=filename)]
                )
                return True
        
        # Create new if not exists
        await channel.send(
            file=discord.File(BytesIO(content.encode()), filename=filename)
        )
        return True
        
    except Exception as e:
        logger.error(f"Language setting failed: {e}")
        return False

async def get_user_language(user_id: int, guild: discord.Guild):
    """Get a user's preferred language."""
    try:
        from config import VERIFIED_DATA_CHANNEL_ID
        channel = guild.get_channel(VERIFIED_DATA_CHANNEL_ID)
        if not channel:
            channel = await guild.fetch_channel(VERIFIED_DATA_CHANNEL_ID)
            
        filename = f"lang_{user_id}.txt"
        async for message in channel.history(limit=200):
            if message.attachments and message.attachments[0].filename == filename:
                content = await message.attachments[0].read()
                return content.decode().strip()
        
        return 'en'  # Default to English
    except Exception as e:
        logger.error(f"Language retrieval failed: {e}")
        return 'en'

async def translate(key: str, guild: discord.Guild, user_id: int = None, **kwargs):
    """Get a translated string."""
    try:
        lang = await get_user_language(user_id, guild) if user_id else 'en'
        translations = await load_translations(guild)
        
        # Fallback chain: user lang -> English -> key itself
        for try_lang in [lang, 'en']:
            if try_lang in translations and key in translations[try_lang]:
                return translations[try_lang][key].format(**kwargs)
        
        return key
    except Exception as e:
        logger.error(f"Translation failed for key {key}: {e}")
        return key

async def assign_middleman_badge(member: discord.Member, guild: discord.Guild):
    """Assign appropriate middleman badge role."""
    from config import MIDDLEMAN_BADGES
    escrows = await get_escrow_transactions(guild)
    user_escrows = [e for e in escrows if e['middleman'] == member.id]
    
    if not user_escrows:
        return False
        
    completed = sum(1 for e in user_escrows if e['status'] == 'completed')
    success_rate = (completed / len(user_escrows)) * 100
    
    # Remove all existing middleman badge roles
    for role in member.roles:
        if role.name in MIDDLEMAN_BADGES:
            await member.remove_roles(role)
    
    # Assign new badge if qualified
    for badge, requirements in sorted(
        MIDDLEMAN_BADGES.items(), 
        key=lambda x: x[1]['escrows'], 
        reverse=True
    ):
        if len(user_escrows) >= requirements['escrows'] and \
           success_rate >= requirements['success_rate']:
            role = discord.utils.get(guild.roles, name=badge)
            if not role:
                role = await guild.create_role(
                    name=badge,
                    color=discord.Color(requirements['color']),
                    hoist=True
                )
            await member.add_roles(role)
            return True
    
    return False
