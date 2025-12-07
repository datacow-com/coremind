import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

export interface StrategyConfigData {
  ocr_provider?: string;
  ocr_fallback_chain?: string[];
  ocr_concurrency?: number;
  force_ocr?: boolean;
  chunking?: {
    mode?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    preserve_tables?: boolean;
  };
  embedding_model?: string;
  embedding_batch_size?: number;
  vector_backend?: string;
  keyword_backend?: string;
  enable_quantization?: boolean;
  enable_cleaning?: boolean;
  min_quality_score?: number;
  enable_dedup?: boolean;
  enable_pii_filter?: boolean;
  algorithms?: {
    enable_raptor?: boolean;
    raptor_max_cluster?: number;
    enable_graphrag?: boolean;
    graph_community_level?: number;
    enable_mindmap?: boolean;
  };
}

const DEFAULT_STRATEGY: StrategyConfigData = {
  ocr_provider: "auto",
  ocr_fallback_chain: ["qwen-vl", "volc_engine"],
  ocr_concurrency: 5,
  force_ocr: false,
  chunking: {
    mode: "fixed",
    chunk_size: 512,
    chunk_overlap: 50,
    preserve_tables: true,
  },
  embedding_model: "BAAI/bge-m3",
  embedding_batch_size: 64,
  vector_backend: "auto",
  keyword_backend: "elasticsearch",
  enable_quantization: true,
  enable_cleaning: false,
  min_quality_score: 0.5,
  enable_dedup: true,
  enable_pii_filter: false,
  algorithms: {
    enable_raptor: false,
    raptor_max_cluster: 10,
    enable_graphrag: false,
    graph_community_level: 2,
    enable_mindmap: false,
  },
};

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  type?: string;
  status?: string;
  latency_ms?: number;
}

// ... existing Props ...

export function StrategyConfig({ onSubmit, initialConfig }: Props) {
  const [embedModels, setEmbedModels] = useState<ModelOption[]>([]);
  const [ocrModels, setOcrModels] = useState<ModelOption[]>([]);
  const [llmModels, setLlmModels] = useState<ModelOption[]>([]);
  const [rerankModels, setRerankModels] = useState<ModelOption[]>([]);
  const [checking, setChecking] = useState<string | null>(null);

  const mergeWithDefaults = (cfg: StrategyConfigData | undefined) => {
    return {
      ...DEFAULT_STRATEGY,
      ...(cfg || {}),
      chunking: { ...DEFAULT_STRATEGY.chunking, ...(cfg?.chunking || {}) },
      algorithms: { ...DEFAULT_STRATEGY.algorithms, ...(cfg?.algorithms || {}) },
    } as StrategyConfigData;
  };

  const [config, setConfig] = useState<StrategyConfigData>(() =>
    mergeWithDefaults(initialConfig),
  );

  useEffect(() => {
    setConfig(mergeWithDefaults(initialConfig));
  }, [initialConfig]);

  useEffect(() => {
    const fetchModels = async () => {
      const types = [
        { key: "embedding", setter: setEmbedModels },
        { key: "ocr", setter: setOcrModels },
        { key: "llm", setter: setLlmModels },
        { key: "rerank", setter: setRerankModels },
      ];
      for (const t of types) {
        try {
          const res = await apiFetch(`/api/models/${t.key}`);
          if (res.ok) {
            const data = await res.json();
            t.setter(data);
          }
        } catch {
          // ignore
        }
      }
    };
    fetchModels();
  }, []);

  const checkModel = async (id: string, type: string) => {
    setChecking(id);
    try {
      const res = await apiFetch(
        `/api/models/${type}/${encodeURIComponent(id)}/check`,
        { method: "POST" },
      );
      const data = await res.json();
      const setter =
        type === "embedding"
          ? setEmbedModels
          : type === "ocr"
            ? setOcrModels
            : type === "llm"
              ? setLlmModels
              : setRerankModels;
      setter((prev) => prev.map((m) => (m.id === id ? { ...m, ...data } : m)));
    } catch {
      // ignore
    } finally {
      setChecking(null);
    }
  };

  // ... existing state ...

  const applyScenario = (preset: StrategyConfigData) => {
    setConfig((prev) => ({ ...preset, ...prev }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(mergeWithDefaults(config));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 p-4 bg-white rounded shadow">
      {/* 场景预设 */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="px-3 py-1 border rounded text-sm"
          onClick={async () => {
            try {
              const res = await apiFetch("/api/ingest/scenarios");
              if (res.ok) {
                const data = await res.json();
                const first = data?.scenarios?.paper || data?.scenarios?.laws || data?.scenarios?.table;
                if (first) applyScenario(first);
              }
            } catch {}
          }}
        >
          载入预设并应用
        </button>
      </div>

      {/* OCR / Vision */}
      <div className="space-y-3 border p-3 rounded">
        <h3 className="font-medium">OCR / Vision</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-sm">OCR Provider</label>
            <select
              value={config.ocr_provider || "auto"}
              onChange={(e) => setConfig({ ...config, ocr_provider: e.target.value })}
              className="w-full border rounded p-2"
            >
              <option value="auto">Auto</option>
              {ocrModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.provider})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="block text-sm">Fallback Chain (逗号分隔)</label>
            <input
              className="w-full border rounded p-2"
              value={(config.ocr_fallback_chain || []).join(",")}
              onChange={(e) =>
                setConfig({ ...config, ocr_fallback_chain: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
              }
              placeholder="qwen-vl, volc_engine"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-sm">并发</label>
            <input
              type="number"
              className="w-full border rounded p-2"
              value={config.ocr_concurrency ?? 5}
              onChange={(e) => setConfig({ ...config, ocr_concurrency: Number(e.target.value) })}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.force_ocr}
              onChange={(e) => setConfig({ ...config, force_ocr: e.target.checked })}
            />
            <span>强制 OCR</span>
          </div>
        </div>
      </div>

      {/* Chunking */}
      <div className="space-y-3 border p-3 rounded">
        <h3 className="font-medium">Chunking</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-sm">模式</label>
            <select
              value={config.chunking?.mode || "fixed"}
              onChange={(e) =>
                setConfig({
                  ...config,
                  chunking: { ...config.chunking, mode: e.target.value },
                })
              }
              className="w-full border rounded p-2"
            >
              <option value="fixed">Fixed</option>
              <option value="semantic">Semantic</option>
              <option value="layout_aware">Layout Aware</option>
              <option value="table_first">Table First</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="block text-sm">Chunk Size</label>
            <input
              type="number"
              className="w-full border rounded p-2"
              value={config.chunking?.chunk_size ?? 512}
              onChange={(e) =>
                setConfig({
                  ...config,
                  chunking: { ...config.chunking, chunk_size: Number(e.target.value) },
                })
              }
            />
          </div>
          <div className="space-y-1">
            <label className="block text-sm">Overlap</label>
            <input
              type="number"
              className="w-full border rounded p-2"
              value={config.chunking?.chunk_overlap ?? 50}
              onChange={(e) =>
                setConfig({
                  ...config,
                  chunking: { ...config.chunking, chunk_overlap: Number(e.target.value) },
                })
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.chunking?.preserve_tables}
              onChange={(e) =>
                setConfig({
                  ...config,
                  chunking: { ...config.chunking, preserve_tables: e.target.checked },
                })
              }
            />
            <span>表格独立/保留</span>
          </div>
        </div>
      </div>

      {/* 质量与安全 */}
      <div className="space-y-3 border p-3 rounded">
        <h3 className="font-medium">质量与安全</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.enable_cleaning}
              onChange={(e) =>
                setConfig({ ...config, enable_cleaning: e.target.checked })
              }
            />
            <span>启用清洗</span>
          </div>
          <div className="space-y-1">
            <label className="block text-sm">最低质量分</label>
            <input
              type="number"
              step="0.01"
              className="w-full border rounded p-2"
              value={config.min_quality_score ?? 0.5}
              onChange={(e) =>
                setConfig({
                  ...config,
                  min_quality_score: Number(e.target.value),
                })
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.enable_dedup}
              onChange={(e) =>
                setConfig({ ...config, enable_dedup: e.target.checked })
              }
            />
            <span>去重</span>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.enable_pii_filter}
              onChange={(e) =>
                setConfig({ ...config, enable_pii_filter: e.target.checked })
              }
            />
            <span>PII 过滤</span>
          </div>
        </div>
      </div>

      {/* Models & Index */}
      <div className="space-y-3 border p-3 rounded">
        <h3 className="font-medium">Models & Index</h3>
        <div className="space-y-2">
          <label className="block text-sm">Embedding Model</label>
          <div className="flex gap-2">
            <select
              value={config.embedding_model || ""}
              onChange={(e) => setConfig({ ...config, embedding_model: e.target.value })}
              className="flex-1 border rounded p-2"
            >
              <option value="">Default / Custom</option>
              {embedModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.provider}) {m.status === "available" ? `✓ ${m.latency_ms}ms` : ""}
                </option>
              ))}
            </select>
            {config.embedding_model && (
              <button
                type="button"
                onClick={() => checkModel(config.embedding_model!, "embedding")}
                className="px-3 border rounded hover:bg-gray-100 text-sm"
                disabled={!!checking}
              >
                {checking === config.embedding_model ? "Checking..." : "Test"}
              </button>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-sm">Embedding Batch Size</label>
          <input
            type="number"
            className="w-full border rounded p-2"
            value={config.embedding_batch_size ?? 64}
            onChange={(e) => setConfig({ ...config, embedding_batch_size: Number(e.target.value) })}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-sm">向量后端</label>
            <select
              value={config.vector_backend || "qdrant"}
              onChange={(e) => setConfig({ ...config, vector_backend: e.target.value })}
              className="w-full border rounded p-2"
            >
              <option value="qdrant">Qdrant</option>
              <option value="milvus" disabled>
                Milvus (deprecated here)
              </option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="block text-sm">关键词后端</label>
            <select
              value={config.keyword_backend || "elasticsearch"}
              onChange={(e) => setConfig({ ...config, keyword_backend: e.target.value })}
              className="w-full border rounded p-2"
            >
              <option value="elasticsearch">Elasticsearch</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={config.enable_quantization ?? true}
            onChange={(e) => setConfig({ ...config, enable_quantization: e.target.checked })}
          />
          <span>启用量化（节省存储）</span>
        </div>
      </div>

      {/* Quality & Algorithms */}
      <div className="space-y-3 border p-3 rounded">
        <h3 className="font-medium">Quality & Algorithms</h3>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={!!config.enable_cleaning}
            onChange={(e) => setConfig({ ...config, enable_cleaning: e.target.checked })}
          />
          <span>启用清洗</span>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={!!config.enable_dedup}
            onChange={(e) => setConfig({ ...config, enable_dedup: e.target.checked })}
          />
          <span>启用去重</span>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={!!config.enable_pii_filter}
            onChange={(e) => setConfig({ ...config, enable_pii_filter: e.target.checked })}
          />
          <span>启用 PII 过滤</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.algorithms?.enable_raptor}
              onChange={(e) =>
                setConfig({
                  ...config,
                  algorithms: { ...config.algorithms, enable_raptor: e.target.checked },
                })
              }
            />
            Raptor
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.algorithms?.enable_graphrag}
              onChange={(e) =>
                setConfig({
                  ...config,
                  algorithms: { ...config.algorithms, enable_graphrag: e.target.checked },
                })
              }
            />
            GraphRAG
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!config.algorithms?.enable_mindmap}
              onChange={(e) =>
                setConfig({
                  ...config,
                  algorithms: { ...config.algorithms, enable_mindmap: e.target.checked },
                })
              }
            />
            Mindmap
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-sm">Raptor Max Cluster</label>
            <input
              type="number"
              className="w-full border rounded p-2"
              value={config.algorithms?.raptor_max_cluster ?? 10}
              onChange={(e) =>
                setConfig({
                  ...config,
                  algorithms: {
                    ...config.algorithms,
                    raptor_max_cluster: Number(e.target.value),
                  },
                })
              }
            />
          </div>
          <div className="space-y-1">
            <label className="block text-sm">Graph Community Level</label>
            <input
              type="number"
              className="w-full border rounded p-2"
              value={config.algorithms?.graph_community_level ?? 2}
              onChange={(e) =>
                setConfig({
                  ...config,
                  algorithms: {
                    ...config.algorithms,
                    graph_community_level: Number(e.target.value),
                  },
                })
              }
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="px-3 py-2 border rounded"
          onClick={() => setConfig(initialConfig || {})}
        >
          重置
        </button>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          保存策略
        </button>
      </div>
    </form>
  );
}
