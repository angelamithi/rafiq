"""Rate limiting, duplicate-message protection and abuse cool-downs.

Backed by Redis in production. Falls back to an in-process store for tests and
local development without Redis.
"""

from __future__ import annotations

import time
from typing import Protocol


class KV(Protocol):
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...
    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None: ...
    async def get(self, key: str) -> str | None: ...
    async def delete(self, *keys: str) -> None: ...


class MemoryKV:
    """Minimal async KV with expiry, for tests/dev."""

    def __init__(self) -> None:
        self._d: dict[str, tuple[str, float | None]] = {}

    def _alive(self, key: str) -> bool:
        item = self._d.get(key)
        if not item:
            return False
        _, exp = item
        if exp is not None and exp < time.time():
            self._d.pop(key, None)
            return False
        return True

    async def incr(self, key: str) -> int:
        val = int(self._d[key][0]) + 1 if self._alive(key) else 1
        exp = self._d[key][1] if self._alive(key) else None
        self._d[key] = (str(val), exp)
        return val

    async def expire(self, key: str, seconds: int) -> None:
        if self._alive(key):
            self._d[key] = (self._d[key][0], time.time() + seconds)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and self._alive(key):
            return None
        self._d[key] = (value, time.time() + ex if ex else None)
        return True

    async def get(self, key: str) -> str | None:
        return self._d[key][0] if self._alive(key) else None

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._d.pop(k, None)


class Limiter:
    def __init__(self, kv: KV, per_minute: int, per_day: int) -> None:
        self.kv, self.per_minute, self.per_day = kv, per_minute, per_day

    async def allow(self, user_key: str) -> tuple[bool, bool]:
        """Returns (allowed, first_time_blocked) so we warn the user only once."""
        now = int(time.time())
        m_key, d_key = f"rl:m:{user_key}:{now // 60}", f"rl:d:{user_key}:{now // 86400}"
        m = await self.kv.incr(m_key)
        if m == 1:
            await self.kv.expire(m_key, 70)
        d = await self.kv.incr(d_key)
        if d == 1:
            await self.kv.expire(d_key, 86_500)
        if m > self.per_minute or d > self.per_day:
            first = (m == self.per_minute + 1) or (d == self.per_day + 1)
            return False, first
        return True, False

    async def first_time_seen(self, message_id: str) -> bool:
        """WhatsApp retries webhooks; process each message id once."""
        return bool(await self.kv.set(f"dedupe:{message_id}", "1", ex=86_400, nx=True))

    async def add_strike(self, user_key: str, threshold: int, cooldown_minutes: int) -> bool:
        """Count guard violations. Returns True when the user enters cool-down."""
        key = f"strikes:{user_key}"
        n = await self.kv.incr(key)
        if n == 1:
            await self.kv.expire(key, 3600)
        if n >= threshold:
            await self.kv.set(f"cooldown:{user_key}", "1", ex=cooldown_minutes * 60)
            await self.kv.delete(key)
            return True
        return False

    async def in_cooldown(self, user_key: str) -> bool:
        return await self.kv.get(f"cooldown:{user_key}") is not None
