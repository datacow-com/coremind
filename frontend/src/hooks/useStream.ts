import { useCallback, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";

type StreamOpts = {
  onEvent?: (data: any) => void;
  onError?: (err: any) => void;
  onDone?: () => void;
};

const parseChunks = (buf: string, emit: (d: any) => void) => {
  const parts = buf.split("\n\n");
  const rest = parts.pop() || "";
  for (const part of parts) {
    const line = part.trim();
    const dataLine = line
      .split("\n")
      .find((l) => l.startsWith("data:"))
      ?.replace("data:", "")
      .trim();
    if (!dataLine) continue;
    try {
      emit(JSON.parse(dataLine));
    } catch {
      emit(dataLine);
    }
  }
  return rest;
};

export const useStream = () => {
  const [running, setRunning] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const toast = useToast();

  const runStream = useCallback(
    async (url: string, init: RequestInit = {}, opts: StreamOpts = {}) => {
      if (running) return;
      const controller = new AbortController();
      controllerRef.current = controller;
      setRunning(true);
      try {
        const res = await apiFetch(url, { ...init, signal: controller.signal });
        if (!res.ok || !res.body) {
          const msg = `流式请求失败 (${res.status})`;
          toast.push({ title: "请求失败", description: msg, variant: "error" });
          opts.onError?.(new Error(msg));
          setRunning(false);
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const r = await reader.read();
          if (r.done) break;
          buffer += decoder.decode(r.value, { stream: true });
          buffer = parseChunks(buffer, (d) => opts.onEvent?.(d));
        }
      } catch (err) {
        toast.push({
          title: "流式中断",
          description: err instanceof Error ? err.message : String(err),
          variant: "error",
        });
        opts.onError?.(err);
      } finally {
        setRunning(false);
        opts.onDone?.();
      }
    },
    [running, toast],
  );

  const abort = useCallback(() => {
    controllerRef.current?.abort();
    setRunning(false);
  }, []);

  return { running, runStream, abort };
};
