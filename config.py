import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

api_id  = int(getenv("API_ID"))
api_hash = getenv("API_HASH")
bot_token = getenv("BOT_TOKEN")
MONGO_URI = getenv("MONGO_URI", None)
DATABASE_NAME = getenv("DATABASE_NAME")
chats_collection = getenv("COLLECTION_NAME")
messages_collection = getenv("MESSAGE_COLLECTION")
SUDOERS = int(getenv("SUDOERS"))
