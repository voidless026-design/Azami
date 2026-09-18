import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { AuditRecord } from "../lib/types";
import { Card } from "./ui";

export function Audit() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [chain, setChain] = useState<{ ok: boolean; length: number; detail: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.audit().then(setRecords).catch((e) => setError(String(e)));
    api.verifyAudit().then(setChain).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      {chain && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            chain.ok
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
              : "border-red-500/30 bg-red-500/5 text-red-300"
          }`}
        >
          {chain.ok ? "✓" : "✗"} Audit chain {chain.ok ? "intact" : "BROKEN"} — {chain.length} records
          <span className="text-slate-500"> · {chain.detail}</span>
        </div>
      )}
      {error && <div className="text-sm text-red-400">{error}</div>}
      <Card title="Audit trail (newest first)">
        <div className="max-h-[32rem] overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-1">
              <tr className="text-left uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-2">#</th>
                <th className="pb-2 pr-2">Time</th>
                <th className="pb-2 pr-2">Action</th>
                <th className="pb-2 pr-2">Target</th>
                <th className="pb-2 pr-2">Decision</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {records.map((r) => {
                const denied = r.scope_decision.startsWith("deny");
                return (
                  <tr key={r.seq} className="border-t border-surface-3">
                    <td className="py-1 pr-2 text-slate-600">{r.seq}</td>
                    <td className="py-1 pr-2 text-slate-500">
                      {new Date(r.ts).toLocaleTimeString()}
                    </td>
                    <td className="py-1 pr-2 text-slate-300">{r.action}</td>
                    <td className="py-1 pr-2 text-slate-400">{r.target ?? "—"}</td>
                    <td className={`py-1 pr-2 ${denied ? "text-red-400" : "text-emerald-400"}`}>
                      {r.scope_decision}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
