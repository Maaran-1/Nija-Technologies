from datetime import date
from typing import Optional
from app.models.user import User
from app.models.task import Task
from app.models.analytics import UtilizationSnapshot
from app.analytics.utilization_calculator import get_consecutive_overload_weeks
from sqlalchemy.orm import Session


def build_rationale(
    db: Session,
    source_user: User,
    target_user: User,
    task: Task,
    source_snap: UtilizationSnapshot,
    target_snap: Optional[UtilizationSnapshot],
    projected_source_util: float,
    projected_target_util: float,
    confidence_score: float,
) -> str:
    """Generate human-readable rationale for a task reassignment recommendation."""

    parts = []

    # Source context
    source_util = float(source_snap.utilization_pct or 0)
    consecutive_weeks = get_consecutive_overload_weeks(db, source_user.id)

    if consecutive_weeks >= 2:
        parts.append(
            f"{source_user.name} is at {source_util:.0f}% utilization "
            f"for {consecutive_weeks} consecutive weeks."
        )
    else:
        parts.append(
            f"{source_user.name} is currently at {source_util:.0f}% utilization "
            f"({source_snap.utilization_band.replace('_', ' ')})."
        )

    # Task context
    hours = float(task.estimated_hours or 0)
    parts.append(
        f"Task '{task.title[:60]}' ({hours:.0f}h estimated) is eligible for reassignment."
    )

    # Target context
    if target_snap:
        target_util = float(target_snap.utilization_pct or 0)
        parts.append(
            f"{target_user.name} has available capacity at {target_util:.0f}% utilization."
        )
    else:
        parts.append(f"{target_user.name} has available capacity.")

    # Project familiarity note (would need recipient_data here; simplified)
    parts.append(
        f"Projected result: {source_user.name} → {projected_source_util:.0f}%, "
        f"{target_user.name} → {projected_target_util:.0f}%."
    )

    # Due date warning
    if task.due_date:
        days_until_due = (task.due_date - date.today()).days
        if days_until_due <= 7:
            parts.append(f"Note: Task is due in {days_until_due} days — coordinate handoff promptly.")

    # Confidence note
    if confidence_score < 60:
        parts.append(
            "Confidence is moderate — recipient has limited history with tasks of this type."
        )

    return " ".join(parts)
