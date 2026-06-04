import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, Numeric, DateTime, SmallInteger, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Task(Base):
    """Zoho-sourced task data."""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zoho_task_id = Column(String(100), unique=True, nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(50), default="open")  # open, in_progress, completed, on_hold
    priority = Column(SmallInteger)  # 1=high, 2=medium, 3=low
    estimated_hours = Column(Numeric(6, 2))
    actual_hours = Column(Numeric(6, 2))  # derived from timesheet sum
    due_date = Column(Date)
    completed_at = Column(DateTime(timezone=True))
    tags = Column(Text)  # comma-separated tags for skill inference
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to])
    timesheet_entries = relationship("TimesheetEntry", back_populates="task")
    recommendations = relationship("Recommendation", back_populates="task")

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_due_date", "due_date"),
        Index("ix_tasks_project_assignee", "project_id", "assigned_to"),
    )

    def __repr__(self):
        return f"<Task id={self.id} title={self.title[:50]} status={self.status}>"
