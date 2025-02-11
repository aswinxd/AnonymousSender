from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
import asyncio
from bson.objectid import ObjectId
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

@app.on_message(filters.command("chats") & filters.private)
async def show_chats(client, message: Message):
    user_id = message.from_user.id
    chats = list(chats_collection.find({"admin_id": user_id}))

    if not chats:
        await message.reply_text("No connected groups found!")
        return

    buttons = [[InlineKeyboardButton(str(chat["chat_id"]), callback_data=f"chat_{chat['chat_id']}")] for chat in chats]
    await message.reply_text("Select a connected chat:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^chat_"))
async def chat_options(client, query):
    chat_id = query.data.split("_")[1]
    buttons = [
        [InlineKeyboardButton("Send an Anonymous Message", callback_data=f"send_{chat_id}")],
        [InlineKeyboardButton("Remove Chat", callback_data=f"remove_{chat_id}")]
    ]
    await query.message.edit_text("Choose an action:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^remove_"))
async def remove_chat(client, query):
    chat_id = query.data.split("_")[1]
    chats_collection.delete_one({"chat_id": int(chat_id)})
    await query.message.edit_text("Chat removed successfully!")

@app.on_callback_query(filters.regex("^send_"))
async def start_anon_message(client, query):
    chat_id = int(query.data.split("_")[1])
    messages_collection.delete_one({"user_id": query.from_user.id})
    messages_collection.insert_one({"user_id": query.from_user.id, "chat_id": chat_id, "image": None, "caption": None, "buttons": [], "saved_name": None})

    buttons = [
        [InlineKeyboardButton("Add Image", callback_data="add_image"),
         InlineKeyboardButton("Add Caption", callback_data="add_caption")],
        [InlineKeyboardButton("Add URL Button", callback_data="add_button"),
         InlineKeyboardButton("Preview", callback_data="preview")],
        [InlineKeyboardButton("Save", callback_data="save_message"),
         InlineKeyboardButton("Send", callback_data="send_final")]
    ]
    await query.message.edit_text("Editing anonymous message:", reply_markup=InlineKeyboardMarkup(buttons))

# Save Message
@app.on_callback_query(filters.regex("^save_message"))
async def ask_save_name(client, query):
    await query.message.reply_text("Send a name for your saved message.")
    await app.listen(query.message.chat.id, filters.text, process_save_message)

async def process_save_message(client, message):
    user_id = message.from_user.id
    save_name = message.text

    messages_collection.update_one({"user_id": user_id}, {"$set": {"saved_name": save_name}})
    await message.reply_text(f"Message saved as '{save_name}'!")

# Manage Saved Messages
@app.on_message(filters.command("saved") & filters.private)
async def show_saved_messages(client, message):
    user_id = message.from_user.id
    saved_messages = list(messages_collection.find({"user_id": user_id, "saved_name": {"$ne": None}}))

    if not saved_messages:
        await message.reply_text("No saved messages found!")
        return

    buttons = [[InlineKeyboardButton(msg["saved_name"], callback_data=f"view_saved_{msg['_id']}")] for msg in saved_messages]
    await message.reply_text("Select a saved message:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^view_saved_"))
async def view_saved_message(client, query):
    msg_id = query.data.split("_")[2]
    msg_data = messages_collection.find_one({"_id": msg_id})

    buttons = [
        [InlineKeyboardButton("Send", callback_data=f"send_saved_{msg_id}")],
        [InlineKeyboardButton("Schedule", callback_data=f"schedule_saved_{msg_id}")]
    ]
    await query.message.reply_text(f"Saved message: {msg_data['saved_name']}", reply_markup=InlineKeyboardMarkup(buttons))

# Send Saved Message
@app.on_callback_query(filters.regex("^send_saved_"))
async def send_saved_message(client, query):
    msg_id = query.data.split("_")[2]
    msg_data = messages_collection.find_one({"_id": msg_id})
    chat_id = msg_data["chat_id"]

    buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if msg_data["image"]:
        await app.send_photo(chat_id, photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
    else:
        await app.send_message(chat_id, text=msg_data["caption"] or "No caption", reply_markup=markup)

    await query.message.reply_text("Message sent successfully!")

# Schedule Message
@app.on_callback_query(filters.regex("^schedule_saved_"))
async def ask_schedule_interval(client, query):
    msg_id = query.data.split("_")[2]
    await query.message.reply_text("Send the interval time in seconds.")
    await app.listen(query.message.chat.id, filters.text, lambda _, m: process_schedule_message(msg_id, m))

async def process_schedule_message(msg_id, message):
    try:
        interval = int(message.text)
        await message.reply_text(f"Scheduling message every {interval} seconds.")
        asyncio.create_task(schedule_message(msg_id, interval))
    except ValueError:
        await message.reply_text("Invalid input! Please enter a number.")

async def schedule_message(msg_id, interval):
    msg_data = messages_collection.find_one({"_id": msg_id})
    chat_id = msg_data["chat_id"]

    while True:
        buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
        markup = InlineKeyboardMarkup(buttons) if buttons else None

        if msg_data["image"]:
            await app.send_photo(chat_id, photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
        else:
            await app.send_message(chat_id, text=msg_data["caption"] or "No caption", reply_markup=markup)

        await asyncio.sleep(interval)

### **Image Handling**
@app.on_callback_query(filters.regex("^add_image"))
async def ask_image(client, query):
    await query.message.reply_text("Send the image now as a **photo**, not a file.")


@app.on_message(filters.photo & filters.private)
async def process_image(client, message):
    user_id = message.from_user.id
    file_id = message.photo.file_id
    
    # Update image in the database
    messages_collection.update_one({"user_id": user_id}, {"$set": {"image": file_id}})
    await message.reply_text("✅ Image added successfully!")


### **Caption Handling**
@app.on_callback_query(filters.regex("^add_caption"))
async def ask_caption(client, query):
    await query.message.reply_text("Send the caption now.")


@app.on_message(filters.text & filters.private)
async def process_caption(client, message):
    user_id = message.from_user.id
    caption = message.text
    
    # Update caption in the database
    messages_collection.update_one({"user_id": user_id}, {"$set": {"caption": caption}})
    await message.reply_text("✅ Caption added successfully!")


### **Button Handling**
@app.on_callback_query(filters.regex("^add_button"))
async def ask_button(client, query):
    await query.message.reply_text("Send the button in this format:\n\n`Button Name - URL`")


@app.on_message(filters.text & filters.private)
async def process_button(client, message):
    user_id = message.from_user.id
    try:
        name, url = message.text.split(" - ", 1)  # Ensure correct splitting
        messages_collection.update_one(
            {"user_id": user_id},
            {"$push": {"buttons": {"name": name.strip(), "url": url.strip()}}}
        )
        await message.reply_text(f"✅ Button '{name}' added successfully!")
    except ValueError:
        await message.reply_text("❌ Invalid format! Use: `Button Name - URL`")


### **Preview Message**
@app.on_callback_query(filters.regex("^preview"))
async def preview_message(client, query):
    user_id = query.from_user.id
    msg_data = messages_collection.find_one({"user_id": user_id})

    if not msg_data:
        await query.message.reply_text("❌ No message found. Please start again.")
        return

    buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if msg_data["image"]:  
        await query.message.reply_photo(photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
    else:
        await query.message.reply_text(text=msg_data["caption"] or "No caption", reply_markup=markup)


### **Send Final Message Anonymously**
@app.on_callback_query(filters.regex("^send_final"))
async def send_final_message(client, query):
    user_id = query.from_user.id
    msg_data = messages_collection.find_one({"user_id": user_id})

    if not msg_data:
        await query.message.reply_text("❌ No message found. Please start again.")
        return

    chat_id = msg_data["chat_id"]
    buttons = [[InlineKeyboardButton(btn["name"], url=btn["url"])] for btn in msg_data["buttons"]]
    markup = InlineKeyboardMarkup(buttons) if buttons else None

    if msg_data["image"]:
        await app.send_photo(chat_id, photo=msg_data["image"], caption=msg_data["caption"] or "", reply_markup=markup)
    else:
        await app.send_message(chat_id, text=msg_data["caption"] or "No caption", reply_markup=markup)

    await query.message.reply_text("✅ Message sent successfully!")
    messages_collection.delete_one({"user_id": user_id})  # Cleanup after sending


app.run()
