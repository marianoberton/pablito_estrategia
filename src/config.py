import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SUPABASE_URL: str = os.environ["SUPABASE_URL"]
    SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

    POLYGON_PRIVATE_KEY: str = os.getenv("POLYGON_PRIVATE_KEY", "")
    POLYMARKET_API_KEY: str = os.getenv("POLYMARKET_API_KEY", "")
    POLYMARKET_API_SECRET: str = os.getenv("POLYMARKET_API_SECRET", "")
    POLYMARKET_API_PASSPHRASE: str = os.getenv("POLYMARKET_API_PASSPHRASE", "")

    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    BOT_MODE: str = os.getenv("BOT_MODE", "logger")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # WebSocket endpoints
    RTDS_WS_URL: str = "wss://ws-live-data.polymarket.com"
    CLOB_MARKET_WS_URL: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    CLOB_USER_WS_URL: str = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    CLOB_REST_URL: str = "https://clob.polymarket.com"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"

    # Heartbeat intervals (seconds)
    RTDS_PING_INTERVAL: int = 5
    CLOB_PING_INTERVAL: int = 10


config = Config()
