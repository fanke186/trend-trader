import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  createChatSession,
  fetchAgents,
  fetchChatMessages,
  fetchChatSessions,
  fetchEvents,
  sendChatMessage
} from './api'
import type { AgentSpec, ChatMessage, ChatSession, EventRecord } from './types'

type AppState = {
  agents: AgentSpec[]
  sessions: ChatSession[]
  chatMessages: ChatMessage[]
  selectedAgentId: number | null
  sessionId: number | null
  currentSymbol: string
  events: EventRecord[]
  setSelectedAgentId: (id: number | null) => void
  setCurrentSymbol: (symbol: string) => void
  sendChat: (content: string) => Promise<void>
  refreshEvents: () => Promise<void>
}

const AppStateContext = createContext<AppState | null>(null)

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [agents, setAgents] = useState<AgentSpec[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [currentSymbol, setCurrentSymbol] = useState('002261')
  const [events, setEvents] = useState<EventRecord[]>([])

  useEffect(() => {
    Promise.all([fetchAgents(), fetchChatSessions(), fetchEvents()])
      .then(([agentRows, sessionRows, eventRows]) => {
        setAgents(agentRows)
        setSessions(sessionRows)
        setEvents(eventRows)
        if (agentRows[0]) setSelectedAgentId(agentRows[0].id)
        if (sessionRows[0]) {
          setSessionId(sessionRows[0].id)
          fetchChatMessages(sessionRows[0].id).then(setChatMessages).catch(() => undefined)
        }
      })
      .catch(() => undefined)
  }, [])

  async function ensureSession(): Promise<number> {
    if (sessionId) return sessionId
    const session = await createChatSession('AI 指挥台', selectedAgentId)
    setSessionId(session.id)
    setSessions(prev => [session, ...prev])
    return session.id
  }

  async function sendChat(content: string) {
    const id = await ensureSession()
    const result = await sendChatMessage(id, content, selectedAgentId)
    setChatMessages(prev => [...prev, result.user, result.assistant])
    await refreshEvents()
  }

  async function refreshEvents() {
    setEvents(await fetchEvents())
  }

  const value = useMemo<AppState>(
    () => ({
      agents,
      sessions,
      chatMessages,
      selectedAgentId,
      sessionId,
      currentSymbol,
      events,
      setSelectedAgentId,
      setCurrentSymbol,
      sendChat,
      refreshEvents
    }),
    [agents, sessions, chatMessages, selectedAgentId, sessionId, currentSymbol, events]
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

export function useAppState() {
  const value = useContext(AppStateContext)
  if (!value) throw new Error('useAppState must be used inside AppStateProvider')
  return value
}
