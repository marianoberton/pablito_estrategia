"""
Kill switch: soft disable via DB flag.
Layer 1 of 4. Layers 2-4 are CLI, systemd, and wallet withdrawal.
"""
from loguru import logger
from src.db.client import get_db


def kill(reason: str = "manual"):
    db = get_db()
    db.table("bot_config").update({"enabled": False}).eq("id", 1).execute()
    logger.critical(f"KILL SWITCH ACTIVATED: {reason}")


def is_enabled() -> bool:
    db = get_db()
    resp = db.table("bot_config").select("enabled").eq("id", 1).single().execute()
    return resp.data.get("enabled", False)
