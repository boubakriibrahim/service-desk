"use client";

import { useCallback, useEffect, useState } from "react";
import { FileText, X } from "lucide-react";
import { StatusBadge } from "@/components/AppShell";
import { api } from "@/lib/api";

type DocChunk = { ordinal: number; section?: string | null; text: string };
type DocData = {
  id: number; title: string; filename: string; content_type: string;
  access_scope: string; sensitivity: string; status: string;
  chunks: DocChunk[];
};

function renderInline(text: string, keyPrefix: string) {
  // **bold**, *italic*, `code` — dependency-free inline formatting.
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={key}>{part.slice(1, -1)}</code>;
    return <span key={key}>{part}</span>;
  });
}

function Markdown({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n\s*\n/);
  const nodes: React.ReactNode[] = [];
  let list: string[] = [];
  const flushList = () => {
    if (list.length > 0) {
      nodes.push(<ul key={`ul-${nodes.length}`}>{list.map((item, i) => <li key={i}>{renderInline(item, `li-${nodes.length}-${i}`)}</li>)}</ul>);
      list = [];
    }
  };
  blocks.forEach((block, b) => {
    const trimmed = block.trim();
    if (!trimmed) return;
    const lines = trimmed.split("\n").map((l) => l.trim());
    if (lines.every((l) => /^([-*]|\d+\.)\s+/.test(l))) {
      flushList();
      list = lines.map((l) => l.replace(/^([-*]|\d+\.)\s+/, ""));
      flushList();
      return;
    }
    flushList();
    if (/^###\s+/.test(trimmed)) nodes.push(<h3 key={b}>{renderInline(trimmed.replace(/^###\s+/, ""), `h-${b}`)}</h3>);
    else if (/^##\s+/.test(trimmed)) nodes.push(<h2 key={b}>{renderInline(trimmed.replace(/^##\s+/, ""), `h-${b}`)}</h2>);
    else if (/^#\s+/.test(trimmed)) nodes.push(<h1 key={b}>{renderInline(trimmed.replace(/^#\s+/, ""), `h-${b}`)}</h1>);
    else if (/^(-{3,}|\*{3,})$/.test(trimmed)) nodes.push(<hr key={b} />);
    else nodes.push(<p key={b}>{renderInline(trimmed.replace(/\n/g, " "), `p-${b}`)}</p>);
  });
  flushList();
  return <>{nodes}</>;
}

/** Show a section heading only where the section changes; untitled chunks continue the previous one. */
function headingFlags(chunks: DocChunk[]): boolean[] {
  let last: string | null = null;
  return chunks.map((chunk) => {
    const show = !!chunk.section && chunk.section !== last;
    last = chunk.section || last;
    return show;
  });
}

export default function DocumentModal({ documentId, onClose }: { documentId: number | null; onClose: () => void }) {
  // Results are keyed by document so a late response for a previous document is never shown.
  const [loaded, setLoaded] = useState<{ id: number; data?: DocData; error?: string } | null>(null);
  const current = loaded && loaded.id === documentId ? loaded : null;
  const data = current?.data ?? null;
  const error = current?.error ?? "";
  // Forget the document on close, so reopening it never shows an earlier copy while it reloads.
  const close = useCallback(() => {
    setLoaded(null);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (documentId == null) return;
    let active = true;
    api<DocData>(`/api/sources/documents/${documentId}`)
      .then((doc) => { if (active) setLoaded({ id: documentId, data: doc }); })
      .catch((err) => { if (active) setLoaded({ id: documentId, error: err instanceof Error ? err.message : "Could not load document" }); });
    return () => { active = false; };
  }, [documentId]);

  useEffect(() => {
    if (documentId == null) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [documentId, close]);

  if (documentId == null) return null;

  const showHeadings = data ? headingFlags(data.chunks) : [];
  return (
    <div className="modal-backdrop" onMouseDown={close}>
      <div className="modal doc-modal" role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
            <FileText size={17} style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <h2 style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{data?.title || "Loading document…"}</h2>
              {data && <div className="secondary-cell mono" style={{ fontSize: 11 }}>{data.filename} · {data.chunks.length} sections</div>}
            </div>
          </div>
          <button type="button" className="button ghost small" onClick={close} aria-label="Close document"><X size={15} /></button>
        </div>
        <div className="modal-body doc-modal-body">
          {error && <div className="error-box">{error}</div>}
          {!data && !error && <div className="secondary-cell">Loading document…</div>}
          {data && (
            <>
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                <StatusBadge>{data.access_scope}</StatusBadge>
                <StatusBadge tone={data.sensitivity === "restricted" ? "warn" : "neutral"}>{data.sensitivity}</StatusBadge>
                <StatusBadge tone={data.status === "ready" ? "good" : "neutral"}>{data.status}</StatusBadge>
              </div>
              <article className="md-body">
                {data.chunks.map((chunk, i) => {
                  return (
                    <div key={chunk.ordinal}>
                      {showHeadings[i] && <h2>{chunk.section}</h2>}
                      <Markdown text={chunk.text} />
                    </div>
                  );
                })}
              </article>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
