from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # LLM providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""          # Also used for DeepSeek via base_url override
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

    # LP Auto-Trader
    lp_auto_enabled: bool = False
    lp_starting_equity: float = 25000.0
    lp_paper_mode: bool = True
    lp_watched_pools: str = ""  # comma-separated pool addresses
    lp_max_positions: int = 6   # LP_MAX_POSITIONS — max concurrent LP positions
    lp_wallet_private_key: str = ""
    lp_chain: str = "arbitrum"  # arbitrum or ethereum
    lp_rpc_url: str = ""  # auto-set based on chain if empty

    # Pool screening
    subgraph_api_key: str = ""

    # Email reports
    resend_api_key: str = ""

    # Service
    tick_interval_seconds: int = 300   # 5 minutes
    log_level: str = "INFO"
    api_secret_key: str = ""           # Bearer token for protected endpoints

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
