import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import os
import uuid
import aiohttp
from io import BytesIO
import logging

from ..utils.constants import TICKET_CHANNEL_ID
from ..utils.utils import *

logger = logging.getLogger(__name__)

class KamasModal(ui.Modal, title="Kamas Transaction Details"):
    """Modal form for kamas transactions."""
    
    amount = ui.TextInput(
        label="Kamas Amount",
        placeholder="Enter amount (e.g. 10M)",
        required=True,
        max_length=20
    )
    
    price = ui.TextInput(
        label="Price per Million",
        placeholder="Enter price (e.g. 5)",
        required=True,
        max_length=20
    )
    
    payment_method = ui.TextInput(
        label="Payment Method",
        placeholder="e.g. PayPal, Bank Transfer",
        required=True,
        max_length=100
    )
    
    contact = ui.TextInput(
        label="Contact Info",
        placeholder="Discord tag or contact info",
        required=True,
        max_length=100
    )
    
    notes = ui.TextInput(
        label="Additional Notes",
        placeholder="Any important details...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    def __init__(self, transaction_type):
        super().__init__()
        self.transaction_type = transaction_type
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            kamas_amount = parse_kamas_amount(self.amount.value)
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
                "additional_info": self.additional_info.value,
                "user_id": interaction.user.id,
                "payment_split": payment_split
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
            logger.exception(f"Error processing kamas form: {e}")
            await interaction.response.send_message(
                "There was an error processing your listing. Please try again later.",
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
        self.bot.loop.create_task(self.restore_active_views())
    
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
