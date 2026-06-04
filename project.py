import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, Numeric, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    """Zoho-sourced project data."""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zoho_project_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active, on_hold, completed, cancelled
    start_date = Column(Date)
    end_date = Column(Date)
    budget_hours = Column(Numeric(8, 2))
    description = Column(Text)
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks = relationship("Task", back_populates="project")
    milestones = relationship("Milestone", back_populates="project")
    health_scores = relationship("ProjectHealthScore", back_populates="project",
                                 order_by="ProjectHealthScore.scored_at.desc()")

    __table_args__ = (
        Index("ix_projects_status", "status"),
    )

    def __repr__(self):
        return f"<Project id={self.id} name={self.name} status={self.status}>"
