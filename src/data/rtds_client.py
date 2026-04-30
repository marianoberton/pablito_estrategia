"""
WebSocket client for Polymarket RTDS.
Delivers crypto_prices_chainlink (Chainlink BTC/USD) and crypto_prices (Binance BTCUSDT).
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

import websockets
from loguru import logger

from src.config import config

# Type alias for tick handler
TickHandler = Callable[[dict], Awaitable[None]]


class RTDSClient:
    def __init__(
        self,
        on_chainlink_tick: TickHandler | None = None,
        on_binance_tick: TickHandler | None = None,
    ):
        self.on_chainlink_tick = on_chainlink_tick
        self.on_binance_tick = on_binance_tick
        self._running = False

    async def connect(self):
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._run()
                backoff = 1
            except Exception as e:
                logger.warning(f"RTDS disconnected: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _run(self):
        url = config.RTDS_WS_URL
        async with websockets.connect(url, ping_interval=None) as ws:
            logger.info(f"Connected to RTDS: {url}")

            sub = {
                "type": "subscribe",
                "topics": ["crypto_prices_chainlink", "crypto_prices"],
            }
            await ws.send(json.dumps(sub))
            logger.info("Subscribed to crypto_prices_chainlink and crypto_prices")

            ping_task = asyncio.create_task(self._ping_loop(ws))
            try:
                async for raw in ws:
                    received_ts = datetime.now(timezone.utc)
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    topic = msg.get("topic", "")
                    data = msg.get("data", {})

                    if topic == "crypto_prices_chainlink":
                        asset = data.get("asset", "").lower()
                        if "btc" in asset and "usd" in asset:
                            tick = self._parse_chainlink_tick(data, received_ts)
                            if tick and self.on_chainlink_tick:
                                await self.on_chainlink_tick(tick)

                    elif topic == "crypto_prices":
                        asset = data.get("asset", "").lower()
                        if "btcusdt" in asset or ("btc" in asset and "usdt" in asset):
                            tick = self._parse_binance_tick(data, received_ts)
                            if tick and self.on_binance_tick:
                                await self.on_binance_tick(tick)
            finally:
                ping_task.cancel()

    async def _ping_loop(self, ws):
        while True:
            await asyncio.sleep(config.RTDS_PING_INTERVAL)
            try:
                await ws.send(json.dumps({"type": "PING"}))
            except Exception:
                break

    def _parse_chainlink_tick(self, data: dict, received_ts: datetime) -> dict | None:
        price = data.get("price")
        ts_ms = data.get("timestamp")
        if price is None or ts_ms is None:
            return None
        ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
        return {
            "ts": ts.isoformat(),
            "received_ts": received_ts.isoformat(),
            "price": float(price),
            "source": "polymarket_rtds",
        }

    def _parse_binance_tick(self, data: dict, received_ts: datetime) -> dict | None:
        price = data.get("price")
        ts_ms = data.get("timestamp")
        if price is None or ts_ms is None:
            return None
        ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
        return {
            "ts": ts.isoformat(),
            "received_ts": received_ts.isoformat(),
            "price": float(price),
            "source": "polymarket_rtds",
        }

    def stop(self):
        self._running = False
