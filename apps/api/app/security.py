from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Cookie, Depends, HTTPException, Response, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.models import Membership, User

password_hash = PasswordHash.recommended()
settings = get_settings()
COOKIE_NAME = "service_desk_session"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=60 * 60 * 12, path="/", httponly=True,
        samesite="lax", secure=settings.effective_cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=settings.effective_cookie_secure)


def hash_password(value: str) -> str:
    return password_hash.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return password_hash.verify(value, hashed)


def create_session_token(user_id: int, organization_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def current_member(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
        org_id = int(payload["org"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    row = db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(User.id == user_id, Membership.organization_id == org_id)
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Membership not found")
    user, membership = row
    return {
        "user": user,
        "membership": membership,
        "organization_id": org_id,
    }


def require_role(*roles: str):
    def dependency(member=Depends(current_member)):
        if member["membership"].role not in roles:
            raise HTTPException(status_code=403, detail="This action requires a different role")
        return member
    return dependency
