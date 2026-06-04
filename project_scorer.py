from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
import structlog
import uuid

from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import Milestone
from app.models.analytics import UtilizationSnapshot, ProjectHealthScore

logger = structlog.get_logger()

SCHEDULE_WEIGHT = 0.40
RESOURCE_WEIGHT = 0.35
VELOCITY_WEIGHT = 0.25


def _compute_schedule_score(db: Session, project: Project, as_of_date: date) -> float:
    """Score 0-100: milestone completion rate, overdue count, deadline proximity."""
    milestones = db.query(Milestone).filter(Milestone.project_id == project.id).all()
    if not milestones:
        return 75.0  # Neutral when no milestones

    total = len(milestones)
    completed = sum(1 for m in milestones if m.is_completed)
    overdue = sum(1 for m in milestones if not m.is_completed and m.due_date and m.due_date < as_of_date)

    completion_rate = completed / total
    overdue_penalty = min(overdue * 10, 40)

    deadline_score = 100.0
    if project.end_date:
        days_remaining = (project.end_date - as_of_date).days
        if days_remaining < 0:
            deadline_score = 0.0
        elif days_remaining < 14:
            deadline_score = max(0.0, days_remaining / 14 * 50)
        elif days_remaining < 30:
            deadline_score = 50.0 + (days_remaining - 14) / 16 * 25

    schedule_score = (completion_rate * 70) + (deadline_score * 0.30) - overdue_penalty
    return max(0.0, min(100.0, schedule_score))


def _compute_resource_score(db: Session, project: Project, as_of_date: date) -> float:
    """Score 0-100: team utilization adequacy and unassigned high-priority tasks."""
    # Get users assigned to this project
    assigned_user_ids = (
        db.query(Task.assigned_to)
        .filter(
            Task.project_id == project.id,
            Task.assigned_to.isnot(None),
            Task.status.in_(["open", "in_progress"]),
        )
        .distinct()
        .all()
    )
    user_ids = [row[0] for row in assigned_user_ids]

    if not user_ids:
        return 50.0  # No assigned users - neutral

    # Get latest utilization for each user
    avg_util = 0.0
    util_records = (
        db.query(UtilizationSnapshot)
        .filter(
            UtilizationSnapshot.user_id.in_(user_ids),
            UtilizationSnapshot.snapshot_date == db.query(
                func.max(UtilizationSnapshot.snapshot_date)
            ).filter(UtilizationSnapshot.user_id.in_(user_ids)).scalar_subquery(),
        )
        .all()
    )

    if util_records:
        avg_util = sum(float(r.utilization_pct or 0) for r in util_records) / len(util_records)

    # Optimal utilization = 70-85%
    if 60 <= avg_util <= 85:
        util_score = 100.0
    elif avg_util < 60:
        util_score = max(0.0, avg_util / 60 * 100)
    else:
        util_score = max(0.0, 100.0 - (avg_util - 85) * 2)

    # Unassigned high-priority tasks penalty
    unassigned_high = (
        db.query(func.count(Task.id))
        .filter(
            Task.project_id == project.id,
            Task.assigned_to.is_(None),
            Task.priority == 1,
            Task.status.in_(["open", "in_progress"]),
        )
        .scalar()
    )
    vacancy_penalty = min(int(unassigned_high or 0) * 15, 40)

    resource_score = util_score - vacancy_penalty
    return max(0.0, min(100.0, resource_score))


def _compute_velocity_score(db: Session, project: Project, as_of_date: date) -> float:
    """Score 0-100: task completion rate and hours variance."""
    tasks = db.query(Task).filter(Task.project_id == project.id).all()
    if not tasks:
        return 75.0

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    overdue_open = sum(1 for t in tasks if t.status in ("open", "in_progress")
                       and t.due_date and t.due_date < as_of_date)

    completion_rate = completed / total
    overdue_penalty = min(overdue_open * 8, 40)

    # Hours variance: actual vs estimated
    estimated_tasks = [t for t in tasks if t.estimated_hours and t.actual_hours]
    variance_penalty = 0.0
    if estimated_tasks:
        variances = [abs(float(t.actual_hours) - float(t.estimated_hours)) / float(t.estimated_hours)
                     for t in estimated_tasks if float(t.estimated_hours) > 0]
        if variances:
            avg_variance = sum(variances) / len(variances)
            variance_penalty = min(avg_variance * 30, 20)

    velocity_score = (completion_rate * 80) + 20 - overdue_penalty - variance_penalty
    return max(0.0, min(100.0, velocity_score))


def _health_band(score: float) -> Tuple[str, str]:
    if score >= 75:
        return "healthy", "low"
    elif score >= 55:
        return "at_risk", "medium"
    elif score >= 35:
        return "at_risk_high", "high"
    else:
        return "critical", "critical"


def score_project(db: Session, project: Project, as_of_date: date = None) -> ProjectHealthScore:
    if as_of_date is None:
        as_of_date = date.today()

    schedule_score = _compute_schedule_score(db, project, as_of_date)
    resource_score = _compute_resource_score(db, project, as_of_date)
    velocity_score = _compute_velocity_score(db, project, as_of_date)

    overall = (
        schedule_score * SCHEDULE_WEIGHT
        + resource_score * RESOURCE_WEIGHT
        + velocity_score * VELOCITY_WEIGHT
    )
    overall = round(overall, 2)
    health_band, risk_level = _health_band(overall)

    record = ProjectHealthScore(
        id=uuid.uuid4(),
        project_id=project.id,
        scored_at=datetime.now(timezone.utc),
        overall_score=overall,
        schedule_score=round(schedule_score, 2),
        resource_score=round(resource_score, 2),
        velocity_score=round(velocity_score, 2),
        risk_level=risk_level,
        health_band=health_band,
    )
    db.add(record)
    db.commit()
    logger.info("project_scored", project_id=str(project.id), score=overall, band=health_band)
    return record


def score_all_projects(db: Session) -> int:
    projects = db.query(Project).filter(Project.status == "active").all()
    count = 0
    for project in projects:
        try:
            score_project(db, project)
            count += 1
        except Exception as e:
            logger.error("project_score_error", project_id=str(project.id), error=str(e))
    return count
