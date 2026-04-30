"""
Direct Binance WebSocket client as backup/redundancy for price data.
Aggregates trades into 1-second buckets and inserts into binance_btc_feed.
"""
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone

import websockets
from loguru import logger

from src.config import config

BinanceTickHandler = callable


class BinanceBackupClient:
    def __init__(self, on_tick=None):
        self.on_tick = on_tick
        self._running = False
        self._bucket: dict = defaultdict(lambda: {
            "price": None, "volume": 0.0,
            "buy_volume": 0.0, "sell_volume": 0.0, "count": 0,
        })

    async def connect(self):
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._run()
                backoff = 1
            except Exception as e:
                logger.warning(f"Binance WS disconnected: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _run(self):
        stream = "btcusdt@aggTrade"
        url = f"{config.BINANCE_WS_URL}/{stream}"
        async with websockets.connect(url, ping_interval=20) as ws:
            logger.info(f"Connected to Binance WS: {url}")
            flush_task = asyncio.create_task(self._flush_loop())
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("e") == "aggTrade":
                        self._process_trade(msg)
            finally:
                flush_task.cancel()

    def _process_trade(self, msg: dict):
        ts_sec = msg["T"] // 1000
        price = float(msg["p"])
        qty = float(msg["q"])
        is_sell = msg["m"]  # maker side is buyer means taker is seller

        b = self._bucket[ts_sec]
        b["price"] = price
        b["volume"] += qty
        if is_sell:
            b["sell_volume"] += qty
        else:
            b["buy_volume"] += qty
        b["count"] += 1

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(1)
            now_sec = int(datetime.now(timezone.utc).timestamp())
            stale = [ts for ts in self._bucket if ts < now_sec - 1]
            for ts in stale:
                b = self._bucket.pop(ts)
                if b["price"] is None:
                    continue
                tick = {
                    "ts": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "received_ts": datetime.now(timezone.utc).isoformat(),
                    "price": b["price"],
                    "volume_1s": b["volume"],
                    "buy_volume_1s": b["buy_volume"],
                    "sell_volume_1s": b["sell_volume"],
                    "trade_count_1s": b["count"],
                    "source": "binance_direct",
                }
                if self.on_tick:
                    await self.on_tick(tick)

    def stop(self):
        self._running = False
