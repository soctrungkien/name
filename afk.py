import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from pyrogram import enums
from pyrogram.session import StringSession

API_ID = int(os.getenv("API_ID", "2040"))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")
SESSION_STRING = os.getenv("SESSION_STRING", "")

app = Client(
    "afk_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

afk_enabled = False
afk_message = ""
afk_lock = asyncio.Lock()
last_replied = {}


async def delete_later(message, seconds=10):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


async def send_afk(message):
    global afk_enabled

    if not afk_enabled or not afk_message:
        return

    user = message.from_user
    if not user:
        return

    if user.is_self:
        return

    key = (message.chat.id, user.id)

    now = asyncio.get_running_loop().time()

    if key in last_replied:
        if now - last_replied[key] < 10:
            return

    last_replied[key] = now

    try:
        reply = await message.reply_text(
            afk_message,
            quote=True
        )
        asyncio.create_task(delete_later(reply, 10))
    except RPCError:
        pass
    except Exception:
        pass


@app.on_message(filters.me & filters.regex(r"^\.afk(?:\s+([\s\S]*))?$"))
async def afk_command(client, message: Message):
    global afk_enabled, afk_message

    text = message.matches[0].group(1)

    if text and text.strip():
        afk_message = text.strip()
        afk_enabled = True
    else:
        afk_enabled = False
        afk_message = ""

    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(
    ~filters.me &
    filters.incoming &
    filters.text
)
async def incoming_message(client, message: Message):
    if not afk_enabled:
        return

    me = await client.get_me()

    if message.from_user and message.from_user.id == me.id:
        return

    mentioned = False

    if message.entities:
        for entity in message.entities:
            if entity.type == enums.MessageEntityType.MENTION:
                username = message.text[
                    entity.offset:entity.offset + entity.length
                ]
                if me.username and username.lower() == f"@{me.username}".lower():
                    mentioned = True
                    break

            elif entity.type == enums.MessageEntityType.TEXT_MENTION:
                if entity.user and entity.user.id == me.id:
                    mentioned = True
                    break

    replied_to_me = False

    if message.reply_to_message:
        replied = message.reply_to_message

        if replied.from_user and replied.from_user.id == me.id:
            replied_to_me = True

    if mentioned or replied_to_me:
        await send_afk(message)


app.run()
