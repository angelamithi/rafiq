from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from app.channels.base import Incoming, Outgoing
from app.channels.telegram import TelegramClient
from app.channels.whatsapp import WhatsAppClient

_clients: dict[str, object] = {}


def _client(channel: str):  # type: ignore[no-untyped-def]
    if channel not in _clients:
        if channel == "web":
            from app.channels.web import WebClient

            _clients[channel] = WebClient()
        else:
            _clients[channel] = WhatsAppClient() if channel == "whatsapp" else TelegramClient()
    return _clients[channel]


async def acknowledge(msg: Incoming) -> None:
    """Show 'read' + typing so the user knows Rafiq is working on it."""
    c = _client(msg.channel)
    if msg.channel == "web":
        return
    if msg.channel == "whatsapp":
        await c.mark_read_and_typing(msg.message_id)
    else:
        if msg.callback_id:
            await c.answer_callback(msg.callback_id)
        await c.typing(msg.external_id)


log = logging.getLogger(__name__)

# How long one "typing…" signal lasts on each channel, so we refresh just before it fades.
# Telegram: ~5 s. WhatsApp: up to 25 s or until we reply.
_REFRESH = {"telegram": 4.0, "whatsapp": 20.0}
_MAX_TYPING_SECONDS = 90.0  # never show dots forever if something hangs


async def _refresh_typing(msg: Incoming) -> None:
    c = _client(msg.channel)
    interval = _REFRESH.get(msg.channel, 4.0)
    waited = 0.0
    while waited < _MAX_TYPING_SECONDS:
        await asyncio.sleep(interval)
        waited += interval
        try:
            if msg.channel == "whatsapp":
                await c.mark_read_and_typing(msg.message_id)
            else:
                await c.typing(msg.external_id)
        except Exception:  # best-effort
            log.info("typing refresh failed")


@contextlib.asynccontextmanager
async def keep_typing(msg: Incoming) -> AsyncIterator[None]:
    """Show read + typing dots straight away and keep them visible until the reply is sent."""
    try:
        await acknowledge(msg)
    except Exception:  # typing indicators are best-effort
        log.info("acknowledge failed")
    task = asyncio.create_task(_refresh_typing(msg))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


def sender_for(channel: str):  # type: ignore[no-untyped-def]
    c = _client(channel)

    async def send(to: str, out: Outgoing) -> None:
        await c.send(to, out)

    return send


async def relay(channel: str, to: str, out: Outgoing, template: tuple[str, list[str]] | None = None) -> None:
    """Send to someone OTHER than the person chatting. Only used for an SOS to a
    trusted contact who opted in. On WhatsApp an approved template is used when
    configured, because the contact may be outside the 24-hour reply window."""
    c = _client(channel)
    if channel == "whatsapp" and template and template[0]:
        from app.channels.whatsapp import send_template
        from app.config import get_settings

        await send_template(c, to, template[0], get_settings().whatsapp_template_language, template[1])
        return
    await c.send(to, out)
