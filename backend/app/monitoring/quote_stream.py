from __future__ import annotations

import asyncio
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Protocol

from app.data.providers import normalize_symbol


@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    change_pct: float
    volume: float
    amount: float
    high: float
    low: float
    open: float
    pre_close: float
    bid_prices: list[float]
    bid_volumes: list[int]
    ask_prices: list[float]
    ask_volumes: list[int]
    timestamp: float
    source: str = "sample"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class QuoteProvider(Protocol):
    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        ...


class MootdxQuoteProvider:
    """mootdx quote provider with deterministic sample fallback."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._client = None
        try:
            from mootdx.quotes import Quotes  # type: ignore

            self._client = Quotes.factory(
                market=self._config.get("market", "std"),
                multithread=self._config.get("multithread", True),
                heartbeat=self._config.get("heartbeat", True),
            )
        except Exception:
            self._client = None

    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        normalized = [normalize_symbol(symbol) for symbol in symbols if symbol]
        if not self._client:
            return {symbol: _sample_quote(symbol) for symbol in normalized}
        result: dict[str, Quote] = {}
        for symbol in normalized:
            try:
                bars = self._client.bars(symbol=symbol, frequency=9, offset=1)
                if hasattr(bars, "to_dict"):
                    rows = bars.to_dict("records")
                elif isinstance(bars, list):
                    rows = bars
                else:
                    rows = []
                item = rows[-1] if rows else {}
                result[symbol] = _quote_from_bar(symbol, item, "mootdx")
            except Exception:
                result[symbol] = _sample_quote(symbol)
        return result


class JvQuantQuoteProvider:
    """jvQuant placeholder provider.

    The real channel needs external credentials and a stable WebSocket server.
    Until connected, it returns cached/sample quotes so the rest of the system
    remains operable.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._quotes: dict[str, Quote] = {}
        self._subscribed: set[str] = set()

    async def connect(self) -> None:
        return None

    async def subscribe(self, symbols: list[str]) -> None:
        self._subscribed.update(normalize_symbol(symbol) for symbol in symbols if symbol)

    async def unsubscribe(self, symbols: list[str]) -> None:
        self._subscribed.difference_update(normalize_symbol(symbol) for symbol in symbols if symbol)

    async def listen(self) -> AsyncIterator[Quote]:
        while True:
            for symbol in sorted(self._subscribed):
                quote = self._quotes.get(symbol) or _sample_quote(symbol)
                self._quotes[symbol] = quote
                yield quote
            await asyncio.sleep(float(self._config.get("reconnect_seconds") or 3))

    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        return {normalize_symbol(symbol): self._quotes.get(normalize_symbol(symbol)) or _sample_quote(symbol) for symbol in symbols if symbol}


class QuoteManager:
    """Active quote stream manager."""

    def __init__(self, config_loader: Any, on_quote=None) -> None:
        self._config = config_loader
        self._on_quote_callback = on_quote
        self._active_symbols: set[str] = set()
        channel_name, channel_config = config_loader.get_active_quote_channel()
        self.channel_name = channel_name
        if channel_name == "jvquant":
            self._provider: QuoteProvider = JvQuantQuoteProvider(channel_config)
        else:
            self._provider = MootdxQuoteProvider(channel_config)

    def set_active_symbols(self, symbols: set[str]) -> None:
        self._active_symbols = {normalize_symbol(symbol) for symbol in symbols if symbol}

    def fetch_once(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        target = symbols or sorted(self._active_symbols)
        quotes = self._provider.fetch_quotes(target)
        return [quote.model_dump() for quote in quotes.values()]

    async def start(self) -> None:
        while True:
            if self._active_symbols:
                quotes = self._provider.fetch_quotes(sorted(self._active_symbols))
                for quote in quotes.values():
                    self._on_quote(quote)
            await asyncio.sleep(3)

    def _on_quote(self, quote: Quote) -> None:
        if self._on_quote_callback:
            self._on_quote_callback(quote)


def _quote_from_bar(symbol: str, item: dict[str, Any], source: str) -> Quote:
    close = _float(item.get("close") or item.get("price") or item.get("now"))
    open_price = _float(item.get("open") or close)
    high = _float(item.get("high") or close)
    low = _float(item.get("low") or close)
    pre_close = _float(item.get("pre_close") or item.get("last_close") or open_price)
    change_pct = ((close - pre_close) / pre_close * 100) if pre_close else 0.0
    return Quote(
        symbol=symbol,
        name=str(item.get("name") or ""),
        price=round(close, 3),
        change_pct=round(change_pct, 2),
        volume=_float(item.get("volume") or item.get("vol")),
        amount=_float(item.get("amount") or item.get("turnover")),
        high=round(high, 3),
        low=round(low, 3),
        open=round(open_price, 3),
        pre_close=round(pre_close, 3),
        bid_prices=[],
        bid_volumes=[],
        ask_prices=[],
        ask_volumes=[],
        timestamp=datetime.utcnow().timestamp(),
        source=source,
    )


def _sample_quote(symbol: str) -> Quote:
    symbol = normalize_symbol(symbol)
    seed = sum(ord(c) for c in symbol)
    base = 8 + seed % 50
    price = base + math.sin(datetime.utcnow().minute / 60 + seed) * 0.2
    pre_close = base
    return Quote(
        symbol=symbol,
        name="",
        price=round(price, 3),
        change_pct=round((price - pre_close) / pre_close * 100, 2),
        volume=0,
        amount=0,
        high=round(max(price, pre_close) * 1.01, 3),
        low=round(min(price, pre_close) * 0.99, 3),
        open=round(pre_close, 3),
        pre_close=round(pre_close, 3),
        bid_prices=[],
        bid_volumes=[],
        ask_prices=[],
        ask_volumes=[],
        timestamp=datetime.utcnow().timestamp(),
        source="sample",
    )


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
