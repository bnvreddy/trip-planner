import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth_schema import LoginRequest, RegisterRequest
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


def _token_response(user_id: str, email: str) -> dict:
    return {
        "access_token": create_access_token(user_id),
        "token_type": "bearer",
        "user": {"user_id": str(user_id), "email": email},
    }


@router.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT user_id FROM users WHERE LOWER(email) = :email"),
        {"email": payload.email},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO users (user_id, email, password_hash, default_transport_mode)
            VALUES (:uid, :email, :pwd, 'driving')
        """),
        {"uid": user_id, "email": payload.email, "pwd": hash_password(payload.password)},
    )
    db.commit()

    return _token_response(user_id, payload.email)


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        text("SELECT user_id, email, password_hash FROM users WHERE LOWER(email) = :email"),
        {"email": payload.email},
    ).fetchone()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return _token_response(str(user.user_id), user.email)


@router.get("/auth/me")
def me(current_user=Depends(get_current_user)):
    return {"user": {"user_id": str(current_user.user_id), "email": current_user.email}}
