from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from app.config import get_settings, validate_runtime_settings
from app.db import SessionLocal
from app.models import (
    DemoAsset, DemoCustomer, DemoPart, DemoServiceCase, DemoWorkOrder,
    Membership, Organization, Source, User, WorkItem,
)
from app.security import hash_password
from app.services.documents import create_document


def seed() -> None:
    settings = get_settings()
    # The seed runs before the API starts, so check the settings here too.
    validate_runtime_settings(settings)
    # The demo accounts share a public password, so production starts without them.
    if not settings.effective_seed_demo_data:
        print("Demo seed skipped (APP_ENV=production or SEED_DEMO_DATA=false). Create users with: python -m app.manage create-user")
        return
    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).where(Organization.slug == "oriole"))
        if not org:
            org = Organization(name="Oriole Packaging Systems", slug="oriole")
            db.add(org)
            db.commit()
            db.refresh(org)

        users = {
            "service@demo.local": ("Maya Chen", "engineer", ["service", "engineering"]),
            "manager@demo.local": ("Luis Martin", "approver", ["service", "engineering", "restricted-service"]),
            "finance@demo.local": ("Avery Brooks", "member", ["finance"]),
        }
        created_users = {}
        for email, (name, role, scopes) in users.items():
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(email=email, name=name, password_hash=hash_password("demo-password"))
                db.add(user)
                db.flush()
            membership = db.scalar(select(Membership).where(
                Membership.organization_id == org.id,
                Membership.user_id == user.id,
            ))
            if not membership:
                db.add(Membership(organization_id=org.id, user_id=user.id, role=role, scopes=scopes))
            created_users[email] = user
        db.commit()

        source = db.scalar(select(Source).where(Source.organization_id == org.id, Source.name == "Service knowledge"))
        if not source:
            source = Source(organization_id=org.id, name="Service knowledge", kind="files", status="ready")
            db.add(source)
            db.commit()
            db.refresh(source)

        ops_source = db.scalar(select(Source).where(Source.organization_id == org.id, Source.name == "Operations database"))
        if not ops_source:
            db.add(Source(
                organization_id=org.id,
                name="Operations database",
                kind="postgresql",
                status="ready",
                config={"mode": "seeded read-only demo", "tables": ["customers", "assets", "service_cases", "parts", "work_orders"]},
            ))
            db.commit()

        # Seed documents once.
        from app.models import Document
        if not db.scalar(select(Document.id).where(Document.organization_id == org.id).limit(1)):
            docs_dir = Path(settings.demo_documents_path)
            specs = [
                ("px400-service-manual.md", "PX-400 Service Manual", "engineering", "internal"),
                ("e217-bulletin.md", "Service Bulletin SB-PX400-217", "service", "internal"),
                ("northstar-maintenance-agreement.md", "Northstar Foods Maintenance Agreement", "service", "internal"),
                ("service-escalation-sop.md", "Service Escalation SOP", "service", "internal"),
                ("finance-private-note.md", "Northstar Finance Note", "finance", "internal"),
            ]
            for filename, title, scope, sensitivity in specs:
                raw = (docs_dir / filename).read_bytes()
                create_document(db, org.id, source.id, title, filename, "text/markdown", raw, scope, sensitivity)

        customer = db.scalar(select(DemoCustomer).where(DemoCustomer.organization_id == org.id, DemoCustomer.name == "Northstar Foods"))
        if not customer:
            customer = DemoCustomer(organization_id=org.id, name="Northstar Foods", tier="Strategic", region="Ontario")
            db.add(customer)
            db.flush()
            asset = DemoAsset(
                organization_id=org.id,
                customer_id=customer.id,
                asset_ref="NSF-PX400-L4",
                model="PX-400",
                line="Line 4",
                firmware="4.8.0",
                installed_at=datetime(2024, 5, 8, tzinfo=timezone.utc),
                status="active",
            )
            db.add(asset)
            db.flush()
            db.add_all([
                DemoServiceCase(
                    organization_id=org.id, customer_id=customer.id, asset_id=asset.id,
                    case_ref="CASE-4821", opened_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
                    status="resolved", error_code="E-217",
                    summary="Unexpected stop during index cycle after firmware 4.8 update.",
                    resolution="Connector reseated; machine returned to service. D-17 passed.",
                ),
                DemoServiceCase(
                    organization_id=org.id, customer_id=customer.id, asset_id=asset.id,
                    case_ref="CASE-4873", opened_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
                    status="resolved", error_code="E-217",
                    summary="Second intermittent E-217 stop on Line 4.",
                    resolution="Remote log collected. No part replaced. Engineering asked to monitor recurrence.",
                ),
                DemoServiceCase(
                    organization_id=org.id, customer_id=customer.id, asset_id=asset.id,
                    case_ref="CASE-4910", opened_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
                    status="open", error_code="E-217",
                    summary="Third E-217 stop this month; customer requests escalation before production run.",
                    resolution=None,
                ),
                DemoPart(organization_id=org.id, sku="EA-400", name="PX-400 encoder assembly", stock_qty=4, compatible_models=["PX-400"]),
                DemoPart(organization_id=org.id, sku="HN-44", name="Shielded encoder harness", stock_qty=11, compatible_models=["PX-400"]),
                DemoPart(organization_id=org.id, sku="PS-12", name="Controller power module", stock_qty=2, compatible_models=["PX-400"]),
                DemoWorkOrder(
                    organization_id=org.id, customer_id=customer.id, asset_id=asset.id,
                    work_order_ref="WO-1841", status="completed",
                    summary="Post-upgrade inspection", requested_work="Verify firmware 4.8 deployment and inspect machine after first E-217 report.",
                ),
            ])
            db.commit()

        work = db.scalar(select(WorkItem).where(WorkItem.organization_id == org.id, WorkItem.asset_ref == "NSF-PX400-L4"))
        if not work:
            db.add(WorkItem(
                organization_id=org.id,
                title="Repeated E-217 stops after firmware 4.8",
                customer_name="Northstar Foods",
                asset_ref="NSF-PX400-L4",
                status="open",
                owner_user_id=created_users["service@demo.local"].id,
                context={"priority": "High", "product": "PX-400", "site": "Northstar Foods — Line 4"},
            ))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
