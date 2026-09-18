import { useEffect, useState } from "react";
import { ApiError, api } from "../lib/api";
import type { Playbook } from "../lib/types";
import { Button, Card, Input } from "./ui";

export function Playbooks() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [target, setTarget] = useState("");
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.playbooks().then(setPlaybooks).catch((e) => setError(String(e)));
  }, []);

  async function run(name: string) {
    setRunning(name);
    setError(null);
    setResult(null);
    try {
      setResult(await api.runPlaybook(name, target));
    } catch (e) {
      if (e instanceof ApiError && e.status === 423) setError("Locked — load a scope first.");
      else setError(String((e as { message?: string }).message ?? e));
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Root target">
        <Input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="example.com" />
        <p className="mt-2 text-xs text-slate-500">
          Playbooks chain steps and <b>re-gate every derived target</b> before any active step runs.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {playbooks.map((pb) => (
          <Card key={pb.name} title={pb.name}>
            <p className="text-sm text-slate-400">{pb.description}</p>
            <ol className="my-3 space-y-1 text-xs text-slate-500">
              {pb.steps.map((s) => (
                <li key={s.id}>
                  <span className="text-slate-300">{s.action}</span> {s.name}{" "}
                  <span className="text-slate-600">→ {s.targets}</span>
                </li>
              ))}
            </ol>
            <Button variant="primary" onClick={() => run(pb.name)} disabled={!target.trim() || running !== null}>
              {running === pb.name ? "Running…" : "Run playbook"}
            </Button>
          </Card>
        ))}
      </div>

      {error && <div className="text-sm text-red-400">⚠ {error}</div>}
      {result != null && (
        <Card title="Playbook result">
          <pre className="max-h-96 overflow-auto rounded bg-surface-0 p-3 text-xs text-slate-300">
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  );
}
