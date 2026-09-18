import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import { Card } from "./ui";

interface Report {
  entities_total: number;
  entities_by_type: Record<string, number>;
  findings_by_severity: Record<string, number>;
  jobs_by_state: Record<string, number>;
  audit: { ok: boolean; length: number; detail: string };
}

const SEV_COLORS: Record<string, string> = {
  critical: "#f43f5e",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#38bdf8",
  info: "#64748b",
};

export function Dashboard() {
  const [report, setReport] = useState<Report | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .report()
      .then((r) => setReport(r as unknown as Report))
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-red-400">{err}</div>;
  if (!report) return <div className="text-slate-500">Loading…</div>;

  const entityData = Object.entries(report.entities_by_type).map(([name, value]) => ({ name, value }));
  const sevData = Object.entries(report.findings_by_severity)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));
  const findingsTotal = Object.values(report.findings_by_severity).reduce((a, b) => a + b, 0);
  const jobsRunning = report.jobs_by_state.running ?? 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Entities" value={report.entities_total} />
        <Stat label="Findings" value={findingsTotal} />
        <Stat label="Jobs running" value={jobsRunning} />
        <Stat
          label="Audit chain"
          value={report.audit.ok ? "intact" : "BROKEN"}
          tone={report.audit.ok ? "good" : "bad"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card title="Attack surface — entities by type">
          {entityData.length === 0 ? (
            <Empty />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={entityData}>
                <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#171e27", border: "1px solid #1e2732" }} />
                <Bar dataKey="value" fill="#34d399" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Findings by severity">
          {sevData.length === 0 ? (
            <Empty />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={sevData} dataKey="value" nameKey="name" outerRadius={90} label>
                  {sevData.map((d) => (
                    <Cell key={d.name} fill={SEV_COLORS[d.name] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#171e27", border: "1px solid #1e2732" }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: "good" | "bad" }) {
  const color = tone === "bad" ? "text-red-400" : tone === "good" ? "text-emerald-400" : "text-white";
  return (
    <div className="rounded-lg border border-surface-3 bg-surface-1 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function Empty() {
  return <div className="flex h-[240px] items-center justify-center text-sm text-slate-600">No data yet — run some recon.</div>;
}
