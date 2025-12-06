import React, { useState, useEffect } from 'react';
import { apiFetch } from '@/lib/api';

export interface StrategyConfigData {
  // ... existing fields ...
  embedding_model: string;
  // ...
}

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  status?: string;
  latency_ms?: number;
}

// ... existing Props ...

export function StrategyConfig({ onSubmit, initialConfig }: Props) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [checking, setChecking] = useState<string | null>(null);
  
  useEffect(() => {
    // Fetch models on mount
    apiFetch('/api/models/embedding').then(async (res) => {
        if (res.ok) {
            const data = await res.json();
            setModels(data);
        }
    });
  }, []);

  const checkModel = async (id: string) => {
      setChecking(id);
      try {
          const res = await apiFetch(`/api/models/embedding/${encodeURIComponent(id)}/check`, { method: 'POST' });
          const data = await res.json();
          setModels(prev => prev.map(m => m.id === id ? { ...m, ...data } : m));
      } catch {
          // ignore
      } finally {
          setChecking(null);
      }
  };

  // ... existing state ...

  return (
    <form onSubmit={handleSubmit} className="space-y-6 p-4 bg-white rounded shadow">
      {/* ... existing fields ... */}

      {/* Embedding Strategy */}
      <div className="space-y-2">
        <label className="block font-medium">Embedding Model</label>
        <div className="flex gap-2">
            <select
            value={config.embedding_model}
            onChange={(e) => setConfig({ ...config, embedding_model: e.target.value })}
            className="flex-1 border rounded p-2"
            >
                <option value="">Custom / Default</option>
                {models.map(m => (
                    <option key={m.id} value={m.id}>
                        {m.name} ({m.provider}) {m.status === 'available' ? `✓ ${m.latency_ms}ms` : ''}
                    </option>
                ))}
            </select>
            {config.embedding_model && (
                <button 
                    type="button"
                    onClick={() => checkModel(config.embedding_model)}
                    className="px-3 border rounded hover:bg-gray-100 text-sm"
                    disabled={!!checking}
                >
                    {checking === config.embedding_model ? 'Checking...' : 'Test'}
                </button>
            )}
        </div>
      </div>

      {/* ... existing fields ... */}
    </form>
  );
}
