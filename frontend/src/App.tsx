import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppStateProvider } from './appState'
import { Layout } from './components/Layout'
import { AIPage } from './pages/AIPage'
import { MonitorPage } from './pages/MonitorPage'
import { PoolPage } from './pages/PoolPage'
import { ReviewPage } from './pages/ReviewPage'
import { SchedulePage } from './pages/SchedulePage'
import { SettingsPage } from './pages/SettingsPage'
import { StrategyPage } from './pages/StrategyPage'

export default function App() {
  return (
    <BrowserRouter>
      <AppStateProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<AIPage />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="review/:symbol" element={<ReviewPage />} />
            <Route path="strategy" element={<StrategyPage />} />
            <Route path="strategy/:id" element={<StrategyPage />} />
            <Route path="pool" element={<PoolPage />} />
            <Route path="monitor" element={<MonitorPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </AppStateProvider>
    </BrowserRouter>
  )
}
