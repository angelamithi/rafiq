"""Trusted services directory (Life admin agent).

Three tiers, always shown, never mixed up:
- Official: a UAE or home-country government body.
- Licensed: a type of business that must hold a licence; Rafiq shows HOW to
  check the licence instead of naming a business. No business is listed until
  it has been verified (see `PARTNERS`, empty until checks are done).
- Community: free help run by communities. Shown as "not checked by Rafiq".
Rafiq never labels an unverified provider as safe, and takes no money for
listings shown to workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import S, t
from app.security.tool_policy import authorize

NODE = "services"


@dataclass(frozen=True)
class Service:
    name: str
    tier: str          # official | licensed | community
    what: str
    how: str           # phone, website or how to check


NEEDS: dict[str, tuple[str, tuple[Service, ...]]] = {
    "work": ("Work problems, unpaid salary", (
        Service("MOHRE (Ministry of Human Resources and Emiratisation)", "official",
                "Labour complaints, contracts, work permits, domestic workers", "Call 80084, the MOHRE app, or mohre.gov.ae"),
        Service("Tadbeer centres", "official", "Domestic worker services and complaints", "Listed on mohre.gov.ae"),
    )),
    "safety": ("Safety, abuse, trafficking", (
        Service("Police", "official", "Emergencies", "999 (emergency), 901 (non-emergency, Dubai)"),
        Service("Human trafficking hotline (800 SAVE)", "official", "Trafficking and forced labour, many languages", "800 7283"),
        Service("Dubai Foundation for Women and Children", "official", "Shelter and support for women and children", "800 111, call or WhatsApp"),
    )),
    "visa": ("Visa, ID and residency", (
        Service("ICP (Federal Authority for Identity, Citizenship, Customs and Port Security)", "official",
                "Emirates ID, residency (most emirates)", "icp.gov.ae or the UAEICP app"),
        Service("GDRFA Dubai", "official", "Dubai residency and visas", "gdrfad.gov.ae"),
        Service("Typing centres (Amer, Tasheel)", "licensed", "Help filing government applications",
                "Use official centres listed on amer.ae or tas-heel.ae; check fees on the official site before paying"),
    )),
    "housing": ("Housing and rent", (
        Service("Dubai Land Department and Rental Disputes Centre", "official", "Ejari, rent index, tenancy disputes", "dubailand.gov.ae"),
        Service("Real estate brokers", "licensed", "Finding a place to rent",
                "Ask for the broker's licence number and check it with the Dubai Land Department before paying any fee"),
    )),
    "health": ("Health", (
        Service("Ambulance", "official", "Emergencies", "998"),
        Service("Dubai Health Authority", "official", "Health services and licensed facilities in Dubai", "dha.gov.ae"),
        Service("Ministry of Health and Prevention", "official", "Health services in the other emirates", "mohap.gov.ae"),
    )),
    "money": ("Sending money, banking", (
        Service("Banks and exchange houses", "licensed", "Transfers, accounts",
                "Check the provider is licensed by the UAE Central Bank (centralbank.ae lists them). Never use street hawala."),
    )),
    "jobs": ("Jobs and recruitment", (
        Service("Recruitment agencies", "licensed", "Placement in jobs",
                "In the UAE, check the agency with MOHRE; at home, with your country's labour authority (type *agency*). Never pay a job fee."),
    )),
    "embassy": ("My embassy", (
        Service("Your embassy or consulate", "official", "Lost passport, legal help, welfare, repatriation", "Type *embassy* for yours"),
    )),
    "community": ("Community and friends", (
        Service("Public libraries and free cultural events", "official", "Free places to meet people", "Type *free things*"),
        Service("Community and faith groups", "community", "Friendship, support, advice",
                "Not checked by Rafiq. Meet in public places, and never pay or hand over documents"),
    )),
}

# Verified private partners (empty until a licence check and a signed agreement exist).
PARTNERS: tuple[Service, ...] = ()

TIER_LABEL = {"official": "🏛️ Official", "licensed": "🔐 Licensed: check before you pay", "community": "👥 Community: not checked by Rafiq"}

STRINGS: dict[str, dict[str, str]] = {
    "svc_menu": {"en": (
        "🧭 *Find trusted help*\nWhat do you need help with?\n\n"
        "🏛️ Official = government · 🔐 Licensed = check the licence first · 👥 Community = not checked by Rafiq"
    )},
    "svc_head": {"en": "🧭 *{need}*"},
    "svc_item": {"en": "{tier}\n*{name}*: {what}\n➜ {how}"},
    "svc_questions": {"en": (
        "*Before you contact a provider, ask:*\n"
        "• What is your licence number? (then check it)\n• What is the full price, in writing?\n"
        "• What do you need from me, and why? (never give your passport)\n• Will I get a receipt?"
    )},
    "btn_services": {"en": "Find help"},
    "menu_grow": {"en": "Work, home & health"},
    "menu_grow_d": {"en": "Career, housing, health, savings, friends"},
    "hub_text": {"en": "🌱 *Work, home & health*\nMove from getting by to getting ahead. What would you like to work on?"},
    "hub_career": {"en": "Career"},
    "hub_career_d": {"en": "Next job, skills, CV, interviews"},
    "hub_housing": {"en": "Housing"},
    "hub_housing_d": {"en": "Check a room before paying, rent rights"},
    "hub_health": {"en": "Health"},
    "hub_health_d": {"en": "Insurance, where to go, appointments"},
    "hub_money": {"en": "Grow my money"},
    "hub_money_d": {"en": "Savings goals, family budget, loans"},
    "hub_friends": {"en": "Friends & wellbeing"},
    "hub_friends_d": {"en": "Meet people, free events, check-ins"},
    "hub_help": {"en": "Find trusted help"},
    "hub_help_d": {"en": "Official and licensed services only"},
    "hub_profile": {"en": "My profile"},
    "hub_profile_d": {"en": "Your details, privacy and your data"},
}
S.update(STRINGS)


def services_menu(lang: str | None) -> Outgoing:
    rows = [ListRow(id=f"svc:{k}", title=label[:24]) for k, (label, _) in NEEDS.items()]
    return Outgoing(text=t("svc_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))


def need_message(key: str, lang: str | None) -> list[Outgoing]:
    label, items = NEEDS[key]
    body = [t("svc_head", lang, need=label)]
    body += [t("svc_item", lang, tier=TIER_LABEL[s.tier], name=s.name, what=s.what, how=s.how) for s in items]
    msgs = [Outgoing(text="\n\n".join(body))]
    if any(s.tier != "official" for s in items):
        msgs.append(Outgoing(text=t("svc_questions", lang)))
    msgs[-1] = msgs[-1].model_copy(update={"buttons": [Button(id="svc:menu", title=t("btn_services", lang)),
                                                       Button(id="menu:main", title=t("btn_menu", lang))]})
    return msgs


async def services(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    authorize(NODE, "get_own_profile")
    bid = msg.button_id or ""
    if state.get("command") == "hub":
        rows = [ListRow(id=i, title=t(f"hub_{k}", lang), description=t(f"hub_{k}_d", lang)) for i, k in (
            ("career:menu", "career"), ("home:menu", "housing"), ("health:menu", "health"), ("grow:menu", "money"),
            ("menu:social", "friends"), ("svc:menu", "help"), ("menu:profile", "profile"))]
        return {"replies": [*state.get("replies", []), Outgoing(text=t("hub_text", lang),
                                                                 menu=ListMenu(button=t("btn_choose", lang), rows=rows))]}
    key = bid.removeprefix("svc:") if bid.startswith("svc:") else ""
    if key in NEEDS:
        return {"replies": [*state.get("replies", []), *need_message(key, lang)],
                "events": [*state.get("events", []), ("service_lookup", key)]}
    return {"replies": [*state.get("replies", []), services_menu(lang)]}
