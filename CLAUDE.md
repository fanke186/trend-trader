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
npx vitest run                          # 前端组件测试
```

## 架构总览

Monorepo：`backend/`（Python 3.9 + FastAPI）和 `frontend/`（Vite + React 19 + TypeScript）。

### 后端分层（`backend/app/` 下）

- **`main.py`** — FastAPI 应用，所有 REST 和 WebSocket 路由直接定义在此。启动时通过 `on_event("startup")` 开启 QuoteManager 后台行情轮询。已启用 CORS。
- **`services.py`** — `TrendTraderService` 单例，集中串联所有后端模块：配置、K线库、策略引擎/释义器、条件求值器、行情管理、交易管理、Agent 工具循环、LLM 调用。初始化时写入默认数据（含 K 线更新定时任务种子）。
- **`config/`** — `ConfigLoader`：YAML + `TREND_TRADER_<section>_<key>` 环境变量覆盖，支持多套 AI / 行情 / 交易配置通过 `active` 字段切换。
- **`storage/repository.py`** — SQLite 仓库层。大多数实体表采用**通用表模式**：列为 `id, name, enabled, status, payload(JSON), created_at, updated_at`。analysis + plan 写入使用事务包装。MigrationRunner 在初始化时自动执行迁移。
- **`storage/migrations.py`** — 版本化数据库迁移：`schema_migrations` 表记录已应用的版本，`_init_schema()` 后自动运行。
- **`tools.py`** — `ToolRegistry`：所有操作的统一入口（17 个已注册工具）。REST API、CLI、AI 聊天、定时任务、MCP 全部走 `ToolRegistry.invoke()`。部分工具需要显式 `confirm=true`。
- **`strategies/`** — 策略系统：
  - `base.py`：`StrategyPlugin` 抽象基类 + `StrategyRegistry`
  - `trend_trading.py`：内置裸 K 趋势策略
  - `engine.py`：**通用策略执行引擎**——输入 `StrategySpec` + `list[DailyBar]`，执行 feature 计算 → filter 筛选 → scoring 加权评分 → overlay 生成 → trade_plan 生成
  - `interpreter.py`：**策略释义器**——对 StrategySpec 的 JSON 做 SHA256 哈希缓存，LLM 生成稳定自然语言释义
- **`data/`** — 数据层：
  - `providers.py`：日 K 数据提供者（QUANTAXIS 优先 → sample 降级）
  - `realtime.py`：实时行情提供者（easyquotation 优先 → sample 降级）
  - `cache.py`：BarCache（JSON 文件缓存）
  - `kline_db.py`：**DuckDB K 线数据库**——DDL（日/周/月 K + 证券信息 + 交易日历）+ Parquet 分区存储 + 聚合函数
- **`monitoring/`** — 监控模块：
  - `condition_evaluator.py`：条件表达式求值器（all/any/not/gte/lte/gt/lt/eq/crosses_above/crosses_below），修复了 crosses 语义（前值 < 阈值且当前 >= 阈值）
  - `quote_stream.py`：`QuoteManager` + mootdx/jvQuant 行情提供者，异步轮询 + `_on_quote` 回调
- **`trading/`** — 交易模块：
  - `gateway.py`：`TradingGateway` 抽象 + `DryRunGateway`
  - `miniqmt_gateway.py`：Mac → Windows MiniQMT HTTP 客户端
  - `paper_gateway.py`：内存模拟撮合交易
  - `manager.py`：`TradeManager`——按 `trading.mode` 切换 dry_run/paper/live
- **`agent/`** — `AgentToolLoop`：LLM 工具调用循环（构建 tools 定义 → 调用 LLM API → 执行 tool_calls → 追加 tool_result → 继续，最多 8 轮）
- **`cli.py`** — argparse 命令分发
- **`worker.py`** — APScheduler `BlockingScheduler`

### 前端分层（`frontend/src/` 下）

- **`App.tsx`** — React Router 7 路由入口，7 个路由：`/`(AI)、`/review`、`/review/:symbol`、`/strategy`、`/strategy/:id`、`/pool`、`/monitor`、`/schedule`、`/settings`
- **`components/`** — 共享组件：`Layout`（Topbar + Sidebar + ChatInput + ContextPanel）、`Sidebar`、`ChatInput`、`ContextPanel`、`StatusIndicator`、`PriceDisplay`、`DataTable`（可排序）、`MetricCard`（霓虹发光）
- **`pages/`** — 各页面：`AIPage`、`ReviewPage`、`StrategyPage`、`PoolPage`、`MonitorPage`、`SchedulePage`、`SettingsPage`
- **`hooks/`** — `useWebSocket`（自动重连）、`useQuotes`（实时行情订阅）、`usePolling`（通用轮询）
- **`api.ts`** — 所有 API 调用函数，`fetch` 薄封装
- **`types.ts`** — TypeScript 类型定义
- **`appState.tsx`** — React Context + useReducer 全局状态
- **`KLinePanel.tsx`** — lightweight-charts (TradingView) 渲染 K 线图，配色 `#0a0d14`/`#00d4aa`/`#ff4757`
- **`index.css`** — Tailwind CSS 4 + 自定义暗色主题（base-950/900/850/800, up/down/warn/info）
- Vite 将 `/api` 和 `/ws` 代理到 `VITE_API_TARGET`（默认 `http://127.0.0.1:8001`）

### 关键模式

- **一切皆工具**：新增后端功能时，在 `ToolRegistry._register_defaults()` 注册即可。无需额外接线，自动对 REST、CLI、AI 聊天、定时任务和 MCP 统一可用。
- **数据源降级**：K 线优先 DuckDB → QUANTAXIS → sample；行情优先 QuoteManager（mootdx/jvQuant）→ easyquotation → sample。
- **通用表 JSON payload**：实体表核心字段存 JSON 列，新增字段加 payload 不加列。
- **LLM 优先 + 规则回退**：`generate_strategy` 和 `ai_create_condition_order` 先尝试 LLM 调用，失败或未配置 API key 时回退到硬编码/正则规则。
- **行情推送模式**：`QuoteManager` 后台统一轮询 → `_handle_quote` 评估条件单 + 广播到所有 WebSocket 客户端。
- **仓库 schema 初始化**：`_init_schema()` + `MigrationRunner.run()` 是 schema 唯一定义来源。

## 外部依赖

- QUANTAXIS — 日 K 数据源（降级链第一级）
- easyquotation — 实时行情（降级链第一级）
- mootdx — 免费行情（QuoteManager 默认通道）
- DuckDB — 本地 K 线分析数据库
- lightweight-charts — K 线图渲染（替代 klinecharts）
- Tailwind CSS 4 — 前端样式框架
- React Router 7 — 前端路由
