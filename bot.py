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

app = Client("anon_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["anon_bot_db"]
chats_collection = db["chats"]
messages_collection = db["messages"]


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

    buttons = []
    for chat in chats:
        chat_id = chat["chat_id"]
        chat_title = f"Unknown Chat ({chat_id})"  # Default title

        try:
            chat_info = await client.get_chat(chat_id)  # Fetch chat details
            chat_title = chat_info.title  # Update with actual title if available
        except Exception as e:
            print(f"Error fetching chat info for {chat_id}: {e}")  # Debugging log

        buttons.append([InlineKeyboardButton(chat_title, callback_data=f"chat_{chat_id}")])

    await message.reply_text("Select a connected chat:", reply_markup=InlineKeyboardMarkup(buttons))


@app.on_callback_query(filters.regex("^chat_"))
async def chat_options(client, query):
    chat_id_str = query.data.split("_")[1]

    if not chat_id_str.isdigit():
        await query.answer("Invalid chat selection!", show_alert=True)
        return

    chat_id = int(chat_id_str)  
    try:
        chat_info = await client.get_chat(chat_id)
        chat_title = chat_info.title  
    except Exception as e:
        print(f"Error fetching chat info for {chat_id}: {e}")
        chat_title = f"Unknown Chat ({chat_id})"

    buttons = [
        [InlineKeyboardButton("Send an Anonymous Message", callback_data=f"send_{chat_id}")],
        [InlineKeyboardButton("Remove Chat", callback_data=f"remove_{chat_id}")]
    ]

    await query.message.edit_text(f"**{chat_title}**\nChoose an action:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^remove_"))
async def remove_chat(client, query):
    chat_id = query.data.split("_")[1]
    chats_collection.delete_one({"chat_id": int(chat_id)})
    await query.message.edit_text("Chat removed successfully!")

user_state = {}

### Start message creation process
@app.on_callback_query(filters.regex("^send_"))
async def start_anon_message(client, query):
    chat_id = int(query.data.split("_")[1])
    
    messages_collection.delete_one({"user_id": query.from_user.id})
    messages_collection.insert_one({
    "user_id": query.from_user.id, 
    "chat_id": chat_id, 
    "image": None, 
    "caption": None, 
    "buttons": [],
    "context": None  #conrejdfisj
     })
  

    buttons = [
        [InlineKeyboardButton("Add Image", callback_data="add_image"),
         InlineKeyboardButton("Add Caption", callback_data="add_caption")],
        [InlineKeyboardButton("Add URL Button", callback_data="add_button"),
         InlineKeyboardButton("Preview", callback_data="preview")],
        [InlineKeyboardButton("Send", callback_data="send_final")]
    ]
    await query.message.edit_text("Editing anonymous message:", reply_markup=InlineKeyboardMarkup(buttons))


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
    user_id = query.from_user.id
    messages_collection.update_one({"user_id": user_id}, {"$set": {"context": "caption"}})
    await query.message.reply_text("Send the caption now.")



@app.on_callback_query(filters.regex("^add_button"))
async def ask_button(client, query):
    user_id = query.from_user.id
    messages_collection.update_one({"user_id": user_id}, {"$set": {"context": "button"}})
    await query.message.reply_text("Send the button in this format:\n\n`Button Name - URL`")


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

@app.on_message(filters.text & filters.private)
async def process_text(client, message):
    user_id = message.from_user.id
    user_data = messages_collection.find_one({"user_id": user_id})

    if not user_data or "context" not in user_data:
        await message.reply_text("❌ No active operation. Please start again.")
        return

    context = user_data["context"]

    if context == "caption":
        # Update the caption
        messages_collection.update_one({"user_id": user_id}, {"$set": {"caption": message.text, "context": None}})
        await message.reply_text("✅ Caption added successfully!")

    elif context == "button":
        # Process button input
        try:
            name, url = message.text.split(" - ", 1)
            messages_collection.update_one(
                {"user_id": user_id},
                {"$push": {"buttons": {"name": name.strip(), "url": url.strip()}}, "$set": {"context": None}}
            )
            await message.reply_text(f"✅ Button '{name}' added successfully!")
        except ValueError:
            await message.reply_text("❌ Invalid format! Use: `Button Name - URL`")
    else:
        await message.reply_text("❌ No active operation. Please start again.")

app.run()
