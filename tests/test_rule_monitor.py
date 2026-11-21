"""Core module: Official Knowledge Base & Rule Monitor."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.agent.graph import build_graph
from app.db.models import AuditLog, SourceCheck
from app.db.session import sessionmaker
from app.knowledge import fetch as kf
from app.knowledge import monitor
from app.knowledge.registry import FACTS, FACTS_BY_ID, U_AE_ILOE
from tests.conftest import Chat, onboard

PAGE_ILOE = "<html><script>var x='AED 999';</script><p>A worker who does not subscribe will be fined 400 AED. Subscribe within 4 months.</p></html>"


class FakeWeb:
    """Serves official pages from memory; anything else gets a plain page."""

    def __init__(self) -> None:
        self.pages: dict[str, str] = {}
        self.down: set[str] = set()

    async def __call__(self, url: str) -> str:
        if url in self.down:
            raise kf.FetchError("status 503")
        f = next((f for f in FACTS if f.url == url), None)
        default = " ".join(f.must_contain) if f else ""
        return kf.html_to_text(self.pages.get(url, f"<p>Official page. {default}</p>"))


@pytest.fixture(autouse=True)
def _fresh_cache():
    monitor.invalidate_cache()
    yield
    monitor.invalidate_cache()


async def run(web: FakeWeb, notes: list[str] | None = None, today: date = date(2026, 11, 23)):
    async def notify(text: str) -> None:
        if notes is not None:
            notes.append(text)

    async with sessionmaker()() as s:
        return await monitor.run_checks(s, web, notify, today=today)


# ------------------------------------------------------------------ registry


def test_registry_sources_are_official_and_modules_exist():
    routes = set(build_graph().get_graph().nodes)
    for f in FACTS:
        assert f.module in routes, f.id
        assert f.mode in ("tokens", "reachable", "manual")
        if f.url:
            assert kf.host_allowed(f.url), f.url
        else:
            assert f.mode == "manual"
    assert len(FACTS_BY_ID) == len(FACTS)                       # unique ids


def test_extract_tokens_finds_rule_numbers_only():
    text = "Fine of AED 400, or 1,000 dirhams. Apply within 30 days, 4 months. Call 800 4673 or 80084. 85% rule. Page 12 of 30."
    tokens = monitor.extract_tokens(text)
    assert {"aed 400", "1000 dirhams", "30 days", "4 months", "8004673", "85%"} <= tokens
    assert not any("page" in t or t == "12" for t in tokens)


# ------------------------------------------------------------------ detection


async def test_first_run_sets_baseline_without_alerts():
    web, notes = FakeWeb(), []
    web.pages[U_AE_ILOE] = PAGE_ILOE
    results = await run(web, notes)
    assert {r.status for r in results} == {"ok"}
    assert notes == []
    async with sessionmaker()() as s:
        row = await s.get(SourceCheck, "iloe_fine")
    assert row.tokens and "aed 999" not in row.tokens               # script content ignored
    assert "subscribe" not in row.tokens                            # no page text stored, only numbers


async def test_changed_fine_raises_one_alert_with_a_readable_diff():
    web, notes = FakeWeb(), []
    web.pages[U_AE_ILOE] = PAGE_ILOE
    await run(web)
    web.pages[U_AE_ILOE] = PAGE_ILOE.replace("400 AED", "500 AED")
    results = await run(web, notes)
    changed = [r for r in results if r.status == "changed"]
    assert [r.fact.id for r in changed] == ["iloe_fine"]
    assert "new on page: 500 aed" in changed[0].detail and "gone: 400 aed" in changed[0].detail
    assert len(notes) == 1 and "iloe_fine" in notes[0] and "ack" in notes[0]
    notes.clear()
    await run(web, notes)                                           # same change again: no repeat alert
    assert notes == []
    async with sessionmaker()() as s:
        events = [e for (e,) in (await s.execute(select(AuditLog.event))).all()]
    assert events.count("rule_alert") == 1


async def test_missing_phrase_is_a_change():
    web = FakeWeb()
    await run(web)
    web.pages[FACTS_BY_ID["safety_hotlines"].url] = "<p>Call 8004888 for help.</p>"   # 8007283 gone
    results = await run(web)
    r = next(r for r in results if r.fact.id == "safety_hotlines")
    assert r.status == "changed" and "missing phrase(s): 8007283" in r.detail


async def test_unreachable_after_two_failures_then_recovers():
    web, notes = FakeWeb(), []
    url = FACTS_BY_ID["iloe_portal"].url
    await run(web)
    web.down.add(url)
    first = next(r for r in await run(web, notes) if r.fact.id == "iloe_portal")
    assert first.status == "ok" and notes == []                     # one blip is ignored
    second = next(r for r in await run(web, notes) if r.fact.id == "iloe_portal")
    assert second.status == "unreachable" and "could not load" in notes[0]
    web.down.clear()
    third = next(r for r in await run(web) if r.fact.id == "iloe_portal")
    assert third.status == "ok"


async def test_manual_facts_get_a_review_reminder_when_due():
    web, notes = FakeWeb(), []
    await run(web, notes, today=date(2027, 6, 1))                   # > 180 days after checking
    assert notes and "re-check by hand" in notes[0] and "wps_due_date" in notes[0]


# ------------------------------------------------------------------ users see a notice until a person reviews


async def test_users_see_notice_until_reviewed(chat: Chat):
    web = FakeWeb()
    web.pages[U_AE_ILOE] = PAGE_ILOE
    await run(web)
    await onboard(chat)
    r = await chat.say("iloe")
    assert "our team is checking" not in chat.text_of(r)
    web.pages[U_AE_ILOE] = PAGE_ILOE.replace("400 AED", "500 AED")
    await run(web)
    r = await chat.say("iloe")                                      # arrival module
    assert "our team is checking" in r[-1].text
    r = await chat.say("salary late")                               # other modules are unaffected
    assert "our team is checking" not in chat.text_of(r)
    r = await chat.say("I want to kill myself")                     # never on safety screens
    assert "our team is checking" not in chat.text_of(r)

    async with sessionmaker()() as s:
        assert await monitor.acknowledge(s, "iloe_fine")
        row = await s.get(SourceCheck, "iloe_fine")
        assert "500 aed" in row.tokens and row.status == "ok"       # new numbers accepted as baseline
        assert not await monitor.acknowledge(s, "not_a_fact")
    r = await chat.say("iloe")
    assert "our team is checking" not in chat.text_of(r)


# ------------------------------------------------------------------ safe fetching (SSRF)


@pytest.mark.parametrize("url,ok", [
    ("https://u.ae/en/x", True),
    ("https://www.mohre.gov.ae/x", True),
    ("http://u.ae/en/x", False),                       # https only
    ("https://u.ae.evil.com/x", False),                # look-alike
    ("https://evilu.ae/x", False),
    ("https://169.254.169.254/latest/meta-data", False),
    ("file:///etc/passwd", False),
])
def test_host_allowed(url, ok):
    assert kf.host_allowed(url) is ok


async def test_redirect_to_unofficial_host_is_refused_before_request():
    requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requested.append(str(req.url))
        if req.url.host == "u.ae":
            return httpx.Response(302, headers={"location": "https://evil.example.com/steal"})
        return httpx.Response(200, text="should never be fetched")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(kf.FetchError):
            await kf.fetch_text("https://u.ae/en/page", http, check_dns=False)
    assert requested == ["https://u.ae/en/page"]


async def test_private_addresses_are_refused(monkeypatch):
    async def fake_getaddrinfo(host, port, type=0):  # noqa: A002
        return [(None, None, None, None, ("10.0.0.5", 443))]

    class Loop:
        getaddrinfo = staticmethod(fake_getaddrinfo)

    monkeypatch.setattr(kf.asyncio, "get_running_loop", lambda: Loop())
    assert not await kf._resolves_public("u.ae")


async def test_large_pages_are_refused():
    big = "x" * (kf.MAX_BYTES + 10)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=big))) as http:
        with pytest.raises(kf.FetchError, match="too large"):
            await kf.fetch_text("https://u.ae/en/page", http, check_dns=False)


def test_html_to_text_drops_scripts_and_styles():
    assert kf.html_to_text("<style>p{}</style><p>Fine <b>AED 400</b></p><script>ignore('AED 1')</script>") == "Fine AED 400"
