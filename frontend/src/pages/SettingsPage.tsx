import { useEffect, useState } from 'react'
import { Settings, Save, Key, Database, Globe } from 'lucide-react'

interface SettingsState {
  llm: {
    provider: string
    model: string
    api_key: string
    temperature: number
    max_tokens: number
  }
  vector_store: {
    host: string
    port: number
    collection_name: string
    embedding_model: string
  }
  web_search: {
    enabled: boolean
    max_results: number
  }
}

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SettingsState>({
    llm: {
      provider: 'gemini',
      model: 'gemini-3',
      api_key: '',
      temperature: 0.7,
      max_tokens: 4096
    },
    vector_store: {
      host: 'localhost',
      port: 19530,
      collection_name: 'omnirag_documents',
      embedding_model: 'sentence-transformers/all-MiniLM-L6-v2'
    },
    web_search: {
      enabled: true,
      max_results: 5
    }
  })

  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [providers, setProviders] = useState<Array<{name: string, model: string, base_url: string}>>([])
  const [validations, setValidations] = useState<Array<{provider: string, required_env: string[], missing_env: string[], configured: boolean}>>([])
  const [groups, setGroups] = useState<{domestic: any[], foreign: any[], local: any[], other: any[]}>({domestic: [], foreign: [], local: [], other: []})
  const [activeTab, setActiveTab] = useState<'domestic'|'foreign'|'local'|'other'>('foreign')
  const [bindings, setBindings] = useState<{parse: string, retrieve: string, chat: string, rerank: string}>({
    parse: 'gemini',
    retrieve: 'embedding',
    chat: 'gemini',
    rerank: 'cross_encoder',
  })

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const token = await fetch('/api/auth/demo', { method: 'POST' })
          .then(r => r.ok ? r.json() : Promise.reject('auth failed'))
          .then(d => d.access_token as string)

        const res = await fetch('/api/models/providers', { headers: { Authorization: `Bearer ${token}` } })
        if (res.ok) {
          const data = await res.json()
          setProviders(data.config?.providers || [])
          setValidations(data.validations || [])
          if (data.config?.bindings) setBindings(data.config.bindings)
        }

        const rg = await fetch('/api/models/providers/groups', { headers: { Authorization: `Bearer ${token}` } })
        if (rg.ok) {
          const gd = await rg.json()
          setGroups(gd.groups || {domestic: [], foreign: [], local: [], other: []})
        }
      } catch (e) {
        // noop
      }
    }
    loadProviders()
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const response = await fetch('/api/models/providers', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bindings,
          providers,
        })
      })

      if (response.ok) {
        setSaveMessage('Settings saved successfully!')
        setTimeout(() => setSaveMessage(''), 3000)
      } else {
        setSaveMessage('Failed to save settings')
        setTimeout(() => setSaveMessage(''), 3000)
      }
    } catch (error) {
      console.error('Error saving settings:', error)
      setSaveMessage('Error saving settings')
      setTimeout(() => setSaveMessage(''), 3000)
    } finally {
      setIsSaving(false)
    }
  }

  const updateLLMSetting = (key: keyof SettingsState['llm'], value: any) => {
    setSettings(prev => ({
      ...prev,
      llm: { ...prev.llm, [key]: value }
    }))
  }

  const updateVectorStoreSetting = (key: keyof SettingsState['vector_store'], value: any) => {
    setSettings(prev => ({
      ...prev,
      vector_store: { ...prev.vector_store, [key]: value }
    }))
  }

  const updateWebSearchSetting = (key: keyof SettingsState['web_search'], value: any) => {
    setSettings(prev => ({
      ...prev,
      web_search: { ...prev.web_search, [key]: value }
    }))
  }

  const testProvider = async (name: string) => {
    try {
      const res = await fetch('/api/models/providers/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      if (res.ok) {
        const data = await res.json()
        const v = data.result
        setValidations(prev => {
          const next = prev.filter(p => p.provider !== name)
          next.push(v)
          return next
        })
        setSaveMessage(v.configured ? `${name} configured` : `Missing env: ${v.missing_env.join(', ')}`)
        setTimeout(() => setSaveMessage(''), 3000)
      }
    } catch (e) {
      setSaveMessage('Test failed')
      setTimeout(() => setSaveMessage(''), 3000)
    }
  }

  const updateBinding = (key: keyof typeof bindings, value: string) => {
    setBindings(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Settings</h2>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Save className="h-4 w-4" />
            <span>{isSaving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {saveMessage && (
          <div className={`mb-4 p-3 rounded-md ${saveMessage.includes('success') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
            {saveMessage}
          </div>
        )}

        {/* LLM Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Key className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">LLM Configuration</h3>
          </div>

          <div className="bg-white border rounded-lg p-6 space-y-4">
            {/* Bindings */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Parse (Vision)</label>
                <select
                  value={bindings.parse}
                  onChange={(e) => updateBinding('parse', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {providers.map(p => (
                    <option key={`parse-${p.name}`} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Chat</label>
                <select
                  value={bindings.chat}
                  onChange={(e) => updateBinding('chat', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {providers.map(p => (
                    <option key={`chat-${p.name}`} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Retrieve</label>
                <select
                  value={bindings.retrieve}
                  onChange={(e) => updateBinding('retrieve', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="embedding">embedding</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Rerank</label>
                <select
                  value={bindings.rerank}
                  onChange={(e) => updateBinding('rerank', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="cross_encoder">cross_encoder</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Provider
                </label>
                <select
                  value={settings.llm.provider}
                  onChange={(e) => updateLLMSetting('provider', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Model
                </label>
                <input
                  type="text"
                  value={settings.llm.model}
                  onChange={(e) => updateLLMSetting('model', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Key
              </label>
              <input
                type="password"
                value={settings.llm.api_key}
                onChange={(e) => updateLLMSetting('api_key', e.target.value)}
                placeholder="Enter your API key"
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Temperature
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={settings.llm.temperature}
                  onChange={(e) => updateLLMSetting('temperature', parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="text-xs text-gray-500 mt-1">
                  {settings.llm.temperature}
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={settings.llm.max_tokens}
                  onChange={(e) => updateLLMSetting('max_tokens', parseInt(e.target.value))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Model Providers */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Settings className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">Model Providers</h3>
          </div>
          <div className="bg-white border rounded-lg p-6">
            <div className="mb-3 space-x-2">
              {(['foreign','domestic','local','other'] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} className={`px-3 py-1 text-xs rounded ${activeTab===tab?'bg-blue-600 text-white':'bg-gray-200 text-gray-800'}`}>{tab}</button>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="px-3 py-2">Provider</th>
                    <th className="px-3 py-2">Model</th>
                    <th className="px-3 py-2">Base URL</th>
                    <th className="px-3 py-2">Configured</th>
                    <th className="px-3 py-2">Missing Env</th>
                    <th className="px-3 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(groups[activeTab] || providers).map((p: any) => {
                    const v = validations.find(x => x.provider === p.name)
                    return (
                      <tr key={p.name} className="border-t">
                        <td className="px-3 py-2 font-medium">{p.name}</td>
                        <td className="px-3 py-2">{p.model}</td>
                        <td className="px-3 py-2 text-gray-600">{p.base_url}</td>
                        <td className="px-3 py-2">{v?.configured ? 'Yes' : 'No'}</td>
                        <td className="px-3 py-2 text-gray-600">{(v?.missing_env || []).join(', ')}</td>
                        <td className="px-3 py-2">
                          <button
                            onClick={() => testProvider(p.name)}
                            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                          >Test</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Vector Store Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Database className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">Vector Store Configuration</h3>
          </div>
          
          <div className="bg-white border rounded-lg p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Host
                </label>
                <input
                  type="text"
                  value={settings.vector_store.host}
                  onChange={(e) => updateVectorStoreSetting('host', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Port
                </label>
                <input
                  type="number"
                  value={settings.vector_store.port}
                  onChange={(e) => updateVectorStoreSetting('port', parseInt(e.target.value))}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Collection Name
              </label>
              <input
                type="text"
                value={settings.vector_store.collection_name}
                onChange={(e) => updateVectorStoreSetting('collection_name', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Embedding Model
              </label>
              <input
                type="text"
                value={settings.vector_store.embedding_model}
                onChange={(e) => updateVectorStoreSetting('embedding_model', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Web Search Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Globe className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">Web Search Configuration</h3>
          </div>
          
          <div className="bg-white border rounded-lg p-6 space-y-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="web-search-enabled"
                checked={settings.web_search.enabled}
                onChange={(e) => updateWebSearchSetting('enabled', e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="web-search-enabled" className="text-sm font-medium text-gray-700">
                Enable Web Search
              </label>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Max Results
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={settings.web_search.max_results}
                onChange={(e) => updateWebSearchSetting('max_results', parseInt(e.target.value))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsPage
