from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.data.cache import BarCache
from app.data.providers import QuantAxisDailyBarProvider, normalize_symbol
from app.data.realtime import EasyQuotationQuoteProvider
from app.models import (
    AgentRunResult,
    AgentSpec,
    AgentTeamSpec,
    AnalyzeRequest,
    EventRecord,
    GenerateSkillRequest,
    ModelProfileTestResult,
    ScheduleRun,
    ScheduleSpec,
    ScreenerRequest,
    ScreenerResult,
    SkillSpec,
    StockPool,
    StockPoolItem,
    StrategyAnalysis,
    StrategySpec,
    WorkflowScript,
)
from app.storage.repository import Repository
from app.strategies import build_registry
from app.tools import ToolRegistry


class TrendTraderService:
    def __init__(self, data_dir: Path) -> None:
        load_dotenv(data_dir.parent / ".env", override=False)
        self.provider = QuantAxisDailyBarProvider()
        self.quote_provider = EasyQuotationQuoteProvider()
        self.cache = BarCache(data_dir / "bars")
        self.repository = Repository(data_dir / "trend_trader.sqlite3")
        self.registry = build_registry()
        self.tools = ToolRegistry(self)
        self._seed_defaults()

    def normalize_symbol(self, symbol: str) -> str:
        return normalize_symbol(symbol)

    def analyze(self, request: AnalyzeRequest) -> StrategyAnalysis:
        symbol = normalize_symbol(request.symbol)
        bars = self.provider.fetch_daily_bars(symbol)
        self.cache.save(symbol, bars)
        strategy = self.registry.get(request.strategy_name)
        analysis = strategy.analyze(symbol, bars)
        self.repository.save_analysis(analysis)
        return analysis

    def run_screener(self, request: ScreenerRequest) -> ScreenerResult:
        analyses = [self.analyze(AnalyzeRequest(symbol=s, strategy_name=request.strategy_name)) for s in request.symbols]
        filtered = [analysis for analysis in analyses if analysis.score >= request.min_score]
        filtered.sort(key=lambda item: item.score, reverse=True)
        return ScreenerResult(strategy_name=request.strategy_name, results=filtered)

    def fetch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        return self.quote_provider.fetch_quotes(symbols)

    def _seed_defaults(self) -> None:
        providers = [
            ("OpenAI", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY", "OpenAI native API"),
            ("GLM 智谱", "glm", "https://open.bigmodel.cn/api/paas/v4", "ZAI_API_KEY", "智谱 GLM OpenAI-compatible API"),
            ("DeepSeek", "deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY", "DeepSeek OpenAI-compatible API"),
            ("Kimi", "kimi", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY", "Moonshot/Kimi OpenAI-compatible API"),
            ("Qwen", "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY", "Alibaba Qwen compatible API"),
            ("OpenRouter", "openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OpenRouter multi-model gateway"),
            ("Ollama", "ollama", "http://localhost:11434/v1", "OLLAMA_API_KEY", "Local Ollama OpenAI-compatible endpoint"),
            ("LiteLLM", "litellm", "http://localhost:4000/v1", "LITELLM_API_KEY", "Local LiteLLM proxy"),
        ]
        provider_ids: dict[str, int] = {}
        for name, provider_type, base_url, api_key_env, notes in providers:
            saved = self.repository.save_generic(
                "model_providers",
                {
                    "name": name,
                    "provider_type": provider_type,
                    "base_url": base_url,
                    "api_key_env": api_key_env,
                    "enabled": True,
                    "notes": notes,
                },
            )
            provider_ids[name] = int(saved["id"])

        default_profiles = [
            ("GLM Agent", "GLM 智谱", "glm-5.1"),
            ("OpenAI Structured", "OpenAI", "gpt-5"),
            ("DeepSeek V4 Pro", "DeepSeek", "deepseek-v4-pro"),
            ("Kimi Review", "Kimi", "kimi-latest"),
            ("Qwen Local CN", "Qwen", "qwen-plus"),
        ]
        for profile_name, provider_name, model in default_profiles:
            extra = {"thinking": {"type": "enabled"}, "reasoning_effort": "high"} if profile_name == "DeepSeek V4 Pro" else {}
            self.repository.save_generic(
                "model_profiles",
                {
                    "name": profile_name,
                    "provider_id": provider_ids[provider_name],
                    "model": model,
                    "temperature": 0.2,
                    "timeout_seconds": 60,
                    "max_tokens": 4096,
                    "supports_json": True,
                    "supports_stream": True,
                    "supports_tools": True,
                    "extra": extra,
                    "enabled": True,
                },
            )

        self.repository.save_generic(
            "skills",
            SkillSpec(
                name="trend-trading-review",
                description="A-share naked K trend review workflow and vocabulary.",
                instructions=(
                    "Use daily bars, volume, amount, pivots, trend lines, key levels, breakout price, "
                    "stop loss, take profit, and risk/reward. Do not invent indicators that are not in the analysis payload."
                ),
                tools_allowed=["strategy.analyze", "strategy.screener_run", "pool.review"],
            ).model_dump(mode="json"),
        )

        profiles = self.repository.list_generic("model_profiles")
        deepseek_profile = next((profile for profile in profiles if profile.get("name") == "DeepSeek V4 Pro"), None)
        model_profile_id = int((deepseek_profile or profiles[0])["id"]) if profiles else None
        self.repository.save_generic(
            "agents",
            AgentSpec(
                name="MarketReviewAgent",
                role="盘后复盘分析员",
                system_prompt=(
                    "你负责解释 A 股趋势交易复盘结果。必须基于工具返回的结构化数据输出，"
                    "明确趋势、关键位、计划、风险，不做确定收益承诺。"
                ),
                model_profile_id=model_profile_id,
                skill_ids=[],
                tools_allowed=["strategy.analyze", "strategy.screener_run", "pool.review", "event.list"],
            ).model_dump(mode="json"),
        )

        agents = self.repository.list_generic("agents")
        agent_id = int(agents[0]["id"]) if agents else None
        if agent_id:
            self.repository.save_generic(
                "agent_teams",
                AgentTeamSpec(
                    name="DailyReviewTeam",
                    mode="sequential",
                    agent_ids=[agent_id],
                    coordinator_agent_id=agent_id,
                    description="Run daily review and produce a concise report.",
                ).model_dump(mode="json"),
            )

        pools = self.repository.list_pools()
        if not pools:
            pool = self.repository.save_pool(StockPool(name="默认自选", description="A股趋势交易默认股票池"))
            for order, symbol in enumerate(["000001", "002261", "600519", "300750", "601318"]):
                self.repository.save_pool_item(
                    StockPoolItem(pool_id=int(pool["id"]), symbol=symbol, group_name="默认", sort_order=order)
                )

        self.repository.save_generic(
            "strategy_specs",
            StrategySpec(
                name="trend_trading",
                description="内置裸 K 趋势交易策略，识别 pivot、趋势线、关键位、突破、止损止盈和盈亏比。",
                source_prompt="built-in deterministic evaluator",
                features=[
                    {"name": "pivot_high_low", "source": "daily_bars"},
                    {"name": "support_resistance_lines", "source": "pivots"},
                    {"name": "volume_ratio_20d", "source": "daily_bars"},
                ],
                scoring=[
                    {"name": "structure", "weight": 25},
                    {"name": "breakout", "weight": 30},
                    {"name": "volume", "weight": 20},
                    {"name": "risk_reward", "weight": 25},
                ],
                explanation=(
                    "该策略只使用日 K、成交量和成交额。它寻找近期 pivot 高低点，拟合支撑/压力线，"
                    "在放量突破压力线附近给出观察或触发状态，并计算止损、止盈和盈亏比。"
                ),
            ).model_dump(mode="json"),
        )

        self._seed_default_schedules()

    def _seed_default_schedules(self) -> None:
        defaults: list[dict[str, Any]] = [
            {
                "name": "收盘后股票池复盘",
                "description": "15:15 对默认股票池重新执行趋势策略评分。",
                "trigger": {"type": "cron", "cron": "15 15 * * 1-5", "timezone": "Asia/Shanghai"},
                "workflow": {
                    "version": 1,
                    "description": "Review default pool after market close.",
                    "steps": [{"type": "tool", "name": "pool.review", "arguments": {"pool_name": "默认自选", "strategy_name": "trend_trading"}}],
                },
                "status": "enabled",
            },
            {
                "name": "开盘前系统检查",
                "description": "09:15 查看近期事件和监控计划状态。",
                "trigger": {"type": "cron", "cron": "15 9 * * 1-5", "timezone": "Asia/Shanghai"},
                "workflow": {
                    "version": 1,
                    "description": "Pre-market status check.",
                    "steps": [{"type": "tool", "name": "event.list", "arguments": {"limit": 20}}],
                },
                "status": "disabled",
            },
            {
                "name": "盘中监控准备",
                "description": "09:25 将复盘计划同步到盘中监控列表。",
                "trigger": {"type": "cron", "cron": "25 9 * * 1-5", "timezone": "Asia/Shanghai"},
                "workflow": {
                    "version": 1,
                    "description": "Prepare intraday monitor.",
                    "steps": [{"type": "tool", "name": "monitor.sync_watchlist", "arguments": {}}],
                },
                "status": "disabled",
            },
        ]
        for item in defaults:
            try:
                schedule = ScheduleSpec(**item)
                self.validate_workflow(schedule.workflow)
                self.repository.save_generic("schedules", schedule.model_dump(mode="json"))
            except Exception:
                continue

    def test_model_profile(self, profile_id: int) -> ModelProfileTestResult:
        profile = self.repository.get_generic("model_profiles", profile_id)
        provider = self.repository.get_generic("model_providers", int(profile["provider_id"]))
        api_key_env = provider.get("api_key_env") or ""
        api_key = os.getenv(api_key_env, "")
        if not api_key and provider.get("provider_type") != "ollama":
            return ModelProfileTestResult(
                ok=False,
                provider=provider["name"],
                model=profile["model"],
                message=f"missing environment variable {api_key_env}",
            )

        started = time.time()
        try:
            response = self._call_openai_compatible(
                provider=provider,
                profile=profile,
                messages=[
                    {"role": "system", "content": "Reply with a short JSON object."},
                    {"role": "user", "content": '{"ping": true}'},
                ],
                max_tokens=128,
            )
            return ModelProfileTestResult(
                ok=True,
                provider=provider["name"],
                model=profile["model"],
                message=response[:160],
                latency_ms=round((time.time() - started) * 1000, 2),
            )
        except Exception as exc:
            return ModelProfileTestResult(
                ok=False,
                provider=provider["name"],
                model=profile["model"],
                message=str(exc),
                latency_ms=round((time.time() - started) * 1000, 2),
            )

    def _call_openai_compatible(
        self,
        provider: dict[str, Any],
        profile: dict[str, Any],
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> str:
        base_url = str(provider.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ValueError("provider base_url is empty")
        api_key = os.getenv(str(provider.get("api_key_env") or ""), "")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": profile["model"],
            "messages": messages,
            "temperature": float(profile.get("temperature") or 0.2),
            "max_tokens": int(max_tokens or profile.get("max_tokens") or 4096),
        }
        payload.update(dict(profile.get("extra") or {}))
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key or 'ollama'}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(profile.get("timeout_seconds") or 60)) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"{exc.code}: {detail[:400]}") from exc
        choices = body.get("choices") or []
        if not choices:
            return json.dumps(body, ensure_ascii=False)[:2000]
        message = choices[0].get("message") or {}
        content = message.get("content") or message.get("reasoning_content")
        if content:
            return str(content)
        return json.dumps(message or body, ensure_ascii=False)[:2000]

    def generate_skill(self, request: GenerateSkillRequest) -> SkillSpec:
        instructions = (
            f"Purpose: {request.description}\n\n"
            f"Source prompt:\n{request.source_prompt.strip()}\n\n"
            "When triggered, stay inside the allowed tools and return structured artifacts when the task changes strategy, "
            "condition orders, schedules, or stock pools."
        )
        return SkillSpec(
            name=request.name,
            description=request.description,
            instructions=instructions,
            tools_allowed=request.tools_allowed,
        )

    def run_agent(self, agent_id: int, prompt: str, context: dict[str, Any] | None = None) -> AgentRunResult:
        context = context or {}
        agent = self.repository.get_generic("agents", agent_id)
        profile = None
        provider = None
        if agent.get("model_profile_id"):
            profile = self.repository.get_generic("model_profiles", int(agent["model_profile_id"]))
            provider = self.repository.get_generic("model_providers", int(profile["provider_id"]))

        output: dict[str, Any]
        status = "ok"
        try:
            if provider and profile and (os.getenv(str(provider.get("api_key_env") or "")) or provider.get("provider_type") == "ollama"):
                text = self._call_openai_compatible(
                    provider=provider,
                    profile=profile,
                    messages=[
                        {"role": "system", "content": str(agent.get("system_prompt") or "")},
                        {"role": "user", "content": prompt},
                    ],
                )
                output = {"text": text, "mode": "model", "model": profile.get("model"), "provider": provider.get("name")}
            else:
                output = {
                    "text": self._local_agent_response(agent, prompt, context),
                    "mode": "local",
                    "reason": "no usable model API key configured",
                }
        except Exception as exc:
            status = "error"
            output = {"error": str(exc), "text": self._local_agent_response(agent, prompt, context), "mode": "fallback"}

        run_id = self.repository.save_ai_run(agent_id, None, status, {"prompt": prompt, "context": context}, output)
        return AgentRunResult(id=run_id, agent_id=agent_id, status=status, input={"prompt": prompt, "context": context}, output=output)

    def run_team(self, team_id: int, prompt: str, context: dict[str, Any] | None = None) -> AgentRunResult:
        context = context or {}
        team = self.repository.get_generic("agent_teams", team_id)
        outputs = []
        status = "ok"
        for agent_id in team.get("agent_ids", []):
            result = self.run_agent(int(agent_id), prompt, {**context, "team": team.get("name")})
            outputs.append(result.model_dump(mode="json"))
            if result.status != "ok":
                status = "partial"
        output = {"team": team.get("name"), "mode": team.get("mode"), "agent_outputs": outputs}
        run_id = self.repository.save_ai_run(None, team_id, status, {"prompt": prompt, "context": context}, output)
        return AgentRunResult(id=run_id, team_id=team_id, status=status, input={"prompt": prompt, "context": context}, output=output)

    def _local_agent_response(self, agent: dict[str, Any], prompt: str, context: dict[str, Any]) -> str:
        tool_names = ", ".join(agent.get("tools_allowed") or [])
        return (
            f"{agent.get('name')} 已收到任务。当前未配置可用 API Key，因此返回本地确定性响应。\n"
            f"角色：{agent.get('role')}\n"
            f"可用工具：{tool_names or '无'}\n"
            f"任务摘要：{prompt[:500]}\n"
            "需要执行系统动作时，请使用 /tool 工具名 JSON 参数，或通过前端工具面板调用。"
        )

    def validate_condition(self, condition: dict[str, Any]) -> None:
        allowed = {"all", "any", "not", "gte", "lte", "gt", "lt", "eq", "crosses_above", "crosses_below"}
        op = condition.get("op")
        if op not in allowed:
            raise ValueError(f"unsupported condition operator: {op}")
        if op in {"all", "any"}:
            children = condition.get("conditions") or []
            if not isinstance(children, list) or not children:
                raise ValueError(f"{op} requires a non-empty conditions list")
            for child in children:
                self.validate_condition(child)
        if op == "not":
            self.validate_condition(dict(condition.get("condition") or {}))
        if op in {"gte", "lte", "gt", "lt", "eq", "crosses_above", "crosses_below"}:
            if "left" not in condition or "right" not in condition:
                raise ValueError(f"{op} requires left and right")

    def evaluate_condition_orders(self, symbol: str, price: float) -> list[dict[str, Any]]:
        symbol = normalize_symbol(symbol)
        events: list[dict[str, Any]] = []
        for payload in self.repository.list_generic("condition_orders"):
            if not payload.get("enabled", True) or normalize_symbol(str(payload.get("symbol", ""))) != symbol:
                continue
            condition = dict(payload.get("condition") or {})
            try:
                fired = self._eval_condition(condition, {"last_price": price, "price": price})
            except Exception as exc:
                self.repository.save_event(
                    EventRecord(
                        category="condition_order",
                        source=f"condition_order:{payload.get('id')}",
                        title=f"Condition evaluation failed: {payload.get('name')}",
                        message=str(exc),
                        status="error",
                        payload={"condition_order": payload, "price": price},
                    )
                )
                continue
            if not fired:
                continue
            today = datetime.utcnow().date().isoformat()
            if str(payload.get("last_triggered_at") or "").startswith(today):
                continue
            payload["last_triggered_at"] = datetime.utcnow().isoformat()
            payload["status"] = "triggered"
            self.repository.save_generic("condition_orders", payload)
            event = self.repository.save_event(
                EventRecord(
                    category="condition_order",
                    source=f"condition_order:{payload.get('id')}",
                    title=f"条件单触发：{payload.get('name')}",
                    message=f"{symbol} price {price:.3f} matched condition order {payload.get('name')}",
                    status="triggered",
                    payload={"condition_order": payload, "price": price},
                )
            )
            events.append(event)
        return events

    def _eval_condition(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        op = condition.get("op")
        if op == "all":
            return all(self._eval_condition(dict(item), context) for item in condition.get("conditions", []))
        if op == "any":
            return any(self._eval_condition(dict(item), context) for item in condition.get("conditions", []))
        if op == "not":
            return not self._eval_condition(dict(condition.get("condition") or {}), context)
        left = self._operand(condition.get("left"), context)
        right = self._operand(condition.get("right"), context)
        if op in {"gte", "crosses_above"}:
            return left >= right
        if op in {"lte", "crosses_below"}:
            return left <= right
        if op == "gt":
            return left > right
        if op == "lt":
            return left < right
        if op == "eq":
            return left == right
        raise ValueError(f"unsupported condition operator: {op}")

    def _operand(self, value: Any, context: dict[str, Any]) -> float:
        if isinstance(value, dict) and "var" in value:
            return float(context.get(str(value["var"]), 0) or 0)
        return float(value or 0)

    def validate_workflow(self, workflow: WorkflowScript | dict[str, Any]) -> WorkflowScript:
        workflow_obj = workflow if isinstance(workflow, WorkflowScript) else WorkflowScript(**workflow)
        workflow_data = workflow_obj.model_dump(mode="json") if hasattr(workflow_obj, "model_dump") else dict(workflow)
        allowed_step_types = {"tool", "agent", "team", "foreach", "condition", "parallel", "notify"}
        tool_names = {tool.name for tool in self.tools.list_definitions()}
        for step in workflow_data.get("steps", []):
            step_type = step.get("type") if isinstance(step, dict) else step.type
            step_name = step.get("name", "") if isinstance(step, dict) else step.name
            if step_type not in allowed_step_types:
                raise ValueError(f"unsupported workflow step type: {step_type}")
            if step_type == "tool" and step_name not in tool_names:
                raise ValueError(f"unknown workflow tool: {step_name}")
        return workflow_obj

    def run_workflow(self, workflow: WorkflowScript | dict[str, Any], source: str = "workflow") -> dict[str, Any]:
        workflow_obj = self.validate_workflow(workflow)
        workflow_data = workflow_obj.model_dump(mode="json") if hasattr(workflow_obj, "model_dump") else dict(workflow)
        results: list[dict[str, Any]] = []
        for raw_step in workflow_data.get("steps", []):
            step = raw_step if isinstance(raw_step, dict) else raw_step.model_dump(mode="json")
            step_type = step.get("type")
            step_name = str(step.get("name") or "")
            step_arguments = dict(step.get("arguments") or {})
            if step_type == "tool":
                result = self.tools.invoke(step_name, step_arguments, source=source, confirmed=True)
                results.append(result.model_dump(mode="json"))
            elif step_type == "agent":
                result = self.run_agent(int(step_arguments.get("agent_id")), str(step_arguments.get("prompt") or ""), step_arguments)
                results.append(result.model_dump(mode="json"))
            elif step_type == "team":
                result = self.run_team(int(step_arguments.get("team_id")), str(step_arguments.get("prompt") or ""), step_arguments)
                results.append(result.model_dump(mode="json"))
            elif step_type == "notify":
                message = str(step_arguments.get("message") or "trend-trader workflow notification")
                result = self.notify_hermes(message, dry_run=bool(step_arguments.get("dry_run", True)))
                results.append({"type": "notify", "output": result})
            elif step_type == "parallel":
                nested = {"version": workflow_data.get("version", 1), "steps": step.get("steps", [])}
                results.append({"type": "parallel", "output": self.run_workflow(nested, source=source)})
            elif step_type == "foreach":
                item_results = []
                for item in step.get("items", []):
                    arguments = dict(step_arguments)
                    arguments["item"] = item
                    if step_name:
                        item_results.append(self.tools.invoke(step_name, arguments, source=source, confirmed=True).model_dump(mode="json"))
                results.append({"type": "foreach", "output": item_results})
            elif step_type == "condition":
                results.append({"type": "condition", "output": {"skipped": True, "reason": "condition steps are reserved in v1"}})
        return {"workflow": workflow_data, "steps": results}

    def run_schedule(self, schedule_id: int) -> dict[str, Any]:
        schedule_payload = self.repository.get_generic("schedules", schedule_id)
        schedule = ScheduleSpec(**schedule_payload)
        started = datetime.utcnow()
        try:
            output = self.run_workflow(schedule.workflow, source=f"schedule:{schedule_id}")
            run = ScheduleRun(
                schedule_id=schedule_id,
                status="ok",
                output=output,
                started_at=started,
                finished_at=datetime.utcnow(),
            )
            saved = self.repository.save_schedule_run(run)
            self.repository.save_event(
                EventRecord(
                    category="schedule",
                    source=f"schedule:{schedule_id}",
                    title=f"Schedule run: {schedule.name}",
                    message="schedule completed",
                    status="ok",
                    payload=saved,
                )
            )
            return saved
        except Exception as exc:
            run = ScheduleRun(
                schedule_id=schedule_id,
                status="error",
                output={},
                error=str(exc),
                started_at=started,
                finished_at=datetime.utcnow(),
            )
            saved = self.repository.save_schedule_run(run)
            self.repository.save_event(
                EventRecord(
                    category="schedule",
                    source=f"schedule:{schedule_id}",
                    title=f"Schedule run failed: {schedule.name}",
                    message=str(exc),
                    status="error",
                    payload=saved,
                )
            )
            return saved

    def notify_hermes(self, message: str, dry_run: bool = True) -> dict[str, Any]:
        hermes = "/Users/yaya/.local/bin/hermes"
        prompt = f"请通过已绑定的飞书渠道发送以下 trend-trader 通知：\n\n{message}"
        if dry_run or not Path(hermes).exists() or os.getenv("TREND_TRADER_HERMES_SEND") != "1":
            return {
                "status": "dry_run",
                "message": message,
                "hermes": hermes,
                "hint": "set TREND_TRADER_HERMES_SEND=1 and pass dry_run=false to execute",
            }
        completed = subprocess.run(
            [hermes, "-z", prompt, "--source", "trend-trader"],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        return {
            "status": "sent" if completed.returncode == 0 else "error",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
