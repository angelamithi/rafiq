"""AI model access, provider-agnostic.

Rafiq uses Google Gemini through LangChain:  LLM_MAIN_MODEL=google_genai:gemini-3.7-flash
with the key in GOOGLE_API_KEY. The provider string is a setting, so another
LangChain provider can be swapped in later without code changes.
Everything degrades gracefully: if the model is off, slow or failing, modules
fall back to their rule-based behaviour.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)


def _extra(name: str, level: str) -> dict[str, Any]:
    """Provider-specific options. Gemini 3 gets a thinking level (lower = faster)."""
    if name.startswith("google_genai:") and level:
        return {"thinking_level": level}
    return {}


def _build(name: str, *, timeout: int, level: str) -> Any:
    from langchain.chat_models import init_chat_model

    return init_chat_model(name, temperature=0, timeout=timeout, max_retries=1, **_extra(name, level))


@lru_cache
def get_main_model() -> Any | None:
    s = get_settings()
    if not s.llm_enabled or not s.llm_main_model:
        return None
    try:
        return _build(s.llm_main_model, timeout=s.llm_timeout_seconds, level=s.llm_thinking_level)
    except Exception:  # missing provider package, bad model string, missing key
        log.exception("Could not initialise the AI model; continuing without it")
        return None


@lru_cache
def get_intent_model() -> Any | None:
    """Fast, shallow-thinking model for picking one of Rafiq's fixed topics."""
    s = get_settings()
    if not s.llm_enabled or not s.llm_main_model:
        return None
    try:
        return _build(s.llm_main_model, timeout=s.intent_timeout_seconds, level=s.intent_thinking_level)
    except Exception:
        log.exception("Could not initialise the intent model")
        return None


@lru_cache
def get_doc_model() -> Any | None:
    """Model used to read photos and scanned PDFs (must accept images and PDFs)."""
    s = get_settings()
    if not s.llm_enabled:
        return None
    name = s.llm_doc_model or s.llm_main_model
    if not name:
        return None
    try:
        return _build(name, timeout=s.llm_doc_timeout_seconds, level=s.llm_thinking_level)
    except Exception:
        log.exception("Could not initialise the document-reading model")
        return None
