import React, { useEffect, useState } from 'react'

type Health = {
  app_up: boolean
  milvus_connected: boolean
  postgres_connected: boolean
}

type ProviderValidation = {
  provider: string
  required_env: string[]
  missing_env: string[]
  configured: boolean
}

export default function SystemStatusPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [validations, setValidations] = useState<ProviderValidation[]>([])
  const [token, setToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch('/api/health')
        if (r.ok) setHealth(await r.json())
      } catch (e) {
        setError('Health fetch failed')
      }
    }
    load()
  }, [])

  const demoLogin = async () => {
    try {
      const r = await fetch('/api/auth/demo', { method: 'POST' })
      if (r.ok) {
        const data = await r.json()
        setToken(data.access_token)
      }
    } catch (e) {
      setError('Demo login failed')
    }
  }

  const fetchProviders = async () => {
    if (!token) {
      setError('Token required, please Demo Login')
      return
    }
    try {
      const r = await fetch('/api/models/providers', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (r.ok) {
        const data = await r.json()
        setValidations(data.validations || [])
        setError(null)
      } else {
        setError('Fetch providers failed')
      }
    } catch (e) {
      setError('Fetch providers failed')
    }
  }

  const Badge = ({ ok, label }: { ok: boolean; label: string }) => (
    <span className={`px-2 py-1 rounded text-xs ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{label}: {ok ? 'OK' : 'DOWN'}</span>
  )

  return (
    <div className="p-6">
      <h2 className="text-xl font-semibold mb-4">System Status</h2>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <div className="bg-white border rounded p-4 mb-6">
        <h3 className="text-md font-medium mb-2">Health</h3>
        {health ? (
          <div className="space-x-2">
            <Badge ok={health.app_up} label="App" />
            <Badge ok={health.milvus_connected} label="Milvus" />
            <Badge ok={health.postgres_connected} label="Postgres" />
          </div>
        ) : (
          <div className="text-gray-600 text-sm">Loading health...</div>
        )}
      </div>

      <div className="bg-white border rounded p-4">
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-md font-medium">Model Providers</h3>
          <div className="space-x-2">
            <button onClick={demoLogin} className="px-3 py-1 text-xs bg-gray-200 rounded hover:bg-gray-300">Demo Login</button>
            <button onClick={fetchProviders} className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Fetch Providers</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="px-3 py-2">Provider</th>
                <th className="px-3 py-2">Configured</th>
                <th className="px-3 py-2">Missing Env</th>
              </tr>
            </thead>
            <tbody>
              {validations.map((v) => (
                <tr key={v.provider} className="border-t">
                  <td className="px-3 py-2 font-medium">{v.provider}</td>
                  <td className="px-3 py-2">{v.configured ? 'Yes' : 'No'}</td>
                  <td className="px-3 py-2 text-gray-600">{(v.missing_env || []).join(', ')}</td>
                </tr>
              ))}
              {validations.length === 0 && (
                <tr><td className="px-3 py-2 text-gray-500" colSpan={3}>No data. Demo Login then Fetch Providers.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

