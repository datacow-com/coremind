import { getAuthState } from "@/store/auth";

const DEFAULT_TIMEOUT = 30_000;

const buildUrl = (input: string) => {
  const base = getAuthState().baseUrl?.replace(/\/+$/, "") || "";
  if (!input.startsWith("http")) {
    const path = input.startsWith("/") ? input : `/${input}`;
    return `${base}${path}`;
  }
  return input;
};

const withTimeout = (signal: AbortSignal | undefined, ms: number) => {
  if (!ms) return signal;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }
  (controller.signal as any).__timer = timer;
  return controller.signal;
};

export interface ApiOptions extends RequestInit {
  timeoutMs?: number;
  rawUrl?: boolean;
}

export const apiFetch = async (input: string, init: ApiOptions = {}) => {
  const {
    timeoutMs = DEFAULT_TIMEOUT,
    rawUrl = false,
    headers,
    ...rest
  } = init;
  const url = rawUrl ? input : buildUrl(input);
  const controllerSignal = withTimeout(init.signal, timeoutMs);
  const token = getAuthState().token;
  const mergedHeaders: HeadersInit = {
    ...(headers || {}),
  };
  if (token) {
    (mergedHeaders as any).Authorization = `Bearer ${token}`;
  }
  const resp = await fetch(url, {
    ...rest,
    headers: mergedHeaders,
    signal: controllerSignal,
  });
  return resp;
};

// New API Functions for V4 Pipeline
export const runIngest = async (data: {
  file_path: string;
  kb_name: string;
  strategy_config: any;
  task_id?: string;
}) => {
  return apiFetch("/api/ingest/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
};

export const runChat = async (data: {
  query: string;
  kb_name: string;
  history: any[];
  strategy_config: any;
}) => {
  return apiFetch("/api/chat/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
};

export const apiJson = async <T = any>(
  input: string,
  init: ApiOptions = {},
): Promise<{ ok: boolean; status: number; data?: T; error?: any }> => {
  try {
    const res = await apiFetch(input, init);
    const status = res.status;
    const ok = res.ok;
    const data = await res
      .clone()
      .json()
      .catch(() => undefined);
    if (!ok && status === 401) {
      // 触发全局登出
      getAuthState().logout();
    }
    return { ok, status, data };
  } catch (error) {
    return { ok: false, status: 0, error };
  }
};

export const buildSseRequest = (input: string, init: ApiOptions = {}) => {
  const token = getAuthState().token;
  const url = init.rawUrl ? input : buildUrl(input);
  const headers: HeadersInit = { ...(init.headers || {}) };
  if (token) {
    (headers as any).Authorization = `Bearer ${token}`;
  }
  return { url, headers };
};
