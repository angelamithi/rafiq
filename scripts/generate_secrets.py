"""Print fresh secrets to paste into .env. Run once per server.

    docker compose run --rm --no-deps web python scripts/generate_secrets.py
    (or: python3 scripts/generate_secrets.py, if the cryptography package is installed)
"""

import secrets

from cryptography.fernet import Fernet

print(f"FIELD_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"ID_HASH_PEPPER={secrets.token_urlsafe(48)}")
print(f"WHATSAPP_VERIFY_TOKEN={secrets.token_urlsafe(24)}")
print(f"TELEGRAM_WEBHOOK_SECRET={secrets.token_urlsafe(32)}")
pg = secrets.token_urlsafe(24)
rd = secrets.token_urlsafe(24)
print(f"POSTGRES_PASSWORD={pg}")
print(f"DATABASE_URL=postgresql+asyncpg://rafiq:{pg}@postgres:5432/rafiq")
print(f"REDIS_PASSWORD={rd}")
print(f"REDIS_URL=redis://:{rd}@redis:6379/0")
print("\n# Keep FIELD_ENCRYPTION_KEY and ID_HASH_PEPPER safe and backed up: without them the saved data cannot be read.")
