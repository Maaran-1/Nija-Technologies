from datetime import date, timedelta
from typing import List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
import structlog

from app.models.user import User
from app.models.task import Task
from app.models.analytics import UtilizationSnapshot
from app.analytics.utilization_calculator import get_consecutive_overload_weeks

logger = structlog.get_logger()

SUSTAINED_OVERLOAD_WEEKS = 2
CONCENTRATION_THRESHOLD = 0.40  # 40% of project tasks on one person = risk


def detect_burnout_risks(db: Session, as_of_date: date = None) -> List[Dict[str, Any]]:
    """Flag employees with sustained overload for 2+ consecutive weeks."""
    if as_of_date is None:
        as_of_date = date.today()

    users = db.query(User).filter(User.is_active == True).all()
    risks = []
    for user in users:
        consecutive_weeks = get_consecutive_overload_weeks(db, user.id, as_of_date)
        if consecutive_weeks >= SUSTAINED_OVERLOAD_WEEKS:
            latest_snap = (
                db.query(UtilizationSnapshot)
                .filter(
                    UtilizationSnapshot.user_id == user.id,
                    UtilizationSnapshot.snapshot_date <= as_of_date,
                )
                .order_by(UtilizationSnapshot.snapshot_date.desc())
                .first()
            )
            risks.append({
                "user_id": user.id,
                "user_name": user.name,
                "email": user.email,
                "consecutive_overload_weeks": consecutive_weeks,
                "current_utilization_pct": float(latest_snap.utilization_pct) if latest_snap else None,
                "utilization_band": latest_snap.utilization_band if latest_snap else None,
                "risk_type": "burnout_risk",
            })
    return risks


def detect_workload_concentration(db: Session) -> List[Dict[str, Any]]:
    """Flag projects where >40% of tasks are assigned to a single employee."""
    from app.models.project import Project

    active_projects = db.query(Project).filter(Project.status == "active").all()
    concentrations = []

    for project in active_projects:
        total_tasks = (
            db.query(func.count(Task.id))
            .filter(
                Task.project_id == project.id,
                Task.status.in_(["open", "in_progress"]),
            )
            .scalar()
        ) or 0

        if total_tasks < 3:
            continue

        # Count tasks per user for this project
        task_counts = (
            db.query(Task.assigned_to, func.count(Task.id).label("cnt"))
            .filter(
                Task.project_id == project.id,
                Task.assigned_to.isnot(None),
                Task.status.in_(["open", "in_progress"]),
            )
            .group_by(Task.assigned_to)
            .all()
        )

        for user_id, count in task_counts:
            ratio = count / total_tasks
            if ratio > CONCENTRATION_THRESHOLD:
                # FIX: Use Session.get() instead of deprecated Query.get()
                user = db.get(User, user_id)
                concentrations.append({
                    "project_id": project.id,
                    "project_name": project.name,
                    "user_id": user_id,
                    "user_name": user.name if user else "Unknown",
                    "task_count": count,
                    "total_project_tasks": total_tasks,
                    "concentration_ratio": round(ratio, 2),
                    "risk_type": "workload_concentration",
                })

    return concentrations


def detect_unassigned_high_priority(db: Session) -> List[Dict[str, Any]]:
    """Detect projects with unassigned high-priority tasks (resource gap signal)."""
    from app.models.project import Project

    unassigned = (
        db.query(Task, Project.name.label("project_name"))
        .join(Project, Task.project_id == Project.id)
        .filter(
            Task.assigned_to.is_(None),
            Task.priority == 1,
            Task.status.in_(["open", "in_progress"]),
            Project.status == "active",
        )
        .all()
    )

    results = []
    for task, project_name in unassigned:
        results.append({
            "task_id": task.id,
            "task_title": task.title,
            "project_id": task.project_id,
            "project_name": project_name,
            "due_date": task.due_date,
            "risk_type": "unassigned_high_priority",
        })
    return results


def compute_team_health_summary(db: Session) -> Dict[str, Any]:
    """Aggregate team health signals into a single summary dict."""
    burnout_risks = detect_burnout_risks(db)
    concentrations = detect_workload_concentration(db)
    unassigned_gaps = detect_unassigned_high_priority(db)

    total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0

    return {
        "total_active_users": total_users,
        "burnout_risk_count": len(burnout_risks),
        "workload_concentration_count": len(concentrations),
        "unassigned_high_priority_count": len(unassigned_gaps),
        "burnout_risks": burnout_risks,
        "workload_concentrations": concentrations,
        "unassigned_gaps": unassigned_gaps,
    }
