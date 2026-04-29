import { Send, Wrench } from 'lucide-react'
import { KeyboardEvent, useEffect, useRef, useState } from 'react'
import { fetchTools } from '../api'
import { useAppState } from '../appState'
import type { ToolDefinition } from '../types'

export function ChatInput() {
  const { agents, selectedAgentId, setSelectedAgentId, sendChat } = useAppState()
  const [input, setInput] = useState('')
  const [tools, setTools] = useState<ToolDefinition[]>([])
  const [showTools, setShowTools] = useState(false)
  const [sending, setSending] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    fetchTools().then(setTools).catch(() => undefined)
  }, [])

  async function submit() {
    const content = input.trim()
    if (!content || sending) return
    setSending(true)
    try {
      await sendChat(content)
      setInput('')
      setShowTools(false)
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submit()
    }
    if (event.key === 'Tab' && input.startsWith('/')) {
      event.preventDefault()
      setShowTools(true)
    }
  }

  return (
    <div className="p-3">
      {showTools && (
        <div className="mb-2 flex max-h-24 flex-wrap gap-1 overflow-auto">
          {tools.map(tool => (
            <button
              key={tool.name}
              className="rounded border border-base-800 bg-base-850 px-2 py-1 font-mono text-xs text-neutral-300 hover:border-primary/50"
              onClick={() => {
                setInput(`/tool ${tool.name} {}`)
                setShowTools(false)
                inputRef.current?.focus()
              }}
            >
              {tool.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <select
          className="h-10 rounded-md border border-base-800 bg-base-850 px-2 text-xs text-neutral-300 outline-none"
          value={selectedAgentId ?? ''}
          onChange={event => setSelectedAgentId(event.target.value ? Number(event.target.value) : null)}
          title="Agent"
        >
          <option value="">本地</option>
          {agents.map(agent => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
            </option>
          ))}
        </select>
        <div className="relative flex-1">
          <Wrench className="absolute left-2 top-2.5 text-neutral-500" size={16} />
          <textarea
            ref={inputRef}
            className="h-14 w-full resize-none rounded-md border border-base-800 bg-base-850 py-2 pl-8 pr-3 font-mono text-sm text-neutral-200 outline-none placeholder:text-neutral-600 focus:border-primary/60"
            value={input}
            onChange={event => {
              setInput(event.target.value)
              setShowTools(event.target.value.startsWith('/'))
            }}
            onKeyDown={handleKeyDown}
            placeholder="输入自然语言或 /tool 工具名 JSON 参数"
          />
        </div>
        <button
          className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-base-950 hover:opacity-90 disabled:opacity-50"
          onClick={() => void submit()}
          disabled={sending}
          title="发送"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
