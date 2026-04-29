from __future__ import annotations

from app.trading.gateway import TradingGateway


class PaperTradingGateway(TradingGateway):
    mode = "paper"

    def __init__(self, config: dict) -> None:
        self._cash = float(config.get("initial_cash") or 100000)
        self._commission_rate = float(config.get("commission_rate") or 0.00025)
        self._stamp_duty = float(config.get("stamp_duty") or 0.001)
        self._min_commission = float(config.get("min_commission") or 5)
        self._positions: dict[str, dict] = {}
        self._orders: list[dict] = []

    def connect(self, config: dict) -> bool:
        return True

    def query_asset(self) -> dict:
        market_value = sum(float(pos.get("market_value") or 0) for pos in self._positions.values())
        return {"mode": self.mode, "total_asset": self._cash + market_value, "market_value": market_value, "cash": self._cash, "frozen_cash": 0}

    def query_positions(self) -> list[dict]:
        return list(self._positions.values())

    def query_orders(self, today_only: bool = True) -> list[dict]:
        return list(self._orders)

    def place_order(self, symbol: str, side: str, price: float, volume: int) -> dict:
        gross = float(price) * int(volume)
        commission = max(gross * self._commission_rate, self._min_commission)
        if side == "buy":
            cost = gross + commission
            if cost > self._cash:
                order = {"symbol": symbol, "side": side, "price": price, "volume": volume, "status": "rejected", "reason": "insufficient cash"}
                self._orders.append(order)
                return order
            self._cash -= cost
            pos = self._positions.setdefault(symbol, {"symbol": symbol, "volume": 0, "avg_cost": 0, "market_value": 0, "unrealized_pnl": 0, "mode": self.mode})
            old_value = pos["avg_cost"] * pos["volume"]
            pos["volume"] += volume
            pos["avg_cost"] = (old_value + gross) / pos["volume"]
            pos["market_value"] = pos["volume"] * price
        else:
            pos = self._positions.get(symbol)
            if not pos or pos["volume"] < volume:
                order = {"symbol": symbol, "side": side, "price": price, "volume": volume, "status": "rejected", "reason": "insufficient position"}
                self._orders.append(order)
                return order
            tax = gross * self._stamp_duty
            self._cash += gross - commission - tax
            pos["volume"] -= volume
            pos["market_value"] = pos["volume"] * price
        order = {"entrust_no": f"paper-{len(self._orders) + 1}", "symbol": symbol, "side": side, "price": price, "volume": volume, "status": "filled"}
        self._orders.append(order)
        return order

    def cancel_order(self, entrust_no: str) -> bool:
        return True

    def disconnect(self) -> None:
        return None
