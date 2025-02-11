from strings.string import start_command_instructions
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sender import app


@app.on_message(filters.command("start") & filters.private)
async def handle_start_command(message):
    buttons = [
        [
            InlineKeyboardButton("add to group", url="https://t.me/MIssALeenA_BOT?startgroup=true"),
        ],
        [
            InlineKeyboardButton("channel", url="https://t.me/elitesbots")
        ]
    ]
    await message.reply_text(
        start_command_instructions,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
