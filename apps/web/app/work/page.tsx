"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowUpRight, CirclePlus } from "lucide-react";
import { useRouter } from "next/navigation";
import AppShell, { InlineLoader, PageTitle, StatusBadge } from "@/components/AppShell";
import { api, timeAgo } from "@/lib/api";
import { useDemoMode } from "@/lib/demo";
import type { WorkItem } from "@/lib/types";

export default function WorkPage() {
  const router = useRouter();
  const demo = useDemoMode();
  const [items, setItems] = useState<WorkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api<{ items: WorkItem[] }>("/api/work")
      .then((data) => setItems(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load work"))
      .finally(() => setLoading(false));
  }, []);

  async function createWork(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setCreating(true);
    setError("");
    try {
      const created = await api<{ id: number }>("/api/work", {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          customer_name: form.get("customer_name"),
          asset_ref: form.get("asset_ref"),
        }),
      });
      router.push(`/work/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create work");
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <div className="page">
        <PageTitle
          eyebrow="Service operations"
          title="Work"
          description="Evidence-heavy customer work, kept in one place from investigation through approved follow-up."
          action={<button className="button" onClick={() => setShowNew(true)}><CirclePlus size={15}/> New work</button>}
        />

        <section className="panel work-list-panel">
          <div className="work-list-head"><span>Work item</span><span>Customer</span><span>Status</span><span>Updated</span><span/></div>
          {loading && <div className="panel-body"><InlineLoader label="Loading work"/></div>}
          {error && <div className="panel-body"><div className="error-box">{error}</div></div>}
          {!loading && !error && items.length === 0 && <div className="empty-state"><strong>No work yet</strong>Create a work item when a real case needs investigation.</div>}
          {items.map((item) => (
            <Link className="work-link" href={`/work/${item.id}`} key={item.id}>
              <div className="work-link-title"><strong>{item.title}</strong><small className="mono">{item.asset_ref}</small></div>
              <div><span>{item.customer_name}</span><small>{item.context?.site || "Customer site"}</small></div>
              <div><StatusBadge tone={item.pending_actions ? "warn" : item.status === "open" ? "blue" : "neutral"}>{item.pending_actions ? `${item.pending_actions} approval` : item.status}</StatusBadge></div>
              <div className="secondary-cell">{timeAgo(item.updated_at)}</div>
              <ArrowUpRight size={15} color="#8b9198"/>
            </Link>
          ))}
        </section>

        {demo && (
          <div style={{ marginTop: 18 }} className="notice">
            <strong>Demo:</strong> open the Northstar Foods case and run the seeded escalation request. The engineer can investigate and propose a work order; the manager account can approve the write.
          </div>
        )}
      </div>
      {showNew && (
        <div className="modal-backdrop" onMouseDown={() => !creating && setShowNew(false)}>
          <form className="modal" onSubmit={createWork} onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-head"><h2>New service work</h2><button type="button" className="button ghost small" onClick={() => setShowNew(false)}>Close</button></div>
            <div className="modal-body">
              <div className="field" style={{ marginBottom: 13 }}><label>Title</label><input className="input" name="title" required defaultValue={demo ? "Customer service investigation" : undefined}/></div>
              <div className="form-grid">
                <div className="field"><label>Customer</label><input className="input" name="customer_name" required defaultValue={demo ? "Northstar Foods" : undefined}/></div>
                <div className="field"><label>Asset reference</label><input className="input mono" name="asset_ref" required defaultValue={demo ? "NSF-PX400-L4" : undefined}/></div>
              </div>
              <div className="form-actions"><button type="button" className="button" onClick={() => setShowNew(false)}>Cancel</button><button className="button primary" disabled={creating}>{creating ? "Creating…" : "Create work"}</button></div>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
