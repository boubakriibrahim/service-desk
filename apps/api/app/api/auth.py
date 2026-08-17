from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.helpers import user_view
from app.config import get_settings
from app.db import get_db
from app.models import Membership, User
from app.schemas import LoginRequest
from app.security import clear_session_cookie, create_session_token, current_member, set_session_cookie, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/options")
def options():
    # Public, so the sign-in page offers the sample accounts only where they are seeded.
    return {"demo": get_settings().effective_seed_demo_data}


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")
    token = create_session_token(user.id, membership.organization_id)
    set_session_cookie(response, token)
    return {"user": user_view(user, membership)}


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(member=Depends(current_member)):
    return {"user": user_view(member["user"], member["membership"])}
