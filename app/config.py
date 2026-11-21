"""Central configuration. Every secret comes from the .env file on the VPS
(or real environment variables). Nothing secret is ever hard-coded."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_env: str = Field("development", description="development | production | test")
    log_level: str = "INFO"
    public_base_url: str = "https://example.com"

    # Process messages in the Redis-backed worker (production). If false, the web
    # process handles them in a background task (simple local development).
    use_queue: bool = True
    max_webhook_body_bytes: int = 512_000

    # --- Storage ---
    database_url: str = "sqlite+aiosqlite:///./rafiq_dev.db"
    redis_url: str = "redis://localhost:6379/0"

    # --- WhatsApp Cloud API ---
    whatsapp_enabled: bool = False
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v23.0"
    # Pre-approved "utility" template for visa reminders (needed to message users
    # more than 24h after their last message). Empty = WhatsApp reminders off.
    whatsapp_visa_template: str = ""
    whatsapp_departure_template: str = ""   # approved template for "you fly in N days" reminders
    whatsapp_arrival_template: str = ""     # approved template for "finish your residence visa" reminders
    whatsapp_pay_template: str = ""         # approved template for monthly "did you get your salary?" check-ins
    # AI intent understanding for messages the rules don't recognise (picks a topic only).
    intent_ai_enabled: bool = True
    intent_ai_per_day: int = 50

    # --- "Do it for me" tasks ---
    tasks_enabled: bool = True
    fx_url: str = "https://open.er-api.com/v6/latest/AED"   # host must be in app/modules/tasks/rates.py ALLOWED_HOSTS
    # Voice notes (Language & Voice): transcribed and translated to English by the doc model (Gemini).
    voice_enabled: bool = True
    voice_max_bytes: int = 3_000_000
    voice_max_seconds: int = 180
    voice_per_day: int = 30
    # Rule Monitor: weekly checks of official sources; alerts go to this Telegram chat (team only).
    rule_monitor_enabled: bool = True
    admin_telegram_chat_id: str = ""
    whatsapp_social_template: str = ""      # approved template for the opt-in weekly "how was your week?" check-in
    whatsapp_vault_template: str = ""       # "Do it for me": a saved document is about to expire
    whatsapp_rate_template: str = ""        # "Do it for me": exchange-rate alert reached
    whatsapp_sos_template: str = ""         # "Do it for me": SOS to a trusted contact (outside the 24 h window)
    whatsapp_public_number: str = ""        # e.g. 9715XXXXXXXX, for wa.me invite links (digits only)
    whatsapp_template_language: str = "en"

    # --- Telegram (development channel) ---
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""         # without @, for t.me invite links
    telegram_webhook_secret: str = ""

    # --- AI model: Google Gemini (key in GOOGLE_API_KEY). Rules still work if it's off. ---
    llm_enabled: bool = False
    llm_main_model: str = "google_genai:gemini-3.7-flash"
    llm_doc_model: str = ""            # optional separate model for reading photos/PDFs; empty = main model
    llm_timeout_seconds: int = 20
    llm_doc_timeout_seconds: int = 45
    # Gemini 3 "thinking" depth. Lower = faster replies. minimal | low | medium | high ; empty = model default
    llm_thinking_level: str = "low"
    intent_thinking_level: str = "minimal"   # picking 1 of 33 labels needs no deep thinking
    intent_timeout_seconds: int = 10

    # --- Photos and PDFs ---
    media_max_bytes: int = 10_000_000  # 10 MB
    pdf_max_pages: int = 5

    # --- Security ---
    field_encryption_key: str = ""  # Fernet key: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
    id_hash_pepper: str = ""        # long random string: python -c "import secrets;print(secrets.token_urlsafe(48))"
    rate_limit_per_minute: int = 20
    rate_limit_per_day: int = 300
    max_message_chars: int = 4000   # WhatsApp allows 4096; job offers can be long
    guard_strikes_before_cooldown: int = 3
    guard_cooldown_minutes: int = 30

    # --- Privacy ---
    privacy_policy_version: str = "2026-11-21.1"  # v10: "Do it for me" (documents, employer/salary, trusted contact)
    data_retention_days_inactive: int = 365

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            missing = [
                name
                for name in ("field_encryption_key", "id_hash_pepper")
                if not getattr(self, name)
            ]
            if self.whatsapp_enabled:
                missing += [
                    n
                    for n in (
                        "whatsapp_access_token",
                        "whatsapp_phone_number_id",
                        "whatsapp_verify_token",
                        "whatsapp_app_secret",
                    )
                    if not getattr(self, n)
                ]
            if self.telegram_enabled:
                missing += [
                    n for n in ("telegram_bot_token", "telegram_webhook_secret") if not getattr(self, n)
                ]
            if missing:
                raise ValueError(f"Missing required settings in .env: {', '.join(missing)}")
            if len(self.id_hash_pepper) < 32:
                raise ValueError("ID_HASH_PEPPER must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
