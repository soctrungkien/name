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
    await app.run_task(host="0.0.0.0", port=port)


async def main():
    await asyncio.gather(
        run_web(),
        name_main(),
        afk_main()
    )


if __name__ == "__main__":
    asyncio.run(main())
