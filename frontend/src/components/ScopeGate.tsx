import { useState } from "react";
import { api } from "../lib/api";
import { Button, Card, Field } from "./ui";

const PLACEHOLDER = `schema_version: 1
engagement:
  id: ENG-2026-0142
  client_name: Example Corp
  assessing_org: Your Security Firm
  authorization_ref: SOW-2026-0142
time_window:
  not_before: "2026-01-01T00:00:00Z"
  not_after: "2026-12-31T23:59:59Z"
in_scope:
  - name: web
    domains: ["example.com", "*.example.com"]
    allowed_actions: {passive: true, active_scan: true}
`;

export function ScopeGate({ onLoaded, canLoad }: { onLoaded: () => void; canLoad: boolean }) {
  const [scope, setScope] = useState("");
  const [sig, setSig] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      await api.loadScope(scope, sig || undefined);
      onLoaded();
    } catch (e: unknown) {
      setError(String((e as { message?: string })?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
        <h2 className="text-lg font-semibold text-red-300">🔒 The console is locked</h2>
        <p className="mt-1 text-sm text-slate-400">
          Azami performs no action against any target until a signed Rules-of-Engagement scope is
          loaded and verified. Every action is then gated against this scope and written to a
          tamper-evident audit log.
        </p>
      </div>

      <Card title="Load engagement scope">
        {!canLoad && (
          <p className="mb-3 rounded bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
            Your role cannot load scopes — a <b>lead</b> operator must do this.
          </p>
        )}
        <div className="space-y-3">
          <Field label="Scope file (YAML)">
            <textarea
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder={PLACEHOLDER}
              spellCheck={false}
              rows={16}
              className="w-full rounded-md border border-surface-3 bg-surface-0 p-3 font-mono text-xs text-slate-200 outline-none focus:border-accent"
            />
          </Field>
          <Field label="Detached signature (base64, optional in dev)">
            <input
              value={sig}
              onChange={(e) => setSig(e.target.value)}
              placeholder="ed25519 signature over the scope bytes"
              className="w-full rounded-md border border-surface-3 bg-surface-0 px-3 py-1.5 font-mono text-xs text-slate-200 outline-none focus:border-accent"
            />
          </Field>
          {error && <div className="text-sm text-red-400">⚠ {error}</div>}
          <Button variant="primary" onClick={load} disabled={busy || !canLoad || !scope.trim()}>
            {busy ? "Verifying…" : "Verify & load scope"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
