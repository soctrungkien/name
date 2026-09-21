import os
import asyncio
from quart import Quart
from name import main as bot_main

app = Quart(__name__)

@app.route('/')
async def home():
    return "Running", 200

async def run_web():
    port = int(os.environ.get("PORT", 10000))
    await app.run_task(host="0.0.0.0", port=port)

async def main():
    # Chạy cả web và bot trong cùng một loop
    await asyncio.gather(
        run_web(),
        bot_main()
    )

if __name__ == "__main__":
    asyncio.run(main())
