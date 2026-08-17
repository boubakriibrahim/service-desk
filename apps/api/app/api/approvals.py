from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.helpers import iso
from app.db import get_db
from app.models import Action, AuditEvent, DemoWorkOrder, WorkItem
from app.schemas import RejectActionRequest
from app.security import current_member, require_role

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _work_order_ref(db: Session, action: Action) -> str | None:
    if action.status != "executed":
        return None
    ref = f"WO-{1900 + action.id}"
    exists = db.scalar(select(DemoWorkOrder.id).where(DemoWorkOrder.work_order_ref == ref))
    return ref if exists else None


def _view(action: Action, db: Session) -> dict:
    return {
        "id": action.id,
        "work_item_id": action.work_item_id,
        "run_id": action.run_id,
        "type": action.type,
        "status": action.status,
        "work_order_ref": _work_order_ref(db, action),
        "payload": action.payload,
        "evidence_ids": action.evidence_ids,
        "proposed_by_user_id": action.proposed_by_user_id,
        "approved_by_user_id": action.approved_by_user_id,
        "rejection_reason": action.rejection_reason,
        "created_at": iso(action.created_at),
        "decided_at": iso(action.decided_at),
        "executed_at": iso(action.executed_at),
    }


@router.get("")
def list_actions(member=Depends(current_member), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    items = db.scalars(select(Action).join(WorkItem, WorkItem.id == Action.work_item_id).where(
        Action.organization_id == member["organization_id"],
        WorkItem.access_scope.in_(allowed_scopes),
    ).order_by(Action.created_at.desc())).all()
    return {"items": [_view(a, db) for a in items]}


@router.get("/{action_id}")
def get_action(action_id: int, member=Depends(current_member), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    action = db.scalar(select(Action).join(WorkItem, WorkItem.id == Action.work_item_id).where(
        Action.id == action_id,
        Action.organization_id == member["organization_id"],
        WorkItem.access_scope.in_(allowed_scopes),
    ))
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return {"action": _view(action, db)}


@router.post("/{action_id}/approve")
def approve_action(action_id: int, member=Depends(require_role("approver", "admin")), db: Session = Depends(get_db)):
    org_id = member["organization_id"]
    user_id = member["user"].id
    # End any implicit read transaction before the explicit lock/execute transaction.
    db.rollback()
    stale_reason = None
    created_ref = None
    with db.begin():
        action = db.scalar(select(Action).where(
            Action.id == action_id,
            Action.organization_id == org_id,
        ).with_for_update())
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if action.status != "pending":
            raise HTTPException(status_code=409, detail="Action is no longer pending")
        work = db.scalar(select(WorkItem).where(WorkItem.id == action.work_item_id).with_for_update())
        allowed_scopes = set((member["membership"].scopes or []) + ["public"])
        if not work or work.access_scope not in allowed_scopes:
            raise HTTPException(status_code=404, detail="Action not found")
        if work.status != action.payload.get("expected_work_status"):
            action.status = "stale"
            action.decided_at = datetime.now(timezone.utc)
            stale_reason = "The work item changed after this proposal was created. Run the investigation again."
        elif action.type != "create_work_order":
            raise HTTPException(status_code=400, detail="Unsupported action type")
        else:
            created_ref = f"WO-{1900 + action.id}"
            existing = db.scalar(select(DemoWorkOrder).where(DemoWorkOrder.work_order_ref == created_ref))
            if not existing:
                db.add(DemoWorkOrder(
                    organization_id=org_id,
                    customer_id=int(action.payload["customer_id"]),
                    asset_id=int(action.payload["asset_id"]),
                    work_order_ref=created_ref,
                    status="open",
                    summary=action.payload["summary"],
                    requested_work=action.payload["requested_work"],
                ))
            now = datetime.now(timezone.utc)
            action.status = "executed"
            action.approved_by_user_id = user_id
            action.decided_at = now
            action.executed_at = now
            db.add(AuditEvent(
                organization_id=org_id,
                user_id=user_id,
                event_type="action.executed",
                entity_type="action",
                entity_id=str(action.id),
                detail={"type": action.type, "work_order_ref": created_ref},
            ))

    if stale_reason:
        raise HTTPException(status_code=409, detail=stale_reason)
    return {"ok": True, "status": "executed", "work_order_ref": created_ref}


@router.post("/{action_id}/reject")
def reject_action(payload: RejectActionRequest, action_id: int, member=Depends(require_role("approver", "admin")), db: Session = Depends(get_db)):
    allowed_scopes = list(set((member["membership"].scopes or []) + ["public"]))
    action = db.scalar(select(Action).join(WorkItem, WorkItem.id == Action.work_item_id).where(
        Action.id == action_id,
        Action.organization_id == member["organization_id"],
        WorkItem.access_scope.in_(allowed_scopes),
    ))
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="Action is no longer pending")
    action.status = "rejected"
    action.approved_by_user_id = member["user"].id
    action.rejection_reason = payload.reason
    action.decided_at = datetime.now(timezone.utc)
    db.add(AuditEvent(
        organization_id=member["organization_id"], user_id=member["user"].id,
        event_type="action.rejected", entity_type="action", entity_id=str(action.id),
        detail={"reason": payload.reason},
    ))
    db.commit()
    return {"ok": True, "status": "rejected"}
