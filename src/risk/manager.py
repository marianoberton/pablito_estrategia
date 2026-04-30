"""
Central risk manager. All pre-trade checks run here.
95%+ test coverage required per plan spec.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RiskRules:
    max_position_size_usdc: float = 10.0
    min_confidence: float = 0.55

    hourly_profit_target: float = 2.0
    hourly_stop_loss: float = -3.0
    max_trades_per_hour: int = 3

    daily_profit_target: float = 20.0
    daily_stop_loss: float = -15.0

    max_drawdown_pct: float = 0.30
    consecutive_errors_pause: int = 3

    initial_capital_per_hour: float = 10.0


@dataclass
class HourlyState:
    trades_this_hour: int = 0
    hourly_pnl: float = 0.0
    last_signal_confidence: float = 0.0


@dataclass
class DailyState:
    trades_today: int = 0
    daily_pnl: float = 0.0
    peak_capital: float = 0.0
    current_capital: float = 0.0
    consecutive_errors: int = 0


@dataclass
class RiskCheckResult:
    passed: bool
    reason: str
    size_usdc: float = 0.0


class RiskManager:
    def __init__(self, rules: RiskRules | None = None, bot_enabled: bool = False):
        self.rules = rules or RiskRules()
        self.bot_enabled = bot_enabled
        self.hourly = HourlyState()
        self.daily = DailyState()

    def check(self, confidence: float) -> RiskCheckResult:
        r = self.rules
        h = self.hourly
        d = self.daily

        if not self.bot_enabled:
            return RiskCheckResult(False, "bot_disabled")
        if h.hourly_pnl >= r.hourly_profit_target:
            return RiskCheckResult(False, "hourly_target_reached")
        if h.hourly_pnl <= r.hourly_stop_loss:
            return RiskCheckResult(False, "hourly_stop_loss")
        if d.daily_pnl >= r.daily_profit_target:
            return RiskCheckResult(False, "daily_target_reached")
        if d.daily_pnl <= r.daily_stop_loss:
            return RiskCheckResult(False, "daily_stop_loss")
        if d.peak_capital > 0:
            drawdown = (d.peak_capital - d.current_capital) / d.peak_capital
            if drawdown >= r.max_drawdown_pct:
                return RiskCheckResult(False, "max_drawdown")
        if h.trades_this_hour >= r.max_trades_per_hour:
            return RiskCheckResult(False, "max_trades_per_hour")
        if confidence < r.min_confidence:
            return RiskCheckResult(False, "low_confidence")
        if d.consecutive_errors >= r.consecutive_errors_pause:
            return RiskCheckResult(False, "consecutive_errors_pause")

        size = self._calculate_size(confidence)
        return RiskCheckResult(True, "ok", size_usdc=size)

    def _calculate_size(self, confidence: float) -> float:
        r = self.rules
        h = self.hourly

        if h.trades_this_hour == 0:
            return r.max_position_size_usdc

        if h.hourly_pnl >= r.hourly_profit_target:
            surplus = h.hourly_pnl - r.hourly_profit_target
            return min(surplus, r.max_position_size_usdc) if surplus > 0 else 0.0

        if h.last_signal_confidence > 0.65:
            return r.max_position_size_usdc / 2

        return 0.0

    def record_trade(self, pnl: float):
        self.hourly.trades_this_hour += 1
        self.hourly.hourly_pnl += pnl
        self.daily.trades_today += 1
        self.daily.daily_pnl += pnl
        self.daily.current_capital += pnl
        if self.daily.current_capital > self.daily.peak_capital:
            self.daily.peak_capital = self.daily.current_capital

    def record_error(self):
        self.daily.consecutive_errors += 1

    def reset_errors(self):
        self.daily.consecutive_errors = 0

    def reset_hourly(self):
        self.hourly = HourlyState()

    def reset_daily(self):
        self.daily = DailyState(
            peak_capital=self.daily.current_capital,
            current_capital=self.daily.current_capital,
        )
