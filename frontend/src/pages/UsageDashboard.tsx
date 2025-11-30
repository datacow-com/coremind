import { useEffect, useState } from 'react'

interface UsageDay {
  [providerModel: string]: { calls: number, tokens_in: number, tokens_out: number, duration_ms: number }
}

export default function UsageDashboard() {
  const [usage, setUsage] = useState<Record<string, UsageDay>>({})
  const [thresholds, setThresholds] = useState<{max_tokens_per_day?: number, max_calls_per_day?: number, max_cost_per_day?: number, webhook_url?: string}>({})
  const [msg, setMsg] = useState('')

  const load = async () => {
    try {
      const u = await fetch('/api/metrics/usage').then(r => r.ok ? r.json() : Promise.reject('usage'))
      setUsage(u.usage || {})
    } catch {}
    try {
      const t = await fetch('/api/alerts/thresholds').then(r => r.ok ? r.json() : Promise.reject('thresholds'))
      setThresholds((t.thresholds || {}))
    } catch {}
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    setMsg('')
    try {
      const res = await fetch('/api/alerts/thresholds', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(thresholds) })
      if (res.ok) {
        setMsg('Saved')
        await load()
      } else {
        setMsg('Failed')
      }
    } catch { setMsg('Failed') }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Usage Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="text-xl font-semibold mb-2">Daily Usage</h2>
          {Object.keys(usage).length === 0 && <p className="text-sm text-gray-500">No data</p>}
          {Object.entries(usage).map(([day, detail]) => (
            <div key={day} className="mb-4">
              <div className="font-medium">{day}</div>
              <table className="w-full text-sm mt-2">
                <thead>
                  <tr className="text-left border-b"><th className="py-1">Provider:Model</th><th className="py-1">Calls</th><th className="py-1">Tokens In</th><th className="py-1">Tokens Out</th><th className="py-1">Duration (ms)</th></tr>
                </thead>
                <tbody>
                  {Object.entries(detail as UsageDay).map(([pm, v]) => (
                    <tr key={pm} className="border-b">
                      <td className="py-1">{pm}</td>
                      <td className="py-1">{v.calls}</td>
                      <td className="py-1">{v.tokens_in}</td>
                      <td className="py-1">{v.tokens_out}</td>
                      <td className="py-1">{v.duration_ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
        <div>
          <h2 className="text-xl font-semibold mb-2">Thresholds</h2>
          <div className="space-y-2">
            <div>
              <label className="block text-sm">Max Tokens / Day</label>
              <input className="border rounded px-2 py-1 w-full" type="number" value={thresholds.max_tokens_per_day ?? ''} onChange={e => setThresholds({...thresholds, max_tokens_per_day: Number(e.target.value)})} />
            </div>
            <div>
              <label className="block text-sm">Max Calls / Day</label>
              <input className="border rounded px-2 py-1 w-full" type="number" value={thresholds.max_calls_per_day ?? ''} onChange={e => setThresholds({...thresholds, max_calls_per_day: Number(e.target.value)})} />
            </div>
            <div>
              <label className="block text-sm">Max Cost / Day</label>
              <input className="border rounded px-2 py-1 w-full" type="number" step="0.000001" value={thresholds.max_cost_per_day ?? ''} onChange={e => setThresholds({...thresholds, max_cost_per_day: Number(e.target.value)})} />
            </div>
            <div>
              <label className="block text-sm">Webhook URL</label>
              <input className="border rounded px-2 py-1 w-full" type="text" value={thresholds.webhook_url ?? ''} onChange={e => setThresholds({...thresholds, webhook_url: e.target.value})} />
            </div>
            <button className="bg-blue-600 text-white px-3 py-1 rounded" onClick={save}>Save</button>
            {msg && <div className="text-sm text-gray-600">{msg}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}

