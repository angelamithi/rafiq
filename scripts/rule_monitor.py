"""Rule Monitor admin tool (run on the server, never from chat).

    python scripts/rule_monitor.py status          # every fact, its source and state
    python scripts/rule_monitor.py check           # run all checks now
    python scripts/rule_monitor.py ack <fact_id>   # reviewed: accept the page's numbers, clear the user notice

There are deliberately no admin commands in the WhatsApp/Telegram chat.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.models import SourceCheck  # noqa: E402
from app.db.session import init_db, sessionmaker  # noqa: E402
from app.knowledge.fetch import fetch_text  # noqa: E402
from app.knowledge.monitor import acknowledge, run_checks  # noqa: E402
from app.knowledge.registry import FACTS  # noqa: E402


async def status() -> None:
    async with sessionmaker()() as s:
        rows = {r.fact_id: r for r in (await s.execute(select(SourceCheck))).scalars()}
    today = date.today()
    for f in FACTS:
        r = rows.get(f.id)
        state = r.status if r else "never checked"
        due = "  ⚠ re-check by hand" if f.review_by <= today else ""
        print(f"{f.id:28} {f.module:11} {f.mode:9} {state:13} {f.url or '(manual)'}{due}")
        if r and r.detail:
            print(f"{'':28} → {r.detail}")


async def check() -> None:
    async def show(text: str) -> None:
        print(text)

    async with sessionmaker()() as s:
        results = await run_checks(s, fetch_text, show)
    print(f"Checked {len(results)} sources.")


async def ack(fact_id: str) -> None:
    async with sessionmaker()() as s:
        ok = await acknowledge(s, fact_id)
    print("Acknowledged." if ok else f"Unknown or never-checked fact: {fact_id}")


async def main(argv: list[str]) -> None:
    await init_db()
    if argv[:1] == ["status"]:
        await status()
    elif argv[:1] == ["check"]:
        await check()
    elif argv[:1] == ["ack"] and len(argv) == 2:
        await ack(argv[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
