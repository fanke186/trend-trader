from app.strategies.base import StrategyRegistry
from app.strategies.trend_trading import TrendTradingStrategy


def build_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(TrendTradingStrategy())
    return registry
