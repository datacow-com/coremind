import React, { useState, useEffect } from 'react';
import { apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface Provider {
  id: string;
  name: string;
  category: string;
  base_url?: string;
  is_active: boolean;
}

interface ModelConfig {
  id: string;
  name: string;
  model_id: string;
  type: string;
  is_default: boolean;
}

export function ModelRegistry() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  
  const loadData = async () => {
    const p = await apiFetch('/api/providers');
    const m = await apiFetch('/api/models');
    if (p.ok) setProviders(await p.json());
    if (m.ok) setModels(await m.json());
  };

  useEffect(() => {
    loadData();
  }, []);

  const [newProvider, setNewProvider] = useState({ name: '', category: 'llm', base_url: '', api_key: '' });

  const handleAddProvider = async () => {
    await apiFetch('/api/providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newProvider)
    });
    loadData();
  };

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Provider Registry</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <Input placeholder="Name" value={newProvider.name} onChange={e => setNewProvider({...newProvider, name: e.target.value})} />
            <Input placeholder="Base URL" value={newProvider.base_url} onChange={e => setNewProvider({...newProvider, base_url: e.target.value})} />
            <Input type="password" placeholder="API Key" value={newProvider.api_key} onChange={e => setNewProvider({...newProvider, api_key: e.target.value})} />
            <Button onClick={handleAddProvider}>Add Provider</Button>
          </div>
          
          <div className="border rounded">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-2 text-left">Name</th>
                  <th className="p-2 text-left">Category</th>
                  <th className="p-2 text-left">Base URL</th>
                  <th className="p-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {providers.map(p => (
                  <tr key={p.id} className="border-t">
                    <td className="p-2">{p.name}</td>
                    <td className="p-2">{p.category}</td>
                    <td className="p-2">{p.base_url}</td>
                    <td className="p-2">{p.is_active ? 'Active' : 'Inactive'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model Configurations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border rounded">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-2 text-left">Name</th>
                  <th className="p-2 text-left">Model ID</th>
                  <th className="p-2 text-left">Type</th>
                  <th className="p-2 text-left">Default</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={m.id} className="border-t">
                    <td className="p-2">{m.name}</td>
                    <td className="p-2">{m.model_id}</td>
                    <td className="p-2">{m.type}</td>
                    <td className="p-2">{m.is_default ? 'Yes' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

