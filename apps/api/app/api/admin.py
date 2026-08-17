from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.models import Action, AuditEvent, DemoWorkOrder, Message, Run, RunEvent, WorkItem
from app.security import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Seeded reference data that a demo reset must preserve.
SEED_WORK_ORDER_REF = "WO-1841"


@router.post("/reset-demo")
def reset_demo(member=Depends(require_role("approver", "admin")), db: Session = Depends(get_db)):
    """Wipe demo runtime state (runs, messages, actions, audit trail and any
    work orders created by approvals) while keeping users, organizations,
    documents and their embeddings. Used to rehearse the golden demo path."""
    if not get_settings().effective_enable_demo_reset:
        raise HTTPException(status_code=404, detail="Not found")
    org_id = member["organization_id"]
    db.rollback()

    counts = {}
    counts["audit_events"] = db.execute(delete(AuditEvent).where(AuditEvent.organization_id == org_id)).rowcount
    counts["actions"] = db.execute(delete(Action).where(Action.organization_id == org_id)).rowcount
    counts["messages"] = db.execute(delete(Message).where(Message.organization_id == org_id)).rowcount
    counts["run_events"] = db.execute(delete(RunEvent).where(RunEvent.organization_id == org_id)).rowcount
    counts["runs"] = db.execute(delete(Run).where(Run.organization_id == org_id)).rowcount
    counts["work_orders"] = db.execute(delete(DemoWorkOrder).where(
        DemoWorkOrder.organization_id == org_id,
        DemoWorkOrder.work_order_ref != SEED_WORK_ORDER_REF,
    )).rowcount

    works = db.scalars(select(WorkItem).where(WorkItem.organization_id == org_id)).all()
    for work in works:
        work.status = "open"
    counts["work_items_reopened"] = len(works)
    db.commit()
    return {"ok": True, **counts}
