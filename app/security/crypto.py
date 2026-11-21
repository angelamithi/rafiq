"""Field-level encryption and identity hashing.

- Phone numbers / chat ids are never stored in plain text. We store:
  * an HMAC hash (for lookup), and
  * a Fernet-encrypted copy (only needed to send reminders later).
- Personal free-text fields (name, visa expiry) are encrypted at rest.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

log = logging.getLogger(__name__)

_DEV_KEY: bytes | None = None
_DEV_PEPPER = "dev-only-pepper-do-not-use-in-production-0000"


def _fernet() -> Fernet:
    global _DEV_KEY
    key = get_settings().field_encryption_key
    if not key:
        if get_settings().is_production:
            raise RuntimeError("FIELD_ENCRYPTION_KEY is required in production")
        if _DEV_KEY is None:
            _DEV_KEY = Fernet.generate_key()
            log.warning("FIELD_ENCRYPTION_KEY not set: using a temporary dev key (data unreadable after restart)")
        return Fernet(_DEV_KEY)
    return Fernet(key.encode())


def encrypt(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        log.error("Could not decrypt a field (wrong key?)")
        return None


def hash_identity(channel: str, external_id: str) -> str:
    pepper = get_settings().id_hash_pepper or _DEV_PEPPER
    msg = f"{channel}:{external_id}".encode()
    return hmac.new(pepper.encode(), msg, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
