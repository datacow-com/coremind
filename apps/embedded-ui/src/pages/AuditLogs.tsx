import { useEffect, useState, useCallback } from "react";
import { apiGet, getDemoToken } from "@/lib/api";

type AuditLog = {
  id: number;
  actor_id?: string;
  actor_name?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  diff?: string | Record<string, unknown> | null;
  created_at: string;
};

type Resp = {
  logs: AuditLog[];
  total: number;
  page: number;
  page_size: number;
};

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await getDemoToken();
      const data = await apiGet<Resp>(
        `/models/audit/logs?page=${page}&page_size=${pageSize}`,
      );
      setLogs(data.logs || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">审计日志</div>
      {error && <div className="text-red-600">{error}</div>}
      {loading ? (
        <div>加载中...</div>
      ) : (
        <table className="w-full border">
          <thead>
            <tr className="bg-gray-50">
              <th className="p-2 border">时间</th>
              <th className="p-2 border">用户</th>
              <th className="p-2 border">动作</th>
              <th className="p-2 border">资源</th>
              <th className="p-2 border">详情</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="p-2 border">
                  {new Date(l.created_at).toLocaleString()}
                </td>
                <td className="p-2 border">
                  {l.actor_name || l.actor_id || ""}
                </td>
                <td className="p-2 border">{l.action}</td>
                <td className="p-2 border">{l.resource_type}</td>
                <td className="p-2 border truncate max-w-[300px]">
                  {typeof l.diff === "string"
                    ? l.diff
                    : JSON.stringify(l.diff || {})}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setPage(Math.max(1, page - 1))}
          className="border px-3 py-1"
        >
          上一页
        </button>
        <div>{page}</div>
        <button onClick={() => setPage(page + 1)} className="border px-3 py-1">
          下一页
        </button>
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          className="border p-2"
        >
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
        </select>
      </div>
    </div>
  );
}
