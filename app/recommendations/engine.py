from datetime import datetime, timezone
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session
import uuid
import structlog

from app.config import settings
from app.models.recommendation import Recommendation
from app.models.analytics import UtilizationSnapshot
from app.recommendations.candidate_selector import get_overloaded_users, get_candidate_tasks
from app.recommendations.recipient_matcher import score_recipients
from app.recommendations.impact_simulator import simulate_impact, compute_confidence_score
from app.recommendations.explainer import build_rationale

logger = structlog.get_logger()


def _get_user_latest_snapshot(db: Session, user_id) -> UtilizationSnapshot:
    """Return the most recent UtilizationSnapshot for a user, or None."""
    return (
        db.query(UtilizationSnapshot)
        .filter(UtilizationSnapshot.user_id == user_id)
        .order_by(UtilizationSnapshot.snapshot_date.desc())
        .first()
    )


def generate_recommendations(db: Session, max_recommendations: int = None) -> int:
    """
    Full recommendation generation pipeline:
    1. Find overloaded users (latest snapshot = overloaded or critical)
    2. Find candidate tasks (open/in_progress, not imminent, has estimated_hours)
    3. Score eligible recipients (by available capacity, skill, familiarity, etc.)
    4. Simulate impact (projected utilization delta)
    5. Build human-readable rationale
    6. Persist to recommendations table (upsert on existing pending rec for same task+target)

    Returns count of new recommendations created or updated.
    """
    if max_recommendations is None:
        max_recommendations = settings.RECOMMENDATION_BATCH_SIZE

    logger.info("recommendation_generation_start", max_recs=max_recommendations)

    overloaded_users = get_overloaded_users(db)
    logger.info("overloaded_users_found", count=len(overloaded_users))

    created_count = 0
    seen_task_ids: set = set()  # Prevent duplicate recommendations for the same task

    for source_user in overloaded_users:
        source_snap = _get_user_latest_snapshot(db, source_user.id)
        if not source_snap:
            continue

        candidate_tasks = get_candidate_tasks(db, source_user)

        for task in candidate_tasks:
            if str(task.id) in seen_task_ids:
                continue
            if created_count >= max_recommendations:
                break

            recipients = score_recipients(db, task, exclude_user_id=source_user.id)
            if not recipients:
                continue

            # Take the highest-scoring recipient
            best = recipients[0]
            target_user = best["user"]
            target_snap = best["snapshot"]

            projected_source, projected_target, impact_score = simulate_impact(
                source_snap, target_snap, task
            )

            # Only generate if impact is meaningful
            if impact_score < settings.MIN_IMPACT_SCORE:
                continue

            confidence = compute_confidence_score(task, best, impact_score)

            rationale = build_rationale(
                db=db,
                source_user=source_user,
                target_user=target_user,
                task=task,
                source_snap=source_snap,
                target_snap=target_snap,
                projected_source_util=projected_source,
                projected_target_util=projected_target,
                confidence_score=confidence,
            )

            # Check if an identical pending recommendation already exists for this task + target
            existing = (
                db.query(Recommendation)
                .filter(
                    Recommendation.task_id == task.id,
                    Recommendation.target_user_id == target_user.id,
                    Recommendation.status == "pending",
                )
                .first()
            )
            if existing:
                # Update scores on the existing recommendation instead of creating a duplicate
                existing.impact_score = impact_score
                existing.confidence_score = confidence
                existing.projected_source_util = projected_source
                existing.projected_target_util = projected_target
                existing.rationale = rationale
                db.commit()
                seen_task_ids.add(str(task.id))
                continue

            rec = Recommendation(
                id=uuid.uuid4(),
                type="task_reassignment",
                source_user_id=source_user.id,
                target_user_id=target_user.id,
                task_id=task.id,
                projected_source_util=projected_source,
                projected_target_util=projected_target,
                impact_score=impact_score,
                confidence_score=confidence,
                status="pending",
                rationale=rationale,
                created_at=datetime.now(timezone.utc),
            )
            db.add(rec)
            seen_task_ids.add(str(task.id))
            created_count += 1

        if created_count >= max_recommendations:
            break

    db.commit()
    logger.info("recommendation_generation_complete", created=created_count)
    return created_count
