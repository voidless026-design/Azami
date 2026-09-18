import { useState } from "react";
import { ApiError, api } from "../lib/api";
import { Button, Card, Field, Input } from "./ui";

export function ScopeGate({ onLoaded, canLoad }: { onLoaded: () => void; canLoad: boolean }) {
  // Quick-start form state (no YAML required).
  const [targets, setTargets] = useState("");
  const [name, setName] = useState("");
  const [activeScan, setActiveScan] = useState(true);
  const [activeTesting, setActiveTesting] = useState(false);
  const [exploitation, setExploitation] = useState(false);
  const [days, setDays] = useState(30);

  const [advanced, setAdvanced] = useState(false);
  const [scope, setScope] = useState("");
  const [sig, setSig] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function parseTargets(): string[] {
    return targets
      .split(/[\n,]+/)
      .map((t) => t.trim())
      .filter(Boolean);
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await api.quickstart({
        targets: parseTargets(),
        client_name: name || undefined,
        allow_active_scan: activeScan,
        allow_active_testing: activeTesting,
        allow_exploitation: exploitation,
        days_valid: days,
      });
      onLoaded();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadYaml() {
    setBusy(true);
    setError(null);
    try {
      await api.loadScope(scope, sig || undefined);
      onLoaded();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4">
      <div className="rounded-lg border border-surface-3 bg-surface-1 p-4">
        <h2 className="text-lg font-semibold text-slate-200">Start an engagement</h2>
        <p className="mt-1 text-sm text-slate-400">
          Name the target(s) you're authorized to assess and choose what's allowed. Azami then gates
          every action to these targets and records them in the audit log. No YAML needed.
        </p>
      </div>

      {!canLoad && (
        <p className="rounded bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          Your role can't start an engagement — a <b>lead</b> operator must. (Signed in as the
          default <code>admin</code>? That account is a lead; if you just reloaded, this clears once
          your session re-syncs.)
        </p>
      )}

      <Card title="Quick start">
        <div className="space-y-3">
          <Field label="Targets (one per line, or comma-separated)">
            <textarea
              value={targets}
              onChange={(e) => setTargets(e.target.value)}
              placeholder={"example.com\n203.0.113.0/24\n10.0.0.5"}
              spellCheck={false}
              rows={4}
              className="w-full rounded-md border border-surface-3 bg-surface-0 p-3 font-mono text-sm text-slate-200 outline-none focus:border-accent"
            />
          </Field>
          <Field label="Engagement name (optional)">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Example Corp assessment" />
          </Field>

          <div className="flex flex-wrap gap-4 text-sm">
            <Toggle label="Passive OSINT" checked disabled hint="always on" />
            <Toggle label="Active scan (nmap/gobuster)" checked={activeScan} onChange={setActiveScan} />
            <Toggle label="Active testing (hydra/john/tcpdump)" checked={activeTesting} onChange={setActiveTesting} />
            <Toggle label="Exploitation (metasploit)" checked={exploitation} onChange={setExploitation} />
          </div>

          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span>Valid for</span>
            <input
              type="number"
              min={1}
              value={days}
              onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
              className="w-20 rounded-md border border-surface-3 bg-surface-0 px-2 py-1 text-slate-200 outline-none focus:border-accent"
            />
            <span>days</span>
          </div>

          {(activeTesting || exploitation) && (
            <p className="rounded bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              Intrusive actions enabled — only turn these on for targets you are explicitly
              authorized to test. Each intrusive run still asks for confirmation.
            </p>
          )}

          {error && <div className="text-sm text-red-400">⚠ {error}</div>}
          <Button
            variant="primary"
            onClick={start}
            disabled={busy || !canLoad || parseTargets().length === 0}
          >
            {busy ? "Starting…" : "Authorize & start"}
          </Button>
        </div>
      </Card>

      <button
        onClick={() => setAdvanced((a) => !a)}
        className="text-xs text-slate-500 hover:text-slate-300"
      >
        {advanced ? "▾" : "▸"} Advanced: paste a signed YAML scope
      </button>
      {advanced && (
        <Card title="Load a scope file (YAML)">
          <div className="space-y-3">
            <textarea
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="schema_version: 1 …"
              spellCheck={false}
              rows={10}
              className="w-full rounded-md border border-surface-3 bg-surface-0 p-3 font-mono text-xs text-slate-200 outline-none focus:border-accent"
            />
            <Input
              value={sig}
              onChange={(e) => setSig(e.target.value)}
              placeholder="detached ed25519 signature (base64) — required in production"
            />
            <Button variant="default" onClick={loadYaml} disabled={busy || !canLoad || !scope.trim()}>
              Verify & load YAML scope
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange?: (v: boolean) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <label className={`flex items-center gap-2 ${disabled ? "opacity-60" : "cursor-pointer"}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
        className="h-4 w-4 accent-emerald-400"
      />
      <span className="text-slate-300">{label}</span>
      {hint && <span className="text-xs text-slate-600">({hint})</span>}
    </label>
  );
}

function errMsg(e: unknown): string {
  if (e instanceof ApiError) return typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail);
  return String((e as { message?: string })?.message ?? e);
}
