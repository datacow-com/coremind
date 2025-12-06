import { useEffect, useState } from "react";
import { Database, Plus, Filter, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import { z } from "zod";
import { useFormZod } from "@/hooks/useFormZod";
import { useToast } from "@/components/ui/toast-provider";

interface CollectionInfo {
  name?: string;
  count?: number;
  dim?: number;
  created_at?: number;
}

const KnowledgeBasesPage: React.FC = () => {
  const [kbs, setKbs] = useState<CollectionInfo[]>([]);
  const [q, setQ] = useState("");
  const { push } = useToast();

  const load = async () => {
    try {
      const r = await apiFetch("/api/kb");
      if (r.ok) {
        const d = await r.json();
        const cs = (d.kbs || []).map((k: any) => ({
          name: k.name || k.stats?.name || "unknown",
          count: k.stats?.chunk_count || 0,
          dim: k.stats?.embedding_dimension || 256,
          created_at: Date.now() / 1000,
        }));
        setKbs(cs);
      }
    } catch {}
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = kbs.filter((x) =>
    (x.name || "").toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Database className="h-5 w-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-800">知识库</h2>
            </div>
            <div className="flex items-center space-x-3">
              <div className="flex items-center border rounded px-2">
                <Search className="h-4 w-4 text-gray-400" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="搜索知识库"
                  className="px-2 py-1 text-sm outline-none"
                />
              </div>
              <button
                className="px-3 py-2 bg-gray-600 text-white rounded-md"
                onClick={load}
              >
                <Filter className="h-4 w-4 inline mr-1" /> 刷新
              </button>
              <CreateKBButton onCreated={load} />
            </div>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.length === 0 ? (
            <div className="text-sm text-gray-500">暂无知识库</div>
          ) : (
            filtered.map((kb) => (
              <Link
                to={`/kb/${encodeURIComponent(kb.name || "unknown")}`}
                key={kb.name}
                className="bg-white border rounded-lg p-4 hover:shadow"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 bg-blue-600 text-white rounded flex items-center justify-center">
                    {String(kb.name || "KB")
                      .slice(0, 1)
                      .toUpperCase()}
                  </div>
                  <div>
                    <div className="font-medium">{kb.name}</div>
                    <div className="text-xs text-gray-500">
                      {kb.count || 0} items • dim {kb.dim || 0}
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(
                        (kb.created_at || Date.now() / 1000) * 1000,
                      ).toLocaleString()}
                    </div>
                  </div>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBasesPage;

const CreateKBButton: React.FC<{ onCreated?: () => void }> = ({
  onCreated,
}) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  const schema = z.object({
    name: z.string().min(1, "名称必填"),
    desc: z.string().optional(),
    stack: z.enum(["cn", "en"]),
    backend: z.enum(["auto", "milvus", "qdrant", "elasticsearch", "local"]),
    collection: z.string().optional(),
  });

  const form = useFormZod(
    schema,
    { name: "", desc: "", stack: "cn", backend: "auto", collection: "" },
    async (v) => {
      setBusy(true);
      try {
        const r = await apiFetch("/api/kb/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: v.name,
            description: v.desc,
            stack: v.stack,
            vector_backend: v.backend,
            collection_name: v.collection || undefined,
          }),
        });
        if (r.ok) {
          push({ title: "创建成功", variant: "success" });
          setOpen(false);
          form.setValues({
            name: "",
            desc: "",
            stack: "cn",
            backend: "auto",
            collection: "",
          });
          onCreated?.();
        } else {
          push({
            title: "创建失败",
            description: r.statusText,
            variant: "error",
          });
        }
      } finally {
        setBusy(false);
      }
    },
  );
  return (
    <>
      <button
        className="px-3 py-2 bg-blue-600 text-white rounded-md"
        onClick={() => setOpen(true)}
      >
        <Plus className="h-4 w-4 inline mr-1" /> 创建知识库
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center">
          <div className="bg-white rounded-md shadow-lg w-[520px] p-4 space-y-3">
            <div className="text-lg font-medium">创建知识库</div>
            <div>
              <label className="block text-sm mb-1">名称</label>
              <input
                value={form.values.name}
                onChange={(e) => form.setField("name", e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="kb name"
              />
              {form.errors.name && (
                <p className="text-xs text-red-600">{form.errors.name}</p>
              )}
            </div>
            <div>
              <label className="block text-sm mb-1">描述</label>
              <input
                value={form.values.desc}
                onChange={(e) => form.setField("desc", e.target.value)}
                className="w-full border rounded px-3 py-2"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm mb-1">语言栈</label>
                <select
                  value={form.values.stack}
                  onChange={(e) =>
                    form.setField("stack", e.target.value as any)
                  }
                  className="w-full border rounded px-3 py-2"
                >
                  <option value="cn">中文</option>
                  <option value="en">英文</option>
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1">向量后端</label>
                <select
                  value={form.values.backend}
                  onChange={(e) =>
                    form.setField("backend", e.target.value as any)
                  }
                  className="w-full border rounded px-3 py-2"
                >
                  <option value="auto">自动</option>
                  <option value="milvus">Milvus</option>
                  <option value="qdrant">Qdrant</option>
                  <option value="elasticsearch">Elasticsearch</option>
                  <option value="local">本地</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm mb-1">集合名称（可选）</label>
              <input
                value={form.values.collection}
                onChange={(e) => form.setField("collection", e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="omnirag_<name>"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                className="px-3 py-2 text-sm border rounded"
                onClick={() => setOpen(false)}
                disabled={busy}
              >
                取消
              </button>
              <button
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded"
                onClick={form.submit}
                disabled={busy || !form.values.name}
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
