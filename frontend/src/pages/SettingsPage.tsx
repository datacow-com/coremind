import { useEffect, useState } from "react";
import {
  Settings,
  Save,
  Key,
  Database,
  Globe,
  AlertCircle,
} from "lucide-react";
import { z } from "zod";
import { useFormZod } from "@/hooks/useFormZod";
import { useToast } from "@/components/ui/toast-provider";
import { EmptyState } from "@/components/ui/empty";
import { AlertCard } from "@/components/ui/alert-card";
import { apiFetch } from "@/lib/api";

const fetch = apiFetch;

interface SettingsState {
  llm: {
    provider: string;
    model: string;
    api_key: string;
    temperature: number;
    max_tokens: number;
  };
  vector_store: {
    host: string;
    port: number;
    collection_name: string;
    embedding_model: string;
  };
  web_search: {
    enabled: boolean;
    max_results: number;
  };
}

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SettingsState>({
    llm: {
      provider: "gemini",
      model: "gemini-3",
      api_key: "",
      temperature: 0.7,
      max_tokens: 4096,
    },
    vector_store: {
      host: "localhost",
      port: 19530,
      collection_name: "omnirag_documents",
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    web_search: {
      enabled: true,
      max_results: 5,
    },
  });

  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [providers, setProviders] = useState<
    Array<{ name: string; model: string; base_url: string }>
  >([]);
  const [validations, setValidations] = useState<
    Array<{
      provider: string;
      required_env: string[];
      missing_env: string[];
      configured: boolean;
    }>
  >([]);
  const [groups, setGroups] = useState<{
    domestic: any[];
    foreign: any[];
    local: any[];
    other: any[];
  }>({ domestic: [], foreign: [], local: [], other: [] });
  const [activeTab, setActiveTab] = useState<
    "domestic" | "foreign" | "local" | "other"
  >("foreign");
  const [bindings, setBindings] = useState<{
    parse: string;
    retrieve: string;
    chat: string;
    rerank: string;
  }>({
    parse: "dashscope",
    retrieve: "embedding",
    chat: "gemini",
    rerank: "cross_encoder",
  });
  const [vectorWeight, setVectorWeight] = useState<number>(0.6);
  const [keywordWeight, setKeywordWeight] = useState<number>(0.4);
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(true);
  const [defaultTopK, setDefaultTopK] = useState<number>(5);
  const [candidateK, setCandidateK] = useState<number>(50);
  const [rateLimitEnabled, setRateLimitEnabled] = useState<boolean>(false);
  const [rateLimitPerMinute, setRateLimitPerMinute] = useState<number>(60);
  const [heartbeatInterval, setHeartbeatInterval] = useState<number>(0);
  const [collections, setCollections] = useState<
    Array<{
      name: string;
      document_count: number;
      chunk_count: number;
      embedding_dimension: number;
      distance_metric: string;
    }>
  >([]);
  const [runtime, setRuntime] = useState<Record<string, any>>({});
  const [runtimeMetrics, setRuntimeMetrics] = useState<Record<string, any>>({});
  const [usageSummary, setUsageSummary] = useState<
    Record<string, { calls: number; tokens: number; duration_ms: number }>
  >({});
  const [webProvidersStatus, setWebProvidersStatus] = useState<{
    current_provider: string;
    providers: Record<string, { configured: boolean }>;
  } | null>(null);
  const { push } = useToast();

  const runtimeSchema = z.object({
    vector_weight: z.number().min(0).max(1),
    keyword_weight: z.number().min(0).max(1),
    top_k_default: z.number().int().min(1).max(50),
    candidate_k: z.number().int().min(1).max(500),
    web_search_enabled: z.boolean(),
    rate_limit_enabled: z.boolean(),
    rate_limit_per_minute: z.number().int().min(1).max(600),
    sse_heartbeat_interval: z.number().int().min(0).max(120),
  });

  const runtimeForm = useFormZod(
    runtimeSchema,
    {
      vector_weight: 0.6,
      keyword_weight: 0.4,
      top_k_default: 5,
      candidate_k: 50,
      web_search_enabled: true,
      rate_limit_enabled: false,
      rate_limit_per_minute: 60,
      sse_heartbeat_interval: 0,
    },
    async () => {
      // defer actual apply to explicit button
    },
  );

  const fetchRuntime = async () => {
    try {
      const r = await fetch("/api/config/runtime");
      if (r.ok) {
        const d = await r.json();
        setRuntime(d);
        runtimeForm.setValues({
          vector_weight: d.vector_weight ?? runtimeForm.values.vector_weight,
          keyword_weight: d.keyword_weight ?? runtimeForm.values.keyword_weight,
          top_k_default: d.top_k_default ?? runtimeForm.values.top_k_default,
          candidate_k: d.candidate_k ?? runtimeForm.values.candidate_k,
          web_search_enabled:
            d.web_search_enabled ?? runtimeForm.values.web_search_enabled,
          rate_limit_enabled:
            d.rate_limit_enabled ?? runtimeForm.values.rate_limit_enabled,
          rate_limit_per_minute:
            d.rate_limit_per_minute ?? runtimeForm.values.rate_limit_per_minute,
          sse_heartbeat_interval:
            d.sse_heartbeat_interval ??
            runtimeForm.values.sse_heartbeat_interval,
        });
        setDefaultTopK(d.top_k_default ?? 5);
        setCandidateK(d.candidate_k ?? 50);
        setRateLimitEnabled(d.rate_limit_enabled ?? false);
        setRateLimitPerMinute(d.rate_limit_per_minute ?? 60);
        setHeartbeatInterval(d.sse_heartbeat_interval ?? 0);
      }
    } catch {}

    try {
      const r2 = await fetch("/api/metrics/runtime");
      if (r2.ok) {
        const d2 = await r2.json();
        setRuntimeMetrics(d2.data || d2 || {});
      }
    } catch {}
  };

  const fetchWebProviders = async () => {
    try {
      const r = await fetch("/api/web/providers/status");
      if (r.ok) setWebProvidersStatus(await r.json());
    } catch {}
  };

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const res = await fetch("/api/models/providers");
        if (res.ok) {
          const data = await res.json();
          setProviders(data.config?.providers || []);
          setValidations(data.validations || []);
          if (data.config?.bindings) setBindings(data.config.bindings);
          const s = data.config?.settings;
          if (s) {
            runtimeForm.setValues((prev) => ({
              ...prev,
              vector_weight: s.vector_weight ?? prev.vector_weight,
              keyword_weight: s.keyword_weight ?? prev.keyword_weight,
              web_search_enabled:
                s.web_search_enabled ?? prev.web_search_enabled,
            }));
            setVectorWeight(s.vector_weight ?? 0.6);
            setKeywordWeight(s.keyword_weight ?? 0.4);
            setWebSearchEnabled(s.web_search_enabled ?? true);
          }
        }

        const rg = await fetch("/api/models/providers/groups");
        if (rg.ok) {
          const gd = await rg.json();
          setGroups(
            gd.groups || { domestic: [], foreign: [], local: [], other: [] },
          );
        }

        const vc = await fetch("/api/vector-store/collections");
        if (vc.ok) {
          const cd = await vc.json();
          setCollections(cd.collections || []);
        }
      } catch (e) {
        // noop
      }
    };
    loadProviders();
    fetchRuntime();
    const loadUsage = async () => {
      try {
        const r = await fetch("/api/metrics/usage");
        if (r.ok) {
          const d = await r.json();
          setUsageSummary(d.summary || {});
        }
      } catch {}
    };
    loadUsage();
    fetchWebProviders();
  }, []);

  const runtimeCards = [
    {
      title: "SSE",
      value: runtimeMetrics.sse_active ?? "-",
      desc: `active / max ${runtimeMetrics.sse_max_connections ?? "-"}`,
    },
    {
      title: "上传",
      value: runtimeMetrics.uploads?.ok ?? "-",
      desc: `拒绝 ${runtimeMetrics.uploads?.rejected ?? 0} / 扫描失败 ${runtimeMetrics.uploads?.scan_fail ?? 0}`,
    },
    {
      title: "限流",
      value: runtimeMetrics.rate_limit_enabled ? "启用" : "关闭",
      desc: `backend ${runtimeMetrics.rate_limit_backend || "memory"}`,
    },
    {
      title: "Web 搜索",
      value: runtimeMetrics.web_search?.enabled ? "启用" : "关闭",
      desc: runtimeMetrics.web_search?.provider || "未配置",
    },
  ];

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await fetch("/api/models/providers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          bindings,
          providers,
          settings: {
            vector_weight: runtimeForm.values.vector_weight,
            keyword_weight: runtimeForm.values.keyword_weight,
            web_search_enabled: runtimeForm.values.web_search_enabled,
          },
        }),
      });

      if (response.ok) {
        setSaveMessage("Settings saved successfully!");
        push({ title: "已保存", variant: "success" });
        try {
          window.dispatchEvent(
            new CustomEvent("settings:update", {
              detail: {
                vector_weight: runtimeForm.values.vector_weight,
                keyword_weight: runtimeForm.values.keyword_weight,
                web_search_enabled: runtimeForm.values.web_search_enabled,
              },
            }),
          );
        } catch {}
        setTimeout(() => setSaveMessage(""), 3000);
      } else {
        setSaveMessage("Failed to save settings");
        push({
          title: "保存失败",
          description: response.statusText,
          variant: "error",
        });
        setTimeout(() => setSaveMessage(""), 3000);
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      setSaveMessage("Error saving settings");
      push({ title: "保存失败", description: "网络错误", variant: "error" });
      setTimeout(() => setSaveMessage(""), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  const applyRuntime = async () => {
    try {
      const res = await fetch("/api/system/settings/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_temperature: settings.llm.temperature,
          vector_weight: runtimeForm.values.vector_weight,
          keyword_weight: runtimeForm.values.keyword_weight,
          top_k_default: runtimeForm.values.top_k_default,
          candidate_k: runtimeForm.values.candidate_k,
          rate_limit_enabled: runtimeForm.values.rate_limit_enabled,
          rate_limit_per_minute: runtimeForm.values.rate_limit_per_minute,
          sse_heartbeat_interval: runtimeForm.values.sse_heartbeat_interval,
        }),
      });
      if (res.ok) {
        try {
          window.dispatchEvent(
            new CustomEvent("settings:update", {
              detail: {
                vector_weight: runtimeForm.values.vector_weight,
                keyword_weight: runtimeForm.values.keyword_weight,
              },
            }),
          );
        } catch {}
        setSaveMessage("Runtime applied");
        push({ title: "运行时已应用", variant: "success" });
        await fetchRuntime();
        await fetchWebProviders();
        setTimeout(() => setSaveMessage(""), 2000);
      } else {
        setSaveMessage("Runtime apply failed");
        push({
          title: "运行时应用失败",
          description: res.statusText,
          variant: "error",
        });
        setTimeout(() => setSaveMessage(""), 2000);
      }
    } catch {
      setSaveMessage("Runtime apply failed");
      push({
        title: "运行时应用失败",
        description: "网络错误",
        variant: "error",
      });
      setTimeout(() => setSaveMessage(""), 2000);
    }
  };

  const updateLLMSetting = (key: keyof SettingsState["llm"], value: any) => {
    setSettings((prev) => ({
      ...prev,
      llm: { ...prev.llm, [key]: value },
    }));
  };

  const updateVectorStoreSetting = (
    key: keyof SettingsState["vector_store"],
    value: any,
  ) => {
    setSettings((prev) => ({
      ...prev,
      vector_store: { ...prev.vector_store, [key]: value },
    }));
  };

  const updateWebSearchSetting = (
    key: keyof SettingsState["web_search"],
    value: any,
  ) => {
    setSettings((prev) => ({
      ...prev,
      web_search: { ...prev.web_search, [key]: value },
    }));
  };

  const testProvider = async (name: string) => {
    try {
      const res = await fetch("/api/models/providers/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.ok) {
        const data = await res.json();
        const v = data.result;
        setValidations((prev) => {
          const next = prev.filter((p) => p.provider !== name);
          next.push(v);
          return next;
        });
        setSaveMessage(
          v.configured
            ? `${name} configured`
            : `Missing env: ${v.missing_env.join(", ")}`,
        );
        setTimeout(() => setSaveMessage(""), 3000);
      }
    } catch (e) {
      setSaveMessage("Test failed");
      setTimeout(() => setSaveMessage(""), 3000);
    }
  };

  const updateBinding = (key: keyof typeof bindings, value: string) => {
    setBindings((prev) => ({ ...prev, [key]: value }));
  };

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
            <span>{isSaving ? "Saving..." : "Save Settings"}</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {saveMessage && (
          <div
            className={`mb-4 p-3 rounded-md ${saveMessage.includes("success") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}
          >
            {saveMessage}
          </div>
        )}

        {/* LLM Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Key className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">
              LLM Configuration
            </h3>
          </div>

          <div className="bg-white border rounded-lg p-6 space-y-4">
            {/* Bindings */}
            {providers.length === 0 ? (
              <EmptyState
                title="暂无可用 Provider"
                description="请先配置模型提供方后再选择绑定。"
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Parse (Vision)
                  </label>
                  <select
                    value={bindings.parse}
                    onChange={(e) => updateBinding("parse", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {providers.map((p) => (
                      <option key={`parse-${p.name}`} value={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Chat
                  </label>
                  <select
                    value={bindings.chat}
                    onChange={(e) => updateBinding("chat", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {providers.map((p) => (
                      <option key={`chat-${p.name}`} value={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Retrieve
                  </label>
                  <select
                    value={bindings.retrieve}
                    onChange={(e) => updateBinding("retrieve", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="embedding">embedding</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Rerank
                  </label>
                  <select
                    value={bindings.rerank}
                    onChange={(e) => updateBinding("rerank", e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="cross_encoder">cross_encoder</option>
                  </select>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Provider
                </label>
                <select
                  value={settings.llm.provider}
                  onChange={(e) => updateLLMSetting("provider", e.target.value)}
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
                  onChange={(e) => updateLLMSetting("model", e.target.value)}
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
                onChange={(e) => updateLLMSetting("api_key", e.target.value)}
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
                  onChange={(e) =>
                    updateLLMSetting("temperature", parseFloat(e.target.value))
                  }
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
                  onChange={(e) =>
                    updateLLMSetting("max_tokens", parseInt(e.target.value))
                  }
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {Object.keys(runtime).length > 0 && (
                <div className="mt-4 text-xs text-gray-600">
                  <div>
                    Runtime: provider {runtime.llm_provider} · vision{" "}
                    {runtime.vision_provider} · web{" "}
                    {runtime.web_search_provider}
                  </div>
                  <div>
                    Temp {runtime.chat_temperature} · top_k{" "}
                    {runtime.top_k_default} · rrf_k {runtime.rrf_k}
                  </div>
                  <div>
                    Uploads {runtime.uploads_dir} · Usage {runtime.usage_dir} ·
                    Milvus {runtime.milvus_uri} · Web timeout{" "}
                    {runtime.web_search_timeout}
                  </div>
                  {Object.keys(usageSummary).length > 0 &&
                    (() => {
                      const days = Object.keys(usageSummary).sort();
                      const today = days[days.length - 1];
                      const s = usageSummary[today];
                      return s ? (
                        <div>
                          Today: calls {s.calls} · tokens {s.tokens} · duration{" "}
                          {s.duration_ms} ms
                        </div>
                      ) : null;
                    })()}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Retrieval Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Database className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">
              Retrieval Settings
            </h3>
          </div>
          <div className="bg-white border rounded-lg p-6 space-y-4">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Vector Weight</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={runtimeForm.values.vector_weight}
                  onChange={(e) => {
                    const v = Math.max(
                      0,
                      Math.min(1, parseFloat(e.target.value || "0.6")),
                    );
                    runtimeForm.setField("vector_weight", v);
                    setVectorWeight(v);
                  }}
                  className="w-20 border rounded px-2 py-1"
                />
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Keyword Weight</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={runtimeForm.values.keyword_weight}
                  onChange={(e) => {
                    const v = Math.max(
                      0,
                      Math.min(1, parseFloat(e.target.value || "0.4")),
                    );
                    runtimeForm.setField("keyword_weight", v);
                    setKeywordWeight(v);
                  }}
                  className="w-20 border rounded px-2 py-1"
                />
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Default Top-K</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={runtimeForm.values.top_k_default}
                  onChange={(e) => {
                    const v = Math.max(
                      1,
                      Math.min(10, parseInt(e.target.value || "5")),
                    );
                    runtimeForm.setField("top_k_default", v);
                    setDefaultTopK(v);
                  }}
                  className="w-20 border rounded px-2 py-1"
                />
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Web Search</label>
                <input
                  type="checkbox"
                  checked={runtimeForm.values.web_search_enabled}
                  onChange={(e) => {
                    runtimeForm.setField(
                      "web_search_enabled",
                      e.target.checked,
                    );
                    setWebSearchEnabled(e.target.checked);
                  }}
                />
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Rate Limit</label>
                <input
                  type="checkbox"
                  checked={runtimeForm.values.rate_limit_enabled}
                  onChange={(e) => {
                    runtimeForm.setField(
                      "rate_limit_enabled",
                      e.target.checked,
                    );
                    setRateLimitEnabled(e.target.checked);
                  }}
                />
                <input
                  type="number"
                  min={1}
                  max={600}
                  value={runtimeForm.values.rate_limit_per_minute}
                  onChange={(e) => {
                    const v = Math.max(
                      1,
                      Math.min(600, parseInt(e.target.value || "60")),
                    );
                    runtimeForm.setField("rate_limit_per_minute", v);
                    setRateLimitPerMinute(v);
                  }}
                  className="w-24 border rounded px-2 py-1"
                />
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Heartbeat (s)</label>
                <input
                  type="number"
                  min={0}
                  max={120}
                  value={runtimeForm.values.sse_heartbeat_interval}
                  onChange={(e) => {
                    const v = Math.max(
                      0,
                      Math.min(120, parseInt(e.target.value || "0")),
                    );
                    runtimeForm.setField("sse_heartbeat_interval", v);
                    setHeartbeatInterval(v);
                  }}
                  className="w-24 border rounded px-2 py-1"
                />
              </div>
            </div>
            <p className="text-xs text-gray-500">
              这些设置将作为默认值用于聊天检索流程，可在聊天页覆盖。
            </p>
            <div>
              <button
                onClick={applyRuntime}
                className="mt-2 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
              >
                Apply Runtime
              </button>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <label className="text-sm text-gray-700">Candidate-K</label>
            <input
              type="number"
              min={10}
              max={200}
              value={runtimeForm.values.candidate_k}
              onChange={(e) => {
                const v = Math.max(
                  10,
                  Math.min(200, parseInt(e.target.value || "50")),
                );
                runtimeForm.setField("candidate_k", v);
                setCandidateK(v);
              }}
              className="w-24 border rounded px-2 py-1"
            />
          </div>
        </div>

        {/* Runtime Metrics */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Activity className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">运行态仪表</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {runtimeCards.map((c) => (
              <div key={c.title} className="bg-white border rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-1">{c.title}</div>
                <div className="text-lg font-semibold text-gray-900">
                  {c.value}
                </div>
                <div className="text-xs text-gray-500">{c.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Model Providers */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Settings className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">
              Model Providers
            </h3>
          </div>
          <div className="bg-white border rounded-lg p-6">
            <div className="mb-3 space-x-2">
              {(["foreign", "domestic", "local", "other"] as const).map(
                (tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1 text-xs rounded ${activeTab === tab ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-800"}`}
                  >
                    {tab}
                  </button>
                ),
              )}
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
                    const v = validations.find((x) => x.provider === p.name);
                    return (
                      <tr key={p.name} className="border-t">
                        <td className="px-3 py-2 font-medium">{p.name}</td>
                        <td className="px-3 py-2">{p.model}</td>
                        <td className="px-3 py-2 text-gray-600">
                          {p.base_url}
                        </td>
                        <td className="px-3 py-2">
                          {v?.configured ? "Yes" : "No"}
                        </td>
                        <td className="px-3 py-2 text-gray-600">
                          {(v?.missing_env || []).join(", ")}
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={() => testProvider(p.name)}
                            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                          >
                            Test
                          </button>
                        </td>
                      </tr>
                    );
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
            <h3 className="text-md font-medium text-gray-900">
              Vector Store Configuration
            </h3>
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
                  onChange={(e) =>
                    updateVectorStoreSetting("host", e.target.value)
                  }
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
                  onChange={(e) =>
                    updateVectorStoreSetting("port", parseInt(e.target.value))
                  }
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
                onChange={(e) =>
                  updateVectorStoreSetting("collection_name", e.target.value)
                }
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
                onChange={(e) =>
                  updateVectorStoreSetting("embedding_model", e.target.value)
                }
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mt-4">
            <div className="text-sm font-medium text-gray-900 mb-2">
              Collections
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Chunks</th>
                    <th className="px-3 py-2">Dim</th>
                    <th className="px-3 py-2">Metric</th>
                  </tr>
                </thead>
                <tbody>
                  {collections.map((c) => (
                    <tr key={c.name} className="border-t">
                      <td className="px-3 py-2 font-medium">{c.name}</td>
                      <td className="px-3 py-2">{c.chunk_count}</td>
                      <td className="px-3 py-2">{c.embedding_dimension}</td>
                      <td className="px-3 py-2">{c.distance_metric}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Web Search Settings */}
        <div className="mb-8">
          <div className="flex items-center space-x-2 mb-4">
            <Globe className="h-5 w-5 text-blue-600" />
            <h3 className="text-md font-medium text-gray-900">
              Web Search Configuration
            </h3>
          </div>

          <div className="bg-white border rounded-lg p-6 space-y-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="web-search-enabled"
                checked={settings.web_search.enabled}
                onChange={(e) =>
                  updateWebSearchSetting("enabled", e.target.checked)
                }
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label
                htmlFor="web-search-enabled"
                className="text-sm font-medium text-gray-700"
              >
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
                onChange={(e) =>
                  updateWebSearchSetting(
                    "max_results",
                    parseInt(e.target.value),
                  )
                }
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {webProvidersStatus && (
              <div className="text-xs text-gray-600">
                <div className="mb-1">
                  Current Provider:{" "}
                  <span className="font-medium">
                    {webProvidersStatus.current_provider}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(webProvidersStatus.providers).map((name) => (
                    <span
                      key={name}
                      className={`px-2 py-1 rounded ${webProvidersStatus.providers[name].configured ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
