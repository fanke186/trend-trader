from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from app.data.providers import infer_exchange, normalize_symbol
from app.models import DailyBar


class KlineDatabase:
    """DuckDB-compatible K-line repository.

    Uses DuckDB when available and sqlite as a deterministic local fallback so
    tests and development keep working without optional market-data tooling.
    """

    def __init__(self, db_path: str | Path, parquet_dir: str | Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.parquet_dir = Path(parquet_dir) if parquet_dir else self.db_path.parent / "kline_parquet"
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        self._duckdb = False
        self._lock = threading.RLock()
        try:
            import duckdb  # type: ignore

            self._conn = duckdb.connect(str(self.db_path))
            self._duckdb = True
        except Exception:
            self._conn = sqlite3.connect(str(self.db_path.with_suffix(".sqlite3")), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._execute(
            """
            create table if not exists securities (
                symbol_id integer primary key,
                code text not null unique,
                name text not null,
                exchange text not null,
                board text,
                list_date date,
                delist_date date,
                status text not null default 'active'
            )
            """
        )
        self._execute("create table if not exists trade_calendar (trade_date date primary key, is_open boolean not null)")
        for table in ("bars_1d", "bars_1w", "bars_1M"):
            self._execute(
                f"""
                create table if not exists {table} (
                    symbol_id integer not null,
                    trade_date date not null,
                    open real not null,
                    high real not null,
                    low real not null,
                    close real not null,
                    pre_close real,
                    volume real not null,
                    amount real not null,
                    turnover real,
                    adj_factor real,
                    limit_up real,
                    limit_down real,
                    is_st boolean default false,
                    primary key (symbol_id, trade_date)
                )
                """
            )

    def get_bars(self, symbol: str, frequency: str = "1d", start_date: Optional[date] = None, end_date: Optional[date] = None, limit: int = 500) -> list[DailyBar]:
        table = _bar_table(frequency)
        symbol = normalize_symbol(symbol)
        symbol_id = self._get_symbol_id(symbol, create=False)
        if symbol_id is None:
            return []
        query = f"""
            select b.trade_date, b.open, b.high, b.low, b.close, b.volume, b.amount, b.turnover, s.code, s.exchange
            from {table} b join securities s on b.symbol_id = s.symbol_id
            where b.symbol_id = ?
        """
        params: list[object] = [symbol_id]
        if start_date:
            query += " and b.trade_date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " and b.trade_date <= ?"
            params.append(end_date.isoformat())
        query += " order by b.trade_date desc limit ?"
        params.append(limit)
        rows = self._fetchall(query, params)
        bars = [
            DailyBar(
                symbol=row["code"],
                exchange=row["exchange"],
                date=_to_date(row["trade_date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                turnover=float(row["turnover"] or row["amount"] or 0),
            )
            for row in rows
        ]
        return list(reversed(bars))

    def update_bars(self, frequency: str, bars: list[DailyBar]) -> None:
        if not bars:
            return
        table = _bar_table(frequency)
        for bar in bars:
            symbol_id = self._get_symbol_id(bar.symbol, create=True, exchange=bar.exchange)
            if self._duckdb:
                self._execute(
                    f"""
                    insert or replace into {table} (
                        symbol_id, trade_date, open, high, low, close, pre_close, volume, amount, turnover
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [symbol_id, bar.date.isoformat(), bar.open, bar.high, bar.low, bar.close, None, bar.volume, bar.turnover, bar.turnover],
                )
            else:
                self._execute(
                    f"""
                    insert or replace into {table} (
                        symbol_id, trade_date, open, high, low, close, pre_close, volume, amount, turnover
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [symbol_id, bar.date.isoformat(), bar.open, bar.high, bar.low, bar.close, None, bar.volume, bar.turnover, bar.turnover],
                )

    def get_all_symbols(self) -> list[dict]:
        return [dict(row) for row in self._fetchall("select * from securities where status = 'active' order by code", [])]

    def is_trade_day(self, d: date) -> bool:
        row = self._fetchone("select is_open from trade_calendar where trade_date = ?", [d.isoformat()])
        if row is None:
            return d.weekday() < 5
        return bool(row["is_open"])

    def seed_symbols_from_bars(self, bars_by_symbol: dict[str, list[DailyBar]]) -> None:
        for bars in bars_by_symbol.values():
            self.update_bars("1d", bars)

    def aggregate_weekly(self, today: date | None = None) -> None:
        return None

    def aggregate_monthly(self, today: date | None = None) -> None:
        return None

    def _get_symbol_id(self, symbol: str, create: bool = True, exchange: str | None = None) -> int | None:
        symbol = normalize_symbol(symbol)
        row = self._fetchone("select symbol_id from securities where code = ?", [symbol])
        if row:
            return int(row["symbol_id"])
        if not create:
            return None
        current = self._fetchone("select max(symbol_id) as max_id from securities", [])
        next_id = int((current["max_id"] if current and current["max_id"] is not None else 0) or 0) + 1
        self._execute(
            "insert into securities(symbol_id, code, name, exchange, status) values (?, ?, ?, ?, 'active')",
            [next_id, symbol, "", exchange or infer_exchange(symbol)],
        )
        return next_id

    def _execute(self, sql: str, params: list[object] | None = None) -> None:
        with self._lock:
            self._conn.execute(sql, params or [])
            if not self._duckdb:
                self._conn.commit()

    def _fetchone(self, sql: str, params: list[object]) -> dict | None:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row, sqlite3.Row):
                return dict(row)
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    def _fetchall(self, sql: str, params: list[object]) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return []
            if isinstance(rows[0], sqlite3.Row):
                return [dict(row) for row in rows]
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]


def _bar_table(frequency: str) -> str:
    mapping = {"1d": "bars_1d", "1w": "bars_1w", "1M": "bars_1M"}
    if frequency not in mapping:
        raise ValueError(f"unsupported kline frequency: {frequency}")
    return mapping[frequency]


def _to_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
