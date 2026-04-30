# trend-trader

A 股趋势交易系统本地版：每日复盘、趋势选股、盘中监控、AI 工作台、定时任务和事件通知。

## 当前功能

- `backend/`：FastAPI 后端，包含通用策略执行引擎、策略释义器、DuckDB K 线数据库、行情管理器、条件求值器、交易网关、Agent 工具循环、配置管理等。
- `frontend/`：Vite + React 19 + Tailwind CSS 4 前端，Chat-First 布局（左侧导航 + 底部全局 ChatInput + 右侧上下文面板），React Router 7 多页面路由，lightweight-charts (TradingView) K 线渲染。
- 通用策略引擎：输入 `StrategySpec` + K 线 → 自动计算 features → 应用 filters → 加权 scoring → 生成 overlays + trade_plan。
- 策略释义器：对 StrategySpec 做 SHA256 哈希缓存，LLM 生成稳定自然语言释义，多次调用输出一致。
- DuckDB K 线数据库：日/周/月 K，Parquet 按年分区存储，支持 QUANTAXIS → mootdx → sample 多级数据源降级。
- 行情监控：mootdx（免费）/ jvQuant（付费）行情通道，异步轮询 + 条件单自动求值 + WebSocket 实时推送。
- 条件单系统：all/any/not + gte/lte/gt/lt/eq/crosses_above/crosses_below 算子，支持通知/下单两种模式，触发后 Hermes 飞书通知。
- 交易模块：TradingGateway 抽象层，支持 dry_run / paper（模拟撮合）/ live（MiniQMT Windows 网关）三种模式。
- Agent 工具循环：LLM 工具调用闭环（最多 8 轮），自动调用 `ToolRegistry` 工具并返回结果。
- 统一 `ToolRegistry`（17 个工具）：前端、CLI、AI 对话、定时任务、MCP 全部走同一套工具。
- 定时任务：持久化 `WorkflowScript`，APScheduler worker 执行，内置 K 线数据自动更新 schedule。
- Docker 支持：`docker-compose.yml` 一键启动 backend + worker + frontend。
- 配置管理：YAML + 环境变量覆盖，支持多套 AI / 行情 / 交易配置通过 `active` 字段切换。

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

如果本地没有 QUANTAXIS/Mongo 行情数据，后端会自动使用确定性的 sample 日 K，保证系统仍可开发和测试。

## 启动前端

```bash
cd frontend
npm install
VITE_API_TARGET=http://127.0.0.1:8001 npm run dev
```

打开：

```text
http://localhost:5173
```

首页默认是 AI 工作台。

## CLI

```bash
cd backend
./trend-trader tool list
./trend-trader tool invoke strategy.analyze '{"symbol":"002261","strategy_name":"trend_trading"}'
./trend-trader ai provider list
./trend-trader ai model list
./trend-trader skill list
./trend-trader agent list
./trend-trader schedule list
./trend-trader schedule run 1
```

CLI 和 REST API、前端 AI 对话页共用同一个 `ToolRegistry`。Hermes/OpenClaw 等外部 agent 建议优先调用：

- `POST /api/tools/invoke`
- `./trend-trader tool invoke ...`
- `./trend-trader mcp serve`

## 定时任务 Worker

```bash
cd backend
./trend-trader worker start
```

定时任务存储在 SQLite。worker 使用 APScheduler 和本地 SQLite job store。macOS 本地部署时可以先用终端或 tmux 常驻，后续再补 launchd plist。

## AI 配置

默认模型渠道包括：

- OpenAI
- GLM/智谱
- DeepSeek
- Kimi
- Qwen
- OpenRouter
- Ollama
- LiteLLM

DeepSeek 默认 profile 已按官方 OpenAI-compatible 方式配置：

- `base_url`: `https://api.deepseek.com`
- `model`: `deepseek-v4-pro`
- `thinking`: `{"type": "enabled"}`
- `reasoning_effort`: `high`

API key 不写入 SQLite。可以通过环境变量或本地忽略的 `backend/.env` 设置：

```bash
export OPENAI_API_KEY=...
export DEEPSEEK_API_KEY=...
export ZAI_API_KEY=...
```

Hermes 飞书通知默认 dry-run。如需真实发送：

```bash
export TREND_TRADER_HERMES_SEND=1
```

## Docker

```bash
# 一键启动 (backend + worker + frontend)
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

本地开发仍推荐直接运行（见下方启动后端/前端章节）。

## 主要 API

- `POST /api/analyze`：单票策略分析。
- `POST /api/screener/run`：批量复盘选股。
- `GET/POST /api/strategies`：策略列表/保存。
- `POST /api/strategies/draft`：AI 生成策略草案。
- `POST /api/strategies/{id}/explain`：策略自然语言释义（哈希缓存稳定输出）。
- `POST /api/strategies/{id}/backtest`：运行策略回测。
- `GET /api/strategies/{id}/backtests`：回测记录列表。
- `GET /api/kline/{symbol}`：从 DuckDB 获取 K 线（支持 frequency=1d/1w/1M）。
- `GET /api/kline/symbols`：证券列表。
- `GET /api/trading/status`：交易状态（资产/持仓/委托）。
- `GET /api/config`：查看当前配置（脱敏）。
- `POST /api/config/reload`：重新加载配置。
- `GET/POST /api/ai/providers`：模型渠道管理。
- `GET/POST /api/ai/model-profiles`：模型配置管理。
- `POST /api/ai/model-profiles/{id}/test`：测试模型配置。
- `GET/POST /api/ai/skills`：Skill 管理。
- `POST /api/ai/skills/generate`：AI 生成 Skill 草案。
- `GET/POST /api/ai/agents`：Agent 管理。
- `GET/POST /api/ai/teams`：Agent Team 管理。
- `POST /api/ai/agents/{id}/run`：运行单个 Agent（使用 ToolLoop）。
- `POST /api/ai/teams/{id}/run`：运行 Agent Team。
- `GET/POST /api/chat/sessions`：AI 聊天会话。
- `POST /api/chat/sessions/{id}/messages`：发送聊天消息。
- `GET /api/tools`：查看可用工具。
- `POST /api/tools/invoke`：调用统一工具。
- `GET/POST /api/schedules`：定时任务管理。
- `POST /api/schedules/{id}/run`：立即执行定时任务。
- `GET /api/schedules/{id}/runs`：查看任务运行记录。
- `GET/POST /api/pools`：股票池管理。
- `GET/POST /api/condition-orders`：条件单管理。
- `POST /api/condition-orders/ai-create`：AI 自然语言创建条件单。
- `GET /api/events`：事件中心。
- `GET /api/monitor/quotes`：获取实时行情（REST）。
- `GET /api/monitor/quotes/stream`：行情 WebSocket 信息。
- `GET /api/plans`：查看复盘生成的交易计划。
- `POST /api/watchlist/sync`：同步交易计划到盘中监控。
- `POST /api/watchlist/tick`：推送价格并触发条件单求值。
- `GET /api/alerts`：查看提醒记录。
- `WS /ws/alerts`：实时提醒流。
- `WS /ws/quotes`：实时行情推送（QuoteManager 统一推送）。
- `WS /ws/chat/{session_id}`：聊天 WebSocket。

## 测试

```bash
cd backend
.venv/bin/python -m unittest discover -s tests
```

前端构建：

```bash
cd frontend
npm run build
```
