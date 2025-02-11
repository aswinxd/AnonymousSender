import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
from sender import app
from bson.objectid import ObjectId
from config import messages_collection, chats_collection



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
        try:
            chat_info = await client.get_chat(chat_id)  
            chat_title = chat_info.title  
        except Exception as e:
            print(f"Error fetching chat info for {chat_id}: {e}")
            chat_title = f"Unknown Chat ({chat_id})"

       
        buttons.append([InlineKeyboardButton(chat_title, callback_data=f"chat_{chat_id}")])

    await message.reply_text("Select a connected chat:", reply_markup=InlineKeyboardMarkup(buttons))


@app.on_callback_query(filters.regex("^chat_"))
async def chat_options(client, query):
    chat_id = int(query.data.split("_")[1])  
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

user_state = {}


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



@app.on_callback_query(filters.regex("^add_image"))
async def ask_image(client, query):
    await query.message.reply_text("Send the image now as a **photo**, not a file.")


@app.on_message(filters.photo & filters.private)
async def process_image(client, message):
    user_id = message.from_user.id
    file_id = message.photo.file_id
    

    messages_collection.update_one({"user_id": user_id}, {"$set": {"image": file_id}})
    await message.reply_text("✅ Image added successfully!")



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
    messages_collection.delete_one({"user_id": user_id}) 




@app.on_message(filters.text & filters.private)
async def process_text(client, message):
    user_id = message.from_user.id
    user_data = messages_collection.find_one({"user_id": user_id})

    if not user_data or "context" not in user_data:
        return

    context = user_data["context"]

    if context == "caption":
        messages_collection.update_one({"user_id": user_id}, {"$set": {"caption": message.text}})
        await message.reply_text("✅ Caption added successfully!")

    elif context == "button":
        buttons = message.text.split("\n")  

        added_buttons = []
        failed_buttons = []

        for btn in buttons:
            try:
                name, url = btn.split(" - ", 1)  
                name, url = name.strip(), url.strip()

            
                if not (url.startswith("http://") or url.startswith("https://")):
                    failed_buttons.append(btn)
                    continue

                messages_collection.update_one(
                    {"user_id": user_id},
                    {"$push": {"buttons": {"name": name, "url": url}}}
                )
                added_buttons.append(name)
            except ValueError:
                failed_buttons.append(btn)

        response = ""
        if added_buttons:
            response += f"✅ Added buttons: {', '.join(added_buttons)}\n"
        if failed_buttons:
            response += f"❌ Failed to add: {', '.join(failed_buttons)} (Check format!)"

        await message.reply_text(response or "❌ No valid buttons added!")

    messages_collection.update_one({"user_id": user_id}, {"$unset": {"context": ""}})  
