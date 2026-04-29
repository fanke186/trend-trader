from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app.data.providers import normalize_symbol


class EasyQuotationQuoteProvider:
    def __init__(self, source: str = "sina") -> None:
        self.source = source

    def fetch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        normalized = [normalize_symbol(symbol) for symbol in symbols if symbol]
        if not normalized:
            return []
        try:
            import easyquotation  # type: ignore

            quotation = easyquotation.use(self.source)
            raw = quotation.stocks(normalized)
            return [self._normalize_quote(symbol, raw.get(symbol) or raw.get(_market_code(symbol)) or {}) for symbol in normalized]
        except Exception:
            return [self._sample_quote(symbol) for symbol in normalized]

    def _normalize_quote(self, symbol: str, item: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        price = _float(item.get("now") or item.get("price") or item.get("close") or item.get("最新价"))
        prev_close = _float(item.get("close") or item.get("昨收") or item.get("pre_close"))
        change_pct = ((price - prev_close) / prev_close * 100) if price and prev_close else 0
        return {
            "symbol": symbol,
            "name": item.get("name") or item.get("名称") or "",
            "price": round(price, 3),
            "change_pct": round(change_pct, 2),
            "volume": _float(item.get("volume") or item.get("成交量")),
            "turnover": _float(item.get("turnover") or item.get("成交额")),
            "source": self.source,
            "at": now,
        }

    def _sample_quote(self, symbol: str) -> dict[str, Any]:
        seed = sum(ord(char) for char in symbol)
        price = 8 + seed % 50 + math.sin(datetime.utcnow().minute / 60) * 0.2
        return {
            "symbol": symbol,
            "name": "",
            "price": round(price, 3),
            "change_pct": round(math.sin(seed) * 3, 2),
            "volume": 0,
            "turnover": 0,
            "source": "sample",
            "at": datetime.utcnow().isoformat(),
        }


def _market_code(symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    if symbol.startswith(("5", "6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
