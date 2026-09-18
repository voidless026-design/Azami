import { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Entity, Graph } from "../lib/types";
import { Badge, Button, Card, Input } from "./ui";

const TYPE_COLORS: Record<string, string> = {
  domain: "#34d399",
  host: "#22d3ee",
  ip: "#a78bfa",
  organization: "#f59e0b",
  location: "#f472b6",
  email: "#60a5fa",
};

export function Entities() {
  const [target, setTarget] = useState("");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  function refresh() {
    api.entities(filter || undefined).then(setEntities).catch(() => {});
    api.graph().then(setGraph).catch(() => {});
  }

  useEffect(refresh, [filter]);

  async function collect() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = (await api.collect(target)) as { entities: number; kind: string };
      setMsg(`Collected — ${r.entities} entities for ${r.kind} target.`);
      refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError(`Out of scope: ${JSON.stringify(e.detail)}`);
      else if (e instanceof ApiError && e.status === 423) setError("Locked — load a scope first.");
      else setError(String((e as { message?: string }).message ?? e));
    } finally {
      setBusy(false);
    }
  }

  const types = Array.from(new Set(entities.map((e) => e.type)));

  return (
    <div className="space-y-4">
      <Card title="Passive OSINT collection">
        <div className="flex gap-2">
          <Input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="example.com, 203.0.113.10, or alice@example.com"
          />
          <Button variant="primary" onClick={collect} disabled={busy || !target.trim()}>
            {busy ? "Collecting…" : "Collect"}
          </Button>
        </div>
        {msg && <div className="mt-2 text-sm text-emerald-400">{msg}</div>}
        {error && <div className="mt-2 text-sm text-red-400">⚠ {error}</div>}
        <p className="mt-2 text-xs text-slate-500">
          DNS · RDAP · certificate transparency · GeoIP — all scope-gated and audited.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          title={`Entities (${entities.length})`}
          right={
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="rounded border border-surface-3 bg-surface-0 px-2 py-1 text-xs text-slate-300"
            >
              <option value="">all types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          }
        >
          <div className="max-h-96 space-y-1.5 overflow-auto">
            {entities.length === 0 && <div className="text-sm text-slate-600">No entities yet.</div>}
            {entities.map((e) => (
              <div key={e.id} className="rounded border border-surface-3 px-2.5 py-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-slate-200">{e.dedup_key}</span>
                  <div className="flex items-center gap-1.5">
                    <Badge>{e.type}</Badge>
                    <span className="text-xs text-slate-500">
                      {(e.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Relationship graph">
          <GraphView graph={graph} />
        </Card>
      </div>
    </div>
  );
}

function GraphView({ graph }: { graph: Graph | null }) {
  if (!graph || graph.nodes.length === 0)
    return <div className="flex h-72 items-center justify-center text-sm text-slate-600">No graph yet.</div>;

  const W = 420;
  const H = 300;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 40;
  const pos = new Map<string, { x: number; y: number }>();
  graph.nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / graph.nodes.length;
    pos.set(n.id, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) });
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-72 w-full">
      {graph.edges.map((e, i) => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        if (!a || !b) return null;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#334155" strokeWidth={1} />;
      })}
      {graph.nodes.map((n) => {
        const p = pos.get(n.id)!;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={7} fill={TYPE_COLORS[n.type] ?? "#64748b"} />
            <title>
              {n.type}: {n.label}
            </title>
            <text x={p.x} y={p.y - 10} textAnchor="middle" fontSize={8} fill="#94a3b8">
              {n.label.length > 18 ? n.label.slice(0, 16) + "…" : n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
