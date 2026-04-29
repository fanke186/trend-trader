import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { addPoolItem, fetchPools, fetchQuotes } from '../api'
import { PriceDisplay } from '../components/PriceDisplay'
import type { Quote, StockPool } from '../types'

export function PoolPage() {
  const [pools, setPools] = useState<StockPool[]>([])
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [symbol, setSymbol] = useState('002261')
  const [group, setGroup] = useState('默认')
  const navigate = useNavigate()
  const pool = pools[0]
  const items = useMemo(() => pool?.items ?? [], [pool])

  async function refresh() {
    const rows = await fetchPools()
    setPools(rows)
    const symbols = rows.flatMap(item => item.items.map(child => child.symbol))
    if (symbols.length) {
      const quoteRows = await fetchQuotes(symbols)
      setQuotes(Object.fromEntries(quoteRows.map(quote => [quote.symbol, quote])))
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function addSymbol() {
    if (!pool) return
    await addPoolItem(pool.id, { pool_id: pool.id, symbol, group_name: group, name: '', tags: [], notes: '', review_enabled: true, monitor_enabled: true, sort_order: 0 })
    await refresh()
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input className="rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm outline-none" value={symbol} onChange={event => setSymbol(event.target.value)} />
        <input className="rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm outline-none" value={group} onChange={event => setGroup(event.target.value)} />
        <button className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-base-950" onClick={() => void addSymbol()}>
          添加
        </button>
      </div>
      <div className="overflow-hidden rounded-md border border-base-800 bg-base-900">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-base-850 text-xs text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left">代码</th>
              <th className="px-3 py-2 text-left">分组</th>
              <th className="px-3 py-2 text-right">最新价</th>
              <th className="px-3 py-2 text-right">涨跌幅</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const quote = quotes[item.symbol]
              return (
                <tr key={item.id} className="cursor-pointer border-t border-base-800 hover:bg-base-850" onClick={() => navigate(`/review/${item.symbol}`)}>
                  <td className="px-3 py-2 font-mono text-neutral-100">{item.symbol}</td>
                  <td className="px-3 py-2 text-neutral-400">{item.group_name}</td>
                  <td className="px-3 py-2 text-right">{quote ? <PriceDisplay price={quote.price} change={quote.change_pct} /> : '--'}</td>
                  <td className={`px-3 py-2 text-right font-mono ${quote && quote.change_pct >= 0 ? 'text-up' : 'text-down'}`}>{quote ? `${quote.change_pct.toFixed(2)}%` : '--'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
