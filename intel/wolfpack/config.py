from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # LLM providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""          # Also used for DeepSeek via base_url override
    openrouter_api_key: str = ""

    # DeepSeek (financial-tuned model)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Exchange API
    hyperliquid_wallet: str = ""
    hyperliquid_private_key: str = ""  # For order signing
    dydx_address: str = ""

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Service
    tick_interval_seconds: int = 300   # 5 minutes
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
