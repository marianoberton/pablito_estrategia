"""
Orchestrates RTDS, Binance backup, Gamma poller, and CLOB orderbook logger.
Runs as a systemd service (pm-logger).
"""
import asyncio
from datetime import datetime, timezone

from loguru import logger

from src.config import config
from src.db.client import get_db
from src.data.rtds_client import RTDSClient
from src.data.binance_backup import BinanceBackupClient
from src.data.gamma_client import GammaClient
from src.data.clob_client import CLOBMarketClient

BATCH_SIZE = 50
FLUSH_INTERVAL = 2  # seconds


class LoggerService:
    def __init__(self):
        self._chainlink_buffer: list[dict] = []
        self._binance_buffer: list[dict] = []

        self.rtds = RTDSClient(
            on_chainlink_tick=self._on_chainlink,
            on_binance_tick=self._on_binance_rtds,
        )
        self.binance_backup = BinanceBackupClient(on_tick=self._on_binance_direct)
        self.gamma = GammaClient()
        self.clob = CLOBMarketClient()

    async def _on_chainlink(self, tick: dict):
        self._chainlink_buffer.append(tick)
        if len(self._chainlink_buffer) >= BATCH_SIZE:
            await self._flush_chainlink()

    async def _on_binance_rtds(self, tick: dict):
        self._binance_buffer.append(tick)
        if len(self._binance_buffer) >= BATCH_SIZE:
            await self._flush_binance()

    async def _on_binance_direct(self, tick: dict):
        self._binance_buffer.append(tick)
        if len(self._binance_buffer) >= BATCH_SIZE:
            await self._flush_binance()

    async def _flush_chainlink(self):
        if not self._chainlink_buffer:
            return
        batch = self._chainlink_buffer[:]
        self._chainlink_buffer.clear()
        try:
            get_db().table("chainlink_btc_feed").upsert(
                batch, on_conflict="ts,source"
            ).execute()
        except Exception as e:
            logger.error(f"Chainlink flush error: {e}")

    async def _flush_binance(self):
        if not self._binance_buffer:
            return
        batch = self._binance_buffer[:]
        self._binance_buffer.clear()
        try:
            get_db().table("binance_btc_feed").upsert(
                batch, on_conflict="ts,source"
            ).execute()
        except Exception as e:
            logger.error(f"Binance flush error: {e}")

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(FLUSH_INTERVAL)
            await self._flush_chainlink()
            await self._flush_binance()

    async def run(self):
        logger.info(f"LoggerService starting in mode={config.BOT_MODE}")
        await asyncio.gather(
            self.rtds.connect(),
            self.binance_backup.connect(),
            self.gamma.run(),
            self._flush_loop(),
        )
