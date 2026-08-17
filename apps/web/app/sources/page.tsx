"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Database, FilePlus2, FileText, UploadCloud } from "lucide-react";
import AppShell, { InlineLoader, PageTitle, StatusBadge } from "@/components/AppShell";
import DocumentModal from "@/components/DocumentModal";
import { api, timeAgo } from "@/lib/api";

type Source = { id: number; name: string; kind: string; status: string; config: Record<string, unknown> };
type Document = { id: number; title: string; filename: string; content_type: string; access_scope: string; sensitivity: string; status: string; chunks: number; created_at: string };

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [openDocId, setOpenDocId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const applySources = useCallback((data: { sources: Source[]; documents: Document[] }) => {
    setSources(data.sources);
    setDocuments(data.documents);
  }, []);
  const load = useCallback(async () => applySources(await api<{ sources: Source[]; documents: Document[] }>("/api/sources")), [applySources]);

  useEffect(() => {
    api<{ sources: Source[]; documents: Document[] }>("/api/sources")
      .then(applySources)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load sources"))
      .finally(() => setLoading(false));
  }, [applySources]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    form.set("file", file);
    setBusy(true);
    setError("");
    try {
      await api("/api/sources/upload", { method: "POST", body: form });
      setShowUpload(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }



  return (
    <AppShell>
      <div className="page">
        <PageTitle
          eyebrow="Knowledge & data"
          title="Sources"
          description="Browse the sample manuals and service records. The app checks what you can see before searching."
          action={<button className="button primary" onClick={() => setShowUpload(true)}><FilePlus2 size={15}/> Add document</button>}
        />

        {error && <div className="error-box" style={{ marginBottom: 18 }}>{error}</div>}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 14, marginBottom: 22 }}>
          {sources.map((source) => (
            <section className="panel" key={source.id}>
              <div className="panel-body" style={{ display: "flex", gap: 13, alignItems: "flex-start" }}>
                <div style={{ width: 34, height: 34, display: "grid", placeItems: "center", border: "1px solid #dedfdc", borderRadius: 7, background: "#fafaf8" }}>
                  {source.kind === "postgresql" ? <Database size={16}/> : <FileText size={16}/>} 
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}><strong>{source.name}</strong><StatusBadge tone="good">{source.status}</StatusBadge></div>
                  <div style={{ color: "#747a82", fontSize: 12, marginTop: 5 }}>{source.kind === "postgresql" ? "Seeded operational records · read-only query path" : "PDF, Markdown and text documents"}</div>
                </div>
              </div>
            </section>
          ))}
        </div>

        <section className="panel">
          <div className="panel-header"><h2>Indexed documents</h2><span className="secondary-cell">{documents.length} documents</span></div>
          {loading ? <div className="panel-body"><InlineLoader label="Loading documents"/></div> : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Document</th><th>Access</th><th>Sensitivity</th><th>Chunks</th><th>Added</th></tr></thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id}>
                      <td><button className="doc-table-title" onClick={() => setOpenDocId(doc.id)} title="Open full document" style={{ background: "none", border: 0, padding: 0, textAlign: "left", cursor: "pointer", font: "inherit", color: "inherit" }}><div className="primary-cell">{doc.title}</div><div className="secondary-cell mono" style={{ marginTop: 3 }}>{doc.filename}</div></button></td>
                      <td><StatusBadge>{doc.access_scope}</StatusBadge></td>
                      <td><StatusBadge tone={doc.sensitivity === "restricted" ? "warn" : "neutral"}>{doc.sensitivity}</StatusBadge></td>
                      <td>{doc.chunks}</td>
                      <td className="secondary-cell">{timeAgo(doc.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <DocumentModal documentId={openDocId} onClose={() => setOpenDocId(null)} />
      {showUpload && (
        <div className="modal-backdrop" onMouseDown={() => !busy && setShowUpload(false)}>
          <form className="modal" onSubmit={upload} onMouseDown={(e) => e.stopPropagation()}>
            <div className="modal-head"><h2>Add a service document</h2><button type="button" className="button ghost small" onClick={() => setShowUpload(false)}>Close</button></div>
            <div className="modal-body">
              <div className="form-grid">
                <div className="field" style={{ gridColumn: "1 / -1" }}><label>Title</label><input className="input" name="title" required placeholder="PX-400 troubleshooting note"/></div>
                <div className="field"><label>Access scope</label><select className="select" name="access_scope" defaultValue="service"><option value="service">service</option><option value="engineering">engineering</option><option value="public">public</option></select></div>
                <div className="field"><label>Sensitivity</label><select className="select" name="sensitivity" defaultValue="internal"><option value="internal">internal</option><option value="public">public</option><option value="restricted">restricted</option></select></div>
                <div className="field" style={{ gridColumn: "1 / -1" }}><label>File</label><input className="input" ref={fileRef} type="file" accept=".pdf,.md,.markdown,.txt" required style={{ paddingTop: 7 }}/><small className="secondary-cell">PDF, Markdown or text · 8 MB max</small></div>
              </div>
              <div className="form-actions"><button type="button" className="button" onClick={() => setShowUpload(false)}>Cancel</button><button className="button primary" disabled={busy}>{busy ? "Indexing…" : <><UploadCloud size={15}/> Upload & index</>}</button></div>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
