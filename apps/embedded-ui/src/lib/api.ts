const BASE_URL = "/api";

let token: string | null = null;

export function setToken(t: string) {
  token = t;
  localStorage.setItem("omnirag_token", t);
}

export function getToken() {
  if (token) return token;
  const t = localStorage.getItem("omnirag_token");
  token = t;
  return t;
}

function headers(extra?: Record<string, string>) {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  if (extra) Object.assign(h, extra);
  return h;
}

export async function apiGet<T>(path: string) {
  const res = await fetch(`${BASE_URL}${path}`, { headers: headers() });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, body: unknown) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as T;
}

export async function apiDelete(path: string) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getDemoToken() {
  const res = await fetch(`${BASE_URL}/auth/demo`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  const t = data?.token || data;
  setToken(typeof t === "string" ? t : "");
  return t as string;
}
