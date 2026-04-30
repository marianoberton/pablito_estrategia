"""
Risk manager tests. Target: 95%+ coverage per plan spec.
"""
import pytest
from src.risk.manager import RiskManager, RiskRules, HourlyState, DailyState


def make_mgr(**kwargs) -> RiskManager:
    mgr = RiskManager(bot_enabled=kwargs.pop("bot_enabled", True))
    mgr.daily.peak_capital = 200.0
    mgr.daily.current_capital = 200.0
    for k, v in kwargs.items():
        setattr(mgr, k, v)
    return mgr


# --- bot disabled ---

def test_bot_disabled_blocks():
    mgr = RiskManager(bot_enabled=False)
    result = mgr.check(confidence=0.8)
    assert not result.passed
    assert result.reason == "bot_disabled"


# --- hourly controls ---

def test_hourly_target_reached():
    mgr = make_mgr()
    mgr.hourly.hourly_pnl = 2.0
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "hourly_target_reached"


def test_hourly_stop_loss():
    mgr = make_mgr()
    mgr.hourly.hourly_pnl = -3.0
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "hourly_stop_loss"


def test_max_trades_per_hour():
    mgr = make_mgr()
    mgr.hourly.trades_this_hour = 3
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "max_trades_per_hour"


# --- daily controls ---

def test_daily_target_reached():
    mgr = make_mgr()
    mgr.daily.daily_pnl = 20.0
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "daily_target_reached"


def test_daily_stop_loss():
    mgr = make_mgr()
    mgr.daily.daily_pnl = -15.0
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "daily_stop_loss"


def test_max_drawdown():
    mgr = make_mgr()
    mgr.daily.peak_capital = 200.0
    mgr.daily.current_capital = 140.0  # 30% drawdown
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "max_drawdown"


def test_consecutive_errors_pause():
    mgr = make_mgr()
    mgr.daily.consecutive_errors = 3
    result = mgr.check(0.8)
    assert not result.passed
    assert result.reason == "consecutive_errors_pause"


# --- confidence ---

def test_low_confidence():
    mgr = make_mgr()
    result = mgr.check(0.54)
    assert not result.passed
    assert result.reason == "low_confidence"


def test_exactly_min_confidence():
    mgr = make_mgr()
    result = mgr.check(0.55)
    assert result.passed


# --- position sizing ---

def test_first_trade_full_size():
    mgr = make_mgr()
    result = mgr.check(0.7)
    assert result.passed
    assert result.size_usdc == 10.0


def test_second_trade_high_confidence():
    mgr = make_mgr()
    mgr.hourly.trades_this_hour = 1
    mgr.hourly.last_signal_confidence = 0.70
    result = mgr.check(0.70)
    assert result.passed
    assert result.size_usdc == 5.0


def test_second_trade_low_confidence_no_size():
    mgr = make_mgr()
    mgr.hourly.trades_this_hour = 1
    mgr.hourly.last_signal_confidence = 0.55
    result = mgr.check(0.55)
    assert result.passed
    assert result.size_usdc == 0.0


# --- record_trade / state tracking ---

def test_record_trade_updates_pnl():
    mgr = make_mgr()
    mgr.record_trade(2.0)
    assert mgr.hourly.hourly_pnl == 2.0
    assert mgr.daily.daily_pnl == 2.0
    assert mgr.hourly.trades_this_hour == 1


def test_record_trade_updates_peak():
    mgr = make_mgr()
    mgr.daily.current_capital = 200.0
    mgr.daily.peak_capital = 200.0
    mgr.record_trade(5.0)
    assert mgr.daily.peak_capital == 205.0


def test_reset_hourly():
    mgr = make_mgr()
    mgr.hourly.hourly_pnl = 5.0
    mgr.hourly.trades_this_hour = 3
    mgr.reset_hourly()
    assert mgr.hourly.hourly_pnl == 0.0
    assert mgr.hourly.trades_this_hour == 0


def test_reset_errors():
    mgr = make_mgr()
    mgr.daily.consecutive_errors = 3
    mgr.reset_errors()
    assert mgr.daily.consecutive_errors == 0


def test_record_error():
    mgr = make_mgr()
    mgr.record_error()
    mgr.record_error()
    assert mgr.daily.consecutive_errors == 2
