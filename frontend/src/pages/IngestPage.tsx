import { useEffect, useRef, useState } from "react";
import {
  Upload,
  FilePlus,
  FileText,
  PlayCircle,
  ListChecks,
} from "lucide-react";

type ThoughtEvent = {
  phase?: string;
  status?: string;
  metrics?: { duration_ms?: number };
};

const IngestPage: React.FC = () => {
  const [indexEnabled, setIndexEnabled] = useState<boolean>(true);
  const [useStream, setUseStream] = useState<boolean>(true);
  const [mdPreview, setMdPreview] = useState<string>("");
  const [mdPath, setMdPath] = useState<string>("");
  const [, setLastDocId] = useState<string>("");
  const [events, setEvents] = useState<ThoughtEvent[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const autoInputRef = useRef<HTMLInputElement>(null);
  const typedInputRef = useRef<HTMLInputElement>(null);
  const [typedEndpoint, setTypedEndpoint] = useState<string>("pdf");
  const [documents, setDocuments] = useState<any[]>([]);

  const loadDocuments = async () => {
    try {
      const r = await fetch("/api/documents");
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

  const handleAutoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy) return;
    resetPreview();
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(
        `/api/ingest/auto?index=${indexEnabled ? "true" : "false"}`,
        { method: "POST", body: form },
      );
      if (!res.ok) throw new Error("ingest failed");
      const data = await res.json();
      setMdPreview(String(data.md || ""));
      setMdPath(String(data.md_path || ""));
      setLastDocId(String(data.document_id || ""));
    } catch {
    } finally {
      setBusy(false);
      e.target.value = "";
      loadDocuments();
    }
  };

  const streamUpload = async (endpoint: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const url = `/api/ingest/${endpoint}/stream?index=${indexEnabled ? "true" : "false"}`;
    const res = await fetch(url, { method: "POST", body: form });
    if (!res.ok || !res.body) throw new Error("stream failed");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const r = await reader.read();
      if (r.done) break;
      buf += decoder.decode(r.value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const chunk of parts) {
        const line = chunk.trim();
        if (!line.startsWith("data:")) continue;
        const js = line.slice(5).trim();
        try {
          const evt = JSON.parse(js);
          if (evt.type === "phase" || evt.phase) {
            const ph = evt.name || evt.phase;
            const st = evt.status || "end";
            const m = evt.metrics || {};
            setEvents((prev) =>
              [
                ...prev,
                { phase: String(ph), status: String(st), metrics: m },
              ].slice(-20),
            );
          } else if (
            evt.type === "final" ||
            evt.md ||
            evt.md_path ||
            evt.document_id
          ) {
            setMdPreview(String(evt.md || ""));
            setMdPath(String(evt.md_path || ""));
            setLastDocId(String(evt.document_id || ""));
          } else if (evt.error) {
            setMdPreview(`Error: ${String(evt.error)}`);
          }
        } catch {}
      }
    }
  };

  const handleTypedUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy) return;
    resetPreview();
    setBusy(true);
    try {
      if (useStream) {
        await streamUpload(typedEndpoint, file);
      } else {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(
          `/api/ingest/${typedEndpoint}?index=${indexEnabled ? "true" : "false"}`,
          { method: "POST", body: form },
        );
        if (!res.ok) throw new Error("ingest failed");
        const data = await res.json();
        setMdPreview(String(data.md || ""));
        setMdPath(String(data.md_path || ""));
        setLastDocId(String(data.document_id || ""));
      }
    } catch {
    } finally {
      setBusy(false);
      e.target.value = "";
      loadDocuments();
    }
  };

  const deleteDocument = async (docId: string) => {
    try {
      const r = await fetch(`/api/documents/${docId}`, { method: "DELETE" });
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
              <label className="text-sm text-gray-700">Index</label>
              <input
                type="checkbox"
                checked={indexEnabled}
                onChange={(e) => setIndexEnabled(e.target.checked)}
              />
              <label className="text-sm text-gray-700">Stream</label>
              <input
                type="checkbox"
                checked={useStream}
                onChange={(e) => setUseStream(e.target.checked)}
              />
              <button
                onClick={resetPreview}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
              >
                Reset
              </button>
            </div>
          </div>
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
              按扩展名自动选择 PDF/图片/Markdown/Office/HTML/EML 摄取管线
            </div>
          </div>

          <div className="bg-white border rounded-lg">
            <div className="p-4 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <PlayCircle className="h-4 w-4" />
                <span className="font-medium">按类型摄取</span>
              </div>
              <div className="flex items-center space-x-2">
                <select
                  value={typedEndpoint}
                  onChange={(e) => setTypedEndpoint(e.target.value)}
                  className="px-2 py-1 border rounded"
                >
                  <option value="pdf">PDF</option>
                  <option value="image">Image</option>
                  <option value="markdown">Markdown</option>
                  <option value="docx">Docx</option>
                  <option value="pptx">PPTX</option>
                  <option value="xlsx">XLSX</option>
                  <option value="html">HTML</option>
                  <option value="eml">EML</option>
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
