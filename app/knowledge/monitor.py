"""Rule Monitor: weekly check of every official source in the registry.

For each "tokens" source it extracts the meaningful numbers on the page (AED
amounts, day/month/year counts, toll-free numbers, percentages) and compares
them with the last reviewed baseline. A change becomes an alert with a short,
human-readable diff ("new on page: aed 500 / gone: aed 400"). Missing
must-contain phrases and unreachable pages (2 checks in a row) also alert.

Alerts go to the team (audit log + optional admin Telegram chat). While a
module has an unreviewed change, users of that module see a short notice to
double-check the official link. A person reviews and acknowledges with
`scripts/rule_monitor.py ack <fact_id>`. Advice text is NEVER changed
automatically, and page text is never shown to users or sent to an AI.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.db.models import AuditLog, SourceCheck, utcnow
from app.knowledge.fetch import FetchError
from app.knowledge.registry import FACTS, FACTS_BY_ID, Fact

log = logging.getLogger(__name__)

UNREACHABLE_AFTER = 2
_TOKEN_PATTERNS = (
    re.compile(r"\b(?:aed|dhs?\.?|dirhams?)\s?\d[\d,]*(?:\.\d+)?\b"),
    re.compile(r"\b\d[\d,]*(?:\.\d+)?\s?(?:aed|dirhams?)\b"),
    re.compile(r"\b\d{1,3}\s?(?:calendar\s|working\s|consecutive\s)?(?:days?|weeks?|months?|years?|hours?)\b"),
    re.compile(r"\b(?:800|600)[\s-]?\d[\d\s-]{2,8}\d\b"),
    re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%"),
)

Fetcher = Callable[[str], Awaitable[str]]
Notifier = Callable[[str], Awaitable[None]]


def extract_tokens(text: str) -> set[str]:
    """The numbers on a page that can change a rule. Normalised for comparison."""
    s = text.lower()
    out: set[str] = set()
    for pat in _TOKEN_PATTERNS:
        for m in pat.findall(s):
            tok = re.sub(r"\s+", " ", m.replace(",", "")).strip()
            if pat.pattern.startswith(r"\b(?:800|600)"):
                tok = re.sub(r"[\s-]", "", tok)
            out.add(tok)
    return out


@dataclass
class Result:
    fact: Fact
    status: str               # ok | changed | unreachable | new
    detail: str = ""


async def check_fact(session, fact: Fact, fetch: Fetcher) -> Result:  # type: ignore[no-untyped-def]
    row = await session.get(SourceCheck, fact.id)
    if row is None:
        row = SourceCheck(fact_id=fact.id, module=fact.module, status="new", fail_count=0)
        session.add(row)
    row.url, row.module = fact.url, fact.module
    row.last_checked = utcnow()

    if fact.mode == "manual" or not fact.url:
        row.status = "ok" if row.status in ("new", "ok") else row.status
        return Result(fact, row.status)

    try:
        text = await fetch(fact.url)
    except FetchError as e:
        row.fail_count = (row.fail_count or 0) + 1
        if row.fail_count >= UNREACHABLE_AFTER and row.status != "unreachable":
            row.status, row.detail = "unreachable", f"could not load page: {e}"[:255]
            return Result(fact, "unreachable", row.detail)
        return Result(fact, row.status)
    row.fail_count = 0
    if row.status == "unreachable":
        row.status, row.detail = "ok", None

    problems: list[str] = []
    low = text.lower()
    missing = [p for p in fact.must_contain if p.lower() not in low]
    if missing:
        problems.append("missing phrase(s): " + ", ".join(missing))

    if fact.mode == "tokens":
        tokens = extract_tokens(text)
        if row.tokens is None:                          # first check: set the baseline
            row.tokens = json.dumps(sorted(tokens))
        else:
            base = set(json.loads(row.tokens))
            added, gone = sorted(tokens - base), sorted(base - tokens)
            if added or gone:
                problems.append("new on page: " + (", ".join(added[:8]) or "-") + " / gone: " + (", ".join(gone[:8]) or "-"))
            row.pending_tokens = json.dumps(sorted(tokens))

    if problems:
        detail = "; ".join(problems)[:255]
        is_new = row.status != "changed" or row.detail != detail
        row.status, row.detail, row.last_changed = "changed", detail, utcnow()
        return Result(fact, "changed" if is_new else "known", detail)
    if row.status in ("new", "ok"):
        row.status = "ok"
    return Result(fact, row.status)


async def run_checks(session, fetch: Fetcher, notify: Notifier | None = None,  # type: ignore[no-untyped-def]
                     today: date | None = None) -> list[Result]:
    today = today or date.today()
    results = [await check_fact(session, f, fetch) for f in FACTS]
    alerts = [r for r in results if r.status in ("changed", "unreachable")]
    due = [f for f in FACTS if f.review_by <= today]
    for r in alerts:
        session.add(AuditLog(user_ref=None, event="rule_alert", detail=f"{r.fact.id}: {r.status}"))
    await session.commit()
    invalidate_cache()
    if notify and (alerts or due):
        lines = ["🔎 Rafiq rule monitor"]
        lines += [f"• {r.fact.id} [{r.fact.module}] {r.status}: {r.detail}" for r in alerts]
        lines += [f"• {f.id}: re-check by hand (last checked {f.checked_on})" for f in due]
        lines.append("Review the official page, update the content if needed, then: scripts/rule_monitor.py ack <id>")
        try:
            await notify("\n".join(lines)[:3900])
        except Exception:
            log.warning("Rule monitor: admin notification failed")
    return results


async def acknowledge(session, fact_id: str) -> bool:  # type: ignore[no-untyped-def]
    """A person reviewed the change (and updated content if needed): accept the
    page's current numbers as the new baseline and clear the notice."""
    if fact_id not in FACTS_BY_ID:
        return False
    row = await session.get(SourceCheck, fact_id)
    if row is None:
        return False
    if row.pending_tokens:
        row.tokens, row.pending_tokens = row.pending_tokens, None
    row.status, row.detail = "ok", None
    session.add(AuditLog(user_ref=None, event="rule_reviewed", detail=fact_id))
    await session.commit()
    invalidate_cache()
    return True


# ---------------------------------------------------------------- user-facing notice

_cache: dict[str, object] = {"at": None, "modules": frozenset()}
CACHE_SECONDS = 300


def invalidate_cache() -> None:
    _cache["at"] = None


async def modules_under_review(session) -> frozenset[str]:  # type: ignore[no-untyped-def]
    """Modules with an unreviewed source change (cached for 5 minutes)."""
    at = _cache["at"]
    if at is not None and time.monotonic() - float(at) < CACHE_SECONDS:  # type: ignore[arg-type]
        return _cache["modules"]  # type: ignore[return-value]
    rows = (await session.execute(select(SourceCheck.module).where(SourceCheck.status == "changed"))).scalars().all()
    _cache["modules"], _cache["at"] = frozenset(rows), time.monotonic()
    return _cache["modules"]  # type: ignore[return-value]
