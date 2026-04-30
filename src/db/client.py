from supabase import create_client, Client
from src.config import config

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client
