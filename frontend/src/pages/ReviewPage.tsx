import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { analyze, runScreener } from '../api'
import { useAppState } from '../appState'
import { KLinePanel } from '../KLinePanel'
import type { StrategyAnalysis } from '../types'

const DEFAULT_SYMBOLS = '000001,002261,600519,300750,601318'

export function ReviewPage() {
  const params = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { currentSymbol, setCurrentSymbol } = useAppState()
  const [symbol, setSymbol] = useState(params.symbol ?? currentSymbol)
  const [strategyName, setStrategyName] = useState(searchParams.get('strategy') ?? 'trend_trading')
  const [analysis, setAnalysis] = useState<StrategyAnalysis | null>(null)
  const [screenerSymbols, setScreenerSymbols] = useState(DEFAULT_SYMBOLS)
  const [screenerResults, setScreenerResults] = useState<StrategyAnalysis[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (params.symbol) {
      setSymbol(params.symbol)
      void handleAnalyze(params.symbol, strategyName)
    }
  }, [params.symbol])

  async function handleAnalyze(target = symbol, strategy = strategyName) {
    setLoading(true)
    setMessage('')
    try {
      const result = await analyze(target, strategy)
      setAnalysis(result)
      setCurrentSymbol(result.symbol)
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-neutral-500">
          股票
          <input className="mt-1 block rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm text-neutral-200 outline-none" value={symbol} onChange={event => setSymbol(event.target.value)} />
        </label>
        <label className="text-xs text-neutral-500">
          策略
          <input className="mt-1 block rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm text-neutral-200 outline-none" value={strategyName} onChange={event => setStrategyName(event.target.value)} />
        </label>
        <button className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-base-950 disabled:opacity-50" onClick={() => void handleAnalyze()} disabled={loading}>
          分析
        </button>
        <button className="rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm text-neutral-200 hover:border-primary/50" onClick={() => navigate(`/monitor?symbol=${symbol}&action=create-condition`)}>
          加入监控
        </button>
      </div>
      {message && <div className="rounded-md border border-down/30 bg-down/10 p-3 text-sm text-down">{message}</div>}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <KLinePanel analysis={analysis} />
        <aside className="space-y-3">
          <div className="metric-card">
            <div className="text-xs text-neutral-500">评分</div>
            <div className="mt-1 font-mono text-4xl font-bold text-primary">{analysis?.score.toFixed(1) ?? '--'}</div>
          </div>
          <div className="metric-card space-y-2 text-sm">
            <div className="font-semibold">交易计划</div>
            <div>入场：{analysis?.trade_plan?.entry_price ?? '--'}</div>
            <div>止损：{analysis?.trade_plan?.stop_loss ?? '--'}</div>
            <div>止盈：{analysis?.trade_plan?.take_profit ?? '--'}</div>
            <div>盈亏比：{analysis?.trade_plan?.risk_reward_ratio ?? '--'}</div>
          </div>
        </aside>
      </div>
      <section className="rounded-md border border-base-800 bg-base-900 p-3">
        <div className="mb-2 flex items-center gap-2">
          <input className="flex-1 rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm outline-none" value={screenerSymbols} onChange={event => setScreenerSymbols(event.target.value)} />
          <button className="rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm hover:border-primary/50" onClick={() => void handleScreener()}>
            运行选股
          </button>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {screenerResults.map(result => (
            <button key={result.symbol} className="rounded-md border border-base-800 bg-base-850 p-3 text-left hover:border-primary/50" onClick={() => navigate(`/review/${result.symbol}`)}>
              <div className="font-mono text-sm text-neutral-100">{result.symbol}</div>
              <div className="mt-1 text-xs text-neutral-500">score {result.score.toFixed(1)} · {result.status}</div>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}
