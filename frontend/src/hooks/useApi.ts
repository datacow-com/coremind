import { useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/ui/toast-provider";

export const useApi = () => {
  const toast = useToast();

  const client = useMemo(() => {
    const json = async <T = any>(
      input: string,
      init?: RequestInit,
    ): Promise<{ ok: boolean; status: number; data?: T; error?: any }> => {
      try {
        const res = await apiFetch(input, init);
        const status = res.status;
        const data = await res.clone().json().catch(() => undefined);
        if (!res.ok) {
          toast.push({
            title: `请求失败 (${status})`,
            description: data?.detail || res.statusText || "网络错误",
            variant: "error",
          });
        }
        return { ok: res.ok, status, data };
      } catch (error: any) {
        toast.push({
          title: "网络错误",
          description: error?.message || String(error),
          variant: "error",
        });
        return { ok: false, status: 0, error };
      }
    };
    const text = async (
      input: string,
      init?: RequestInit,
    ): Promise<{ ok: boolean; status: number; data?: string; error?: any }> => {
      try {
        const res = await apiFetch(input, init);
        const status = res.status;
        const data = await res.clone().text().catch(() => undefined);
        if (!res.ok) {
          toast.push({
            title: `请求失败 (${status})`,
            description: res.statusText || "网络错误",
            variant: "error",
          });
        }
        return { ok: res.ok, status, data };
      } catch (error: any) {
        toast.push({
          title: "网络错误",
          description: error?.message || String(error),
          variant: "error",
        });
        return { ok: false, status: 0, error };
      }
    };
    return { json, text };
  }, [toast]);

  return { ...client, toast };
};
