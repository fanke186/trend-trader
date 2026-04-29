import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { ChatInput } from './ChatInput'
import { ContextPanel } from './ContextPanel'
import { Sidebar } from './Sidebar'
import { StatusIndicator } from './StatusIndicator'

export function Layout() {
  const [contextOpen, setContextOpen] = useState(true)
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-base-950 text-neutral-200">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-base-800 bg-base-900/80 px-4 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <h1 className="font-mono text-sm font-bold text-primary">trend-trader</h1>
          <span className="text-xs text-neutral-500">v0.2</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-neutral-400">
          <StatusIndicator />
          <span className="font-mono">{new Date().toLocaleTimeString('zh-CN', { hour12: false })}</span>
          <span>飞书 dry-run</span>
          <span>交易 dry-run</span>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-auto p-4">
            <Outlet />
          </div>
          <div className="shrink-0 border-t border-base-800 bg-base-900/70 backdrop-blur-xl">
            <ChatInput />
          </div>
        </main>
        {contextOpen && <ContextPanel onClose={() => setContextOpen(false)} />}
      </div>
    </div>
  )
}
