export function PriceDisplay({ price, change }: { price: number; change?: number }) {
  const color = !change ? 'text-neutral-400' : change > 0 ? 'text-up text-glow-up' : 'text-down text-glow-down'
  const arrow = !change ? '' : change > 0 ? 'up' : 'down'
  return (
    <span className={`font-mono font-semibold ${color}`}>
      {price.toFixed(2)} {arrow}
    </span>
  )
}
