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
const ROLE_KEY = "azami.role";

function loadStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export const useApp = create<AppState>((set, get) => ({
  token: loadStored(STORAGE_KEY),
  role: (loadStored(ROLE_KEY) as Role | null) ?? null,
  status: null,
  error: null,

  login: async (username, password) => {
    set({ error: null });
    const { access_token, role } = await api.login(username, password);
    setToken(access_token);
    store(STORAGE_KEY, access_token);
    store(ROLE_KEY, role);
    set({ token: access_token, role: role as Role });
    await get().refreshStatus();
  },

  logout: () => {
    setToken(null);
    store(STORAGE_KEY, null);
    store(ROLE_KEY, null);
    set({ token: null, role: null, status: null });
  },

  refreshStatus: async () => {
    try {
      // Re-derive the role from the token so it survives a page reload.
      if (!get().role) {
        try {
          const me = await api.me();
          store(ROLE_KEY, me.role);
          set({ role: me.role as Role });
        } catch {
          /* token may be invalid; status call below will surface it */
        }
      }
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
const existing = loadStored(STORAGE_KEY);
if (existing) setToken(existing);
