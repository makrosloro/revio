from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str
    DATABASE_URL: str
    WEBHOOK_URL: str

    GOOGLE_PLACES_API_KEY: str
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRO_PRICE_ID: str
    STRIPE_MULTI_PRICE_ID: str

    ANTHROPIC_API_KEY: str

    BOT_ADMIN_CHAT_ID: int
    DAILY_DIGEST_HOUR: int = 21
    POLLING_INTERVAL_HOURS: int = 2


settings = Settings()
