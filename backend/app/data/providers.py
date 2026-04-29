from __future__ import annotations

import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol

from app.models import DailyBar


class DailyBarProvider(Protocol):
    def fetch_daily_bars(self, symbol: str, end: Optional[date] = None) -> list[DailyBar]:
        ...


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(".SH", "").replace(".SZ", "")


def infer_exchange(symbol: str) -> str:
    s = normalize_symbol(symbol)
    if s.startswith(("5", "6", "9")):
        return "SSE"
    if s.startswith(("0", "1", "2", "3")):
        return "SZSE"
    if s.startswith("8"):
        return "BSE"
    return "UNKNOWN"


class QuantAxisDailyBarProvider:
    """Reads A-share daily bars from QUANTAXIS, with a sample fallback."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = workspace_root or Path(__file__).resolve().parents[4]
        self.fallback = SampleDailyBarProvider()

    def fetch_daily_bars(self, symbol: str, end: Optional[date] = None) -> list[DailyBar]:
        symbol = normalize_symbol(symbol)
        end = end or date.today()
        try:
            qa_path = self.workspace_root / "QUANTAXIS"
            if qa_path.exists() and str(qa_path) not in sys.path:
                sys.path.insert(0, str(qa_path))

            import QUANTAXIS as QA  # type: ignore

            data = QA.QA_fetch_stock_day_adv(symbol, "all", end.isoformat())
            if data is None:
                return self.fallback.fetch_daily_bars(symbol, end)

            frame = data.data if hasattr(data, "data") else data
            return _frame_to_bars(symbol, frame, end)
        except Exception:
            return self.fallback.fetch_daily_bars(symbol, end)


class SampleDailyBarProvider:
    """Deterministic sample bars for local development and tests."""

    def fetch_daily_bars(self, symbol: str, end: Optional[date] = None) -> list[DailyBar]:
        symbol = normalize_symbol(symbol)
        end = end or date.today()
        start = end - timedelta(days=520)
        bars: list[DailyBar] = []
        close = 9.5 + (sum(ord(c) for c in symbol) % 50) / 10
        day = start
        index = 0
        while day <= end:
            if day.weekday() < 5:
                trend = 0.014 * index
                wave = math.sin(index / 9) * 0.8 + math.sin(index / 29) * 1.4
                breakout = max(0, index - 250) * 0.018
                base = close + trend + wave + breakout
                open_price = base * (1 + math.sin(index / 5) * 0.006)
                close_price = base * (1 + math.cos(index / 7) * 0.008)
                high_price = max(open_price, close_price) * (1.012 + abs(math.sin(index)) * 0.012)
                low_price = min(open_price, close_price) * (0.988 - abs(math.cos(index)) * 0.008)
                volume = 800000 + index * 1700 + abs(math.sin(index / 6)) * 350000
                if index in (245, 246, 247, 270):
                    volume *= 2.3
                turnover = volume * close_price
                bars.append(
                    DailyBar(
                        symbol=symbol,
                        exchange=infer_exchange(symbol),
                        date=day,
                        open=round(open_price, 3),
                        high=round(high_price, 3),
                        low=round(low_price, 3),
                        close=round(close_price, 3),
                        volume=round(volume, 2),
                        turnover=round(turnover, 2),
                    )
                )
                index += 1
            day += timedelta(days=1)
        return bars


def _frame_to_bars(symbol: str, frame, end: date) -> list[DailyBar]:
    if frame.empty:
        return []

    df = frame.reset_index(drop=True).copy()
    if "date" not in df.columns and "datetime" in df.columns:
        df["date"] = df["datetime"]
    import pandas as pd

    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[df["date"] <= end].sort_values("date")

    bars: list[DailyBar] = []
    for row in df.to_dict("records"):
        volume = float(row.get("volume", row.get("vol", 0)) or 0)
        bars.append(
            DailyBar(
                symbol=symbol,
                exchange=infer_exchange(symbol),
                date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=volume,
                turnover=float(row.get("turnover", row.get("amount", 0)) or 0),
            )
        )
    return bars
