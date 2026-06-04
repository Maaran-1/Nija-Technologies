import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Date, Numeric, DateTime, Boolean, ForeignKey, CheckConstraint, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class TimesheetEntry(Base):
    """Zoho-sourced timesheet log entries."""
    __tablename__ = "timesheet_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zoho_entry_id = Column(String(100), unique=True, nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    hours_logged = Column(Numeric(5, 2), nullable=False)
    notes = Column(Text)
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = relationship("Task", back_populates="timesheet_entries")
    user = relationship("User", back_populates="timesheet_entries")

    __table_args__ = (
        CheckConstraint("hours_logged > 0", name="check_hours_positive"),
        Index("ix_timesheet_user_date", "user_id", "work_date"),
        Index("ix_timesheet_task_user", "task_id", "user_id"),
    )

    def __repr__(self):
        return f"<TimesheetEntry user={self.user_id} date={self.work_date} hours={self.hours_logged}>"


class Milestone(Base):
    """Zoho-sourced project milestones."""
    __tablename__ = "milestones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zoho_milestone_id = Column(String(100), unique=True, nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    due_date = Column(Date)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="milestones")

    __table_args__ = (
        Index("ix_milestones_project_due", "project_id", "due_date"),
    )

    def __repr__(self):
        return f"<Milestone id={self.id} name={self.name} completed={self.is_completed}>"
