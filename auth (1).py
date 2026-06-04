from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.core.auth import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, get_current_user, hash_password,
)
from app.core.exceptions import UnauthorizedError, ConflictError
from app.core.responses import success_response
from app.models.user import PlatformUser
from app.schemas.user import LoginRequest, TokenResponse, PlatformUserCreate, PlatformUserOut
from app.config import settings
import uuid

router = APIRouter()


@router.post("/login", response_model=dict)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(PlatformUser).filter(
        PlatformUser.email == payload.email.lower(),
        PlatformUser.is_active == True,
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return success_response(
        TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ).model_dump()
    )


@router.post("/refresh", response_model=dict)
def refresh_token(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("refresh_token")
    if not token:
        raise UnauthorizedError("Refresh token required")

    decoded = decode_token(token)
    if decoded.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type")

    user = db.query(PlatformUser).filter(
        PlatformUser.id == decoded["sub"],
        PlatformUser.is_active == True,
    ).first()
    if not user:
        raise UnauthorizedError("User not found")

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    return success_response(
        TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ).model_dump()
    )


@router.post("/logout", response_model=dict)
def logout(current_user=Depends(get_current_user)):
    # JWT is stateless; client discards token. Optionally implement token blacklist via Redis.
    return success_response({"message": "Logged out successfully"})


@router.get("/me", response_model=dict)
def get_me(current_user=Depends(get_current_user)):
    return success_response(PlatformUserOut.model_validate(current_user).model_dump())


@router.post("/register", response_model=dict)
def register(payload: PlatformUserCreate, db: Session = Depends(get_db)):
    """Create a new platform user. In production restrict to admins."""
    existing = db.query(PlatformUser).filter(PlatformUser.email == payload.email.lower()).first()
    if existing:
        raise ConflictError(f"User with email {payload.email} already exists")

    if payload.role not in ("admin", "manager", "viewer"):
        from app.core.exceptions import ValidationError
        raise ValidationError("Role must be one of: admin, manager, viewer")

    user = PlatformUser(
        id=uuid.uuid4(),
        name=payload.name,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response(PlatformUserOut.model_validate(user).model_dump())
