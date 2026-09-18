import { useEffect, useRef, useState } from "react";
import { ApiError, api, jobSocketUrl } from "../lib/api";
import type { Job, JobEvent, ToolInfo } from "../lib/types";
import { Badge, Button, Card, Field, Input, StateBadge } from "./ui";

const DEFAULT_PARAMS: Record<string, object> = {
  nmap: { ports: "top1000", scan_type: "version", timing: 3 },
  gobuster: { mode: "dir", wordlist: "seclists-common-web-content", threads: 10 },
  hydra: { service: "ssh", userlist: "seclists-common-usernames", passlist: "seclists-common-passwords-10k" },
  john: { hash_ref: "captured.hashes", wordlist: "seclists-common-passwords-10k" },
  metasploit: { module: "auxiliary/scanner/portscan/tcp" },
  tcpdump: { interface: "eth0", count: 200 },
};

export function Tools() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [tool, setTool] = useState<string>("nmap");
  const [target, setTarget] = useState("");
  const [params, setParams] = useState<string>(JSON.stringify(DEFAULT_PARAMS.nmap, null, 2));
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const current = tools.find((t) => t.name === tool);

  useEffect(() => {
    api.tools().then(setTools).catch((e) => setError(String(e)));
    refreshJobs();
  }, []);

  useEffect(() => {
    setParams(JSON.stringify(DEFAULT_PARAMS[tool] ?? {}, null, 2));
  }, [tool]);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [lines]);

  function refreshJobs() {
    api.jobs().then((j) => setJobs(j.slice(0, 15))).catch(() => {});
  }

  function streamJob(job: Job) {
    setActiveJob(job);
    setLines([`— job ${job.id} (${job.tool} → ${job.target}) —`]);
    wsRef.current?.close();
    const ws = new WebSocket(jobSocketUrl(job.id));
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const e: JobEvent = JSON.parse(ev.data);
      if (e.type === "stdout" || e.type === "stderr") {
        setLines((l) => [...l, (e.type === "stderr" ? "! " : "") + e.data]);
      } else if (e.type === "state") {
        setLines((l) => [...l, `[state] ${e.data}`]);
        if (["succeeded", "failed", "cancelled", "timed_out"].includes(e.data)) {
          api.job(job.id).then(setActiveJob).catch(() => {});
          refreshJobs();
        }
      }
    };
    ws.onerror = () => setLines((l) => [...l, "[ws error]"]);
  }

  async function run(confirm = false) {
    setError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(params || "{}");
    } catch {
      setError("params must be valid JSON");
      return;
    }
    try {
      const job = await api.submitJob(tool, target, parsed, confirm);
      streamJob(job);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        if (window.confirm(`This is an INTRUSIVE action (${current?.required_action}). Confirm you are authorized to run it against ${target}?`)) {
          return run(true);
        }
        return;
      }
      if (e instanceof ApiError && e.status === 423) setError("Locked — load a scope first.");
      else if (e instanceof ApiError && e.status === 403) setError(`Out of scope: ${JSON.stringify(e.detail)}`);
      else setError(String((e as { message?: string }).message ?? e));
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <Card title="Run a tool">
          <div className="space-y-3">
            <Field label="Tool">
              <div className="flex flex-wrap gap-1.5">
                {tools.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => setTool(t.name)}
                    className={`rounded-md px-2.5 py-1 text-xs ${
                      tool === t.name ? "bg-accent text-surface-0 font-semibold" : "bg-surface-3 text-slate-300"
                    }`}
                  >
                    {t.name}
                    {t.intrusive && " ⚠"}
                  </button>
                ))}
              </div>
            </Field>
            {current && (
              <div className="text-xs text-slate-500">
                requires{" "}
                <Badge tone={current.intrusive ? "warn" : "default"}>{current.required_action}</Badge>{" "}
                {current.intrusive && "· needs per-run confirmation"}
              </div>
            )}
            <Field label="Target (must be in scope)">
              <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="api.example.com" />
            </Field>
            <Field label="Parameters (JSON)">
              <textarea
                value={params}
                onChange={(e) => setParams(e.target.value)}
                rows={6}
                spellCheck={false}
                className="w-full rounded-md border border-surface-3 bg-surface-0 p-2 font-mono text-xs text-slate-200 outline-none focus:border-accent"
              />
            </Field>
            {error && <div className="text-sm text-red-400">⚠ {error}</div>}
            <Button variant="primary" onClick={() => run(false)} disabled={!target.trim()}>
              ▶ Run {tool}
            </Button>
          </div>
        </Card>

        <Card title="Recent jobs">
          <div className="space-y-1.5">
            {jobs.length === 0 && <div className="text-sm text-slate-600">No jobs yet.</div>}
            {jobs.map((j) => (
              <button
                key={j.id}
                onClick={() => streamJob(j)}
                className="flex w-full items-center justify-between rounded border border-surface-3 px-2.5 py-1.5 text-left text-xs hover:bg-surface-2"
              >
                <span className="font-mono text-slate-300">
                  {j.tool} → {j.target}
                </span>
                <StateBadge state={j.state} />
              </button>
            ))}
          </div>
        </Card>
      </div>

      <Card
        title="Live output"
        right={activeJob ? <StateBadge state={activeJob.state} /> : undefined}
      >
        <div
          ref={logRef}
          className="h-72 overflow-auto rounded bg-surface-0 p-3 font-mono text-xs leading-relaxed text-slate-300"
        >
          {lines.length === 0 ? (
            <span className="text-slate-600">Run a tool to see live stdout stream here.</span>
          ) : (
            lines.map((l, i) => (
              <div key={i} className={l.startsWith("!") ? "text-red-400" : l.startsWith("[") ? "text-slate-500" : ""}>
                {l}
              </div>
            ))
          )}
        </div>
        {activeJob?.result && Object.keys(activeJob.result).length > 0 && (
          <div className="mt-3">
            <div className="mb-1 text-xs uppercase tracking-wide text-slate-500">Parsed result</div>
            <pre className="max-h-48 overflow-auto rounded bg-surface-0 p-3 text-xs text-slate-300">
              {JSON.stringify(activeJob.result, null, 2)}
            </pre>
          </div>
        )}
      </Card>
    </div>
  );
}
