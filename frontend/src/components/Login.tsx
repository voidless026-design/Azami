import { useState } from "react";
import { useApp } from "../store";
import { Button, Field, Input } from "./ui";

export function Login() {
  const login = useApp((s) => s.login);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError("Login failed — check credentials.");
      console.error(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border border-surface-3 bg-surface-1 p-6">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">
            Azami<span className="text-accent">·</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">Authorized reconnaissance console</div>
        </div>
        <Field label="Operator">
          <Input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </Field>
        <Field label="Password">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <div className="text-sm text-red-400">{error}</div>}
        <Button type="submit" variant="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="text-center text-xs text-slate-600">
          Default dev credentials: admin / changeme
        </p>
      </form>
    </div>
  );
}
