"""Runs the labelled cases through Rafiq's full pipeline (security checks,
orchestrator, agents, output guard) and scores them.

Offline mode (default) uses the rules only: deterministic, free, and what
judges can reproduce. Live mode (--live) also lets Gemini help with unclear
messages, and counts AI calls and tokens so cost per task can be estimated.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TODAY = date(2026, 11, 19)


def setup_env(live: bool) -> str:
    """Isolated settings and a throwaway database, so an eval never touches real users."""
    from cryptography.fernet import Fernet

    tmp = tempfile.mkdtemp(prefix="rafiq-eval-")
    os.environ.update(
        APP_ENV="test", FIELD_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        ID_HASH_PEPPER="eval-pepper-0123456789-0123456789-0123456789", USE_QUEUE="false",
        WHATSAPP_ENABLED="true", WHATSAPP_APP_SECRET="eval", WHATSAPP_VERIFY_TOKEN="eval", WHATSAPP_PHONE_NUMBER_ID="1",
        TELEGRAM_ENABLED="false", LLM_ENABLED="true" if live else "false",
    )
    return f"sqlite+aiosqlite:///{tmp}/eval.db"


class CountingModel:
    """Wraps the real chat model to count calls and tokens (live mode only)."""

    def __init__(self, model: Any) -> None:
        self.model, self.calls, self.tokens_in, self.tokens_out = model, 0, 0, 0

    async def ainvoke(self, *a: Any, **kw: Any) -> Any:
        self.calls += 1
        res = await self.model.ainvoke(*a, **kw)
        usage = getattr(res, "usage_metadata", None) or {}
        self.tokens_in += int(usage.get("input_tokens", 0))
        self.tokens_out += int(usage.get("output_tokens", 0))
        return res

    def __getattr__(self, name: str) -> Any:
        return getattr(self.model, name)


@dataclass
class Result:
    id: str
    kind: str
    agent_expected: str | None
    agent_got: str | None
    passed: bool
    problems: list[str] = field(default_factory=list)
    ms: int = 0


async def run(cases: Any, *, live: bool = False) -> tuple[list[Result], dict[str, Any]]:
    from sqlalchemy import select

    from app.channels.base import Incoming, Outgoing
    from app.config import get_settings
    from app.db import repo
    from app.db import session as db_session
    from app.db.models import AuditLog
    from app.security.ratelimit import MemoryKV
    from app.service import process_message

    get_settings.cache_clear()
    db_session.reset_engine_for_tests(setup_env(live))
    await db_session.init_db()
    model = None
    if live:
        from app.agent.llm import get_intent_model

        base = get_intent_model()
        model = CountingModel(base) if base is not None else None

    results: list[Result] = []
    counter = 0
    for n, case in enumerate(cases):
        kv = MemoryKV()
        phone = f"2547{n:08d}"
        sent: list[Outgoing] = []

        async def send(to: str, out: Outgoing, _sent: list[Outgoing] = sent) -> None:
            _sent.append(out)

        async def relay(*_a: Any, **_k: Any) -> None:
            return None

        async def no_fx(_url: str) -> None:      # offline: no network
            return None

        async def go(**kw: Any) -> list[Outgoing]:
            nonlocal counter
            counter += 1
            msg = Incoming(channel="whatsapp", external_id=phone, message_id=f"e{counter}", **kw)
            ctx = {"intent_model": model} if live else {"intent_model": None, "doc_model": None, "fx_fetcher": no_fx}
            return await process_message(msg, kv=kv, send=send, today=TODAY, relay=relay, agent_context=ctx)

        # Standard onboarding (not scored): employment-first setup, then stage and visa via profile edit.
        for kind, value in (("say", "hi"), ("tap", "consent:yes"), ("say", "Amina"), ("tap", f"sector:{case.sector}"),
                            ("tap", "country:Kenya"), ("tap", "salary:skip"),
                            ("tap", "summary:edit"), ("tap", "edit:stage"), ("tap", "stage:offer"),
                            ("tap", "summary:edit"), ("tap", "edit:visa"), ("tap", "visa:visit"), ("say", "15/03/2027"),
                            ("tap", "summary:ok")):
            await (go(text=value) if kind == "say" else go(kind="button", button_id=value))

        start = time.perf_counter()
        replies: list[Outgoing] = []
        problems: list[str] = []
        try:
            for kind, value in case.steps:
                replies = await (go(text=value) if kind == "say" else go(kind="button", button_id=value))
        except Exception as e:  # a crash is a failure, never a skipped case
            problems.append(f"crashed: {type(e).__name__}")
        ms = int((time.perf_counter() - start) * 1000)
        text = "\n".join(r.text for r in replies)
        ids = {i for r in replies for i in r.all_option_ids()}
        async with db_session.sessionmaker()() as s:
            from app.db.models import User

            uid = (await s.execute(select(User.id).where(User.identity_hash == repo.hash_identity("whatsapp", phone)))).scalar()
            q = select(AuditLog.detail).where(AuditLog.event == "handled_by", AuditLog.user_ref == uid)
            handled = [d for (d,) in (await s.execute(q.order_by(AuditLog.id))).all()]
        agent = handled[-1] if handled else None
        if not replies:
            problems.append("no reply")
        if case.agent and agent != case.agent:
            problems.append(f"agent {agent} != {case.agent}")
        problems += [f"missing '{c}'" for c in case.contains if c.lower() not in text.lower()]
        problems += [f"should not say '{c}'" for c in case.absent if c.lower() in text.lower()]
        problems += [f"no button {b}" for b in case.buttons if b not in ids]
        results.append(Result(case.id, case.kind, case.agent, agent, not problems, problems, ms))

    meta = {"mode": "live" if live else "offline", "ai_calls": model.calls if model else 0,
            "tokens_in": model.tokens_in if model else 0, "tokens_out": model.tokens_out if model else 0}
    await db_session.get_engine().dispose()
    return results, meta


def report(results: list[Result], meta: dict[str, Any], price_in: float, price_out: float) -> str:
    total = len(results)
    passed = sum(r.passed for r in results)
    lines = [f"# Rafiq evaluation report ({meta['mode']})", "",
             f"**{passed} of {total} cases passed ({passed / total:.0%}).** Synthetic, labelled cases; "
             "every case runs through the full pipeline: security checks, orchestrator, specialist agent, output guard.", "",
             "Limits: the cases were written by the Rafiq team, so a high score shows the agent does what we designed, "
             "not yet how it does on real messages. Next: add anonymised real offers and questions from user interviews.", ""]
    lines += ["| Case type | Passed | Total |", "| --- | --- | --- |"]
    for kind in ("complete", "missing", "unexpected", "out_of_context", "safety"):
        rs = [r for r in results if r.kind == kind]
        if rs:
            lines.append(f"| {kind.replace('_', ' ')} | {sum(r.passed for r in rs)} | {len(rs)} |")
    lines += ["", "| Agent | Passed | Total |", "| --- | --- | --- |"]
    for agent in sorted({r.agent_expected for r in results if r.agent_expected}):
        rs = [r for r in results if r.agent_expected == agent]
        lines.append(f"| {agent} | {sum(r.passed for r in rs)} | {len(rs)} |")
    avg_ms = sum(r.ms for r in results) / max(total, 1)
    lines += ["", f"Average time per case: {avg_ms:.0f} ms (excluding network to WhatsApp)."]
    if meta["mode"] == "live":
        cost = (meta["tokens_in"] * price_in + meta["tokens_out"] * price_out) / 1_000_000
        lines.append(f"AI calls: {meta['ai_calls']} for {total} cases; tokens in/out {meta['tokens_in']}/{meta['tokens_out']}; "
                     f"estimated AI cost USD {cost:.4f} in total, USD {cost / max(total, 1):.5f} per task "
                     f"(at USD {price_in}/{price_out} per million tokens; check current Gemini prices).")
    else:
        lines.append("AI cost in this mode: USD 0. Rules handle every case here; the AI only reads photos, voice notes "
                     "and messages the rules don't recognise.")
    failed = [r for r in results if not r.passed]
    if failed:
        lines += ["", "## Failures", "", "| Case | Type | Problem |", "| --- | --- | --- |"]
        lines += [f"| {r.id} | {r.kind} | {'; '.join(r.problems)} |" for r in failed]
    lines += ["", "## All cases", "", "| Case | Type | Agent | Result |", "| --- | --- | --- | --- |"]
    lines += [f"| {r.id} | {r.kind} | {r.agent_got or '-'} | {'pass' if r.passed else 'FAIL'} |" for r in results]
    return "\n".join(lines) + "\n"
