from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Platform User ─────────────────────────────────────────────────────────────

class PlatformUserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(default="viewer")


class PlatformUserOut(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Zoho User ─────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: UUID
    zoho_user_id: str
    name: str
    email: str
    role: Optional[str] = None
    capacity_hours_per_week: float
    is_active: bool
    synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithUtilization(UserOut):
    current_utilization_pct: Optional[float] = None
    utilization_band: Optional[str] = None
    consecutive_overload_weeks: Optional[int] = None


class UserCapacityUpdate(BaseModel):
    capacity_hours_per_week: float = Field(..., gt=0, le=168)
