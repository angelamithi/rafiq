"""LangGraph node for Module 3: Stay Legal.

All answers are fixed, sourced text (content.py). No AI writes any of it.
The only AI use is reading a photo of a medicine box, and that text is only
matched against our list, never shown or obeyed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent import ui
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import t
from app.media.flow import read_media_from_message
from app.modules.stay_legal import content  # noqa: F401  (registers the text)
from app.modules.stay_legal.content import EDE, MOHRE, U_AE_PART_TIME
from app.modules.stay_legal.medicines import check_medicine, find_medicines
from app.modules.stay_legal.visa import visa_check_message, visa_status
from app.security.tool_policy import authorize

AWAIT_MEDICINE = "legal:await_medicine"

WORK = ("visit", "later", "second", "family", "heat")
POST = ("people", "accident", "news", "complaint", "fundraise")

_VISIT_WORK = re.compile(r"\b(visit|tourist)\s+visa\b.*\b(work|working|job|employ\w*|start)\b|\b(work|working|job)\b.*\b(visit|tourist)\s+visa\b", re.I | re.S)


def legal_intent(text: str) -> str | None:
    """Free-text questions Stay Legal can answer directly."""
    if not text or len(text) > 300:
        return None
    if _VISIT_WORK.search(text):
        return "work_visit"
    if find_medicines(text):
        return "medicine"
    return None


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _events(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _back(lang: str | None, *extra: Button) -> list[Button]:
    return [*extra, Button(id="menu:legal", title=t("btn_legal_menu", lang)), Button(id="menu:main", title=t("btn_menu", lang))][:3]


def legal_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"legal:{k}", title=t(f"legal_{k}", lang), description=t(f"legal_{k}_d", lang))
            for k in ("visa", "work", "med", "post", "rules")]
    return Outgoing(text=t("legal_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def work_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"work:{k}", title=t(f"work_{k}", lang), description=t(f"work_{k}_d", lang)) for k in WORK]
    return Outgoing(text=t("work_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def post_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"post:{k}", title=t(f"post_{k}", lang), description=t(f"post_{k}_d", lang)) for k in POST]
    return Outgoing(text=t("post_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def work_answer(key: str, lang: str | None) -> Outgoing:
    body = t(f"ans_work_{key}", lang, mohre=MOHRE, u_ae=U_AE_PART_TIME)
    return Outgoing(text=f"{body}\n\n{t('legal_footer', lang)}",
                    buttons=_back(lang, Button(id="legal:work", title=t("legal_work", lang))))


def post_answer(key: str, lang: str | None) -> Outgoing:
    body = t(f"ans_post_{key}", lang)
    return Outgoing(text=f"{body}\n\n{t('legal_footer', lang)}",
                    buttons=_back(lang, Button(id="legal:post", title=t("legal_post", lang))))


def rules_message(lang: str | None) -> Outgoing:
    return Outgoing(text=t("rules_list", lang, mohre=MOHRE, ede=EDE) + "\n\n" + t("legal_footer", lang), buttons=_back(lang))


def medicine_prompt(lang: str | None) -> Outgoing:
    return Outgoing(text=t("med_prompt", lang), buttons=_back(lang))


def medicine_result(text: str, lang: str | None, *, from_photo: bool = False) -> tuple[Outgoing, str]:
    m = check_medicine(text)
    if m.status == "unknown" and from_photo:
        body = t("med_unknown_photo", lang, ede=EDE)
    else:
        key = f"med_{m.status}"
        if m.status in ("controlled", "common") and m.ingredient.split(" (")[0].lower() == m.name.lower():
            key += "_same"   # "Tramadol is controlled", not "Tramadol contains tramadol"
        body = t(key, lang, name=m.name, ingredient=m.ingredient, group=m.group, ede=EDE)
    msg = Outgoing(text=f"{body}\n\n{t('med_disclaimer', lang)}",
                   buttons=_back(lang, Button(id="legal:med", title=t("btn_med_another", lang))))
    return msg, m.status


async def stay_legal(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    lang = user.language
    msg = state["incoming"]
    bid = msg.button_id or ""
    cmd = state.get("command")
    text = state.get("text", "")
    today: date = ctx(config).get("today") or date.today()

    # ---- menus and views
    if bid == "menu:legal" or cmd == "legal":
        user.step = "ready"
        return _out(state, legal_menu(lang))
    if bid == "legal:visa" or cmd == "visa":
        user.step = "ready"
        authorize("stay_legal", "get_own_profile")
        return _out(state, visa_status(user, today, lang))
    if bid == "legal:visa_check":
        return _out(state, visa_check_message(lang))
    if bid == "legal:visa_set":
        # Re-use the profile question; afterwards the user returns to this view.
        user.step, user.return_to = "expiry", "visa"
        return _out(state, ui.expiry_prompt(lang))
    if bid == "legal:work" or cmd == "work":
        return _out(state, work_menu(lang))
    if bid.startswith("work:") and bid.split(":", 1)[1] in WORK:
        return _out(state, work_answer(bid.split(":", 1)[1], lang), events=_events(state, ("legal_answer", bid)))
    if cmd == "work_visit":
        return _out(state, work_answer("visit", lang), events=_events(state, ("legal_answer", "work:visit")))
    if bid == "legal:post" or cmd == "post":
        return _out(state, post_menu(lang))
    if bid.startswith("post:") and bid.split(":", 1)[1] in POST:
        return _out(state, post_answer(bid.split(":", 1)[1], lang), events=_events(state, ("legal_answer", bid)))
    if bid == "legal:rules" or cmd == "rules":
        return _out(state, rules_message(lang))
    if bid == "legal:med" or cmd == "medicine_prompt":
        user.step = AWAIT_MEDICINE
        return _out(state, medicine_prompt(lang))

    # ---- medicine check (typed name, a question mentioning a medicine, or a photo)
    if msg.kind == "media":
        if msg.media_type not in ("image", "document"):
            return _out(state, Outgoing(text=t("job_media", lang)))
        read, _kind = await read_media_from_message(state, config)
        if read.error:
            user.step = AWAIT_MEDICINE
            return _out(state, Outgoing(text=t(f"doc_err_{read.error}", lang, mb=10)))
        authorize("stay_legal", "check_medicine")
        user.step = "ready"
        result, status = medicine_result(read.text or "", lang, from_photo=True)
        return _out(state, result, events=_events(state, ("medicine_checked", f"status={status};photo=yes")))

    if text and (user.step == AWAIT_MEDICINE or cmd == "medicine"):
        authorize("stay_legal", "check_medicine")
        user.step = "ready"
        result, status = medicine_result(text, lang)
        return _out(state, result, events=_events(state, ("medicine_checked", f"status={status};photo=no")))

    user.step = "ready"
    return _out(state, legal_menu(lang))
