from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import DemoAsset, DemoCustomer, DemoPart, DemoServiceCase, DemoWorkOrder


def get_operations_context(db: Session, organization_id: int, customer_name: str, asset_ref: str) -> dict:
    customer = db.scalar(select(DemoCustomer).where(
        DemoCustomer.organization_id == organization_id,
        DemoCustomer.name == customer_name,
    ))
    if not customer:
        return {"customer": None, "asset": None, "service_cases": [], "parts": [], "work_orders": []}

    asset = db.scalar(select(DemoAsset).where(
        DemoAsset.organization_id == organization_id,
        DemoAsset.customer_id == customer.id,
        DemoAsset.asset_ref == asset_ref,
    ))
    if not asset:
        return {"customer": _customer(customer), "asset": None, "service_cases": [], "parts": [], "work_orders": []}

    cases = db.scalars(select(DemoServiceCase).where(
        DemoServiceCase.organization_id == organization_id,
        DemoServiceCase.asset_id == asset.id,
    ).order_by(DemoServiceCase.opened_at.desc()).limit(8)).all()

    parts = db.scalars(select(DemoPart).where(DemoPart.organization_id == organization_id)).all()
    compatible = [p for p in parts if asset.model in (p.compatible_models or [])]

    work_orders = db.scalars(select(DemoWorkOrder).where(
        DemoWorkOrder.organization_id == organization_id,
        DemoWorkOrder.asset_id == asset.id,
    ).order_by(DemoWorkOrder.created_at.desc()).limit(8)).all()

    return {
        "customer": _customer(customer),
        "asset": {
            "id": asset.id,
            "asset_ref": asset.asset_ref,
            "model": asset.model,
            "line": asset.line,
            "firmware": asset.firmware,
            "status": asset.status,
        },
        "service_cases": [{
            "case_ref": c.case_ref,
            "opened_at": c.opened_at.isoformat(),
            "status": c.status,
            "error_code": c.error_code,
            "summary": c.summary,
            "resolution": c.resolution,
        } for c in cases],
        "parts": [{"sku": p.sku, "name": p.name, "stock_qty": p.stock_qty} for p in compatible],
        "work_orders": [{
            "work_order_ref": w.work_order_ref,
            "status": w.status,
            "summary": w.summary,
            "requested_work": w.requested_work,
        } for w in work_orders],
    }


def _customer(customer: DemoCustomer) -> dict:
    return {"id": customer.id, "name": customer.name, "tier": customer.tier, "region": customer.region}
