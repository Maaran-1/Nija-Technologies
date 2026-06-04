from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
import structlog

from app.models.user import User
from app.models.task import Task
from app.models.analytics import UtilizationSnapshot

logger = structlog.get_logger()


def simulate_impact(
    source_snap: UtilizationSnapshot,
    target_snap: UtilizationSnapshot,
    task: Task,
) -> Tuple[float, float, float]:
    """
    Compute projected utilization for source and target after reassignment.
    Returns (projected_source_util, projected_target_util, impact_score).
    impact_score = source_util_improvement - (target_util_cost * 0.5).
    """
    task_hours = float(task.estimated_hours or 0)
    source_capacity = float(source_snap.capacity_hours or 80)
    target_capacity = float(target_snap.capacity_hours or 80)

    source_current = float(source_snap.utilization_pct or 0)
    target_current = float(target_snap.utilization_pct or 0)

    if source_capacity > 0:
        source_reduction_pct = (task_hours / source_capacity) * 100
    else:
        source_reduction_pct = 0

    if target_capacity > 0:
        target_increase_pct = (task_hours / target_capacity) * 100
    else:
        target_increase_pct = 0

    projected_source = max(0.0, source_current - source_reduction_pct)
    projected_target = target_current + target_increase_pct

    # Impact score: net utilization improvement (source relief minus target cost)
    impact_score = source_reduction_pct - (target_increase_pct * 0.5)
    impact_score = max(0.0, round(impact_score, 2))

    return round(projected_source, 2), round(projected_target, 2), impact_score


def compute_confidence_score(
    task: Task,
    recipient_data: Dict[str, Any],
    impact_score: float,
) -> float:
    """
    Compute confidence score 0-100 for a recommendation.
    Reduced when: skill match is inferred, recipient has no category history,
    imminent due date, or marginal impact.
    """
    score = 100.0

    # Skill match quality
    skill_score = recipient_data.get("skill_score", 50.0)
    if skill_score < 40:
        score -= 25  # No skill evidence
    elif skill_score < 65:
        score -= 10  # Weak skill inference

    # Project familiarity
    familiarity = recipient_data.get("familiarity_score", 30.0)
    if familiarity < 40:
        score -= 10  # No project context

    # Historical completion rate
    completion_rate = recipient_data.get("completion_rate", 50.0)
    if completion_rate < 60:
        score -= 10

    # Marginal impact penalty
    if impact_score < 5.0:
        score -= 20
    elif impact_score < 10.0:
        score -= 10

    # No due date info = slightly less certain
    if task.due_date is None:
        score -= 5

    return max(0.0, min(100.0, round(score, 1)))
