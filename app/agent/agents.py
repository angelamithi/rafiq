"""Rafiq's agents: one orchestrator and six specialists.

Rafiq is ONE LangGraph graph and ONE AI model (cheaper, fewer moving parts and
less attack surface than six separate LLM agents). The orchestrator is the
`route` node: it checks consent and safety first, then picks the specialist.
Each specialist is a group of nodes with its OWN tool allow-list
(app/security/tool_policy.py), so, for example, the Financial agent can never
open a saved passport and only the Protection agent can send anything outward.

This file is the single source of truth for that grouping. The agent card in
the README and the judges' demo are generated from it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    key: str
    title: str
    purpose: str
    nodes: tuple[str, ...]          # graph nodes this agent owns
    task_actions: tuple[str, ...]   # "Do it for me" actions it owns (tasks node)
    never: tuple[str, ...]          # stated limits, shown to judges and users
    live: bool = True


AGENTS: dict[str, Agent] = {
    "orchestrator": Agent(
        "orchestrator", "Rafiq orchestrator",
        "Checks consent, then crisis and abuse signs first; rules pick the specialist, the AI picks only "
        "from a fixed list when the rules can't.",
        ("onboarding", "menu", "privacy", "fallback", "tasks"), (),
        ("acts on another person's data", "lets the AI choose a tool or write advice"),
    ),
    "employment": Agent(
        "employment", "Employment agent",
        "Job offer and contract checks, salary watch and gaps, evidence packs, letters and dispute cases.",
        ("job_safety", "pay", "cases"), ("pack", "forms", "contract"),
        ("contacts an employer, recruiter or office", "submits a complaint for the worker",
         "opens saved ID documents", "gives a legal ruling"),
    ),
    "protection": Agent(
        "protection", "Protection agent",
        "Crisis and abuse detection, exploitation early warning, incident records, emergency help and SOS.",
        ("help", "protection"), ("sos",),
        ("sends an SOS without the worker's confirmation", "messages anyone but the opted-in trusted contact",
         "decides for the worker whether to leave or report"),
    ),
    "life_admin": Agent(
        "life_admin", "Life admin agent",
        "Renewals calendar (visa, Emirates ID, passport, tenancy) with document checks and reminders, legal status, "
        "journey checklists, document vault, housing, trusted services and the Life Manager brief.",
        ("renewals", "stay_legal", "departure", "arrival", "life", "housing", "services"), ("vault", "status", "brief"),
        ("files a visa or renewal application", "shares a saved document with anyone"),
    ),
    "financial": Agent(
        "financial", "Financial agent",
        "Sending money home, budgets, savings goals, loan costs, rate alerts and financial scam checks.",
        ("money", "growth"), ("rate",),
        ("moves or holds money", "opens saved documents", "recommends a specific lender"),
    ),
    "wellbeing": Agent(
        "wellbeing", "Wellbeing agent",
        "Friends, free events, opt-in weekly check-ins and healthcare navigation. Crisis words go to the Protection agent.",
        ("social", "health"), (),
        ("diagnoses or suggests prescription medicine", "opens documents or salary records"),
    ),
    "career": Agent(
        "career", "Career agent (roadmap)",
        "Skills gap to a target job, 90-day plan, CV, application and interview tracker, safe job search.",
        ("career",), (), ("applies for a job or contacts an employer", "opens saved documents or salary records"),
    ),
}

ROUTE_AGENT: dict[str, str] = {node: a.key for a in AGENTS.values() for node in a.nodes}
TASK_AGENT: dict[str, str] = {act: a.key for a in AGENTS.values() for act in a.task_actions}


def task_agent(action: str) -> str:
    """Which agent owns a "Do it for me" action (button id after 'task:' or typed command)."""
    head = action.split(":", 1)[0]
    for prefix, agent in (("pack", "employment"), ("form", "employment"), ("contract", "employment"),
                          ("vault", "life_admin"), ("vk", "life_admin"), ("doc", "life_admin"),
                          ("status", "life_admin"), ("brief", "life_admin"),
                          ("sos", "protection"), ("rate", "financial")):
        if head.startswith(prefix):
            return agent
    return "orchestrator"


def agent_for(route: str, command: str | None = None, button_id: str | None = None, step: str | None = None) -> str:
    if route == "tasks":
        if button_id and button_id.startswith("task:"):
            return task_agent(button_id[5:])
        if command == "task_input" and step and step.startswith("task:"):
            return task_agent(step[5:])
        cmd_map = {"pack": "employment", "forms": "employment", "contract": "employment", "vault": "life_admin",
                   "task_status": "life_admin", "sos": "protection", "sos_menu": "protection",
                   "sos_join": "protection", "sos_leave": "protection", "location": "protection", "rate": "financial"}
        return cmd_map.get(command or "", "orchestrator")
    if route == "social" and command == "crisis":
        return "protection"
    return ROUTE_AGENT.get(route, "orchestrator")


def agent_card_markdown() -> str:
    lines = ["| Agent | What it does | Never |", "| --- | --- | --- |"]
    for a in AGENTS.values():
        lines.append(f"| {a.title} | {a.purpose} | {'; '.join(a.never)} |")
    return "\n".join(lines)
