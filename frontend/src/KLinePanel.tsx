import { useEffect, useRef } from 'react'
import { dispose, init } from 'klinecharts'
import type { StrategyAnalysis } from './types'

type ChartApi = {
  setSymbol: (symbol: unknown) => void
  setPeriod: (period: unknown) => void
  setDataLoader: (loader: unknown) => void
  createIndicator?: (indicator: unknown) => void
  createOverlay?: (overlay: unknown) => void
  removeOverlay?: (filter?: unknown) => void
}

function toTimestamp(date: string): number {
  return new Date(`${date}T00:00:00+08:00`).getTime()
}

function overlayToKLine(overlay: StrategyAnalysis['overlays'][number]) {
  return {
    id: overlay.id,
    name: overlay.name,
    lock: true,
    points: overlay.points.map(point => ({
      timestamp: toTimestamp(point.date),
      value: point.value
    })),
    styles: overlay.styles,
    extendData: {
      label: overlay.label,
      kind: overlay.kind
    }
  }
}

export function KLinePanel({ analysis }: { analysis: StrategyAnalysis | null }) {
  const chartRef = useRef<ChartApi | null>(null)

  useEffect(() => {
    const chart = init('trend-kline') as ChartApi | null
    if (!chart) {
      return
    }
    chartRef.current = chart
    chart.setPeriod({ span: 1, type: 'day' })
    chart.createIndicator?.({ name: 'VOL', paneId: 'volume_pane' })

    return () => {
      dispose('trend-kline')
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !analysis) {
      return
    }
    chart.setSymbol({ ticker: `${analysis.symbol}.${analysis.bars.at(-1)?.exchange ?? ''}` })
    chart.setDataLoader({
      getBars: ({ callback }: { callback: (bars: unknown[]) => void }) => {
        callback(
          analysis.bars.map(bar => ({
            timestamp: toTimestamp(bar.date),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            turnover: bar.turnover
          }))
        )
      }
    })
    chart.removeOverlay?.()
    analysis.overlays.forEach(overlay => {
      chart.createOverlay?.(overlayToKLine(overlay))
    })
  }, [analysis])

  return <div id="trend-kline" className="kline" />
}
