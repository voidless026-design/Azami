import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { WordlistStatus } from "../lib/types";
import { Badge, Button, Card } from "./ui";

export function Wordlists() {
  const [lists, setLists] = useState<WordlistStatus[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api.wordlists().then(setLists).catch((e) => setError(String(e)));
  }
  useEffect(refresh, []);

  async function install(name: string) {
    setBusy(name);
    setError(null);
    try {
      await api.installWordlist(name);
      refresh();
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title="Managed wordlists">
      {error && <div className="mb-2 text-sm text-red-400">⚠ {error}</div>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="pb-2">Name</th>
            <th className="pb-2">Category</th>
            <th className="pb-2">License</th>
            <th className="pb-2">Status</th>
            <th className="pb-2"></th>
          </tr>
        </thead>
        <tbody>
          {lists.map((w) => (
            <tr key={w.name} className="border-t border-surface-3">
              <td className="py-2 font-mono text-xs text-slate-200">{w.name}</td>
              <td className="py-2 text-slate-400">{w.category}</td>
              <td className="py-2 text-slate-500">{w.license}</td>
              <td className="py-2">
                {w.installed ? (
                  <Badge tone="good">installed ({(w.size_bytes / 1024).toFixed(0)} KB)</Badge>
                ) : (
                  <Badge>not installed</Badge>
                )}
              </td>
              <td className="py-2 text-right">
                {!w.installed && (
                  <Button onClick={() => install(w.name)} disabled={busy === w.name}>
                    {busy === w.name ? "Downloading…" : "Install"}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-slate-500">
        Lists are fetched on demand, checksum-verified, versioned, and mounted read-only into tool
        runners for reproducible runs.
      </p>
    </Card>
  );
}
