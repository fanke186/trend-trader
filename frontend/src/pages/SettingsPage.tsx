import { useEffect, useState } from 'react'
import { fetchConfig, fetchModelProfiles, fetchProviders, fetchTradingStatus, reloadConfig, testModelProfile } from '../api'
import type { ModelProfile, ModelProvider, TradingStatus } from '../types'

export function SettingsPage() {
  const [providers, setProviders] = useState<ModelProvider[]>([])
  const [profiles, setProfiles] = useState<ModelProfile[]>([])
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [trading, setTrading] = useState<TradingStatus | null>(null)
  const [message, setMessage] = useState('')

  async function refresh() {
    const [providerRows, profileRows, configView, tradingView] = await Promise.all([fetchProviders(), fetchModelProfiles(), fetchConfig(), fetchTradingStatus()])
    setProviders(providerRows)
    setProfiles(profileRows)
    setConfig(configView.config)
    setTrading(tradingView)
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function testProfile(id: number) {
    setMessage(JSON.stringify(await testModelProfile(id), null, 2))
  }

  async function reload() {
    const result = await reloadConfig()
    setConfig(result.config)
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="rounded-md border border-base-800 bg-base-900 p-3">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">配置</h3>
          <button className="rounded-md border border-base-800 bg-base-850 px-2 py-1 text-xs" onClick={() => void reload()}>
            Reload
          </button>
        </div>
        <pre className="max-h-96 overflow-auto text-xs text-neutral-400">{JSON.stringify(config, null, 2)}</pre>
      </section>
      <section className="rounded-md border border-base-800 bg-base-900 p-3">
        <h3 className="font-semibold">交易状态</h3>
        <pre className="mt-3 max-h-64 overflow-auto text-xs text-neutral-400">{JSON.stringify(trading, null, 2)}</pre>
      </section>
      <section className="rounded-md border border-base-800 bg-base-900 p-3 xl:col-span-2">
        <h3 className="font-semibold">模型配置</h3>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {profiles.map(profile => {
            const provider = providers.find(item => item.id === profile.provider_id)
            return (
              <div key={profile.id} className="rounded-md border border-base-800 bg-base-850 p-3">
                <div className="font-mono text-sm text-primary">{profile.name}</div>
                <div className="mt-1 text-xs text-neutral-500">{provider?.name} · {profile.model}</div>
                <button className="mt-3 rounded-md border border-base-800 px-2 py-1 text-xs hover:border-primary/50" onClick={() => void testProfile(profile.id)}>
                  测试
                </button>
              </div>
            )
          })}
        </div>
        {message && <pre className="mt-3 max-h-60 overflow-auto rounded-md bg-base-850 p-3 text-xs">{message}</pre>}
      </section>
    </div>
  )
}
