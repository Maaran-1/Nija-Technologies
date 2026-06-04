from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import structlog

from app.models.user import User
from app.models.task import Task
from app.models.timesheet import TimesheetEntry
from app.models.analytics import UtilizationSnapshot

logger = structlog.get_logger()


def _compute_completion_velocity(db: Session, user_id, lookback_days: int = 30) -> float:
    """Estimate hours completed per day based on historical timesheet data."""
    cutoff = date.today() - timedelta(days=lookback_days)
    total_logged = (
        db.query(func.coalesce(func.sum(TimesheetEntry.hours_logged), 0.0))
        .filter(
            TimesheetEntry.user_id == user_id,
            TimesheetEntry.work_date >= cutoff,
        )
        .scalar()
    )
    # Assume 5-day work week
    work_days = lookback_days * (5 / 7)
    if work_days > 0:
        return float(total_logged) / work_days
    return 4.0  # Default 4 hours/day if no history


def forecast_user_availability(
    db: Session,
    user: User,
    forecast_days: int = 14,
) -> Dict[str, Any]:
    """
    Predict availability windows for a user over the next N days.
    Returns days where the user is expected to have available capacity.
    """
    capacity_per_day = float(user.capacity_hours_per_week or 40.0) / 5

    # Active tasks with estimated hours remaining
    active_tasks = (
        db.query(Task)
        .filter(
            Task.assigned_to == user.id,
            Task.status.in_(["open", "in_progress"]),
        )
        .all()
    )

    total_remaining_hours = sum(
        float(t.estimated_hours or 0) - float(t.actual_hours or 0)
        for t in active_tasks
    )
    total_remaining_hours = max(0.0, total_remaining_hours)

    velocity = _compute_completion_velocity(db, user.id)
    days_to_free = int(total_remaining_hours / max(velocity, 0.5)) if velocity > 0 else 999

    # Build day-by-day forecast
    forecast = []
    today = date.today()
    daily_load = total_remaining_hours

    for i in range(forecast_days):
        forecast_date = today + timedelta(days=i)
        if forecast_date.weekday() >= 5:  # Skip weekends
            continue

        daily_burn = min(velocity, daily_load)
        daily_load = max(0.0, daily_load - daily_burn)
        available_hours = max(0.0, capacity_per_day - daily_burn)
        utilization_pct = (daily_burn / capacity_per_day * 100) if capacity_per_day > 0 else 0

        forecast.append({
            "date": forecast_date.isoformat(),
            "available_hours": round(available_hours, 1),
            "estimated_load_hours": round(daily_burn, 1),
            "utilization_pct": round(utilization_pct, 1),
        })

    current_snap = (
        db.query(UtilizationSnapshot)
        .filter(UtilizationSnapshot.user_id == user.id)
        .order_by(UtilizationSnapshot.snapshot_date.desc())
        .first()
    )

    return {
        "user_id": str(user.id),
        "user_name": user.name,
        "capacity_hours_per_week": float(user.capacity_hours_per_week or 40.0),
        "total_remaining_hours": round(total_remaining_hours, 1),
        "days_until_available": days_to_free,
        "current_utilization_pct": float(current_snap.utilization_pct) if current_snap else None,
        "utilization_band": current_snap.utilization_band if current_snap else None,
        "daily_forecast": forecast,
    }


def get_available_users(
    db: Session,
    required_hours: float,
    by_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Find users who will have capacity for a task of given hours by a date."""
    if by_date is None:
        by_date = date.today() + timedelta(days=14)

    users = db.query(User).filter(User.is_active == True).all()
    available = []

    for user in users:
        forecast = forecast_user_availability(db, user)
        total_available = sum(
            day["available_hours"]
            for day in forecast["daily_forecast"]
            if date.fromisoformat(day["date"]) <= by_date
        )
        if total_available >= required_hours:
            available.append({
                **forecast,
                "total_available_by_date": round(total_available, 1),
                "can_absorb": True,
            })

    available.sort(key=lambda x: x.get("current_utilization_pct") or 0)
    return available
