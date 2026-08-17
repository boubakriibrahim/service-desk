"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Box, Clock3, Database, FileSearch, Gauge, Shield, Wrench } from "lucide-react";
import AppShell, { InlineLoader, PageTitle, StatusBadge } from "@/components/AppShell";
import { api, timeAgo } from "@/lib/api";

type Run = {
  id: number; work_item_id: number; status: string; task: string; provider?: string | null; model?: string | null;
  route_reason?: string | null; latency_ms?: number | null; input_tokens?: number | null; output_tokens?: number | null;
  error?: string | null; created_at: string; completed_at?: string | null;
};
type Event = { id: number; kind: string; label: string; detail: Record<string, unknown>; created_at: string };

const icons: Record<string, React.ReactNode> = {
  retrieval: <FileSearch size={15}/>,
  tool: <Database size={15}/>,
  model: <Gauge size={15}/>,
  decision: <Gauge size={15}/>,
  artifact: <Box size={15}/>,
  action: <Shield size={15}/>,
  error: <Wrench size={15}/>,
};

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ run: Run; events: Event[] }>(`/api/runs/${params.id}`)
      .then((data) => { setRun(data.run); setEvents(data.events); })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load run"));
  }, [params.id]);

  return (
    <AppShell>
      <div className="page narrow">
        <Link href={run ? `/work/${run.work_item_id}` : "/work"} className="button ghost small" style={{ marginBottom: 15, paddingLeft: 0 }}><ArrowLeft size={14}/> Back to work</Link>
        <PageTitle eyebrow={run ? `Run #${run.id}` : "Run"} title="Activity" description="See the steps the app took to prepare its answer." action={run && <StatusBadge tone={run.status === "completed" ? "good" : run.status === "failed" ? "danger" : "warn"}>{run.status}</StatusBadge>} />
        {error && <div className="error-box">{error}</div>}
        {!run && !error && <InlineLoader label="Loading run"/>}
        {run && (
          <>
            <section className="panel" style={{ marginBottom: 18 }}>
              <div className="panel-body">
                <div className="message-label">Task</div>
                <div style={{ fontSize: 15, lineHeight: 1.6, marginBottom: 20 }}>{run.task}</div>
                <dl className="payload-box" style={{ margin: 0 }}>
                  <dt>Provider</dt><dd>{run.provider || "—"}</dd>
                  <dt>Model</dt><dd className="mono">{run.model || "—"}</dd>
                  <dt>Route reason</dt><dd>{run.route_reason || "—"}</dd>
                  <dt>Model latency</dt><dd>{run.latency_ms != null ? `${run.latency_ms} ms` : "Not reported"}</dd>
                  <dt>Tokens</dt><dd>{run.input_tokens != null ? `${run.input_tokens} in / ${run.output_tokens ?? "?"} out` : "Provider did not report usage"}</dd>
                </dl>
              </div>
            </section>
            <section className="panel">
              <div className="panel-header"><h2>Activity</h2><span className="secondary-cell">{events.length} events</span></div>
              <div className="panel-body" style={{ paddingTop: 10, paddingBottom: 10 }}>
                {events.map((event) => (
                  <div key={event.id} style={{ display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 10, alignItems: "start", padding: "11px 0", borderBottom: "1px solid #ecece9" }}>
                    <div style={{ width: 28, height: 28, display: "grid", placeItems: "center", borderRadius: 7, border: "1px solid #dedfdc", color: "#666d75" }}>{icons[event.kind] || <Clock3 size={15}/>}</div>
                    <div><strong style={{ fontSize: 12.5 }}>{event.label}</strong>{Object.keys(event.detail || {}).length > 0 && <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0", color: "#747a82", fontSize: 10.5, fontFamily: "ui-monospace, monospace" }}>{JSON.stringify(event.detail, null, 2)}</pre>}</div>
                    <small className="secondary-cell">{timeAgo(event.created_at)}</small>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
