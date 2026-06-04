from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ── Utilization ───────────────────────────────────────────────────────────────

class UtilizationSnapshotOut(BaseModel):
    id: UUID
    user_id: UUID
    snapshot_date: date
    window_weeks: int
    capacity_hours: Optional[float] = None
    allocated_hours: Optional[float] = None
    logged_hours: Optional[float] = None
    utilization_pct: Optional[float] = None
    utilization_band: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserUtilizationSummary(BaseModel):
    user_id: UUID
    user_name: str
    user_email: str
    current_utilization_pct: Optional[float] = None
    utilization_band: Optional[str] = None
    capacity_hours_per_week: float
    allocated_hours: Optional[float] = None
    consecutive_overload_weeks: int = 0
    trend: Optional[List[UtilizationSnapshotOut]] = None


class TeamUtilizationOverview(BaseModel):
    total_users: int
    underutilized_count: int
    optimal_count: int
    overloaded_count: int
    critical_count: int
    average_utilization_pct: float
    users: List[UserUtilizationSummary]


# ── Project Health ────────────────────────────────────────────────────────────

class ProjectHealthScoreOut(BaseModel):
    id: UUID
    project_id: UUID
    scored_at: datetime
    overall_score: Optional[float] = None
    schedule_score: Optional[float] = None
    resource_score: Optional[float] = None
    velocity_score: Optional[float] = None
    risk_level: Optional[str] = None
    health_band: Optional[str] = None

    class Config:
        from_attributes = True


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationOut(BaseModel):
    id: UUID
    type: str
    source_user_id: Optional[UUID] = None
    source_user_name: Optional[str] = None
    source_user_current_util: Optional[float] = None
    target_user_id: Optional[UUID] = None
    target_user_name: Optional[str] = None
    target_user_current_util: Optional[float] = None
    task_id: Optional[UUID] = None
    task_title: Optional[str] = None
    task_estimated_hours: Optional[float] = None
    projected_source_util: Optional[float] = None
    projected_target_util: Optional[float] = None
    impact_score: Optional[float] = None
    confidence_score: Optional[float] = None
    status: str
    rationale: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecommendationReviewRequest(BaseModel):
    idempotency_key: Optional[str] = None


class RecommendationDeferRequest(BaseModel):
    reason: Optional[str] = None


# ── Analytics Aggregates ──────────────────────────────────────────────────────

class WorkloadDistributionOut(BaseModel):
    snapshot_date: date
    users: List[UserUtilizationSummary]
    band_distribution: dict


class ProjectPortfolioHealthOut(BaseModel):
    scored_at: datetime
    total_projects: int
    healthy_count: int
    at_risk_count: int
    critical_count: int
    average_health_score: float
    projects: List[dict]


class DeliveryRiskOut(BaseModel):
    project_id: UUID
    project_name: str
    risk_level: str
    days_to_next_milestone: Optional[int] = None
    overdue_milestone_count: int
    health_score: Optional[float] = None


# ── Sync ─────────────────────────────────────────────────────────────────────

class SyncStatusOut(BaseModel):
    entity_type: str
    last_synced_at: Optional[datetime] = None
    last_sync_count: Optional[int] = None
    last_sync_status: str
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class SyncTriggerResponse(BaseModel):
    message: str
    task_id: str
