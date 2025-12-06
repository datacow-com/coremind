import React, { useState, useEffect } from "react";
import { FileText, Download, Trash2, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Document {
  id: string;
  filename: string;
  upload_date: string;
  processing_status: "pending" | "processing" | "completed" | "failed";
  processed_pages: number;
  total_pages: number;
  file_size: number;
}

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await apiFetch("/api/documents");
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents);
      }
    } catch (error) {
      console.error("Error fetching documents:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    try {
      const response = await apiFetch(`/api/documents/${documentId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));
      }
    } catch (error) {
      console.error("Error deleting document:", error);
    }
  };

  const handleDownload = async (documentId: string) => {
    try {
      const url = `/api/documents/${documentId}/download`;
      window.open(url, "_blank");
    } catch (error) {
      console.error("Error downloading file:", error);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-green-600 bg-green-50";
      case "processing":
        return "text-blue-600 bg-blue-50";
      case "failed":
        return "text-red-600 bg-red-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Documents</h2>
          <button
            onClick={fetchDocuments}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-center text-gray-500 mt-20">
            <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <p className="text-sm">Loading documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center text-gray-500 mt-20">
            <FileText className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <h3 className="text-lg font-medium mb-2">No documents uploaded</h3>
            <p className="text-sm">
              Upload PDF documents from the Chat page to get started.
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {documents.map((document) => (
              <div key={document.id} className="bg-white border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <FileText className="h-8 w-8 text-blue-600 mt-1" />
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">
                        {document.filename}
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Uploaded:{" "}
                        {new Date(document.upload_date).toLocaleDateString()}
                      </p>
                      <p className="text-sm text-gray-500">
                        Size: {formatFileSize(document.file_size)}
                      </p>

                      <div className="flex items-center space-x-4 mt-2">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(document.processing_status)}`}
                        >
                          {document.processing_status.charAt(0).toUpperCase() +
                            document.processing_status.slice(1)}
                        </span>

                        {document.processing_status === "processing" && (
                          <span className="text-xs text-gray-500">
                            Processing: {document.processed_pages}/
                            {document.total_pages} pages
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleDownload(document.id)}
                      className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteDocument(document.id)}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
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
