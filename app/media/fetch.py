"""Download a photo or document a user sent, safely and in memory only.

- WhatsApp: GET /<media-id>?phone_number_id=<ours> (Meta confirms the media
  belongs to our number), then download the short-lived URL with our token.
  The URL must be https on a Meta host, so a bad response can't make us fetch
  arbitrary addresses (SSRF).
- Telegram: getFile, then download from api.telegram.org only.
- Size is checked from the metadata BEFORE downloading, and again while
  streaming, so a large file is never fully loaded.
- Files are never written to disk or the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

META_MEDIA_HOSTS = ("fbsbx.com", "facebook.com", "whatsapp.net", "fbcdn.net")


class MediaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # too_large | download_failed


@dataclass
class Media:
    data: bytes
    declared_mime: str | None


def _host_ok(url: str, allowed: tuple[str, ...]) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == d or host.endswith("." + d) for d in allowed)


async def _stream_limited(http: httpx.AsyncClient, url: str, headers: dict[str, str], limit: int,
                         allowed: tuple[str, ...], max_redirects: int = 3) -> bytes:
    """Download with a size cap. Redirects are followed by hand, and every hop
    is checked against the allowed hosts BEFORE any request is sent to it."""
    for _ in range(max_redirects + 1):
        if not _host_ok(url, allowed):
            log.warning("Refusing download from an unexpected host")
            raise MediaError("download_failed")
        async with http.stream("GET", url, headers=headers, follow_redirects=False) as r:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = str(r.url.join(r.headers["location"]))
                continue
            if r.status_code != 200:
                raise MediaError("download_failed")
            declared = int(r.headers.get("content-length") or 0)
            if declared > limit:
                raise MediaError("too_large")
            buf = bytearray()
            async for chunk in r.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > limit:
                    raise MediaError("too_large")
            return bytes(buf)
    raise MediaError("download_failed")


async def fetch_whatsapp(media_id: str, http: httpx.AsyncClient) -> Media:
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.whatsapp_access_token}"}
    try:
        meta = await http.get(
            f"https://graph.facebook.com/{s.whatsapp_api_version}/{media_id}",
            params={"phone_number_id": s.whatsapp_phone_number_id},
            headers=headers,
        )
        if meta.status_code != 200:
            raise MediaError("download_failed")
        info = meta.json()
        if int(info.get("file_size") or 0) > s.media_max_bytes:
            raise MediaError("too_large")
        url = info.get("url") or ""
        if not _host_ok(url, META_MEDIA_HOSTS):
            log.warning("Refusing media URL on an unexpected host")
            raise MediaError("download_failed")
        data = await _stream_limited(http, url, headers, s.media_max_bytes, META_MEDIA_HOSTS)
        return Media(data=data, declared_mime=info.get("mime_type"))
    except httpx.HTTPError:
        raise MediaError("download_failed") from None


async def fetch_telegram(file_id: str, http: httpx.AsyncClient) -> Media:
    s = get_settings()
    base = f"https://api.telegram.org/bot{s.telegram_bot_token}"
    try:
        r = await http.get(f"{base}/getFile", params={"file_id": file_id})
        body = r.json() if r.status_code == 200 else {}
        result = body.get("result") or {}
        if not body.get("ok") or not result.get("file_path"):
            raise MediaError("download_failed")
        if int(result.get("file_size") or 0) > s.media_max_bytes:
            raise MediaError("too_large")
        path = str(result["file_path"]).lstrip("/")
        if ".." in path:
            raise MediaError("download_failed")
        url = f"https://api.telegram.org/file/bot{s.telegram_bot_token}/{path}"
        return Media(data=await _stream_limited(http, url, {}, s.media_max_bytes, ("api.telegram.org",)), declared_mime=None)
    except httpx.HTTPError:
        raise MediaError("download_failed") from None


async def fetch_media(channel: str, media_id: str, http: httpx.AsyncClient | None = None) -> Media:
    if not media_id:
        raise MediaError("download_failed")
    own = http is None
    http = http or httpx.AsyncClient(timeout=30, follow_redirects=False)
    try:
        if channel == "whatsapp":
            return await fetch_whatsapp(media_id, http)
        if channel == "telegram":
            return await fetch_telegram(media_id, http)
        if channel == "web":
            from app.channels.web import load_media

            data = await load_media(media_id)
            if not data:
                raise MediaError("download_failed")
            return Media(data=data, declared_mime=None)
        raise MediaError("download_failed")
    finally:
        if own:
            await http.aclose()
