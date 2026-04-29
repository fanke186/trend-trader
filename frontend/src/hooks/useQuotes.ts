import { useCallback, useRef, useState } from 'react'
import { useWebSocket } from './useWebSocket'
import type { Quote } from '../types'

export function useQuotes(symbols: string[]) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const symbolsRef = useRef(symbols)
  symbolsRef.current = symbols

  const handleMessage = useCallback((data: unknown) => {
    const payload = data as { type?: string; data?: Quote }
    if (payload.type === 'quote' && payload.data) {
      setQuotes(prev => ({ ...prev, [payload.data!.symbol]: payload.data! }))
    }
  }, [])

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const { connected, send } = useWebSocket(`${protocol}://${location.host}/ws/quotes`, { onMessage: handleMessage })

  const subscribe = useCallback((newSymbols: string[]) => {
    send({ symbols: newSymbols })
  }, [send])

  // re-subscribe when symbols change
  const prevSymbols = useRef(symbols)
  if (prevSymbols.current.join(',') !== symbols.join(',')) {
    prevSymbols.current = symbols
    if (connected && symbols.length > 0) {
      subscribe(symbols)
    }
  }

  return { quotes, connected, subscribe }
}
