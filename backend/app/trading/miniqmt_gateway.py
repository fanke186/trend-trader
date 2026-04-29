from __future__ import annotations

import requests

from app.trading.gateway import TradingGateway


class MiniQmtGateway(TradingGateway):
    mode = "live"

    def __init__(self, base_url: str, timeout_seconds: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def connect(self, config: dict) -> bool:
        resp = requests.post(f"{self._base_url}/connect", json=config, timeout=self._timeout)
        resp.raise_for_status()
        return bool(resp.json().get("success", False))

    def query_asset(self) -> dict:
        resp = requests.get(f"{self._base_url}/asset", timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def query_positions(self) -> list[dict]:
        resp = requests.get(f"{self._base_url}/positions", timeout=self._timeout)
        resp.raise_for_status()
        return resp.json().get("positions", [])

    def query_orders(self, today_only: bool = True) -> list[dict]:
        resp = requests.get(f"{self._base_url}/orders", params={"today_only": today_only}, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json().get("orders", [])

    def place_order(self, symbol: str, side: str, price: float, volume: int) -> dict:
        resp = requests.post(
            f"{self._base_url}/order",
            json={"symbol": symbol, "side": side, "price": price, "volume": volume, "price_type": "limit"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, entrust_no: str) -> bool:
        resp = requests.post(f"{self._base_url}/cancel", json={"entrust_no": entrust_no}, timeout=self._timeout)
        resp.raise_for_status()
        return bool(resp.json().get("success", False))

    def disconnect(self) -> None:
        return None
