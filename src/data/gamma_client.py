"""
Polymarket Gamma API client for market discovery and resolution tracking.
Polls /markets every 30s, upserts into markets table.
"""
import asyncio
from datetime import datetime, timezone

import httpx
from loguru import logger

from src.config import config
from src.db.client import get_db

POLL_INTERVAL = 30
BTC_FILTERS = ["BTC Up", "BTC Down", "Bitcoin Up", "Bitcoin Down"]


class GammaClient:
    def __init__(self):
        self._running = False

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self._poll_markets()
            except Exception as e:
                logger.error(f"Gamma poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_markets(self):
        async with httpx.AsyncClient(timeout=15) as client:
            params = {
                "active": "true",
                "closed": "false",
                "tag_slug": "btc",
                "limit": 100,
            }
            resp = await client.get(f"{config.GAMMA_API_URL}/markets", params=params)
            resp.raise_for_status()
            markets = resp.json()

        btc_ud = [m for m in markets if self._is_btc_updown(m)]
        if not btc_ud:
            return

        db = get_db()
        for m in btc_ud:
            row = self._to_row(m)
            db.table("markets").upsert(row, on_conflict="market_id").execute()

        logger.debug(f"Upserted {len(btc_ud)} BTC Up/Down markets")

    def _is_btc_updown(self, m: dict) -> bool:
        q = m.get("question", "")
        return any(f in q for f in BTC_FILTERS)

    def _to_row(self, m: dict) -> dict:
        outcomes = m.get("outcomes", [])
        asset_up = asset_down = None
        for o in outcomes:
            name = o.get("name", "").upper()
            if "UP" in name:
                asset_up = o.get("asset_id") or o.get("token_id")
            elif "DOWN" in name:
                asset_down = o.get("asset_id") or o.get("token_id")

        q = m.get("question", "")
        duration = None
        if "5 min" in q or "5min" in q:
            duration = 300
        elif "15 min" in q or "15min" in q:
            duration = 900
        elif "1 hour" in q or "1h" in q:
            duration = 3600

        return {
            "market_id": m["id"],
            "condition_id": m.get("conditionId"),
            "question": q,
            "asset": "BTC",
            "market_type": "updown",
            "duration_seconds": duration,
            "open_time": m.get("startDateIso") or m.get("startDate"),
            "close_time": m.get("endDateIso") or m.get("endDate"),
            "asset_id_up": asset_up,
            "asset_id_down": asset_down,
            "raw_payload": m,
        }

    def stop(self):
        self._running = False
