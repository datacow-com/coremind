import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  FileText,
  ClipboardList,
  Settings,
  Activity,
  Upload,
  Download,
  Search,
  LayoutTemplate, // New Icon
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { SelectSearch } from "@/components/ui/select-search";
import Button from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { useFormZod } from "@/hooks/useFormZod";
import { z } from "zod";
import { useToast } from "@/components/ui/toast-provider";
import { useDebouncedEffect } from "@/hooks/useDebouncedEffect";
import { StrategyTab } from "@/components/StrategyTab"; // Import new component

const fetch = apiFetch;

// ... (Existing Interfaces and Component Logic) ...

// In KnowledgeBaseDetail component, update the updateKb function to accept strategy config
// The existing updateKb just PATCHes payload. If backend accepts nested strategy_config, we are good.
// We need to ensure backend (server/routes.py update_kb) handles it.
// The legacy backend might store extra keys in config json blob.

const KnowledgeBaseDetail: React.FC = () => {
  // ... (Existing State) ...
  const { name } = useParams();
  const [tab, setTab] = useState<string>("files");
  const [runtime, setRuntime] = useState<any>({});
  const [kbConfig, setKbConfig] = useState<any>({});
  const [effectiveConfig, setEffectiveConfig] = useState<any>({});
  const { push } = useToast();

  // ... (Existing Load Logic) ...
  
  const load = async () => {
    try {
      const r = await fetch(
          `/api/kb/${encodeURIComponent(String(name || ""))}/config`,
      );
      if (r.ok) {
        const d = await r.json();
        setKbConfig(d.config || {});
        setEffectiveConfig(d.effective_config || {});
          // ... populate forms ...
      }
    } catch {}
  };

  useEffect(() => {
    load();
  }, [name]);

  const updateKb = async (payload: any) => {
    try {
    const r = await fetch(
      `/api/kb/${encodeURIComponent(String(name || ""))}/config`,
      {
          method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
      if (r.ok) {
        load(); // Reload to refresh effective config
      } else {
        push({ title: "更新失败", variant: "error" });
      }
    } catch {
      push({ title: "网络错误", variant: "error" });
    }
  };

  return (
    <div className="flex h-full flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center">
            {name}
            <span className="ml-3 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
              {effectiveConfig.stack === "en" ? "English" : "中文"}
            </span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {effectiveConfig.description || "暂无描述"}
          </p>
          </div>
        <div className="flex space-x-2">
           {/* ... Actions ... */}
        </div>
      </div>

      <div className="flex-1 overflow-hidden flex">
        {/* Sidebar */}
        <div className="w-64 bg-white border-r flex flex-col">
          <nav className="flex-1 p-4 space-y-1">
          <button
            onClick={() => setTab("files")}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
                tab === "files"
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
          >
              <FileText className="h-5 w-5" />
              <span>文件管理</span>
          </button>
          <button
              onClick={() => setTab("strategy")}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
                tab === "strategy"
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <LayoutTemplate className="h-5 w-5" />
              <span>策略配置 (V4)</span>
          </button>
          <button
              onClick={() => setTab("retrieval")}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
                tab === "retrieval"
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <Search className="h-5 w-5" />
              <span>检索参数</span>
          </button>
          <button
              onClick={() => setTab("settings")}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium ${
                tab === "settings"
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <Settings className="h-5 w-5" />
              <span>基础设置</span>
          </button>
        </nav>
      </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto p-8">
          {tab === "files" && (
             <div className="text-gray-500">文件列表组件 (Placeholder)</div>
             /* Reuse existing file list logic here */
          )}

          {tab === "strategy" && (
            <div className="max-w-4xl mx-auto">
            <Card>
              <CardHeader>
                  <CardTitle>Ingestion Strategy (V4 Pipeline)</CardTitle>
              </CardHeader>
              <CardContent>
                  <StrategyTab config={kbConfig} onUpdate={updateKb} />
              </CardContent>
            </Card>
          </div>
        )}

          {tab === "retrieval" && (
             /* Reuse existing retrieval form */
             <div className="text-gray-500">检索参数组件 (Placeholder)</div>
          )}

          {tab === "settings" && (
             /* Reuse existing settings form */
             <div className="text-gray-500">基础设置组件 (Placeholder)</div>
                  )}
                </div>
          </div>
    </div>
  );
};

export default KnowledgeBaseDetail;
