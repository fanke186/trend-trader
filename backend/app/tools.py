from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.models import (
    AnalyzeRequest,
    ConditionOrder,
    EventRecord,
    ScheduleSpec,
    StockPool,
    StockPoolItem,
    ToolDefinition,
    ToolInvokeResult,
)


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Tool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, service: Any) -> None:
        self.service = service
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def list_definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in sorted(self._tools.values(), key=lambda item: item.definition.name)]

    def invoke(self, name: str, arguments: dict[str, Any], source: str = "api", confirmed: bool = False) -> ToolInvokeResult:
        if name not in self._tools:
            result = ToolInvokeResult(tool_name=name, status="error", error=f"unknown tool: {name}")
            result.invocation_id = self.service.repository.log_tool_invocation(
                name, source, result.status, arguments, result.output, result.error
            )
            return result

        tool = self._tools[name]
        if tool.definition.requires_confirmation and not confirmed:
            result = ToolInvokeResult(
                tool_name=name,
                status="confirmation_required",
                output={"message": "tool requires explicit confirmation"},
                requires_confirmation=True,
            )
            result.invocation_id = self.service.repository.log_tool_invocation(
                name,
                source,
                result.status,
                arguments,
                result.output,
                requires_confirmation=True,
            )
            return result

        try:
            output = tool.handler(arguments)
            result = ToolInvokeResult(tool_name=name, status="ok", output=output)
            result.invocation_id = self.service.repository.log_tool_invocation(
                name, source, result.status, arguments, result.output, requires_confirmation=tool.definition.requires_confirmation
            )
            return result
        except Exception as exc:
            result = ToolInvokeResult(tool_name=name, status="error", error=str(exc))
            result.invocation_id = self.service.repository.log_tool_invocation(
                name, source, result.status, arguments, result.output, result.error
            )
            return result

    def register(
        self,
        name: str,
        description: str,
        handler: ToolHandler,
        input_schema: dict[str, Any] | None = None,
        requires_confirmation: bool = False,
        category: str = "system",
    ) -> None:
        self._tools[name] = Tool(
            definition=ToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema or {},
                requires_confirmation=requires_confirmation,
                category=category,
            ),
            handler=handler,
        )

    def _register_defaults(self) -> None:
        self.register(
            "strategy.analyze",
            "Analyze one A-share symbol with a saved strategy.",
            self._strategy_analyze,
            {"symbol": "string", "strategy_name": "string"},
            category="strategy",
        )
        self.register(
            "strategy.screener_run",
            "Run a strategy against a symbol list and rank results.",
            self._strategy_screener_run,
            {"symbols": "string[]", "strategy_name": "string", "min_score": "number"},
            requires_confirmation=True,
            category="strategy",
        )
        self.register("pool.create", "Create or update a stock pool.", self._pool_create, category="pool")
        self.register("pool.add_symbol", "Add one stock to a pool.", self._pool_add_symbol, category="pool")
        self.register("pool.review", "Run a strategy against every review-enabled stock in a pool.", self._pool_review, requires_confirmation=True, category="pool")
        self.register("condition_order.create", "Create a validated condition order.", self._condition_order_create, category="condition_order")
        self.register("monitor.fetch_quotes", "Fetch realtime A-share quotes with easyquotation fallback.", self._monitor_fetch_quotes, category="monitor")
        self.register("monitor.sync_watchlist", "Sync trade plans into the intraday watchlist.", self._monitor_sync, requires_confirmation=True, category="monitor")
        self.register("schedule.create", "Create or update a workflow schedule.", self._schedule_create, category="schedule")
        self.register("schedule.run", "Run a saved workflow schedule immediately.", self._schedule_run, category="schedule")
        self.register("event.list", "List recent system events.", self._event_list, category="event")
        self.register("agent.run", "Run a saved AI agent.", self._agent_run, category="agent")
        self.register("notify.hermes_test", "Send or dry-run a Hermes Feishu notification.", self._notify_hermes, requires_confirmation=True, category="notify")

    def _strategy_analyze(self, args: dict[str, Any]) -> dict[str, Any]:
        result = self.service.analyze(
            AnalyzeRequest(
                symbol=str(args.get("symbol", "")),
                strategy_name=str(args.get("strategy_name") or "trend_trading"),
            )
        )
        return {"analysis": result.model_dump(mode="json")}

    def _strategy_screener_run(self, args: dict[str, Any]) -> dict[str, Any]:
        from app.models import ScreenerRequest

        symbols = args.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [item.strip() for item in symbols.split(",") if item.strip()]
        result = self.service.run_screener(
            ScreenerRequest(
                symbols=list(symbols),
                strategy_name=str(args.get("strategy_name") or "trend_trading"),
                min_score=float(args.get("min_score") or 0),
            )
        )
        return {"screener": result.model_dump(mode="json")}

    def _pool_create(self, args: dict[str, Any]) -> dict[str, Any]:
        pool = StockPool(name=str(args.get("name") or "默认自选"), description=str(args.get("description") or ""))
        return {"pool": self.service.repository.save_pool(pool)}

    def _pool_add_symbol(self, args: dict[str, Any]) -> dict[str, Any]:
        pool_id = int(args.get("pool_id") or 0)
        if not pool_id:
            name = str(args.get("pool_name") or "默认自选")
            pools = [pool for pool in self.service.repository.list_pools() if pool["name"] == name]
            pool = pools[0] if pools else self.service.repository.save_pool(StockPool(name=name))
            pool_id = int(pool["id"])
        item = StockPoolItem(
            pool_id=pool_id,
            symbol=self.service.normalize_symbol(str(args.get("symbol", ""))),
            name=str(args.get("name") or ""),
            group_name=str(args.get("group_name") or "默认"),
            tags=list(args.get("tags") or []),
            notes=str(args.get("notes") or ""),
            review_enabled=bool(args.get("review_enabled", True)),
            monitor_enabled=bool(args.get("monitor_enabled", True)),
        )
        return {"item": self.service.repository.save_pool_item(item)}

    def _pool_review(self, args: dict[str, Any]) -> dict[str, Any]:
        pool_id = args.get("pool_id")
        pool_name = str(args.get("pool_name") or "默认自选")
        pools = self.service.repository.list_pools()
        pool = next((item for item in pools if pool_id and int(item["id"]) == int(pool_id)), None)
        if pool is None:
            pool = next((item for item in pools if item["name"] == pool_name), None)
        if pool is None:
            raise KeyError(f"pool not found: {pool_id or pool_name}")
        symbols = [item["symbol"] for item in pool.get("items", []) if item.get("review_enabled", True)]
        from app.models import ScreenerRequest

        result = self.service.run_screener(
            ScreenerRequest(
                symbols=symbols,
                strategy_name=str(args.get("strategy_name") or "trend_trading"),
                min_score=float(args.get("min_score") or 0),
            )
        )
        return {"pool": pool, "screener": result.model_dump(mode="json")}

    def _condition_order_create(self, args: dict[str, Any]) -> dict[str, Any]:
        condition = args.get("condition") or {}
        self.service.validate_condition(condition)
        order = ConditionOrder(
            name=str(args.get("name") or f"{args.get('symbol')}-condition"),
            symbol=self.service.normalize_symbol(str(args.get("symbol", ""))),
            order_type=args.get("order_type") or "notify",
            condition=condition,
            action=dict(args.get("action") or {}),
            strategy_name=str(args.get("strategy_name") or "trend_trading"),
            dedupe_key=str(args.get("dedupe_key") or ""),
        )
        return {"condition_order": self.service.repository.save_condition_order(order)}

    def _monitor_sync(self, args: dict[str, Any]) -> dict[str, Any]:
        synced = self.service.repository.sync_watchlist_from_plans()
        return {"synced": synced}

    def _monitor_fetch_quotes(self, args: dict[str, Any]) -> dict[str, Any]:
        symbols = args.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [item.strip() for item in symbols.split(",") if item.strip()]
        return {"quotes": self.service.fetch_quotes(list(symbols))}

    def _schedule_create(self, args: dict[str, Any]) -> dict[str, Any]:
        schedule = ScheduleSpec(**args)
        self.service.validate_workflow(schedule.workflow)
        saved = self.service.repository.save_generic("schedules", schedule.model_dump(mode="json"))
        return {"schedule": saved}

    def _schedule_run(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"run": self.service.run_schedule(int(args.get("schedule_id") or args.get("id")))}

    def _event_list(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"events": self.service.repository.list_events(int(args.get("limit") or 100))}

    def _agent_run(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_id = int(args.get("agent_id") or args.get("id"))
        result = self.service.run_agent(agent_id, str(args.get("prompt") or ""), dict(args.get("context") or {}))
        return {"agent_run": result.model_dump(mode="json")}

    def _notify_hermes(self, args: dict[str, Any]) -> dict[str, Any]:
        message = str(args.get("message") or "trend-trader notification test")
        dry_run = bool(args.get("dry_run", True))
        output = self.service.notify_hermes(message, dry_run=dry_run)
        self.service.repository.save_event(
            EventRecord(
                category="notification",
                source="notify.hermes_test",
                title="Hermes Feishu notification",
                message=message,
                status="dry_run" if dry_run else output.get("status", "sent"),
                payload=output,
            )
        )
        return output
