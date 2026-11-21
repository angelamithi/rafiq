from __future__ import annotations

from app.channels.base import Incoming, Outgoing
from app.channels.telegram import TelegramClient
from app.channels.whatsapp import WhatsAppClient

_clients: dict[str, object] = {}


def _client(channel: str):  # type: ignore[no-untyped-def]
    if channel not in _clients:
        _clients[channel] = WhatsAppClient() if channel == "whatsapp" else TelegramClient()
    return _clients[channel]


async def acknowledge(msg: Incoming) -> None:
    """Show 'read' + typing so the user knows Rafiq is working on it."""
    c = _client(msg.channel)
    if msg.channel == "whatsapp":
        await c.mark_read_and_typing(msg.message_id)
    else:
        if msg.callback_id:
            await c.answer_callback(msg.callback_id)
        await c.typing(msg.external_id)


def sender_for(channel: str):  # type: ignore[no-untyped-def]
    c = _client(channel)

    async def send(to: str, out: Outgoing) -> None:
        await c.send(to, out)

    return send
