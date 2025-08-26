from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = -1002015777041
CHAT_ID = -1002042675240
CHANNEL_INVITE = os.getenv("CHANNEL_INVITE")  # e.g., https://t.me/+abc123
CHAT_INVITE = os.getenv("CHAT_INVITE")       # e.g., https://t.me/+xyz456