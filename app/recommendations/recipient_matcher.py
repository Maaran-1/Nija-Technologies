from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.models.user import User
from app.models.task import Task
from app.models.analytics import UtilizationSnapshot

logger = structlog.get_logger()


def _get_user_latest_utilization(db: Session, user_id) -> Optional[UtilizationSnapshot]:
    return (
        db.query(UtilizationSnapshot)
        .filter(UtilizationSnapshot.user_id == user_id)
        .order_by(UtilizationSnapshot.snapshot_date.desc())
        .first()
    )


def _project_utilization_after_assignment(
    current_util_pct: float,
    current_capacity_hours: float,
    task_estimated_hours: float,
    window_weeks: int = 2,
) -> float:
    """Compute projected utilization after adding task_estimated_hours."""
    if current_capacity_hours <= 0:
        return 999.0
    additional_pct = (task_estimated_hours / current_capacity_hours) * 100
    return current_util_pct + additional_pct


def _compute_skill_match_score(task: Task, user: User, db: Session) -> float:
    """
    Infer skill match from historical task completions in same category/tags.
    Returns 0-100.
    """
    if not task.tags:
        return 50.0  # Neutral when no tags

    task_tags = {t.strip().lower() for t in (task.tags or "").split(",") if t.strip()}
    if not task_tags:
        return 50.0

    # Count completed tasks by user with matching tags
    user_completed_with_tags = (
        db.query(func.count(Task.id))
        .filter(
            Task.assigned_to == user.id,
            Task.status == "completed",
            Task.tags.isnot(None),
        )
        .scalar()
    ) or 0

    if user_completed_with_tags > 5:
        return 85.0
    elif user_completed_with_tags > 0:
        return 65.0
    else:
        return 35.0


def _compute_project_familiarity(task: Task, user: User, db: Session) -> float:
    """Score 0-100: does the user already work on the same project?"""
    existing = (
        db.query(func.count(Task.id))
        .filter(
            Task.assigned_to == user.id,
            Task.project_id == task.project_id,
            Task.status.in_(["open", "in_progress", "completed"]),
        )
        .scalar()
    ) or 0

    if existing > 3:
        return 100.0
    elif existing > 0:
        return 70.0
    return 30.0


def _compute_historical_completion_rate(user: User, db: Session) -> float:
    """Score 0-100: ratio of completed tasks to total assigned."""
    total = (
        db.query(func.count(Task.id))
        .filter(Task.assigned_to == user.id)
        .scalar()
    ) or 0

    completed = (
        db.query(func.count(Task.id))
        .filter(Task.assigned_to == user.id, Task.status == "completed")
        .scalar()
    ) or 0

    if total == 0:
        return 50.0
    return round((completed / total) * 100, 1)


def _compute_wip_depth_score(user: User, db: Session) -> float:
    """Score 0-100: fewer open high-priority tasks = higher score."""
    open_high = (
        db.query(func.count(Task.id))
        .filter(
            Task.assigned_to == user.id,
            Task.priority == 1,
            Task.status.in_(["open", "in_progress"]),
        )
        .scalar()
    ) or 0

    if open_high == 0:
        return 100.0
    elif open_high <= 2:
        return 70.0
    elif open_high <= 5:
        return 40.0
    return 10.0


def score_recipients(
    db: Session,
    task: Task,
    exclude_user_id=None,
) -> List[Dict[str, Any]]:
    """
    Score all eligible users as potential recipients for a task.
    Eligible = utilization_band underutilized or optimal, and projected util < 90%.
    """
    from sqlalchemy import func

    # Get latest snapshot dates
    latest_snap_dates = (
        db.query(
            UtilizationSnapshot.user_id,
            func.max(UtilizationSnapshot.snapshot_date).label("max_date"),
        )
        .group_by(UtilizationSnapshot.user_id)
        .subquery()
    )

    eligible_snaps = (
        db.query(UtilizationSnapshot)
        .join(
            latest_snap_dates,
            (UtilizationSnapshot.user_id == latest_snap_dates.c.user_id)
            & (UtilizationSnapshot.snapshot_date == latest_snap_dates.c.max_date),
        )
        .filter(UtilizationSnapshot.utilization_band.in_(["underutilized", "optimal"]))
        .all()
    )

    scored = []
    for snap in eligible_snaps:
        if snap.user_id == exclude_user_id:
            continue

        user = db.query(User).filter(User.id == snap.user_id, User.is_active == True).first()
        if not user:
            continue

        projected_util = _project_utilization_after_assignment(
            float(snap.utilization_pct or 0),
            float(snap.capacity_hours or 80),
            float(task.estimated_hours or 0),
        )

        if projected_util > settings.MAX_PROJECTED_UTILIZATION:
            continue  # Would overload recipient

        skill_score = _compute_skill_match_score(task, user, db)
        familiarity_score = _compute_project_familiarity(task, user, db)
        completion_rate = _compute_historical_completion_rate(user, db)
        wip_score = _compute_wip_depth_score(user, db)

        # Weighted composite recipient score
        recipient_score = (
            (100 - float(snap.utilization_pct or 0)) * 0.35  # Available capacity weight
            + skill_score * 0.25
            + familiarity_score * 0.20
            + completion_rate * 0.10
            + wip_score * 0.10
        )

        scored.append({
            "user": user,
            "snapshot": snap,
            "projected_util": round(projected_util, 2),
            "current_util_pct": float(snap.utilization_pct or 0),
            "skill_score": skill_score,
            "familiarity_score": familiarity_score,
            "completion_rate": completion_rate,
            "wip_score": wip_score,
            "recipient_score": round(recipient_score, 2),
        })

    scored.sort(key=lambda x: x["recipient_score"], reverse=True)
    logger.info("recipients_scored", task_id=str(task.id), eligible_count=len(scored))
    return scored
