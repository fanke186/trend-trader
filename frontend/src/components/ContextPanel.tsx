import { X } from 'lucide-react'
import { useAppState } from '../appState'

export function ContextPanel({ onClose }: { onClose: () => void }) {
  const { currentSymbol, events } = useAppState()
  return (
    <aside className="hidden w-80 shrink-0 border-l border-base-800 bg-base-900/70 backdrop-blur-xl xl:block">
      <div className="flex h-12 items-center justify-between border-b border-base-800 px-3">
        <span className="text-sm font-semibold text-neutral-200">上下文</span>
        <button className="rounded p-1 text-neutral-500 hover:bg-base-850 hover:text-neutral-100" onClick={onClose} title="关闭">
          <X size={16} />
        </button>
      </div>
      <div className="space-y-4 p-3">
        <section className="metric-card">
          <div className="text-xs text-neutral-500">当前股票</div>
          <div className="mt-1 font-mono text-2xl font-bold text-primary">{currentSymbol}</div>
        </section>
        <section>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">最近事件</div>
          <div className="space-y-2">
            {events.slice(0, 6).map(event => (
              <div key={event.id} className="rounded-md border border-base-800 bg-base-850 p-2">
                <div className="truncate text-xs font-medium text-neutral-200">{event.title}</div>
                <div className="mt-1 line-clamp-2 text-xs text-neutral-500">{event.message}</div>
              </div>
            ))}
            {!events.length && <div className="text-xs text-neutral-500">暂无事件</div>}
          </div>
        </section>
      </div>
    </aside>
  )
}
