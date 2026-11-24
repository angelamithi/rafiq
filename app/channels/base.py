"""Channel-neutral message types. The agent only ever produces these; each
channel adapter turns them into WhatsApp or Telegram API calls."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Incoming(BaseModel):
    channel: str                      # whatsapp | telegram
    external_id: str                  # phone number (WhatsApp) or chat id (Telegram); verified by webhook
    message_id: str
    kind: str = "text"                # text | button | media | location | unsupported
    text: str = ""
    button_id: str | None = None
    media_type: str | None = None     # image | document | audio | voice | video | sticker
    media_id: str | None = None       # WhatsApp media id or Telegram file_id (never a URL)
    mime_type: str | None = None      # as declared by the sender; re-checked from file bytes
    callback_id: str | None = None    # Telegram callback query id
    duration: int | None = None       # seconds, for voice notes when the channel reports it
    latitude: float | None = None     # shared location (used only for an SOS; never stored)
    longitude: float | None = None


class Button(BaseModel):
    id: str
    title: str


class ListRow(BaseModel):
    id: str
    title: str
    description: str | None = None


class ListMenu(BaseModel):
    button: str
    rows: list[ListRow]
    section_title: str | None = None


class Outgoing(BaseModel):
    text: str
    buttons: list[Button] = Field(default_factory=list)   # max 3 (WhatsApp limit)
    menu: ListMenu | None = None                          # max 10 rows (WhatsApp limit)
    # Optional file (a PDF Rafiq made, or the user's own saved document). `text` is the caption.
    file: bytes | None = None
    filename: str | None = None
    file_mime: str | None = None
    # Stays in English even when replies are translated (complaint drafts, letters: officials need this version).
    keep_english: bool = False

    def all_option_ids(self) -> list[str]:
        ids = [b.id for b in self.buttons]
        if self.menu:
            ids += [r.id for r in self.menu.rows]
        return ids


def fit(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
