"""
Unit tests for RTDSClient tick parsing (no network required).
"""
import pytest
from datetime import datetime, timezone
from src.data.rtds_client import RTDSClient


@pytest.fixture
def client():
    return RTDSClient()


def test_parse_chainlink_tick_valid(client):
    data = {"asset": "btc/usd", "price": "95000.50", "timestamp": "1714500000000"}
    received = datetime.now(timezone.utc)
    tick = client._parse_chainlink_tick(data, received)
    assert tick is not None
    assert tick["price"] == 95000.50
    assert tick["source"] == "polymarket_rtds"
    assert "ts" in tick


def test_parse_chainlink_tick_missing_price(client):
    data = {"asset": "btc/usd", "timestamp": "1714500000000"}
    tick = client._parse_chainlink_tick(data, datetime.now(timezone.utc))
    assert tick is None


def test_parse_chainlink_tick_missing_ts(client):
    data = {"asset": "btc/usd", "price": "95000"}
    tick = client._parse_chainlink_tick(data, datetime.now(timezone.utc))
    assert tick is None


def test_parse_binance_tick_valid(client):
    data = {"asset": "btcusdt", "price": "94999.99", "timestamp": "1714500001000"}
    received = datetime.now(timezone.utc)
    tick = client._parse_binance_tick(data, received)
    assert tick is not None
    assert tick["price"] == 94999.99


def test_parse_binance_tick_missing_fields(client):
    data = {}
    tick = client._parse_binance_tick(data, datetime.now(timezone.utc))
    assert tick is None
