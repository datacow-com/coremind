import { useEffect, useRef, useState } from "react";
import { Upload, Folder, Trash2, Download, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { checkFile } from "@/lib/validation";
import { useToast } from "@/components/ui/toast-provider";

interface DocItem {
  id: string;
  filename: string;
  processing_status: string;
  processed_pages: number;
  total_pages: number;
}

const FilesManagerPage: React.FC = () => {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [errMsg, setErrMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { push } = useToast();

  const loadDocs = async () => {
    try {
      const r = await apiFetch("/api/documents");
      if (r.ok) {
        const d = await r.json();
        setDocs(d.documents || []);
      }
    } catch {}
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const uploadPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || busy) return;
    setErrMsg("");
    const ck = checkFile(file, { exts: ["pdf"] });
    if (!ck.ok) {
      setErrMsg(ck.error || "文件校验失败");
      push({ title: "上传失败", description: ck.error, variant: "error" });
      e.target.value = "";
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await apiFetch("/api/documents/upload", {
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
      const r = await apiFetch(`/api/documents/${docId}`, { method: "DELETE" });
      if (r.ok) await loadDocs();
    } catch {}
  };

  const filtered = docs.filter((d) =>
    (d.filename || "").toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Folder className="h-5 w-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-800">文件管理</h2>
            </div>
            <div className="flex items-center space-x-3">
              <div className="flex items-center border rounded px-2">
                <Search className="h-4 w-4 text-gray-400" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="搜索文件名"
                  className="px-2 py-1 text-sm outline-none"
                />
              </div>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={uploadPdf}
              />
              <button
                onClick={() => inputRef.current?.click()}
                className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <Upload className="h-4 w-4 inline mr-1" /> 新增文件
              </button>
            </div>
          </div>
          {errMsg && <div className="mt-2 text-sm text-red-600">{errMsg}</div>}
        </div>

        <div className="p-6">
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="px-2 py-2">名称</th>
                  <th className="px-2 py-2">上传日期</th>
                  <th className="px-2 py-2">状态</th>
                  <th className="px-2 py-2">页数</th>
                  <th className="px-2 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td className="px-2 py-6 text-gray-500" colSpan={5}>
                      暂无文件
                    </td>
                  </tr>
                ) : (
                  filtered.map((d) => (
                    <tr key={d.id} className="border-t">
                      <td className="px-2 py-2">{d.filename}</td>
                      <td className="px-2 py-2">
                        {new Date(
                          (d as any).upload_date * 1000,
                        ).toLocaleString()}
                      </td>
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
                        <button
                          className="text-red-600"
                          onClick={() => removeDoc(d.id)}
                        >
                          <Trash2 className="h-4 w-4 inline" /> 删除
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FilesManagerPage;
