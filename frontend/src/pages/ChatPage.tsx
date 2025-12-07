import { useState, useRef, useEffect } from "react";
import { Send, Upload } from "lucide-react";
import { apiFetch, uploadAndRunIngest } from "@/lib/api";
import { useStream } from "@/hooks/useStream";
import { useToast } from "@/components/ui/toast-provider";
import { EmptyState } from "@/components/ui/empty";
import { AlertCard } from "@/components/ui/alert-card";

interface SourceItem {
  chunk_id: string;
  content: string;
  score: number;
  document_name: string;
  page_number: number;
  block_type?: string;
  heading_level?: number | null;
  table_id?: number | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceItem[];
}

interface Document {
  id: string;
  filename: string;
  processing_status: string;
  processed_pages: number;
  total_pages: number;
}

const fetch = apiFetch;

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [pdfPreview, setPdfPreview] = useState<string | null>(null);
  const [previewImg, setPreviewImg] = useState<string | null>(null);
  const [previewBBoxes, setPreviewBBoxes] = useState<
    Array<{ x: number; y: number; w: number; h: number }>
  >([]);
  const previewImgRef = useRef<HTMLImageElement>(null);
  const previewContainerRef = useRef<HTMLDivElement>(null);
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string>("");
  const [sourceOriginFilter, setSourceOriginFilter] = useState<string>("");
  const [lastCitationMeta, setLastCitationMeta] = useState<{
    block_type?: string;
    heading_level?: number | null;
    table_id?: number | null;
  } | null>(null);
  const [citationMetaByChunkId, setCitationMetaByChunkId] = useState<
    Record<
      string,
      {
        block_type?: string;
        heading_level?: number | null;
        table_id?: number | null;
      }
    >
  >({});
  const [imgScale, setImgScale] = useState<{ sx: number; sy: number }>({
    sx: 1,
    sy: 1,
  });
  const [topK, setTopK] = useState<number>(5);
  const [candidateK, setCandidateK] = useState<number>(50);
  const streaming = true;
  const [phase, setPhase] = useState<string>("idle");
  const [phaseHistory, setPhaseHistory] = useState<string[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [vectorWeight, setVectorWeight] = useState<number>(0.6);
  const [keywordWeight, setKeywordWeight] = useState<number>(0.4);
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(true);
  const [llmProvider, setLlmProvider] = useState<string>("dashscope");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [genStats, setGenStats] = useState<{
    chars: number;
    words: number;
  } | null>(null);
  const [fallbackMsg, setFallbackMsg] = useState<string | null>(null);
  const [retrievalCount, setRetrievalCount] = useState<number | null>(null);
  const [rerankAvg, setRerankAvg] = useState<number | null>(null);
  const [tokenRate, setTokenRate] = useState<{
    cps: number;
    wps: number;
  } | null>(null);
  const [lastPing, setLastPing] = useState<number | null>(null);
  const [exportLinks, setExportLinks] = useState<Record<string, string>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputExtRef = useRef<HTMLInputElement>(null);
  const [lastIngestInfo, setLastIngestInfo] = useState<{
    type: string;
    md_path: string;
    document_id: string;
  } | null>(null);
  const [kbBinding, setKbBinding] = useState<string>("");
  const [chats, setChats] = useState<any[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [conversationMap, setConversationMap] = useState<
    Record<string, string>
  >({});
  const [kbList, setKbList] = useState<{ name: string }[]>([]);
  const [kbEffective, setKbEffective] = useState<any | null>(null);
  const { runStream, running: streamRunning } = useStream();
  const { push } = useToast();

  const extractDocumentId = (documentName: string): string | null => {
    try {
      const base = documentName.split("/").pop() || documentName;
      const id = base.replace(".pdf", "");
      return id;
    } catch {
      return null;
    }
  };

  const loadPreviewForSource = async (source: {
    document_name: string;
    page_number: number;
  }) => {
    const docId = extractDocumentId(source.document_name);
    if (!docId || !source.page_number) {
      setPdfPreview(
        `Document: ${source.document_name}, Page: ${source.page_number}`,
      );
      setPreviewImg(null);
      setPreviewBBoxes([]);
      return;
    }
    try {
      const res = await fetch(
        `/api/documents/${docId}/pages/${source.page_number}`,
      );
      if (res.ok) {
        const data = await res.json();
        setPdfPreview(
          `Document: ${source.document_name}, Page: ${source.page_number}`,
        );
        setPreviewImg(`data:image/png;base64,${data.image_base64}`);
        setPreviewBBoxes(data.bboxes || []);
      } else {
        setPdfPreview(
          `Document: ${source.document_name}, Page: ${source.page_number}`,
        );
        setPreviewImg(null);
        setPreviewBBoxes([]);
      }
    } catch {
      setPdfPreview(
        `Document: ${source.document_name}, Page: ${source.page_number}`,
      );
      setPreviewImg(null);
      setPreviewBBoxes([]);
    }
  };

  const loadPreviewByDocId = async (
    docId: string,
    page: number,
    focusBBox?: { x: number; y: number; w: number; h: number } | null,
  ) => {
    if (!docId || !page) return;
    try {
      const res = await fetch(`/api/documents/${docId}/pages/${page}`);
      if (res.ok) {
        const data = await res.json();
        setPdfPreview(`Document: ${docId}.pdf, Page: ${page}`);
        setPreviewImg(`data:image/png;base64,${data.image_base64}`);
        const boxes = data.bboxes || [];
        setPreviewBBoxes(boxes);
        if (focusBBox) {
          setTimeout(() => {
            try {
              const el = previewContainerRef.current;
              const img = previewImgRef.current;
              if (!el || !img) return;
              const y = focusBBox.y * imgScale.sy;
              el.scrollTo({
                top: Math.max(y - el.clientHeight / 2, 0),
                behavior: "smooth",
              });
            } catch {}
          }, 100);
        }
      } else {
        setPdfPreview(`Document: ${docId}.pdf, Page: ${page}`);
        setPreviewImg(null);
        setPreviewBBoxes([]);
      }
    } catch {
      setPdfPreview(`Document: ${docId}.pdf, Page: ${page}`);
      setPreviewImg(null);
      setPreviewBBoxes([]);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const loadDocs = async () => {
      if (!kbBinding) {
        setDocuments([]);
        setSelectedDocument(null);
        return;
      }
      try {
        const r = await fetch(
          `/api/kb/${encodeURIComponent(kbBinding)}/documents`,
        );
        if (r.ok) {
          const data = await r.json();
          setDocuments(data.documents || []);
        } else {
          setDocuments([]);
        }
      } catch {
        setDocuments([]);
      }
    };
    loadDocs();
  }, [kbBinding]);

  useEffect(() => {
    const loadDefaults = async () => {
      try {
        const res = await fetch("/api/models/providers");
        if (res.ok) {
          const data = await res.json();
          const s = data.config?.settings;
          if (s) {
            setVectorWeight(s.vector_weight ?? 0.6);
            setKeywordWeight(s.keyword_weight ?? 0.4);
            setWebSearchEnabled(s.web_search_enabled ?? true);
            if (s.llm_provider) setLlmProvider(String(s.llm_provider));
          }
        }
      } catch {}
    };
    loadDefaults();
  }, []);

  useEffect(() => {
    const onSettingsUpdate = (e: any) => {
      const d = e.detail || {};
      if (typeof d.vector_weight === "number") setVectorWeight(d.vector_weight);
      if (typeof d.keyword_weight === "number")
        setKeywordWeight(d.keyword_weight);
      if (typeof d.web_search_enabled === "boolean")
        setWebSearchEnabled(d.web_search_enabled);
    };
    window.addEventListener("settings:update", onSettingsUpdate as any);
    return () =>
      window.removeEventListener("settings:update", onSettingsUpdate as any);
  }, []);

  useEffect(() => {
    try {
      const savedMap = JSON.parse(
        localStorage.getItem("omnirag_conversations") || "{}",
      );
      if (savedMap && typeof savedMap === "object")
        setConversationMap(savedMap);
      const reg = JSON.parse(localStorage.getItem("omnirag_chats") || "[]");
      if (Array.isArray(reg) && reg.length > 0) setChats(reg);
      const ac = localStorage.getItem("omnirag_active_chat_id");
      if (ac) setActiveChatId(ac);
    } catch {}
    (async () => {
      try {
        const r = await fetch("/api/chat/sessions");
        if (r.ok) {
          const d = await r.json();
          const list = d.data?.sessions || d.sessions || [];
          if (Array.isArray(list)) {
            setChats(list);
            if (
              !localStorage.getItem("omnirag_active_chat_id") &&
              list.length > 0
            ) {
              setActiveChatId(list[0].id);
            }
          }
        }
      } catch {}
      try {
        const r = await fetch("/api/vector-store/collections");
        if (r.ok) {
          const d = await r.json();
          const arr = (d.collections || [])
            .map((c: any) => ({ name: c.name || c.collection || c.id || "" }))
            .filter((x: any) => x.name);
          setKbList(arr);
        }
      } catch {}
    })();
  }, []);

  useEffect(() => {
    const cfg = chats.find((c) => c.id === activeChatId)?.config;
    if (cfg) {
      if (typeof cfg.top_k === "number") setTopK(cfg.top_k);
      if (typeof cfg.candidate_k === "number") setCandidateK(cfg.candidate_k);
      if (typeof cfg.vector_weight === "number")
        setVectorWeight(cfg.vector_weight);
      if (typeof cfg.keyword_weight === "number")
        setKeywordWeight(cfg.keyword_weight);
      if (typeof cfg.web_search_enabled === "boolean")
        setWebSearchEnabled(cfg.web_search_enabled);
      if (typeof cfg.kb_name === "string") setKbBinding(cfg.kb_name);
      else if (typeof cfg.lang_hint === "string") setKbBinding(cfg.lang_hint);
    }
    try {
      if (activeChatId)
        localStorage.setItem("omnirag_active_chat_id", activeChatId);
    } catch {}
  }, [activeChatId, chats]);

  useEffect(() => {
    if (activeChatId) {
      setConversationId(conversationMap[activeChatId] || null);
    } else {
      setConversationId(null);
    }
  }, [activeChatId, conversationMap]);

  useEffect(() => {
    const loadKbEffective = async () => {
      if (!kbBinding) {
        setKbEffective(null);
        return;
      }
      try {
        const r = await fetch(
          `/api/kb/${encodeURIComponent(kbBinding)}/config`,
        );
        if (r.ok) {
          const d = await r.json();
          setKbEffective(d.effective_config || null);
        }
      } catch {}
    };
    loadKbEffective();
  }, [kbBinding]);

  const patchSessionConfig = async (
    sid: string,
    config: any,
    kb?: string | null,
  ) => {
    try {
      await fetch(`/api/chat/sessions/${encodeURIComponent(sid)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config, kb_name: kb }),
      });
    } catch {}
  };

  const upsertActiveChatConfig = (partial: any) => {
    if (!activeChatId) return;
    const current = chats.find((c) => c.id === activeChatId);
    const nextCfg = { ...(current?.config || {}), ...partial };
    const kbName = partial.kb_name ?? current?.kb_name ?? null;
    setChats((prev) =>
      prev.map((c) =>
        c.id === activeChatId ? { ...c, kb_name: kbName, config: nextCfg } : c,
      ),
    );
    patchSessionConfig(activeChatId, nextCfg, kbName);
  };

  const createChat = async () => {
    const name = window.prompt("请输入聊天名称") || "会话";
    const cfg = {
      top_k: topK,
      candidate_k: candidateK,
      vector_weight: vectorWeight,
      keyword_weight: keywordWeight,
      web_search_enabled: webSearchEnabled,
      kb_name: kbBinding || null,
      lang_hint: kbBinding || null,
    };
    try {
      const res = await fetch("/api/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, kb_name: kbBinding || null, config: cfg }),
      });
      if (res.ok) {
        const d = await res.json();
        const item = d.data?.session ||
          d.session || { id: `${Date.now()}`, name, config: cfg };
        setChats((prev) => [item, ...prev]);
        setActiveChatId(item.id);
        setMessages([]);
        setConversationId(null);
        setConversationMap((prev) => {
          const next = { ...prev };
          delete next[item.id];
          return next;
        });
        return;
      }
    } catch {}
    const fallbackId = `${Date.now()}`;
    setChats((prev) => [{ id: fallbackId, name, config: cfg }, ...prev]);
    setActiveChatId(fallbackId);
    setMessages([]);
    setConversationId(null);
  };

  const deleteChat = async (id?: string) => {
    const target = id || activeChatId;
    if (!target) return;
    try {
      await fetch(`/api/chat/sessions/${encodeURIComponent(target)}`, {
        method: "DELETE",
      });
    } catch {}
    const remaining = chats.filter((c) => c.id !== target);
    setChats(remaining);
    setConversationMap((prev) => {
      const next = { ...prev };
      delete next[target];
      return next;
    });
    if (activeChatId === target) {
      const next = remaining[0];
      setActiveChatId(next ? next.id : null);
      setMessages([]);
      setConversationId(null);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading || streamRunning) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const convId = activeChatId
        ? conversationMap[activeChatId] || null
        : conversationId;
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
      };
      setMessages((prev) => [...prev, assistantMessage]);
      const payload = {
        query: input,
        conversation_id: convId,
        document_ids: selectedDocument ? [selectedDocument] : undefined,
        top_k: topK,
        candidate_k: candidateK,
        temperature: 0.7,
        vector_weight: vectorWeight,
        keyword_weight: keywordWeight,
        web_search_enabled: webSearchEnabled,
        kb_name: kbBinding || undefined,
      };
      setStreamError(null);
      await runStream(
        "/api/chat/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: input,
            history: messages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            kb_name: kbBinding || "default",
            strategy_config: {
              top_k: topK,
              candidate_k: candidateK,
              temperature: 0.7,
              vector_weight: vectorWeight,
              keyword_weight: keywordWeight,
              web_search_enabled: webSearchEnabled,
            },
          }),
        },
        {
          onEvent: async (evt: any) => {
            if (evt.type === "node_start" || evt.type === "node_end") {
              const status = evt.type === "node_start" ? "start" : "end";
              const name = evt.node || "node";
              setPhase(`${name}:${status}`);
              setPhaseHistory((prev) =>
                [...prev, `${name}:${status}`].slice(-6),
              );
            } else if (evt.type === "answer") {
              const content = evt.content || evt.answer || evt.delta || "";
              const citations = evt.citations || evt.sources || [];
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id
                    ? {
                        ...m,
                        content: content || m.content,
                        sources: citations,
                      }
                    : m,
                ),
              );
              if (citations?.length > 0) {
                const first = citations[0];
                await loadPreviewForSource(first);
              }
            } else if (evt.type === "final") {
              // 兼容旧协议
              if (evt.sources && evt.sources.length > 0) {
                const firstSource = evt.sources[0];
                await loadPreviewForSource(firstSource);
                const enrichedSources: SourceItem[] = (evt.sources || []).map(
                  (s: any) => {
                    const meta =
                      citationMetaByChunkId[String(s.chunk_id || "")] || {};
                    const hl =
                      typeof meta.heading_level === "number"
                        ? meta.heading_level
                        : null;
                    const tid =
                      typeof meta.table_id === "number" ? meta.table_id : null;
                    return {
                      ...s,
                      block_type: meta.block_type,
                      heading_level: hl,
                      table_id: tid,
                    } as SourceItem;
                  },
                );
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id
                      ? { ...m, sources: enrichedSources }
                      : m,
                  ),
                );
              }
              if (evt.answer) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id
                      ? { ...m, content: (m.content || "") + evt.answer }
                      : m,
                  ),
                );
              }
            } else if (evt.type === "citation") {
              const docId = String(evt.doc_id || "");
              const page = parseInt(evt.page || 0);
              const bbox = evt.bbox || null;
              const bt = evt.block_type || null;
              const hl = evt.heading_level ?? null;
              const tid = evt.table_id ?? null;
              const cid = String(evt.chunk_id || "");
              setLastCitationMeta({
                block_type: bt || undefined,
                heading_level: typeof hl === "number" ? hl : null,
                table_id: typeof tid === "number" ? tid : null,
              });
              if (cid) {
                setCitationMetaByChunkId((prev) => ({
                  ...prev,
                  [cid]: {
                    block_type: bt || undefined,
                    heading_level: typeof hl === "number" ? hl : null,
                    table_id: typeof tid === "number" ? tid : null,
                  },
                }));
              }
              if (docId && page) {
                await loadPreviewByDocId(
                  docId.replace(/\.pdf$/i, ""),
                  page,
                  bbox,
                );
              }
            } else if (evt.type === "meta") {
              if (evt.request_id) setRequestId(String(evt.request_id));
            } else if (evt.type === "metrics") {
              const ch = parseInt(evt.chars || 0);
              const wd = parseInt(evt.words || 0);
              const cps = parseFloat(evt.chars_per_sec || 0);
              const wps = parseFloat(evt.words_per_sec || 0);
              setGenStats({ chars: ch, words: wd });
              setTokenRate({ cps, wps });
            } else if (evt.type === "error") {
              setStreamError(evt.error || "流式失败，请重试");
              push({
                title: "流式失败",
                description: evt.error || "请重试",
                variant: "error",
              });
            }
          },
          onError: (err) => {
            setStreamError(err?.message || "流式失败，请重试");
            push({
              title: "流式失败",
              description: err?.message || "请重试",
              variant: "error",
            });
          },
          onDone: () => {
            setIsLoading(false);
          },
        },
      );
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "抱歉，处理请求时出现错误，请稍后重试。",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExtIngestUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const name = (file.name || "").toLowerCase();
    const ext = name.split(".").pop() || "";
    const scenarioMap: Record<string, string> = {
      pdf: "paper",
      html: "html",
      htm: "html",
      png: "table",
      jpg: "table",
      jpeg: "table",
      webp: "table",
    };
    try {
      const scenario = scenarioMap[ext];
      const response = await uploadAndRunIngest({ file, scenario });
      if (!response.ok) throw new Error("Failed to ingest file");
      const data = await response.json();
      setLastIngestInfo({
        type: ext,
        md_path: data.md_path || "",
        document_id: data.document_id || "",
      });
    } catch (e) {
      // noop
    }
  };

  const handleExportTables = async (message: Message) => {
    try {
      const tables = (message.sources || [])
        .map((s) => s.content || "")
        .filter((c) => c.includes("|"));
      if (tables.length === 0) return;
      const res = await fetch("/api/execute/export/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tables }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.download_url)
        setExportLinks((prev: Record<string, string>) => ({
          ...prev,
          [message.id]: data.download_url,
        }));
    } catch {}
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(null);
    if (activeChatId) {
      setConversationMap((prev) => {
        const next = { ...prev };
        delete next[activeChatId];
        return next;
      });
    }
  };

  const clearPreview = () => {
    setPdfPreview(null);
    setPreviewImg(null);
    setPreviewBBoxes([]);
  };

  return (
    <div className="flex h-full">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">聊天</h2>
            <div className="flex items-center space-x-3">
              <button
                onClick={startNewChat}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                重置聊天
              </button>
              <button
                onClick={createChat}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                新建聊天
              </button>
              <button
                onClick={() => deleteChat()}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                disabled={!activeChatId}
              >
                删除当前
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await fetch("/api/models/providers");
                    if (res.ok) {
                      const data = await res.json();
                      const s = data.config?.settings;
                      if (s) {
                        setVectorWeight(s.vector_weight ?? 0.6);
                        setKeywordWeight(s.keyword_weight ?? 0.4);
                        setWebSearchEnabled(s.web_search_enabled ?? true);
                      }
                    }
                    const r2 = await fetch("/api/config/runtime");
                    if (r2.ok) {
                      const d2 = await r2.json();
                      if (typeof d2.top_k_default === "number")
                        setTopK(d2.top_k_default);
                      if (typeof d2.candidate_k === "number")
                        setCandidateK(d2.candidate_k);
                    }
                  } catch {}
                }}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                重置默认配置
              </button>
              <select
                value={activeChatId || ""}
                onChange={(e) => setActiveChatId(e.target.value || null)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">未选择会话</option>
                {chats.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <select
                value={selectedDocument || ""}
                onChange={(e) => setSelectedDocument(e.target.value || null)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">全部文件</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename} ({doc.processing_status})
                  </option>
                ))}
              </select>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">知识库</label>
                <select
                  value={kbBinding}
                  onChange={(e) => {
                    setKbBinding(e.target.value);
                    upsertActiveChatConfig({ kb_name: e.target.value || null });
                  }}
                  className="px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="">未绑定</option>
                  {kbList.map((kb) => (
                    <option key={kb.name} value={kb.name}>
                      {kb.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">Top K</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(e) => {
                    const v = Math.max(
                      1,
                      Math.min(10, parseInt(e.target.value || "5")),
                    );
                    setTopK(v);
                    upsertActiveChatConfig({ top_k: v });
                  }}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">候选数</label>
                <input
                  type="number"
                  min={10}
                  max={200}
                  value={candidateK}
                  onChange={(e) => {
                    const v = Math.max(
                      10,
                      Math.min(200, parseInt(e.target.value || "50")),
                    );
                    setCandidateK(v);
                    upsertActiveChatConfig({ candidate_k: v });
                  }}
                  className="w-20 border border-gray-300 rounded px-2 py-1"
                />
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">向量权重</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={vectorWeight}
                  onChange={(e) => {
                    const v = Math.max(
                      0,
                      Math.min(1, parseFloat(e.target.value || "0.6")),
                    );
                    setVectorWeight(v);
                    upsertActiveChatConfig({ vector_weight: v });
                  }}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
                <label className="text-gray-600">关键词权重</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.1}
                  value={keywordWeight}
                  onChange={(e) => {
                    const v = Math.max(
                      0,
                      Math.min(1, parseFloat(e.target.value || "0.4")),
                    );
                    setKeywordWeight(v);
                    upsertActiveChatConfig({ keyword_weight: v });
                  }}
                  className="w-16 border border-gray-300 rounded px-2 py-1"
                />
              </div>
              <div className="text-xs text-gray-600">
                <span className="mr-2">
                  连接:{" "}
                  {lastPing && Date.now() - lastPing < 30000 ? "活跃" : "空闲"}
                </span>
                {requestId && <span className="mr-2">req: {requestId}</span>}
                {streamError && streamError.includes("Too many requests") && (
                  <span className="text-red-600">429</span>
                )}
              </div>

              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">来源类型</label>
                <select
                  value={sourceTypeFilter}
                  onChange={(e) => setSourceTypeFilter(e.target.value)}
                  className="px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="">全部</option>
                  <option value="heading">标题</option>
                  <option value="paragraph">段落</option>
                  <option value="table">表格</option>
                  <option value="figure">图像</option>
                </select>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">来源</label>
                <select
                  value={sourceOriginFilter}
                  onChange={(e) => setSourceOriginFilter(e.target.value)}
                  className="px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="">全部</option>
                  <option value="internal">内部</option>
                  <option value="web">网页</option>
                </select>
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">网页检索</label>
                <input
                  type="checkbox"
                  checked={webSearchEnabled}
                  onChange={(e) => {
                    setWebSearchEnabled(e.target.checked);
                    upsertActiveChatConfig({
                      web_search_enabled: e.target.checked,
                    });
                  }}
                />
              </div>
              <div className="flex items-center space-x-2 text-sm">
                <label className="text-gray-600">提供方</label>
                <select
                  value={llmProvider}
                  onChange={async (e) => {
                    const v = e.target.value;
                    setLlmProvider(v);
                    try {
                      await fetch("/api/system/settings/update", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ llm_provider: v }),
                      });
                    } catch {}
                  }}
                  className="px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="dashscope">dashscope</option>
                  <option value="ark">ark</option>
                  <option value="ollama">ollama</option>
                  <option value="openai">openai</option>
                  <option value="gemini">gemini</option>
                </select>
              </div>
              <div className="text-xs text-gray-600">
                <span className="mr-2">阶段: {phase}</span>
                {streamError && (
                  <span className="text-red-600">{streamError}</span>
                )}
                {phaseHistory.length > 0 && (
                  <span className="ml-2 text-gray-400">
                    [{phaseHistory.join(" > ")}]
                  </span>
                )}
                {requestId && (
                  <span className="ml-2 text-gray-400">req: {requestId}</span>
                )}
                {genStats && (
                  <span className="ml-2 text-gray-400">
                    生成: {genStats.chars} 字符 / {genStats.words} 词
                  </span>
                )}
                {tokenRate && (
                  <span className="ml-2 text-gray-400">
                    速率: {tokenRate.cps.toFixed(1)} 字符/秒 /{" "}
                    {tokenRate.wps.toFixed(1)} 词/秒
                  </span>
                )}
                {retrievalCount !== null && (
                  <span className="ml-2 text-gray-400">
                    命中: {retrievalCount}
                  </span>
                )}
                {rerankAvg !== null && (
                  <span className="ml-2 text-gray-400">
                    平均: {rerankAvg.toFixed(3)}
                  </span>
                )}
                {fallbackMsg && (
                  <span className="ml-2 text-yellow-600">{fallbackMsg}</span>
                )}
                {lastPing && <span className="ml-2 text-green-600">心跳</span>}
              </div>

              <input
                ref={fileInputExtRef}
                type="file"
                accept=".docx,.pptx,.xlsx,.md,.markdown,.png,.jpg,.jpeg,.webp,.html,.htm,.eml"
                onChange={handleExtIngestUpload}
                className="hidden"
              />

              <button
                onClick={() => fileInputExtRef.current?.click()}
                className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
              >
                <Upload className="h-4 w-4" />
                <span>摄取其他格式</span>
              </button>
            </div>
          </div>
        </div>

        {kbEffective?.chunk_strategy && (
          <div className="bg-muted/60 border-b px-6 py-3 text-sm text-muted-foreground">
            <div className="font-medium text-foreground mb-1">
              当前 KB 分块策略
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="px-2 py-1 bg-white border rounded">
                min/max {kbEffective.chunk_strategy.min_tokens}/
                {kbEffective.chunk_strategy.max_tokens}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                overlap {kbEffective.chunk_strategy.chunk_overlap}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                semantic{" "}
                {kbEffective.chunk_strategy.semantic_enabled ? "on" : "off"}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                layout{" "}
                {kbEffective.chunk_strategy.keep_layout ? "keep" : "drop"}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                bbox {kbEffective.chunk_strategy.keep_bbox ? "keep" : "drop"}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                table {kbEffective.chunk_strategy.table_extract ? "on" : "off"}
              </span>
              <span className="px-2 py-1 bg-white border rounded">
                ocr {kbEffective.chunk_strategy.ocr_enabled ? "on" : "off"}
              </span>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {(retrievalCount !== null ||
            rerankAvg !== null ||
            genStats ||
            tokenRate) && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-white border rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">检索</div>
                <div className="text-sm text-gray-800">
                  命中 {retrievalCount ?? "-"}
                </div>
              </div>
              <div className="bg-white border rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">重排</div>
                <div className="text-sm text-gray-800">
                  平均 {rerankAvg !== null ? rerankAvg.toFixed(3) : "-"}
                </div>
              </div>
              <div className="bg-white border rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">生成</div>
                <div className="text-sm text-gray-800">
                  {genStats
                    ? `${genStats.chars} 字 / ${genStats.words} 词`
                    : "等待结果"}
                  ，速率{" "}
                  {tokenRate
                    ? `${tokenRate.cps.toFixed(1)} 字/s / ${tokenRate.wps.toFixed(1)} 词/s`
                    : "-"}
                </div>
              </div>
            </div>
          )}
          {streamError && (
            <AlertCard
              variant="error"
              title="流式错误"
              description={streamError}
            />
          )}
          {messages.length === 0 ? (
            <EmptyState
              title="欢迎使用 OmniRAG"
              description="上传文档后开始问答，或直接输入问题。"
            />
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-3xl rounded-lg px-4 py-2 ${
                    message.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-white border border-gray-200 text-gray-800"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>

                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs text-gray-500 mb-2">来源：</p>
                      <div className="space-y-1">
                        {message.sources
                          .filter((s) => {
                            const bt = s.block_type || undefined;
                            if (!sourceTypeFilter) return true;
                            return (
                              (bt || "").toLowerCase() === sourceTypeFilter
                            );
                          })
                          .filter((s) => {
                            if (!sourceOriginFilter) return true;
                            const nm = (s.document_name || "").toLowerCase();
                            const isWeb =
                              nm.startsWith("http://") ||
                              nm.startsWith("https://");
                            return sourceOriginFilter === "web"
                              ? isWeb
                              : !isWeb;
                          })
                          .sort((a: SourceItem, b: SourceItem) => {
                            const ha =
                              typeof a.heading_level === "number"
                                ? a.heading_level
                                : 99;
                            const hb =
                              typeof b.heading_level === "number"
                                ? b.heading_level
                                : 99;
                            if (ha !== hb) return ha - hb;
                            if (
                              typeof a.score === "number" &&
                              typeof b.score === "number"
                            )
                              return b.score - a.score;
                            return (a.page_number || 0) - (b.page_number || 0);
                          })
                          .map((source, index) => (
                            <div
                              key={source.chunk_id}
                              className="flex items-start gap-2"
                            >
                              <button
                                className="text-xs text-blue-600 hover:underline"
                                onClick={() => loadPreviewForSource(source)}
                              >
                                <span className="font-medium">
                                  [{index + 1}]
                                </span>{" "}
                                {source.document_name}（第 {source.page_number}{" "}
                                页）{" "}
                                {(() => {
                                  const bt = source.block_type;
                                  const hl = source.heading_level;
                                  const tid = source.table_id;
                                  const bbox = source.bbox;
                                  const parts: string[] = [];
                                  if (bt) parts.push(String(bt));
                                  if (typeof hl === "number")
                                    parts.push(`h${hl}`);
                                  if (typeof tid === "number")
                                    parts.push(`table#${tid}`);
                                  if (bbox && typeof bbox === "object")
                                    parts.push("bbox");
                                  return parts.length ? (
                                    <span className="text-gray-500">
                                      [{parts.join(",")}]
                                    </span>
                                  ) : null;
                                })()}
                              </button>
                              {source.bbox && (
                                <span className="text-[10px] text-gray-500">
                                  bbox: x{source.bbox.x} y{source.bbox.y} w
                                  {source.bbox.w} h{source.bbox.h}
                                </span>
                              )}
                            </div>
                          ))}
                      </div>
                      <div className="mt-2 flex items-center space-x-2">
                        <button
                          className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
                          onClick={() => handleExportTables(message)}
                        >
                          导出表格 CSV
                        </button>
                        {exportLinks[message.id] && (
                          <a
                            className="text-xs text-blue-600 hover:underline"
                            href={exportLinks[message.id]}
                            target="_blank"
                            rel="noreferrer"
                          >
                            下载 CSV
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t px-6 py-4">
          <div className="flex space-x-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="提问与文档相关的问题..."
              className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              disabled={isLoading}
            />
            <button
              onClick={handleSendMessage}
              disabled={!input.trim() || isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* PDF Preview Panel */}
      <div className="w-96 bg-white border-l">
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">PDF 预览</h3>
          <button
            onClick={clearPreview}
            className="text-xs px-2 py-1 border rounded hover:bg-gray-50"
          >
            清空
          </button>
        </div>
        <div className="p-4">
          {lastIngestInfo && (
            <div className="mb-4 text-xs text-gray-600">
              <div>
                Last Ingest:{" "}
                <span className="font-medium">.{lastIngestInfo.type}</span>
              </div>
              {lastIngestInfo.md_path && (
                <div className="truncate">md: {lastIngestInfo.md_path}</div>
              )}
            </div>
          )}
          {pdfPreview ? (
            <div className="text-sm text-gray-600">
              <p className="mb-2">{pdfPreview}</p>
              {lastCitationMeta && (
                <div className="mb-2 text-xs text-gray-500">
                  <span>type: {lastCitationMeta.block_type || "-"}</span>{" "}
                  <span className="ml-2">
                    heading: {lastCitationMeta.heading_level ?? "-"}
                  </span>{" "}
                  <span className="ml-2">
                    table: {lastCitationMeta.table_id ?? "-"}
                  </span>
                </div>
              )}
              {previewImg ? (
                <div
                  ref={previewContainerRef}
                  className="relative border rounded overflow-auto max-h-[620px]"
                >
                  <img
                    ref={previewImgRef}
                    src={previewImg}
                    alt="preview"
                    className="max-w-full"
                    onLoad={() => {
                      try {
                        const el = previewImgRef.current;
                        if (!el) return;
                        const nw = el.naturalWidth || 1;
                        const nh = el.naturalHeight || 1;
                        const cw = el.clientWidth || nw;
                        const ch = el.clientHeight || nh;
                        setImgScale({ sx: cw / nw, sy: ch / nh });
                      } catch {}
                    }}
                  />
                  {previewBBoxes.map((b, i) => (
                    <div
                      key={i}
                      style={{
                        position: "absolute",
                        left: b.x * imgScale.sx,
                        top: b.y * imgScale.sy,
                        width: b.w * imgScale.sx,
                        height: b.h * imgScale.sy,
                        border: "2px solid rgba(59,130,246,0.8)",
                        boxShadow: "0 0 0 2px rgba(59,130,246,0.3) inset",
                      }}
                    />
                  ))}
                </div>
              ) : (
                <div className="mt-4 p-4 bg-gray-100 rounded-lg">
                  <p className="text-xs text-gray-500">暂无预览</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-sm">引用来源时将显示 PDF 预览</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
