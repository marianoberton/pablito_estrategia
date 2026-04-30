"""
Phase 1 entry point: runs the LoggerService.
Usage: python scripts/run_logger.py
"""
import asyncio
import sys

from loguru import logger
from src.config import config
from src.data.logger_service import LoggerService


def main():
    logger.remove()
    logger.add(sys.stderr, level=config.LOG_LEVEL)
    logger.add("logs/logger_{time}.log", rotation="100 MB", retention="30 days", level="DEBUG")

    if config.BOT_MODE != "logger":
        logger.warning(f"BOT_MODE is '{config.BOT_MODE}', expected 'logger'. Proceeding anyway.")

    service = LoggerService()
    asyncio.run(service.run())


if __name__ == "__main__":
    main()
