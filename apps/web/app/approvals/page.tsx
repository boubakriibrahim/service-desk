"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, ExternalLink, ShieldCheck, X } from "lucide-react";
import AppShell, { InlineLoader, PageTitle, StatusBadge } from "@/components/AppShell";
import { api, timeAgo } from "@/lib/api";
import { useDemoMode } from "@/lib/demo";

type Action = {
  id: number; work_item_id: number; run_id: number; type: string; status: string;
  work_order_ref?: string | null;
  payload: Record<string, string>; evidence_ids: string[]; created_at: string; rejection_reason?: string | null;
};

export default function ApprovalsPage() {
  const demo = useDemoMode();
  const [items, setItems] = useState<Action[]>([]);
  const [role, setRole] = useState("member");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const fetchActions = useCallback(() => api<{ items: Action[] }>("/api/actions").then((data) => data.items), []);
  const load = useCallback(async () => setItems(await fetchActions()), [fetchActions]);

  useEffect(() => {
    Promise.all([fetchActions(), api<{ user: { role: string } }>("/api/auth/me")])
      .then(([actions, me]) => { setItems(actions); setRole(me.user.role); })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load approvals"))
      .finally(() => setLoading(false));
  }, [fetchActions]);

  async function approve(id: number) {
    setBusy(id); setError("");
    try {
      const result = await api<{ ok: boolean; status: string; work_order_ref: string }>(`/api/actions/${id}/approve`, { method: "POST" });
      setItems((prev) => prev.map((a) => (a.id === id ? { ...a, status: "executed", work_order_ref: result.work_order_ref } : a)));
      await load();
    }
    catch (err) { setError(err instanceof Error ? err.message : "Approval failed"); }
    finally { setBusy(null); }
  }

  async function reject(id: number) {
    const reason = prompt("Reason for rejecting this action?");
    if (!reason) return;
    setBusy(id); setError("");
    try { await api(`/api/actions/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Rejection failed"); }
    finally { setBusy(null); }
  }

  return (
    <AppShell>
      <div className="page narrow">
        <PageTitle eyebrow="Guarded actions" title="Approvals" description="The model can prepare a proposal. Backend authorization, current-state validation and a human decision control the write." />
        {error && <div className="error-box" style={{ marginBottom: 18 }}>{error}</div>}
        {!loading && !["approver", "admin"].includes(role) && <div className="notice" style={{ marginBottom: 18 }}>You can inspect proposed actions, but only an approver can authorize the external write.{demo && " Sign in with the seeded manager account to complete the demo."}</div>}
        <section className="panel">
          <div className="panel-header"><h2>Action requests</h2><span className="secondary-cell">{items.filter((x) => x.status === "pending").length} pending</span></div>
          {loading && <div className="panel-body"><InlineLoader label="Loading approvals"/></div>}
          {!loading && items.length === 0 && <div className="empty-state"><strong>No approvals</strong>{demo ? "Run the Northstar investigation to create the seeded work-order proposal." : "Work orders proposed by an investigation appear here for approval."}</div>}
          {items.map((action) => (
            <div className="approval-card" key={action.id}>
              <div className="approval-row">
                <div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 5 }}><ShieldCheck size={15}/><h3>{action.payload.summary || "Service work order"}</h3></div>
                  <p>Proposed from run #{action.run_id} · {timeAgo(action.created_at)}</p>
                </div>
                <StatusBadge tone={action.status === "executed" ? "good" : action.status === "pending" ? "warn" : action.status === "rejected" ? "danger" : "neutral"}>{action.status}</StatusBadge>
              </div>
              <dl className="payload-box">
                <dt>Action</dt><dd className="mono">{action.type}</dd>
                <dt>Asset</dt><dd>{action.payload.asset_ref}</dd>
                <dt>Requested work</dt><dd>{action.payload.requested_work}</dd>
                <dt>Evidence</dt><dd>{action.evidence_ids?.length ? action.evidence_ids.join(", ") : "No document citation required"}</dd>
                <dt>Execution policy</dt><dd>Approval required · current work state is revalidated before write</dd>
                {action.status === "executed" && action.work_order_ref && <><dt>Work order</dt><dd className="mono">{action.work_order_ref} · open in the operational system</dd></>}
              </dl>
              {action.status === "pending" && (
                <div className="approval-actions">
                  <a className="button" href={`/runs/${action.run_id}`}>Inspect run <ExternalLink size={13}/></a>
                  {["approver", "admin"].includes(role) && <>
                    <button className="button danger" onClick={() => reject(action.id)} disabled={busy === action.id}><X size={14}/> Reject</button>
                    <button className="button primary" onClick={() => approve(action.id)} disabled={busy === action.id}><Check size={14}/> {busy === action.id ? "Executing…" : "Approve & execute"}</button>
                  </>}
                </div>
              )}
              {action.rejection_reason && <div className="notice" style={{ marginTop: 12 }}>Rejected: {action.rejection_reason}</div>}
            </div>
          ))}
        </section>
      </div>
    </AppShell>
  );
}
