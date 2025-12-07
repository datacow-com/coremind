import { useEffect, useState } from "react";
import { Folder, RefreshCw, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";

interface DocItem {
  id: string;
  filename: string;
  processing_status: string;
  processed_pages: number;
  total_pages: number;
  file_size?: number;
}

const FilesManagerPage: React.FC = () => {
  const [kb, setKb] = useState<string>("");
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const { push } = useToast();

  const loadDocs = async () => {
    if (!kb) {
      setDocs([]);
      return;
    }
    setLoading(true);
    try {
      const r = await apiFetch(`/api/kb/${encodeURIComponent(kb)}/documents`);
      if (r.ok) {
        const d = await r.json();
        setDocs(d.documents || []);
      } else {
        setDocs([]);
      }
    } catch (e: any) {
      push({
        title: "加载失败",
        description: e?.message || "无法获取文件列表",
        variant: "error",
      });
      setDocs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kb]);

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
                value={kb}
                onChange={(e) => setKb(e.target.value)}
                placeholder="输入 KB 名称"
                className="px-3 py-2 border rounded-md text-sm"
              />
              <button
                onClick={loadDocs}
                className="px-3 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800 flex items-center space-x-1"
              >
                <RefreshCw className="h-4 w-4" />
                <span>刷新</span>
              </button>
            </div>
          </div>
          <div className="px-6 py-2 text-sm text-gray-500">
            上传与索引请前往“摄取”页，列表数据来自 `{kb}
            /documents`。下载与预览签名暂未提供。
          </div>
        </div>

        <div className="p-6">
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="px-2 py-2">名称</th>
                  <th className="px-2 py-2">状态</th>
                  <th className="px-2 py-2">页数</th>
                  <th className="px-2 py-2">大小</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td className="px-2 py-6 text-gray-500" colSpan={4}>
                      加载中...
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td className="px-2 py-6 text-gray-500" colSpan={4}>
                      暂无文件
                    </td>
                  </tr>
                ) : (
                  filtered.map((d) => (
                    <tr key={d.id} className="border-t">
                      <td className="px-2 py-2">{d.filename}</td>
                      <td className="px-2 py-2">{d.processing_status}</td>
                      <td className="px-2 py-2">
                        {d.processed_pages}/{d.total_pages}
                      </td>
                      <td className="px-2 py-2">
                        {d.file_size
                          ? `${(d.file_size / 1024 / 1024).toFixed(2)} MB`
                          : "-"}
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
