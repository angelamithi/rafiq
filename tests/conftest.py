from __future__ import annotations

import os
from datetime import date

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

os.environ.update(
    APP_ENV="test",
    FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    ID_HASH_PEPPER="test-pepper-0123456789-0123456789-0123456789",
    WHATSAPP_ENABLED="true",
    WHATSAPP_APP_SECRET="test-app-secret",
    WHATSAPP_VERIFY_TOKEN="test-verify-token",
    WHATSAPP_PHONE_NUMBER_ID="111",
    TELEGRAM_ENABLED="true",
    TELEGRAM_WEBHOOK_SECRET="test-telegram-secret",
    USE_QUEUE="false",
    PRIVACY_POLICY_VERSION="2026-11-21.1",
)

from app.channels.base import Incoming, Outgoing  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.security.ratelimit import MemoryKV  # noqa: E402
from app.service import process_message  # noqa: E402

TODAY = date(2026, 11, 19)


@pytest_asyncio.fixture(autouse=True)
async def fresh_db(tmp_path):
    get_settings.cache_clear()
    db_session.reset_engine_for_tests(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await db_session.init_db()
    yield
    await db_session.get_engine().dispose()


class Chat:
    """Simulates one person chatting with Rafiq through the full pipeline."""

    _counter = 0

    def __init__(self, kv: MemoryKV, phone: str = "254700000001", channel: str = "whatsapp", extractor=None) -> None:
        self.kv, self.phone, self.channel = kv, phone, channel
        self.sent: list[Outgoing] = []
        self.extractor = extractor  # fake AI for tests; None = rules only
        self.media_loader = None    # fake media download for tests
        self.doc_model = None       # fake Gemini for reading photos/scans; None = no AI
        self.intent_model = None    # fake Gemini for understanding unclear messages; None = rules only
        self.fx_fetcher = None      # fake exchange-rate source
        self.relayed: list[tuple[str, str, Outgoing, object]] = []   # messages to a trusted contact

    async def _relay(self, channel: str, to: str, out: Outgoing, template=None) -> None:
        self.relayed.append((channel, to, out, template))

    async def _send(self, to: str, out: Outgoing) -> None:
        assert to == self.phone, "a reply was addressed to someone else"
        self.sent.append(out)

    async def _go(self, **kw) -> list[Outgoing]:
        Chat._counter += 1
        msg = Incoming(channel=self.channel, external_id=self.phone, message_id=f"m{Chat._counter}", **kw)
        return await process_message(msg, kv=self.kv, send=self._send, today=TODAY,
                                     relay=self._relay,
                                     agent_context={"extractor": self.extractor, "media_loader": self.media_loader,
                                                    "doc_model": self.doc_model, "intent_model": self.intent_model,
                                                    "fx_fetcher": self.fx_fetcher})

    async def say(self, text: str) -> list[Outgoing]:
        return await self._go(text=text)

    async def tap(self, button_id: str) -> list[Outgoing]:
        return await self._go(kind="button", button_id=button_id)

    async def media(self, media_type: str = "image", media_id: str = "media-1") -> list[Outgoing]:
        return await self._go(kind="media", media_type=media_type, media_id=media_id)

    async def location(self, lat: float, lon: float) -> list[Outgoing]:
        return await self._go(kind="location", latitude=lat, longitude=lon)

    @staticmethod
    def text_of(replies: list[Outgoing]) -> str:
        return "\n---\n".join(r.text for r in replies)

    @staticmethod
    def ids_of(replies: list[Outgoing]) -> list[str]:
        return [i for r in replies for i in r.all_option_ids()]


@pytest.fixture
def kv() -> MemoryKV:
    return MemoryKV()


@pytest.fixture
def chat(kv) -> Chat:
    return Chat(kv)


async def onboard(c: Chat, *, name: str = "Wanjiru", country: str = "Kenya") -> None:
    await c.say("hi")
    await c.tap("consent:yes")
    await c.say(name)
    await c.tap("stage:offer")
    await c.tap(f"country:{country}")
    await c.tap("visa:visit")
    await c.say("15/03/2027")
    await c.tap("sector:hospitality")
    await c.tap("summary:ok")
