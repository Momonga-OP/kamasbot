import os
from dotenv import load_dotenv

load_dotenv()

# Channel IDs
PANEL_CHANNEL_ID = int(os.getenv('PANEL_CHANNEL_ID'))
TICKET_CHANNEL_ID = int(os.getenv('TICKET_CHANNEL_ID'))
VERIFIED_DATA_CHANNEL_ID = int(os.getenv('VERIFIED_DATA_CHANNEL_ID'))
SERVER_ID = int(os.getenv('SERVER_ID'))

# Kamas logo URL
KAMAS_LOGO_URL = "https://static.wikia.nocookie.net/dofus/images/1/1e/Kama.png"

# Currency symbols
CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$"
}
