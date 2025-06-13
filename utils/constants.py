"""Constants that reference configuration values and Discord IDs"""

# Discord server and channel IDs
SERVER_ID = 1217700740949348443  # Discord server ID
PANEL_CHANNEL_ID = 1383214622290481252  # Main trading panel channel
TICKET_CHANNEL_ID = 1383214670348943470  # Channel for creating tickets
TICKETS_CATEGORY_ID = 1358383554798817410  # Category for ticket channels
VERIFIED_DATA_CHANNEL_ID = 1383214781162459256  # Channel for storing verification data
REPUTATION_CHANNEL_ID = 1383214819158786108  # Channel for reputation tracking
BADGES_CHANNEL_ID = 1383214869926383696  # Channel for badge assignments
ARCHIVE_CHANNEL_ID = 1383214911378690210  # Channel for archiving transactions

# URLs
KAMAS_LOGO_URL = "https://static.wikia.nocookie.net/dofus/images/1/1e/Kama.png"

# Badge thresholds and colors
BADGE_THRESHOLDS = {
    "BRONZE": 10,
    "SILVER": 50,
    "GOLD": 100
}

BADGE_COLORS = {
    "BRONZE": 0xcd7f32,
    "SILVER": 0xc0c0c0,
    "GOLD": 0xffd700
}

# Other constants
ARCHIVE_AFTER_DAYS = 30  # Days before archiving transactions
CURRENCY_SYMBOLS = ["k", "m", "b"]  # Kamas amount symbols
