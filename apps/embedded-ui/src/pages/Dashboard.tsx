import { useEffect, useState, useCallback } from "react";
import { apiGet, getDemoToken } from "@/lib/api";

type Stats = {
  total_models: number;
  active_models: number;
  cn_models: number;
  overseas_models: number;
  avg_ttft: number;
  avg_throughput: number;
  avg_error_rate: number;
};

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await getDemoToken();
      const data = await apiGet<Stats>("/models/dashboard/stats");
      setStats(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">监控仪表盘</div>
      {error && <div className="text-red-600">{error}</div>}
      {loading ? (
        <div>加载中...</div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          <div className="border p-4">
            <div className="text-gray-600">模型总数</div>
            <div className="text-3xl">{stats?.total_models ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">启用模型</div>
            <div className="text-3xl">{stats?.active_models ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">国内模型</div>
            <div className="text-3xl">{stats?.cn_models ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">海外模型</div>
            <div className="text-3xl">{stats?.overseas_models ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">平均 TTFT(s)</div>
            <div className="text-3xl">{stats?.avg_ttft ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">平均吞吐(tps)</div>
            <div className="text-3xl">{stats?.avg_throughput ?? 0}</div>
          </div>
          <div className="border p-4">
            <div className="text-gray-600">平均错误率</div>
            <div className="text-3xl">{stats?.avg_error_rate ?? 0}</div>
          </div>
        </div>
      )}
    </div>
  );
}
