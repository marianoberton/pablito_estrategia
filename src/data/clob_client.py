"""
Polymarket CLOB WebSocket client.
Subscribes to agg_orderbook for active BTC Up/Down markets.
Snapshots orderbook every 5s, logs trades.
"""
import asyncio
import json
from datetime import datetime, timezone

import websockets
from loguru import logger

from src.config import config
from src.db.client import get_db

SNAPSHOT_INTERVAL = 5


class CLOBMarketClient:
    def __init__(self):
        self._running = False
        self._subscribed_assets: set[str] = set()
        self._orderbooks: dict[str, dict] = {}
        self._ws = None

    async def run(self, asset_ids: list[str]):
        self._running = True
        self._subscribed_assets = set(asset_ids)
        backoff = 1
        while self._running:
            try:
                await self._run_once()
                backoff = 1
            except Exception as e:
                logger.warning(f"CLOB WS error: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _run_once(self):
        url = config.CLOB_MARKET_WS_URL
        async with websockets.connect(url, ping_interval=None) as ws:
            self._ws = ws
            logger.info(f"Connected to CLOB market WS: {url}")

            if self._subscribed_assets:
                await self._subscribe(ws, list(self._subscribed_assets))

            ping_task = asyncio.create_task(self._ping_loop(ws))
            snapshot_task = asyncio.create_task(self._snapshot_loop())
            try:
                async for raw in ws:
                    msgs = json.loads(raw)
                    if not isinstance(msgs, list):
                        msgs = [msgs]
                    for msg in msgs:
                        await self._handle_msg(msg)
            finally:
                ping_task.cancel()
                snapshot_task.cancel()

    async def _subscribe(self, ws, asset_ids: list[str]):
        sub = {
            "type": "subscribe",
            "channel": "market",
            "assets_ids": asset_ids,
        }
        await ws.send(json.dumps(sub))
        logger.info(f"Subscribed CLOB orderbook for {len(asset_ids)} assets")

    async def _ping_loop(self, ws):
        while True:
            await asyncio.sleep(config.CLOB_PING_INTERVAL)
            try:
                await ws.send(json.dumps({"type": "PING"}))
            except Exception:
                break

    async def _snapshot_loop(self):
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL)
            try:
                await self._flush_snapshots()
            except Exception as e:
                logger.error(f"Snapshot flush error: {e}")

    async def _handle_msg(self, msg: dict):
        event_type = msg.get("event_type") or msg.get("type", "")
        asset_id = msg.get("asset_id")

        if event_type in ("book", "price_change"):
            if asset_id:
                self._orderbooks[asset_id] = msg

        elif event_type == "trade":
            await self._log_trade(msg)

    async def _flush_snapshots(self):
        db = get_db()
        now = datetime.now(timezone.utc)
        rows = []
        for asset_id, ob in self._orderbooks.items():
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None

            microprice = None
            imbalance = None
            if best_bid and best_ask:
                bid_qty = float(bids[0].get("size", 0)) if bids else 0
                ask_qty = float(asks[0].get("size", 0)) if asks else 0
                total = bid_qty + ask_qty
                if total > 0:
                    microprice = (best_bid * ask_qty + best_ask * bid_qty) / total
                    imbalance = (bid_qty - ask_qty) / total

            rows.append({
                "market_id": None,  # resolved by asset_id lookup if needed
                "snapshot_time": now.isoformat(),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_depth_5": bids[:5],
                "ask_depth_5": asks[:5],
                "microprice": microprice,
                "imbalance": imbalance,
            })

        if rows:
            db.table("orderbook_snapshots").insert(rows).execute()

    async def _log_trade(self, msg: dict):
        db = get_db()
        row = {
            "trade_time": datetime.now(timezone.utc).isoformat(),
            "side": msg.get("side"),
            "price": msg.get("price"),
            "size": msg.get("size"),
            "raw_payload": msg,
        }
        db.table("polymarket_trades").insert(row).execute()

    async def subscribe_asset(self, asset_id: str):
        self._subscribed_assets.add(asset_id)
        if self._ws:
            await self._subscribe(self._ws, [asset_id])

    def stop(self):
        self._running = False
