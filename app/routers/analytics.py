from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import structlog

from app.database import get_db
from app.core.auth import get_current_user
from app.core.responses import success_response
from app.models.project import Project
from app.models.analytics import ProjectHealthScore, UtilizationSnapshot
from app.models.recommendation import Recommendation
from app.analytics.team_health import compute_team_health_summary

router = APIRouter()
logger = structlog.get_logger()


@router.get("/dashboard", response_model=dict)
def get_executive_dashboard(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executive dashboard: team health, project portfolio overview,
    utilization distribution, and pending recommendations count.
    """
    from app.models.user import User

    # Get the latest snapshot per user via GROUP BY subquery
    latest_dates = (
        db.query(
            UtilizationSnapshot.user_id,
            func.max(UtilizationSnapshot.snapshot_date).label("max_date"),
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

    band_counts = {"underutilized": 0, "optimal": 0, "overloaded": 0, "critical": 0}
    total_util = 0.0
    for snap in latest_snaps:
        band = snap.utilization_band or "underutilized"
        if band in band_counts:
            band_counts[band] += 1
        total_util += float(snap.utilization_pct or 0)

    total_users = len(latest_snaps)
    avg_util = round(total_util / total_users, 2) if total_users > 0 else 0.0

    # Project health distribution
    active_projects = db.query(Project).filter(Project.status == "active").all()
    project_health = {"healthy": 0, "at_risk": 0, "at_risk_high": 0, "critical": 0}
    total_health_score = 0.0
    health_count = 0

    for project in active_projects:
        latest_score = (
            db.query(ProjectHealthScore)
            .filter(ProjectHealthScore.project_id == project.id)
            .order_by(ProjectHealthScore.scored_at.desc())
            .first()
        )
        if latest_score:
            band = latest_score.health_band or "healthy"
            if band in project_health:
                project_health[band] += 1
            total_health_score += float(latest_score.overall_score or 0)
            health_count += 1

    avg_health = round(total_health_score / health_count, 2) if health_count > 0 else 0.0

    # Pending recommendations count
    pending_recs = (
        db.query(func.count(Recommendation.id))
        .filter(Recommendation.status == "pending")
        .scalar()
    ) or 0

    # Team health signals
    team_health = compute_team_health_summary(db)

    return success_response({
        "utilization": {
            "total_users": total_users,
            "average_pct": avg_util,
            "distribution": band_counts,
        },
        "projects": {
            "total_active": len(active_projects),
            "average_health_score": avg_health,
            "health_distribution": project_health,
        },
        "recommendations": {
            "pending_count": pending_recs,
        },
        "team_health": {
            "burnout_risk_count": team_health["burnout_risk_count"],
            "workload_concentration_count": team_health["workload_concentration_count"],
            "unassigned_high_priority_count": team_health["unassigned_high_priority_count"],
        },
    })


@router.get("/portfolio-health", response_model=dict)
def get_portfolio_health(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Project portfolio health with latest scores for all active projects."""
    projects = db.query(Project).filter(Project.status == "active").all()
    result = []

    for project in projects:
        score = (
            db.query(ProjectHealthScore)
            .filter(ProjectHealthScore.project_id == project.id)
            .order_by(ProjectHealthScore.scored_at.desc())
            .first()
        )
        result.append({
            "project_id": str(project.id),
            "project_name": project.name,
            "zoho_project_id": project.zoho_project_id,
            "status": project.status,
            "end_date": str(project.end_date) if project.end_date else None,
            "overall_score": float(score.overall_score or 0) if score else None,
            "schedule_score": float(score.schedule_score or 0) if score else None,
            "resource_score": float(score.resource_score or 0) if score else None,
            "velocity_score": float(score.velocity_score or 0) if score else None,
            "health_band": score.health_band if score else None,
            "risk_level": score.risk_level if score else None,
            "scored_at": str(score.scored_at) if score else None,
        })

    # Sort by score ascending (worst-performing projects first)
    result.sort(key=lambda x: x.get("overall_score") or 100.0)

    return success_response({
        "total_projects": len(result),
        "projects": result,
    })


@router.get("/team-health", response_model=dict)
def get_team_health_signals(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detailed team health signals: burnout risks, concentration, unassigned gaps."""
    import uuid
    from datetime import date
    summary = compute_team_health_summary(db)

    def serialize(obj):
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [serialize(i) for i in obj]
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, date):
            return str(obj)
        return obj

    return success_response(serialize(summary))


@router.get("/workload-distribution", response_model=dict)
def get_workload_distribution(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current workload distribution across the entire team."""
    from app.models.user import User
    from datetime import date

    latest_dates = (
        db.query(
            UtilizationSnapshot.user_id,
            func.max(UtilizationSnapshot.snapshot_date).label("max_date"),
        )
        .group_by(UtilizationSnapshot.user_id)
        .subquery()
    )

    rows = (
        db.query(UtilizationSnapshot, User)
        .join(User, UtilizationSnapshot.user_id == User.id)
        .join(
            latest_dates,
            (UtilizationSnapshot.user_id == latest_dates.c.user_id)
            & (UtilizationSnapshot.snapshot_date == latest_dates.c.max_date),
        )
        .filter(User.is_active == True)
        .all()
    )

    users = []
    for snap, user in rows:
        users.append({
            "user_id": str(user.id),
            "user_name": user.name,
            "role": user.role,
            "utilization_pct": float(snap.utilization_pct or 0),
            "utilization_band": snap.utilization_band,
            "allocated_hours": float(snap.allocated_hours or 0),
            "capacity_hours": float(snap.capacity_hours or 80),
            "snapshot_date": str(snap.snapshot_date),
        })

    users.sort(key=lambda x: x["utilization_pct"], reverse=True)

    return success_response({
        "snapshot_date": str(date.today()),
        "total_users": len(users),
        "users": users,
    })
