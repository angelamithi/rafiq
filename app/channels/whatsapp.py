"""WhatsApp Cloud API adapter: webhook verification, parsing, sending."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.channels.base import Incoming, Outgoing, fit
from app.config import get_settings

log = logging.getLogger(__name__)

# WhatsApp interactive message limits
BODY_MAX_INTERACTIVE = 1024
BODY_MAX_TEXT = 4096
BUTTON_TITLE_MAX = 20
LIST_BUTTON_MAX = 20
ROW_TITLE_MAX = 24
ROW_DESC_MAX = 72
MAX_BUTTONS = 3
MAX_ROWS = 10


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Meta signs every webhook with the app secret (X-Hub-Signature-256)."""
    secret = get_settings().whatsapp_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def _coord(v: Any, limit: float) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 5) if -limit <= f <= limit else None


def parse_webhook(payload: dict[str, Any]) -> list[Incoming]:
    out: list[Incoming] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            # Only accept messages addressed to OUR number.
            pnid = (value.get("metadata") or {}).get("phone_number_id")
            if pnid and get_settings().whatsapp_phone_number_id and pnid != get_settings().whatsapp_phone_number_id:
                log.warning("Ignoring webhook for another phone number id")
                continue
            for m in value.get("messages", []) or []:
                sender, mid, mtype = str(m.get("from", "")), str(m.get("id", "")), m.get("type")
                if not sender or not mid:
                    continue
                msg = Incoming(channel="whatsapp", external_id=sender, message_id=mid)
                if mtype == "text":
                    msg.text = (m.get("text") or {}).get("body", "")
                elif mtype == "interactive":
                    inter = m.get("interactive") or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    msg.kind, msg.button_id, msg.text = "button", reply.get("id"), reply.get("title", "")
                elif mtype == "button":  # quick reply on a template message
                    b = m.get("button") or {}
                    msg.kind, msg.button_id, msg.text = "button", b.get("payload"), b.get("text", "")
                elif mtype == "location":
                    loc = m.get("location") or {}
                    msg.kind = "location"
                    msg.latitude, msg.longitude = _coord(loc.get("latitude"), 90), _coord(loc.get("longitude"), 180)
                    if msg.latitude is None or msg.longitude is None:
                        msg.kind = "unsupported"
                elif mtype in {"image", "audio", "voice", "document", "video", "sticker"}:
                    media = m.get(mtype) or {}
                    msg.kind, msg.media_type = "media", mtype
                    msg.media_id, msg.mime_type = media.get("id"), media.get("mime_type")
                    msg.text = media.get("caption") or ""
                else:
                    msg.kind = "unsupported"
                out.append(msg)
    return out


def to_payload(to: str, msg: Outgoing) -> dict[str, Any]:
    base: dict[str, Any] = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if msg.buttons:
        base |= {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": fit(msg.text, BODY_MAX_INTERACTIVE)},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b.id, "title": fit(b.title, BUTTON_TITLE_MAX)}}
                        for b in msg.buttons[:MAX_BUTTONS]
                    ]
                },
            },
        }
    elif msg.menu:
        section: dict[str, Any] = {
            "rows": [
                {"id": r.id, "title": fit(r.title, ROW_TITLE_MAX), **({"description": fit(r.description, ROW_DESC_MAX)} if r.description else {})}
                for r in msg.menu.rows[:MAX_ROWS]
            ]
        }
        if msg.menu.section_title:
            section["title"] = fit(msg.menu.section_title, 24)
        base |= {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": fit(msg.text, BODY_MAX_INTERACTIVE)},
                "action": {"button": fit(msg.menu.button, LIST_BUTTON_MAX), "sections": [section]},
            },
        }
    else:
        base |= {"type": "text", "text": {"body": fit(msg.text, BODY_MAX_TEXT), "preview_url": False}}
    return base


class WhatsAppClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        s = get_settings()
        self.url = f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_number_id}/messages"
        self.headers = {"Authorization": f"Bearer {s.whatsapp_access_token}"}
        self.http = http or httpx.AsyncClient(timeout=15)

    async def mark_read_and_typing(self, message_id: str) -> None:
        body = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id, "typing_indicator": {"type": "text"}}
        try:
            await self.http.post(self.url, json=body, headers=self.headers)
        except httpx.HTTPError:
            log.info("typing indicator failed (non-fatal)")

    async def _upload(self, data: bytes, filename: str, mime: str) -> str:
        url = self.url.rsplit("/", 1)[0] + "/media"
        r = await self.http.post(url, headers=self.headers, data={"messaging_product": "whatsapp", "type": mime},
                                 files={"file": (filename, data, mime)})
        if r.status_code >= 400:
            log.error("WhatsApp media upload failed: status=%s", r.status_code)
            r.raise_for_status()
        return str(r.json()["id"])

    async def send(self, to: str, msg: Outgoing) -> None:
        if msg.file:
            await self._send_file(to, msg)
            if msg.buttons or msg.menu:   # WhatsApp files can't carry buttons: send them right after
                await self.send(to, msg.model_copy(update={"file": None, "text": "👇"}))
            return
        r = await self.http.post(self.url, json=to_payload(to, msg), headers=self.headers)
        if r.status_code >= 400:
            # Never log the full response body: it can echo the recipient's number.
            log.error("WhatsApp send failed: status=%s", r.status_code)
            r.raise_for_status()


    async def _send_file(self, to: str, msg: Outgoing) -> None:
        mime = msg.file_mime or "application/pdf"
        name = msg.filename or "document.pdf"
        media_id = await self._upload(msg.file or b"", name, mime)
        kind = "image" if mime in ("image/jpeg", "image/png") else "document"
        body: dict[str, Any] = {"id": media_id, "caption": fit(msg.text, 1024)}
        if kind == "document":
            body["filename"] = name
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": kind, kind: body}
        r = await self.http.post(self.url, json=payload, headers=self.headers)
        if r.status_code >= 400:
            log.error("WhatsApp file send failed: status=%s", r.status_code)
            r.raise_for_status()


def template_payload(to: str, name: str, language: str, params: list[str]) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": name,
            "language": {"code": language},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": fit(p, 60)} for p in params]}],
        },
    }


async def send_template(client: "WhatsAppClient", to: str, name: str, language: str, params: list[str]) -> None:
    r = await client.http.post(client.url, json=template_payload(to, name, language, params), headers=client.headers)
    if r.status_code >= 400:
        log.error("WhatsApp template send failed: status=%s", r.status_code)
        r.raise_for_status()
