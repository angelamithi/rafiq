"""Web channel for the judges' demo page (/demo).

The demo runs the SAME pipeline as WhatsApp and Telegram (security checks,
orchestrator, agents, output guard). The worker "sends" a reply by putting it
in a short-lived Redis list for that browser session; the demo page collects
it. Files a judge uploads are held in Redis for 10 minutes, never on disk.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from app.channels.base import Outgoing

OUT_TTL = 600
MEDIA_TTL = 600
MAX_UPLOAD = 3_000_000


def _redis() -> Any:
    from redis.asyncio import Redis

    from app.config import get_settings

    return Redis.from_url(get_settings().redis_url)


def out_key(session_id: str) -> str:
    return f"web:out:{session_id}"


def to_json(msg: Outgoing) -> dict[str, Any]:
    d: dict[str, Any] = {"text": msg.text, "buttons": [{"id": b.id, "title": b.title} for b in msg.buttons]}
    if msg.menu:
        d["menu"] = {"button": msg.menu.button, "rows": [{"id": r.id, "title": r.title, "description": r.description}
                                                         for r in msg.menu.rows]}
    if msg.file:
        d["file"] = {"name": msg.filename or "file", "mime": msg.file_mime or "application/octet-stream",
                     "b64": base64.b64encode(msg.file).decode()}
    return d


class WebClient:
    def __init__(self, redis: Any = None) -> None:
        self.r = redis or _redis()

    async def send(self, to: str, msg: Outgoing) -> None:
        key = out_key(to)
        await self.r.rpush(key, json.dumps(to_json(msg)))
        await self.r.expire(key, OUT_TTL)

    async def typing(self, _to: str) -> None:
        return None

    async def answer_callback(self, _cid: str) -> None:
        return None

    async def mark_read_and_typing(self, _mid: str) -> None:
        return None


async def drain(redis: Any, session_id: str) -> list[dict[str, Any]]:
    key = out_key(session_id)
    items = await redis.lrange(key, 0, -1)
    await redis.delete(key)
    return [json.loads(i) for i in items]


async def store_media(redis: Any, media_id: str, data: bytes) -> None:
    await redis.set(f"web:media:{media_id}", base64.b64encode(data), ex=MEDIA_TTL)


async def load_media(media_id: str) -> bytes | None:
    r = _redis()
    try:
        raw = await r.get(f"web:media:{media_id}")
    finally:
        await r.aclose()
    return base64.b64decode(raw) if raw else None
