"""Shared helper: download and read the photo/PDF in the current message."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.state import AgentState, ctx
from app.media.fetch import MediaError, fetch_media
from app.media.reader import ReadResult, read_document, sniff


def _settings(config: RunnableConfig) -> Any:
    from app.config import get_settings

    return ctx(config).get("settings") or get_settings()


async def read_media_from_message(state: AgentState, config: RunnableConfig) -> tuple[ReadResult, str]:
    """Download (in memory) and read the user's photo/PDF. Returns (result, kind)
    where kind is "photo" or "pdf". The file bytes are never stored."""
    msg = state["incoming"]
    settings = _settings(config)
    loader = ctx(config).get("media_loader") or fetch_media
    try:
        media = await loader(msg.channel, msg.media_id or "")
    except MediaError as e:
        return ReadResult(error=e.code), "photo"
    kind = "pdf" if sniff(media.data) == "application/pdf" else "photo"
    model = ctx(config).get("doc_model", "default")
    if model == "default":
        from app.agent.llm import get_doc_model

        model = get_doc_model()
    result = await read_document(media.data, model=model, max_bytes=settings.media_max_bytes,
                                 max_pages=settings.pdf_max_pages, timeout=float(settings.llm_doc_timeout_seconds))
    return result, kind
