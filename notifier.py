"""
Sends messages via Telegram Bot API.
"""
import asyncio
import os

from telegram import Bot
from telegram.constants import ParseMode


def _chunk(text: str, size: int = 4000) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


async def _send_async(token: str, chat_id: str, message: str):
    async with Bot(token) as bot:
        chunks = _chunk(message)
        for i, chunk in enumerate(chunks):
            prefix = f"*[{i + 1}/{len(chunks)}]*\n" if len(chunks) > 1 else ""
            await bot.send_message(
                chat_id=chat_id,
                text=prefix + chunk,
                parse_mode=ParseMode.MARKDOWN,
            )
            print(f"  → Mensagem {i + 1}/{len(chunks)} enviada")


def send_message(message: str, chat_id: str | None = None):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
    asyncio.run(_send_async(token, chat_id, message))
