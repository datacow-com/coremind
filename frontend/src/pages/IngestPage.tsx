import { useEffect, useRef, useState } from "react";
import {
  Upload,
  FilePlus,
  FileText,
  PlayCircle,
  ListChecks,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { checkFile } from "@/lib/validation";
import { useToast } from "@/components/ui/toast-provider";
import { useStream } from "@/hooks/useStream";

type ThoughtEvent = {
  phase?: string;
  status?: string;
  metrics?: { duration_ms?: number };
};

const IngestPage: React.FC = () => {
  const [indexEnabled] = useState<boolean>(false);
  const [useStream] = useState<boolean>(false);
  const [mdPreview, setMdPreview] = useState<string>("");
  const [mdPath, setMdPath] = useState<string>("");
  const [, setLastDocId] = useState<string>("");
  const [events, setEvents] = useState<ThoughtEvent[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [errMsg, setErrMsg] = useState<string>("");
  const autoInputRef = useRef<HTMLInputElement>(null);
  const typedInputRef = useRef<HTMLInputElement>(null);
  const [typedEndpoint, setTypedEndpoint] = useState<string>("pdf");
  const [documents, setDocuments] = useState<any[]>([]);
  const { push } = useToast();
  const { runStream, running: streamBusy } = useStream();

  const loadDocuments = async () => {
    try {
      const r = await apiFetch("/api/documents");
      if (r.ok) {
        const d = await r.json();
        setDocuments(d.documents || []);
      }
    } catch {}
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const resetPreview = () => {
    setMdPreview("");
    setMdPath("");
    setLastDocId("");
    setEvents([]);
  };

  const scenarioByExt: Record<string, string> = {
    pdf: "paper",
    html: "html",
    htm: "html",
    png: "table",
    jpg: "table",
    jpeg: "table",
    webp: "table",
  };

  const streamUpload = async (file: File, scenario?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (scenario) form.append("scenario", scenario);
    setEvents([]);
    await runStream(
      "/api/ingest/upload_run/stream",
      { method: "POST", body: form },
      {
        onEvent: (evt) => {
          if (evt?.node) {
            setEvents((prev) =>
              [...prev, { phase: evt.node, status: evt.type }].slice(-50),
            );
          } else if (evt?.type === "complete") {
            setEvents((prev) =>
              [...prev, { phase: "complete", status: "end" }].slice(-50),
            );
          } else if (evt?.error) {
            setErrMsg(String(evt.error));
          }
        },
        onError: (err) => setErrMsg(err?.message || String(err)),
      },
    );
  };

  const handleAutoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy || streamBusy) return;
    setErrMsg("");
    const ck = checkFile(file, {
      exts: ["pdf", "png", "jpg", "jpeg", "webp", "html", "htm"],
    });
    if (!ck.ok) {
      setErrMsg(ck.error || "文件校验失败");
      push({ title: "上传失败", description: ck.error, variant: "error" });
      e.target.value = "";
      return;
    }
    resetPreview();
    setBusy(true);
    try {
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      const scenario = scenarioByExt[ext];
      await streamUpload(file, scenario);
    } catch {
    } finally {
      setBusy(false);
      e.target.value = "";
      loadDocuments();
    }
  };

  const handleTypedUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy || streamBusy) return;
    setErrMsg("");
    const extMap: Record<string, string[]> = {
      pdf: ["pdf"],
      image: ["png", "jpg", "jpeg", "webp"],
      html: ["html", "htm"],
    };
    const ck = checkFile(file, { exts: extMap[typedEndpoint] || [] });
    if (!ck.ok) {
      setErrMsg(ck.error || "文件校验失败");
      push({ title: "上传失败", description: ck.error, variant: "error" });
      e.target.value = "";
      return;
    }
    resetPreview();
    setBusy(true);
    try {
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      const scenario = scenarioByExt[ext];
      await streamUpload(file, scenario);
    } catch {
    } finally {
      setBusy(false);
      e.target.value = "";
      loadDocuments();
    }
  };

  const deleteDocument = async (docId: string) => {
    try {
      const r = await apiFetch(`/api/documents/${docId}`, { method: "DELETE" });
      if (!r.ok) return;
      await loadDocuments();
    } catch {}
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FilePlus className="h-5 w-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-800">Ingestion</h2>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={resetPreview}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                Reset
              </button>
              {streamBusy && (
                <span className="text-xs text-gray-500">流式进行中...</span>
              )}
            </div>
          </div>
          {errMsg && <div className="mt-2 text-sm text-red-600">{errMsg}</div>}
        </div>

        <div className="p-6 grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border rounded-lg">
            <div className="p-4 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Upload className="h-4 w-4" />
                <span className="font-medium">自动摄取</span>
              </div>
              <button
                onClick={() => autoInputRef.current?.click()}
                className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                选择文件
              </button>
              <input
                ref={autoInputRef}
                type="file"
                onChange={handleAutoUpload}
                className="hidden"
              />
            </div>
            <div className="p-4 text-sm text-gray-600">
              上传后通过新管线流式处理，实时展示进度；仅支持
              PDF/图片/HTML，其他格式请先转 PDF/HTML
            </div>
          </div>

          <div className="bg-white border rounded-lg">
            <div className="p-4 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <PlayCircle className="h-4 w-4" />
                <span className="font-medium">
                  按类型摄取（仅支持 PDF/图片/HTML）
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <select
                  value={typedEndpoint}
                  onChange={(e) => setTypedEndpoint(e.target.value)}
                  className="px-2 py-1 border rounded"
                >
                  <option value="pdf">PDF</option>
                  <option value="image">Image</option>
                  <option value="markdown" disabled>
                    Markdown (deprecated)
                  </option>
                  <option value="docx" disabled>
                    Docx (deprecated)
                  </option>
                  <option value="pptx" disabled>
                    PPTX (deprecated)
                  </option>
                  <option value="xlsx" disabled>
                    XLSX (deprecated)
                  </option>
                  <option value="html">HTML</option>
                  <option value="eml" disabled>
                    EML (deprecated)
                  </option>
                </select>
                <button
                  onClick={() => typedInputRef.current?.click()}
                  className="px-3 py-1 bg-gray-700 text-white rounded-md hover:bg-gray-800"
                >
                  选择文件
                </button>
                <input
                  ref={typedInputRef}
                  type="file"
                  onChange={handleTypedUpload}
                  className="hidden"
                />
              </div>
            </div>
            <div className="p-4 text-sm text-gray-600">
              选择具体摄取管线，支持流式进度反馈
            </div>
          </div>

          <div className="bg-white border rounded-lg xl:col-span-2">
            <div className="p-4 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4" />
                <span className="font-medium">提取结果</span>
              </div>
              <div className="text-xs text-gray-500">
                {mdPath ? `md: ${mdPath}` : ""}
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3">
              <div className="lg:col-span-2 p-4">
                {mdPreview ? (
                  <pre className="text-xs whitespace-pre-wrap bg-gray-50 border rounded p-3 max-h-[480px] overflow-auto">
                    {mdPreview}
                  </pre>
                ) : (
                  <div className="p-8 text-center text-gray-500">
                    等待摄取结果
                  </div>
                )}
              </div>
              <div className="p-4 border-l">
                <div className="font-medium mb-2">进度</div>
                <div className="space-y-2">
                  {events.map((ev, i) => (
                    <div
                      key={i}
                      className="text-xs text-gray-700 flex items-center justify-between"
                    >
                      <span>{ev.phase}</span>
                      <span className="text-gray-500">
                        {ev.metrics?.duration_ms
                          ? `${ev.metrics.duration_ms}ms`
                          : ev.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white border rounded-lg xl:col-span-2">
            <div className="p-4 border-b flex items-center space-x-2">
              <ListChecks className="h-4 w-4" />
              <span className="font-medium">PDF 文档</span>
            </div>
            <div className="p-4">
              {documents.length === 0 ? (
                <div className="text-sm text-gray-500">暂无已上传 PDF</div>
              ) : (
                <div className="overflow-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500">
                        <th className="px-2 py-2">文件</th>
                        <th className="px-2 py-2">状态</th>
                        <th className="px-2 py-2">页数</th>
                        <th className="px-2 py-2">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((d) => (
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
                              下载
                            </a>
                            <button
                              className="text-red-600"
                              onClick={() => deleteDocument(d.id)}
                            >
                              删除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IngestPage;
