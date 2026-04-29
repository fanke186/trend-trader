import { Bot, CalendarClock, Crosshair, Database, LineChart, Radio, Settings } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const items = [
  { to: '/', label: 'AI', icon: Bot },
  { to: '/review', label: '复盘', icon: LineChart },
  { to: '/strategy', label: '策略', icon: Crosshair },
  { to: '/pool', label: '股票池', icon: Database },
  { to: '/monitor', label: '监控', icon: Radio },
  { to: '/schedule', label: '任务', icon: CalendarClock },
  { to: '/settings', label: '设置', icon: Settings }
]

export function Sidebar() {
  return (
    <nav className="flex w-16 shrink-0 flex-col items-center gap-2 border-r border-base-800 bg-base-900/80 py-3">
      {items.map(item => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            title={item.label}
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                isActive ? 'bg-primary text-base-950' : 'text-neutral-400 hover:bg-base-850 hover:text-neutral-100'
              }`
            }
          >
            <Icon size={19} />
          </NavLink>
        )
      })}
    </nav>
  )
}
