# trend-trader

A 股趋势交易系统本地版：每日复盘、趋势选股、盘中监控、AI 工作台、定时任务和事件通知。

## 当前功能

- `backend/`：FastAPI 后端，包含策略插件、日 K 数据适配、SQLite 持久化、股票池、条件单、事件中心、统一工具层和告警 WebSocket。
- `frontend/`：Vite + React + KLineChart 前端，默认打开 AI 工作台，同时提供复盘、定时任务、股票池、条件单和事件页面。
- 内置策略 `trend_trading`：裸 K 趋势策略，识别 pivot、高低点趋势线、关键位、突破买点、止损、止盈、盈亏比和综合评分。
- AI 控制面：模型渠道、模型配置、Skill、Agent、Agent Team、聊天会话、工具调用审计。
- 统一 `ToolRegistry`：前端、CLI、AI 对话、定时任务、MCP、Hermes/OpenClaw 外部调用都走同一套工具。
- 定时任务：持久化 `WorkflowScript`，用 APScheduler worker 执行收盘复盘、开盘检查、监控准备等重复任务。
- 盘中能力：`easyquotation` 行情适配、条件单 AST 校验、事件中心、Hermes 飞书通知 dry-run/真实发送适配。

项目不直接修改 `QUANTAXIS`、`vnpy`、`KLineChart` 源码，只把它们作为外部依赖或适配对象。

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

## 主要 API

- `POST /api/analyze`：单票策略分析。
- `POST /api/screener/run`：批量复盘选股。
- `GET/POST /api/ai/providers`：模型渠道管理。
- `GET/POST /api/ai/model-profiles`：模型配置管理。
- `POST /api/ai/model-profiles/{id}/test`：测试模型配置。
- `GET/POST /api/ai/skills`：Skill 管理。
- `POST /api/ai/skills/generate`：AI 生成 Skill 草案。
- `GET/POST /api/ai/agents`：Agent 管理。
- `GET/POST /api/ai/teams`：Agent Team 管理。
- `POST /api/ai/agents/{id}/run`：运行单个 Agent。
- `POST /api/ai/teams/{id}/run`：运行 Agent Team。
- `GET/POST /api/chat/sessions`：AI 聊天会话。
- `POST /api/chat/sessions/{id}/messages`：发送聊天消息，可用 `/tool 工具名 JSON参数` 调用系统工具。
- `GET /api/tools`：查看可用工具。
- `POST /api/tools/invoke`：调用统一工具。
- `GET/POST /api/schedules`：定时任务管理。
- `POST /api/schedules/{id}/run`：立即执行定时任务。
- `GET /api/schedules/{id}/runs`：查看任务运行记录。
- `GET/POST /api/pools`：股票池管理。
- `GET/POST /api/condition-orders`：条件单管理。
- `GET /api/events`：事件中心。
- `GET /api/monitor/quotes`：获取实时行情，优先 easyquotation，失败时 sample fallback。
- `GET /api/plans`：查看复盘生成的交易计划。
- `POST /api/watchlist/sync`：同步交易计划到盘中监控。
- `POST /api/watchlist/tick`：模拟或接入最新价格并触发提醒。
- `GET /api/alerts`：查看提醒记录。
- `WS /ws/alerts`：实时提醒流。
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
