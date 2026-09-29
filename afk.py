import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import RPCError

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

last_trigger = {}
cooldown_until = {}


async def delete_later(message, seconds=10):
    await asyncio.sleep(seconds)

    try:
        await message.delete()
    except Exception:
        pass


async def send_afk(message):
    if not afk_enabled or not afk_message:
        return

    user = message.from_user

    if not user:
        return

    if user.is_self or user.is_bot:
        return

    user_id = user.id
    now = asyncio.get_running_loop().time()

    if now < cooldown_until.get(user_id, 0):
        return

    previous = last_trigger.get(user_id)

    if previous is not None:
        elapsed = now - previous

        if elapsed < 60:
            cooldown_until[user_id] = now + 600
            last_trigger.pop(user_id, None)
            return

    last_trigger[user_id] = now

    try:
        reply = await message.reply_text(
            afk_message,
            quote=True
        )

        asyncio.create_task(
            delete_later(reply, 10)
        )

    except RPCError:
        pass
    except Exception:
        pass


@app.on_message(
    filters.me &
    filters.regex(r"^\.afk(?:\s+([\s\S]+))?$")
)
async def afk_command(client, message: Message):
    global afk_enabled, afk_message

    text = message.matches[0].group(1)

    if text and text.strip():
        afk_message = text.strip()

    if afk_message:
        afk_enabled = True

    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(
    filters.me &
    filters.regex(r"^\.on$")
)
async def on_command(client, message: Message):
    global afk_enabled, afk_message

    afk_enabled = False
    afk_message = ""

    last_trigger.clear()
    cooldown_until.clear()

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
    if not afk_enabled or not afk_message:
        return

    user = message.from_user

    if not user:
        return

    if user.is_self or user.is_bot:
        return

    me = await client.get_me()

    mentioned = False
    replied_to_me = False

    if message.entities:
        for entity in message.entities:

            if entity.type == enums.MessageEntityType.MENTION:
                username = message.text[
                    entity.offset:
                    entity.offset + entity.length
                ]

                if (
                    me.username
                    and username.lower() == f"@{me.username}".lower()
                ):
                    mentioned = True
                    break

            elif entity.type == enums.MessageEntityType.TEXT_MENTION:
                if entity.user and entity.user.id == me.id:
                    mentioned = True
                    break

    if message.reply_to_message:
        replied = message.reply_to_message

        if (
            replied.from_user
            and replied.from_user.id == me.id
        ):
            replied_to_me = True

    if mentioned or replied_to_me:
        await send_afk(message)


async def main():
    await app.start()
    await asyncio.Event().wait()

"render.py" để chạy "name.py" + "afk.py" + web song song:

import os
import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())

from quart import Quart
from name import main as name_main
from afk import main as afk_main

app = Quart(__name__)


@app.route("/")
async def home():
    return "Running", 200


async def run_web():
    port = int(os.environ.get("PORT", 10000))
    await app.run_task(
        host="0.0.0.0",
        port=port
    )


async def main():
    await asyncio.gather(
        run_web(),
        name_main(),
        afk_main()
    )


if __name__ == "__main__":
    asyncio.run(main())

"requirements.txt":

pyrogram==2.0.106
tgcrypto==1.2.5
quart==0.23.1

Hoạt động

.afk Đang bận

→ Bật AFK, lưu "Đang bận".

.afk

→ Bật AFK bằng nội dung "Đang bận".

.on

→ Tắt AFK, xoá nội dung, reset toàn bộ cooldown.

Nếu một người tag/reply:

Lần 1       → reply AFK
< 1 phút    → không reply + khóa người đó 10 phút
10 phút sau → có thể reply lại

Bot gửi tin AFK sẽ tự xoá sau 10 giây.

Bot Telegram khác tag/reply bạn sẽ không được auto-reply.
