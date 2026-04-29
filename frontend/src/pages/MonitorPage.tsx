import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { aiCreateConditionOrder, fetchConditionOrders, fetchEvents, fetchQuotes } from '../api'
import { PriceDisplay } from '../components/PriceDisplay'
import type { ConditionOrder, EventRecord, Quote } from '../types'

export function MonitorPage() {
  const [searchParams] = useSearchParams()
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [orders, setOrders] = useState<ConditionOrder[]>([])
  const [events, setEvents] = useState<EventRecord[]>([])
  const [symbol, setSymbol] = useState(searchParams.get('symbol') ?? '002261')
  const [description, setDescription] = useState('突破 18.5 时通知我')
  const symbols = useMemo(() => Array.from(new Set([symbol, ...orders.map(order => order.symbol)])), [symbol, orders])

  async function refresh() {
    const [orderRows, eventRows] = await Promise.all([fetchConditionOrders(), fetchEvents()])
    setOrders(orderRows)
    setEvents(eventRows)
    const quoteRows = await fetchQuotes(symbols.length ? symbols : ['002261'])
    setQuotes(Object.fromEntries(quoteRows.map(quote => [quote.symbol, quote])))
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/quotes`
    const ws = new WebSocket(url)
    ws.onopen = () => ws.send(JSON.stringify({ symbols }))
    ws.onmessage = event => {
      const payload = JSON.parse(event.data) as { type?: string; data?: Quote }
      if (payload.type === 'quote' && payload.data) {
        setQuotes(prev => ({ ...prev, [payload.data!.symbol]: payload.data! }))
      }
    }
    return () => ws.close()
  }, [symbols.join(',')])

  async function createCondition() {
    await aiCreateConditionOrder(symbol, description)
    await refresh()
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="rounded-md border border-base-800 bg-base-900">
        <div className="border-b border-base-800 p-3 text-sm font-semibold">实时行情</div>
        <div className="divide-y divide-base-800">
          {symbols.map(item => {
            const quote = quotes[item]
            return (
              <div key={item} className="grid grid-cols-4 gap-2 px-3 py-2 text-sm">
                <span className="font-mono">{item}</span>
                <span>{quote ? <PriceDisplay price={quote.price} change={quote.change_pct} /> : '--'}</span>
                <span className="text-right font-mono text-neutral-400">{quote?.high?.toFixed(2) ?? '--'}</span>
                <span className="text-right font-mono text-neutral-400">{quote?.low?.toFixed(2) ?? '--'}</span>
              </div>
            )
          })}
        </div>
      </section>
      <aside className="space-y-4">
        <section className="rounded-md border border-base-800 bg-base-900 p-3">
          <div className="mb-2 text-sm font-semibold">创建条件单</div>
          <div className="space-y-2">
            <input className="w-full rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm outline-none" value={symbol} onChange={event => setSymbol(event.target.value)} />
            <input className="w-full rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm outline-none" value={description} onChange={event => setDescription(event.target.value)} />
            <button className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-base-950" onClick={() => void createCondition()}>
              AI 创建
            </button>
          </div>
        </section>
        <section className="rounded-md border border-base-800 bg-base-900">
          <div className="border-b border-base-800 p-3 text-sm font-semibold">条件单</div>
          <div className="max-h-72 overflow-auto divide-y divide-base-800">
            {orders.map(order => (
              <div key={order.id} className="p-3 text-sm">
                <div className="font-mono text-primary">{order.symbol}</div>
                <div className="text-neutral-300">{order.name}</div>
                <div className="text-xs text-neutral-500">{order.status}</div>
              </div>
            ))}
          </div>
        </section>
        <section className="rounded-md border border-base-800 bg-base-900">
          <div className="border-b border-base-800 p-3 text-sm font-semibold">事件中心</div>
          <div className="max-h-72 overflow-auto divide-y divide-base-800">
            {events.slice(0, 20).map(event => (
              <div key={event.id} className="p-3 text-xs">
                <div className="text-neutral-200">{event.title}</div>
                <div className="mt-1 text-neutral-500">{event.message}</div>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </div>
  )
}
