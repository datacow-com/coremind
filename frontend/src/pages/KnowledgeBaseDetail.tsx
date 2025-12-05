import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  FileText,
  ClipboardList,
  Settings,
  Activity,
  Upload,
  Trash2,
  Download,
  Search,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { SelectSearch } from "@/components/ui/select-search";
import Button from "@/components/ui/button";

interface UsageAgg {
  day: string;
  calls: number;
  tokens: number;
  duration_ms: number;
}

interface DocItem {
  id: string;
  filename: string;
  processing_status: string;
  processed_pages: number;
  total_pages: number;
}

const KnowledgeBaseDetail: React.FC = () => {
  const { name } = useParams();
  const [tab, setTab] = useState<string>("files");
  const [runtime, setRuntime] = useState<any>({});
  const [kbConfig, setKbConfig] = useState<any>({});
  const [webProviders, setWebProviders] = useState<string[]>([]);
  const [newSource, setNewSource] = useState<{
    type: string;
    endpoint?: string;
    token?: string;
  }>({ type: "" });
  const [agg, setAgg] = useState<UsageAgg[]>([]);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState<number>(5);
  const [results, setResults] = useState<any[]>([]);
  const [docs, setDocs] = useState<DocItem[]>([]);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [embedModels, setEmbedModels] = useState<
    { label: string; value: string }[]
  >([]);

  const ingestMode = kbConfig.ingestion_pipeline?.mode || "builtin";

  const loadRuntime = async () => {
    try {
      const r = await fetch("/api/config/runtime");
      if (r.ok) setRuntime(await r.json());
    } catch {}
  };

  const loadUsage = async () => {
    try {
      const r = await fetch("/api/metrics/usage");
      if (r.ok) {
        const d = await r.json();
        const summary = d.summary || {};
        const arr: UsageAgg[] = Object.keys(summary).map((day) => ({
          day,
          calls: Math.round((summary[day].calls || 0) * 100) / 100,
          tokens: Math.round((summary[day].tokens || 0) * 100) / 100,
          duration_ms: Math.round((summary[day].duration_ms || 0) * 100) / 100,
        }));
        setAgg(arr.sort((a, b) => a.day.localeCompare(b.day)));
      }
    } catch {}
  };

  const loadDocs = async () => {
    try {
      const r = await fetch("/api/documents");
      if (r.ok) {
        const d = await r.json();
        setDocs(d.documents || []);
      }
    } catch {}
  };

  useEffect(() => {
    loadRuntime();
    loadUsage();
    loadDocs();
    (async () => {
      try {
        const r = await fetch(
          `/api/kb/${encodeURIComponent(String(name || ""))}/config`,
        );
        if (r.ok) {
          const d = await r.json();
          setKbConfig(d.config || {});
        }
      } catch {}
      try {
        const r2 = await fetch("/api/web/providers/status");
        if (r2.ok) {
          const d2 = await r2.json();
          const p = d2.providers || {};
          setWebProviders(Object.keys(p));
        }
      } catch {}
      try {
        const r3 = await fetch("/api/embedding/models");
        if (r3.ok) {
          const d3 = await r3.json();
          const arr = (d3.models || []).map((m: string) => ({
            label: m,
            value: m,
          }));
          setEmbedModels(arr);
        }
      } catch {}
    })();
  }, [name]);

  const updateKb = async (payload: any) => {
    try {
      const r = await fetch(
        `/api/kb/${encodeURIComponent(String(name || ""))}/config`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (r.ok) {
        const d = await r.json();
        setKbConfig(d.config || {});
      }
    } catch {}
  };

  const testSearch = async () => {
    try {
      const r = await fetch("/api/vector-store/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          top_k: topK,
          kb_name: String(name || ""),
        }),
      });
      if (r.ok) {
        const d = await r.json();
        setResults(d.results || []);
      }
    } catch {}
  };

  const uploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch("/api/documents/upload", {
        method: "POST",
        body: form,
      });
      if (r.ok) await loadDocs();
    } catch {
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  const removeDoc = async (docId: string) => {
    try {
      const r = await fetch(`/api/documents/${docId}`, { method: "DELETE" });
      if (r.ok) await loadDocs();
    } catch {}
  };

  const docsFiltered = docs.filter((d) =>
    (d.filename || "").toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="flex h-full">
      <div className="w-64 bg-white border-r">
        <div className="p-4">
          <div className="w-12 h-12 bg-blue-600 text-white rounded flex items-center justify-center text-lg">
            {String(name || "KB")
              .slice(0, 1)
              .toUpperCase()}
          </div>
          <div className="mt-3 font-medium">{name}</div>
          <div className="text-xs text-gray-500">独立配置与管理</div>
        </div>
        <nav className="mt-2 space-y-1">
          <button
            className={`w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-muted text-muted-foreground ${tab === "files" ? "text-foreground font-medium border-l-2 border-primary" : ""}`}
            onClick={() => setTab("files")}
          >
            <FileText className="h-4 w-4 mr-2" /> 文件列表
          </button>
          <button
            className={`w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-muted text-muted-foreground ${tab === "test" ? "text-foreground font-medium border-l-2 border-primary" : ""}`}
            onClick={() => setTab("test")}
          >
            <ClipboardList className="h-4 w-4 mr-2" /> 检索测试
          </button>
          <button
            className={`w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-muted text-muted-foreground ${tab === "logs" ? "text-foreground font-medium border-l-2 border-primary" : ""}`}
            onClick={() => setTab("logs")}
          >
            <Activity className="h-4 w-4 mr-2" /> 日志
          </button>
          <button
            className={`w-full flex items-center px-3 py-2 text-sm rounded-md hover:bg-muted text-muted-foreground ${tab === "config" ? "text-foreground font-medium border-l-2 border-primary" : ""}`}
            onClick={() => setTab("config")}
          >
            <Settings className="h-4 w-4 mr-2" /> 配置
          </button>
        </nav>
      </div>

      <div className="flex-1">
        {tab === "config" && (
          <div className="max-w-screen-lg mx-auto p-6 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>基础信息</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4">
                <div>
                  <Label requiredMark>名称</Label>
                  <Input value={String(name || "")} readOnly />
                </div>
                <div>
                  <Label>描述</Label>
                  <Input
                    value={kbConfig.description || ""}
                    onChange={(e) => updateKb({ description: e.target.value })}
                  />
                </div>
                <div>
                  <Label>标签</Label>
                  <Input
                    value={(kbConfig.tags || []).join(", ")}
                    onChange={(e) =>
                      updateKb({
                        tags: e.target.value.split(/\s*,\s*/).filter(Boolean),
                      })
                    }
                  />
                </div>
                <div>
                  <Label>可见性</Label>
                  <Select
                    value={kbConfig.visibility || "private"}
                    onChange={(e) => updateKb({ visibility: e.target.value })}
                  >
                    <option value="private">仅自己</option>
                    <option value="org">组织可见</option>
                    <option value="public">公开</option>
                  </Select>
                </div>
                <div>
                  <Label requiredMark>嵌入模型</Label>
                  <SelectSearch
                    options={embedModels}
                    value={kbConfig.embedding_model || ""}
                    onChange={(v) => updateKb({ embedding_model: v })}
                    placeholder="搜索模型..."
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>检索参数</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <Label>语言栈</Label>
                    <Select
                      value={kbConfig.stack || "cn"}
                      onChange={(e) => updateKb({ stack: e.target.value })}
                    >
                      <option value="cn">中文</option>
                      <option value="en">英文</option>
                    </Select>
                  </div>
                  <div>
                    <Label>Top K（库级）</Label>
                    <Input
                      type="number"
                      value={kbConfig.top_k_default ?? 5}
                      onChange={(e) =>
                        updateKb({
                          top_k_default: parseInt(e.target.value || "5"),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Candidate K（库级）</Label>
                    <Input
                      type="number"
                      value={kbConfig.candidate_k ?? 50}
                      onChange={(e) =>
                        updateKb({
                          candidate_k: parseInt(e.target.value || "50"),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>向量权重（库级）</Label>
                    <Input
                      type="number"
                      step={0.1}
                      min={0}
                      max={1}
                      value={kbConfig.vector_weight ?? 0.6}
                      onChange={(e) =>
                        updateKb({
                          vector_weight: parseFloat(e.target.value || "0.6"),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>关键词权重（库级）</Label>
                    <Input
                      type="number"
                      step={0.1}
                      min={0}
                      max={1}
                      value={kbConfig.keyword_weight ?? 0.4}
                      onChange={(e) =>
                        updateKb({
                          keyword_weight: parseFloat(e.target.value || "0.4"),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Reranker 阈值（库级）</Label>
                    <Input
                      type="number"
                      step={0.05}
                      value={kbConfig.reranker_filter_threshold ?? 0.2}
                      onChange={(e) =>
                        updateKb({
                          reranker_filter_threshold: parseFloat(
                            e.target.value || "0.2",
                          ),
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>RRF K</Label>
                    <Input
                      type="number"
                      value={kbConfig.rrf_k ?? runtime.rrf_k ?? 60}
                      onChange={(e) =>
                        updateKb({ rrf_k: parseInt(e.target.value || "60") })
                      }
                    />
                  </div>
                </div>
                <Separator />
                <div className="grid grid-cols-1 gap-4">
                  <div className="flex items-center space-x-3">
                    <Label>启用网页检索</Label>
                    <Switch
                      checked={!!kbConfig.web_search_enabled}
                      onChange={(e) =>
                        updateKb({
                          web_search_enabled: !!(e.target as HTMLInputElement)
                            .checked,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>网页检索提供方</Label>
                    <Select
                      value={
                        kbConfig.web_search_provider ||
                        runtime.web_search_provider ||
                        "duckduckgo"
                      }
                      onChange={(e) =>
                        updateKb({ web_search_provider: e.target.value })
                      }
                    >
                      {webProviders.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>全局索引</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <Label>提取知识图谱</Label>
                    <Input value={kbConfig.global_index?.status || "未生成"} readOnly />
                  </div>
                  <div>
                    <Label requiredMark>实体类型</Label>
                    <div className="flex flex-wrap gap-2">
                      {(["organization","person","geo","event","category"] as const).map((et) => {
                        const list = kbConfig.global_index?.entity_types || [];
                        const active = list.includes(et);
                        return (
                          <button
                            key={et}
                            className={`px-2 py-1 rounded-md text-sm ${active ? "bg-primary text-primary-foreground" : "border border-border text-muted-foreground"}`}
                            onClick={() => {
                              const next = active ? list.filter((x)=> x!==et) : [...list, et];
                              updateKb({ global_index: { ...(kbConfig.global_index||{}), entity_types: next } });
                            }}
                          >
                            {et}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <Label>方法</Label>
                    <Select
                      value={kbConfig.global_index?.method || "Light"}
                      onChange={(e)=> updateKb({ global_index: { ...(kbConfig.global_index||{}), method: e.target.value } })}
                    >
                      <option value="Light">Light</option>
                      <option value="Standard">Standard</option>
                    </Select>
                  </div>
                  <div className="flex items-center space-x-3">
                    <Label>实体归一化</Label>
                    <Switch
                      checked={!!kbConfig.global_index?.entity_normalize}
                      onChange={(e)=> updateKb({ global_index: { ...(kbConfig.global_index||{}), entity_normalize: !!(e.target as HTMLInputElement).checked } })}
                    />
                  </div>
                  <div className="flex items-center space-x-3">
                    <Label>社区报告生成</Label>
                    <Switch
                      checked={!!kbConfig.global_index?.community_report}
                      onChange={(e)=> updateKb({ global_index: { ...(kbConfig.global_index||{}), community_report: !!(e.target as HTMLInputElement).checked } })}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Ingestion pipeline（内置）</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <Label>内置模板</Label>
                    <Select
                      value={kbConfig.ingestion_pipeline?.template || "naive"}
                      onChange={(e) => {
                        const t = e.target.value;
                        const useLayout = ["naive","manual","paper","book","laws","presentation"].includes(t);
                        const useYolo = t === "picture";
                        const useVlm = useLayout || useYolo;
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            template: t,
                            layoutlm_enabled: useLayout,
                            yolo_enabled: useYolo,
                            vlm_enabled: useVlm,
                          },
                        });
                      }}
                    >
                      {["naive","qa","manual","table","paper","book","laws","presentation","picture","resume","one","tag","audio","email","knowledge_graph"].map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </Select>
                    <div className="text-xs text-muted-foreground mt-1">
                      {(() => {
                        const tpl = kbConfig.ingestion_pipeline?.template || "naive";
                        const hint: Record<string,string> = {
                          naive: "通用解析，结合解析器；默认可能启用 LayoutLM",
                          qa: "问答优化，无强制视觉组件",
                          manual: "默认启用 LayoutLM（版面理解）",
                          table: "表格处理，视情况启用表格转 HTML",
                          paper: "默认启用 LayoutLM（提升公式/表格/段落识别）",
                          book: "默认启用 LayoutLM（长文档）",
                          laws: "默认启用 LayoutLM（法条格式）",
                          presentation: "默认启用 LayoutLM（版面/条目识别）",
                          picture: "默认启用 YOLO（版面目标检测）",
                          resume: "简历解析，可配关键词/问题提取",
                          one: "单页文档解析",
                          tag: "标签抽取",
                          audio: "语音转文本后解析",
                          email: "邮件解析",
                          knowledge_graph: "结构化实体关系提取",
                        };
                        return hint[tpl];
                      })()}
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <Label>语义分块</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.semantic_chunking}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            semantic_chunking: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>

                  {(["naive","manual","paper","book","laws","presentation"].includes(kbConfig.ingestion_pipeline?.template || "naive")) && (
                  <div>
                    <Label>PDF 解析器</Label>
                    <Select
                      value={kbConfig.ingestion_pipeline?.pdf_parser || "DeepDOC"}
                      onChange={(e)=> updateKb({ ingestion_pipeline: { ...(kbConfig.ingestion_pipeline||{}), pdf_parser: e.target.value } })}
                    >
                      {["DeepDOC","PyMuPDF","PDFMiner","Unstructured"].map((p)=> (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </Select>
                    <div className="text-xs text-muted-foreground mt-1">模板需要版面解析时显示 PDF 解析器选择</div>
                  </div>
                  )}

                  <div className="flex items-center space-x-3">
                    <Label>解析去噪</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.parser_denoise}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            parser_denoise: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>

                  <div>
                    <Label>建议文本块大小</Label>
                    <Input
                      type="number"
                      value={kbConfig.ingestion_pipeline?.chunk_size ?? 512}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            chunk_size: parseInt(e.target.value || "512"),
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>文本分段标识符</Label>
                    <Input
                      value={kbConfig.ingestion_pipeline?.split_separator ?? "\n"}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            split_separator: e.target.value,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center space-x-3">
                    <Label>TOC Enhance</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.toc_enhance}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            toc_enhance: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center space-x-3">
                    <Label>自动关键词提取</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.auto_keywords}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            auto_keywords: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center space-x-3">
                    <Label>自动问题提取</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.auto_questions}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            auto_questions: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  {((kbConfig.ingestion_pipeline?.template || "naive") === "table") && (
                  <div className="flex items-center space-x-3">
                    <Label>表格转HTML</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.table_to_html}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            table_to_html: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  )}

                  <div className="flex items-center space-x-3">
                    <Label>启用多模态</Label>
                    <Switch
                      checked={!!kbConfig.ingestion_pipeline?.vlm_enabled}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            vlm_enabled: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>

                  <div>
                    <Label>视觉提供方</Label>
                    <Select
                      value={kbConfig.ingestion_pipeline?.vision_provider || runtime.vision_provider || "dashscope"}
                      disabled={!kbConfig.ingestion_pipeline?.vlm_enabled}
                      onChange={(e) =>
                        updateKb({
                          ingestion_pipeline: {
                            ...(kbConfig.ingestion_pipeline || {}),
                            vision_provider: e.target.value,
                          },
                        })
                      }
                    >
                      {["dashscope","openai","gemini","ark","ollama"].map((v)=>(
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </Select>
                    <div className="text-xs text-muted-foreground mt-1">选择用于视觉理解的提供方（VLM）</div>
                  </div>

                  <div className="rounded-md border border-border p-3 space-y-1">
                    <div className="text-xs text-muted-foreground">
                      默认视觉能力：
                      {kbConfig.ingestion_pipeline?.layoutlm_enabled ? "LayoutLM已启用；" : ""}
                      {kbConfig.ingestion_pipeline?.yolo_enabled ? "YOLO已启用；" : ""}
                      {!(kbConfig.ingestion_pipeline?.layoutlm_enabled || kbConfig.ingestion_pipeline?.yolo_enabled) ? "未启用视觉模块（基于模板）" : ""}
                    </div>
                  </div>

                  {/* 当前系统不支持用户自定义 pipeline，已移除该配置 */}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>知识图谱</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <div className="flex items-center space-x-3">
                    <Label>启用</Label>
                    <Switch
                      checked={!!kbConfig.knowledge_graph?.enabled}
                      onChange={(e) =>
                        updateKb({
                          knowledge_graph: {
                            ...(kbConfig.knowledge_graph || {}),
                            enabled: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>状态</Label>
                    <Input
                      value={kbConfig.knowledge_graph?.status || "idle"}
                      readOnly
                    />
                  </div>
                </div>
                <div>
                  <Button size="sm" onClick={async () => {
                      await fetch(
                        `/api/kb/${encodeURIComponent(String(name || ""))}/graph/build`,
                        { method: "POST" },
                      );
                      const r = await fetch(
                        `/api/kb/${encodeURIComponent(String(name || ""))}/graph/status`,
                      );
                      if (r.ok) {
                        const d = await r.json();
                        setKbConfig((prev: any) => ({
                          ...prev,
                          knowledge_graph: {
                            ...(prev.knowledge_graph || {}),
                            status: d.status,
                          },
                        }));
                      }
                    }}>构建知识图谱</Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>RAPTOR 策略</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <div className="flex items-center space-x-3">
                    <Label>启用</Label>
                    <Switch
                      checked={!!kbConfig.raptor?.enabled}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            enabled: !!(e.target as HTMLInputElement).checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>生成范围</Label>
                    <Select
                      value={kbConfig.raptor?.scope || "whole"}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            scope: e.target.value,
                          },
                        })
                      }
                    >
                      <option value="whole">整库</option>
                      <option value="file">单文件</option>
                    </Select>
                  </div>
                  <div className="md:col-span-2">
                    <Label>提示词</Label>
                    <textarea
                      className="w-full border rounded px-3 py-2 text-sm"
                      rows={4}
                      value={kbConfig.raptor?.prompt || ""}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            prompt: e.target.value,
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>最大 token 数</Label>
                    <Input
                      type="number"
                      value={kbConfig.raptor?.max_tokens ?? 256}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            max_tokens: parseInt(e.target.value || "256"),
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>阈值</Label>
                    <Input
                      type="number"
                      step={0.01}
                      value={kbConfig.raptor?.threshold ?? 0.1}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            threshold: parseFloat(e.target.value || "0.1"),
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>最大簇数</Label>
                    <Input
                      type="number"
                      value={kbConfig.raptor?.max_clusters ?? 64}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            max_clusters: parseInt(e.target.value || "64"),
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>随机种子</Label>
                    <Input
                      type="number"
                      value={kbConfig.raptor?.seed ?? 0}
                      onChange={(e) =>
                        updateKb({
                          raptor: {
                            ...(kbConfig.raptor || {}),
                            seed: parseInt(e.target.value || "0"),
                          },
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>状态</Label>
                    <Input value={kbConfig.raptor?.status || "idle"} readOnly />
                  </div>
                </div>
                <div>
                  <Button size="sm" onClick={async () => {
                      await fetch(
                        `/api/kb/${encodeURIComponent(String(name || ""))}/raptor/generate`,
                        {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            scope: kbConfig.raptor?.scope || "whole",
                            prompt: kbConfig.raptor?.prompt || "",
                            max_tokens: kbConfig.raptor?.max_tokens ?? 256,
                            threshold: kbConfig.raptor?.threshold ?? 0.1,
                            max_clusters: kbConfig.raptor?.max_clusters ?? 64,
                            seed: kbConfig.raptor?.seed ?? 0,
                          }),
                        },
                      );
                      const r = await fetch(
                        `/api/kb/${encodeURIComponent(String(name || ""))}/raptor/status`,
                      );
                      if (r.ok) {
                        const d = await r.json();
                        setKbConfig((prev: any) => ({
                          ...prev,
                          raptor: { ...(prev.raptor || {}), status: d.status },
                        }));
                      }
                    }}>生成 RAPTOR</Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>数据源</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <Label>类型</Label>
                    <Select
                      value={newSource.type}
                      onChange={(e) =>
                        setNewSource((s) => ({ ...s, type: e.target.value }))
                      }
                    >
                      {[
                        "s3",
                        "confluence",
                        "notion",
                        "jira",
                        "google_drive",
                        "discord",
                        "web",
                      ].map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>端点/地址</Label>
                    <Input
                      value={newSource.endpoint || ""}
                      onChange={(e) =>
                        setNewSource((s) => ({
                          ...s,
                          endpoint: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Label>令牌/密钥</Label>
                    <Input
                      value={newSource.token || ""}
                      onChange={(e) =>
                        setNewSource((s) => ({ ...s, token: e.target.value }))
                      }
                    />
                  </div>
                </div>
                <div>
                  <Button size="sm" onClick={() => {
                      const arr = Array.isArray(kbConfig.data_sources)
                        ? kbConfig.data_sources.slice()
                        : [];
                      if (newSource.type)
                        arr.push({
                          type: newSource.type,
                          config: {
                            endpoint: newSource.endpoint,
                            token: newSource.token,
                          },
                        });
                      updateKb({ data_sources: arr });
                      setNewSource({ type: "" });
                    }}>添加数据源</Button>
                </div>
                <Separator />
                <div className="space-y-2">
                  {(kbConfig.data_sources || []).length === 0 ? (
                    <div className="text-sm text-gray-500">暂无数据源</div>
                  ) : (
                    (kbConfig.data_sources || []).map(
                      (ds: any, idx: number) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between border rounded p-3 text-sm"
                        >
                          <div>
                            <div className="font-medium">{ds.type}</div>
                            <div className="text-gray-500">
                              {ds.config?.endpoint || ""}
                            </div>
                          </div>
                          <Button variant="destructive" onClick={() => {
                              const arr = (kbConfig.data_sources || []).slice();
                              arr.splice(idx, 1);
                              updateKb({ data_sources: arr });
                            }}>删除</Button>
                        </div>
                      ),
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>检索测试</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center space-x-2 mb-3">
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="输入测试查询"
                  />
                  <div className="flex items-center space-x-2">
                    <Label>Top K</Label>
                    <Input
                      type="number"
                      value={topK}
                      min={1}
                      max={50}
                      onChange={(e) => setTopK(parseInt(e.target.value || "5"))}
                      className="w-24"
                    />
                  </div>
                  <Button onClick={testSearch}>查询</Button>
                </div>
                <div className="space-y-2">
                  {results.length === 0 ? (
                    <div className="text-sm text-gray-500">暂无结果</div>
                  ) : (
                    results.map((r, idx) => (
                      <div key={idx} className="border rounded p-3 text-sm">
                        <div className="text-gray-600">
                          {r.document_name} • p.{r.page_number} • score{" "}
                          {r.score?.toFixed?.(3) ?? r.score}
                        </div>
                        <div className="mt-1 whitespace-pre-wrap">
                          {r.content}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {tab === "logs" && (
          <div className="max-w-screen-lg mx-auto p-6">
            <div className="text-lg font-semibold mb-4">日志</div>
            <div className="bg-white border rounded p-4">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="px-2 py-2">日期</th>
                    <th className="px-2 py-2">调用次数</th>
                    <th className="px-2 py-2">Tokens</th>
                    <th className="px-2 py-2">耗时(ms)</th>
                  </tr>
                </thead>
                <tbody>
                  {agg.length === 0 ? (
                    <tr>
                      <td className="px-2 py-6 text-gray-500" colSpan={4}>
                        暂无日志
                      </td>
                    </tr>
                  ) : (
                    agg.map((r) => (
                      <tr key={r.day} className="border-t">
                        <td className="px-2 py-2">{r.day}</td>
                        <td className="px-2 py-2">{r.calls}</td>
                        <td className="px-2 py-2">{r.tokens}</td>
                        <td className="px-2 py-2">{r.duration_ms}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "test" && (
          <div className="max-w-screen-lg mx-auto p-6">
            <div className="text-lg font-semibold mb-4">检索测试</div>
            <Card>
              <CardContent className="p-4">
              <div className="flex items-center space-x-2 mb-3">
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="输入测试查询" className="flex-1 h-9" />
                <div className="flex items-center space-x-2">
                  <Label>Top K</Label>
                  <Input type="number" value={topK} min={1} max={50} onChange={(e) => setTopK(parseInt(e.target.value || "5"))} className="w-20" />
                </div>
                <Button size="sm" onClick={testSearch}>查询</Button>
              </div>
              <div className="space-y-2">
                {results.length === 0 ? (
                  <div className="text-sm text-gray-500">暂无结果</div>
                ) : (
                  results.map((r, idx) => (
                    <div key={idx} className="border rounded p-3 text-sm">
                      <div className="text-gray-600">
                        {r.document_name} • p.{r.page_number} • score {" "}
                        {r.score?.toFixed?.(3) ?? r.score}
                      </div>
                      <div className="mt-1 whitespace-pre-wrap">
                        {r.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
              </CardContent>
            </Card>
          </div>
        )}

        {tab === "files" && (
          <div className="max-w-screen-lg mx-auto p-6">
            <div className="text-lg font-semibold mb-4">文件列表</div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索文件名" className="w-64" />
              </div>
              <div>
                <input
                  ref={uploadRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={uploadPdf}
                />
                <Button size="sm" onClick={() => uploadRef.current?.click()}>
                  <Upload className="h-4 w-4 inline mr-1" /> 新增文件
                </Button>
              </div>
            </div>
            <Card>
              <CardContent className="p-0">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th className="px-2 py-2">名称</th>
                    <th className="px-2 py-2">状态</th>
                    <th className="px-2 py-2">页数</th>
                    <th className="px-2 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {docsFiltered.length === 0 ? (
                    <tr>
                      <td className="px-2 py-6 text-gray-500" colSpan={4}>
                        暂无文件
                      </td>
                    </tr>
                  ) : (
                    docsFiltered.map((d) => (
                      <tr key={d.id} className="border-t">
                        <td className="px-2 py-2">{d.filename}</td>
                        <td className="px-2 py-2">{d.processing_status}</td>
                        <td className="px-2 py-2">
                          {d.processed_pages}/{d.total_pages}
                        </td>
                        <td className="px-2 py-2 space-x-2">
                          <a
                            className="text-blue-600 hover:underline"
                            href={`/api/documents/${d.id}/download`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Download className="h-4 w-4 inline" /> 下载
                          </a>
                          <a
                            className="text-destructive cursor-pointer hover:underline"
                            onClick={() => removeDoc(d.id)}
                          >
                            删除
                          </a>
                          <a
                            className="text-primary cursor-pointer hover:underline"
                            onClick={async () => {
                              await fetch(
                                `/api/kb/${encodeURIComponent(String(name || ""))}/raptor/generate`,
                                {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                  },
                                  body: JSON.stringify({
                                    scope: "file",
                                    file_id: d.id,
                                    prompt: kbConfig.raptor?.prompt || "",
                                    max_tokens:
                                      kbConfig.raptor?.max_tokens ?? 256,
                                    threshold:
                                      kbConfig.raptor?.threshold ?? 0.1,
                                    max_clusters:
                                      kbConfig.raptor?.max_clusters ?? 64,
                                    seed: kbConfig.raptor?.seed ?? 0,
                                  }),
                                },
                              );
                              const r = await fetch(
                                `/api/kb/${encodeURIComponent(String(name || ""))}/raptor/status`,
                              );
                              if (r.ok) {
                                const s = await r.json();
                                setKbConfig((prev: any) => ({
                                  ...prev,
                                  raptor: {
                                    ...(prev.raptor || {}),
                                    status: s.status,
                                  },
                                }));
                              }
                            }}
                          >
                            生成RAPTOR
                          </a>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseDetail;
