from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # LLM providers
    anthropic_api_key: str = ""       # Retained for non-fallback use; NOT in fallback chain
    openai_api_key: str = ""          # Also used for DeepSeek via base_url override
    openrouter_api_key: str = ""      # Retained for compat; NOT in fallback chain
    # DeepSeek (financial-tuned model) — primary
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"
    # Ollama Cloud (for Minimax and GLM via https://ollama.com/v1)
    ollama_api_key: str = ""
    ollama_cloud_base_url: str = "https://ollama.com/v1"

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

    # Trading hours (UTC) — only open new positions during this window
    trading_hours_start: int = 0
    trading_hours_end: int = 18

    # Position size sweet spot (USD)
    min_position_usd: float = 500.0
    max_position_usd: float = 7000.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
