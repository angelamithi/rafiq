from __future__ import annotations

import logging

from app.security.pii import PIIMaskingFilter


def setup_logging(level: str = "INFO") -> None:
    """Every log line passes through the PII mask, including library logs."""
    handler = logging.StreamHandler()
    handler.addFilter(PIIMaskingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # httpx logs full request URLs, which contain the Telegram bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
