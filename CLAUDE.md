# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库中工作时提供指引。

## 常用命令

```bash
# 后端
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
./trend-trader tool list                 # CLI 入口（PYTHONPATH=.. python3 -m app.cli）
./trend-trader tool invoke <工具名> '<JSON参数>'
./trend-trader worker start             # APScheduler 常驻 worker
.venv/bin/python -m unittest discover -s tests   # 运行全部测试

# 前端
cd frontend
npm install
VITE_API_TARGET=http://127.0.0.1:8001 npm run dev  # 开发服务器，端口 :5173
npm run build                           # tsc -b && vite build
```

## 架构总览

Monorepo：`backend/`（Python 3.9 + FastAPI）和 `frontend/`（Vite + React 19 + TypeScript）。

### 后端分层（`backend/app/` 下）

- **`main.py`** — FastAPI 应用，所有 REST 和 WebSocket 路由直接定义在此（未拆分为 router 模块）。已启用 CORS。
- **`services.py`** — `TrendTraderService` 单例，负责把数据提供者、缓存、仓库层、策略注册表和工具注册表串联起来。初始化时写入默认数据。
- **`storage/repository.py`** — SQLite 仓库层。大多数实体表采用**通用表模式**：列为 `id, name, enabled, status, payload(JSON), created_at, updated_at`。仅 analyses、plans、watchlist、alerts 等少数表有定型 schema。
- **`tools.py`** — `ToolRegistry`：所有操作的统一入口。REST API `/api/tools/invoke`、CLI `tool invoke`、AI 聊天中的 `/tool` 指令、定时任务、MCP 全部走同一个 `ToolRegistry.invoke()`。部分工具需要显式传入 `confirm=true`。
- **`strategies/`** — 策略插件系统：`StrategyPlugin` 抽象基类 + `StrategyRegistry`。目前仅一个内置实现 `trend_trading`（裸 K 趋势：识别 pivot、高低点趋势线、关键位、突破买点、止损止盈、盈亏比和综合评分）。
- **`data/`** — 日 K 数据提供者（优先 QUANTAXIS，失败时用 sample 降级）和实时行情提供者（优先 easyquotation，失败时用 sample 降级）。缓存层以 JSON 形态存储在 `.data/bars/` 下。
- **`cli.py`** — argparse 命令分发，子命令：`chat`、`tool`、`ai`、`skill`、`agent`、`team`、`schedule`、`worker`、`mcp`。
- **`worker.py`** — APScheduler `BlockingScheduler`，使用 SQLite job store，从主仓库读取定时任务配置。

### 前端分层（`frontend/src/` 下）

- **`App.tsx`** — 单页面应用，6 个 Tab：AI、Review（含 KLinePanel）、Schedules、Pools、Conditions、Events。
- **`api.ts`** — 所有 API 调用函数，对 `fetch` 的薄封装。
- **`types.ts`** — TypeScript 类型定义，与后端 Pydantic 模型对应。
- **`KLinePanel.tsx`** — 通过 `klinecharts` 库渲染 K 线图。
- Vite 将 `/api` 和 `/ws` 代理到 `VITE_API_TARGET`（默认 `http://127.0.0.1:8001`）。

### 关键模式

- **一切皆工具**：新增后端功能时，在 `ToolRegistry._register_defaults()` 注册即可。无须额外接线，即可自动对 REST、CLI、AI 聊天、定时任务和 MCP 统一可用。
- **数据源降级**：如果本地没有 QUANTAXIS/Mongo 行情数据，系统会自动静默降级为确定性的 sample 数据——保证随时随地可运行和开发。
- **通用表 JSON payload**：model_providers、model_profiles、skills、agents、teams、strategy_specs、condition_orders、schedules 等实体表的核心字段均存放在 JSON 列中。新增字段加到 payload JSON 里，不要加新列。
- **仓库 schema 初始化**：`_init_schema()` 是所有表的唯一定义来源，新增表必须在此方法中添加。
- **前端暂无测试框架**（没有 Jest/Vitest 配置）。后端测试使用 Python `unittest`。

## 外部依赖（本项目不修改其源码）

- QUANTAXIS — 日 K 数据源
- easyquotation — 实时行情
- KLineChart — K 线图渲染（Vite 配置中使用 alias 指向）
