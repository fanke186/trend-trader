import { useEffect, useRef } from 'react'
import { CandlestickSeries, ColorType, HistogramSeries, createChart } from 'lightweight-charts'
import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts'
import type { StrategyAnalysis } from './types'

function toTime(date: string): Time {
  return date as Time
}

export function KLinePanel({ analysis }: { analysis: StrategyAnalysis | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: '#0a0d14' },
        textColor: '#94a3b8'
      },
      grid: {
        vertLines: { color: '#1a1f2e' },
        horzLines: { color: '#1a1f2e' }
      },
      rightPriceScale: { borderColor: '#1a1f2e' },
      timeScale: { borderColor: '#1a1f2e' }
    })
    chartRef.current = chart
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#00d4aa',
      downColor: '#ff4757',
      borderUpColor: '#00d4aa',
      borderDownColor: '#ff4757',
      wickUpColor: '#00d4aa',
      wickDownColor: '#ff4757'
    })
    volumeRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      color: '#38bdf8'
    })
    volumeRef.current.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

    const resize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      volumeRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!analysis || !candleRef.current || !volumeRef.current || !chartRef.current) return
    candleRef.current.setData(
      analysis.bars.map(bar => ({
        time: toTime(bar.date),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close
      }))
    )
    volumeRef.current.setData(
      analysis.bars.map(bar => ({
        time: toTime(bar.date),
        value: bar.volume,
        color: bar.close >= bar.open ? '#00d4aa55' : '#ff475755'
      }))
    )
    analysis.overlays.forEach(overlay => {
      const point = overlay.points[0]
      if (point && (overlay.kind === 'entry' || overlay.kind === 'stop')) {
        candleRef.current?.createPriceLine({
          price: point.value,
          color: overlay.kind === 'entry' ? '#38bdf8' : '#ff4757',
          lineWidth: 1,
          title: overlay.label
        })
      }
    })
    chartRef.current.timeScale().fitContent()
  }, [analysis])

  return <div ref={containerRef} className="h-[420px] w-full overflow-hidden rounded-md border border-base-800 bg-base-900" />
}
