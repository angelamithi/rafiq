from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig

from app.channels.base import Incoming, Outgoing
from app.db.models import User


class AgentState(TypedDict, total=False):
    incoming: Incoming
    text: str                 # cleaned user text ("" for buttons/media)
    user: User                # resolved from the VERIFIED webhook identity only
    is_new: bool
    command: str | None       # detected typed command, if any
    route: str                # onboarding | menu | privacy | fallback | job_safety | stay_legal | departure | arrival | pay | social | money | help
    replies: list[Outgoing]
    delete_user: bool         # set by the privacy node after a confirmed delete
    reconsent: bool           # privacy notice changed; show the "updated" consent screen
    content_guard: Any        # injection scan of a pasted document (job offer), never blocks
    inferred_topic: str       # set when the AI (not the rules) picked the topic
    auto_offer: bool          # a pasted job offer was detected without the user asking
    agent: str                     # which specialist handled the message (app/agent/agents.py)
    outbox: list[dict[str, Any]]  # SOS messages for the user's trusted contact (channel, to, out, template)
    events: list[tuple[str, str]]  # audit events (event, detail) to record; never message text


def ctx(config: RunnableConfig) -> dict[str, Any]:
    """Server-side context passed through LangGraph's config (settings, clock).
    Nodes never receive identity from the model or from message text."""
    return config.get("configurable", {})
