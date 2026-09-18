import { useEffect, useState } from "react";
import { Audit } from "./components/Audit";
import { Dashboard } from "./components/Dashboard";
import { Entities } from "./components/Entities";
import { Login } from "./components/Login";
import { Playbooks } from "./components/Playbooks";
import { Report } from "./components/Report";
import { ScopeGate } from "./components/ScopeGate";
import { Tools } from "./components/Tools";
import { Button } from "./components/ui";
import { Wordlists } from "./components/Wordlists";
import { useApp } from "./store";

const TABS = [
  "Dashboard",
  "OSINT",
  "Tools",
  "Playbooks",
  "Wordlists",
  "Audit",
  "Report",
] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const { token, status, role, refreshStatus, logout, killSwitch } = useApp();
  const [tab, setTab] = useState<Tab>("Dashboard");

  useEffect(() => {
    if (token) refreshStatus();
  }, [token, refreshStatus]);

  if (!token) return <Login />;
  if (!status) return <Splash text="Connecting to backend…" />;

  const locked = status.locked;

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        locked={locked}
        engagementRef={status.engagement?.engagement_ref ?? null}
        verified={status.engagement?.signature_verified ?? false}
        notAfter={status.engagement?.not_after ?? null}
        role={role}
        onKill={async () => {
          if (confirm("KILL SWITCH: cancel all jobs, revoke scope, and re-lock the app?")) {
            await killSwitch();
          }
        }}
        onLogout={logout}
      />

      {locked ? (
        <main className="flex-1">
          <ScopeGate onLoaded={refreshStatus} canLoad={role === "lead"} />
        </main>
      ) : (
        <>
          <nav className="flex gap-1 border-b border-surface-3 bg-surface-1 px-4">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-2.5 text-sm transition-colors ${
                  tab === t
                    ? "border-b-2 border-accent text-white"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {t}
              </button>
            ))}
          </nav>
          <main className="mx-auto w-full max-w-6xl flex-1 p-4">
            {tab === "Dashboard" && <Dashboard />}
            {tab === "OSINT" && <Entities />}
            {tab === "Tools" && <Tools />}
            {tab === "Playbooks" && <Playbooks />}
            {tab === "Wordlists" && <Wordlists />}
            {tab === "Audit" && <Audit />}
            {tab === "Report" && <Report />}
          </main>
        </>
      )}
    </div>
  );
}

function Header({
  locked,
  engagementRef,
  verified,
  notAfter,
  role,
  onKill,
  onLogout,
}: {
  locked: boolean;
  engagementRef: string | null;
  verified: boolean;
  notAfter: string | null;
  role: string | null;
  onKill: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b border-surface-3 bg-surface-1 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold tracking-tight text-white">
          Azami<span className="text-accent">·</span>
        </span>
        {locked ? (
          <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-semibold text-red-300">
            🔒 LOCKED — no active engagement
          </span>
        ) : (
          <span className="flex items-center gap-2 text-xs text-slate-400">
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-semibold text-emerald-300">
              {engagementRef}
            </span>
            {verified ? (
              <span className="text-emerald-400">✓ signed</span>
            ) : (
              <span className="text-amber-400">⚠ unsigned</span>
            )}
            {notAfter && <span>expires {new Date(notAfter).toLocaleString()}</span>}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {role && <span className="text-xs text-slate-500">role: {role}</span>}
        {!locked && role === "lead" && (
          <Button variant="danger" onClick={onKill}>
            ⏻ Kill switch
          </Button>
        )}
        <Button variant="ghost" onClick={onLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}

function Splash({ text }: { text: string }) {
  return <div className="flex min-h-screen items-center justify-center text-slate-500">{text}</div>;
}
