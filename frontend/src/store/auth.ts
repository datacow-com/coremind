import { create } from "zustand";

const STORAGE_KEY = "omnirag_auth_token";
const STORAGE_BASE = "omnirag_api_base";

type AuthState = {
  token: string | null;
  baseUrl: string | null;
  setToken: (t: string | null) => void;
  setBaseUrl: (u: string | null) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>((set) => {
  const saved =
    typeof localStorage !== "undefined"
      ? localStorage.getItem(STORAGE_KEY)
      : null;
  const savedBase =
    typeof localStorage !== "undefined"
      ? localStorage.getItem(STORAGE_BASE)
      : null;
  return {
    token: saved,
    baseUrl: savedBase,
    setToken: (t) => {
      if (t) localStorage.setItem(STORAGE_KEY, t);
      else localStorage.removeItem(STORAGE_KEY);
      set({ token: t });
    },
    setBaseUrl: (u) => {
      if (u) localStorage.setItem(STORAGE_BASE, u);
      else localStorage.removeItem(STORAGE_BASE);
      set({ baseUrl: u });
    },
    logout: () => {
      localStorage.removeItem(STORAGE_KEY);
      set({ token: null });
    },
  };
});

export const getAuthState = () => useAuthStore.getState();
