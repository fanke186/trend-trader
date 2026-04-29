export type DailyBar = {
  symbol: string
  exchange: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  turnover: number
}

export type ChartPoint = {
  date: string
  value: number
}

export type ChartOverlay = {
  id: string
  kind: string
  name: string
  label: string
  points: ChartPoint[]
  styles: Record<string, unknown>
}

export type TradePlan = {
  symbol: string
  strategy_name: string
  status: 'no_setup' | 'watch' | 'triggered' | 'invalidated'
  entry_price: number | null
  entry_reason: string
  stop_loss: number | null
  take_profit: number | null
  risk_reward_ratio: number | null
  invalidated_if: string
  created_at: string
}

export type StrategyAnalysis = {
  symbol: string
  strategy_name: string
  as_of: string
  score: number
  status: TradePlan['status']
  bars: DailyBar[]
  score_breakdown: Record<string, number>
  metrics: Record<string, unknown>
  overlays: ChartOverlay[]
  trade_plan: TradePlan | null
}

export type AlertEvent = {
  id: number
  symbol: string
  strategy_name: string
  trigger_type: string
  price: number
  message: string
  created_at: string
  delivered_channels: string[]
}

export type ModelProvider = {
  id: number
  name: string
  provider_type: string
  base_url: string
  api_key_env: string
  enabled: boolean
  notes?: string
}

export type ModelProfile = {
  id: number
  name: string
  provider_id: number
  model: string
  temperature: number
  max_tokens: number
  supports_tools: boolean
  enabled: boolean
}

export type SkillSpec = {
  id: number
  name: string
  description: string
  instructions: string
  tools_allowed: string[]
  enabled: boolean
}

export type AgentSpec = {
  id: number
  name: string
  role: string
  system_prompt: string
  model_profile_id: number | null
  tools_allowed: string[]
  enabled: boolean
}

export type ToolDefinition = {
  name: string
  description: string
  input_schema: Record<string, unknown>
  requires_confirmation: boolean
  category: string
}

export type ChatSession = {
  id: number
  title: string
  agent_id: number | null
  model_profile_id: number | null
  updated_at: string
}

export type ChatMessage = {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  payload: Record<string, unknown>
  created_at: string
}

export type StockPoolItem = {
  id: number
  pool_id: number
  symbol: string
  name: string
  group_name: string
  tags: string[]
  notes: string
  review_enabled: boolean
  monitor_enabled: boolean
}

export type StockPool = {
  id: number
  name: string
  description: string
  enabled: boolean
  items: StockPoolItem[]
}

export type ConditionOrder = {
  id: number
  name: string
  symbol: string
  order_type: 'notify' | 'order'
  condition: Record<string, unknown>
  strategy_name: string
  enabled: boolean
  status: string
  last_triggered_at?: string | null
}

export type ScheduleSpec = {
  id: number
  name: string
  description: string
  trigger: {
    type: 'cron' | 'interval' | 'date'
    cron?: string
    every_seconds?: number | null
    run_at?: string | null
    timezone: string
  }
  workflow: Record<string, unknown>
  status: 'enabled' | 'disabled'
}

export type EventRecord = {
  id: number
  category: string
  source: string
  title: string
  message: string
  status: string
  payload: Record<string, unknown>
  created_at: string
}
