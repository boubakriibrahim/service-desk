from __future__ import annotations
import hashlib
import io
from pathlib import Path
from pypdf import PdfReader
from sqlalchemy.orm import Session
from app.models import Document, DocumentChunk
from app.services.embeddings import embed_text
from app.services.chunking import chunk_text


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix in {".md", ".markdown", ".txt"}:
        return data.decode("utf-8", errors="replace")
    raise ValueError("Supported formats: PDF, Markdown and plain text")


def create_document(
    db: Session,
    organization_id: int,
    source_id: int,
    title: str,
    filename: str,
    content_type: str,
    raw: bytes,
    access_scope: str,
    sensitivity: str,
) -> Document:
    text = extract_text(filename, raw)
    checksum = hashlib.sha256(raw).hexdigest()
    doc = Document(
        organization_id=organization_id,
        source_id=source_id,
        title=title,
        filename=filename,
        content_type=content_type,
        access_scope=access_scope,
        sensitivity=sensitivity,
        checksum=checksum,
        status="processing",
    )
    db.add(doc)
    db.flush()
    for ordinal, (section, body) in enumerate(chunk_text(text)):
        db.add(DocumentChunk(
            organization_id=organization_id,
            document_id=doc.id,
            ordinal=ordinal,
            text=body,
            section=section,
            access_scope=access_scope,
            sensitivity=sensitivity,
            embedding=embed_text(body),
        ))
    doc.status = "ready"
    db.commit()
    db.refresh(doc)
    return doc
