"""Configuration file for the Kamas bot."""

# Channel IDs
PANEL_CHANNEL_ID = 1383214622290481252
TICKET_CHANNEL_ID = 1383214670348943470
VERIFIED_DATA_CHANNEL_ID = 1383214781162459256
REPUTATION_CHANNEL_ID = 1383214819158786108  # Example ID
BADGES_CHANNEL_ID = 1383214869926383696       # Example ID
ARCHIVE_CHANNEL_ID = 1383214911378690210      # Example ID
STATS_CHANNEL_ID = 1383214960766619789        # Example ID
SERVER_ID = 1217700740949348443

# Security Settings
RATE_LIMIT_WINDOW = 60  # Seconds
RATE_LIMIT_MAX = 5      # Max requests per window

# Badge Thresholds
BADGE_THRESHOLDS = {
    "BRONZE": 10,   # Min 10 positive transactions
    "SILVER": 30,
    "GOLD": 50
}

# Badge Colors
BADGE_COLORS = {
    "BRONZE": 0xcd7f32,
    "SILVER": 0xc0c0c0,
    "GOLD": 0xffd700
}

# Archive Settings
ARCHIVE_AFTER_DAYS = 7  # Auto-archive transactions after this period

# Escrow Settings
ESCROW_CHANNEL_ID = 1383215018455207987  # Example ID - replace with your channel
ESCROW_FEE_PERCENT = 1.0  # 1% fee for escrow services
ESCROW_TIMEOUT_HOURS = 72  # 3 days timeout
MIN_ESCROW_AMOUNT = 10000  # Minimum kamas amount for escrow

# Language Settings
TRANSLATIONS_CHANNEL_ID = 1383215130346786966  # Example ID - replace with your channel
SUPPORTED_LANGUAGES = ['en', 'fr', 'es']  # English, French, Spanish
