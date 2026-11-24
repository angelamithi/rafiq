"""Orchestrator + specialist agents, salary gaps, payslips, cases, protection early warning, Life Manager."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.agent.agents import AGENTS, ROUTE_AGENT, agent_for
from app.db import repo
from app.db.models import AuditLog, Case
from app.db.session import sessionmaker
from app.modules.cases import store
from app.modules.cases.node import send_case_follow_ups
from app.modules.life.node import send_weekly_briefs
from app.modules.pay import amounts as am
from app.modules.protection.node import assess, needs_protection
from app.security.tool_policy import AGENT_ALLOWLIST, NODE_ALLOWLIST, ToolNotAllowed, agent_of, authorize
from tests.conftest import TODAY, Chat, onboard
from tests.test_documents import JPEG, FakeVision
from tests.test_tasks import db_user, loader


async def events(name: str) -> list[str]:
    async with sessionmaker()() as s:
        return [d or "" for (d,) in (await s.execute(select(AuditLog.detail).where(AuditLog.event == name))).all()]


# ------------------------------------------------------------------ agents

def test_every_node_belongs_to_one_agent():
    from app.agent.graph import build_graph

    graph_nodes = set(build_graph().get_graph().nodes) - {"__start__", "__end__", "route"}
    assert graph_nodes <= set(ROUTE_AGENT), graph_nodes - set(ROUTE_AGENT)
    owners = [n for a in AGENTS.values() for n in a.nodes]
    assert len(owners) == len(set(owners))


def test_agent_walls_hold_even_if_a_node_list_is_wrong(monkeypatch):
    # Data scopes: no Financial or Wellbeing code can ever open the vault or send an SOS.
    for agent in ("financial", "wellbeing", "employment"):
        assert "get_own_vault" not in AGENT_ALLOWLIST[agent]
    assert {a for a, tools in AGENT_ALLOWLIST.items() if "send_sos" in tools} == {"protection"}
    for node, tools in NODE_ALLOWLIST.items():
        assert tools <= AGENT_ALLOWLIST[agent_of(node)], node
    monkeypatch.setitem(NODE_ALLOWLIST, "money", {"get_own_profile", "get_own_vault"})   # a mistake in one list...
    with pytest.raises(ToolNotAllowed, match="Agent 'financial'"):
        authorize("money", "get_own_vault")                                              # ...is still refused
    assert agent_of("tasks.protection") == "protection" and agent_of("pay") == "employment"


def test_agent_for_tasks_and_crisis():
    assert agent_for("tasks", None, "task:sos_now") == "protection"
    assert agent_for("tasks", None, "task:vk:passport") == "life_admin"
    assert agent_for("tasks", "rate") == "financial"
    assert agent_for("social", "crisis") == "protection"
    assert agent_for("cases") == "employment" and agent_for("life") == "life_admin"


async def test_orchestrator_logs_the_agent(chat: Chat):
    await onboard(chat)
    await chat.say("my salary is late")
    await chat.say("rate alert")
    handled = await events("handled_by")
    assert "employment" in handled and "financial" in handled


# ------------------------------------------------------------------ salary amounts and gaps

async def test_part_payment_gap_owed_and_pattern(chat: Chat):
    await onboard(chat)
    r = await chat.tap("pay:part")
    assert "monthly salary" in Chat.text_of(r)
    r = await chat.say("1500")
    assert "How much did you receive" in r[0].text
    r = await chat.say("1200")
    assert "AED 300 less" in r[0].text and "pay:gap_not" in chat.ids_of(r)
    r = await chat.tap("pay:gap_not")
    assert "about AED 300" in Chat.text_of(r) and "case:new:wages" in chat.ids_of(r)
    user = await db_user(chat)
    assert am.received(user) == {"2026-10": 1200} and am.gaps(user)[1] == 300
    # A second short month -> the pattern is named.
    repo.set_pay_status(user, "2026-09", "unpaid")
    assert am.shortfall_streak(user) == 2


async def test_agreed_deduction_is_not_owed(chat: Chat):
    await onboard(chat)
    await chat.tap("pay:part")
    await chat.say("2000")
    await chat.say("1800")
    r = await chat.tap("pay:gap_agreed")
    assert "agreed deduction" in r[0].text
    assert am.gaps(await db_user(chat))[1] == 0


async def test_paid_in_full_records_amount(chat: Chat):
    await onboard(chat)
    await chat.tap("pay:part")
    await chat.say("1500")
    await chat.say("1500")
    r = await chat.say("what am i owed")
    assert "No gaps" in r[0].text


SLIP = """AL NOOR CLEANING LLC  PAYSLIP October 2026
Basic salary 1,000.00
Housing allowance 500
Gross pay 1,500.00
Accommodation deduction 200
Absence deduction 100
Net pay 1,200.00"""


async def test_payslip_reading(chat: Chat):
    await onboard(chat)
    await chat.tap("pay:part")
    await chat.say("1500")
    await chat.say("1500")                       # contract salary now known
    chat.media_loader, chat.doc_model = loader(JPEG), FakeVision(SLIP)
    r = await chat.say("read my payslip")
    assert "photo" in r[0].text
    r = await chat.media("image")
    text = r[0].text
    assert "Net pay (what you got): AED 1,200" in text and "Accommodation" in text and "AED 300 less" in text
    r = await chat.tap("pay:slip_save")
    assert "AED 1,200 received for October 2026" in r[0].text


def test_payslip_parser():
    slip = am.read_payslip(SLIP, TODAY)
    assert (slip.net, slip.gross, slip.basic, slip.month) == (1200, 1500, 1000, "2026-10")
    assert [a for _, a in slip.deductions] == [200, 100]
    assert am.read_payslip("hello there", TODAY).found() is False


# ------------------------------------------------------------------ cases

async def test_case_lifecycle(chat: Chat, kv):
    await onboard(chat)
    r = await chat.tap("case:new:wages")
    assert "Case opened" in r[0].text
    case_id = next(i for i in chat.ids_of(r) if i.startswith("case:filed:")).split(":")[2]
    r = await chat.tap(f"case:filed:{case_id}")
    assert "reference number" in r[0].text
    r = await chat.say("MOHRE-20261124-778899")
    from app.i18n import fmt_date

    assert f"check in with you on *{fmt_date(TODAY + timedelta(days=7), 'en')}*" in r[0].text
    assert "MOHRE-20261124-778899" in r[1].text            # the user's own reference isn't masked
    await chat.tap(f"case:note:{case_id}")
    await chat.say("Called MOHRE, they said wait 2 weeks")
    sent = []

    async def send(rem):
        sent.append(rem)
        return True

    async with sessionmaker()() as s:
        assert await send_case_follow_ups(s, send, TODAY + timedelta(days=7)) == 1
        assert await send_case_follow_ups(s, send, TODAY + timedelta(days=8)) == 0       # next one in 14 days
    assert sent[0].kind == "case" and "MOHRE-20261124-778899" in sent[0].text
    await chat.tap(f"case:out:{case_id}")
    r = await chat.tap(f"case:o:0:{case_id}")
    assert "How much" in r[0].text
    r = await chat.say("3000")
    assert "Outcome recorded" in r[0].text and "resolved" in r[1].text
    r = await chat.tap(f"case:pdf:{case_id}")
    assert r[0].file.startswith(b"%PDF")
    assert "Paid in full" in await events("case_resolved")
    # Someone else can't see it.
    other = Chat(kv, phone="254700000077")
    await onboard(other, name="Otieno")
    r = await other.tap(f"case:view:{case_id}")
    assert "couldn't find" in r[0].text


async def test_one_open_case_per_kind(chat: Chat):
    await onboard(chat)
    await chat.tap("case:new:passport")
    await chat.tap("case:new:passport")
    async with sessionmaker()() as s:
        assert len((await s.execute(select(Case))).all()) == 1


# ------------------------------------------------------------------ protection early warning

def test_indicator_scoring():
    msg = "My employer has not paid me for two months, and he says I cannot leave until I repay my recruitment fee."
    assert set(assess(msg)) == {"unpaid", "debt"} and needs_protection(msg)
    assert not needs_protection("my salary is late this month")
    assert not needs_protection("I use my phone to call home every day")
    assert needs_protection("madam took my phone and I work 18 hours a day with no day off")


async def test_protection_flow_from_example(chat: Chat):
    await onboard(chat)
    r = await chat.say("My employer has not paid me for two months, and he says I cannot leave until I repay my recruitment fee.")
    assert "2 warning signs" in r[0].text and "Wages not paid" in r[0].text and "Are you safe" in r[0].text
    r = await chat.tap("pro:danger")
    assert "999" in r[0].text and "800 7283" in r[0].text
    r = await chat.tap("pro:safe")
    assert {"pro:record", "pro:checklist", "pro:help"} <= set(chat.ids_of(r))
    r = await chat.tap("pro:record")
    assert "incident record" in r[0].text
    r = await chat.say("On 20 Nov he shouted and said I owe 5000 to the agency")
    assert "Note added" in r[0].text
    async with sessionmaker()() as s:
        case = (await s.execute(select(Case))).scalar_one()
        d = store.data(case)
    assert case.kind == "safety" and d["signs"] == ["Wages not paid", "Made to repay a recruitment fee or debt"]
    assert any("owe 5000" in e["e"] for e in d["timeline"])
    assert "unpaid,debt" in await events("protection_warning")


async def test_protection_works_before_consent(kv):
    c = Chat(kv, phone="254711111111")
    r = await c.say("they took my passport and locked me in the house")
    assert "warning signs" in r[0].text


# ------------------------------------------------------------------ Life Manager

async def test_life_manager_brief_prioritises(chat: Chat):
    soon = TODAY + timedelta(days=16)
    await onboard(chat, visa_expiry=soon.strftime("%d/%m/%Y"))
    await chat.tap("pay:part")
    await chat.say("1500")
    await chat.say("0")
    await chat.tap("case:new:wages")
    r = await chat.say("what needs my attention")
    text = r[0].text
    assert text.index("Urgent") < text.index("Coming up") < text.index("Ongoing")
    assert "not fully paid" in text and "Visa expires in 16 days" in text
    assert "File your unpaid or short wages complaint" in text and "No trusted contact" in text
    assert "pay:gaps" in chat.ids_of(r) and "life:on" in chat.ids_of(r)


async def test_weekly_brief_is_opt_in(chat: Chat):
    await onboard(chat)
    await chat.tap("pay:unpaid")
    sent = []

    async def send(rem):
        sent.append(rem)
        return True

    async with sessionmaker()() as s:
        assert await send_weekly_briefs(s, send, TODAY) == 0
    r = await chat.tap("life:on")
    assert "every Monday" in r[0].text
    async with sessionmaker()() as s:
        assert await send_weekly_briefs(s, send, TODAY) == 1
    assert sent[0].kind == "brief"


async def test_life_manager_all_clear(chat: Chat):
    await onboard(chat, visa_expiry="15/03/2028")
    r = await chat.tap("life:brief")
    assert "No trusted contact" in Chat.text_of(r) and "Urgent" not in Chat.text_of(r)


# ---- free legal help (when a case needs a lawyer) -----------------------------
async def test_free_legal_help_lists_official_routes(chat: Chat):
    await onboard(chat)
    r = await chat.say("I need a lawyer")
    text = r[0].text
    assert "Shoor" in text and "04 334 7777" in text and "80084" in text and "not a lawyer" in text
    assert "u.ae/en/information-and-services/justice" in text
    assert "employment" in await events("handled_by") and await events("legal_help")


async def test_unresolved_case_offers_legal_help(chat: Chat):
    await onboard(chat)
    r = await chat.tap("case:new:wages")
    case_id = next(i for i in chat.ids_of(r) if i.startswith("case:pdf:")).split(":", 2)[2]
    assert "case:legal" in chat.ids_of(r)
    await chat.tap(f"case:out:{case_id}")
    r = await chat.tap(f"case:o:5:{case_id}")              # Not resolved
    assert "case:legal" in chat.ids_of(r)


async def test_wages_case_pack_is_bilingual_with_amounts_owed(chat: Chat):
    from io import BytesIO

    from pypdf import PdfReader

    await onboard(chat)
    r = await chat.tap("case:new:wages")
    case_id = next(i for i in chat.ids_of(r) if i.startswith("case:pdf:")).split(":", 2)[2]
    r = await chat.tap(f"case:pdf:{case_id}")
    pdf = r[0].file
    assert pdf.startswith(b"%PDF") and b"DejaVu" in pdf             # Unicode font embedded for Arabic
    text = "".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf)).pages)
    assert "Bring to MOHRE" in text and "80084" in text
    assert any("\u0600" <= ch <= "\u06ff" or "\ufe70" <= ch <= "\ufeff" for ch in text)   # Arabic page present
