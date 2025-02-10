from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient

# Bot configuration
API_ID = "24428727"
API_HASH = "1089a994258b8d77f06a2be5b1a01a31"
BOT_TOKEN = "6520550784:AAHZPv8eOS2Unc91jIVYSH5PB0z8SO36lUY"
MONGO_URI = "mongodb+srv://bot:bot@cluster0.8vepzds.mongodb.net/?retryWrites=true&w=majority"  # Replace with your MongoDB URI

# Initialize bot and database
app = Client("anon_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["anon_bot_db"]
chats_collection = db["chats"]
messages_collection = db["messages"]

# Connect command (group only, admin only)
@app.on_message(filters.command("connect") & filters.group)
async def connect_group(client, message: Message):
    admin_id = message.from_user.id
    chat_id = message.chat.id

    if chats_collection.find_one({"chat_id": chat_id}):
        await message.reply_text("This group is already connected!")
        return

    chats_collection.insert_one({"chat_id": chat_id, "admin_id": admin_id})
    await message.reply_text("Group successfully connected!")

# Show connected chats in PM
@app.on_message(filters.command("chats") & filters.private)
async def show_chats(client, message: Message):
    user_id = message.from_user.id
    chats = list(chats_collection.find({"admin_id": user_id}))

    if not chats:
        await message.reply_text("No connected groups found!")
        return

    buttons = [[InlineKeyboardButton(str(chat["chat_id"]), callback_data=f"chat_{chat['chat_id']}")] for chat in chats]
    await message.reply_text("Select a connected chat:", reply_markup=InlineKeyboardMarkup(buttons))

# Handle chat selection
@app.on_callback_query(filters.regex("^chat_"))
async def chat_options(client, query):
    chat_id = query.data.split("_")[1]
    buttons = [
        [InlineKeyboardButton("Send an Anonymous Message", callback_data=f"send_{chat_id}")],
        [InlineKeyboardButton("Remove Chat", callback_data=f"remove_{chat_id}")]
    ]
    await query.message.edit_text("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))

# Remove chat
@app.on_callback_query(filters.regex("^remove_"))
async def remove_chat(client, query):
    chat_id = query.data.split("_")[1]
    chats_collection.delete_one({"chat_id": int(chat_id)})
    await query.message.edit_text("Chat removed successfully!")

# Start anonymous message process
@app.on_callback_query(filters.regex("^send_"))
async def start_anon_message(client, query):
    chat_id = int(query.data.split("_")[1])
    messages_collection.delete_one({"user_id": query.from_user.id})
    messages_collection.insert_one({"user_id": query.from_user.id, "chat_id": chat_id, "image": None, "caption": None, "buttons": []})

    buttons = [
        [InlineKeyboardButton("Add Image", callback_data="add_image"),
         InlineKeyboardButton("Add Caption", callback_data="add_caption")],
        [InlineKeyboardButton("Add URL Button", callback_data="add_button"),
         InlineKeyboardButton("Preview", callback_data="preview")],
        [InlineKeyboardButton("Send", callback_data="send_final")]
    ]
    await query.message.edit_text("Editing anonymous message:", reply_markup=InlineKeyboardMarkup(buttons))

# Add image
@app.on_callback_query(filters.regex("^add_image"))
def ask_image(client, query):
    query.message.reply_text("Send the image now.")
    app.listen(query.message.chat.id, filters.photo, process_image)

async def process_image(client, message):
    user_id = message.from_user.id
    file_id = message.photo.file_id
    messages_collection.update_one({"user_id": user_id}, {"$set": {"image": file_id}})
    await message.reply_text("Image added successfully!")

# Add caption
@app.on_callback_query(filters.regex("^add_caption"))
async def ask_caption(client, query):
    await query.message.reply_text("Send the caption now.")
    app.listen(query.message.chat.id, filters.text, process_caption)

async def process_caption(client, message):
    user_id = message.from_user.id
    caption = message.text
    messages_collection.update_one({"user_id": user_id}, {"$set": {"caption": caption}})
    await message.reply_text("Caption added successfully!")

# Add button
@app.on_callback_query(filters.regex("^add_button"))
async def ask_button(client, query):
    await query.message.reply_text("Send button in the format: Button Name - URL")
    app.listen(query.message.chat.id, filters.text, process_button)

async def process_button(client, message):
    user_id = message.from_user.id
    try:
        name, url = message.text.split(" - ")
        messages_collection.update_one({"user_id": user_id}, {"$push": {"buttons": {"name": name, "url": url}}})
        await message.reply_text("Button added successfully!")
    except ValueError:
        await message.reply_text("Invalid format! Use: Button Name - URL")

# Preview message
@app.on_callback_query(filters.regex("^preview"))
async def preview_message(client, query):
    user_id = query.from_user.id
    msg_data = messages_collection.find_one({"user_id": user_id})

    buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if msg_data["image"]:  # Image exists
        await query.message.reply_photo(photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
    else:
        await query.message.reply_text(text=msg_data["caption"] or "No caption", reply_markup=markup)

# Send final message
@app.on_callback_query(filters.regex("^send_final"))
async def send_final_message(client, query):
    user_id = query.from_user.id
    msg_data = messages_collection.find_one({"user_id": user_id})

    chat_id = msg_data["chat_id"]
    buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if msg_data["image"]:  # Image exists
        await app.send_photo(chat_id, photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
    else:
        await app.send_message(chat_id, text=msg_data["caption"] or "No caption", reply_markup=markup)

    await query.message.reply_text("Message sent successfully!")
    messages_collection.delete_one({"user_id": user_id})

app.run()
