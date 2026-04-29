from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.models import (
    AlertEvent,
    ChatMessage,
    ChatSession,
    ConditionOrder,
    EventRecord,
    ScheduleRun,
    ScheduleSpec,
    StockPool,
    StockPoolItem,
    StrategyAnalysis,
    TradePlan,
)
from app.storage.migrations import MigrationRunner


GENERIC_TABLES = {
    "model_providers": "model_providers",
    "model_profiles": "model_profiles",
    "skills": "skills",
    "agents": "agents",
    "agent_teams": "agent_teams",
    "strategy_specs": "strategy_specs",
    "condition_orders": "condition_orders",
    "schedules": "schedules",
}


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        MigrationRunner(db_path).run()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists analyses (
                    id integer primary key autoincrement,
                    symbol text not null,
                    strategy_name text not null,
                    as_of text not null,
                    score real not null,
                    status text not null,
                    payload text not null,
                    created_at text not null
                );

                create table if not exists plans (
                    id integer primary key autoincrement,
                    symbol text not null,
                    strategy_name text not null,
                    status text not null,
                    entry_price real,
                    stop_loss real,
                    take_profit real,
                    risk_reward_ratio real,
                    payload text not null,
                    created_at text not null
                );

                create table if not exists watchlist (
                    id integer primary key autoincrement,
                    symbol text not null,
                    strategy_name text not null,
                    entry_price real,
                    stop_loss real,
                    take_profit real,
                    status text not null,
                    plan_payload text not null,
                    created_at text not null,
                    unique(symbol, strategy_name)
                );

                create table if not exists alerts (
                    id integer primary key autoincrement,
                    symbol text not null,
                    strategy_name text not null,
                    trigger_type text not null,
                    price real not null,
                    message text not null,
                    created_at text not null,
                    delivered_channels text not null default '[]',
                    unique(symbol, strategy_name, trigger_type)
                );

                create table if not exists model_providers (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists model_profiles (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists skills (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists agents (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists agent_teams (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists strategy_specs (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists condition_orders (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'active',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists schedules (
                    id integer primary key autoincrement,
                    name text not null unique,
                    enabled integer not null default 1,
                    status text not null default 'enabled',
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists tool_invocations (
                    id integer primary key autoincrement,
                    tool_name text not null,
                    source text not null,
                    status text not null,
                    requires_confirmation integer not null default 0,
                    arguments text not null,
                    output text not null,
                    error text,
                    created_at text not null
                );

                create table if not exists ai_runs (
                    id integer primary key autoincrement,
                    agent_id integer,
                    team_id integer,
                    status text not null,
                    input text not null,
                    output text not null,
                    created_at text not null
                );

                create table if not exists chat_sessions (
                    id integer primary key autoincrement,
                    title text not null,
                    agent_id integer,
                    model_profile_id integer,
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists chat_messages (
                    id integer primary key autoincrement,
                    session_id integer not null,
                    role text not null,
                    content text not null,
                    payload text not null,
                    created_at text not null
                );

                create table if not exists stock_pools (
                    id integer primary key autoincrement,
                    name text not null unique,
                    description text not null default '',
                    enabled integer not null default 1,
                    payload text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists stock_pool_items (
                    id integer primary key autoincrement,
                    pool_id integer not null,
                    symbol text not null,
                    name text not null default '',
                    group_name text not null default '默认',
                    tags text not null default '[]',
                    notes text not null default '',
                    review_enabled integer not null default 1,
                    monitor_enabled integer not null default 1,
                    sort_order integer not null default 0,
                    payload text not null,
                    created_at text not null,
                    updated_at text not null,
                    unique(pool_id, symbol)
                );

                create table if not exists events (
                    id integer primary key autoincrement,
                    category text not null,
                    source text not null,
                    title text not null,
                    message text not null,
                    status text not null,
                    payload text not null,
                    created_at text not null
                );

                create table if not exists schedule_runs (
                    id integer primary key autoincrement,
                    schedule_id integer not null,
                    status text not null,
                    output text not null,
                    error text,
                    started_at text not null,
                    finished_at text
                );
                """
            )

    def _json_dumps(self, value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        return json.dumps(value, ensure_ascii=False, default=str)

    def _json_loads(self, value: str) -> dict[str, Any]:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {"value": loaded}

    def _generic_table(self, table_key: str) -> str:
        try:
            return GENERIC_TABLES[table_key]
        except KeyError as exc:
            raise KeyError(f"unknown table {table_key}") from exc

    def save_generic(self, table_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        table = self._generic_table(table_key)
        now = datetime.utcnow().isoformat()
        payload = dict(payload)
        name = str(payload.get("name") or payload.get("title") or table_key)
        enabled = 1 if payload.get("enabled", True) else 0
        status = str(payload.get("status") or ("enabled" if table_key == "schedules" else "active"))
        with self._connect() as conn:
            if payload.get("id"):
                conn.execute(
                    f"""
                    update {table}
                    set name = ?, enabled = ?, status = ?, payload = ?, updated_at = ?
                    where id = ?
                    """,
                    (name, enabled, status, self._json_dumps(payload), now, payload["id"]),
                )
                row_id = int(payload["id"])
            else:
                cur = conn.execute(
                    f"""
                    insert into {table}(name, enabled, status, payload, created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?)
                    on conflict(name) do update set
                        enabled=excluded.enabled,
                        status=excluded.status,
                        payload=excluded.payload,
                        updated_at=excluded.updated_at
                    """,
                    (name, enabled, status, self._json_dumps(payload), now, now),
                )
                row = conn.execute(f"select id from {table} where name = ?", (name,)).fetchone()
                row_id = int(row["id"] if row else cur.lastrowid)
        return self.get_generic(table_key, row_id)

    def list_generic(self, table_key: str, limit: int = 200) -> list[dict[str, Any]]:
        table = self._generic_table(table_key)
        with self._connect() as conn:
            rows = conn.execute(f"select * from {table} order by updated_at desc limit ?", (limit,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["enabled"] = bool(row["enabled"])
            payload["status"] = row["status"]
            payload["created_at"] = payload.get("created_at", row["created_at"])
            payload["updated_at"] = row["updated_at"]
            result.append(payload)
        return result

    def get_generic(self, table_key: str, record_id: int) -> dict[str, Any]:
        table = self._generic_table(table_key)
        with self._connect() as conn:
            row = conn.execute(f"select * from {table} where id = ?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(f"{table_key} {record_id} not found")
        payload = self._json_loads(row["payload"])
        payload["id"] = row["id"]
        payload["enabled"] = bool(row["enabled"])
        payload["status"] = row["status"]
        payload["created_at"] = payload.get("created_at", row["created_at"])
        payload["updated_at"] = row["updated_at"]
        return payload

    def save_analysis(self, analysis: StrategyAnalysis) -> None:
        payload = analysis.model_dump_json()
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            try:
                conn.execute("begin")
                conn.execute(
                    """
                    insert into analyses(symbol, strategy_name, as_of, score, status, payload, created_at)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis.symbol,
                        analysis.strategy_name,
                        analysis.as_of.isoformat(),
                        analysis.score,
                        analysis.status,
                        payload,
                        now,
                    ),
                )
                if analysis.trade_plan:
                    plan = analysis.trade_plan
                    conn.execute(
                        """
                        insert into plans(
                            symbol, strategy_name, status, entry_price, stop_loss, take_profit,
                            risk_reward_ratio, payload, created_at
                        )
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            plan.symbol,
                            plan.strategy_name,
                            plan.status,
                            plan.entry_price,
                            plan.stop_loss,
                            plan.take_profit,
                            plan.risk_reward_ratio,
                            plan.model_dump_json(),
                            plan.created_at.isoformat(),
                        ),
                    )
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise

    def save_plan(self, plan: TradePlan) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into plans(
                    symbol, strategy_name, status, entry_price, stop_loss, take_profit,
                    risk_reward_ratio, payload, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.symbol,
                    plan.strategy_name,
                    plan.status,
                    plan.entry_price,
                    plan.stop_loss,
                    plan.take_profit,
                    plan.risk_reward_ratio,
                    plan.model_dump_json(),
                    plan.created_at.isoformat(),
                ),
            )

    def list_plans(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from plans order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def sync_watchlist_from_plans(self) -> int:
        plans = self.list_plans(limit=500)
        synced = 0
        with self._connect() as conn:
            for row in plans:
                if row["status"] not in ("watch", "triggered"):
                    continue
                plan = json.loads(row["payload"])
                if not plan.get("entry_price"):
                    continue
                conn.execute(
                    """
                    insert into watchlist(
                        symbol, strategy_name, entry_price, stop_loss, take_profit,
                        status, plan_payload, created_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(symbol, strategy_name) do update set
                        entry_price=excluded.entry_price,
                        stop_loss=excluded.stop_loss,
                        take_profit=excluded.take_profit,
                        status=excluded.status,
                        plan_payload=excluded.plan_payload,
                        created_at=excluded.created_at
                    """,
                    (
                        plan["symbol"],
                        plan["strategy_name"],
                        plan.get("entry_price"),
                        plan.get("stop_loss"),
                        plan.get("take_profit"),
                        plan.get("status"),
                        row["payload"],
                        datetime.utcnow().isoformat(),
                    ),
                )
                synced += 1
        return synced

    def evaluate_tick(self, symbol: str, price: float) -> list[AlertEvent]:
        now = datetime.utcnow().isoformat()
        alerts: list[AlertEvent] = []
        with self._connect() as conn:
            rows = conn.execute(
                "select * from watchlist where symbol = ? and status in ('watch', 'triggered')",
                (symbol,),
            ).fetchall()
            for row in rows:
                plan = json.loads(row["plan_payload"])
                checks = [
                    ("entry", row["entry_price"], price >= row["entry_price"] if row["entry_price"] else False),
                    ("stop_loss", row["stop_loss"], price <= row["stop_loss"] if row["stop_loss"] else False),
                    ("take_profit", row["take_profit"], price >= row["take_profit"] if row["take_profit"] else False),
                ]
                for trigger_type, trigger_price, fired in checks:
                    if not fired:
                        continue
                    message = (
                        f"{symbol} {row['strategy_name']} {trigger_type} triggered at {price:.3f}; "
                        f"plan price {trigger_price:.3f}"
                    )
                    try:
                        cur = conn.execute(
                            """
                            insert into alerts(symbol, strategy_name, trigger_type, price, message, created_at, delivered_channels)
                            values (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                symbol,
                                row["strategy_name"],
                                trigger_type,
                                price,
                                message,
                                now,
                                json.dumps(["local"]),
                            ),
                        )
                    except sqlite3.IntegrityError:
                        continue
                    alerts.append(
                        AlertEvent(
                            id=int(cur.lastrowid),
                            symbol=symbol,
                            strategy_name=row["strategy_name"],
                            trigger_type=trigger_type,
                            price=price,
                            message=message,
                            created_at=datetime.fromisoformat(now),
                            delivered_channels=["local"],
                        )
                    )
        return alerts

    def list_alerts(self, limit: int = 100) -> list[AlertEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from alerts order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [
            AlertEvent(
                id=row["id"],
                symbol=row["symbol"],
                strategy_name=row["strategy_name"],
                trigger_type=row["trigger_type"],
                price=row["price"],
                message=row["message"],
                created_at=datetime.fromisoformat(row["created_at"]),
                delivered_channels=json.loads(row["delivered_channels"]),
            )
            for row in rows
        ]

    def log_tool_invocation(
        self,
        tool_name: str,
        source: str,
        status: str,
        arguments: dict[str, Any],
        output: dict[str, Any],
        error: str | None = None,
        requires_confirmation: bool = False,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into tool_invocations(
                    tool_name, source, status, requires_confirmation, arguments, output, error, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_name,
                    source,
                    status,
                    1 if requires_confirmation else 0,
                    self._json_dumps(arguments),
                    self._json_dumps(output),
                    error,
                    datetime.utcnow().isoformat(),
                ),
            )
        return int(cur.lastrowid)

    def list_tool_invocations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from tool_invocations order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [
            {
                **dict(row),
                "requires_confirmation": bool(row["requires_confirmation"]),
                "arguments": json.loads(row["arguments"]),
                "output": json.loads(row["output"]),
            }
            for row in rows
        ]

    def save_ai_run(
        self,
        agent_id: int | None,
        team_id: int | None,
        status: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into ai_runs(agent_id, team_id, status, input, output, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    team_id,
                    status,
                    self._json_dumps(input_payload),
                    self._json_dumps(output_payload),
                    datetime.utcnow().isoformat(),
                ),
            )
        return int(cur.lastrowid)

    def list_ai_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from ai_runs order by created_at desc limit ?", (limit,)).fetchall()
        return [
            {
                **dict(row),
                "input": json.loads(row["input"]),
                "output": json.loads(row["output"]),
            }
            for row in rows
        ]

    def save_chat_session(self, session: ChatSession) -> dict[str, Any]:
        payload = session.model_dump(mode="json")
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if session.id:
                conn.execute(
                    """
                    update chat_sessions
                    set title = ?, agent_id = ?, model_profile_id = ?, payload = ?, updated_at = ?
                    where id = ?
                    """,
                    (
                        session.title,
                        session.agent_id,
                        session.model_profile_id,
                        self._json_dumps(payload),
                        now,
                        session.id,
                    ),
                )
                row_id = session.id
            else:
                cur = conn.execute(
                    """
                    insert into chat_sessions(title, agent_id, model_profile_id, payload, created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.title,
                        session.agent_id,
                        session.model_profile_id,
                        self._json_dumps(payload),
                        now,
                        now,
                    ),
                )
                row_id = int(cur.lastrowid)
        return self.get_chat_session(row_id)

    def list_chat_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from chat_sessions order by updated_at desc limit ?", (limit,)).fetchall()
        result = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["title"] = row["title"]
            payload["updated_at"] = row["updated_at"]
            result.append(payload)
        return result

    def get_chat_session(self, session_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from chat_sessions where id = ?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(f"chat session {session_id} not found")
        payload = self._json_loads(row["payload"])
        payload["id"] = row["id"]
        payload["title"] = row["title"]
        payload["updated_at"] = row["updated_at"]
        return payload

    def save_chat_message(self, message: ChatMessage) -> dict[str, Any]:
        payload = message.model_dump(mode="json")
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into chat_messages(session_id, role, content, payload, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    message.session_id,
                    message.role,
                    message.content,
                    self._json_dumps(payload),
                    message.created_at.isoformat(),
                ),
            )
            conn.execute(
                "update chat_sessions set updated_at = ? where id = ?",
                (datetime.utcnow().isoformat(), message.session_id),
            )
        payload["id"] = int(cur.lastrowid)
        return payload

    def list_chat_messages(self, session_id: int, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select * from chat_messages
                where session_id = ?
                order by created_at asc
                limit ?
                """,
                (session_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["role"] = row["role"]
            payload["content"] = row["content"]
            payload["created_at"] = row["created_at"]
            result.append(payload)
        return result

    def save_pool(self, pool: StockPool) -> dict[str, Any]:
        payload = pool.model_dump(mode="json")
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if pool.id:
                conn.execute(
                    """
                    update stock_pools
                    set name = ?, description = ?, enabled = ?, payload = ?, updated_at = ?
                    where id = ?
                    """,
                    (pool.name, pool.description, int(pool.enabled), self._json_dumps(payload), now, pool.id),
                )
                row_id = pool.id
            else:
                cur = conn.execute(
                    """
                    insert into stock_pools(name, description, enabled, payload, created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?)
                    on conflict(name) do update set
                        description=excluded.description,
                        enabled=excluded.enabled,
                        payload=excluded.payload,
                        updated_at=excluded.updated_at
                    """,
                    (pool.name, pool.description, int(pool.enabled), self._json_dumps(payload), now, now),
                )
                row_id = int(cur.lastrowid or conn.execute("select id from stock_pools where name = ?", (pool.name,)).fetchone()["id"])
        return self.get_pool(row_id)

    def get_pool(self, pool_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from stock_pools where id = ?", (pool_id,)).fetchone()
        if row is None:
            raise KeyError(f"pool {pool_id} not found")
        payload = self._json_loads(row["payload"])
        payload["id"] = row["id"]
        payload["enabled"] = bool(row["enabled"])
        return payload

    def list_pools(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from stock_pools order by name asc").fetchall()
        pools: list[dict[str, Any]] = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["enabled"] = bool(row["enabled"])
            payload["items"] = self.list_pool_items(row["id"])
            pools.append(payload)
        return pools

    def save_pool_item(self, item: StockPoolItem) -> dict[str, Any]:
        payload = item.model_dump(mode="json")
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into stock_pool_items(
                    pool_id, symbol, name, group_name, tags, notes, review_enabled,
                    monitor_enabled, sort_order, payload, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(pool_id, symbol) do update set
                    name=excluded.name,
                    group_name=excluded.group_name,
                    tags=excluded.tags,
                    notes=excluded.notes,
                    review_enabled=excluded.review_enabled,
                    monitor_enabled=excluded.monitor_enabled,
                    sort_order=excluded.sort_order,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    item.pool_id,
                    item.symbol,
                    item.name,
                    item.group_name,
                    self._json_dumps(item.tags),
                    item.notes,
                    int(item.review_enabled),
                    int(item.monitor_enabled),
                    item.sort_order,
                    self._json_dumps(payload),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "select id from stock_pool_items where pool_id = ? and symbol = ?",
                (item.pool_id, item.symbol),
            ).fetchone()
        row_id = int(row["id"] if row else cur.lastrowid)
        return self.get_pool_item(row_id)

    def get_pool_item(self, item_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from stock_pool_items where id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(f"pool item {item_id} not found")
        payload = self._json_loads(row["payload"])
        payload["id"] = row["id"]
        payload["tags"] = json.loads(row["tags"])
        payload["review_enabled"] = bool(row["review_enabled"])
        payload["monitor_enabled"] = bool(row["monitor_enabled"])
        return payload

    def list_pool_items(self, pool_id: int | None = None) -> list[dict[str, Any]]:
        sql = "select * from stock_pool_items"
        params: tuple[Any, ...] = ()
        if pool_id is not None:
            sql += " where pool_id = ?"
            params = (pool_id,)
        sql += " order by group_name asc, sort_order asc, symbol asc"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["tags"] = json.loads(row["tags"])
            payload["review_enabled"] = bool(row["review_enabled"])
            payload["monitor_enabled"] = bool(row["monitor_enabled"])
            result.append(payload)
        return result

    def save_event(self, event: EventRecord) -> dict[str, Any]:
        payload = event.model_dump(mode="json")
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into events(category, source, title, message, status, payload, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.category,
                    event.source,
                    event.title,
                    event.message,
                    event.status,
                    self._json_dumps(payload),
                    event.created_at.isoformat(),
                ),
            )
        payload["id"] = int(cur.lastrowid)
        return payload

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from events order by created_at desc limit ?", (limit,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = self._json_loads(row["payload"])
            payload["id"] = row["id"]
            payload["category"] = row["category"]
            payload["source"] = row["source"]
            payload["title"] = row["title"]
            payload["message"] = row["message"]
            payload["status"] = row["status"]
            payload["created_at"] = row["created_at"]
            result.append(payload)
        return result

    def cleanup_events(self, max_days: int = 30, max_count: int = 10000) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=max_days)).isoformat()
        deleted = 0
        with self._connect() as conn:
            deleted = int(conn.execute("delete from events where created_at < ?", (cutoff,)).rowcount or 0)
            count = int(conn.execute("select count(*) from events").fetchone()[0])
            if count > max_count:
                excess = count - max_count
                deleted += int(
                    conn.execute(
                        "delete from events where id in (select id from events order by created_at asc limit ?)",
                        (excess,),
                    ).rowcount
                    or 0
                )
        return deleted

    def save_backtest_run(self, strategy_spec_id: int, symbol: str, start_date: str, end_date: str, status: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into backtest_runs(strategy_spec_id, symbol, start_date, end_date, status, payload, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (strategy_spec_id, symbol, start_date, end_date, status, self._json_dumps(payload), now),
            )
        return {"id": int(cur.lastrowid), "strategy_spec_id": strategy_spec_id, "symbol": symbol, "start_date": start_date, "end_date": end_date, "status": status, "payload": payload, "created_at": now}

    def list_backtest_runs(self, strategy_spec_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from backtest_runs where strategy_spec_id = ? order by created_at desc limit ?",
                (strategy_spec_id, limit),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def save_schedule_run(self, run: ScheduleRun) -> dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into schedule_runs(schedule_id, status, output, error, started_at, finished_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.schedule_id,
                    run.status,
                    self._json_dumps(run.output),
                    run.error,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                ),
            )
        payload = run.model_dump(mode="json")
        payload["id"] = int(cur.lastrowid)
        return payload

    def list_schedule_runs(self, schedule_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select * from schedule_runs
                where schedule_id = ?
                order by started_at desc
                limit ?
                """,
                (schedule_id, limit),
            ).fetchall()
        return [
            {
                **dict(row),
                "output": json.loads(row["output"]),
            }
            for row in rows
        ]

    def list_enabled_schedules(self) -> list[ScheduleSpec]:
        return [ScheduleSpec(**row) for row in self.list_generic("schedules") if row.get("status") == "enabled"]

    def save_condition_order(self, order: ConditionOrder) -> dict[str, Any]:
        return self.save_generic("condition_orders", order.model_dump(mode="json"))
