from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.exceptions import NotFoundError
from app.core.responses import success_response, paginated_response
from app.models.user import User
from app.models.analytics import UtilizationSnapshot
from app.schemas.user import UserOut, UserWithUtilization, UserCapacityUpdate
from app.analytics.utilization_calculator import get_consecutive_overload_weeks, get_user_utilization_trend
from app.analytics.availability_forecaster import forecast_user_availability

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=dict)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(True),
    role: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all Zoho-sourced employees with optional filters."""
    query = db.query(User)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if role:
        query = query.filter(User.role == role)

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # Enrich with utilization data
    result = []
    for user in users:
        snap = (
            db.query(UtilizationSnapshot)
            .filter(UtilizationSnapshot.user_id == user.id)
            .order_by(UtilizationSnapshot.snapshot_date.desc())
            .first()
        )
        data = UserWithUtilization.model_validate(user).model_dump()
        if snap:
            data["current_utilization_pct"] = float(snap.utilization_pct or 0)
            data["utilization_band"] = snap.utilization_band
            data["consecutive_overload_weeks"] = get_consecutive_overload_weeks(db, user.id)
        result.append(data)

    return paginated_response(result, page, page_size, total)


@router.get("/{user_id}", response_model=dict)
def get_user(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single user with utilization and trend data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", user_id)

    snap = (
        db.query(UtilizationSnapshot)
        .filter(UtilizationSnapshot.user_id == user.id)
        .order_by(UtilizationSnapshot.snapshot_date.desc())
        .first()
    )

    trend = get_user_utilization_trend(db, user.id, weeks_back=8)

    data = UserOut.model_validate(user).model_dump()
    data["current_utilization_pct"] = float(snap.utilization_pct or 0) if snap else None
    data["utilization_band"] = snap.utilization_band if snap else None
    data["consecutive_overload_weeks"] = get_consecutive_overload_weeks(db, user.id)
    data["trend"] = [
        {
            "snapshot_date": str(s.snapshot_date),
            "utilization_pct": float(s.utilization_pct or 0),
            "utilization_band": s.utilization_band,
        }
        for s in trend
    ]

    return success_response(data)


@router.patch("/{user_id}/capacity", response_model=dict)
def update_user_capacity(
    user_id: str,
    payload: UserCapacityUpdate,
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Update a user's weekly capacity hours."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", user_id)

    user.capacity_hours_per_week = payload.capacity_hours_per_week
    db.commit()
    db.refresh(user)
    logger.info("user_capacity_updated", user_id=user_id, capacity=payload.capacity_hours_per_week)
    return success_response(UserOut.model_validate(user).model_dump())


@router.get("/{user_id}/availability", response_model=dict)
def get_user_availability(
    user_id: str,
    forecast_days: int = Query(14, ge=1, le=90),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Forecast a user's availability over the next N days."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", user_id)

    forecast = forecast_user_availability(db, user, forecast_days=forecast_days)
    return success_response(forecast)
