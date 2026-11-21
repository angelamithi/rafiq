"""The LangGraph agent.

    START -> route -> onboarding | menu | privacy | fallback | job_safety | stay_legal | departure | arrival | pay | social | money | help -> END

Input and output guards run in app/service.py, *outside* the graph, so no
node (and no future AI node) can skip them. Later modules add their own nodes
and routes here.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.modules.arrival.content import TOPICS as ARRIVAL_TOPICS
from app.modules.arrival.node import arrival
from app.modules.departure.node import departure
from app.modules.help.node import help_node, unsafe_intent
from app.modules.job_safety.node import job_safety
from app.modules.money.node import money, money_intent
from app.modules.pay.node import pay
from app.modules.social.node import crisis_intent, social
from app.modules.job_safety.rules import looks_like_offer
from app.modules.stay_legal.node import legal_intent, stay_legal
from app.agent.parsing import simplify
from app.agent.state import AgentState, ctx

COMMANDS: dict[str, set[str]] = {
    "menu": {"menu", "main menu", "home", "options", "0"},
    "help": {"help", "emergency", "help me", "sos"},
    "profile": {"profile", "my profile", "my details"},
    "privacy": {"privacy"},
    "export": {"my data", "see my data", "export", "show my data"},
    "delete": {"delete", "delete my data", "delete account", "erase my data", "delete me"},
    "job": {"check offer", "check an offer", "check job", "check a job", "job offer", "check job offer", "check a job offer",
            "is this job real", "is this offer real", "scam", "is this a scam", "check scam", "job check"},
    "agency": {"check agency", "check an agency", "check recruitment agency", "is this agency real", "agency"},
    "legal": {"stay legal", "legal", "laws", "law", "is it legal"},
    "visa": {"my visa", "visa", "visa status", "visa expiry", "when does my visa expire", "check my visa"},
    "medicine_prompt": {"medicine", "medicines", "medicine check", "check medicine", "check my medicine", "medication"},
    "work": {"can i work", "work rules", "work permit", "part time", "part-time", "second job"},
    "post": {"can i post this", "can i post", "posting rules", "social media rules"},
    "rules": {"rules", "everyday rules", "uae rules", "uae laws"},
    "plan": {"checklist", "my checklist", "before you fly", "before i fly", "before i travel", "departure",
             "departure checklist", "departure planner", "travel checklist", "pre departure", "pre departure checklist",
             "packing", "packing list", "what to pack", "what should i pack", "plan", "my plan", "travel plan"},
    "plan_date": {"travel date", "my travel date", "flight date", "my flight date", "set travel date", "change travel date"},
    "arrive": {"arrival", "arrival guide", "first weeks", "my first weeks", "your first weeks", "just arrived",
               "i just arrived", "i have arrived", "i arrived", "i ve arrived", "new arrival", "settling in", "after arrival"},
    "arrive_date": {"arrival date", "my arrival date", "set arrival date", "change arrival date"},
    "pay": {"pay", "pay and rights", "pay rights", "my pay", "my salary", "salary", "rights", "my rights",
            "workers rights", "work rights", "labour rights", "labor rights"},
    "salary_watch": {"salary watch", "salary record", "my salary record", "salary check", "salary check in"},
    "salary_late": {"salary late", "late salary", "my salary is late", "salary is late", "salary delayed",
                    "delayed salary", "late pay"},
    "pay_paid": {"paid", "salary paid", "i got paid", "got paid", "got my salary", "salary received",
                 "received my salary", "yes paid", "paid in full"},
    "pay_part": {"part", "part paid", "partly paid", "partial", "partial salary", "only part", "half salary",
                 "half paid", "paid part"},
    "pay_unpaid": {"not paid", "not paid yet", "no salary", "salary not paid", "i was not paid", "unpaid",
                   "unpaid salary", "salary not received", "not received"},
    "complaint": {"complaint", "make a complaint", "write a complaint", "file a complaint", "complain",
                  "report my employer", "report employer", "labour complaint", "labor complaint"},
    "gratuity": {"gratuity", "end of service", "end of service pay", "final settlement", "gratuity calculator",
                 "end of service gratuity"},
    "work_hours": {"working hours", "overtime", "annual leave", "leave", "sick leave", "day off", "days off",
                   "rest day", "holidays", "hours"},
    "social": {"friends and wellbeing", "wellbeing", "social", "social circle"},
    "lonely": {"lonely", "i feel lonely", "i am lonely", "im lonely", "i m lonely", "feeling lonely", "so lonely",
               "homesick", "i am homesick", "i m homesick", "i miss home", "i miss my family", "sad", "i feel sad",
               "i am sad", "i m sad", "feeling sad", "depressed", "i feel depressed", "i am depressed", "alone",
               "i feel alone", "i am alone"},
    "free_things": {"free things to do", "things to do", "what to do", "weekend", "free events", "events",
                    "whats on", "what s on", "this weekend"},
    "meet": {"meet people", "make friends", "meet people safely", "friends", "find friends", "community",
             "new friends"},
    "talk": {"talk to someone", "counsellor", "counselor", "mental health", "helpline", "need to talk",
             "i need to talk", "therapist", "someone to talk to"},
    "wellbeing_checkin": {"weekly check in", "wellbeing check in", "check in"},
    "mood_good": {"good", "good week", "great", "great week", "fine", "it was good", "very good"},
    "mood_ok": {"ok", "okay", "ok week", "okay week", "so so", "not bad", "average"},
    "mood_hard": {"hard", "hard week", "bad", "bad week", "not good", "terrible", "awful", "difficult week",
                  "tough week", "very hard", "it was hard"},
    "money": {"money", "money home", "send money home", "remittance", "remittances", "sending money"},
    "send_money": {"send money", "transfer money", "how to send money", "hawala", "exchange house", "send money safely"},
    "compare_costs": {"compare", "compare rates", "exchange rate", "exchange rates", "best rate", "compare transfer",
                      "transfer cost", "transfer costs", "cheapest way to send money"},
    "budget": {"budget", "money plan", "monthly plan", "my budget", "save money", "saving", "savings"},
    "loans": {"loan", "loans", "debt", "debts", "credit card", "borrow money", "i need a loan", "need a loan", "loan app"},
    "money_scams": {"money scam", "money scams", "bank scam", "otp", "fake bank", "bank called me"},
    "rent_account": {"money mule", "rent my account", "rent my bank account", "lend my account"},
    "embassy": {"embassy", "my embassy", "consulate", "my consulate", "embassy contact", "embassy number"},
    "lost_passport": {"lost passport", "i lost my passport", "passport lost", "lost my passport", "stolen passport",
                      "passport stolen", "lost emirates id", "lost my emirates id", "lost id", "lost my id"},
    "report_crime": {"report crime", "report a crime", "al ameen", "report to police"},
    "police_trouble": {"arrested", "i was arrested", "police case", "court case", "jail", "in jail", "detained",
                       "travel ban", "police stopped me"},
    "numbers": {"numbers", "useful numbers", "emergency numbers", "important numbers", "phone numbers"},
    "unsafe": {"not safe", "i am not safe", "i m not safe", "unsafe", "abuse", "i am abused", "human trafficking",
               "trafficking", "help me please", "domestic violence"},
    "stop": {"stop", "unsubscribe", "pause"},
    "start": {"start", "resume"},
    "greeting": {"hi", "hello", "hey", "hiya", "salaam", "salam", "hi rafiq", "hello rafiq",
                 "good morning", "good evening", "good afternoon"},
}
_LOOKUP = {phrase: cmd for cmd, phrases in COMMANDS.items() for phrase in phrases}
# Arrival topics ("emirates id", "ejari"...) open one step; never override a command above.
for _key, _phrases in ARRIVAL_TOPICS.items():
    for _p in _phrases:
        _LOOKUP.setdefault(_p, f"arrive_topic:{_key}")
PRIVACY_COMMANDS = {"privacy", "export", "delete"}
ALWAYS_AVAILABLE = {"help"} | PRIVACY_COMMANDS  # work even in the middle of setup
LEGAL_COMMANDS = {"legal", "visa", "medicine_prompt", "work", "post", "rules"}
PLAN_COMMANDS = {"plan", "plan_date"}
ARRIVE_COMMANDS = {"arrive", "arrive_date"}
SOCIAL_COMMANDS = {"social", "lonely", "free_things", "meet", "talk", "wellbeing_checkin", "mood_good", "mood_ok",
                   "mood_hard"}
HELP_COMMANDS = {"help", "embassy", "lost_passport", "report_crime", "police_trouble", "numbers", "unsafe"}
MONEY_COMMANDS = {"money", "send_money", "compare_costs", "budget", "loans", "money_scams", "rent_account"}
PAY_COMMANDS = {"pay", "salary_watch", "salary_late", "pay_paid", "pay_part", "pay_unpaid", "complaint", "gratuity",
                "work_hours"}


def _is_arrival(command: str | None) -> bool:
    return bool(command) and (command in ARRIVE_COMMANDS or command.startswith("arrive_topic:"))


# Natural speech ("can you please check my job offer") rarely matches a command
# exactly, especially from voice notes. Fillers are removed from both sides.
_FILLERS = re.compile(
    r"\b(please|pls|plz|kindly|thanks?|thank you|rafiq|hi|hello|hey|ok|okay|so|um+|uh+|"
    r"can you|could you|would you|will you|i want to|i would like to|i d like to|i need to|i wanna|"
    r"help me|tell me|show me|let me|how do i|i want|i need|my|a|an|the|me|for|about)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _FILLERS.sub(" ", simplify(text))).strip()


_LOOKUP_NORM: dict[str, str] = {}
for _phrase, _cmd in _LOOKUP.items():
    if (_n := _norm(_phrase)) and len(_n) >= 3:
        _LOOKUP_NORM.setdefault(_n, _cmd)


def detect_command(text: str) -> str | None:
    s = simplify(text)
    if s in _LOOKUP:
        return _LOOKUP[s]
    if len(s) > 80:          # long messages are content, not commands
        return None
    n = _norm(text)
    return _LOOKUP_NORM.get(n) if len(n) >= 3 else None


def _rule_route(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    msg = state["incoming"]
    settings = ctx(config).get("settings")
    command = detect_command(state.get("text", "")) if msg.kind == "text" else None
    bid = msg.button_id or ""
    prefix = bid.split(":", 1)[0] if bid else ""

    # Safety net, before anything else (even mid-setup): mentions of suicide or
    # self-harm always get support lines first. Nothing is stored about it.
    if msg.kind == "text" and crisis_intent(state.get("text", "")):
        return {"command": "crisis", "route": "social"}
    # Same for abuse, confinement, forced work or trafficking.
    if msg.kind == "text" and unsafe_intent(state.get("text", "")):
        return {"command": "unsafe_detected", "route": "help"}

    if user.step == "new":
        return {"command": None, "route": "onboarding"}

    # Privacy notice changed since the user agreed: ask again before anything else.
    current = getattr(settings, "privacy_policy_version", None)
    if user.consent_status == "granted" and current and user.consent_version != current and user.step == "ready":
        user.step, user.return_to = "consent", "ready"
        return {"command": None, "route": "onboarding", "reconsent": True}

    if prefix in ("privacy", "delete"):
        return {"command": command, "route": "privacy"}
    if bid == "menu:job" or prefix == "job":
        return {"command": command, "route": "job_safety"}
    if bid == "menu:legal" or prefix in ("legal", "work", "post"):
        return {"command": command, "route": "stay_legal"}
    if bid == "menu:plan" or prefix == "plan":
        return {"command": command, "route": "departure"}
    if bid == "menu:arrive" or prefix == "arrive":
        return {"command": command, "route": "arrival"}
    if bid == "menu:pay" or prefix == "pay":
        return {"command": command, "route": "pay"}
    if bid == "menu:social" or prefix == "social":
        return {"command": command, "route": "social"}
    if bid == "menu:money" or prefix == "money":
        return {"command": command, "route": "money"}
    if (bid == "menu:help" or prefix == "help") and user.step not in nodes.ONBOARDING_STEPS:
        return {"command": command, "route": "help"}
    if prefix in ("menu", "profile"):
        return {"command": command, "route": "menu"}

    # Modules 2-5: waiting for a job offer / a medicine / a date. Global
    # commands still work; anything else is the thing we're waiting for.
    if user.step.startswith(("job:", "legal:", "plan:", "arrive:", "pay:", "money:")):
        if command in PRIVACY_COMMANDS:
            return {"command": command, "route": "privacy"}
        if command in PLAN_COMMANDS:
            return {"command": command, "route": "departure"}
        if _is_arrival(command):
            return {"command": command, "route": "arrival"}
        if command in PAY_COMMANDS:
            return {"command": command, "route": "pay"}
        if command in SOCIAL_COMMANDS:
            return {"command": command, "route": "social"}
        if command in MONEY_COMMANDS:
            return {"command": command, "route": "money"}
        if command in HELP_COMMANDS:
            return {"command": command, "route": "help"}
        if command in LEGAL_COMMANDS:
            user.step = "ready"
            return {"command": command, "route": "stay_legal"}
        if command in ("menu", "help", "profile", "stop", "start", "greeting", "agency", "job"):
            user.step = "ready"
            return {"command": command, "route": "job_safety" if command in ("agency", "job") else "menu"}
        if user.step.startswith("legal:"):
            return {"command": "medicine", "route": "stay_legal"}
        if user.step.startswith("plan:"):
            return {"command": "travel_date", "route": "departure"}
        if user.step.startswith("arrive:"):
            return {"command": "arrival_date", "route": "arrival"}
        if user.step.startswith("pay:"):
            return {"command": "gratuity_input", "route": "pay"}
        if user.step.startswith("money:"):
            return {"command": "money_input", "route": "money"}
        return {"command": "offer", "route": "job_safety"}

    if user.step != "ready":
        if command in ALWAYS_AVAILABLE:
            return {"command": command, "route": "privacy" if command in PRIVACY_COMMANDS else "menu"}
        if command in ("menu", "greeting", "profile", "stop", "start") and user.consent_status == "granted":
            return {"command": command, "route": "menu"}
        return {"command": command, "route": "onboarding"}

    if command in PRIVACY_COMMANDS:
        return {"command": command, "route": "privacy"}
    if command in ("job", "agency"):
        return {"command": command, "route": "job_safety"}
    if command in LEGAL_COMMANDS:
        return {"command": command, "route": "stay_legal"}
    if command in PLAN_COMMANDS:
        return {"command": command, "route": "departure"}
    if _is_arrival(command):
        return {"command": command, "route": "arrival"}
    if command in PAY_COMMANDS:
        return {"command": command, "route": "pay"}
    if command in SOCIAL_COMMANDS:
        return {"command": command, "route": "social"}
    if command in MONEY_COMMANDS:
        return {"command": command, "route": "money"}
    if command in HELP_COMMANDS:
        return {"command": command, "route": "help"}
    if command:
        return {"command": command, "route": "menu"}
    if msg.kind == "text" and looks_like_offer(state.get("text", "")):
        return {"command": "offer", "route": "job_safety", "auto_offer": True}
    if msg.kind == "text" and (intent := legal_intent(state.get("text", ""))):
        return {"command": intent, "route": "stay_legal"}
    if msg.kind == "text" and (intent := money_intent(state.get("text", ""))):
        return {"command": intent, "route": "money"}
    if msg.kind == "media" and msg.media_type in ("image", "document"):
        return {"command": "offer", "route": "job_safety"}  # a photo/PDF is most likely an offer to check
    return {"command": None, "route": "fallback"}


async def route(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Rules first (fast, predictable, safety nets). Only if they don't recognise
    a typed message does the AI pick a topic, from a fixed list (app/agent/intent.py)."""
    decided = _rule_route(state, config)
    user, msg = state["user"], state["incoming"]
    if decided.get("route") != "fallback" or msg.kind != "text" or user.step != "ready":
        return decided
    from app.agent.intent import understand
    from app.config import get_settings

    cfg = ctx(config)
    found = await understand(state.get("text", ""), user=user, cfg=cfg, settings=cfg.get("settings") or get_settings())
    if found is None:
        return decided
    return {"command": found.command, "route": found.route, "inferred_topic": found.topic,
            "events": [*state.get("events", []), ("intent_ai", found.command)]}


def _pick(state: AgentState) -> str:
    return state["route"]


@lru_cache
def build_graph():  # type: ignore[no-untyped-def]
    g = StateGraph(AgentState)
    g.add_node("route", route)
    g.add_node("onboarding", nodes.onboarding)
    g.add_node("menu", nodes.menu)
    g.add_node("privacy", nodes.privacy)
    g.add_node("fallback", nodes.fallback)
    g.add_node("job_safety", job_safety)
    g.add_node("stay_legal", stay_legal)
    g.add_node("departure", departure)
    g.add_node("arrival", arrival)
    g.add_node("pay", pay)
    g.add_node("social", social)
    g.add_node("money", money)
    g.add_node("help", help_node)
    g.add_edge(START, "route")
    routes = ["onboarding", "menu", "privacy", "fallback", "job_safety", "stay_legal", "departure", "arrival", "pay", "social", "money", "help"]
    g.add_conditional_edges("route", _pick, routes)
    for n in routes:
        g.add_edge(n, END)
    return g.compile()
