from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.helpers import iso
from app.config import get_settings
from app.db import get_db
from app.models import Document, DocumentChunk, Source
from app.security import current_member
from app.services.documents import create_document

router = APIRouter(prefix="/api/sources", tags=["sources"])
settings = get_settings()


@router.get("")
def list_sources(member=Depends(current_member), db: Session = Depends(get_db)):
    org_id = member["organization_id"]
    sources = db.scalars(select(Source).where(Source.organization_id == org_id).order_by(Source.created_at.asc())).all()
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    docs = db.scalars(select(Document).where(
        Document.organization_id == org_id,
        Document.access_scope.in_(allowed_scopes),
    ).order_by(Document.created_at.desc())).all()
    chunk_counts = dict(db.execute(
        select(DocumentChunk.document_id, func.count(DocumentChunk.id)).where(DocumentChunk.organization_id == org_id).group_by(DocumentChunk.document_id)
    ).all())
    return {
        "sources": [{"id": s.id, "name": s.name, "kind": s.kind, "status": s.status, "config": s.config} for s in sources],
        "documents": [{
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "content_type": d.content_type,
            "access_scope": d.access_scope,
            "sensitivity": d.sensitivity,
            "status": d.status,
            "chunks": chunk_counts.get(d.id, 0),
            "created_at": iso(d.created_at),
        } for d in docs],
    }


@router.post("/upload")
def upload_source(
    title: str = Form(...),
    access_scope: str = Form("service"),
    sensitivity: str = Form("internal"),
    file: UploadFile = File(...),
    member=Depends(current_member),
    db: Session = Depends(get_db),
):
    if member["membership"].role not in {"engineer", "approver", "admin"}:
        raise HTTPException(status_code=403, detail="You cannot add sources")
    if access_scope not in set((member["membership"].scopes or []) + ["public"]):
        raise HTTPException(status_code=403, detail="You cannot upload into that access scope")
    if sensitivity not in {"public", "internal", "restricted"}:
        raise HTTPException(status_code=400, detail="Invalid sensitivity")
    raw = file.file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Uploads are limited to 8 MB")
    source = db.scalar(select(Source).where(
        Source.organization_id == member["organization_id"],
        Source.kind == "files",
    ))
    if not source:
        raise HTTPException(status_code=500, detail="File source is not configured")
    Path(settings.file_storage_path).mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.txt").name
    (Path(settings.file_storage_path) / f"{member['organization_id']}-{safe_name}").write_bytes(raw)
    try:
        doc = create_document(
            db, member["organization_id"], source.id, title, safe_name,
            file.content_type or "application/octet-stream", raw, access_scope, sensitivity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": doc.id, "title": doc.title, "status": doc.status}


@router.get("/documents/{document_id}")
def read_document(document_id: int, member=Depends(current_member), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    doc = db.scalar(select(Document).where(
        Document.id == document_id,
        Document.organization_id == member["organization_id"],
        Document.access_scope.in_(allowed_scopes),
    ))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = db.scalars(select(DocumentChunk).where(
        DocumentChunk.document_id == doc.id,
    ).order_by(DocumentChunk.ordinal.asc())).all()
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "access_scope": doc.access_scope,
        "sensitivity": doc.sensitivity,
        "status": doc.status,
        "created_at": iso(doc.created_at),
        "chunks": [{"ordinal": c.ordinal, "section": c.section, "text": c.text} for c in chunks],
    }


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, member=Depends(current_member), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    doc = db.scalar(select(Document).where(
        Document.id == document_id,
        Document.organization_id == member["organization_id"],
        Document.access_scope.in_(allowed_scopes),
    ))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if member["membership"].role not in {"approver", "admin"}:
        raise HTTPException(status_code=403, detail="Only an approver can remove a source in the demo")
    db.delete(doc)
    db.commit()
    return {"ok": True}
