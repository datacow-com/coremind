import { useEffect, useState, useCallback } from "react";
import { apiGet, apiPost, apiDelete, getDemoToken } from "@/lib/api";

type Provider = { id: string; name: string };
type Credential = {
  id: string;
  provider_id: string;
  env: "dev" | "test" | "prod";
  auth_type?: string;
  key_name?: string;
  key_last4?: string;
  rate_limit_rps?: number;
  quota_limit?: number;
  quota_window?: string;
  billing_info?: Record<string, unknown>;
};

export default function Credentials() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [env, setEnv] = useState<"dev" | "test" | "prod">("dev");
  const [list, setList] = useState<Credential[]>([]);
  const [form, setForm] = useState<Partial<Credential>>({
    auth_type: "api_key",
    key_name: "",
    rate_limit_rps: undefined,
    quota_limit: undefined,
    quota_window: "daily",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ensure = useCallback(async () => {
    await getDemoToken();
  }, []);

  const loadProviders = useCallback(async () => {
    await ensure();
    const data = await apiGet<{ models: Provider[] }>(
      "/models?page=1&page_size=200",
    );
    setProviders(data.models || []);
  }, [ensure]);

  const loadList = useCallback(async () => {
    if (!selected) return;
    await ensure();
    const data = await apiGet<Credential[]>(`/models/${selected}/credentials`);
    setList(data || []);
  }, [selected, ensure]);

  async function upsert() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      await ensure();
      await apiPost(`/models/${selected}/credentials/${env}`, form);
      await loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function remove(cred: Credential) {
    setError(null);
    try {
      await ensure();
      await apiDelete(`/models/${cred.provider_id}/credentials/${cred.env}`);
      await loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);
  useEffect(() => {
    loadList();
  }, [loadList]);

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">模型凭据</div>
      <div className="grid grid-cols-3 gap-2">
        <select
          value={selected}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            setSelected(e.target.value)
          }
          className="border p-2"
        >
          <option value="">选择模型</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={env}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            setEnv(e.target.value as "dev" | "test" | "prod")
          }
          className="border p-2"
        >
          <option value="dev">dev</option>
          <option value="test">test</option>
          <option value="prod">prod</option>
        </select>
        <button onClick={loadList} className="border px-4 py-2">
          刷新
        </button>
      </div>
      <div className="border p-3 space-y-2">
        <div className="font-medium">新增/更新</div>
        <div className="grid grid-cols-3 gap-2">
          <select
            value={form.auth_type}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              setForm({ ...form, auth_type: e.target.value })
            }
            className="border p-2"
          >
            <option value="api_key">api_key</option>
            <option value="oauth">oauth</option>
            <option value="none">none</option>
          </select>
          <input
            value={form.key_name || ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setForm({ ...form, key_name: e.target.value })
            }
            placeholder="Key 名称"
            className="border p-2"
          />
          <input
            type="number"
            value={form.rate_limit_rps || 0}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setForm({ ...form, rate_limit_rps: Number(e.target.value) })
            }
            placeholder="RPS 限制"
            className="border p-2"
          />
          <input
            type="number"
            value={form.quota_limit || 0}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setForm({ ...form, quota_limit: Number(e.target.value) })
            }
            placeholder="配额上限"
            className="border p-2"
          />
          <input
            value={form.quota_window || ""}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setForm({ ...form, quota_window: e.target.value })
            }
            placeholder="配额窗口"
            className="border p-2"
          />
        </div>
        <button
          disabled={!selected || loading}
          onClick={upsert}
          className="border px-4 py-2"
        >
          保存
        </button>
        {error && <div className="text-red-600">{error}</div>}
      </div>
      <div className="border p-3">
        <div className="font-medium mb-2">当前凭据</div>
        <table className="w-full border">
          <thead>
            <tr className="bg-gray-50">
              <th className="p-2 border">环境</th>
              <th className="p-2 border">类型</th>
              <th className="p-2 border">名称</th>
              <th className="p-2 border">RPS</th>
              <th className="p-2 border">配额</th>
              <th className="p-2 border">窗口</th>
              <th className="p-2 border">操作</th>
            </tr>
          </thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id}>
                <td className="p-2 border">{c.env}</td>
                <td className="p-2 border">{c.auth_type}</td>
                <td className="p-2 border">{c.key_name}</td>
                <td className="p-2 border">{c.rate_limit_rps ?? ""}</td>
                <td className="p-2 border">{c.quota_limit ?? ""}</td>
                <td className="p-2 border">{c.quota_window ?? ""}</td>
                <td className="p-2 border">
                  <button
                    onClick={() => remove(c)}
                    className="border px-2 py-1"
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
