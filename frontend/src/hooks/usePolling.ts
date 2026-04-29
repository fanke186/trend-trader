import { useEffect, useRef, useState } from 'react'

export function usePolling(
  callback: () => Promise<void>,
  intervalMs: number,
  enabled = true
) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    if (!enabled) return

    let running = true

    async function tick() {
      if (!running) return
      setLoading(true)
      try {
        await callbackRef.current()
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)))
      } finally {
        if (running) setLoading(false)
      }
    }

    void tick()
    const timer = setInterval(() => void tick(), intervalMs)

    return () => {
      running = false
      clearInterval(timer)
    }
  }, [intervalMs, enabled])

  return { loading, error }
}
