import { useEffect, useState } from 'react'
import { explainStrategy, fetchStrategies, generateStrategy } from '../api'
import type { StrategySpec } from '../types'

export function StrategyPage() {
  const [strategies, setStrategies] = useState<StrategySpec[]>([])
  const [name, setName] = useState('ma_volume_strategy')
  const [description, setDescription] = useState('5日线上穿20日线并且成交量放大')
  const [message, setMessage] = useState('')

  async function refresh() {
    setStrategies(await fetchStrategies())
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function createStrategy() {
    const strategy = await generateStrategy(name, description)
    setStrategies(prev => [strategy, ...prev])
  }

  async function explain(id: number) {
    const result = await explainStrategy(id)
    setMessage(result.explanation)
    await refresh()
  }

  return (
    <div className="space-y-4">
      <section className="rounded-md border border-base-800 bg-base-900 p-3">
        <div className="grid gap-2 md:grid-cols-[220px_minmax(0,1fr)_auto]">
          <input className="rounded-md border border-base-800 bg-base-850 px-3 py-2 font-mono text-sm outline-none" value={name} onChange={event => setName(event.target.value)} />
          <input className="rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm outline-none" value={description} onChange={event => setDescription(event.target.value)} />
          <button className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-base-950" onClick={() => void createStrategy()}>
            生成策略
          </button>
        </div>
      </section>
      {message && <pre className="max-h-80 overflow-auto rounded-md border border-base-800 bg-base-900 p-3 whitespace-pre-wrap text-sm text-neutral-300">{message}</pre>}
      <div className="grid gap-3 xl:grid-cols-2">
        {strategies.map(strategy => (
          <article key={strategy.id} className="rounded-md border border-base-800 bg-base-900 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-mono text-base font-semibold text-primary">{strategy.name}</h3>
                <p className="mt-1 text-sm text-neutral-400">{strategy.description}</p>
              </div>
              <button className="rounded-md border border-base-800 bg-base-850 px-2 py-1 text-xs hover:border-primary/50" onClick={() => void explain(strategy.id)}>
                释义
              </button>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-neutral-500">
              <div>features {strategy.features.length}</div>
              <div>filters {strategy.filters.length}</div>
              <div>scoring {strategy.scoring.length}</div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
