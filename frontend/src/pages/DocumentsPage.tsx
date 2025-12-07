import React, { useState } from "react";
import { FileText, RefreshCw, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Document {
  id: string;
  filename: string;
  processing_status: string;
  processed_pages: number;
  total_pages: number;
  file_size?: number;
}

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [kb, setKb] = useState("");
  const [q, setQ] = useState("");

  const fetchDocuments = async () => {
    if (!kb) {
      setDocuments([]);
      return;
    }
    setIsLoading(true);
    try {
      const response = await apiFetch(
        `/api/kb/${encodeURIComponent(kb)}/documents`,
      );
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      } else {
        setDocuments([]);
      }
    } catch {
      setDocuments([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filtered = documents.filter((d) =>
    (d.filename || "").toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-gray-800">
            Documents (KB)
          </h2>
          <div className="flex items-center gap-2">
            <input
              value={kb}
              onChange={(e) => setKb(e.target.value)}
              placeholder="输入 KB 名称"
              className="px-3 py-2 border rounded-md text-sm"
            />
            <div className="flex items-center border rounded px-2">
              <Search className="h-4 w-4 text-gray-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="搜索文件名"
                className="px-2 py-1 text-sm outline-none"
              />
            </div>
            <button
              onClick={fetchDocuments}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              <span>Refresh</span>
            </button>
          </div>
        </div>
        <div className="px-6 py-2 text-sm text-gray-500">
          列表来自 `/api/kb/{kb}
          /documents`。上传/索引请在摄取页完成；下载签名暂未提供。
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-center text-gray-500 mt-20">
            <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <p className="text-sm">Loading documents...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center text-gray-500 mt-20">
            <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <h3 className="text-lg font-medium mb-2">No documents</h3>
            <p className="text-sm">请先选择 KB 并在摄取页上传/索引。</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {filtered.map((document) => (
              <div key={document.id} className="bg-white border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <FileText className="h-8 w-8 text-blue-600 mt-1" />
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">
                        {document.filename}
                      </h3>
                      <p className="text-sm text-gray-500">
                        状态：{document.processing_status}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 text-sm text-gray-600">
                  <p>
                    Pages: {document.processed_pages}/{document.total_pages}
                  </p>
                  <p>
                    Size:{" "}
                    {document.file_size
                      ? `${(document.file_size / 1024 / 1024).toFixed(2)} MB`
                      : "-"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsPage;
