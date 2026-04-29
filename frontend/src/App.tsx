import { useEffect, useMemo, useState } from 'react'
import {
  addPoolItem,
  analyze,
  createChatSession,
  createConditionOrder,
  fetchAgents,
  fetchAlerts,
  fetchChatMessages,
  fetchChatSessions,
  fetchConditionOrders,
  fetchEvents,
  fetchModelProfiles,
  fetchPools,
  fetchProviders,
  fetchSchedules,
  fetchSkills,
  fetchTools,
  invokeTool,
  runSchedule,
  runScreener,
  sendChatMessage,
  sendTick,
  setScheduleEnabled,
  syncWatchlist,
  testModelProfile
} from './api'
import { KLinePanel } from './KLinePanel'
import type {
  AgentSpec,
  AlertEvent,
  ChatMessage,
  ChatSession,
  ConditionOrder,
  EventRecord,
  ModelProfile,
  ModelProvider,
  ScheduleSpec,
  SkillSpec,
  StockPool,
  StrategyAnalysis,
  ToolDefinition
} from './types'
import './style.css'

const DEFAULT_SYMBOLS = '000001,002261,600519,300750,601318'
type Tab = 'review' | 'ai' | 'schedules' | 'pools' | 'conditions' | 'events'

export default function App() {
  const [tab, setTab] = useState<Tab>('ai')
  const [symbol, setSymbol] = useState('002261')
  const [strategyName, setStrategyName] = useState('trend_trading')
  const [analysis, setAnalysis] = useState<StrategyAnalysis | null>(null)
  const [screenerSymbols, setScreenerSymbols] = useState(DEFAULT_SYMBOLS)
  const [screenerResults, setScreenerResults] = useState<StrategyAnalysis[]>([])
  const [alerts, setAlerts] = useState<AlertEvent[]>([])
  const [tickPrice, setTickPrice] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const [providers, setProviders] = useState<ModelProvider[]>([])
  const [profiles, setProfiles] = useState<ModelProfile[]>([])
  const [skills, setSkills] = useState<SkillSpec[]>([])
  const [agents, setAgents] = useState<AgentSpec[]>([])
  const [tools, setTools] = useState<ToolDefinition[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('/tool strategy.analyze {"symbol":"002261","strategy_name":"trend_trading"}')
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null)

  const [pools, setPools] = useState<StockPool[]>([])
  const [poolSymbol, setPoolSymbol] = useState('002261')
  const [poolGroup, setPoolGroup] = useState('默认')
  const [orders, setOrders] = useState<ConditionOrder[]>([])
  const [conditionSymbol, setConditionSymbol] = useState('002261')
  const [conditionPrice, setConditionPrice] = useState('10')
  const [schedules, setSchedules] = useState<ScheduleSpec[]>([])
  const [events, setEvents] = useState<EventRecord[]>([])

  const plan = analysis?.trade_plan
  const scoreColor = useMemo(() => {
    if (!analysis) return '#667085'
    if (analysis.score >= 70) return '#047857'
    if (analysis.score >= 50) return '#b7791f'
    return '#c2410c'
  }, [analysis])

  async function refreshAll() {
    await Promise.all([
      fetchAIMeta(),
      refreshPools(),
      refreshOrders(),
      refreshSchedules(),
      refreshEvents(),
      fetchAlerts().then(setAlerts).catch(() => undefined)
    ])
  }

  async function fetchAIMeta() {
    const [providerRows, profileRows, skillRows, agentRows, toolRows, sessionRows] = await Promise.all([
      fetchProviders(),
      fetchModelProfiles(),
      fetchSkills(),
      fetchAgents(),
      fetchTools(),
      fetchChatSessions()
    ])
    setProviders(providerRows)
    setProfiles(profileRows)
    setSkills(skillRows)
    setAgents(agentRows)
    setTools(toolRows)
    setSessions(sessionRows)
    if (!selectedAgentId && agentRows[0]) setSelectedAgentId(agentRows[0].id)
    if (!sessionId && sessionRows[0]) {
      setSessionId(sessionRows[0].id)
      fetchChatMessages(sessionRows[0].id).then(setChatMessages).catch(() => undefined)
    }
  }

  async function refreshPools() {
    setPools(await fetchPools())
  }

  async function refreshOrders() {
    setOrders(await fetchConditionOrders())
  }

  async function refreshSchedules() {
    setSchedules(await fetchSchedules())
  }

  async function refreshEvents() {
    setEvents(await fetchEvents())
  }

  async function handleAnalyze() {
    setLoading(true)
    setMessage('')
    try {
      const result = await analyze(symbol, strategyName)
      setAnalysis(result)
      setTickPrice(result.trade_plan?.entry_price?.toString() ?? result.bars.at(-1)?.close.toString() ?? '')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setLoading(false)
    }
  }

  async function handleScreener() {
    setLoading(true)
    setMessage('')
    try {
      const symbols = screenerSymbols.split(',').map(item => item.trim()).filter(Boolean)
      const result = await runScreener(symbols, strategyName)
      setScreenerResults(result.results)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setLoading(false)
    }
  }

  async function handleSync() {
    const result = await syncWatchlist()
    setMessage(`已同步 ${result.synced} 条盘中监控计划`)
  }

  async function handleTick() {
    const price = Number(tickPrice)
    if (!Number.isFinite(price)) {
      setMessage('请输入有效价格')
      return
    }
    const newAlerts = await sendTick(symbol, price)
    setAlerts(await fetchAlerts())
    await refreshEvents()
    setMessage(newAlerts.length ? `触发 ${newAlerts.length} 条提醒` : '未触发 watchlist 提醒，条件单事件已写入事件中心')
  }

  async function ensureSession(): Promise<number> {
    if (sessionId) return sessionId
    const session = await createChatSession('AI 工作台', selectedAgentId)
    setSessionId(session.id)
    setSessions([session, ...sessions])
    return session.id
  }

  async function handleSendChat() {
    const id = await ensureSession()
    const result = await sendChatMessage(id, chatInput, selectedAgentId)
    setChatMessages(prev => [...prev, result.user, result.assistant])
    setChatInput('')
    await refreshEvents()
  }

  async function handleToolClick(tool: ToolDefinition) {
    const sample = tool.name === 'strategy.analyze'
      ? ` /tool ${tool.name} {"symbol":"${symbol}","strategy_name":"${strategyName}"}`
      : ` /tool ${tool.name} {}`
    setChatInput(sample.trim())
  }

  async function handleTestProfile(id: number) {
    const result = await testModelProfile(id)
    setMessage(JSON.stringify(result, null, 2))
  }

  async function handleAddPoolSymbol() {
    const pool = pools[0]
    if (!pool) return
    await addPoolItem(pool.id, {
      pool_id: pool.id,
      symbol: poolSymbol,
      name: '',
      group_name: poolGroup,
      tags: [],
      notes: '',
      review_enabled: true,
      monitor_enabled: true,
      sort_order: 0
    })
    await refreshPools()
  }

  async function handleCreateCondition() {
    const price = Number(conditionPrice)
    if (!Number.isFinite(price)) {
      setMessage('条件价格无效')
      return
    }
    await createConditionOrder({
      name: `${conditionSymbol} 突破 ${price}`,
      symbol: conditionSymbol,
      order_type: 'notify',
      strategy_name: strategyName,
      condition: { op: 'gte', left: { var: 'last_price' }, right: price },
      action: { notify: true },
      enabled: true,
      status: 'active'
    })
    await refreshOrders()
  }

  async function handleRunSchedule(id: number) {
    const result = await runSchedule(id)
    setMessage(JSON.stringify(result, null, 2))
    await refreshEvents()
  }

  useEffect(() => {
    handleAnalyze()
    refreshAll().catch(error => setMessage(error instanceof Error ? error.message : String(error)))
  }, [])

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>trend-trader</h1>
          <p>A股趋势交易工作台 · 复盘、AI 指挥、定时任务、盘中事件</p>
        </div>
        <nav className="tabs">
          {([
            ['ai', 'AI'],
            ['review', '复盘'],
            ['schedules', '定时任务'],
            ['pools', '股票池'],
            ['conditions', '条件单'],
            ['events', '事件']
          ] as [Tab, string][]).map(([key, label]) => (
            <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>
          ))}
        </nav>
      </header>

      {message && <pre className="message">{message}</pre>}

      {tab === 'review' && (
        <ReviewView
          symbol={symbol}
          setSymbol={setSymbol}
          strategyName={strategyName}
          setStrategyName={setStrategyName}
          analysis={analysis}
          scoreColor={scoreColor}
          plan={plan ?? null}
          loading={loading}
          tickPrice={tickPrice}
          setTickPrice={setTickPrice}
          screenerSymbols={screenerSymbols}
          setScreenerSymbols={setScreenerSymbols}
          screenerResults={screenerResults}
          alerts={alerts}
          onAnalyze={handleAnalyze}
          onScreener={handleScreener}
          onSync={handleSync}
          onTick={handleTick}
          onPickResult={(result) => { setSymbol(result.symbol); setAnalysis(result) }}
        />
      )}

      {tab === 'ai' && (
        <AIView
          providers={providers}
          profiles={profiles}
          skills={skills}
          agents={agents}
          tools={tools}
          sessions={sessions}
          sessionId={sessionId}
          selectedAgentId={selectedAgentId}
          setSelectedAgentId={setSelectedAgentId}
          chatMessages={chatMessages}
          chatInput={chatInput}
          setChatInput={setChatInput}
          onSendChat={handleSendChat}
          onToolClick={handleToolClick}
          onTestProfile={handleTestProfile}
        />
      )}

      {tab === 'schedules' && (
        <SchedulesView
          schedules={schedules}
          onRun={handleRunSchedule}
          onToggle={async (id, enabled) => {
            await setScheduleEnabled(id, enabled)
            await refreshSchedules()
          }}
        />
      )}

      {tab === 'pools' && (
        <PoolsView
          pools={pools}
          poolSymbol={poolSymbol}
          setPoolSymbol={setPoolSymbol}
          poolGroup={poolGroup}
          setPoolGroup={setPoolGroup}
          onAdd={handleAddPoolSymbol}
        />
      )}

      {tab === 'conditions' && (
        <ConditionsView
          orders={orders}
          symbol={conditionSymbol}
          setSymbol={setConditionSymbol}
          price={conditionPrice}
          setPrice={setConditionPrice}
          onCreate={handleCreateCondition}
        />
      )}

      {tab === 'events' && (
        <EventsView events={events} alerts={alerts} onRefresh={async () => { await refreshEvents(); setAlerts(await fetchAlerts()) }} />
      )}
    </main>
  )
}

function ReviewView(props: {
  symbol: string
  setSymbol: (value: string) => void
  strategyName: string
  setStrategyName: (value: string) => void
  analysis: StrategyAnalysis | null
  scoreColor: string
  plan: StrategyAnalysis['trade_plan']
  loading: boolean
  tickPrice: string
  setTickPrice: (value: string) => void
  screenerSymbols: string
  setScreenerSymbols: (value: string) => void
  screenerResults: StrategyAnalysis[]
  alerts: AlertEvent[]
  onAnalyze: () => void
  onScreener: () => void
  onSync: () => void
  onTick: () => void
  onPickResult: (result: StrategyAnalysis) => void
}) {
  return (
    <>
      <section className="toolbar">
        <label>股票代码<input value={props.symbol} onChange={event => props.setSymbol(event.target.value)} /></label>
        <label>策略名<input value={props.strategyName} onChange={event => props.setStrategyName(event.target.value)} /></label>
        <button onClick={props.onAnalyze} disabled={props.loading}>单票复盘</button>
        <button onClick={props.onSync}>同步监控</button>
      </section>

      <section className="main-grid">
        <div className="chart-wrap"><KLinePanel analysis={props.analysis} /></div>
        <aside className="panel">
          <div className="score" style={{ color: props.scoreColor }}>{props.analysis ? props.analysis.score.toFixed(1) : '--'}</div>
          <div className="muted">综合得分 · {props.analysis?.status ?? 'waiting'}</div>
          <MetricList title="分项评分" data={props.analysis?.score_breakdown ?? {}} />
          <MetricList title="策略指标" data={props.analysis?.metrics ?? {}} />
          <h2>交易计划</h2>
          <p>{props.plan?.entry_reason ?? '暂无计划'}</p>
          <dl>
            <div><dt>买点</dt><dd>{props.plan?.entry_price ?? '-'}</dd></div>
            <div><dt>止损</dt><dd>{props.plan?.stop_loss ?? '-'}</dd></div>
            <div><dt>止盈</dt><dd>{props.plan?.take_profit ?? '-'}</dd></div>
            <div><dt>盈亏比</dt><dd>{props.plan?.risk_reward_ratio ?? '-'}</dd></div>
          </dl>
          <h2>盘中模拟</h2>
          <div className="inline">
            <input value={props.tickPrice} onChange={event => props.setTickPrice(event.target.value)} />
            <button onClick={props.onTick}>推送价格</button>
          </div>
        </aside>
      </section>

      <section className="bottom-grid">
        <div className="panel">
          <h2>批量复盘选股</h2>
          <textarea value={props.screenerSymbols} onChange={event => props.setScreenerSymbols(event.target.value)} />
          <button onClick={props.onScreener} disabled={props.loading}>运行选股</button>
          <DataTable headers={['代码', '得分', '状态', '买点']} rows={props.screenerResults.map(result => [
            result.symbol,
            result.score.toFixed(1),
            result.status,
            result.trade_plan?.entry_price ?? '-'
          ])} onRowClick={(index) => props.onPickResult(props.screenerResults[index])} />
        </div>
        <div className="panel">
          <h2>盘中提醒</h2>
          <DataTable headers={['时间', '代码', '类型', '价格']} rows={props.alerts.map(alert => [
            new Date(alert.created_at).toLocaleString(),
            alert.symbol,
            alert.trigger_type,
            alert.price.toFixed(3)
          ])} />
        </div>
      </section>
    </>
  )
}

function AIView(props: {
  providers: ModelProvider[]
  profiles: ModelProfile[]
  skills: SkillSpec[]
  agents: AgentSpec[]
  tools: ToolDefinition[]
  sessions: ChatSession[]
  sessionId: number | null
  selectedAgentId: number | null
  setSelectedAgentId: (id: number | null) => void
  chatMessages: ChatMessage[]
  chatInput: string
  setChatInput: (value: string) => void
  onSendChat: () => void
  onToolClick: (tool: ToolDefinition) => void
  onTestProfile: (id: number) => void
}) {
  return (
    <section className="ai-grid">
      <div className="panel chat-panel">
        <div className="panel-head">
          <h2>AI 对话控制台</h2>
          <select value={props.selectedAgentId ?? ''} onChange={event => props.setSelectedAgentId(event.target.value ? Number(event.target.value) : null)}>
            <option value="">无 Agent</option>
            {props.agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
          </select>
        </div>
        <div className="chat-log">
          {props.chatMessages.map(message => (
            <div key={message.id} className={`chat-message ${message.role}`}>
              <strong>{message.role}</strong>
              <pre>{message.content}</pre>
            </div>
          ))}
        </div>
        <div className="chat-input">
          <textarea value={props.chatInput} onChange={event => props.setChatInput(event.target.value)} />
          <button onClick={props.onSendChat}>发送</button>
        </div>
        <p className="muted">当前会话：{props.sessionId ?? '新会话'} · 历史会话 {props.sessions.length} 个</p>
      </div>

      <aside className="panel">
        <h2>模型渠道</h2>
        <DataTable headers={['渠道', '类型', 'Key']} rows={props.providers.map(item => [item.name, item.provider_type, item.api_key_env])} />
        <h2>模型配置</h2>
        <table>
          <thead><tr><th>名称</th><th>模型</th><th>测试</th></tr></thead>
          <tbody>
            {props.profiles.map(profile => (
              <tr key={profile.id}>
                <td>{profile.name}</td>
                <td>{profile.model}</td>
                <td><button className="small" onClick={() => props.onTestProfile(profile.id)}>测</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <h2>Skills</h2>
        <DataTable headers={['名称', '工具数']} rows={props.skills.map(skill => [skill.name, skill.tools_allowed.length])} />
        <h2>Tools</h2>
        <div className="tool-list">
          {props.tools.map(tool => (
            <button key={tool.name} className={tool.requires_confirmation ? 'warn' : 'ghost'} onClick={() => props.onToolClick(tool)}>{tool.name}</button>
          ))}
        </div>
      </aside>
    </section>
  )
}

function SchedulesView(props: { schedules: ScheduleSpec[]; onRun: (id: number) => void; onToggle: (id: number, enabled: boolean) => void }) {
  return (
    <section className="panel">
      <h2>定时任务</h2>
      <table>
        <thead><tr><th>名称</th><th>触发</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          {props.schedules.map(schedule => (
            <tr key={schedule.id}>
              <td><strong>{schedule.name}</strong><div className="muted">{schedule.description}</div></td>
              <td>{schedule.trigger.type} {schedule.trigger.cron ?? schedule.trigger.every_seconds}</td>
              <td>{schedule.status}</td>
              <td className="actions">
                <button onClick={() => props.onRun(schedule.id)}>立即执行</button>
                <button className="ghost" onClick={() => props.onToggle(schedule.id, schedule.status !== 'enabled')}>
                  {schedule.status === 'enabled' ? '停用' : '启用'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function PoolsView(props: {
  pools: StockPool[]
  poolSymbol: string
  setPoolSymbol: (value: string) => void
  poolGroup: string
  setPoolGroup: (value: string) => void
  onAdd: () => void
}) {
  return (
    <section className="pool-layout">
      <aside className="panel">
        <h2>添加自选</h2>
        <label>股票代码<input value={props.poolSymbol} onChange={event => props.setPoolSymbol(event.target.value)} /></label>
        <label>分组<input value={props.poolGroup} onChange={event => props.setPoolGroup(event.target.value)} /></label>
        <button onClick={props.onAdd}>添加</button>
      </aside>
      <div className="panel">
        <h2>股票池</h2>
        {props.pools.map(pool => (
          <div key={pool.id} className="pool-block">
            <h3>{pool.name}</h3>
            <DataTable headers={['分组', '代码', '名称', '复盘', '监控']} rows={pool.items.map(item => [
              item.group_name,
              item.symbol,
              item.name || '-',
              item.review_enabled ? '是' : '否',
              item.monitor_enabled ? '是' : '否'
            ])} />
          </div>
        ))}
      </div>
    </section>
  )
}

function ConditionsView(props: {
  orders: ConditionOrder[]
  symbol: string
  setSymbol: (value: string) => void
  price: string
  setPrice: (value: string) => void
  onCreate: () => void
}) {
  return (
    <section className="bottom-grid">
      <div className="panel">
        <h2>创建叮叮条件单</h2>
        <label>股票代码<input value={props.symbol} onChange={event => props.setSymbol(event.target.value)} /></label>
        <label>触发价 ≥<input value={props.price} onChange={event => props.setPrice(event.target.value)} /></label>
        <button onClick={props.onCreate}>保存条件单</button>
      </div>
      <div className="panel">
        <h2>条件单列表</h2>
        <DataTable headers={['名称', '代码', '类型', '状态', '条件']} rows={props.orders.map(order => [
          order.name,
          order.symbol,
          order.order_type,
          order.status,
          JSON.stringify(order.condition)
        ])} />
      </div>
    </section>
  )
}

function EventsView(props: { events: EventRecord[]; alerts: AlertEvent[]; onRefresh: () => void }) {
  return (
    <section className="bottom-grid">
      <div className="panel">
        <div className="panel-head"><h2>事件中心</h2><button onClick={props.onRefresh}>刷新</button></div>
        <DataTable headers={['时间', '类型', '标题', '状态']} rows={props.events.map(event => [
          new Date(event.created_at).toLocaleString(),
          event.category,
          event.title,
          event.status
        ])} />
      </div>
      <div className="panel">
        <h2>Watchlist 提醒</h2>
        <DataTable headers={['时间', '代码', '类型', '消息']} rows={props.alerts.map(alert => [
          new Date(alert.created_at).toLocaleString(),
          alert.symbol,
          alert.trigger_type,
          alert.message
        ])} />
      </div>
    </section>
  )
}

function MetricList({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <>
      <h2>{title}</h2>
      <dl>
        {Object.entries(data).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{typeof value === 'number' ? value.toFixed(2) : String(value ?? '-')}</dd>
          </div>
        ))}
      </dl>
    </>
  )
}

function DataTable({ headers, rows, onRowClick }: { headers: string[]; rows: unknown[][]; onRowClick?: (index: number) => void }) {
  return (
    <table>
      <thead><tr>{headers.map(header => <th key={header}>{header}</th>)}</tr></thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex} onClick={() => onRowClick?.(rowIndex)}>
            {row.map((cell, cellIndex) => <td key={cellIndex}>{String(cell ?? '-')}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
