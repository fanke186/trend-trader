from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Literal, Optional

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    class _FieldInfo:
        def __init__(self, default: Any = None, default_factory: Any = None) -> None:
            self.default = default
            self.default_factory = default_factory

    def Field(default: Any = None, default_factory: Any = None) -> _FieldInfo:
        return _FieldInfo(default, default_factory)

    class BaseModel:
        def __init__(self, **kwargs: Any) -> None:
            annotations: dict[str, Any] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for name in annotations:
                if name in kwargs:
                    setattr(self, name, kwargs[name])
                    continue
                default = getattr(self.__class__, name, None)
                if isinstance(default, _FieldInfo):
                    value = default.default_factory() if default.default_factory else default.default
                else:
                    value = default
                setattr(self, name, value)

        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            annotations: dict[str, Any] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            return {name: _dump_value(getattr(self, name)) for name in annotations}

        def model_dump_json(self) -> str:
            return json.dumps(self.model_dump(), ensure_ascii=False)


def _dump_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_dump_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump_value(item) for key, item in value.items()}
    return value


StrategyStatus = Literal["no_setup", "watch", "triggered", "invalidated"]
ProviderType = Literal[
    "openai",
    "glm",
    "deepseek",
    "kimi",
    "qwen",
    "openrouter",
    "ollama",
    "litellm",
    "openai_compatible",
]
ConditionOrderType = Literal["notify", "order"]
ScheduleStatus = Literal["enabled", "disabled"]
WorkflowStepType = Literal["tool", "agent", "team", "foreach", "condition", "parallel", "notify"]


class DailyBar(BaseModel):
    symbol: str
    exchange: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


class AnalyzeRequest(BaseModel):
    symbol: str
    strategy_name: str = "trend_trading"


class ScreenerRequest(BaseModel):
    symbols: list[str]
    strategy_name: str = "trend_trading"
    min_score: float = 0


class ChartPoint(BaseModel):
    date: date
    value: float


class ChartOverlay(BaseModel):
    id: str
    kind: str
    name: str
    label: str
    points: list[ChartPoint]
    styles: dict[str, Any] = Field(default_factory=dict)


class TradePlan(BaseModel):
    symbol: str
    strategy_name: str
    status: StrategyStatus
    entry_price: Optional[float] = None
    entry_reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    invalidated_if: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StrategyAnalysis(BaseModel):
    symbol: str
    strategy_name: str
    as_of: date
    score: float
    status: StrategyStatus
    bars: list[DailyBar]
    score_breakdown: dict[str, float]
    metrics: dict[str, Any]
    overlays: list[ChartOverlay]
    trade_plan: Optional[TradePlan]


class ScreenerResult(BaseModel):
    strategy_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    results: list[StrategyAnalysis]


class WatchlistSyncResult(BaseModel):
    synced: int


class TickInput(BaseModel):
    symbol: str
    price: float
    at: datetime = Field(default_factory=datetime.utcnow)


class AlertEvent(BaseModel):
    id: int
    symbol: str
    strategy_name: str
    trigger_type: str
    price: float
    message: str
    created_at: datetime
    delivered_channels: list[str] = Field(default_factory=list)


class ModelProvider(BaseModel):
    id: Optional[int] = None
    name: str
    provider_type: ProviderType = "openai_compatible"
    base_url: str
    api_key_env: str
    enabled: bool = True
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ModelProfile(BaseModel):
    id: Optional[int] = None
    name: str
    provider_id: int
    model: str
    temperature: float = 0.2
    timeout_seconds: int = 60
    max_tokens: int = 4096
    supports_json: bool = True
    supports_stream: bool = True
    supports_tools: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ModelProfileTestResult(BaseModel):
    ok: bool
    provider: str
    model: str
    message: str
    latency_ms: Optional[float] = None


class SkillSpec(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    instructions: str
    references: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    version: int = 1
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GenerateSkillRequest(BaseModel):
    name: str
    description: str
    source_prompt: str
    tools_allowed: list[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    id: Optional[int] = None
    name: str
    role: str
    system_prompt: str
    model_profile_id: Optional[int] = None
    skill_ids: list[int] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    max_turns: int = 8
    allow_sub_agents: bool = False
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRunRequest(BaseModel):
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class AgentRunResult(BaseModel):
    id: Optional[int] = None
    agent_id: Optional[int] = None
    team_id: Optional[int] = None
    status: str
    input: dict[str, Any]
    output: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentTeamSpec(BaseModel):
    id: Optional[int] = None
    name: str
    mode: Literal["sequential", "parallel", "review", "delegate_merge"] = "sequential"
    agent_ids: list[int] = Field(default_factory=list)
    coordinator_agent_id: Optional[int] = None
    description: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    id: Optional[int] = None
    title: str
    agent_id: Optional[int] = None
    model_profile_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    id: Optional[int] = None
    session_id: int
    role: Literal["user", "assistant", "tool", "system"]
    content: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessageRequest(BaseModel):
    content: str
    agent_id: Optional[int] = None
    model_profile_id: Optional[int] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    category: str = "system"


class ToolInvokeRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    source: str = "api"


class ToolInvokeResult(BaseModel):
    tool_name: str
    status: Literal["ok", "error", "confirmation_required"]
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    requires_confirmation: bool = False
    invocation_id: Optional[int] = None


class StrategySpec(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""
    source_prompt: str = ""
    version: int = 1
    universe: dict[str, Any] = Field(default_factory=dict)
    features: list[dict[str, Any]] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    scoring: list[dict[str, Any]] = Field(default_factory=list)
    overlays: list[dict[str, Any]] = Field(default_factory=list)
    trade_plan_template: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StockPool(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StockPoolItem(BaseModel):
    id: Optional[int] = None
    pool_id: int
    symbol: str
    name: str = ""
    group_name: str = "默认"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    review_enabled: bool = True
    monitor_enabled: bool = True
    sort_order: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConditionOrder(BaseModel):
    id: Optional[int] = None
    name: str
    symbol: str
    order_type: ConditionOrderType = "notify"
    condition: dict[str, Any]
    action: dict[str, Any] = Field(default_factory=dict)
    strategy_name: str = "trend_trading"
    enabled: bool = True
    status: str = "active"
    last_triggered_at: Optional[datetime] = None
    dedupe_key: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EventRecord(BaseModel):
    id: Optional[int] = None
    category: str
    source: str
    title: str
    message: str
    status: str = "created"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowStep(BaseModel):
    type: WorkflowStepType
    name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    items: list[Any] = Field(default_factory=list)
    condition: dict[str, Any] = Field(default_factory=dict)


class WorkflowScript(BaseModel):
    version: int = 1
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)


class ScheduleTrigger(BaseModel):
    type: Literal["cron", "interval", "date"] = "cron"
    cron: str = ""
    every_seconds: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: str = "Asia/Shanghai"


class ScheduleSpec(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""
    trigger: ScheduleTrigger
    workflow: WorkflowScript
    status: ScheduleStatus = "enabled"
    next_run_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduleRun(BaseModel):
    id: Optional[int] = None
    schedule_id: int
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
