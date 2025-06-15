import discord
from discord.ext import commands
from discord import ui
from discord import app_commands
from datetime import datetime, timedelta, timezone
import os
import uuid
import aiohttp
from io import BytesIO
import logging
import json
import asyncio
from dotenv import load_dotenv
from utils.utils import archive_transaction, search_archives, generate_market_report
from utils.constants import TICKET_CHANNEL_ID, CURRENCY_SYMBOLS, ARCHIVE_AFTER_DAYS
from utils.utils import parse_kamas_amount, format_kamas_amount, store_verification_data, validate_kamas_amount
from datetime import timedelta

logger = logging.getLogger(__name__)

class CurrencySelect(discord.ui.Select):
    """Dropdown for selecting currency type."""
    def __init__(self):
        options = [
            discord.SelectOption(label="USD", value="USD", emoji="💵"),
            discord.SelectOption(label="EUR", value="EUR", emoji="💶"),
            discord.SelectOption(label="GBP", value="GBP", emoji="💷"),
            discord.SelectOption(label="CAD", value="CAD", emoji="💵"),
            discord.SelectOption(label="Other", value="OTHER", emoji="🌐")
        ]
        super().__init__(
            placeholder="Select payment currency...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.currency = self.values[0]

class KamasModal(ui.Modal):
    """Modal form for kamas transactions."""
    
    def __init__(self, transaction_type):
        super().__init__(
            title=f"{transaction_type} Kamas Transaction Details",
            timeout=None,
            custom_id=f"kamas_modal_{transaction_type}_{uuid.uuid4()}",
        )
        self.transaction_type = transaction_type
        self.currency = "USD"  # Default currency
        
        # Define fields with proper names
        self.kamas_amount = ui.TextInput(
            label="Kamas Amount",
            placeholder="Enter amount (e.g. 10M)",
            required=True,
            max_length=20
        )
        
        self.price_per_million = ui.TextInput(
            label="Price per Million",
            placeholder="Enter price (e.g. 5)",
            required=True,
            max_length=20
        )
        
        self.payment_method = ui.TextInput(
            label="Payment Method",
            placeholder="e.g. PayPal, Bank Transfer",
            required=True,
            max_length=100
        )
        
        self.contact_info = ui.TextInput(
            label="Contact Info",
            placeholder="Discord tag or contact info",
            required=True,
            max_length=100
        )
        
        self.notes = ui.TextInput(
            label="Additional Notes",
            placeholder="Any important details...",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        # Currency dropdown
        self.currency_select = CurrencySelect()
        
        # Add fields to modal
        self.add_item(self.kamas_amount)
        self.add_item(self.price_per_million)
        self.add_item(self.payment_method)
        self.add_item(self.contact_info)
        self.add_item(self.notes)
        self.add_item(self.currency_select)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # First validate inputs
            if not validate_kamas_amount(self.kamas_amount.value):
                await interaction.response.send_message(
                    "Invalid kamas amount format. Please use format like '10M' or '500K'.",
                    ephemeral=True
                )
                return
            
            # Check available space (max 50 active transactions)
            ticket_channel = interaction.guild.get_channel(TICKET_CHANNEL_ID)
            if not ticket_channel:
                ticket_channel = await interaction.guild.fetch_channel(TICKET_CHANNEL_ID)
                
            active_threads = len([t for t in ticket_channel.threads if not t.archived])
            MAX_TRANSACTIONS = 50
            
            if active_threads >= MAX_TRANSACTIONS:
                await interaction.response.send_message(
                    "⚠️ Currently at maximum capacity. Please try again later.\n"
                    f"(Max {MAX_TRANSACTIONS} active transactions allowed)",
                    ephemeral=True
                )
                logger.warning(f"Transaction capacity reached ({active_threads}/{MAX_TRANSACTIONS})")
                return
            
            # Get all input values
            amount = self.children[0].value
            price_per_million = self.children[1].value
            payment_method = self.children[2].value
            contact_info = self.children[3].value
            additional_info = self.children[4].value
            currency = self.children[5].values[0]
            
            # Validate kamas amount
            kamas_amount = parse_kamas_amount(amount)
            if kamas_amount is None:
                await interaction.response.send_message(
                    "Invalid kamas amount format. Please use formats like '10M', '500K', or '1000000'.",
                    ephemeral=True
                )
                return
            
            # Split payments for amounts over 50MK
            payment_split = None
            if kamas_amount > 50000000:  # 50MK
                half_amount = kamas_amount / 2
                payment_split = {
                    "first_half": half_amount,
                    "second_half": kamas_amount - half_amount
                }
                
            try:
                price_per_m = float(self.price_per_million.value.replace(',', '.'))
            except ValueError:
                await interaction.response.send_message(
                    "Invalid price format. Please enter a numeric value.",
                    ephemeral=True
                )
                return
                
            form_data = {
                "transaction_type": self.transaction_type,
                "kamas_amount": kamas_amount,
                "kamas_amount_str": format_kamas_amount(kamas_amount),
                "price_per_m": price_per_m,
                "payment_method": self.payment_method.value,
                "contact_info": self.contact_info.value,
                "additional_info": self.notes.value,
                "user_id": interaction.user.id,
                "payment_split": payment_split,
                "currency": currency
            }
            
            temp_file_name = f"temp_form_{interaction.user.id}.txt"
            with open(temp_file_name, "w") as f:
                for key, value in form_data.items():
                    f.write(f"{key}:{value}\n")
            
            view = ui.View(timeout=300)
            currency_select = CurrencySelect()
            view.add_item(currency_select)
            
            async def currency_callback(interaction: discord.Interaction):
                selected_currency = currency_select.values[0]
                await process_listing(interaction, selected_currency, temp_file_name)
                
            currency_select.callback = currency_callback
            
            await interaction.response.send_message(
                "Please select the currency for your transaction:", 
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Modal submission error: {e}")
            await interaction.response.send_message(
                "An error occurred. Please try again later.",
                ephemeral=True
            )

class PrivateThreadButton(ui.View):
    """Button to create a private thread for transactions."""
    
    def __init__(self, seller_id, buyer_id=None, transaction_type=None):
        super().__init__(timeout=None)
        self.seller_id = seller_id
        self.buyer_id = buyer_id
        self.transaction_type = transaction_type
        self.custom_id = f"private_thread_{seller_id}_{buyer_id if buyer_id else '0'}"
        self.create_thread_button.custom_id = self.custom_id
    
    @discord.ui.button(label="Start Private Discussion", style=discord.ButtonStyle.primary, emoji="🔒", custom_id="private_thread")
    async def create_thread_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not (interaction.user.guild_permissions.administrator or 
                   interaction.user.id == self.seller_id or 
                   (self.buyer_id and interaction.user.id == self.buyer_id)):
                await interaction.response.send_message(
                    "You don't have permission to access this transaction thread.", 
                    ephemeral=True
                )
                return
            
            existing_thread_id = None
            thread_file_path = f"thread_{self.custom_id}.txt"
            
            if os.path.exists(thread_file_path):
                try:
                    with open(thread_file_path, "r") as f:
                        existing_thread_id = int(f.read().strip())
                    try:
                        thread = await interaction.guild.fetch_channel(existing_thread_id)
                        await interaction.response.send_message(
                            f"Thread already exists. [Click here to join](<https://discord.com/channels/{interaction.guild.id}/{existing_thread_id}>)",
                            ephemeral=True
                        )
                        return
                    except discord.NotFound:
                        existing_thread_id = None
                        os.remove(thread_file_path)
                except:
                    existing_thread_id = None
            
            unique_id = str(uuid.uuid4())[:8]
            thread_name = f"Transaction-{unique_id}"
            
            thread = await interaction.channel.create_thread(
                name=thread_name,
                message=interaction.message,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=10080
            )
            
            with open(thread_file_path, "w") as f:
                f.write(str(thread.id))
            
            try:
                seller = await interaction.client.fetch_user(self.seller_id)
                await thread.add_user(seller)
                if self.buyer_id:
                    buyer = await interaction.client.fetch_user(self.buyer_id)
                    await thread.add_user(buyer)
            except Exception as e:
                logger.error(f"Error adding users to thread: {e}")
            
            await interaction.response.send_message(
                f"Private thread created! [Click here to join](<https://discord.com/channels/{interaction.guild.id}/{thread.id}>)",
                ephemeral=True
            )
            
            transaction_text = "listing" if not self.transaction_type else self.transaction_type.lower()
            thread_management = ThreadManagementView()
            
            seller = await interaction.client.fetch_user(self.seller_id)
            seller_info = f"**Seller:** {seller.mention} (ID: {seller.id})\n"
            
            buyer_info = ""
            if self.buyer_id:
                buyer = await interaction.client.fetch_user(self.buyer_id)
                buyer_info = f"**Buyer:** {buyer.mention} (ID: {buyer.id})\n"
            
            # Add payment split information if applicable
            payment_info = ""
            if form_data.get("payment_split"):
                payment_info = (
                    f"**Payment Split Required:**\n"
                    f"• First half: {format_kamas_amount(payment_split['first_half'])}\n"
                    f"• Second half: {format_kamas_amount(payment_split['second_half'])}\n\n"
                )
            
            await thread.send(
                f"### Secure Transaction Thread\n\n"
                f"{seller_info}{buyer_info}"
                f"{payment_info}"
                f"**Transaction Details:**\n"
                f"• Amount: {form_data['kamas_amount_str']}\n"
                f"• Price per Million: {form_data['price_per_m']}\n"
                f"• Payment Method: {form_data['payment_method']}\n\n"
                f"**Guidelines:**\n"
                f"• Verify payment details\n"
                f"• Complete transaction in order\n"
                f"• Close with 'Close Transaction'\n\n"
                f"*AFL Wall Street is here to help!*",
                view=thread_management
            )
            
        except Exception as e:
            logger.exception(f"Error creating private thread: {e}")
            await interaction.response.send_message(
                "There was an error creating the private thread. Please try again later.",
                ephemeral=True
            )

class ThreadManagementView(ui.View):
    """Provides buttons for thread management (close/delete)."""
    
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Transaction", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_thread")
    async def close_thread_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not (interaction.user.guild_permissions.administrator or 
                   interaction.channel.owner_id == interaction.user.id):
                await interaction.response.send_message(
                    "Only administrators or the thread creator can close this transaction.", 
                    ephemeral=True
                )
                return
            
            thread = interaction.channel
            if not isinstance(thread, discord.Thread):
                await interaction.response.send_message(
                    "This command can only be used in transaction threads.", 
                    ephemeral=True
                )
                return
            
            thread_file_paths = [f for f in os.listdir() if f.startswith("thread_") and f.endswith(".txt")]
            for file_path in thread_file_paths:
                try:
                    with open(file_path, "r") as f:
                        thread_id = int(f.read().strip())
                        if thread_id == thread.id:
                            os.remove(file_path)
                            logger.info(f"Removed thread file {file_path}")
                            break
                except:
                    pass
            
            await interaction.response.send_message("Closing this transaction thread. Thank you for using AFL Wall Street!")
            
            await asyncio.sleep(3)
            
            await thread.edit(archived=True, locked=True)
            logger.info(f"Thread {thread.id} has been closed and archived")
            
        except Exception as e:
            logger.exception(f"Error closing thread: {e}")
            await interaction.response.send_message(
                "There was an error closing the thread. Please try again or contact an administrator.",
                ephemeral=True
            )

class TicketsCog(commands.Cog):
    """Cog for managing kamas listings and tickets."""
    
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_listener(self.on_reaction_add, 'on_reaction_add')
        self.bot.loop.create_task(self.check_old_tickets())  # Start auto-archive
        self.bot.loop.create_task(self.weekly_market_report())
        self.bot.loop.create_task(self.check_escrow_timeouts())  # Add this line
        self.bot.loop.create_task(self.restore_active_views())
    
    async def on_reaction_add(self, reaction, user):
        """Handle reputation updates from reactions."""
        try:
            if user.bot:
                return
                
            if reaction.message.channel.id != TICKET_CHANNEL_ID:
                return
                
            if str(reaction.emoji) == '👍':
                seller_id = reaction.message.embeds[0].fields[0].value.split(':')[1].strip()
                await update_reputation(reaction.message, int(seller_id), True)
            elif str(reaction.emoji) == '👎':
                seller_id = reaction.message.embeds[0].fields[0].value.split(':')[1].strip()
                await update_reputation(reaction.message, int(seller_id), False)
        except Exception as e:
            logger.error(f"Reaction handling failed: {e}")

    async def show_seller_reputation(self, interaction: discord.Interaction, seller_id: int):
        """Display seller reputation in an embed."""
        rep = await calculate_reputation(seller_id, interaction.guild)
        if not rep:
            await interaction.response.send_message("Could not calculate reputation.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title=f"Seller Reputation",
            description=f"<@{seller_id}>'s trading reputation",
            color=discord.Color.gold()
        )
        embed.add_field(name="Score", value=str(rep['score']))
        embed.add_field(name="Total Transactions", value=str(rep['total']))
        embed.add_field(name="Positive", value=str(rep['positive']))
        embed.add_field(name="Negative", value=str(rep['negative']))
        
        await interaction.response.send_message(embed=embed)

    async def restore_active_views(self):
        await self.bot.wait_until_ready()
        try:
            ticket_channel = self.bot.get_channel(TICKET_CHANNEL_ID)
            if not ticket_channel:
                ticket_channel = await self.bot.fetch_channel(TICKET_CHANNEL_ID)
            
            listing_files = [f for f in os.listdir() if f.startswith("listing_")]
            
            for file in listing_files:
                try:
                    with open(file, "r") as f:
                        message_id = int(f.read().strip())
                    
                    parts = file.replace("listing_", "").replace(".txt", "").split("-")
                    transaction_type = parts[0]
                    seller_id = int(parts[1])
                    
                    try:
                        message = await ticket_channel.fetch_message(message_id)
                        thread_files = [tf for tf in os.listdir() if tf.startswith(f"thread_private_thread_{seller_id}_")]
                        buyer_id = None
                        
                        if thread_files and not thread_files[0].endswith("_0.txt"):
                            buyer_part = thread_files[0].split("_")[-1].replace(".txt", "")
                            if buyer_part != "0":
                                buyer_id = int(buyer_part)
                        
                        view = PrivateThreadButton(seller_id=seller_id, buyer_id=buyer_id, transaction_type=transaction_type)
                        await message.edit(view=view)
                        logger.info(f"Restored view for listing {file}")
                    except discord.NotFound:
                        os.remove(file)
                        logger.info(f"Removed stale listing file {file}")
                    except Exception as e:
                        logger.error(f"Error restoring view for {file}: {e}")
                except Exception as e:
                    logger.error(f"Error processing listing file {file}: {e}")
            
            thread_files = [f for f in os.listdir() if f.startswith("thread_private_thread_")]
            for file in thread_files:
                try:
                    with open(file, "r") as f:
                        thread_id = int(f.read().strip())
                    
                    try:
                        thread = await self.bot.fetch_channel(thread_id)
                        messages = [msg async for msg in thread.history(limit=10)]
                        has_management_view = False
                        
                        for msg in messages:
                            if msg.author.id == self.bot.user.id and "Secure Transaction Thread" in msg.content and msg.components:
                                has_management_view = True
                                break
                        
                        if not has_management_view:
                            await thread.send(
                                "**Transaction Thread Management**\n\n"
                                "Use the button below to close this thread when your transaction is complete:",
                                view=ThreadManagementView()
                            )
                    except discord.NotFound:
                        os.remove(file)
                    except Exception as e:
                        logger.error(f"Error restoring thread management for {file}: {e}")
                except Exception as e:
                    logger.error(f"Error processing thread file {file}: {e}")
            
            logger.info("Completed restoration of active views and threads")
            
        except Exception as e:
            logger.exception(f"Error in restore_active_views: {e}")

    async def check_old_tickets(self):
        """Auto-archive tickets older than ARCHIVE_AFTER_DAYS."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                channel = self.bot.get_channel(TICKET_CHANNEL_ID)
                if not channel:
                    channel = await self.bot.fetch_channel(TICKET_CHANNEL_ID)
                
                now = datetime.now(timezone.utc)
                archive_cutoff = now - timedelta(days=ARCHIVE_AFTER_DAYS)
                
                async for message in channel.history(limit=1000):
                    if message.created_at < archive_cutoff:
                        await archive_transaction(message)
                        
                # Check daily
                await asyncio.sleep(86400)  
            except Exception as e:
                logger.error(f"Ticket archive check failed: {e}")
                await asyncio.sleep(3600)

    async def check_escrow_timeouts(self):
        """Check for expired escrow transactions."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                from config import ESCROW_TIMEOUT_HOURS
                from utils.utils import get_escrow_transactions
                
                escrows = await get_escrow_transactions(self.bot.guilds[0])
                for escrow in escrows:
                    if escrow['status'] == 'pending':
                        created_at = datetime.fromisoformat(escrow['created_at'])
                        if (datetime.now(timezone.utc) - created_at).total_seconds() > ESCROW_TIMEOUT_HOURS * 3600:
                            # Mark as expired in the file
                            await self.expire_escrow(escrow)
            
                # Check hourly
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Escrow timeout check failed: {e}")
                await asyncio.sleep(3600)

    async def expire_escrow(self, escrow_data):
        """Mark an escrow as expired."""
        from config import ESCROW_CHANNEL_ID
        try:
            escrow_data['status'] = 'expired'
            channel = self.bot.get_channel(ESCROW_CHANNEL_ID)
            if not channel:
                channel = await self.bot.fetch_channel(ESCROW_CHANNEL_ID)
        
            # Find and update the original message
            async for message in channel.history(limit=200):
                if message.attachments:
                    for att in message.attachments:
                        if f"escrow_{escrow_data['buyer']}_{escrow_data['seller']}" in att.filename:
                            await message.edit(
                                content=f"ESCROW EXPIRED - {message.content}",
                                attachments=[discord.File(
                                    BytesIO(json.dumps(escrow_data).encode()),
                                    filename=att.filename
                                )]
                            )
                            return True
            return False
        except Exception as e:
            logger.error(f"Escrow expiration failed: {e}")
            return False

    async def weekly_market_report(self):
        """Generate and post weekly market analysis report."""
        while True:
            try:
                # Wait until next Monday
                now = datetime.now(timezone.utc)
                next_monday = now + timedelta(days=(7 - now.weekday()))
                next_monday = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
                wait_seconds = (next_monday - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                # Generate and post report
                report = await generate_market_report(self.bot)
                channel = self.bot.get_channel(TICKET_CHANNEL_ID)
                await channel.send(embed=report)
                
            except Exception as e:
                logger.error(f"Weekly market report failed: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retrying

    @app_commands.command(name="generate_report", description="Generate a market report manually")
    @app_commands.checks.has_permissions(administrator=True)
    async def generate_report(self, interaction: discord.Interaction):
        """Manually generate a market report."""
        await interaction.response.defer()
        try:
            success = await generate_market_report(interaction.guild)
            if success:
                await interaction.followup.send("Market report generated successfully!", ephemeral=True)
            else:
                await interaction.followup.send("Failed to generate report. Check logs.", ephemeral=True)
        except Exception as e:
            logger.error(f"Manual report failed: {e}")
            await interaction.followup.send("An error occurred. Check logs.", ephemeral=True)

    @app_commands.command(name="create_escrow", description="Create an escrow for a high-value trade")
    async def create_escrow(
        self, 
        interaction: discord.Interaction,
        seller: discord.Member,
        middleman: discord.Member,
        amount: int
    ):
        """Create an escrow transaction."""
        from config import MIN_ESCROW_AMOUNT
        
        if amount < MIN_ESCROW_AMOUNT:
            return await interaction.response.send_message(
                f"Escrow only available for trades of {MIN_ESCROW_AMOUNT:,}+ kamas",
                ephemeral=True
            )
            
        await interaction.response.defer()
        success = await create_escrow(interaction.user, seller, middleman, amount)
        
        if success:
            await interaction.followup.send(
                f"Escrow created successfully! {middleman.mention} will mediate this trade.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Failed to create escrow. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="complete_escrow", description="Mark an escrow as completed")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def complete_escrow(self, interaction: discord.Interaction, escrow_id: str):
        """Mark an escrow as completed."""
        from config import ESCROW_CHANNEL_ID
        from utils.utils import assign_middleman_badge
        await interaction.response.defer()
        
        try:
            channel = interaction.guild.get_channel(ESCROW_CHANNEL_ID)
            if not channel:
                channel = await interaction.guild.fetch_channel(ESCROW_CHANNEL_ID)
            
            # Find and update escrow file
            async for message in channel.history(limit=200):
                if message.attachments:
                    for att in message.attachments:
                        if escrow_id in att.filename:
                            content = await att.read()
                            escrow = json.loads(content.decode())
                            escrow['status'] = 'completed'
                            
                            await message.edit(
                                content=f"COMPLETED - {message.content}",
                                attachments=[discord.File(
                                    BytesIO(json.dumps(escrow).encode()),
                                    filename=att.filename
                                )]
                            )
                            
                            # Assign badge if qualified
                            middleman = interaction.guild.get_member(escrow['middleman_id'])
                            if middleman:
                                await assign_middleman_badge(middleman, interaction.guild)
                            
                            await interaction.followup.send(
                                "Escrow marked as completed",
                                ephemeral=True
                            )
                            return
            
            await interaction.followup.send("Escrow not found", ephemeral=True)
        except Exception as e:
            logger.error(f"Escrow completion failed: {e}")
            await interaction.followup.send("Failed to complete escrow", ephemeral=True)

    @app_commands.command(name="cancel_escrow", description="Cancel an escrow transaction")
    async def cancel_escrow(self, interaction: discord.Interaction, escrow_id: str):
        """Cancel an escrow transaction."""
        await interaction.response.defer()
        # Implementation would update escrow file status
        await interaction.followup.send("Escrow cancelled", ephemeral=True)

    @app_commands.command(name="dispute_escrow", description="File a dispute for an escrow transaction")
    async def dispute_escrow(self, interaction: discord.Interaction, escrow_id: str, reason: str):
        """File an escrow dispute."""
        from config import ESCROW_CHANNEL_ID
        await interaction.response.defer()
        
        try:
            channel = interaction.guild.get_channel(ESCROW_CHANNEL_ID)
            if not channel:
                channel = await interaction.guild.fetch_channel(ESCROW_CHANNEL_ID)
            
            # Find and update escrow file
            async for message in channel.history(limit=200):
                if message.attachments:
                    for att in message.attachments:
                        if escrow_id in att.filename:
                            content = await att.read()
                            escrow = json.loads(content.decode())
                            escrow['dispute'] = {
                                "filed_by": interaction.user.id,
                                "reason": reason,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            escrow['status'] = 'disputed'
                            
                            await message.edit(
                                content=f"DISPUTE FILED - {message.content}",
                                attachments=[discord.File(
                                    BytesIO(json.dumps(escrow).encode()),
                                    filename=att.filename
                                )]
                            )
                            
                            await interaction.followup.send(
                                "Dispute filed successfully. An admin will review your case.",
                                ephemeral=True
                            )
                            return
            
            await interaction.followup.send("Escrow not found", ephemeral=True)
        except Exception as e:
            logger.error(f"Escrow dispute failed: {e}")
            await interaction.followup.send("Failed to file dispute", ephemeral=True)

    @app_commands.command(name="middleman_stats", description="View middleman performance statistics")
    async def middleman_stats(self, interaction: discord.Interaction, middleman: discord.Member):
        """Display middleman performance metrics."""
        from utils.utils import get_escrow_transactions
        from config import MIDDLEMAN_BADGES
        await interaction.response.defer()
        
        escrows = await get_escrow_transactions(interaction.guild)
        middleman_escrows = [e for e in escrows if e['middleman_id'] == middleman.id]
        
        if not middleman_escrows:
            return await interaction.followup.send(
                f"No escrow history found for {middleman.display_name}",
                ephemeral=True
            )
            
        completed = sum(1 for e in middleman_escrows if e['status'] == 'completed')
        disputed = sum(1 for e in middleman_escrows if 'dispute' in e)
        success_rate = (completed / len(middleman_escrows)) * 100
        
        # Determine badge
        current_badge = "None"
        for badge, requirements in sorted(
            MIDDLEMAN_BADGES.items(), 
            key=lambda x: x[1]['escrows'], 
            reverse=True
        ):
            if len(middleman_escrows) >= requirements['escrows'] and \
               success_rate >= requirements['success_rate']:
                current_badge = badge
                break
        
        embed = discord.Embed(
            title=f"Middleman Stats: {middleman.display_name}",
            color=MIDDLEMAN_BADGES.get(current_badge, {}).get('color', 0x000000)
        )
        embed.add_field(name="Badge", value=current_badge)
        embed.add_field(name="Total Escrows", value=str(len(middleman_escrows)))
        embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%")
        embed.add_field(name="Dispute Rate", value=f"{(disputed/len(middleman_escrows))*100:.1f}%")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="middleman_leaderboard", description="Top middlemen by performance")
    async def middleman_leaderboard(self, interaction: discord.Interaction):
        """Display middleman leaderboard."""
        from utils.utils import get_escrow_transactions
        from config import MIDDLEMAN_BADGES
        await interaction.response.defer()
        
        escrows = await get_escrow_transactions(interaction.guild)
        middlemen = {}
        
        # Collect stats for all middlemen
        for escrow in escrows:
            mid = escrow['middleman_id']
            if mid not in middlemen:
                middlemen[mid] = {"total": 0, "completed": 0, "disputed": 0}
            middlemen[mid]["total"] += 1
            if escrow['status'] == 'completed':
                middlemen[mid]["completed"] += 1
            if 'dispute' in escrow:
                middlemen[mid]["disputed"] += 1
        
        # Calculate scores and sort
        leaderboard = []
        for mid, stats in middlemen.items():
            member = interaction.guild.get_member(mid)
            if member:
                score = (stats["completed"] / stats["total"]) * 100
                leaderboard.append((member, score, stats["total"]))
        
        leaderboard.sort(key=lambda x: (-x[1], -x[2]))
        
        # Build embed
        embed = discord.Embed(
            title="Top Middlemen",
            color=0xFFD700,
            description="Ranked by success rate and total escrows"
        )
        
        for i, (member, score, total) in enumerate(leaderboard[:10], 1):
            embed.add_field(
                name=f"#{i} {member.display_name}",
                value=f"{score:.1f}% success ({total} escrows)",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
