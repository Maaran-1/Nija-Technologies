from datetime import date, timedelta
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session
import structlog

from app.models.user import User
from app.models.task import Task
from app.models.analytics import UtilizationSnapshot

logger = structlog.get_logger()

# Tasks with due dates within this many days are NOT eligible for reassignment
IMMINENT_DUE_DATE_DAYS = 3


def get_overloaded_users(db: Session) -> List[User]:
    """
    Return active users whose latest utilization snapshot is 'overloaded' or 'critical'.
    Uses a GROUP BY subquery to reliably get the most recent snapshot per user.
    """
    # Get the latest snapshot date per user
    latest_snap_dates = (
        db.query(
            UtilizationSnapshot.user_id,
            func.max(UtilizationSnapshot.snapshot_date).label("max_date"),
        )
        .group_by(UtilizationSnapshot.user_id)
        .subquery()
    )

    # Join snapshots to their latest date and filter by overload bands
    overloaded_user_ids_query = (
        db.query(UtilizationSnapshot.user_id)
        .join(
            latest_snap_dates,
            (UtilizationSnapshot.user_id == latest_snap_dates.c.user_id)
            & (UtilizationSnapshot.snapshot_date == latest_snap_dates.c.max_date),
        )
        .filter(UtilizationSnapshot.utilization_band.in_(["overloaded", "critical"]))
        .all()
    )

    user_ids = [row[0] for row in overloaded_user_ids_query]
    return db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()


def get_candidate_tasks(db: Session, user: User) -> List[Task]:
    """
    Return tasks assigned to a user that are eligible for reassignment:
    - Status: open or in_progress
    - Due date not imminent (> 3 days away or null)
    - Has estimated hours (so we can compute impact)
    Ordered by priority ascending (1=high first), then by estimated hours descending.
    """
    today = date.today()
    imminent_cutoff = today + timedelta(days=IMMINENT_DUE_DATE_DAYS)

    candidates = (
        db.query(Task)
        .filter(
            Task.assigned_to == user.id,
            Task.status.in_(["open", "in_progress"]),
            Task.estimated_hours.isnot(None),
            Task.estimated_hours > 0,
            # Either no due date or due date is not imminent
            (Task.due_date.is_(None)) | (Task.due_date > imminent_cutoff),
        )
        .order_by(Task.priority.asc(), Task.estimated_hours.desc())
        .all()
    )

    logger.info("candidate_tasks_found", user_id=str(user.id), count=len(candidates))
    return candidates
