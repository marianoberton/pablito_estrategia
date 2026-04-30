import pytest
from src.risk.manager import RiskManager, RiskRules, HourlyState, DailyState


@pytest.fixture
def rules():
    return RiskRules()


@pytest.fixture
def enabled_manager():
    mgr = RiskManager(bot_enabled=True)
    mgr.daily.peak_capital = 200.0
    mgr.daily.current_capital = 200.0
    return mgr


@pytest.fixture
def disabled_manager():
    return RiskManager(bot_enabled=False)
