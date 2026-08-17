"use client";

import { useEffect, useState } from "react";
import { Cable, LockKeyhole, RotateCcw, Server } from "lucide-react";
import AppShell, { InlineLoader, PageTitle, StatusBadge } from "@/components/AppShell";
import { api } from "@/lib/api";

type SettingsData = {
  effective: { mode: string; model: string; base_url?: string | null; embedding_mode: string; embedding_model: string; decision_mode: string; decision_model: string; decision_base_url?: string | null };
  configured_endpoints: Array<{ id: number; name: string; kind: string; model: string; max_sensitivity: string; enabled: boolean; healthy: boolean; priority: number }>;
  routing_order: string[];
  demo_reset: boolean;
};

export default function SettingsPage() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [role, setRole] = useState("member");
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [resetResult, setResetResult] = useState("");
  useEffect(() => {
    api<SettingsData>("/api/settings/models").then(setData).catch((err) => setError(err instanceof Error ? err.message : "Could not load model settings"));
    api<{ user: { role: string } }>("/api/auth/me").then((me) => setRole(me.user.role)).catch(() => null);
  }, []);

  async function resetDemo() {
    if (!window.confirm("Reset demo state? This clears runs, messages, approvals and created work orders. Documents and users are kept.")) return;
    setResetting(true); setResetResult("");
    try {
      const result = await api<Record<string, number | boolean>>("/api/admin/reset-demo", { method: "POST" });
      const cleared = ["runs", "messages", "actions", "work_orders"].map((k) => `${result[k] ?? 0} ${k.replace("_", " ")}`).join(", ");
      setResetResult(`Demo reset: cleared ${cleared}.`);
    } catch (err) {
      setResetResult(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setResetting(false);
    }
  }

  return (
    <AppShell>
      <div className="page narrow">
        <PageTitle eyebrow="Administration" title="Models & access" description="Generation, the local Laya guard/decision layer, and embeddings are configured independently. Secrets stay outside the application database and UI." />
        {error && <div className="error-box">{error}</div>}
        {!data && !error && <InlineLoader label="Loading settings"/>}
        {data && (
          <div className="settings-grid">
            <section className="panel">
              <div className="panel-header"><h2><Server size={14} style={{ verticalAlign: "-2px", marginRight: 6 }}/>Effective model configuration</h2></div>
              <div className="panel-body">
                <dl style={{ margin: 0 }}>
                  <div className="key-value"><dt>AI mode</dt><dd><StatusBadge tone={data.effective.mode === "demo" ? "blue" : "good"}>{data.effective.mode}</StatusBadge></dd></div>
                  <div className="key-value"><dt>Generation model</dt><dd className="mono">{data.effective.model || "not configured"}</dd></div>
                  <div className="key-value"><dt>Base URL</dt><dd className="mono">{data.effective.base_url || "local deterministic provider"}</dd></div>
                  <div className="key-value"><dt>Local guard mode</dt><dd>{data.effective.decision_mode}</dd></div>
                  <div className="key-value"><dt>Local guard model</dt><dd className="mono">{data.effective.decision_model || "disabled"}</dd></div>
                  <div className="key-value"><dt>Local guard endpoint</dt><dd className="mono">{data.effective.decision_base_url || (data.effective.decision_mode === "demo" ? "local deterministic signals" : "—")}</dd></div>
                  <div className="key-value"><dt>Embedding mode</dt><dd>{data.effective.embedding_mode}</dd></div>
                  <div className="key-value"><dt>Embedding model</dt><dd className="mono">{data.effective.embedding_model || "not configured"}</dd></div>
                </dl>
                <div className="notice" style={{ marginTop: 14 }}><LockKeyhole size={14} style={{ verticalAlign: "-2px", marginRight: 5 }}/>Keys and credentials stay in environment/secret configuration and are never returned to this page. Local Laya routing and scoring happen inside the Docker stack when enabled.</div>
              </div>
            </section>
            <section className="panel">
              <div className="panel-header"><h2><Cable size={14} style={{ verticalAlign: "-2px", marginRight: 6 }}/>Routing order</h2></div>
              <div className="panel-body">
                <ol className="route-list">{data.routing_order.map((item) => <li key={item}>{item}</li>)}</ol>
                <p className="secondary-cell" style={{ lineHeight: 1.55, marginBottom: 0 }}>Privacy and authorization decide eligibility first. Health and optimization criteria only rank models that are already allowed.</p>
              </div>
            </section>
          </div>
        )}

        {data && data.configured_endpoints.length > 0 && (
          <section className="panel" style={{ marginTop: 18 }}>
            <div className="panel-header"><h2>Organization endpoints</h2></div>
            <div className="table-wrap"><table className="data-table"><thead><tr><th>Name</th><th>Kind</th><th>Model</th><th>Privacy ceiling</th><th>State</th></tr></thead><tbody>{data.configured_endpoints.map((endpoint) => <tr key={endpoint.id}><td className="primary-cell">{endpoint.name}</td><td>{endpoint.kind}</td><td className="mono">{endpoint.model}</td><td>{endpoint.max_sensitivity}</td><td><StatusBadge tone={endpoint.enabled && endpoint.healthy ? "good" : "warn"}>{endpoint.enabled && endpoint.healthy ? "healthy" : "unavailable"}</StatusBadge></td></tr>)}</tbody></table></div>
          </section>
        )}

        {["approver", "admin"].includes(role) && data?.demo_reset && (
          <section className="panel" style={{ marginTop: 18 }}>
            <div className="panel-header"><h2><RotateCcw size={14} style={{ verticalAlign: "-2px", marginRight: 6 }}/>Demo state</h2></div>
            <div className="panel-body">
              <p className="secondary-cell" style={{ lineHeight: 1.55 }}>Clears runs, messages, approvals and work orders created during the demo, and reopens work items. Users, documents and embeddings are kept.</p>
              <button className="button danger" onClick={resetDemo} disabled={resetting}>{resetting ? "Resetting…" : "Reset demo state"}</button>
              {resetResult && <div className="notice" style={{ marginTop: 12 }}>{resetResult}</div>}
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
