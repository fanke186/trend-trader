import { useCallback, useEffect, useRef, useState } from 'react'

interface UseWebSocketOptions {
  onMessage: (data: unknown) => void
  reconnectInterval?: number
}

export function useWebSocket(url: string | null, { onMessage, reconnectInterval = 5000 }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const send = useCallback((payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  useEffect(() => {
    if (!url) return
    const wsUrl = url

    function connect() {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        reconnectTimer.current = setTimeout(connect, reconnectInterval)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (event) => {
        try {
          onMessageRef.current(JSON.parse(event.data as string))
        } catch {
          // ignore parse errors
        }
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [url, reconnectInterval])

  return { connected, send }
}
