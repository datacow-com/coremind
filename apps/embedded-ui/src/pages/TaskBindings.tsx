import { useEffect, useState, useCallback } from "react";
import { apiGet, apiPost, getDemoToken } from "@/lib/api";

type BindingCreate = {
  task_id: string;
  task_name: string;
  model_id: string;
  priority: number;
  fallback_config?: Record<string, unknown>;
  environment: "dev" | "test" | "prod";
};

type BindingView = {
  id: string;
  task_id: string;
  task_name: string;
  model_id: string;
  priority: number;
  environment: string;
  model: { id: string; name: string };
};

type Provider = { id: string; name: string };

export default function TaskBindings() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [form, setForm] = useState<BindingCreate>({
    task_id: "chat",
    task_name: "chat-default",
    model_id: "",
    priority: 1,
    fallback_config: {},
    environment: "dev",
  });
  const [queryTask, setQueryTask] = useState("chat-default");
  const [queryEnv, setQueryEnv] = useState("dev");
  const [bindings, setBindings] = useState<BindingView[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    try {
      await getDemoToken();
      const data = await apiGet<{ models: Provider[] }>(
        "/models?page=1&page_size=200",
      );
      setProviders(data.models || []);
    } catch {
      /* noop */
    }
  }, []);

  async function create() {
    setError(null);
    try {
      await getDemoToken();
      await apiPost("/models/bindings", form);
      await query();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const query = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await getDemoToken();
      const data = await apiGet<BindingView[]>(
        `/models/bindings/${encodeURIComponent(queryTask)}/${queryEnv}`,
      );
      setBindings(data || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [queryTask, queryEnv]);

  useEffect(() => {
    loadProviders();
    query();
  }, [loadProviders, query]);

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">任务绑定</div>
      <div className="border p-3 space-y-2">
        <div className="font-medium">创建绑定</div>
        <div className="grid grid-cols-3 gap-2">
          <input
            value={form.task_id}
            onChange={(e) => setForm({ ...form, task_id: e.target.value })}
            placeholder="任务ID"
            className="border p-2"
          />
          <input
            value={form.task_name}
            onChange={(e) => setForm({ ...form, task_name: e.target.value })}
            placeholder="任务名"
            className="border p-2"
          />
          <select
            value={form.environment}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              setForm({
                ...form,
                environment: e.target.value as "dev" | "test" | "prod",
              })
            }
            className="border p-2"
          >
            <option value="dev">dev</option>
            <option value="test">test</option>
            <option value="prod">prod</option>
          </select>
          <select
            value={form.model_id}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            className="border p-2"
          >
            <option value="">选择模型</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            type="number"
            value={form.priority}
            onChange={(e) =>
              setForm({ ...form, priority: Number(e.target.value) })
            }
            placeholder="优先级"
            className="border p-2"
          />
        </div>
        <button onClick={create} className="border px-4 py-2">
          创建
        </button>
      </div>

      <div className="border p-3 space-y-2">
        <div className="font-medium">查询绑定</div>
        <div className="grid grid-cols-3 gap-2">
          <input
            value={queryTask}
            onChange={(e) => setQueryTask(e.target.value)}
            placeholder="任务名"
            className="border p-2"
          />
          <select
            value={queryEnv}
            onChange={(e) => setQueryEnv(e.target.value)}
            className="border p-2"
          >
            <option value="dev">dev</option>
            <option value="test">test</option>
            <option value="prod">prod</option>
          </select>
          <button onClick={query} className="border px-4 py-2">
            查询
          </button>
        </div>
        {error && <div className="text-red-600">{error}</div>}
        {loading ? (
          <div>加载中...</div>
        ) : (
          <table className="w-full border">
            <thead>
              <tr className="bg-gray-50">
                <th className="p-2 border">任务ID</th>
                <th className="p-2 border">任务名</th>
                <th className="p-2 border">环境</th>
                <th className="p-2 border">模型</th>
                <th className="p-2 border">优先级</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((b) => (
                <tr key={b.id}>
                  <td className="p-2 border">{b.task_id}</td>
                  <td className="p-2 border">{b.task_name}</td>
                  <td className="p-2 border">{b.environment}</td>
                  <td className="p-2 border">{b.model?.name}</td>
                  <td className="p-2 border">{b.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
