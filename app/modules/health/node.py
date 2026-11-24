"""Healthcare navigation (Wellbeing agent). Helps workers use the system:
their insurance rights, where to go, what bills mean, what to ask a doctor,
and reminders for appointments. Rafiq never diagnoses and never suggests a
prescription medicine.

Rules checked on 2026-11-24:
- Since 1 January 2025 health insurance is mandatory for private-sector
  employees and domestic workers in every emirate; the employer (or sponsor)
  pays, at visa issue or renewal (MOHRE health insurance scheme page).
- Dubai: employers must provide and pay for employees' health insurance and
  may not deduct it from salary (Dubai Health Insurance Law, in force 2014).
- Work permits can't be issued or renewed without valid insurance, and cover
  must stay valid for the whole permit (MOHRE guide, 2026).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import S, fmt_date, t
from app.modules.reminders import store as reminders
from app.security.tool_policy import authorize

NODE = "health"
CHECKED = "2026-11-24"

STRINGS: dict[str, dict[str, str]] = {
    "health_menu": {"en": "🩺 *Health*\nI help you use the health system: your insurance, where to go, and what to ask. I don't diagnose. In an emergency call *998*."},
    "health_m_insurance": {"en": "My insurance rights"},
    "health_m_insurance_d": {"en": "Who pays, what it must cover"},
    "health_m_where": {"en": "Where to get care"},
    "health_m_where_d": {"en": "Clinic, pharmacy or emergency?"},
    "health_m_noins": {"en": "No insurance card"},
    "health_m_noins_d": {"en": "Employer hasn't arranged it"},
    "health_m_bill": {"en": "Understand a bill"},
    "health_m_bill_d": {"en": "Co-pay, network, pre-approval..."},
    "health_m_doctor": {"en": "Prepare for a doctor"},
    "health_m_doctor_d": {"en": "What to say and ask"},
    "health_m_appt": {"en": "Appointment reminder"},
    "health_m_appt_d": {"en": "I'll remind you the day before"},
    "health_m_emergency": {"en": "Emergency"},
    "health_m_emergency_d": {"en": "What to do right now"},
    "btn_health": {"en": "Health"},
    "health_insurance": {"en": (
        "🪪 *Your health insurance* (checked {checked})\n"
        "• Every private-sector worker and domestic worker in the UAE must have health insurance, since 1 January 2025 in all emirates.\n"
        "• Your *employer pays*. In Dubai they may not take it from your salary. For domestic workers, the sponsor pays.\n"
        "• Your work permit can't be issued or renewed without valid insurance, and it must stay valid the whole time.\n"
        "• Ask your employer for your *insurance card* (or the app) and the list of clinics in your network.\n\n"
        "Problem with this? Call MOHRE on *80084*."
    )},
    "health_where": {"en": (
        "🏥 *Where to go*\n"
        "• *Life-threatening* (chest pain, can't breathe, heavy bleeding, collapse): call *998* or go to the nearest hospital emergency department.\n"
        "• *Need a doctor today*: a clinic in your insurance network. Show your card and Emirates ID. Your insurer's app or card lists the network.\n"
        "• *Minor problem*: a pharmacist can advise on over-the-counter options. Don't take someone else's prescription medicine.\n"
        "• *Mental health*: you can ask any network clinic for a referral. In crisis, call *999*."
    )},
    "health_noins": {"en": (
        "⚠️ *No insurance card yet?*\n"
        "1. Ask your employer in writing for your insurance card or policy number. It's their legal duty and cost.\n"
        "2. If they don't arrange it, report it to MOHRE (*80084* or the MOHRE app). Not insuring a worker is a violation.\n"
        "3. In an emergency, go to a hospital emergency department anyway, or call *998*. Keep every bill and receipt.\n"
        "Want me to write the request letter for you?"
    )},
    "btn_insurance_letter": {"en": "Write the letter"},
    "health_bill": {"en": (
        "🧾 *Words on medical bills*\n"
        "• *Network*: clinics your insurance has a deal with. Outside it, you may pay everything.\n"
        "• *Co-pay / co-insurance*: the part you pay each visit, e.g. 20% of the bill.\n"
        "• *Deductible*: a fixed amount you pay before insurance pays.\n"
        "• *Pre-approval*: the insurer must agree before some tests or treatments. Ask the clinic to request it.\n"
        "• *Exclusion*: something the policy doesn't cover.\n"
        "• *Claim rejected?* Ask for the reason in writing; you can complain to your insurer and then the health authority."
    )},
    "health_doctor": {"en": (
        "📝 *Before you see the doctor*, write down:\n"
        "• What you feel, where, since when, and what makes it better or worse.\n"
        "• Medicines you take now (bring the boxes) and any allergies.\n"
        "• Ask: What do you think it is? What should I do? Are there side effects? When should I come back?\n"
        "• Ask for a *sick leave certificate* if you need time off. Your employer must accept a valid one.\n"
        "• Don't understand? Ask them to explain again, slowly. You can ask for an interpreter."
    )},
    "health_emergency": {"en": (
        "🚑 *Emergency*: call *998* (ambulance) or *999* (police). Say where you are, what happened, and stay on the line.\n"
        "Emergency departments must treat life-threatening cases. Bring your Emirates ID if you can, but don't wait for it."
    )},
    "health_ask_when": {"en": "When is the appointment? Type the date and time, e.g. *28/11/2026 10:30*."},
    "health_ask_what": {"en": "What is it for, or where? (e.g. *eye clinic, Karama*)"},
    "health_bad_when": {"en": "Please type a future date, e.g. *28/11/2026 10:30*."},
    "health_appt_set": {"en": "✅ Saved: *{what}* on {date}{time}. I'll remind you the day before."},
}
S.update(STRINGS)


def health_menu(lang: str | None) -> Outgoing:
    keys = ("emergency", "where", "insurance", "noins", "bill", "doctor", "appt")
    rows = [ListRow(id=f"health:{k}", title=t(f"health_m_{k}", lang), description=t(f"health_m_{k}_d", lang)) for k in keys]
    return Outgoing(text=t("health_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _back(lang: str | None) -> list[Button]:
    return [Button(id="health:menu", title=t("btn_health", lang)), Button(id="menu:main", title=t("btn_menu", lang))]


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


async def health(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    from app.db import repo

    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_profile")
    action = bid.removeprefix("health:") if bid.startswith("health:") else ""
    events = list(state.get("events", []))

    if not bid and user.step.startswith("health:"):
        kit = repo.toolkit(user)
        draft = kit.get("health_draft") if isinstance(kit.get("health_draft"), dict) else {}
        if user.step == "health:when":
            import re

            d = parse_date(text.split()[0]) if text else None
            tm = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
            if not d or d < today:
                return _out(state, Outgoing(text=t("health_bad_when", lang)))
            repo.update_toolkit(user, health_draft={"d": d.isoformat(), "t": f"{tm.group(1)}:{tm.group(2)}" if tm else ""})
            user.step = "health:what"
            return _out(state, Outgoing(text=t("health_ask_what", lang)))
        if user.step == "health:what":
            what = text[:80] or "Appointment"
            d = date.fromisoformat(draft.get("d", today.isoformat()))
            tm = draft.get("t") or ""
            authorize(NODE, "update_own_reminders")
            when = fmt_date(d, lang)
            remind = max(today, date.fromordinal(d.toordinal() - 1))
            await reminders.add(ctx(config).get("db"), user.id, "appointment", remind,
                                f"Appointment: {what} on {when}{' at ' + tm if tm else ''}. Bring your Emirates ID and insurance card.")
            repo.update_toolkit(user, health_draft=None)
            user.step = "ready"
            return _out(state, Outgoing(text=t("health_appt_set", lang, what=what, date=when, time=f" at {tm}" if tm else ""),
                                        buttons=[Button(id="health:doctor", title=t("health_m_doctor", lang)[:20]), *_back(lang)]),
                        events=[*events, ("appointment_reminder", "")])
    user.step = "ready"
    cmd = state.get("command") or ""
    key = action or {"health_insurance": "insurance", "health_emergency": "emergency", "appointment": "appt"}.get(cmd, "")
    if key in ("insurance", "where", "bill", "doctor", "emergency"):
        extra = [Button(id="health:noins", title=t("health_m_noins", lang))] if key == "insurance" else []
        return _out(state, Outgoing(text=t(f"health_{key}", lang, checked=CHECKED), buttons=[*extra, *_back(lang)][:3]),
                    events=[*events, ("health_info", key)])
    if key == "noins":
        return _out(state, Outgoing(text=t("health_noins", lang),
                                    buttons=[Button(id="task:form:insurance", title=t("btn_insurance_letter", lang)), *_back(lang)][:3]),
                    events=[*events, ("health_info", "noins")])
    if key == "appt":
        user.step = "health:when"
        return _out(state, Outgoing(text=t("health_ask_when", lang)))
    _ = datetime  # (time parsing above uses plain text)
    return _out(state, health_menu(lang))
