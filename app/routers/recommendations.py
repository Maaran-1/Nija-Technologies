from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import json
import uuid
import structlog

from app.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.exceptions import NotFoundError
from app.core.responses import success_response, paginated_response
from app.models.recommendation import Recommendation, AuditLog
from app.models.user import User
from app.models.task import Task
from app.schemas.analytics import RecommendationOut, RecommendationReviewRequest, RecommendationDeferRequest

router = APIRouter()
logger = structlog.get_logger()


def _enrich_recommendation(rec: Recommendation, db: Session) -> dict:
    """Add user names and task title to a recommendation dict."""
    data = RecommendationOut.model_validate(rec).model_dump()

    if rec.source_user_id:
        src = db.query(User).filter(User.id == rec.source_user_id).first()
        data["source_user_name"] = src.name if src else None
        # Get current utilization
        from app.models.analytics import UtilizationSnapshot
        snap = (
            db.query(UtilizationSnapshot)
            .filter(UtilizationSnapshot.user_id == rec.source_user_id)
            .order_by(UtilizationSnapshot.snapshot_date.desc())
            .first()
        )
        data["source_user_current_util"] = float(snap.utilization_pct or 0) if snap else None

    if rec.target_user_id:
        tgt = db.query(User).filter(User.id == rec.target_user_id).first()
        data["target_user_name"] = tgt.name if tgt else None
        from app.models.analytics import UtilizationSnapshot
        snap = (
            db.query(UtilizationSnapshot)
            .filter(UtilizationSnapshot.user_id == rec.target_user_id)
            .order_by(UtilizationSnapshot.snapshot_date.desc())
            .first()
        )
        data["target_user_current_util"] = float(snap.utilization_pct or 0) if snap else None

    if rec.task_id:
        task = db.query(Task).filter(Task.id == rec.task_id).first()
        data["task_title"] = task.title if task else None
        data["task_estimated_hours"] = float(task.estimated_hours or 0) if task else None

    return data


@router.get("", response_model=dict)
def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query("pending"),
    type: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recommendations with optional status and type filters."""
    query = db.query(Recommendation)
    if status:
        query = query.filter(Recommendation.status == status)
    if type:
        query = query.filter(Recommendation.type == type)

    query = query.order_by(Recommendation.impact_score.desc(), Recommendation.created_at.desc())
    total = query.count()
    recs = query.offset((page - 1) * page_size).limit(page_size).all()

    return paginated_response(
        [_enrich_recommendation(r, db) for r in recs],
        page, page_size, total,
    )


@router.get("/{rec_id}", response_model=dict)
def get_recommendation(
    rec_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single recommendation by ID."""
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise NotFoundError("Recommendation", rec_id)
    return success_response(_enrich_recommendation(rec, db))


@router.post("/{rec_id}/approve", response_model=dict)
def approve_recommendation(
    rec_id: str,
    payload: RecommendationReviewRequest = RecommendationReviewRequest(),
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Approve a recommendation, updating task assignment in DB."""
    from datetime import datetime, timezone

    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise NotFoundError("Recommendation", rec_id)

    if rec.status != "pending":
        from app.core.exceptions import ConflictError
        raise ConflictError(f"Recommendation is already {rec.status}")

    # Apply the task reassignment
    if rec.task_id and rec.target_user_id:
        task = db.query(Task).filter(Task.id == rec.task_id).first()
        if task:
            task.assigned_to = rec.target_user_id

    rec.status = "approved"
    rec.reviewed_by = current_user.id
    rec.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        action="recommendation_approved",
        actor_id=current_user.id,
        entity_type="recommendation",
        entity_id=rec.id,
        metadata=json.dumps({"rec_id": str(rec_id), "task_id": str(rec.task_id)}),
    )
    db.add(audit)
    db.commit()

    logger.info("recommendation_approved", rec_id=rec_id, actor=str(current_user.id))
    return success_response(_enrich_recommendation(rec, db))


@router.post("/{rec_id}/reject", response_model=dict)
def reject_recommendation(
    rec_id: str,
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Reject a pending recommendation."""
    from datetime import datetime, timezone

    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise NotFoundError("Recommendation", rec_id)

    if rec.status != "pending":
        from app.core.exceptions import ConflictError
        raise ConflictError(f"Recommendation is already {rec.status}")

    rec.status = "rejected"
    rec.reviewed_by = current_user.id
    rec.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    audit = AuditLog(
        id=uuid.uuid4(),
        action="recommendation_rejected",
        actor_id=current_user.id,
        entity_type="recommendation",
        entity_id=rec.id,
        metadata=json.dumps({"rec_id": str(rec_id)}),
    )
    db.add(audit)
    db.commit()

    logger.info("recommendation_rejected", rec_id=rec_id, actor=str(current_user.id))
    return success_response(_enrich_recommendation(rec, db))


@router.post("/{rec_id}/defer", response_model=dict)
def defer_recommendation(
    rec_id: str,
    payload: RecommendationDeferRequest = RecommendationDeferRequest(),
    current_user=Depends(require_role("admin", "manager")),
    db: Session = Depends(get_db),
):
    """Defer a pending recommendation for later review."""
    from datetime import datetime, timezone

    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise NotFoundError("Recommendation", rec_id)

    rec.status = "deferred"
    rec.reviewed_by = current_user.id
    rec.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("recommendation_deferred", rec_id=rec_id, reason=payload.reason)
    return success_response(_enrich_recommendation(rec, db))


@router.post("/generate", response_model=dict)
def trigger_recommendation_generation(
    current_user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Manually trigger recommendation engine."""
    from app.recommendations.engine import generate_recommendations
    count = generate_recommendations(db)
    logger.info("recommendations_generated_manually", count=count)
    return success_response({"recommendations_created": count})
