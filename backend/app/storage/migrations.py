from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class MigrationRunner:
    """Tiny append-only SQLite migration runner."""

    MIGRATIONS: dict[int, str] = {
        1: """
        create table if not exists backtest_runs (
            id integer primary key autoincrement,
            strategy_spec_id integer not null,
            symbol text not null,
            start_date text not null,
            end_date text not null,
            status text not null,
            payload text not null,
            created_at text not null
        );
        create table if not exists agent_memories (
            id integer primary key autoincrement,
            agent_id integer,
            session_id text not null,
            memory_type text not null,
            content text not null,
            created_at text not null
        );
        create table if not exists trade_orders (
            id integer primary key autoincrement,
            order_type text not null,
            symbol text not null,
            price real,
            volume integer,
            status text not null,
            mode text not null,
            entrust_no text,
            filled_price real,
            filled_volume integer,
            condition_order_id integer,
            payload text not null,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists positions (
            id integer primary key autoincrement,
            symbol text not null,
            volume integer not null,
            avg_cost real not null,
            market_value real,
            unrealized_pnl real,
            mode text not null,
            updated_at text not null,
            unique(symbol, mode)
        );
        """,
    }

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def run(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists schema_migrations (
                    version integer primary key,
                    applied_at text not null
                )
                """
            )
            applied = {int(row[0]) for row in conn.execute("select version from schema_migrations").fetchall()}
            for version in sorted(self.MIGRATIONS):
                if version in applied:
                    continue
                conn.executescript(self.MIGRATIONS[version])
                conn.execute("insert into schema_migrations(version, applied_at) values (?, ?)", (version, datetime.utcnow().isoformat()))
