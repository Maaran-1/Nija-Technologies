from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.models.user import User
from app.models.task import Task
from app.models.timesheet import TimesheetEntry
from app.models.analytics import UtilizationSnapshot

logger = structlog.get_logger()


def _utilization_band(pct: float) -> str:
    if pct < settings.UTILIZATION_UNDERUTILIZED_THRESHOLD:
        return "underutilized"
    elif pct <= settings.UTILIZATION_OPTIMAL_MAX:
        return "optimal"
    elif pct <= settings.UTILIZATION_OVERLOADED_MAX:
        return "overloaded"
    else:
        return "critical"


def compute_user_utilization(
    db: Session,
    user: User,
    snapshot_date: date,
    window_weeks: int = None,
) -> Tuple[float, float, float, str]:
    """
    Returns (capacity_hours, allocated_hours, logged_hours, band).
    allocated_hours = sum of estimated_hours on active tasks.
    logged_hours = sum of timesheet hours in window.
    """
    if window_weeks is None:
        window_weeks = settings.UTILIZATION_WINDOW_WEEKS

    window_start = snapshot_date - timedelta(weeks=window_weeks)
    capacity_hours = float(user.capacity_hours_per_week or 40.0) * window_weeks

    # Allocated hours: estimated hours on open/in_progress tasks
    allocated = (
        db.query(func.coalesce(func.sum(Task.estimated_hours), 0.0))
        .filter(
            Task.assigned_to == user.id,
            Task.status.in_(["open", "in_progress"]),
        )
        .scalar()
    )
    allocated_hours = float(allocated or 0.0)

    # Logged hours: actual timesheet entries in the window
    logged = (
        db.query(func.coalesce(func.sum(TimesheetEntry.hours_logged), 0.0))
        .filter(
            TimesheetEntry.user_id == user.id,
            TimesheetEntry.work_date >= window_start,
            TimesheetEntry.work_date <= snapshot_date,
        )
        .scalar()
    )
    logged_hours = float(logged or 0.0)

    if capacity_hours > 0:
        util_pct = round((allocated_hours / capacity_hours) * 100, 2)
    else:
        util_pct = 0.0

    band = _utilization_band(util_pct)
    return capacity_hours, allocated_hours, logged_hours, util_pct, band


def compute_and_save_utilization_snapshots(
    db: Session,
    snapshot_date: Optional[date] = None,
    user_ids: Optional[List] = None,
    window_weeks: int = None,
) -> int:
    """Compute utilization for all (or specified) users and upsert snapshot records."""
    from sqlalchemy.dialects.postgresql import insert

    if snapshot_date is None:
        snapshot_date = date.today()
    if window_weeks is None:
        window_weeks = settings.UTILIZATION_WINDOW_WEEKS

    query = db.query(User).filter(User.is_active == True)
    if user_ids:
        query = query.filter(User.id.in_(user_ids))
    users = query.all()

    count = 0
    for user in users:
        try:
            capacity_hours, allocated_hours, logged_hours, util_pct, band = compute_user_utilization(
                db, user, snapshot_date, window_weeks
            )
            stmt = insert(UtilizationSnapshot).values(
                id=__import__("uuid").uuid4(),
                user_id=user.id,
                snapshot_date=snapshot_date,
                window_weeks=window_weeks,
                capacity_hours=capacity_hours,
                allocated_hours=allocated_hours,
                logged_hours=logged_hours,
                utilization_pct=util_pct,
                utilization_band=band,
                created_at=datetime.now(timezone.utc),
            ).on_conflict_do_update(
                constraint="uq_utilization_snapshot",
                set_={
                    "capacity_hours": capacity_hours,
                    "allocated_hours": allocated_hours,
                    "logged_hours": logged_hours,
                    "utilization_pct": util_pct,
                    "utilization_band": band,
                },
            )
            db.execute(stmt)
            count += 1
        except Exception as e:
            logger.error("utilization_compute_error", user_id=str(user.id), error=str(e))

    db.commit()
    logger.info("utilization_snapshots_saved", count=count, snapshot_date=str(snapshot_date))
    return count


def get_consecutive_overload_weeks(db: Session, user_id, as_of_date: date = None) -> int:
    """Count consecutive weekly snapshots where band = critical or overloaded."""
    if as_of_date is None:
        as_of_date = date.today()

    snapshots = (
        db.query(UtilizationSnapshot)
        .filter(
            UtilizationSnapshot.user_id == user_id,
            UtilizationSnapshot.snapshot_date <= as_of_date,
        )
        .order_by(UtilizationSnapshot.snapshot_date.desc())
        .limit(12)
        .all()
    )

    consecutive = 0
    for snap in snapshots:
        if snap.utilization_band in ("critical", "overloaded"):
            consecutive += 1
        else:
            break
    return consecutive


def get_user_utilization_trend(
    db: Session, user_id, weeks_back: int = 8
) -> List[UtilizationSnapshot]:
    cutoff = date.today() - timedelta(weeks=weeks_back)
    return (
        db.query(UtilizationSnapshot)
        .filter(
            UtilizationSnapshot.user_id == user_id,
            UtilizationSnapshot.snapshot_date >= cutoff,
        )
        .order_by(UtilizationSnapshot.snapshot_date.asc())
        .all()
    )
