from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.exceptions import NotFoundError
from app.core.responses import success_response, paginated_response
from app.models.user import User
from app.models.analytics import UtilizationSnapshot
from app.schemas.analytics import (
    UtilizationSnapshotOut, UserUtilizationSummary, TeamUtilizationOverview,
)
from app.analytics.utilization_calculator import (
    compute_and_save_utilization_snapshots,
    get_consecutive_overload_weeks,
    get_user_utilization_trend,
)

router = APIRouter()
logger = structlog.get_logger()


@router.get("/team", response_model=dict)
def get_team_utilization(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Team-wide utilization overview with band distribution."""
    # Get latest snapshot per user
    from sqlalchemy import func as fn
    latest_dates = (
        db.query(
            UtilizationSnapshot.user_id,
            fn.max(UtilizationSnapshot.snapshot_date).label("max_date"),
        )
        .group_by(UtilizationSnapshot.user_id)
        .subquery()
    )

    latest_snaps = (
        db.query(UtilizationSnapshot)
        .join(
            latest_dates,
            (UtilizationSnapshot.user_id == latest_dates.c.user_id)
            & (UtilizationSnapshot.snapshot_date == latest_dates.c.max_date),
        )
        .all()
    )

    users_data = []
    band_counts = {"underutilized": 0, "optimal": 0, "overloaded": 0, "critical": 0}
    total_pct = 0.0

    for snap in latest_snaps:
        user = db.query(User).filter(User.id == snap.user_id).first()
        if not user or not user.is_active:
            continue

        band = snap.utilization_band or "underutilized"
        if band in band_counts:
            band_counts[band] += 1

        pct = float(snap.utilization_pct or 0)
        total_pct += pct

        users_data.append({
            "user_id": str(user.id),
            "user_name": user.name,
            "user_email": user.email,
            "current_utilization_pct": pct,
            "utilization_band": band,
            "capacity_hours_per_week": float(user.capacity_hours_per_week or 40.0),
            "allocated_hours": float(snap.allocated_hours or 0),
            "consecutive_overload_weeks": get_consecutive_overload_weeks(db, user.id),
        })

    total_users = len(users_data)
    avg_pct = round(total_pct / total_users, 2) if total_users > 0 else 0.0

    return success_response({
        "total_users": total_users,
        "underutilized_count": band_counts["underutilized"],
        "optimal_count": band_counts["optimal"],
        "overloaded_count": band_counts["overloaded"],
        "critical_count": band_counts["critical"],
        "average_utilization_pct": avg_pct,
        "users": users_data,
    })


@router.get("/user/{user_id}", response_model=dict)
def get_user_utilization(
    user_id: str,
    weeks_back: int = Query(8, ge=1, le=52),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get utilization trend for a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundError("User", user_id)

    trend = get_user_utilization_trend(db, user.id, weeks_back=weeks_back)

    return success_response({
        "user_id": user_id,
        "user_name": user.name,
        "snapshots": [UtilizationSnapshotOut.model_validate(s).model_dump() for s in trend],
    })


@router.post("/recompute", response_model=dict)
def trigger_utilization_recompute(
    current_user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Manually trigger utilization snapshot recomputation for today."""
    count = compute_and_save_utilization_snapshots(db)
    logger.info("utilization_recomputed_manually", count=count)
    return success_response({"snapshots_computed": count, "snapshot_date": str(date.today())})
