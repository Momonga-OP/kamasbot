import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import os
import logging

from utils.constants import VERIFIED_DATA_CHANNEL_ID, KAMAS_LOGO_URL, TICKET_CHANNEL_ID
from utils.utils import fetch_kamas_logo

logger = logging.getLogger(__name__)

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data using SHA-256."""
    import hashlib
    return hashlib.sha256(data.encode()).hexdigest()

class VerificationModal(ui.Modal, title="Seller Verification Application"):
    """Modal for seller verification submission."""
    
    phone_number = ui.TextInput(
        label="Phone Number",
        placeholder="Enter your phone number (e.g., +1234567890)",
        required=True,
        max_length=20
    )
    
    social_media_type = ui.TextInput(
        label="Social Media Platform",
        placeholder="Twitter, Instagram, or Facebook",
        required=True,
        max_length=20
    )
    
    social_media_handle = ui.TextInput(
        label="Social Media Handle/Username",
        placeholder="Your username/handle (without @)",
        required=True,
        max_length=100
    )
    
    trading_experience = ui.TextInput(
        label="Trading Experience",
        placeholder="How long have you been trading kamas?",
        required=True,
        max_length=200
    )
    
    additional_info = ui.TextInput(
        label="Additional Information",
        placeholder="Any additional info that helps verify your legitimacy",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not all([
                self.social_media_handle.value,
                self.social_media_type.value,
                len(self.additional_info.value) < 500
            ]):
                await interaction.response.send_message(
                    "Please fill all required fields and keep additional info under 500 characters.",
                    ephemeral=True
                )
                return
            
            platform = self.social_media_type.value.lower().strip()
            valid_platforms = ['twitter', 'instagram', 'facebook']
            
            if platform not in valid_platforms:
                await interaction.response.send_message(
                    "Please enter a valid social media platform: Twitter, Instagram, or Facebook",
                    ephemeral=True
                )
                return
            
            user_id = str(interaction.user.id)
            verification_entry = {
                'user_id': user_id,
                'username': interaction.user.display_name,
                'phone_hash': hash_sensitive_data(self.phone_number.value),
                'social_platform': platform.capitalize(),
                'social_handle': self.social_media_handle.value.strip(),
                'trading_experience': self.trading_experience.value,
                'additional_info': self.additional_info.value,
                'application_date': datetime.now().isoformat(),
                'verified': False,
                'verified_date': None,
                'verified_by': None
            }
            
            admin_embed = discord.Embed(
                title="🔍 New Seller Verification Application",
                description=f"**User:** {interaction.user.mention} ({interaction.user.display_name})",
                color=discord.Color.orange()
            )
            
            admin_embed.add_field(name="Social Media", value=f"{platform.capitalize()}: @{self.social_media_handle.value}", inline=True)
            admin_embed.add_field(name="Trading Experience", value=self.trading_experience.value, inline=False)
            
            if self.additional_info.value:
                admin_embed.add_field(name="Additional Info", value=self.additional_info.value, inline=False)
            
            admin_embed.add_field(name="Application ID", value=f"`{user_id}`", inline=False)
            admin_embed.set_footer(text=f"Applied on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            ticket_channel = interaction.client.get_channel(TICKET_CHANNEL_ID)
            if not ticket_channel:
                ticket_channel = await interaction.client.fetch_channel(TICKET_CHANNEL_ID)
            
            admin_view = VerificationAdminView(user_id)
            await ticket_channel.send(embed=admin_embed, view=admin_view)
            
            await interaction.response.send_message(
                "✅ **Verification Application Submitted!**\n\n"
                "Your application has been submitted for review. Our administrators will verify your information and get back to you soon.\n\n"
                "**What happens next:**\n"
                "• Admins will review your social media profile\n"
                "• Your phone number is securely hashed and stored\n"
                "• You'll be notified once verified\n"
                "• Verified sellers get a special badge on their listings\n\n"
                "*Please allow 24-48 hours for processing.*",
                ephemeral=True
            )
            
            logger.info(f"Verification application submitted by user {user_id}")
            
        except Exception as e:
            logger.exception(f"Error processing verification application: {e}")
            await interaction.response.send_message(
                "There was an error processing your application. Please try again later.",
                ephemeral=True
            )

class VerificationAdminView(ui.View):
    """Admin view for approving/rejecting verification applications."""
    
    def __init__(self, applicant_user_id):
        super().__init__(timeout=None)
        self.applicant_user_id = applicant_user_id
        
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can approve verifications.", ephemeral=True)
            return
        
        try:
            if await store_verification_data(interaction, self.applicant_user_id, {
                'user_id': self.applicant_user_id,
                'verified': True,
                'verified_date': datetime.now().isoformat(),
                'verified_by': str(interaction.user.id)
            }):
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.green()
                embed.title = "✅ Seller Verification APPROVED"
                embed.add_field(name="Approved By", value=interaction.user.mention, inline=True)
                embed.add_field(name="Approved On", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
                
                await interaction.response.edit_message(embed=embed, view=None)
                
                try:
                    applicant = await interaction.client.fetch_user(int(self.applicant_user_id))
                    await applicant.send(
                        "🎉 **Congratulations! You're now a Verified Seller!**\n\n"
                        "Your seller verification has been approved. You now have access to:\n"
                        "• ✅ Verified badge on all your listings\n"
                        "• 🏆 Enhanced trust and credibility\n"
                        "• 📈 Higher visibility in the marketplace\n\n"
                        "Thank you for helping make AFL Wall Street a safer trading environment!"
                    )
                except:
                    pass
            else:
                await interaction.response.send_message("Error storing verification data. Please try again.", ephemeral=True)
                
        except Exception as e:
            logger.exception(f"Error approving verification: {e}")
            await interaction.response.send_message("Error processing approval.", ephemeral=True)
    
    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can reject verifications.", ephemeral=True)
            return
        
        await interaction.response.send_modal(RejectionReasonModal(self.applicant_user_id))

class RejectionReasonModal(ui.Modal, title="Rejection Reason"):
    """Modal for providing rejection reason."""
    
    reason = ui.TextInput(
        label="Reason for Rejection",
        placeholder="Please provide a reason for rejecting this application",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    def __init__(self, applicant_user_id):
        super().__init__()
        self.applicant_user_id = applicant_user_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.title = "❌ Seller Verification REJECTED"
            embed.add_field(name="Rejected By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Rejection Reason", value=self.reason.value, inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            try:
                applicant = await interaction.client.fetch_user(int(self.applicant_user_id))
                await applicant.send(
                    "❌ **Seller Verification Application Rejected**\n\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    "You can reapply for verification once you've addressed the concerns mentioned above.\n"
                    "If you have questions, please contact an administrator."
                )
            except:
                pass
            
        except Exception as e:
            logger.exception(f"Error rejecting verification: {e}")
            await interaction.response.send_message("Error processing rejection.", ephemeral=True)
