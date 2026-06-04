from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.database import get_db
from app.core.exceptions import UnauthorizedError, ForbiddenError

logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {str(e)}")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    from app.models.user import PlatformUser

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token missing subject")

    user = db.query(PlatformUser).filter(PlatformUser.id == user_id, PlatformUser.is_active == True).first()
    if not user:
        raise UnauthorizedError("User not found or inactive")

    return user


def require_role(*roles: str):
    def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise ForbiddenError(f"Requires one of roles: {', '.join(roles)}")
        return current_user
    return role_checker


def get_admin_user(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise ForbiddenError("Admin access required")
    return current_user


def get_manager_or_admin(current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "manager"):
        raise ForbiddenError("Manager or admin access required")
    return current_user
