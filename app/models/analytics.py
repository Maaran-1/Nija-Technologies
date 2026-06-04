import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, Numeric, DateTime, SmallInteger, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UtilizationSnapshot(Base):
    """Time-series utilization record per user per day."""
    __tablename__ = "utilization_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    window_weeks = Column(SmallInteger, default=2)
    capacity_hours = Column(Numeric(6, 2))
    allocated_hours = Column(Numeric(6, 2))
    logged_hours = Column(Numeric(6, 2))
    utilization_pct = Column(Numeric(5, 2))
    utilization_band = Column(String(20))  # underutilized, optimal, overloaded, critical
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="utilization_snapshots")

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", "window_weeks", name="uq_utilization_snapshot"),
        Index("ix_utilization_band", "utilization_band"),
        Index("ix_utilization_user_date", "user_id", "snapshot_date"),
    )

    def __repr__(self):
        return f"<UtilizationSnapshot user={self.user_id} date={self.snapshot_date} pct={self.utilization_pct}>"


class ProjectHealthScore(Base):
    """Composite project health score records."""
    __tablename__ = "project_health_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    scored_at = Column(DateTime(timezone=True), nullable=False, index=True)
    overall_score = Column(Numeric(5, 2))
    schedule_score = Column(Numeric(5, 2))
    resource_score = Column(Numeric(5, 2))
    velocity_score = Column(Numeric(5, 2))
    risk_level = Column(String(20))  # low, medium, high, critical
    health_band = Column(String(20))  # healthy, at_risk, at_risk_high, critical

    # Relationships
    project = relationship("Project", back_populates="health_scores")

    __table_args__ = (
        Index("ix_health_scores_project_scored", "project_id", "scored_at"),
    )

    def __repr__(self):
        return f"<ProjectHealthScore project={self.project_id} score={self.overall_score} scored_at={self.scored_at}>"


class SyncMetadata(Base):
    """Tracks last successful sync per entity type for delta-sync."""
    __tablename__ = "sync_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), unique=True, nullable=False)  # users, projects, tasks, timesheets, milestones
    last_synced_at = Column(DateTime(timezone=True))
    last_sync_count = Column(SmallInteger, default=0)
    last_sync_status = Column(String(20), default="pending")  # success, failed, running
    last_error = Column(String(500))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SyncMetadata entity={self.entity_type} last_synced={self.last_synced_at}>"
