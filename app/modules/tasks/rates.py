"""Live exchange rates for rate alerts.

Source: ExchangeRate-API's open endpoint (no key), fetched only from the
allow-listed host, HTTPS only, no redirects, small size limit. Results are cached
in Redis for an hour, so users never trigger more than one fetch per hour.
The rate is the mid-market rate; users are told providers give a bit less.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

ALLOWED_HOSTS = {"open.er-api.com"}
CACHE_SECONDS = 3600
MAX_BYTES = 200_000
_CODE = re.compile(r"^[A-Z]{3}$")


@dataclass
class Rates:
    rates: dict[str, float]
    updated: str          # e.g. "Sat, 21 Nov 2026"


async def _download(url: str) -> dict[str, Any] | None:
    u = urlparse(url)
    if u.scheme != "https" or (u.hostname or "") not in ALLOWED_HOSTS:
        log.error("FX URL not allowed")
        return None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            r = await http.get(url, headers={"Accept": "application/json"})
        if r.status_code != 200 or len(r.content) > MAX_BYTES:
            return None
        data = r.json()
        return data if isinstance(data, dict) and data.get("result") == "success" else None
    except (httpx.HTTPError, ValueError):
        log.warning("FX fetch failed")
        return None


def _parse(data: dict[str, Any]) -> Rates | None:
    raw = data.get("rates")
    if not isinstance(raw, dict):
        return None
    rates = {k: float(v) for k, v in raw.items() if isinstance(k, str) and _CODE.match(k)
             and isinstance(v, (int, float)) and 0 < float(v) < 1e7}
    if "USD" not in rates:
        return None
    updated = str(data.get("time_last_update_utc") or "")[:16]
    return Rates(rates=rates, updated=updated)


async def get_rates(kv: Any, url: str, fetcher: Any = None) -> Rates | None:
    """fetcher(url) -> dict | None  (tests pass a fake)."""
    key = "fx:aed"
    if kv is not None and (cached := await kv.get(key)):
        try:
            c = json.loads(cached if isinstance(cached, str) else cached.decode())
            return Rates(rates=c["rates"], updated=c["updated"])
        except (ValueError, KeyError, AttributeError):
            pass
    data = await (fetcher or _download)(url)
    rates = _parse(data) if data else None
    if rates and kv is not None:
        await kv.set(key, json.dumps({"rates": rates.rates, "updated": rates.updated}), ex=CACHE_SECONDS)
    return rates


def fmt_rate(v: float) -> str:
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:.3f}"
    return f"{v:.5f}"


def parse_target(text: str) -> float | None:
    m = re.fullmatch(r"\s*(\d{1,7}(?:[.,]\d{1,5})?)\s*", text or "")
    return float(m[1].replace(",", ".")) if m else None


# ---------------------------------------------------------------- alerts (worker)

async def check_rate_alerts(session: Any, kv: Any, send: Any, url: str, fetcher: Any = None) -> int:
    from sqlalchemy import select

    from app.db import repo
    from app.db.models import Toolkit, User
    from app.i18n import t
    from app.modules.stay_legal.visa import Reminder
    from app.security.crypto import decrypt

    rows = (await session.execute(
        select(User).join(Toolkit, Toolkit.user_id == User.id)
        .where(Toolkit.rate_on == 1, User.consent_status == "granted"))).scalars().all()
    if not rows:
        return 0
    rates = await get_rates(kv, url, fetcher)
    if not rates:
        return 0
    sent = 0
    for user in rows:
        kit = repo.toolkit(user)
        alert = kit.get("rate") or {}
        cur, target = alert.get("cur"), alert.get("target")
        now = rates.rates.get(cur or "")
        if not now or not isinstance(target, (int, float)) or now < target:
            continue
        to = decrypt(user.address_enc)
        if not to or user.notifications_paused:
            continue
        lang = user.language
        r = Reminder(user_id=user.id, channel=user.channel, to=to, days=0,
                     text=t("rate_hit", lang, rate=fmt_rate(now), cur=cur, target=fmt_rate(target)),
                     template_params=[cur, fmt_rate(now), fmt_rate(target)], kind="rate")
        try:
            if await send(r):
                sent += 1
                kit.pop("rate", None)          # one alert, then it switches off
                repo.save_toolkit(user, kit, rate_on=False)
        except Exception:
            log.warning("Rate alert send failed")
    await session.commit()
    return sent
