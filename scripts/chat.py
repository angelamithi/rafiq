"""Chat with Rafiq in your terminal: no WhatsApp, Redis or Postgres needed.
Uses the real pipeline (guards + agent) with a local SQLite file.

    python3 scripts/chat.py

Type a message, or a button id shown in [brackets] (e.g. lang:en), or the
option number. Ctrl+C to quit.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./rafiq_chat.db")

from app.channels.base import Incoming, Outgoing  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.security.ratelimit import MemoryKV  # noqa: E402
from app.service import process_message  # noqa: E402

options: list[str] = []


async def show(_to: str, out: Outgoing) -> None:
    global options
    print("\n\033[96mRafiq:\033[0m " + out.text.replace("\n", "\n       "))
    options = out.all_option_ids()
    for i, b in enumerate(out.buttons, 1):
        print(f"   {i}. ({b.title})  [{b.id}]")
    if out.menu:
        print(f"   ☰ {out.menu.button}")
        for i, r in enumerate(out.menu.rows, 1):
            print(f"   {i}. {r.title}" + (f" – {r.description}" if r.description else "") + f"  [{r.id}]")


async def main() -> None:
    await init_db()
    kv, n = MemoryKV(), 0
    print("Chatting with Rafiq. Say hi!")
    while True:
        raw = await asyncio.to_thread(input, "\n\033[92mYou:\033[0m ")
        n += 1
        raw = raw.strip()
        if raw in options:
            msg = Incoming(channel="whatsapp", external_id="254700000000", message_id=f"local-{n}", kind="button", button_id=raw)
        else:
            msg = Incoming(channel="whatsapp", external_id="254700000000", message_id=f"local-{n}", text=raw)
        await process_message(msg, kv=kv, send=show)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")
