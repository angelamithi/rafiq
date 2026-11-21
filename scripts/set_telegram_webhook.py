"""Register the Telegram webhook (with the secret header) for the dev bot.

    docker compose exec worker python scripts/set_telegram_webhook.py

(Run it in the worker: the web container has no internet access by design.)
"""

import asyncio

import httpx

from app.config import get_settings


async def main() -> None:
    s = get_settings()
    url = f"{s.public_base_url.rstrip('/')}/webhook/telegram"
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/setWebhook",
            json={
                "url": url,
                "secret_token": s.telegram_webhook_secret,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True,
            },
        )
    print("Webhook set" if r.json().get("ok") else f"Failed: {r.json().get('description')}", "->", url)


if __name__ == "__main__":
    asyncio.run(main())
