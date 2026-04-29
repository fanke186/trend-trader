import { useEffect, useState } from 'react'
import { fetchSchedules, runSchedule, setScheduleEnabled } from '../api'
import type { ScheduleSpec } from '../types'

export function SchedulePage() {
  const [schedules, setSchedules] = useState<ScheduleSpec[]>([])
  const [message, setMessage] = useState('')

  async function refresh() {
    setSchedules(await fetchSchedules())
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function run(id: number) {
    const result = await runSchedule(id)
    setMessage(JSON.stringify(result, null, 2))
    await refresh()
  }

  return (
    <div className="space-y-3">
      {message && <pre className="max-h-72 overflow-auto rounded-md border border-base-800 bg-base-900 p-3 text-xs">{message}</pre>}
      {schedules.map(schedule => (
        <article key={schedule.id} className="rounded-md border border-base-800 bg-base-900 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold">{schedule.name}</h3>
              <p className="mt-1 text-sm text-neutral-500">{schedule.description}</p>
            </div>
            <div className="flex gap-2">
              <button className="rounded-md border border-base-800 bg-base-850 px-2 py-1 text-xs" onClick={() => void setScheduleEnabled(schedule.id, schedule.status !== 'enabled').then(refresh)}>
                {schedule.status === 'enabled' ? '停用' : '启用'}
              </button>
              <button className="rounded-md bg-primary px-2 py-1 text-xs font-semibold text-base-950" onClick={() => void run(schedule.id)}>
                运行
              </button>
            </div>
          </div>
          <div className="mt-2 font-mono text-xs text-neutral-500">{schedule.trigger.cron || schedule.trigger.type}</div>
        </article>
      ))}
    </div>
  )
}
