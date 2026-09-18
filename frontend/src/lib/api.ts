import type {
  AuditRecord,
  Decision,
  Engagement,
  Entity,
  Graph,
  Job,
  Playbook,
  Status,
  ToolInfo,
  WordlistStatus,
} from "./types";

const BASE = ""; // proxied to the backend in dev; same-origin in the packaged app.

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

let token: string | null = null;
export const setToken = (t: string | null) => {
  token = t;
};
export const getToken = () => token;

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(BASE + path, { method, headers, body: payload });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) throw new ApiError(resp.status, data?.detail ?? data);
  return data as T;
}

export const api = {
  async login(username: string, password: string): Promise<{ access_token: string; role: string }> {
    const form = new URLSearchParams({ username, password });
    const resp = await fetch(BASE + "/api/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data?.detail ?? data);
    return data;
  },

  status: () => request<Status>("GET", "/api/engagement/status"),
  loadScope: (scope_text: string, signature_b64?: string) =>
    request<Engagement>("POST", "/api/engagement/load", { scope_text, signature_b64 }),
  killSwitch: () => request<{ cancelled_jobs: number }>("POST", "/api/engagement/kill-switch"),
  scope: () => request<Record<string, unknown>>("GET", "/api/engagement/scope"),
  check: (target: string, action: string) =>
    request<Decision>("POST", "/api/engagement/check", { target, action }),

  tools: () => request<ToolInfo[]>("GET", "/api/tools"),
  submitJob: (tool: string, target: string, params: Record<string, unknown>, confirm_intrusive: boolean) =>
    request<Job>("POST", "/api/jobs", { tool, target, params, confirm_intrusive }),
  jobs: () => request<Job[]>("GET", "/api/jobs"),
  job: (id: string) => request<Job>("GET", `/api/jobs/${id}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>("POST", `/api/jobs/${id}/cancel`),

  collectors: () => request<{ name: string; applies_to: string[] }[]>("GET", "/api/osint/collectors"),
  collect: (target: string, sources?: string[]) =>
    request<Record<string, unknown>>("POST", "/api/osint/collect", { target, sources }),
  entities: (type?: string) =>
    request<Entity[]>("GET", "/api/entities" + (type ? `?type=${type}` : "")),
  graph: () => request<Graph>("GET", "/api/entities/graph"),

  playbooks: () => request<Playbook[]>("GET", "/api/playbooks"),
  runPlaybook: (name: string, target: string) =>
    request<Record<string, unknown>>("POST", `/api/playbooks/${name}/run`, { target }),

  wordlists: () => request<WordlistStatus[]>("GET", "/api/wordlists"),
  installWordlist: (name: string) =>
    request<Record<string, unknown>>("POST", `/api/wordlists/${name}/install`),

  audit: () => request<AuditRecord[]>("GET", "/api/audit?limit=300"),
  verifyAudit: () => request<{ ok: boolean; length: number; detail: string }>("GET", "/api/audit/verify"),
  report: () => request<Record<string, unknown>>("GET", "/api/report"),
  reportMarkdown: async (): Promise<string> => {
    const resp = await fetch(BASE + "/api/report/markdown", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return resp.text();
  },
};

export function jobSocketUrl(jobId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/ws/jobs/${jobId}?token=${encodeURIComponent(token ?? "")}`;
}
