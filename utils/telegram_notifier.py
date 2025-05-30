import aiohttp
import os
from dotenv import load_dotenv
import re

def escape_markdown(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Set environment to either "prod" or "dev"
ENVIRONMENT = "dev"  # change to "dev" during development

TELEGRAM_CHANNELS = {
    "prod_api": "-1002574866497",
    "dev_api": "-1002552699144",
    "prod_cron": "-1002665204199",
    "dev_cron": "-1002500338967",
    "customer_queries": "-1002607200395",
    "public_updates": "-1002590393922",  # MonkTrader.ai
}

ALLOWED_PUBLIC_MESSAGES = [
    "new_feature",
    "downtime_notice",
    "weekly_summary",
    "promotion",
]

IS_PROD = os.getenv("ENV", "dev") == "prod"
DEFAULT_CHANNEL_KEY = "prod_api" if IS_PROD else "dev_api"

async def notify_internal(message: str, parse_mode="Markdown"):
    formatted_message = escape_markdown(message)
    channel_id = TELEGRAM_CHANNELS.get(DEFAULT_CHANNEL_KEY)
    await _send_to_telegram(channel_id, formatted_message, parse_mode)

async def notify_public(message: str, message_type: str, parse_mode="Markdown"):
    if message_type not in ALLOWED_PUBLIC_MESSAGES:
        return
    channel_id = TELEGRAM_CHANNELS.get("public_updates")
    formatted_message = escape_markdown(message)
    await _send_to_telegram(channel_id, formatted_message, parse_mode)

async def _send_to_telegram(chat_id: str, message: str, parse_mode: str = "Markdown"):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": parse_mode}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=5) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[Telegram Error] Status {resp.status}: {error_text}")
    except Exception as e:
        print(f"[Telegram Error] Failed to send message: {e}")
