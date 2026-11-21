"""Telegram Bot API adapter (development and testing channel)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.channels.base import Incoming, Outgoing, fit
from app.config import get_settings
from app.security.crypto import constant_time_equals

log = logging.getLogger(__name__)


def verify_secret(header: str | None) -> bool:
    secret = get_settings().telegram_webhook_secret
    return bool(secret and header and constant_time_equals(secret, header))


def parse_update(update: dict[str, Any]) -> list[Incoming]:
    if cq := update.get("callback_query"):
        chat = ((cq.get("message") or {}).get("chat") or {})
        if chat.get("type", "private") != "private":
            return []
        return [Incoming(channel="telegram", external_id=str(chat.get("id")), message_id=f"cb-{cq.get('id')}",
                         kind="button", button_id=cq.get("data"), callback_id=str(cq.get("id")))]
    m = update.get("message") or {}
    chat = m.get("chat") or {}
    if not chat or chat.get("type") != "private":   # ignore groups: the agent is 1:1 only
        return []
    msg = Incoming(channel="telegram", external_id=str(chat["id"]), message_id=f"msg-{chat['id']}-{m.get('message_id')}")
    if "text" in m:
        msg.text = m["text"]
    elif any(k in m for k in ("photo", "voice", "audio", "document", "video", "sticker")):
        kind = next(k for k in ("photo", "voice", "audio", "document", "video", "sticker") if k in m)
        msg.kind = "media"
        msg.media_type = "image" if kind == "photo" else kind
        if kind == "photo":  # several sizes are sent; take the largest
            best = max(m["photo"], key=lambda p: (p.get("file_size") or 0, p.get("width") or 0))
            msg.media_id, msg.mime_type = best.get("file_id"), "image/jpeg"
        elif isinstance(m.get(kind), dict):
            msg.media_id, msg.mime_type = m[kind].get("file_id"), m[kind].get("mime_type")
            if isinstance(m[kind].get("duration"), int):
                msg.duration = m[kind]["duration"]
        msg.text = m.get("caption", "")
    else:
        msg.kind = "unsupported"
    return [msg]


def to_payload(chat_id: str, msg: Outgoing) -> dict[str, Any]:
    body: dict[str, Any] = {"chat_id": chat_id, "text": fit(msg.text, 4096), "disable_web_page_preview": True}
    keyboard: list[list[dict[str, str]]] = []
    if msg.buttons:
        keyboard = [[{"text": b.title, "callback_data": b.id[:64]} for b in msg.buttons[:3]]]
    elif msg.menu:
        keyboard = [[{"text": r.title, "callback_data": r.id[:64]}] for r in msg.menu.rows[:10]]
    if keyboard:
        body["reply_markup"] = {"inline_keyboard": keyboard}
    return body


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.base = f"https://api.telegram.org/bot{get_settings().telegram_bot_token}"
        self.http = http or httpx.AsyncClient(timeout=15)

    async def typing(self, chat_id: str) -> None:
        try:
            await self.http.post(f"{self.base}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
        except httpx.HTTPError:
            pass

    async def answer_callback(self, callback_id: str) -> None:
        try:
            await self.http.post(f"{self.base}/answerCallbackQuery", json={"callback_query_id": callback_id})
        except httpx.HTTPError:
            pass

    async def send(self, chat_id: str, msg: Outgoing) -> None:
        r = await self.http.post(f"{self.base}/sendMessage", json=to_payload(chat_id, msg))
        if r.status_code >= 400:
            log.error("Telegram send failed: status=%s", r.status_code)
            r.raise_for_status()
