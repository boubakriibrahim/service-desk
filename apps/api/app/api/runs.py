from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.helpers import iso
from app.db import get_db
from app.models import Run, RunEvent, WorkItem
from app.security import current_member

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{run_id}")
def run_detail(run_id: int, member=Depends(current_member), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    run = db.scalar(select(Run).join(WorkItem, WorkItem.id == Run.work_item_id).where(
        Run.id == run_id,
        Run.organization_id == member["organization_id"],
        WorkItem.access_scope.in_(allowed_scopes),
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = db.scalars(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.created_at.asc())).all()
    return {
        "run": {
            "id": run.id,
            "work_item_id": run.work_item_id,
            "status": run.status,
            "task": run.task,
            "provider": run.provider,
            "model": run.model,
            "route_reason": run.route_reason,
            "latency_ms": run.latency_ms,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "error": run.error,
            "created_at": iso(run.created_at),
            "completed_at": iso(run.completed_at),
        },
        "events": [{
            "id": e.id,
            "kind": e.kind,
            "label": e.label,
            "detail": e.detail,
            "created_at": iso(e.created_at),
        } for e in events],
    }
