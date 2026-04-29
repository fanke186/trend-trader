import { useNavigate } from 'react-router-dom'
import { useAppState } from '../appState'

function readAnalysisSymbol(payload: Record<string, unknown>): string | null {
  const output = payload.output
  const direct = payload.analysis
  const container = typeof output === 'object' && output !== null ? (output as Record<string, unknown>) : payload
  const analysis = direct ?? container.analysis
  if (typeof analysis === 'object' && analysis !== null) {
    const symbol = (analysis as Record<string, unknown>).symbol
    return typeof symbol === 'string' ? symbol : null
  }
  return null
}

export function AIPage() {
  const { chatMessages, currentSymbol } = useAppState()
  const navigate = useNavigate()
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">AI 指挥台</h2>
          <p className="mt-1 text-sm text-neutral-500">当前上下文股票：{currentSymbol}</p>
        </div>
        <button className="rounded-md border border-base-800 bg-base-850 px-3 py-2 text-sm text-neutral-200 hover:border-primary/50" onClick={() => navigate(`/review/${currentSymbol}`)}>
          查看K线
        </button>
      </div>
      <div className="space-y-3">
        {chatMessages.map(message => {
          const symbol = readAnalysisSymbol(message.payload)
          return (
            <article key={message.id} className={`rounded-md border p-3 ${message.role === 'user' ? 'border-base-800 bg-base-850' : 'border-base-800 bg-base-900'}`}>
              <div className="mb-2 font-mono text-xs uppercase text-neutral-500">{message.role}</div>
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-neutral-200">{message.content}</pre>
              {symbol && (
                <div className="mt-3 flex gap-2">
                  <button className="rounded bg-base-850 px-2 py-1 text-xs hover:bg-base-800" onClick={() => navigate(`/review/${symbol}`)}>
                    查看K线图
                  </button>
                  <button className="rounded bg-base-850 px-2 py-1 text-xs hover:bg-base-800" onClick={() => navigate(`/monitor?symbol=${symbol}&action=create-condition`)}>
                    加入监控
                  </button>
                </div>
              )}
            </article>
          )
        })}
        {!chatMessages.length && (
          <div className="rounded-md border border-base-800 bg-base-900 p-8 text-center text-sm text-neutral-500">
            可在底部输入“分析 002261 近期趋势”或使用 `/tool strategy.analyze {"{"}"symbol":"002261","strategy_name":"trend_trading"{"}"}`
          </div>
        )}
      </div>
    </div>
  )
}
