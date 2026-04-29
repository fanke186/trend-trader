# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick commands

```bash
# Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
./trend-trader tool list                 # CLI entry (PYTHONPATH=.. python3 -m app.cli)
./trend-trader tool invoke <tool> '<json>'
./trend-trader worker start             # APScheduler blocking worker
.venv/bin/python -m unittest discover -s tests   # Run all tests

# Frontend
cd frontend
npm install
VITE_API_TARGET=http://127.0.0.1:8001 npm run dev  # Dev server on :5173
npm run build                           # tsc -b && vite build
```

## Architecture

Monorepo: `backend/` (Python 3.9 + FastAPI) and `frontend/` (Vite + React 19 + TypeScript).

### Backend layers (inside `backend/app/`)

- **`main.py`** — FastAPI app with all REST + WebSocket routes defined directly (no router modules). CORS middleware enabled.
- **`services.py`** — `TrendTraderService` singleton that wires together data providers, cache, repository, strategy registry, and tool registry. Seeds default data on init.
- **`storage/repository.py`** — SQLite repository. Most entity tables use a **generic table pattern**: columns are `id, name, enabled, status, payload(JSON), created_at, updated_at`. Only analyses, plans, watchlist, alerts, and a few others have typed schemas.
- **`tools.py`** — `ToolRegistry`: the unified entry point for all operations. REST API `/api/tools/invoke`, CLI `tool invoke`, AI chat `/tool` commands, scheduled workflows, and MCP all route through the same `ToolRegistry.invoke()` call. Some tools require explicit `confirm=true`.
- **`strategies/`** — Plugin system: `StrategyPlugin` ABC + `StrategyRegistry`. Single built-in implementation: `trend_trading` (raw-K trend: pivot points, breakout signals, stop/target, risk-reward scoring).
- **`data/`** — Daily bar providers (`QUANTAXIS + sample fallback`) and real-time quote provider (`easyquotation + sample fallback`). Cache layer stores bars as JSON under `.data/bars/`.
- **`cli.py`** — argparse dispatcher with subcommands: `chat`, `tool`, `ai`, `skill`, `agent`, `team`, `schedule`, `worker`, `mcp`.
- **`worker.py`** — APScheduler `BlockingScheduler` with SQLite job store, reads schedules from the main repo.

### Frontend layers (inside `frontend/src/`)

- **`App.tsx`** — Single SPA with 6 tabs: AI, Review (+KLinePanel), Schedules, Pools, Conditions, Events.
- **`api.ts`** — All API call functions, thin wrappers around `fetch`.
- **`types.ts`** — TypeScript types mirroring backend Pydantic models.
- **`KLinePanel.tsx`** — Candlestick chart via `klinecharts` library.
- Vite proxies `/api` and `/ws` to `VITE_API_TARGET` (default `http://127.0.0.1:8001`).

### Key patterns

- **Everything is a tool**: When adding new backend functionality, register it in `ToolRegistry._register_defaults()`. This makes it available across REST, CLI, AI chat, schedules, and MCP without extra wiring.
- **Data provider fallback**: If QUANTAXIS/Mongo is unavailable, the system silently falls back to deterministic sample data — the app is always runnable for development and testing.
- **Generic table payload**: JSON columns store the meaningful fields for model_providers, model_profiles, skills, agents, teams, strategy_specs, condition_orders, and schedules. Add new fields to the `payload` JSON, not as new columns.
- **Repository schema**: `_init_schema()` is the source of truth for all tables. New tables must be added there.
- **No frontend test framework** configured (no Jest/Vitest). Backend tests use Python `unittest`.

## External dependencies (not modified by this project)

- QUANTAXIS — daily bar data source
- easyquotation — real-time quotes
- KLineChart — candlestick chart rendering (aliased in Vite config)
