"""Administrative commands for deployments that run without the demo data.

    python -m app.manage create-user --email lead@example.com --name "Service Lead" \
        --role approver --scopes service,engineering --org "Example Industries"

The password comes from SERVICE_DESK_PASSWORD or an interactive prompt. The organization is created on
first use, together with the file source that document uploads need.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Membership, Organization, Source, User
from app.security import hash_password

ROLES = ("member", "engineer", "approver", "admin")
MIN_PASSWORD = 12


def create_user(email: str, name: str, role: str, scopes: list[str], org_name: str, password: str) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    email = email.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == email)):
            raise ValueError(f"a user with email {email} already exists")
        org = db.scalar(select(Organization).where(Organization.slug == slug))
        if not org:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            db.flush()
            db.add(Source(organization_id=org.id, name="Documents", kind="files", status="ready"))
        user = User(email=email, name=name, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        db.add(Membership(organization_id=org.id, user_id=user.id, role=role, scopes=scopes))
        db.commit()
        return f"created {role} {email} in {org.name}"
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    cu = commands.add_parser("create-user", help="create a user (and their organization if needed)")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", choices=ROLES, default="engineer")
    cu.add_argument("--scopes", default="service", help="comma-separated access scopes, e.g. service,engineering")
    cu.add_argument("--org", required=True, help="organization name")
    args = parser.parse_args()
    password = os.environ.get("SERVICE_DESK_PASSWORD") or getpass.getpass("Password: ")
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    try:
        print(create_user(args.email, args.name, args.role, scopes, args.org, password))
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
