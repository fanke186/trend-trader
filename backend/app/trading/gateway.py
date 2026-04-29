from __future__ import annotations

from abc import ABC, abstractmethod


class TradingGateway(ABC):
    mode = "unknown"

    @abstractmethod
    def connect(self, config: dict) -> bool:
        ...

    @abstractmethod
    def query_asset(self) -> dict:
        ...

    @abstractmethod
    def query_positions(self) -> list[dict]:
        ...

    @abstractmethod
    def query_orders(self, today_only: bool = True) -> list[dict]:
        ...

    @abstractmethod
    def place_order(self, symbol: str, side: str, price: float, volume: int) -> dict:
        ...

    @abstractmethod
    def cancel_order(self, entrust_no: str) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...


class DryRunGateway(TradingGateway):
    mode = "dry_run"

    def connect(self, config: dict) -> bool:
        return True

    def query_asset(self) -> dict:
        return {"mode": self.mode, "total_asset": 0, "market_value": 0, "cash": 0, "frozen_cash": 0}

    def query_positions(self) -> list[dict]:
        return []

    def query_orders(self, today_only: bool = True) -> list[dict]:
        return []

    def place_order(self, symbol: str, side: str, price: float, volume: int) -> dict:
        return {"status": "dry_run", "symbol": symbol, "side": side, "price": price, "volume": volume}

    def cancel_order(self, entrust_no: str) -> bool:
        return True

    def disconnect(self) -> None:
        return None
