from __future__ import annotations

from app.trading.gateway import DryRunGateway, TradingGateway
from app.trading.miniqmt_gateway import MiniQmtGateway
from app.trading.paper_gateway import PaperTradingGateway


class TradeManager:
    def __init__(self, config_loader) -> None:
        trading = config_loader.trading
        mode = trading.get("mode") or trading.get("trade_mode") or "dry_run"
        self.mode = str(mode)
        if self.mode == "live":
            cfg = trading.get("miniqmt", {})
            self._gateway: TradingGateway = MiniQmtGateway(str(cfg.get("gateway_url") or "http://127.0.0.1:8800"), int(cfg.get("timeout_seconds") or 10))
        elif self.mode == "paper":
            self._gateway = PaperTradingGateway(trading.get("paper", {}))
        else:
            self.mode = "dry_run"
            self._gateway = DryRunGateway()

    def status(self) -> dict:
        return {"mode": self.mode, "asset": self._gateway.query_asset(), "positions": self._gateway.query_positions(), "orders": self._gateway.query_orders()}

    def execute_condition_trade(self, order: dict) -> dict:
        action = dict(order.get("action") or {})
        return self._gateway.place_order(
            symbol=str(order.get("symbol") or ""),
            side=str(action.get("side") or "buy"),
            price=float(action.get("price") or 0),
            volume=int(action.get("volume") or 100),
        )
