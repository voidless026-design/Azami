import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, Card } from "./ui";

export function Report() {
  const [markdown, setMarkdown] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reportMarkdown().then(setMarkdown).catch((e) => setError(String(e)));
  }, []);

  function download() {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "azami-engagement-report.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card title="Engagement report" right={<Button onClick={download}>⬇ Download .md</Button>}>
      {error && <div className="text-sm text-red-400">{error}</div>}
      <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap rounded bg-surface-0 p-4 text-sm text-slate-300">
        {markdown || "Loading…"}
      </pre>
    </Card>
  );
}
