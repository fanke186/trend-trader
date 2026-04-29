import type {
  AgentSpec,
  AlertEvent,
  ChatMessage,
  ChatSession,
  ConditionOrder,
  DailyBar,
  EventRecord,
  ModelProfile,
  ModelProvider,
  ScheduleSpec,
  SkillSpec,
  ScreenerResult,
  StockPool,
  StockPoolItem,
  StrategySpec,
  StrategyAnalysis,
  ToolInvokeResult,
  TradingStatus,
  Quote,
  ToolDefinition
} from './types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options)
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

export async function analyze(symbol: string, strategyName: string): Promise<StrategyAnalysis> {
  return request('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, strategy_name: strategyName })
  })
}

export async function runScreener(symbols: string[], strategyName: string): Promise<ScreenerResult> {
  return request('/api/screener/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbols, strategy_name: strategyName, min_score: 0 })
  })
}

export async function syncWatchlist(): Promise<{ synced: number }> {
  return request('/api/watchlist/sync', { method: 'POST' })
}

export async function sendTick(symbol: string, price: number): Promise<AlertEvent[]> {
  return request('/api/watchlist/tick', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, price })
  })
}

export async function fetchAlerts(): Promise<AlertEvent[]> {
  return request('/api/alerts')
}

export const fetchProviders = () => request<ModelProvider[]>('/api/ai/providers')
export const fetchModelProfiles = () => request<ModelProfile[]>('/api/ai/model-profiles')
export const testModelProfile = (id: number) => request<Record<string, unknown>>(`/api/ai/model-profiles/${id}/test`, { method: 'POST' })
export const fetchSkills = () => request<SkillSpec[]>('/api/ai/skills')
export const fetchAgents = () => request<AgentSpec[]>('/api/ai/agents')
export const fetchTools = () => request<ToolDefinition[]>('/api/tools')
export const fetchChatSessions = () => request<ChatSession[]>('/api/chat/sessions')
export const createChatSession = (title: string, agentId?: number | null) => request<ChatSession>('/api/chat/sessions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title, agent_id: agentId ?? null, model_profile_id: null })
})
export const fetchChatMessages = (sessionId: number) => request<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`)
export const sendChatMessage = (sessionId: number, content: string, agentId?: number | null) => request<{ user: ChatMessage; assistant: ChatMessage }>(`/api/chat/sessions/${sessionId}/messages`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ content, agent_id: agentId ?? null })
})
export const invokeTool = (name: string, args: Record<string, unknown>, confirmed = false) => request<ToolInvokeResult>('/api/tools/invoke', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name, arguments: args, confirmed, source: 'frontend' })
})
export const fetchPools = () => request<StockPool[]>('/api/pools')
export const addPoolItem = (poolId: number, payload: Record<string, unknown>) => request<StockPoolItem>(`/api/pools/${poolId}/items`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
export const fetchConditionOrders = () => request<ConditionOrder[]>('/api/condition-orders')
export const createConditionOrder = (payload: Record<string, unknown>) => request<ConditionOrder>('/api/condition-orders', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
export const fetchSchedules = () => request<ScheduleSpec[]>('/api/schedules')
export const runSchedule = (id: number) => request<Record<string, unknown>>(`/api/schedules/${id}/run`, { method: 'POST' })
export const setScheduleEnabled = (id: number, enabled: boolean) => request<ScheduleSpec>(`/api/schedules/${id}/${enabled ? 'enable' : 'disable'}`, { method: 'POST' })
export const fetchEvents = () => request<EventRecord[]>('/api/events')
export const fetchQuotes = (symbols: string[]) => request<Quote[]>(`/api/monitor/quotes?symbols=${encodeURIComponent(symbols.join(','))}`)
export const fetchStrategies = () => request<StrategySpec[]>('/api/strategies')
export const explainStrategy = (id: number) => request<{ explanation: string; hash: string }>(`/api/strategies/${id}/explain`, { method: 'POST' })
export const generateStrategy = (name: string, description: string) => request<ToolInvokeResult>('/api/tools/invoke', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'strategy.generate', arguments: { name, description }, confirmed: true, source: 'frontend' })
}).then(result => {
  const output = (result as ToolInvokeResult).output
  return output.strategy as StrategySpec
})
export const aiCreateConditionOrder = (symbol: string, description: string) => request<ConditionOrder>('/api/condition-orders/ai-create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ symbol, description })
})
export const fetchKline = (symbol: string, frequency = '1d', limit = 500) => request<DailyBar[]>(`/api/kline/${symbol}?frequency=${encodeURIComponent(frequency)}&limit=${limit}`)
export const fetchTradingStatus = () => request<TradingStatus>('/api/trading/status')
export const fetchConfig = () => request<{ path: string; config: Record<string, unknown> }>('/api/config')
export const reloadConfig = () => request<{ path: string; config: Record<string, unknown> }>('/api/config/reload', { method: 'POST' })
