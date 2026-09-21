import os
import threading
import asyncio
from flask import Flask
from name import main as bot_main # Import hàm main từ file name.py của Hihi

# 1. Flask Web Server
app = Flask(__name__)
@app.route('/')
def home():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Chạy bot
def run_bot():
    asyncio.run(bot_main())

if __name__ == "__main__":
    # Chạy Flask ở thread riêng
    threading.Thread(target=run_web, daemon=True).start()
    
    # Chạy bot ở main thread
    run_bot()
