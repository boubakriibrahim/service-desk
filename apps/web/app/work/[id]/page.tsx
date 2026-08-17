"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, FileText, Play, Send, ShieldAlert, Wrench } from "lucide-react";
import AppShell, { InlineLoader, StatusBadge } from "@/components/AppShell";
import DocumentModal from "@/components/DocumentModal";
import { api, timeAgo } from "@/lib/api";
import { useDemoMode } from "@/lib/demo";
import type { Artifact } from "@/lib/types";

type Evidence = { id: string; title: string; section?: string | null; sensitivity: string; excerpt: string; document_id?: number | null };
type Message = { id: number; role: string; content: string; meta: { artifact?: Artifact; evidence?: Evidence[]; run_id?: number; action_id?: number; error?: string }; created_at: string };
type Action = { id: number; type: string; status: string; work_order_ref?: string | null; payload: Record<string, string>; evidence_ids: string[]; created_at: string };
type RunEvent = { id: number; kind: string; label: string; detail: Record<string, unknown>; created_at: string };
type WorkResponse = {
  item: { id: number; title: string; customer_name: string; asset_ref: string; status: string; context: Record<string, string>; updated_at: string };
  messages: Message[];
  actions: Action[];
  latest_run: { id: number; status: string; model?: string; provider?: string } | null;
  operations: { asset?: Record<string, string>; service_cases?: Array<Record<string, string>>; parts?: Array<Record<string, string | number>>; work_orders?: Array<Record<string, string>> };
  demo_task: string;
  security_demo_task: string;
};

export default function WorkDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const demo = useDemoMode();
  const [data, setData] = useState<WorkResponse | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [sideTab, setSideTab] = useState<"sources" | "activity">("sources");
  const [openDocId, setOpenDocId] = useState<number | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const fetchWork = useCallback(async () => {
    const result = await api<WorkResponse>(`/api/work/${id}`);
    const run = result.latest_run?.id
      ? await api<{ events: RunEvent[] }>(`/api/runs/${result.latest_run.id}`).catch(() => ({ events: [] }))
      : null;
    return { result, events: run?.events };
  }, [id]);
  const applyWork = useCallback(({ result, events }: { result: WorkResponse; events?: RunEvent[] }) => {
    setData(result);
    if (events) setEvents(events);
  }, []);
  const load = useCallback(async () => applyWork(await fetchWork()), [fetchWork, applyWork]);

  useEffect(() => {
    fetchWork()
      .then(applyWork)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load this work item"))
      .finally(() => setLoading(false));
  }, [fetchWork, applyWork]);

  const lastAssistant = useMemo(() => [...(data?.messages || [])].reverse().find((m) => m.role === "assistant" && m.meta?.artifact), [data]);
  const artifact = lastAssistant?.meta?.artifact;
  const evidence = lastAssistant?.meta?.evidence || [];
  const pendingAction = data?.actions.find((action) => action.status === "pending");
  const lastUser = useMemo(() => [...(data?.messages || [])].reverse().find((m) => m.role === "user"), [data]);
  const blocked = artifact?.title?.toLowerCase().includes("blocked") || false;
  const verdict = artifact?.security_signals?.verdict ?? (blocked ? "blocked" : "passed");
  const verdictLabel = verdict === "blocked" ? "Blocked" : verdict === "needs_review" ? "Needs review" : "Passed screening";

  async function submit(event?: FormEvent, value?: string) {
    event?.preventDefault();
    const content = (value ?? draft).trim();
    if (!content || busy) return;
    setBusy(true);
    setError("");
    setDraft("");
    setSideTab("activity");
    // The investigation runs synchronously server-side and can take a minute
    // with a real model. Poll for staged run events so the activity tab shows
    // live progress instead of a frozen page.
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const result = await api<WorkResponse>(`/api/work/${id}`);
        setData(result);
        if (result.latest_run?.id) {
          const run = await api<{ events: RunEvent[] }>(`/api/runs/${result.latest_run.id}`).catch(() => ({ events: [] }));
          setEvents(run.events);
        }
      } catch {
        /* keep polling until the investigation request resolves */
      }
    }, 4000);
    try {
      await api(`/api/work/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
      await load().catch(() => null);
    } finally {
      stopPolling();
      setBusy(false);
    }
  }

  const stage = busy ? (events.length > 0 ? events[events.length - 1].label : "Starting local security screening") : "";

  if (loading) {
    return <AppShell><div className="page"><InlineLoader label="Opening work item"/></div></AppShell>;
  }
  if (!data) {
    return (
      <AppShell>
        <div className="page">
          <div className="error-box" style={{ marginBottom: 18 }}>{error || "Could not load this work item"}</div>
          <Link className="button" href="/work"><ArrowLeft size={14}/> Back to work</Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="workspace-page">
        <header className="workspace-topbar">
          <Link className="back-link" href="/work" aria-label="Back to work"><ArrowLeft size={18}/></Link>
          <div className="workspace-title">
            <strong>{data.item.customer_name} / {data.item.asset_ref}</strong>
            <small>{data.item.title}</small>
          </div>
          <div className="spacer"/>
          <StatusBadge tone={blocked ? "warn" : pendingAction ? "warn" : "blue"}>{blocked ? "Blocked" : pendingAction ? "Approval needed" : data.item.status}</StatusBadge>
          {data.latest_run && <Link className="button small" href={`/runs/${data.latest_run.id}`}>View run <ArrowRight size={13}/></Link>}
        </header>

        <div className="workspace-grid">
          <section className="workspace-main">
            {lastUser ? (
              <div className="task-card">
                <div className="message-label">Assigned task · {timeAgo(lastUser.created_at)}</div>
                <p>{lastUser.content}</p>
              </div>
            ) : demo ? (
              <div className="task-card">
                <div className="message-label">Suggested scenarios</div>
                <p>{data.demo_task}</p>
                <div style={{ marginTop: 15, display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <button className="button primary" disabled={busy} onClick={() => submit(undefined, data.demo_task)}>
                    {busy ? <><Wrench size={15} className="spin-slow"/> Investigating…</> : <><Play size={15}/> Run investigation</>}
                  </button>
                  <button className="button" disabled={busy} onClick={() => submit(undefined, data.security_demo_task)}>
                    <ShieldAlert size={15}/> Try blocked request
                  </button>
                </div>
              </div>
            ) : (
              <div className="task-card">
                <div className="message-label">No task yet</div>
                <p>Describe the task in the box below to start an investigation.</p>
              </div>
            )}

            {error && <div className="error-box" style={{ marginBottom: 18 }}>{error}</div>}
            {busy && <div className="panel" style={{ marginBottom: 18 }}><div className="panel-body"><InlineLoader label={stage || "Investigation running"}/></div></div>}

            {artifact ? (
              <article className="artifact">
                <header className="artifact-head">
                  <div className="eyebrow">{blocked ? "Security review" : "Service brief"}</div>
                  <h2>{artifact.title}</h2>
                </header>
                <div className="artifact-summary">{artifact.summary}</div>
                {artifact.security_signals && (
                  <div className="decision-strip" style={blocked ? { background: "#fff8ed", borderColor: "#f0d6ad" } : undefined}>
                    <div><small>Screening verdict</small><strong>{verdictLabel}</strong></div>
                    <div><small>Request check</small><strong>{artifact.security_signals.provider === "laya" ? "Laya" : (artifact.security_signals.provider || "Checks")}</strong></div>
                    <div><small>Block</small><strong>{artifact.security_signals.block_probability != null ? `${Math.round(artifact.security_signals.block_probability * 100)}%` : "—"}</strong></div>
                  </div>
                )}
                {artifact.security_signals && (artifact.security_signals.request_category || artifact.security_signals.malicious_probability != null) && (
                  <div className="secondary-cell" style={{ marginTop: 6 }}><small>Screening detail: category {(artifact.security_signals.request_category || "benign").replaceAll("_", " ")}{artifact.security_signals.category_confidence != null ? ` (${Math.round(artifact.security_signals.category_confidence * 100)}%)` : ""} · malicious {artifact.security_signals.malicious_probability != null ? `${Math.round(artifact.security_signals.malicious_probability * 100)}%` : "—"}</small></div>
                )}
                {!blocked && artifact.decision_signals && (
                  <div className="decision-strip">
                    <div><small>Case suggestions</small><strong>{artifact.decision_signals.provider === "laya" ? "Laya" : "Service Desk"}</strong></div>
                    <div><small>Case type</small><strong>{(artifact.decision_signals.case_type || "unclassified").replaceAll("_", " ")}</strong></div>
                    <div><small>Priority</small><strong>{artifact.decision_signals.priority_score != null ? `${artifact.decision_signals.priority_score.toFixed(2)} / 2` : "—"}</strong></div>
                    <div><small>On-site signal</small><strong>{artifact.decision_signals.onsite_probability != null ? `${Math.round(artifact.decision_signals.onsite_probability * 100)}%` : "—"}</strong></div>
                  </div>
                )}
                {artifact.sections?.map((section) => (
                  <section className="artifact-section" key={section.heading}>
                    <h3>{section.heading}</h3>
                    <p>{section.body}</p>
                    {section.citations?.length > 0 && <div className="citation-row">{section.citations.map((citation) => <button key={citation} className="citation-chip" onClick={() => setSideTab("sources")}>{citation}</button>)}</div>}
                  </section>
                ))}
                <section className="artifact-section">
                  <h3>{blocked ? "Safe next steps" : "Next steps"}</h3>
                  <ol className="next-steps">{artifact.next_steps?.map((step) => <li key={step}>{step}</li>)}</ol>
                </section>
              </article>
            ) : (
              <div className="panel">
                <div className="empty-state"><strong>No report yet</strong>{demo ? "Run the sample case or try a blocked request. " : ""}The report and activity stay with this case.</div>
              </div>
            )}

            {pendingAction && (
              <div className="action-card">
                <div>
                  <strong>Service work order is ready for review</strong>
                  <p>{pendingAction.payload.summary}. The AI suggested it. Service Desk has not saved it.</p>
                </div>
                <Link className="button" href="/approvals">Review action <ArrowRight size={14}/></Link>
              </div>
            )}

            {data.actions.some((action) => action.status === "executed") && (
              <div className="action-card" style={{ borderColor: "#c9e6d3", background: "#f5fbf7" }}>
                <div><strong><CheckCircle2 size={14} style={{ verticalAlign: "-2px", marginRight: 5 }}/>Approved action executed</strong><p>{(() => {
                  const refs = data.actions.filter((a) => a.status === "executed" && a.work_order_ref).map((a) => a.work_order_ref as string);
                  return refs.length > 0 ? `Work ${refs.length > 1 ? "orders" : "order"} ${refs.join(", ")} now ${refs.length > 1 ? "exist" : "exists"} in the operational system.` : "The approved work order now exists in the operational system.";
                })()}</p></div>
              </div>
            )}

            {blocked && (
              <div className="action-card" style={{ borderColor: "#f0d6ad", background: "#fff9f0" }}>
                <div><strong><AlertTriangle size={14} style={{ verticalAlign: "-2px", marginRight: 5 }}/>Request stopped</strong><p>The app blocked this request before searching documents or writing an answer.</p></div>
              </div>
            )}
          </section>

          <aside className="workspace-side">
            <div className="side-sticky">
              <div className="side-tabs">
                <button className={sideTab === "sources" ? "active" : ""} onClick={() => setSideTab("sources")}>Sources</button>
                <button className={sideTab === "activity" ? "active" : ""} onClick={() => setSideTab("activity")}>Activity</button>
              </div>
              <div className="side-content">
                {sideTab === "sources" ? (
                  <>
                    {evidence.length > 0 ? evidence.map((source) => (
                      <button className="source-item clickable" key={source.id} onClick={() => setOpenDocId(source.document_id as number)} title="Open full document">
                        <strong><FileText size={13} style={{ verticalAlign: "-2px", marginRight: 5 }}/>{source.title}</strong>
                        <small>{source.id}{source.section ? ` · ${source.section}` : ""} · {source.sensitivity}</small>
                          <div className="source-excerpt">{source.excerpt}</div>
                        </button>
                    )) : (
                      <>
                        <div className="context-block"><div className="context-label">Asset</div><div className="context-value"><strong>{data.item.asset_ref}</strong><br/>{data.operations.asset?.model || "PX-400"} · {data.operations.asset?.firmware || "—"}</div></div>
                        <div className="context-block"><div className="context-label">Recent cases</div><div className="context-value">{data.operations.service_cases?.length || 0} service records available</div></div>
                        <div className="context-block"><div className="context-label">Parts</div><div className="context-value">{data.operations.parts?.map((p) => `${p.sku}: ${p.stock_qty}`).join(" · ") || "No matching stock"}</div></div>
                      </>
                    )}
                  </>
                ) : (
                  <>
                    {busy && <div className="activity-item"><span className="activity-dot"/><div><strong>Investigation running</strong><small>Local guard first, read-only tools second</small></div></div>}
                    {events.length === 0 && !busy && <div className="empty-state" style={{ padding: "30px 10px" }}><strong>No activity yet</strong>The steps taken during an investigation will appear here.</div>}
                    {events.map((event) => (
                      <div className="activity-item" key={event.id}>
                        <span className="activity-dot"/>
                        <div><strong>{event.label}</strong><small>{event.kind} · {timeAgo(event.created_at)}</small></div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          </aside>
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={submit}>
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask a follow-up about this customer, asset, evidence, or service history…" rows={1}/>
            <button className="button primary icon-button" aria-label="Send" disabled={busy || !draft.trim()}><Send size={16}/></button>
          </form>
          <div className="composer-hint">The app checks each request for unsafe instructions before searching or writing a report.</div>
        </div>
      </div>
      <DocumentModal documentId={openDocId} onClose={() => setOpenDocId(null)} />
    </AppShell>
  );
}
