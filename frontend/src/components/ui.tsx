import type { ReactNode } from "react";

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="rounded-lg border border-surface-3 bg-surface-1 shadow-sm">
      {title && (
        <div className="flex items-center justify-between border-b border-surface-3 px-4 py-2.5">
          <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "default",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "default" | "primary" | "danger" | "ghost";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const styles: Record<string, string> = {
    default: "bg-surface-3 hover:bg-surface-2 text-slate-200",
    primary: "bg-accent hover:bg-emerald-400 text-surface-0 font-semibold",
    danger: "bg-red-600 hover:bg-red-500 text-white font-semibold",
    ghost: "bg-transparent hover:bg-surface-2 text-slate-400",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${styles[variant]}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-surface-3 bg-surface-0 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-accent ${props.className ?? ""}`}
    />
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}

const STATE_COLORS: Record<string, string> = {
  queued: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  running: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  succeeded: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  failed: "bg-red-500/20 text-red-300 border-red-500/40",
  cancelled: "bg-slate-500/20 text-slate-300 border-slate-500/40",
  timed_out: "bg-orange-500/20 text-orange-300 border-orange-500/40",
};

export function StateBadge({ state }: { state: string }) {
  const cls = STATE_COLORS[state] ?? "bg-surface-3 text-slate-300 border-surface-3";
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs ${cls}`}>
      {state === "running" && <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulseDot" />}
      {state}
    </span>
  );
}

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "warn" | "good" | "bad" }) {
  const tones: Record<string, string> = {
    default: "bg-surface-3 text-slate-300",
    warn: "bg-amber-500/20 text-amber-300",
    good: "bg-emerald-500/20 text-emerald-300",
    bad: "bg-red-500/20 text-red-300",
  };
  return <span className={`rounded px-2 py-0.5 text-xs ${tones[tone]}`}>{children}</span>;
}
