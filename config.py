import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMPLOYER_EMAIL = os.getenv("EMPLOYER_EMAIL", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Denver")
MYSQL_URL = os.getenv("MYSQL_URL", "")
