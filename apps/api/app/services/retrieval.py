from __future__ import annotations
from collections import defaultdict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Document, DocumentChunk
from app.services.embeddings import embed_text

SENSITIVITY_ORDER = {"public": 0, "internal": 1, "restricted": 2}


def retrieve(db: Session, organization_id: int, scopes: list[str], query: str, limit: int = 6) -> list[dict]:
    allowed_scopes = list(set(scopes + ["public"]))
    query_embedding = embed_text(query)

    base_filters = (
        DocumentChunk.organization_id == organization_id,
        DocumentChunk.access_scope.in_(allowed_scopes),
    )

    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    dense_rows = db.execute(
        select(DocumentChunk, Document, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*base_filters)
        .order_by(distance)
        .limit(14)
    ).all()

    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(func.to_tsvector("english", DocumentChunk.text), tsquery)
    lexical_rows = db.execute(
        select(DocumentChunk, Document, rank.label("rank"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*base_filters, rank > 0)
        .order_by(rank.desc())
        .limit(14)
    ).all()

    fused: dict[int, float] = defaultdict(float)
    rows_by_id: dict[int, tuple[DocumentChunk, Document]] = {}
    for position, row in enumerate(dense_rows, start=1):
        chunk, doc, _ = row
        fused[chunk.id] += 1 / (60 + position)
        rows_by_id[chunk.id] = (chunk, doc)
    for position, row in enumerate(lexical_rows, start=1):
        chunk, doc, _ = row
        fused[chunk.id] += 1 / (60 + position)
        rows_by_id[chunk.id] = (chunk, doc)

    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:limit]
    results = []
    for chunk_id, score in ordered:
        chunk, doc = rows_by_id[chunk_id]
        results.append({
            "id": f"SRC-{chunk.id}",
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "title": doc.title,
            "filename": doc.filename,
            "section": chunk.section,
            "page": chunk.page,
            "text": chunk.text,
            "sensitivity": chunk.sensitivity,
            "access_scope": chunk.access_scope,
            "score": round(score, 6),
        })
    return results


def max_sensitivity(items: list[dict]) -> str:
    if not items:
        return "internal"
    return max((i.get("sensitivity", "internal") for i in items), key=lambda value: SENSITIVITY_ORDER.get(value, 1))
