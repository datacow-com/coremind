import { useState } from "react";
import { getDemoToken } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState<string>("");
  async function ensure() {
    try {
      await getDemoToken();
      setStatus("已获取 demo token");
    } catch (e: unknown) {
      setStatus(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <div className="p-4 space-y-4">
      <div className="text-2xl font-semibold">模型网关配置</div>
      <div className="space-x-2">
        <a href="/providers" className="underline">Providers</a>
        <a href="/bindings" className="underline">Bindings</a>
        <a href="/dashboard" className="underline">Dashboard</a>
        <a href="/audit" className="underline">Audit</a>
      </div>
      <div className="space-x-2">
        <button onClick={ensure} className="border px-4 py-2">获取 Demo Token</button>
        <span>{status}</span>
      </div>
    </div>
  );
}
