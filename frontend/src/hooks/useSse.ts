import { useEffect, useRef } from "react";
import { buildSseRequest } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";

type Options = {
  onData?: (evt: any) => void;
  onError?: (err: any) => void;
};

export const useSse = (url: string | null, opts: Options = {}) => {
  const { onData, onError } = opts;
  const sourceRef = useRef<EventSource | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (!url) return;
    const req = buildSseRequest(url);
    // EventSource 不允许自定义 headers，若后端需要 token 需走 fetch+reader。这里仅用于公共 SSE（若后端需 Auth，应改为 fetch 流模式）。
    // 为保留 token 能力，可用 polyfill（未引入），此处先直接用原生 EventSource。
    sourceRef.current = new EventSource(req.url);
    const src = sourceRef.current;

    const onMessage = (ev: MessageEvent) => {
      if (onData) {
        try {
          onData(JSON.parse(ev.data));
        } catch {
          onData(ev.data);
        }
      }
    };
    const onErr = (e: any) => {
      toast.push({
        title: "SSE 连接中断",
        description: "请重试或检查网络/权限",
        variant: "error",
      });
      onError?.(e);
    };

    src.addEventListener("message", onMessage);
    src.addEventListener("error", onErr);

    return () => {
      src.removeEventListener("message", onMessage);
      src.removeEventListener("error", onErr);
      src.close();
    };
  }, [url, onData, onError, toast]);
};
