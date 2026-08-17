from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.models import ModelEndpoint
from app.security import current_member

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/models")
def model_settings(member=Depends(current_member), db: Session = Depends(get_db)):
    settings = get_settings()
    endpoints = db.scalars(select(ModelEndpoint).where(ModelEndpoint.organization_id == member["organization_id"]).order_by(ModelEndpoint.priority.asc())).all()
    effective = {
        "mode": settings.ai_mode,
        "model": "service-desk-demo" if settings.ai_mode == "demo" else settings.ai_model,
        "base_url": None if settings.ai_mode == "demo" else settings.ai_base_url,
        "provider_kind": "demo" if settings.ai_mode == "demo" else settings.ai_provider_kind,
        "max_sensitivity": "restricted" if settings.ai_mode == "demo" else settings.ai_max_sensitivity,
        "embedding_mode": settings.embedding_mode,
        "embedding_model": "deterministic-384" if settings.embedding_mode == "demo" else settings.embedding_model,
        "decision_mode": settings.laya_mode,
        "decision_model": "deterministic-decision-signals" if settings.laya_mode == "demo" else settings.laya_model,
        "decision_base_url": None if settings.laya_mode in {"demo", "off"} else settings.laya_base_url,
    }
    return {
        "effective": effective,
        "demo_reset": settings.effective_enable_demo_reset,
        "configured_endpoints": [{
            "id": e.id,
            "name": e.name,
            "kind": e.kind,
            "base_url": e.base_url,
            "model": e.model,
            "max_sensitivity": e.max_sensitivity,
            "capabilities": e.capabilities,
            "enabled": e.enabled,
            "healthy": e.healthy,
            "priority": e.priority,
        } for e in endpoints],
        "routing_order": ["organization policy", "data sensitivity", "required capability", "health", "priority / quality / latency / configured cost"],
    }
