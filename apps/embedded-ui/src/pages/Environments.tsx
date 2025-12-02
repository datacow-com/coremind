import { useEffect, useState, useCallback } from "react";
import { apiGet, apiPost, getDemoToken } from "@/lib/api";

type Env = { name: string; description?: string; is_production: boolean };
type EnvVersion = {
  id: string;
  name: string;
  version: number;
  config: Record<string, unknown>;
  created_at: string;
  created_by?: string;
};

export default function Environments() {
  const [envs, setEnvs] = useState<Env[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [versions, setVersions] = useState<EnvVersion[]>([]);
  const [preview, setPreview] = useState<unknown | null>(null);
  const [configText, setConfigText] = useState<string>(
    '{\\n  \\"llm\\": { \\"default\\": \\"gpt-4o-mini\\" }\\n}',
  );
  const [error, setError] = useState<string | null>(null);

  const ensure = useCallback(async () => {
    await getDemoToken();
  }, []);

  const loadEnvs = useCallback(async () => {
    await ensure();
    const data = await apiGet<Env[]>("/models/environments");
    setEnvs(data || []);
  }, [ensure]);

  const loadVersions = useCallback(async () => {
    if (!selected) return;
    await ensure();
    const data = await apiGet<EnvVersion[]>(
      `/models/environments/${selected}/versions`,
    );
    setVersions(data || []);
  }, [selected, ensure]);

  async function createVersion() {
    setError(null);
    try {
      await ensure();
      let cfg: Record<string, unknown> = {};
      try {
        cfg = JSON.parse(configText) as Record<string, unknown>;
      } catch {
        setError("JSON 解析失败");
        return;
      }
      await apiPost(`/models/environments/${selected}/versions`, {
        config: cfg,
      });
      await loadVersions();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function rollback(version: number) {
    setError(null);
    try {
      await ensure();
      await apiPost(
        `/models/environments/${selected}/versions/${version}/rollback`,
        {},
      );
      await loadVersions();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function previewApply(version: number) {
    setError(null);
    try {
      await ensure();
      const data = await apiPost<{ preview?: unknown }>(
        `/models/environments/${selected}/versions/${version}/apply?dry_run=true`,
        {},
      );
      setPreview(data.preview ?? data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function confirmApply(version: number) {
    setError(null);
    try {
      await ensure();
      await apiPost(
        `/models/environments/${selected}/versions/${version}/apply?dry_run=false`,
        {},
      );
      setPreview(null);
      await loadVersions();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    loadEnvs();
  }, [loadEnvs]);
  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">环境版本管理</div>
      <div className="grid grid-cols-3 gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="border p-2"
        >
          <option value="">选择环境</option>
          {envs.map((e) => (
            <option key={e.name} value={e.name}>
              {e.name}
            </option>
          ))}
        </select>
        <button onClick={loadVersions} className="border px-4 py-2">
          刷新版本
        </button>
      </div>
      {error && <div className="text-red-600">{error}</div>}
      <div className="grid grid-cols-2 gap-4">
        <div className="border p-3">
          <div className="font-medium mb-2">版本列表</div>
          <table className="w-full border">
            <thead>
              <tr className="bg-gray-50">
                <th className="p-2 border">版本</th>
                <th className="p-2 border">创建人</th>
                <th className="p-2 border">时间</th>
                <th className="p-2 border">操作</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.id}>
                  <td className="p-2 border">{v.version}</td>
                  <td className="p-2 border">{v.created_by || ""}</td>
                  <td className="p-2 border">
                    {new Date(v.created_at).toLocaleString()}
                  </td>
                  <td className="p-2 border flex gap-2">
                    <button
                      onClick={() => previewApply(v.version)}
                      className="border px-2 py-1"
                    >
                      预览应用
                    </button>
                    <button
                      onClick={() => confirmApply(v.version)}
                      className="border px-2 py-1"
                    >
                      确认应用
                    </button>
                    <button
                      onClick={() => rollback(v.version)}
                      className="border px-2 py-1"
                    >
                      回滚
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border p-3">
          <div className="font-medium mb-2">创建新版本</div>
          <textarea
            className="border w-full h-48 p-2"
            value={configText}
            onChange={(e) => setConfigText(e.target.value)}
          />
          <button
            disabled={!selected}
            onClick={createVersion}
            className="border px-4 py-2 mt-2"
          >
            保存版本
          </button>
          {preview && (
            <div className="mt-3 border p-2">
              <div className="font-medium">预览差异</div>
              <pre className="text-xs whitespace-pre-wrap">
                {JSON.stringify(preview, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
