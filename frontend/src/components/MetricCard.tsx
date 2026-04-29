interface Props {
  label: string
  value: number | string
  color?: string
  sub?: string
}

const GLOW_MAP: Record<string, string> = {
  'text-up': 'drop-shadow-[0_0_12px_rgba(0,212,170,0.35)]',
  'text-down': 'drop-shadow-[0_0_12px_rgba(255,71,87,0.35)]',
  'text-warn': 'drop-shadow-[0_0_12px_rgba(251,191,36,0.35)]',
}

export function MetricCard({ label, value, color = 'text-neutral-200', sub }: Props) {
  const glow = GLOW_MAP[color] ?? ''

  return (
    <div className="metric-card">
      <div className="text-xs text-neutral-400 mb-1">{label}</div>
      <div className={`font-mono text-2xl font-bold ${color} ${glow}`}>
        {typeof value === 'number' ? value.toFixed(2) : value}
      </div>
      {sub && <div className="mt-1 text-xs text-neutral-500">{sub}</div>}
    </div>
  )
}
