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
    deepseek_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"

    # Exchange API
    hyperliquid_wallet: str = ""
    hyperliquid_private_key: str = ""  # For order signing
    dydx_address: str = ""

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Auto-trader
    auto_trade_enabled: bool = False
    auto_trade_equity: float = 5000.0
    auto_trade_conviction_threshold: int = 75

    # Pool screening
    subgraph_api_key: str = ""

    # Service
    tick_interval_seconds: int = 300   # 5 minutes
    log_level: str = "INFO"
    api_secret_key: str = ""           # Bearer token for protected endpoints

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
