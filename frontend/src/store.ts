import { create } from "zustand";
import { api, setToken } from "./lib/api";
import type { Role, Status } from "./lib/types";

interface AppState {
  token: string | null;
  role: Role | null;
  status: Status | null;
  error: string | null;
  login: (u: string, p: string) => Promise<void>;
  logout: () => void;
  refreshStatus: () => Promise<void>;
  killSwitch: () => Promise<void>;
}

const STORAGE_KEY = "azami.token";

function loadToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export const useApp = create<AppState>((set, get) => ({
  token: loadToken(),
  role: null,
  status: null,
  error: null,

  login: async (username, password) => {
    set({ error: null });
    const { access_token, role } = await api.login(username, password);
    setToken(access_token);
    try {
      localStorage.setItem(STORAGE_KEY, access_token);
    } catch {
      /* ignore */
    }
    set({ token: access_token, role: role as Role });
    await get().refreshStatus();
  },

  logout: () => {
    setToken(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    set({ token: null, role: null, status: null });
  },

  refreshStatus: async () => {
    try {
      const status = await api.status();
      set({ status });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  killSwitch: async () => {
    await api.killSwitch();
    await get().refreshStatus();
  },
}));

// Restore token into the api client on module load.
const existing = loadToken();
if (existing) setToken(existing);
