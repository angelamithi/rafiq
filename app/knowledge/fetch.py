"""Safe fetching of official pages for the Rule Monitor.

- Only https, and only hosts on the output guard's official allow-list.
- Every redirect hop is checked BEFORE it is requested.
- Hosts that resolve to private, loopback or link-local addresses are refused
  (no reaching into the server's own network: SSRF).
- Size and time limits; the text is never stored, shown to users or sent to
  an AI. Only extracted numbers (see monitor.py) leave this module.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.security.output_guard import ALLOWED_LINK_DOMAINS

log = logging.getLogger(__name__)

MAX_BYTES = 2_000_000
TIMEOUT = 20
USER_AGENT = "RafiqRuleMonitor/1.0 (+https://rafiq.example; checks official UAE guidance weekly)"


class FetchError(Exception):
    pass


def host_allowed(url: str) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == d or host.endswith("." + d) for d in ALLOWED_LINK_DOMAINS)


async def _resolves_public(host: str) -> bool:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)


async def fetch_text(url: str, http: httpx.AsyncClient | None = None, *, check_dns: bool = True,
                     max_redirects: int = 3) -> str:
    """Fetch an official page and return its visible text."""
    own = http is None
    http = http or httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    try:
        for _ in range(max_redirects + 1):
            if not host_allowed(url):
                raise FetchError("host not allowed")
            if check_dns and not await _resolves_public(urlparse(url).hostname or ""):
                raise FetchError("host does not resolve to a public address")
            async with http.stream("GET", url, follow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = str(r.url.join(r.headers["location"]))
                    continue
                if r.status_code != 200:
                    raise FetchError(f"status {r.status_code}")
                body = bytearray()
                async for chunk in r.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise FetchError("page too large")
                return html_to_text(body.decode(r.encoding or "utf-8", errors="replace"))
        raise FetchError("too many redirects")
    except httpx.HTTPError as e:
        raise FetchError(type(e).__name__) from e
    finally:
        if own:
            await http.aclose()


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):  # type: ignore[no-untyped-def]
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):  # type: ignore[no-untyped-def]
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):  # type: ignore[no-untyped-def]
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()
