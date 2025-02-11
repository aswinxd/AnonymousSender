from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode

import config

from .logger import LOGGER


class app(Client):
    def __init__(self):
        LOGGER(__name__).info(f"Starting Bot...")
        super().__init__(
            name="anonymous messager",
            api_id=config.api_id,
            api_hash=config.api_hash,
            bot_token=config.bot_token,
            in_memory=True,
            parse_mode=ParseMode.HTML,
            max_concurrent_transmissions=7,
        )

    async def start(self):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name + " " + (self.me.last_name or "")
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(
                chat_id=config.SUDOERS,
                text=f"bot restarted",
            )
        finally:
             LOGGER(__name__).info(f"Running {self.name}")

    async def stop(self):
        await super().stop()