from datetime import datetime
from typing import Any


def iso(value: datetime | None):
    return value.isoformat() if value else None


def user_view(user, membership=None) -> dict[str, Any]:
    data = {"id": user.id, "name": user.name, "email": user.email}
    if membership is not None:
        data.update({"role": membership.role, "scopes": membership.scopes, "organization": membership.organization.name})
    return data
