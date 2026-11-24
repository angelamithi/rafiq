"""LangGraph node for Module 2: Job Safety.

Offers can arrive as pasted text, a photo or a PDF. All three end up as text
that goes through the same checks: rules -> injection scan -> (optional) AI
extraction with grounding -> fixed-wording report.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.channels.base import Outgoing
from app.i18n import t
from app.media.flow import read_media_from_message
from app.modules.job_safety import report
from app.modules.job_safety.extract import OfferFields, make_llm_extractor
from app.modules.job_safety.rules import HIGH, MEDIUM, Flag, check_offer, looks_like_offer
from app.security.injection import scan
from app.security.tool_policy import authorize

AWAITING = "job:await_offer"
MIN_OFFER_CHARS = 60
INJECTION_SCORE = 6
READABLE_MEDIA = ("image", "document")


def _settings(config: RunnableConfig) -> Any:
    from app.config import get_settings

    return ctx(config).get("settings") or get_settings()


def _default_extractor(config: RunnableConfig):  # type: ignore[no-untyped-def]
    from app.agent.llm import get_main_model

    model = get_main_model()
    if model is None:
        return None
    return make_llm_extractor(model, timeout=float(_settings(config).llm_timeout_seconds))


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _missing_from_pending(pending: str | None) -> list[str]:
    if pending and pending.startswith("jobq:"):
        return [m for m in pending.removeprefix("jobq:").split(",") if m]
    return []


async def _check(state: AgentState, config: RunnableConfig, text: str, guard: Any, *,
                 auto: bool = False, prefix: str | None = None, extra_events: tuple[tuple[str, str], ...] = ()) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    authorize("job_safety", "check_job_offer")   # read-only tool, current user only
    rules = check_offer(text)
    flags = list(rules.flags)

    suspicious = bool(guard and guard.score >= INJECTION_SCORE)
    if suspicious:
        flags.append(Flag("hidden_instructions", MEDIUM, t("flag_hidden_title", lang), t("flag_hidden_detail", lang)))

    fields: OfferFields | None = None
    extractor = ctx(config).get("extractor", "default")
    if extractor == "default":
        extractor = _default_extractor(config)
    if extractor and not suspicious:  # never hand a booby-trapped text to the AI
        fields = await extractor(text)

    # The AI can only ADD a flag by quoting a sentence that really is in the offer.
    if fields:
        codes = {f.code for f in flags}
        if fields.worker_payment_quote and "fees" not in codes:
            flags.append(Flag("fees", HIGH, "They ask you to pay fees",
                              "In the UAE, the employer must pay recruitment costs such as the visa, permit and medical. "
                              f"The offer says: \"{fields.worker_payment_quote}\"", report.MOHRE))
        if fields.visit_visa_quote and "visit_visa" not in codes:
            flags.append(Flag("visit_visa", HIGH, "Working on a visit visa",
                              "Working on a visit or tourist visa is illegal in the UAE. "
                              f"The offer says: \"{fields.visit_visa_quote}\"", report.MOHRE))

    missing = report.effective_missing(rules, fields)
    user.step = "ready"
    user.pending_action = "jobq:" + ",".join(missing)
    replies = report.build_report(rules, flags, fields, missing, user.home_country, lang, auto=auto, prefix=prefix)
    risk = HIGH if any(f.severity == HIGH for f in flags) else MEDIUM if flags else "low"
    detail = f"risk={risk};flags={','.join(sorted({f.code for f in flags}))};ai={'yes' if fields else 'no'}"
    return _out(state, *replies, events=_events(state, *extra_events, ("offer_checked", detail)))


async def job_safety(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command")
    text = state.get("text", "")
    waiting = user.step == AWAITING

    if bid in ("menu:job", "job:check") or cmd == "job":
        user.step = AWAITING
        return _out(state, report.intro_message(lang))

    if cmd == "offer_vague":
        user.step = AWAITING
        return _out(state, Outgoing(text=t("job_vague", lang)), events=_events(state, ("offer_too_short", "")))

    if bid == "job:agency" or cmd == "agency":
        user.step = "ready"
        return _out(state, report.agency_message(user.home_country, lang))

    if bid == "job:questions":
        user.step = "ready"
        return _out(state, report.questions_message(_missing_from_pending(user.pending_action), lang))

    # ---- photo or PDF
    if msg.kind == "media":
        if msg.media_type not in READABLE_MEDIA:
            return _out(state, Outgoing(text=t("job_media", lang)))
        read, kind = await read_media_from_message(state, config)
        if read.error:
            user.step = AWAITING  # let them simply send it again or paste the text
            mb = round(_settings(config).media_max_bytes / 1_000_000)
            return _out(state, Outgoing(text=t(f"doc_err_{read.error}", lang, mb=mb)),
                        events=_events(state, ("document_unreadable", read.error)))
        kind_word = t(f"doc_kind_{kind}", lang)
        doc_text = read.text or ""
        if not waiting and not looks_like_offer(doc_text):
            return _out(state, Outgoing(text=t("doc_not_offer", lang, kind=kind_word)),
                        events=_events(state, ("document_read", f"source={read.source};offer=no")))
        note = t("doc_read_note", lang, kind=kind_word)
        if read.pages_skipped:
            note += " " + t("doc_pages_skipped", lang, n=_settings(config).pdf_max_pages)
        guard = scan(doc_text, block_threshold=99)   # the document is evidence, never held against the user
        extra = [("document_read", f"source={read.source};offer=yes")]
        if guard.score >= INJECTION_SCORE:
            extra.append(("offer_injection_detected", ",".join(guard.categories)))
        return await _check(state, config, doc_text, guard, prefix=note, extra_events=tuple(extra))

    # ---- pasted text
    if not text or (len(text) < MIN_OFFER_CHARS and not looks_like_offer(text)):
        user.step = AWAITING
        return _out(state, Outgoing(text=t("job_too_short", lang)))

    return await _check(state, config, text, state.get("content_guard"), auto=bool(state.get("auto_offer")))
