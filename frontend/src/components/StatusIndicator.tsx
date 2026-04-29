import { Wifi } from 'lucide-react'

export function StatusIndicator() {
  return (
    <span className="inline-flex items-center gap-1 text-up">
      <Wifi size={14} />
      <span className="font-mono">API</span>
    </span>
  )
}
