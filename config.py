import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

api_id  = int(getenv("API_ID"))
api_hash = getenv("API_HASH")
bot_token = getenv("BOT_TOKEN")
MONGO_URI = getenv("MONGO_URI", None)
db = getenv("DATABASE_NAME")
messages_collection = db["messages"]
chats_collection = db["chats"]
SUDOERS = int(getenv("SUDOERS"))
