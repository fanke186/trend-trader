from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    AlertEvent,
    AgentRunRequest,
    AgentSpec,
    AgentTeamSpec,
    AnalyzeRequest,
    ChatMessage,
    ChatMessageRequest,
    ChatSession,
    ConditionOrder,
    GenerateSkillRequest,
    ModelProfile,
    ModelProvider,
    ScheduleSpec,
    ScreenerRequest,
    ScreenerResult,
    SkillSpec,
    StockPool,
    StockPoolItem,
    StrategySpec,
    TickInput,
    ToolInvokeRequest,
    WatchlistSyncResult,
)
from app.services import TrendTraderService


DATA_DIR = Path(__file__).resolve().parents[1] / ".data"
service = TrendTraderService(DATA_DIR)

app = FastAPI(title="trend-trader", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

alert_clients: set[WebSocket] = set()
quote_clients: set[WebSocket] = set()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    try:
        return service.analyze(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/ai/providers")
def list_model_providers():
    return service.repository.list_generic("model_providers")


@app.post("/api/ai/providers")
def save_model_provider(provider: ModelProvider):
    return service.repository.save_generic("model_providers", provider.model_dump(mode="json"))


@app.get("/api/ai/model-profiles")
def list_model_profiles():
    return service.repository.list_generic("model_profiles")


@app.post("/api/ai/model-profiles")
def save_model_profile(profile: ModelProfile):
    return service.repository.save_generic("model_profiles", profile.model_dump(mode="json"))


@app.post("/api/ai/model-profiles/{profile_id}/test")
def test_model_profile(profile_id: int):
    return service.test_model_profile(profile_id)


@app.get("/api/ai/skills")
def list_skills():
    return service.repository.list_generic("skills")


@app.post("/api/ai/skills")
def save_skill(skill: SkillSpec):
    return service.repository.save_generic("skills", skill.model_dump(mode="json"))


@app.post("/api/ai/skills/generate")
def generate_skill(request: GenerateSkillRequest):
    skill = service.generate_skill(request)
    return service.repository.save_generic("skills", skill.model_dump(mode="json"))


@app.post("/api/ai/skills/import")
def import_skill(payload: dict):
    skill = SkillSpec(**payload)
    return service.repository.save_generic("skills", skill.model_dump(mode="json"))


@app.get("/api/ai/agents")
def list_agents():
    return service.repository.list_generic("agents")


@app.post("/api/ai/agents")
def save_agent(agent: AgentSpec):
    return service.repository.save_generic("agents", agent.model_dump(mode="json"))


@app.post("/api/ai/agents/{agent_id}/run")
def run_agent(agent_id: int, request: AgentRunRequest):
    return service.run_agent(agent_id, request.prompt, request.context)


@app.get("/api/ai/teams")
def list_teams():
    return service.repository.list_generic("agent_teams")


@app.post("/api/ai/teams")
def save_team(team: AgentTeamSpec):
    return service.repository.save_generic("agent_teams", team.model_dump(mode="json"))


@app.post("/api/ai/teams/{team_id}/run")
def run_team(team_id: int, request: AgentRunRequest):
    return service.run_team(team_id, request.prompt, request.context)


@app.get("/api/chat/sessions")
def list_chat_sessions():
    return service.repository.list_chat_sessions()


@app.post("/api/chat/sessions")
def create_chat_session(session: ChatSession):
    return service.repository.save_chat_session(session)


@app.get("/api/chat/sessions/{session_id}/messages")
def list_chat_messages(session_id: int):
    return service.repository.list_chat_messages(session_id)


@app.post("/api/chat/sessions/{session_id}/messages")
def send_chat_message(session_id: int, request: ChatMessageRequest):
    try:
        session = service.repository.get_chat_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    user_message = service.repository.save_chat_message(
        ChatMessage(session_id=session_id, role="user", content=request.content, payload={})
    )
    assistant_payload: dict = {}
    content = request.content.strip()
    if content.startswith("/tool "):
        tool_name, arguments = _parse_tool_command(content)
        tool_result = service.tools.invoke(tool_name, arguments, source="chat", confirmed=bool(arguments.get("confirmed")))
        assistant_payload = tool_result.model_dump(mode="json")
        assistant_content = json.dumps(assistant_payload, ensure_ascii=False, indent=2)
    else:
        agent_id = request.agent_id or session.get("agent_id")
        if agent_id:
            result = service.run_agent(int(agent_id), request.content, {"session_id": session_id})
            assistant_payload = result.model_dump(mode="json")
            assistant_content = str(result.output.get("text") or json.dumps(result.output, ensure_ascii=False))
        else:
            assistant_content = (
                "已收到。你可以用 /tool 工具名 JSON参数 调用系统工具，例如："
                '/tool strategy.analyze {"symbol":"002261","strategy_name":"trend_trading"}'
            )
            assistant_payload = {"mode": "local_help"}

    assistant_message = service.repository.save_chat_message(
        ChatMessage(session_id=session_id, role="assistant", content=assistant_content, payload=assistant_payload)
    )
    return {"user": user_message, "assistant": assistant_message}


@app.get("/api/tools")
def list_tools():
    return service.tools.list_definitions()


@app.post("/api/tools/invoke")
def invoke_tool(request: ToolInvokeRequest):
    return service.tools.invoke(request.name, request.arguments, source=request.source, confirmed=request.confirmed)


@app.get("/api/strategies")
def list_strategy_specs():
    return service.repository.list_generic("strategy_specs")


@app.post("/api/strategies")
def save_strategy_spec(strategy: StrategySpec):
    return service.repository.save_generic("strategy_specs", strategy.model_dump(mode="json"))


@app.post("/api/strategies/draft")
def draft_strategy_spec(payload: dict):
    name = str(payload.get("name") or "ai_strategy")
    prompt = str(payload.get("prompt") or "")
    strategy = StrategySpec(
        name=name,
        description="AI generated strategy draft. Review before enabling.",
        source_prompt=prompt,
        features=[{"name": "daily_bars", "source": "ohlcv"}],
        filters=[{"op": "manual_review_required"}],
        scoring=[{"name": "trend_structure", "weight": 40}, {"name": "volume_confirmation", "weight": 30}, {"name": "risk_reward", "weight": 30}],
        explanation=f"该策略草案由 AI 对话生成，原始需求：{prompt[:300]}",
        enabled=False,
    )
    return service.repository.save_generic("strategy_specs", strategy.model_dump(mode="json"))


@app.post("/api/strategies/{strategy_id}/explain")
def explain_strategy(strategy_id: int):
    try:
        return service.explain_strategy(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/strategies/{strategy_id}/backtest")
def run_strategy_backtest(strategy_id: int, payload: dict):
    try:
        return service.run_backtest(
            strategy_id,
            str(payload.get("symbol") or "000001"),
            payload.get("start_date"),
            payload.get("end_date"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/strategies/{strategy_id}/backtests")
def list_strategy_backtests(strategy_id: int):
    return service.list_backtests(strategy_id)


@app.get("/api/pools")
def list_pools():
    return service.repository.list_pools()


@app.post("/api/pools")
def save_pool(pool: StockPool):
    return service.repository.save_pool(pool)


@app.post("/api/pools/{pool_id}/items")
def save_pool_item(pool_id: int, item: StockPoolItem):
    item.pool_id = pool_id
    item.symbol = service.normalize_symbol(item.symbol)
    return service.repository.save_pool_item(item)


@app.get("/api/condition-orders")
def list_condition_orders():
    return service.repository.list_generic("condition_orders")


@app.post("/api/condition-orders")
def save_condition_order(order: ConditionOrder):
    service.validate_condition(order.condition)
    order.symbol = service.normalize_symbol(order.symbol)
    return service.repository.save_condition_order(order)


@app.post("/api/condition-orders/ai-create")
def ai_create_condition_order(payload: dict):
    return service.ai_create_condition_order(str(payload.get("symbol") or ""), str(payload.get("description") or ""))


@app.post("/api/condition-orders/{order_id}/enable")
def enable_condition_order(order_id: int):
    return _set_generic_status("condition_orders", order_id, enabled=True, status="active")


@app.post("/api/condition-orders/{order_id}/disable")
def disable_condition_order(order_id: int):
    return _set_generic_status("condition_orders", order_id, enabled=False, status="disabled")


@app.get("/api/schedules")
def list_schedules():
    return service.repository.list_generic("schedules")


@app.post("/api/schedules")
def save_schedule(schedule: ScheduleSpec):
    service.validate_workflow(schedule.workflow)
    return service.repository.save_generic("schedules", schedule.model_dump(mode="json"))


@app.post("/api/schedules/{schedule_id}/run")
def run_schedule(schedule_id: int):
    return service.run_schedule(schedule_id)


@app.post("/api/schedules/{schedule_id}/enable")
def enable_schedule(schedule_id: int):
    return _set_generic_status("schedules", schedule_id, enabled=True, status="enabled")


@app.post("/api/schedules/{schedule_id}/disable")
def disable_schedule(schedule_id: int):
    return _set_generic_status("schedules", schedule_id, enabled=False, status="disabled")


@app.get("/api/schedules/{schedule_id}/runs")
def list_schedule_runs(schedule_id: int):
    return service.repository.list_schedule_runs(schedule_id)


@app.get("/api/events")
def list_events(limit: int = 100):
    return service.repository.list_events(limit)


@app.get("/api/monitor/quotes")
def fetch_quotes(symbols: str):
    return service.fetch_quotes([item.strip() for item in symbols.split(",") if item.strip()])


@app.get("/api/monitor/quotes/stream")
def quote_stream_info():
    return {"websocket": "/ws/quotes"}


@app.get("/api/kline/symbols")
def list_kline_symbols():
    return service.list_kline_symbols()


@app.get("/api/kline/{symbol}")
def get_kline(symbol: str, frequency: str = "1d", limit: int = 500):
    return service.get_kline_bars(symbol, frequency, limit)


@app.get("/api/trading/status")
def trading_status():
    return service.trading_status()


@app.get("/api/config")
def get_config():
    return service.config_view()


@app.post("/api/config/reload")
def reload_config():
    return service.reload_config()


@app.post("/api/notifications/hermes/test")
def test_hermes_notification(payload: dict):
    return service.notify_hermes(str(payload.get("message") or "trend-trader test"), dry_run=bool(payload.get("dry_run", True)))


@app.post("/api/screener/run", response_model=ScreenerResult)
def run_screener(request: ScreenerRequest) -> ScreenerResult:
    try:
        return service.run_screener(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/plans")
def list_plans(limit: int = 100):
    return service.repository.list_plans(limit)


@app.post("/api/watchlist/sync", response_model=WatchlistSyncResult)
def sync_watchlist() -> WatchlistSyncResult:
    return WatchlistSyncResult(synced=service.repository.sync_watchlist_from_plans())


@app.post("/api/watchlist/tick", response_model=list[AlertEvent])
async def ingest_tick(tick: TickInput) -> list[AlertEvent]:
    alerts = service.repository.evaluate_tick(tick.symbol, tick.price)
    service.evaluate_condition_orders(tick.symbol, tick.price)
    for alert in alerts:
        await _broadcast_alert(alert)
    return alerts


@app.get("/api/alerts", response_model=list[AlertEvent])
def list_alerts(limit: int = 100) -> list[AlertEvent]:
    return service.repository.list_alerts(limit)


@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    alert_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_clients.discard(websocket)


@app.websocket("/ws/quotes")
async def quotes_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    quote_clients.add(websocket)
    symbols: list[str] = []
    try:
        while True:
            try:
                text = await asyncio.wait_for(websocket.receive_text(), timeout=3)
                payload = json.loads(text) if text else {}
                if isinstance(payload, dict) and payload.get("symbols"):
                    raw_symbols = payload.get("symbols")
                    if isinstance(raw_symbols, str):
                        symbols = [item.strip() for item in raw_symbols.split(",") if item.strip()]
                    else:
                        symbols = [str(item) for item in raw_symbols]
            except asyncio.TimeoutError:
                if not symbols:
                    orders = service.repository.list_generic("condition_orders")
                    symbols = sorted({str(order.get("symbol")) for order in orders if order.get("enabled", True) and order.get("symbol")})
                quotes = service.fetch_quotes(symbols or ["000001", "002261"])
                for quote in quotes:
                    await websocket.send_json({"type": "quote", "data": quote})
    except WebSocketDisconnect:
        quote_clients.discard(websocket)


async def _broadcast_alert(alert: AlertEvent) -> None:
    disconnected: list[WebSocket] = []
    for client in alert_clients:
        try:
            await client.send_json(alert.model_dump(mode="json"))
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        alert_clients.discard(client)


@app.websocket("/ws/chat/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: int) -> None:
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            response = send_chat_message(session_id, ChatMessageRequest(content=text))
            await websocket.send_json(response)
    except WebSocketDisconnect:
        return


def _parse_tool_command(content: str) -> tuple[str, dict]:
    body = content[len("/tool "):].strip()
    if not body:
        raise HTTPException(status_code=400, detail="missing tool name")
    if " " not in body:
        return body, {}
    name, raw = body.split(" ", 1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid tool json: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="tool arguments must be an object")
    return name, parsed


def _set_generic_status(table: str, record_id: int, enabled: bool, status: str):
    try:
        payload = service.repository.get_generic(table, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload["enabled"] = enabled
    payload["status"] = status
    return service.repository.save_generic(table, payload)
