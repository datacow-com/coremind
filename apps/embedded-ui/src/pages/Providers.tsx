import { useEffect, useMemo, useState, useCallback } from "react";
import { apiGet, apiPost, apiDelete, getDemoToken } from "@/lib/api";

type Provider = {
  id: string;
  name: string;
  stack: "cn" | "overseas";
  category: "llm" | "embedding" | "reranker";
  endpoint: string;
  status: "active" | "inactive" | "testing";
  priority: number;
  created_at: string;
  updated_at: string;
};

type ListResp = {
  models: Provider[];
  total: number;
  page: number;
  page_size: number;
};

export default function Providers() {
  const [items, setItems] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stack, setStack] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const qs = useMemo(() => {
    const params = new URLSearchParams();
    if (stack) params.set("stack", stack);
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    return `?${params.toString()}`;
  }, [stack, category, status, search, page, pageSize]);

  async function ensureToken() {
    await getDemoToken();
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await ensureToken();
      const data = await apiGet<ListResp>(`/models${qs}`);
      setItems(data.models || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [qs]);

  useEffect(() => {
    load();
  }, [load]);

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    stack: "cn",
    category: "llm",
    endpoint: "",
    priority: 1,
  });

  async function create() {
    setCreating(true);
    setError(null);
    try {
      await ensureToken();
      await apiPost<Provider>("/models/", form);
      setForm({ name: "", stack: "cn", category: "llm", endpoint: "", priority: 1 });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await ensureToken();
      await apiDelete(`/models/${id}`);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">模型提供商</div>
      <div className="grid grid-cols-5 gap-2">
        <select value={stack} onChange={(e) => setStack(e.target.value)} className="border p-2">
          <option value="">全部栈</option>
          <option value="cn">国内</option>
          <option value="overseas">海外</option>
          
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="border p-2">
          <option value="">全部类型</option>
          <option value="llm">LLM</option>
          <option value="embedding">Embedding</option>
          <option value="reranker">Reranker</option>
          
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border p-2">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">停用</option>
        </select>
        <input value={search} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)} placeholder="搜索名称或地址" className="border p-2" />
        <button onClick={load} className="border p-2">刷新</button>
      </div>
      <div className="grid grid-cols-4 gap-2">
        <input type="number" value={page} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPage(Number(e.target.value) || 1)} className="border p-2" placeholder="页码" />
        <input type="number" value={pageSize} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPageSize(Number(e.target.value) || 20)} className="border p-2" placeholder="每页" />
        <div></div>
        <div></div>
      </div>
      <div className="border p-3 space-y-2">
        <div className="font-medium">新增提供商</div>
        <div className="grid grid-cols-3 gap-2">
          <input value={form.name} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, name: e.target.value })} placeholder="标识名称" className="border p-2" />
          
          <input value={form.endpoint} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, endpoint: e.target.value })} placeholder="接口地址" className="border p-2" />
          <select value={form.stack} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setForm({ ...form, stack: e.target.value as ("cn" | "overseas") })} className="border p-2">
            <option value="cn">国内</option>
            <option value="overseas">海外</option>
          </select>
          <select value={form.category} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setForm({ ...form, category: e.target.value as ("llm" | "embedding" | "reranker") })} className="border p-2">
            <option value="llm">LLM</option>
            <option value="embedding">Embedding</option>
            <option value="reranker">Reranker</option>
          </select>
          <input type="number" value={form.priority} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, priority: Number(e.target.value) })} placeholder="优先级" className="border p-2" />
        </div>
        <button disabled={creating} onClick={create} className="border px-4 py-2">创建</button>
      </div>
      {error && <div className="text-red-600">{error}</div>}
      {loading ? (
        <div>加载中...</div>
      ) : (
        <table className="w-full border">
          <thead>
            <tr className="bg-gray-50">
              <th className="p-2 border">名称</th>
              <th className="p-2 border">显示名</th>
              <th className="p-2 border">栈</th>
              <th className="p-2 border">类型</th>
              <th className="p-2 border">地址</th>
              <th className="p-2 border">状态</th>
              <th className="p-2 border">优先级</th>
              <th className="p-2 border">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td className="p-2 border">{p.name}</td>
                
                <td className="p-2 border">{p.stack}</td>
                <td className="p-2 border">{p.category}</td>
                <td className="p-2 border truncate max-w-[240px]">{p.endpoint}</td>
                <td className="p-2 border">{p.status}</td>
                <td className="p-2 border">{p.priority}</td>
                <td className="p-2 border">
                  <button onClick={() => remove(p.id)} className="border px-2 py-1">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
