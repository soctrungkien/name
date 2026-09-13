#!/usr/bin/env python3
"""
Script hỗ trợ tạo Telethon StringSession cho tài khoản Telegram.
Chạy script:
    python3 generate_session.py
"""

import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("=" * 60)
    print("🔑 TELEGRAM SESSION STRING GENERATOR")
    print("=" * 60)
    print("Lấy API_ID & API_HASH tại: https://my.telegram.org (hoặc dùng mặc định)\n")

    default_api_id = os.getenv("API_ID", "2040")
    default_api_hash = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

    api_id_input = input(f"Nhập API_ID [{default_api_id}]: ").strip()
    api_id = int(api_id_input if api_id_input else default_api_id)

    api_hash_input = input(f"Nhập API_HASH [{default_api_hash}]: ").strip()
    api_hash = api_hash_input if api_hash_input else default_api_hash

    print("\n⏳ Đang kết nối Telethon...")
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    await client.start()
    
    session_string = client.session.save()
    me = await client.get_me()
    
    print("\n" + "=" * 60)
    print("✅ ĐĂNG NHẬP THÀNH CÔNG!")
    print(f"👤 Tài khoản: {me.first_name} {me.last_name or ''} (@{me.username or 'None'}, ID: {me.id})")
    print("=" * 60)
    print("\n📋 SESSION STRING CỦA BẠN (đã tạo thành công):\n")
    print(session_string)
    print("\n" + "=" * 60)

    # Cập nhật tự động vào file .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        save_choice = input("\nBạn có muốn tự động lưu SESSION_STRING vào .env không? (y/n) [y]: ").strip().lower()
        if save_choice in ("", "y", "yes"):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "SESSION_STRING=" in content:
                import re
                new_content = re.sub(r"SESSION_STRING=.*", f"SESSION_STRING={session_string}", content)
            else:
                new_content = content + f"\nSESSION_STRING={session_string}\n"
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("✅ Đã lưu SESSION_STRING vào file .env!")

    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[👋] Đã hủy.")
