from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.exceptions import NotFoundError
from app.core.responses import success_response, paginated_response
from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import Milestone
from app.models.analytics import ProjectHealthScore
from app.schemas.project import ProjectOut, ProjectWithHealth, TaskOut, MilestoneOut

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=dict)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all projects with optional status filter and latest health score."""
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)

    total = query.count()
    projects = query.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for project in projects:
        data = ProjectWithHealth.model_validate(project).model_dump()
        latest_health = (
            db.query(ProjectHealthScore)
            .filter(ProjectHealthScore.project_id == project.id)
            .order_by(ProjectHealthScore.scored_at.desc())
            .first()
        )
        if latest_health:
            data["latest_health_score"] = float(latest_health.overall_score or 0)
            data["health_band"] = latest_health.health_band
            data["risk_level"] = latest_health.risk_level
        result.append(data)

    return paginated_response(result, page, page_size, total)


@router.get("/{project_id}", response_model=dict)
def get_project(
    project_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single project with full health history."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("Project", project_id)

    data = ProjectOut.model_validate(project).model_dump()

    health_scores = (
        db.query(ProjectHealthScore)
        .filter(ProjectHealthScore.project_id == project.id)
        .order_by(ProjectHealthScore.scored_at.desc())
        .limit(10)
        .all()
    )
    data["health_history"] = [
        {
            "scored_at": str(h.scored_at),
            "overall_score": float(h.overall_score or 0),
            "schedule_score": float(h.schedule_score or 0),
            "resource_score": float(h.resource_score or 0),
            "velocity_score": float(h.velocity_score or 0),
            "health_band": h.health_band,
            "risk_level": h.risk_level,
        }
        for h in health_scores
    ]

    return success_response(data)


@router.get("/{project_id}/tasks", response_model=dict)
def get_project_tasks(
    project_id: str,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tasks for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("Project", project_id)

    query = db.query(Task).filter(Task.project_id == project_id)
    if status:
        query = query.filter(Task.status == status)

    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()

    return paginated_response(
        [TaskOut.model_validate(t).model_dump() for t in tasks],
        page, page_size, total,
    )


@router.get("/{project_id}/milestones", response_model=dict)
def get_project_milestones(
    project_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List milestones for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("Project", project_id)

    milestones = (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id)
        .order_by(Milestone.due_date.asc())
        .all()
    )

    return success_response([MilestoneOut.model_validate(m).model_dump() for m in milestones])


@router.post("/{project_id}/score", response_model=dict)
def trigger_project_scoring(
    project_id: str,
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Manually trigger health scoring for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("Project", project_id)

    from app.analytics.project_scorer import score_project
    score = score_project(db, project)
    logger.info("project_scored_manually", project_id=project_id, score=float(score.overall_score))

    return success_response({
        "project_id": str(project.id),
        "overall_score": float(score.overall_score or 0),
        "health_band": score.health_band,
        "risk_level": score.risk_level,
        "scored_at": str(score.scored_at),
    })
