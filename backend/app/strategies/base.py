from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import DailyBar, StrategyAnalysis


class StrategyPlugin(ABC):
    name: str

    @abstractmethod
    def analyze(self, symbol: str, bars: list[DailyBar]) -> StrategyAnalysis:
        pass


class StrategyRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, StrategyPlugin] = {}

    def register(self, plugin: StrategyPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> StrategyPlugin:
        if name not in self._plugins:
            raise KeyError(f"Unknown strategy: {name}")
        return self._plugins[name]

    def names(self) -> list[str]:
        return sorted(self._plugins)
