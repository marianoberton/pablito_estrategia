"""
Resolves BTC price at a given timestamp using Chainlink feed with Binance fallback.
"""
from datetime import datetime, timezone, timedelta

from loguru import logger

from src.db.client import get_db

MAX_GAP_SECONDS = 2


def get_chainlink_price_at(ts: datetime) -> dict | None:
    """
    Returns {"price": float, "ts": str, "source": str} or None if INVALID.
    Tries Chainlink within ±MAX_GAP_SECONDS, falls back to Binance.
    """
    db = get_db()
    low = (ts - timedelta(seconds=MAX_GAP_SECONDS)).isoformat()
    high = (ts + timedelta(seconds=MAX_GAP_SECONDS)).isoformat()

    resp = (
        db.table("chainlink_btc_feed")
        .select("ts, price, source")
        .gte("ts", low)
        .lte("ts", high)
        .order("ts")
        .execute()
    )
    rows = resp.data or []

    if rows:
        # Nearest tick by absolute time difference
        best = min(rows, key=lambda r: abs(
            datetime.fromisoformat(r["ts"]).timestamp() - ts.timestamp()
        ))
        return {"price": float(best["price"]), "ts": best["ts"], "source": best["source"]}

    # Fallback: Binance
    logger.warning(f"No Chainlink tick near {ts.isoformat()}, falling back to Binance")
    resp2 = (
        db.table("binance_btc_feed")
        .select("ts, price, source")
        .gte("ts", low)
        .lte("ts", high)
        .order("ts")
        .execute()
    )
    rows2 = resp2.data or []
    if rows2:
        best2 = min(rows2, key=lambda r: abs(
            datetime.fromisoformat(r["ts"]).timestamp() - ts.timestamp()
        ))
        return {"price": float(best2["price"]), "ts": best2["ts"], "source": "binance_fallback"}

    logger.error(f"No price data near {ts.isoformat()} — marking INVALID")
    return None
